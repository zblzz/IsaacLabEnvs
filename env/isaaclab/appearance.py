"""Lighting and optional material overrides, independent of physics and source assets."""

import isaaclab.sim as sim
from isaaclab.assets import AssetBaseCfg

from ..config import AssetCfg, LightingCfg, RendererCfg


def add_lighting(scene_cfg, cfg: LightingCfg):
    texture = cfg.environment_texture
    if texture is not None and not texture.is_file():
        raise FileNotFoundError(texture)
    xyzw = cfg.environment_quaternion
    scene_cfg.ambient_light = AssetBaseCfg(
        prim_path="/World/Lighting/Ambient",
        spawn=sim.DomeLightCfg(
            intensity=cfg.ambient_intensity,
            texture_file=str(texture) if texture is not None else None,
            texture_format="latlong",
            visible_in_primary_ray=cfg.environment_visible,
        ),
        init_state=AssetBaseCfg.InitialStateCfg(rot=(xyzw[3], *xyzw[:3])),
    )
    xyzw = cfg.key_quaternion
    scene_cfg.key_light = AssetBaseCfg(
        prim_path="/World/Lighting/Key",
        spawn=sim.DistantLightCfg(intensity=cfg.key_intensity, angle=cfg.key_angle),
        init_state=AssetBaseCfg.InitialStateCfg(rot=(xyzw[3], *xyzw[:3])),
    )


def bind_appearance(assets: dict[str, AssetCfg], env_paths):
    for name, asset in assets.items():
        visual = asset.visual_material
        if visual is None:
            continue
        path = "/World/VisualMaterials/" + name
        if visual.shader == "omnipbr":
            from pxr import Sdf, UsdShade

            material = sim.MdlFileCfg(mdl_path="OmniPBR.mdl")
            prim = material.func(path, material)
            shader = UsdShade.Shader(prim)
            shader.CreateInput("diffuse_color_constant", Sdf.ValueTypeNames.Color3f).Set(tuple(visual.color))
            shader.CreateInput("reflection_roughness_constant", Sdf.ValueTypeNames.Float).Set(
                visual.roughness
            )
            shader.CreateInput("metallic_constant", Sdf.ValueTypeNames.Float).Set(visual.metallic)
            if visual.roughness_texture is not None:
                if not visual.roughness_texture.is_file():
                    raise FileNotFoundError(visual.roughness_texture)
                texture = shader.CreateInput("reflectionroughness_texture", Sdf.ValueTypeNames.Asset)
                texture.Set(Sdf.AssetPath(str(visual.roughness_texture)))
                texture.GetAttr().SetMetadata("colorSpace", "raw")
                shader.CreateInput("reflection_roughness_texture_influence", Sdf.ValueTypeNames.Float).Set(
                    visual.roughness_texture_weight
                )
                shader.CreateInput("project_uvw", Sdf.ValueTypeNames.Bool).Set(True)
                shader.CreateInput("world_or_object", Sdf.ValueTypeNames.Bool).Set(True)
                shader.CreateInput("texture_scale", Sdf.ValueTypeNames.Float2).Set(
                    tuple(visual.texture_scale)
                )
        else:
            material = sim.PreviewSurfaceCfg(
                diffuse_color=tuple(visual.color), roughness=visual.roughness, metallic=visual.metallic
            )
            material.func(path, material)
        roots = ["/World"] if asset.shared else env_paths
        for root in roots:
            sim.bind_visual_material(root + "/" + name, path)


def configure_renderer(cfg: RendererCfg | None):
    """Apply an explicit profile after SimulationContext initialization, before rendering."""
    if cfg is None:
        return
    import carb

    settings = carb.settings.get_settings()
    settings.set("/rtx/rendermode", "PathTracing" if cfg.mode == "path_tracing" else "RaytracedLighting")
    settings.set("/rtx/post/histogram/enabled", cfg.auto_exposure)
    settings.set("/rtx/post/tonemap/op", 6)  # ACES in the pinned Isaac Sim 5.1 renderer.
    if cfg.mode == "path_tracing":
        settings.set("/rtx/pathtracing/spp", cfg.samples_per_frame)
        settings.set("/rtx/pathtracing/totalSpp", cfg.total_samples)
        settings.set("/rtx/pathtracing/maxBounces", cfg.max_bounces)
        settings.set("/rtx/pathtracing/optixDenoiser/enabled", cfg.denoiser)
