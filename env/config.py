"""Serializable scene configuration. Relative paths are relative to the YAML file."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class DriveCfg:
    joints: tuple[str, ...] = (".*",)
    stiffness: float = 100.0
    damping: float = 10.0
    effort_limit: float | None = None
    velocity_limit: float | None = None


@dataclass(frozen=True)
class LightingCfg:
    """Uniform fill plus a directional key. Key orientation uses xyzw; emission is local -Z."""

    ambient_intensity: float = 300.0
    environment_texture: Path | None = None
    environment_quaternion: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)
    environment_visible: bool = True
    key_intensity: float = 1000.0
    key_angle: float = 8.0
    key_quaternion: tuple[float, float, float, float] = (0.2391176, -0.3696438, -0.0990458, 0.8923991)


@dataclass(frozen=True)
class VisualMaterialCfg:
    """Optional appearance override; never changes friction or source asset files."""

    color: tuple[float, float, float] = (0.3, 0.3, 0.3)
    roughness: float = 0.65
    metallic: float = 0.0
    shader: Literal["preview", "omnipbr"] = "preview"
    roughness_texture: Path | None = None
    roughness_texture_weight: float = 1.0
    texture_scale: tuple[float, float] = (1.0, 1.0)

    def __post_init__(self):
        if self.shader not in ("preview", "omnipbr"):
            raise ValueError(f"Unknown visual shader: {self.shader}")
        if self.roughness_texture is not None and self.shader != "omnipbr":
            raise ValueError("Roughness textures require shader=omnipbr")


@dataclass(frozen=True)
class RendererCfg:
    """Optional capture profile. Samples accumulate while the scene is stationary."""

    mode: Literal["realtime", "path_tracing"] = "realtime"
    samples_per_frame: int = 16
    total_samples: int = 128
    max_bounces: int = 6
    denoiser: bool = True
    auto_exposure: bool = False

    def __post_init__(self):
        if self.mode not in ("realtime", "path_tracing"):
            raise ValueError(f"Unknown renderer: {self.mode}")
        if not 1 <= self.samples_per_frame <= 32 or self.total_samples < 1 or self.max_bounces < 0:
            raise ValueError(
                "Renderer requires 1..32 samples/frame, positive total samples and nonnegative bounces"
            )


@dataclass(frozen=True)
class AssetCfg:
    kind: Literal["articulation", "rigid", "static"]
    source: Path | None = None
    size: tuple[float, float, float] = (0.1, 0.1, 0.1)
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    quaternion: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)
    scale: float = 1.0
    # None preserves a USD's authored root; URDF conversion defaults to a floating base.
    fixed_base: bool | None = None
    shared: bool = False
    self_collision: bool = False
    merge_fixed_joints: bool = False
    mimic: Literal["preserve", "independent"] = "preserve"
    # Explicit opt-in for visualization-only links lacking inertia; source files remain unchanged.
    marker_mass: float | None = None
    marker_inertia: float | None = None
    collision: Literal["convex_hull", "convex_decomposition", "convex_parts"] = "convex_hull"
    collision_enabled: bool = True
    contact_offset: float = 0.005
    rest_offset: float = 0.0
    gravity: bool = True
    kinematic: bool = False
    mass: float | None = None
    center_of_mass: tuple[float, float, float] | None = None
    inertia_tensor: tuple[tuple[float, ...], ...] | None = None
    friction: float = 1.0
    restitution: float = 0.0
    linear_damping: float = 0.0
    angular_damping: float = 0.0
    max_linear_velocity: float = 1000.0
    max_angular_velocity: float = 1000.0
    max_depenetration_velocity: float = 10.0
    position_iterations: int = 8
    velocity_iterations: int = 1
    color: tuple[float, float, float] = (0.5, 0.6, 0.7)
    visual_material: VisualMaterialCfg | None = None
    joints: dict[str, float] = field(default_factory=dict)
    drives: dict[str, DriveCfg] = field(default_factory=lambda: {"all": DriveCfg()})


@dataclass(frozen=True)
class ContactCfg:
    entity: str
    bodies: str = ".*"
    # Scene-relative paths, e.g. "object/top"; one sensor body required for pair filtering.
    filters: tuple[str, ...] = ()
    history_length: int = 1


@dataclass(frozen=True)
class SceneCfg:
    assets: dict[str, AssetCfg]
    contacts: dict[str, ContactCfg] = field(default_factory=dict)
    num_envs: int = 4
    spacing: float = 2.0
    device: str = "cuda:0"
    physics_dt: float = 0.005
    decimation: int = 4
    gravity: tuple[float, float, float] = (0.0, 0.0, -9.81)
    cache: Path = Path(".cache/assets")
    bounce_threshold: float = 0.2
    gpu_max_rigid_patch_count: int = 163840
    external_forces_every_iteration: bool = False
    camera_eye: tuple[float, float, float] = (1.5, 1.5, 1.2)
    camera_target: tuple[float, float, float] = (0.0, 0.0, 0.5)
    resolution: tuple[int, int] = (960, 720)
    lighting: LightingCfg = field(default_factory=LightingCfg)
    renderer: RendererCfg | None = None
    camera_focal_length: float | None = None  # mm; None preserves Isaac Sim viewport default

    @property
    def control_dt(self):
        return self.physics_dt * self.decimation

    def __post_init__(self):
        import re

        if self.num_envs < 1 or self.physics_dt <= 0 or self.decimation < 1 or self.spacing <= 0:
            raise ValueError("num_envs, dt, decimation and spacing must be positive")
        for name, asset in self.assets.items():
            if name == "contacts":
                raise ValueError("Entity name 'contacts' is reserved for sensor state")
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name):
                raise ValueError(f"Invalid entity name: {name}")
            if asset.kind not in ("articulation", "rigid", "static"):
                raise ValueError(f"Unsupported entity kind: {asset.kind}")
            if asset.kind == "articulation" and asset.source is None:
                raise ValueError(f"Articulation {name} requires a URDF or USD source")
            if (
                asset.source is not None
                and asset.source.suffix.lower() == ".urdf"
                and asset.kind != "articulation"
            ):
                raise ValueError(
                    "URDF imports use kind=articulation; use meshes/USD for a single rigid object"
                )
            if asset.shared and asset.kind != "static":
                raise ValueError("Only static scenery may be shared between environment clones")
            if asset.mimic not in ("preserve", "independent"):
                raise ValueError(f"Unsupported mimic policy: {asset.mimic}")
            if asset.collision not in ("convex_hull", "convex_decomposition", "convex_parts"):
                raise ValueError(f"Unsupported collision mode: {asset.collision}")
            if (asset.marker_mass is None) != (asset.marker_inertia is None):
                raise ValueError("Set marker_mass and marker_inertia together")
        for sensor in self.contacts.values():
            if sensor.entity not in self.assets or self.assets[sensor.entity].kind == "static":
                raise ValueError(f"Contact sensor requires a dynamic entity: {sensor.entity}")


def load_scene(path: str | Path) -> SceneCfg:
    from .presets import load_mapping

    path = Path(path).resolve()
    values = load_mapping(path)
    assets = {}
    for name, raw in values.pop("assets").items():
        item = dict(raw)
        if "drives" in item:
            item["drives"] = {key: DriveCfg(**drive) for key, drive in item["drives"].items()}
        if item.get("visual_material") is not None:
            visual = dict(item["visual_material"])
            item["visual_material"] = VisualMaterialCfg(**visual)
        assets[name] = AssetCfg(**item)
    contacts = {name: ContactCfg(**item) for name, item in values.pop("contacts", {}).items()}
    values["cache"] = (path.parent / values.get("cache", "../.cache/assets")).resolve()
    lighting = dict(values.get("lighting", {}))
    values["lighting"] = LightingCfg(**lighting)
    if values.get("renderer") is not None:
        values["renderer"] = RendererCfg(**values["renderer"])
    return SceneCfg(assets=assets, contacts=contacts, **values)


def save_scene(config: SceneCfg, path: str | Path):
    """Save effective settings with file-relative paths, preserving project layout on relocation."""
    import os
    from dataclasses import asdict

    import yaml

    path = Path(path).resolve()
    values = asdict(config)
    values["cache"] = os.path.relpath(config.cache.resolve(), path.parent)
    if config.lighting.environment_texture is not None:
        values["lighting"]["environment_texture"] = os.path.relpath(
            config.lighting.environment_texture.resolve(), path.parent
        )
    for asset in values["assets"].values():
        if asset["source"] is not None:
            asset["source"] = os.path.relpath(asset["source"].resolve(), path.parent)
        visual = asset["visual_material"]
        if visual is not None and visual["roughness_texture"] is not None:
            visual["roughness_texture"] = os.path.relpath(visual["roughness_texture"].resolve(), path.parent)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(values, sort_keys=False))
