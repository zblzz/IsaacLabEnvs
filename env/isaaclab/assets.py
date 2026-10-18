"""Translate neutral assets to Lab configs; conversion stays behind this boundary."""

import hashlib
from pathlib import Path

import isaaclab.sim as sim
from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.assets import ArticulationCfg, AssetBaseCfg, RigidObjectCfg
from isaaclab.sim.converters import MeshConverter, MeshConverterCfg, UrdfConverter, UrdfConverterCfg
from pxr import Usd

from ..config import AssetCfg
from .urdf import prepare_urdf


def convert(cfg: AssetCfg, cache: Path) -> str:
    source = cfg.source.resolve()
    if source.suffix.lower() in (".usd", ".usda", ".usdc"):
        return str(source)
    # Include source path and conversion options, not project-specific robot identifiers.
    digest = hashlib.sha256((str(source) + repr(cfg)).encode()).hexdigest()[:16]
    directory = cache / digest
    if source.suffix.lower() == ".urdf":
        prepared = prepare_urdf(source, directory / "source.urdf", cfg)
        converter = UrdfConverter(
            UrdfConverterCfg(
                asset_path=str(prepared),
                usd_dir=str(directory / "usd"),
                fix_base=bool(cfg.fixed_base),
                merge_fixed_joints=cfg.merge_fixed_joints,
                convert_mimic_joints_to_normal_joints=False,
                self_collision=cfg.self_collision,
                joint_drive=UrdfConverterCfg.JointDriveCfg(
                    gains=UrdfConverterCfg.JointDriveCfg.PDGainsCfg(stiffness=0.0, damping=0.0)
                ),
            )
        )
    elif cfg.collision == "convex_parts":
        from .convex_parts import convex_parts_usd

        return str(convex_parts_usd(source, directory, cfg.scale))
    else:
        approximation = (
            sim.ConvexHullPropertiesCfg()
            if cfg.collision == "convex_hull"
            else sim.ConvexDecompositionPropertiesCfg()
        )
        converter = MeshConverter(
            MeshConverterCfg(
                asset_path=str(source),
                usd_dir=str(directory),
                scale=(cfg.scale,) * 3,
                make_instanceable=False,
                mesh_collision_props=approximation,
                rigid_props=sim.RigidBodyPropertiesCfg() if cfg.kind != "static" else None,
                collision_props=sim.CollisionPropertiesCfg(),
                mass_props=sim.MassPropertiesCfg(mass=cfg.mass) if cfg.kind != "static" else None,
            )
        )
    # Importer can produce mesh instances despite make_instanceable=False.
    # Deinstance cached output so spawn-time collision offsets can be authored.
    stage = Usd.Stage.Open(converter.usd_path)
    for prim in list(stage.Traverse()):
        if prim.IsInstance():
            prim.SetInstanceable(False)
    stage.GetRootLayer().Save()
    return converter.usd_path


def asset_config(name: str, cfg: AssetCfg, cache: Path):
    path = ("/World/" if cfg.shared else "{ENV_REGEX_NS}/") + name
    material = sim.RigidBodyMaterialCfg(
        static_friction=cfg.friction, dynamic_friction=cfg.friction, restitution=cfg.restitution
    )
    properties = dict(
        collision_props=sim.CollisionPropertiesCfg(
            collision_enabled=cfg.collision_enabled,
            contact_offset=cfg.contact_offset,
            rest_offset=cfg.rest_offset,
        ),
        physics_material=material,
    )
    if cfg.kind != "static":
        properties.update(
            activate_contact_sensors=True,
            rigid_props=sim.RigidBodyPropertiesCfg(
                kinematic_enabled=cfg.kinematic,
                disable_gravity=not cfg.gravity,
                linear_damping=cfg.linear_damping,
                angular_damping=cfg.angular_damping,
                enable_gyroscopic_forces=True,
                max_linear_velocity=cfg.max_linear_velocity,
                max_angular_velocity=cfg.max_angular_velocity,
                max_depenetration_velocity=cfg.max_depenetration_velocity,
                solver_position_iteration_count=cfg.position_iterations,
                solver_velocity_iteration_count=cfg.velocity_iterations,
            ),
        )
        if cfg.mass is not None:
            properties["mass_props"] = sim.MassPropertiesCfg(mass=cfg.mass)
    if cfg.kind == "articulation":
        properties["articulation_props"] = sim.ArticulationRootPropertiesCfg(
            fix_root_link=cfg.fixed_base,
            enabled_self_collisions=cfg.self_collision,
            solver_position_iteration_count=cfg.position_iterations,
            solver_velocity_iteration_count=cfg.velocity_iterations,
        )
    if cfg.source is None:
        spawn = sim.CuboidCfg(
            size=tuple(cfg.size),
            visual_material=sim.PreviewSurfaceCfg(diffuse_color=tuple(cfg.color)),
            **properties,
        )
    else:
        # USD spawners don't accept a material config. Dynamic materials are set
        # through PhysX after initialization; static USD materials are bound by Scene.
        properties.pop("physics_material")
        spawn = sim.UsdFileCfg(usd_path=convert(cfg, cache), **properties)
        if cfg.source.suffix.lower() in (".usd", ".usda", ".usdc", ".urdf"):
            spawn.scale = (cfg.scale,) * 3
    xyzw = cfg.quaternion
    pose = dict(pos=tuple(cfg.position), rot=(xyzw[3], *xyzw[:3]))
    if cfg.kind == "articulation":
        drives = {
            key: ImplicitActuatorCfg(
                joint_names_expr=list(value.joints),
                stiffness=value.stiffness,
                damping=value.damping,
                effort_limit_sim=value.effort_limit,
                velocity_limit_sim=value.velocity_limit,
            )
            for key, value in cfg.drives.items()
        }
        return ArticulationCfg(
            prim_path=path,
            spawn=spawn,
            actuators=drives,
            init_state=ArticulationCfg.InitialStateCfg(**pose, joint_pos=cfg.joints),
            soft_joint_pos_limit_factor=1.0,
        )
    if cfg.kind == "rigid":
        return RigidObjectCfg(prim_path=path, spawn=spawn, init_state=RigidObjectCfg.InitialStateCfg(**pose))
    return AssetBaseCfg(
        prim_path=path,
        spawn=spawn,
        init_state=AssetBaseCfg.InitialStateCfg(**pose),
        collision_group=-1 if cfg.shared else 0,
    )
