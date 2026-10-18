"""Vector physics, without task rewards, policy layouts or dataset dependencies."""

import isaaclab.sim as sim
import torch
from isaaclab.scene import InteractiveScene, InteractiveSceneCfg
from isaaclab.sensors import ContactSensorCfg

from ..config import SceneCfg
from ..contracts import Command, ResetState
from .appearance import add_lighting, bind_appearance, configure_renderer
from .assets import asset_config


def from_lab(state, origins):
    result = state.clone()
    result[..., :3] -= origins
    result[..., 3:7] = state[..., [4, 5, 6, 3]]
    return result


def to_lab(state, origins):
    result = state.clone()
    result[..., :3] += origins
    result[..., 3:7] = state[..., [6, 3, 4, 5]]
    return result


class Scene:
    def __init__(self, cfg: SceneCfg):
        self.cfg, self.num_envs, self.device = cfg, cfg.num_envs, cfg.device
        self.physics_dt, self.control_dt = cfg.physics_dt, cfg.control_dt
        self._bindings = {}
        self._closed = False
        self._annotator = None
        self._render_product = None
        self.sim = sim.SimulationContext(
            sim.SimulationCfg(
                device=cfg.device,
                dt=cfg.physics_dt,
                gravity=tuple(cfg.gravity),
                render_interval=cfg.decimation,
                physx=sim.PhysxCfg(
                    bounce_threshold_velocity=cfg.bounce_threshold,
                    gpu_max_rigid_patch_count=cfg.gpu_max_rigid_patch_count,
                    enable_external_forces_every_iteration=cfg.external_forces_every_iteration,
                ),
            )
        )
        scene_cfg = InteractiveSceneCfg(
            num_envs=cfg.num_envs, env_spacing=cfg.spacing, replicate_physics=True
        )
        add_lighting(scene_cfg, cfg.lighting)
        for name, asset in cfg.assets.items():
            if hasattr(scene_cfg, name):
                raise ValueError(f"Entity name conflicts with a scene configuration field: {name}")
            setattr(scene_cfg, name, asset_config(name, asset, cfg.cache))
        for name, contact in cfg.contacts.items():
            if hasattr(scene_cfg, "contact_" + name):
                raise ValueError(f"Sensor name conflicts with an entity: contact_{name}")
            suffix = "/" + contact.bodies if contact.bodies else ""
            setattr(
                scene_cfg,
                "contact_" + name,
                ContactSensorCfg(
                    prim_path="{ENV_REGEX_NS}/" + contact.entity + suffix,
                    filter_prim_paths_expr=["{ENV_REGEX_NS}/" + item for item in contact.filters],
                    history_length=contact.history_length,
                    update_period=0.0,
                ),
            )
        self.scene = InteractiveScene(scene_cfg)
        for name, asset in cfg.assets.items():
            if asset.kind == "static" and asset.source is not None:
                material = sim.RigidBodyMaterialCfg(
                    static_friction=asset.friction,
                    dynamic_friction=asset.friction,
                    restitution=asset.restitution,
                )
                material_path = "/World/Materials/" + name
                material.func(material_path, material)
                roots = ["/World"] if asset.shared else self.scene.env_prim_paths
                for root in roots:
                    sim.bind_physics_material(root + "/" + name, material_path)
        bind_appearance(cfg.assets, self.scene.env_prim_paths)
        self.sim.reset()
        self._camera_path = "/OmniverseKit_Persp"
        if cfg.camera_focal_length is not None:
            from omni.kit.viewport.utility import get_active_viewport
            from pxr import UsdGeom

            # A dedicated camera avoids the viewport controller resetting focal length.
            self._camera_path = "/World/OverviewCamera"
            camera = UsdGeom.Camera.Define(self.sim.stage, self._camera_path)
            camera.GetFocalLengthAttr().Set(cfg.camera_focal_length)
            camera.GetHorizontalApertureAttr().Set(36.0)
            camera.GetVerticalApertureAttr().Set(36.0 * cfg.resolution[1] / cfg.resolution[0])
            camera.GetClippingRangeAttr().Set((0.01, 1000.0))
            viewport = get_active_viewport()
            if viewport is not None:
                viewport.camera_path = self._camera_path
        self.sim.set_camera_view(cfg.camera_eye, cfg.camera_target, self._camera_path)
        configure_renderer(cfg.renderer)
        self.entities = {**self.scene.articulations, **self.scene.rigid_objects}
        self.ids = torch.arange(cfg.num_envs, device=cfg.device, dtype=torch.long)
        for name, asset in cfg.assets.items():
            if name in self.entities:
                self.set_friction(name, asset.friction, restitution=asset.restitution)
                if asset.center_of_mass is not None or asset.inertia_tensor is not None:
                    self.set_mass_properties(name, asset.center_of_mass, asset.inertia_tensor)
        for name, sensor_cfg in cfg.contacts.items():
            if sensor_cfg.filters and self.scene.sensors["contact_" + name].num_bodies != 1:
                raise ValueError(f"Pair-filtered sensor {name} must select exactly one body")
        self.reset()

    def binding(self, entity, names, kind):
        """Resolve ordered exact names once; regular expressions belong only in config."""
        if names is None:
            return slice(None)
        key = entity, tuple(names), kind
        if key not in self._bindings:
            available = getattr(self.entities[entity], kind + "_names")
            self._bindings[key] = [available.index(name) for name in names]
        return self._bindings[key]

    def step(self, commands: dict[str, Command]):
        wrenches = []
        for name, command in commands.items():
            entity = self.entities[name]
            for field in ("position", "velocity", "effort"):
                value = getattr(command, "joint_" + field)
                if value is not None:
                    indices = self.binding(name, command.joints, "joint")
                    count = len(command.joints) if command.joints is not None else entity.num_joints
                    if value.shape != (self.num_envs, count):
                        raise ValueError(f"{name}/joint_{field}: expected {(self.num_envs, count)}")
                    getattr(entity, "set_joint_" + field + "_target")(value, joint_ids=indices)
            if command.force is not None or command.torque is not None:
                body_ids = self.binding(name, command.bodies, "body")
                count = len(command.bodies) if command.bodies is not None else entity.num_bodies
                for value in (command.force, command.torque):
                    if value is not None and value.shape != (self.num_envs, count, 3):
                        raise ValueError(f"{name}/wrench: expected {(self.num_envs, count, 3)}")
                wrenches.append((entity, body_ids, command))
        for _ in range(self.cfg.decimation):
            for entity, body_ids, command in wrenches:
                entity.instantaneous_wrench_composer.set_forces_and_torques(
                    command.force, command.torque, body_ids=body_ids, is_global=True
                )
            self.scene.write_data_to_sim()
            self.sim.step(render=False)
            self.scene.update(self.physics_dt)
        if self.sim.has_gui():
            self.sim.render()
        return self.state()

    def write_state(self, states: dict[str, ResetState], *, env_ids=None):
        """Write physical state without resetting task state or advancing simulation time."""
        ids = self.ids if env_ids is None else env_ids
        for name, state in states.items():
            entity = self.entities[name]
            if state.root is not None:
                entity.write_root_state_to_sim(to_lab(state.root, self.scene.env_origins[ids]), ids)
            if state.joint_position is not None or state.joint_velocity is not None:
                indices = self.binding(name, state.joints, "joint")
                q = state.joint_position
                dq = state.joint_velocity
                if q is None:
                    q = entity.data.joint_pos[ids][:, indices]
                if dq is None:
                    dq = torch.zeros_like(q)
                entity.write_joint_state_to_sim(q, dq, joint_ids=indices, env_ids=ids)
                entity.set_joint_position_target(q, joint_ids=indices, env_ids=ids)
        self.sim.forward()
        self.scene.update(0.0)

    def reset(self, states: dict[str, ResetState] | None = None, *, env_ids=None):
        ids = self.ids if env_ids is None else env_ids
        for entity in self.entities.values():
            root = entity.data.default_root_state[ids].clone()
            root[:, :3] += self.scene.env_origins[ids]
            entity.write_root_state_to_sim(root, ids)
            if hasattr(entity.data, "joint_pos"):
                q = entity.data.default_joint_pos[ids]
                dq = entity.data.default_joint_vel[ids]
                entity.write_joint_state_to_sim(q, dq, env_ids=ids)
                entity.set_joint_position_target(q, env_ids=ids)
                entity.set_joint_velocity_target(torch.zeros_like(dq), env_ids=ids)
                entity.set_joint_effort_target(torch.zeros_like(dq), env_ids=ids)
        self.scene.reset(ids)
        self.write_state(states or {}, env_ids=ids)
        return self.state()

    def state(self):
        """Return owned tensor snapshots; reset and future steps cannot overwrite them."""
        result = {}
        for name, entity in self.entities.items():
            data = entity.data
            result[name] = dict(
                root=from_lab(data.root_state_w, self.scene.env_origins),
                bodies=from_lab(data.body_state_w, self.scene.env_origins[:, None]),
            )
            if name in self.scene.articulations:
                result[name].update(
                    joint_position=data.joint_pos.clone(),
                    joint_velocity=data.joint_vel.clone(),
                    joint_effort=data.applied_torque.clone(),
                )
        result["contacts"] = {}
        for name in self.cfg.contacts:
            data = self.scene.sensors["contact_" + name].data
            result["contacts"][name] = {"net_force": data.net_forces_w.clone()}
            if data.force_matrix_w is not None:
                result["contacts"][name]["pair_force"] = data.force_matrix_w.clone()
        return result

    def set_friction(self, name, coefficient, *, restitution=None):
        view = self.entities[name].root_physx_view
        properties = view.get_material_properties()
        properties[..., :2] = coefficient
        if restitution is not None:
            properties[..., 2] = restitution
        view.set_material_properties(properties, torch.arange(self.num_envs))

    def set_mass_properties(self, name, center_of_mass=None, inertia_tensor=None):
        entity = self.entities[name]
        if name in self.scene.articulations:
            raise ValueError("Articulation inertias belong in the source asset; override rigid bodies only")
        view = entity.root_physx_view
        indices = torch.arange(self.num_envs, dtype=torch.int32)
        if center_of_mass is not None:
            coms = view.get_coms()
            coms[:, :3] = torch.tensor(center_of_mass)
            view.set_coms(coms, indices)
        if inertia_tensor is not None:
            inertia = torch.tensor(inertia_tensor).T.contiguous().reshape(1, 9)
            view.set_inertias(inertia.repeat(self.num_envs, 1), indices)

    def describe(self):
        assets = {}
        for name, entity in self.entities.items():
            data = dict(bodies=list(entity.body_names), mass=entity.root_physx_view.get_masses()[0].tolist())
            if name in self.scene.articulations:
                data.update(
                    joints=list(entity.joint_names), joint_limits=entity.data.joint_pos_limits[0].tolist()
                )
            assets[name] = data
        return dict(
            backend="isaaclab",
            implementation=__file__,
            num_envs=self.num_envs,
            physics_dt=self.physics_dt,
            control_dt=self.control_dt,
            quaternion="xyzw",
            position_frame="environment",
            wrench_frame="world",
            autoreset=False,
            assets=assets,
            contacts={
                key: list(self.scene.sensors["contact_" + key].body_names) for key in self.cfg.contacts
            },
        )

    def present(self):
        """Update the interactive viewport without copying RGB pixels to the CPU."""
        self.sim.render()

    def render(self, *, settle_frames=0):
        """Overview RGB. Extra settling frames update rendering only, never physics."""
        if self.sim.render_mode.value < self.sim.RenderMode.PARTIAL_RENDERING.value:
            raise RuntimeError("Open Runtime with cameras=True before requesting RGB")
        if self._annotator is None:
            import omni.replicator.core as rep

            self._render_product = rep.create.render_product(self._camera_path, self.cfg.resolution)
            self._annotator = rep.AnnotatorRegistry.get_annotator("rgb", device="cpu")
            self._annotator.attach([self._render_product])
            for _ in range(4):
                self.sim.render()
        for _ in range(settle_frames):
            self.sim.render()
        self.sim.render()
        return self._annotator.get_data()[..., :3].copy()

    def close(self):
        if not self._closed:
            if self._annotator is not None:
                self._annotator.detach()
                self._render_product.destroy()
            # Release scene subscriptions before clearing the simulation singleton,
            # following Lab's environment teardown order. Runtime owns app shutdown.
            self.entities.clear()
            del self.scene
            self.sim.clear_all_callbacks()
            self.sim.clear_instance()
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
