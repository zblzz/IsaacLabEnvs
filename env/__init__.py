"""Public scene interface. Importing configuration does not launch Isaac Sim."""

from .config import AssetCfg, ContactCfg, LightingCfg, RendererCfg, SceneCfg, VisualMaterialCfg, load_scene
from .contracts import Command, ResetState

__all__ = [
    "AssetCfg",
    "ContactCfg",
    "LightingCfg",
    "VisualMaterialCfg",
    "RendererCfg",
    "SceneCfg",
    "Command",
    "ResetState",
    "load_scene",
    "make_scene",
]


def make_scene(config: SceneCfg):
    """Create a physics scene after opening Runtime; the caller owns its lifecycle."""
    from .isaaclab.backend import Scene

    return Scene(config)
