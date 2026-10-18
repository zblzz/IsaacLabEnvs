"""Configuration must remain usable without Isaac Sim or CUDA imports."""

import subprocess
import sys

import pytest
from isaaclab_envs import AssetCfg, SceneCfg, load_scene


def test_config_import_does_not_start_simulator():
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import isaaclab_envs, sys; "
            "assert 'isaaclab.sim' not in sys.modules; assert 'omni' not in sys.modules",
        ],
        check=True,
    )


def test_relative_paths_and_unknown_fields(tmp_path):
    path = tmp_path / "scene.yaml"
    path.write_text("assets:\n  hand:\n    kind: articulation\n    source: robot.urdf\n")
    assert load_scene(path).assets["hand"].source == tmp_path / "robot.urdf"
    path.write_text("assets: {}\nphyscis_dt: 0.01\n")
    with pytest.raises(TypeError, match="physcis_dt"):
        load_scene(path)


def test_invalid_scene_boundary():
    with pytest.raises(ValueError, match="requires"):
        SceneCfg(assets={"hand": AssetCfg(kind="articulation")})
    with pytest.raises(ValueError, match="positive"):
        SceneCfg(assets={}, decimation=0)
    with pytest.raises(ValueError, match="reserved"):
        SceneCfg(assets={"contacts": AssetCfg(kind="rigid")})


def test_physics_and_control_clocks_are_distinct():
    assert SceneCfg(assets={}, physics_dt=0.0025, decimation=4).control_dt == 0.01


def test_appearance_survives_scene_export(tmp_path):
    from isaaclab_envs.config import save_scene

    source = tmp_path / "scene.yaml"
    source.write_text(
        "lighting:\n  ambient_intensity: 180\n  key_intensity: 900\n"
        "  environment_texture: studio.hdr\n"
        "renderer:\n  mode: path_tracing\n  total_samples: 128\n"
        "camera_focal_length: 35\n"
        "assets:\n  table:\n    kind: static\n    source: table.usda\n"
        "    friction: 0.7\n    visual_material:\n      color: [0.24, 0.25, 0.26]\n"
        "      roughness: 0.7\n      shader: omnipbr\n      roughness_texture: rough.jpg\n"
    )
    original = load_scene(source)
    exported = tmp_path / "run" / "scene.yaml"
    save_scene(original, exported)
    restored = load_scene(exported)
    assert restored.lighting.ambient_intensity == 180
    assert restored.lighting.key_intensity == 900
    assert restored.lighting.environment_texture == tmp_path / "studio.hdr"
    assert restored.renderer.mode == "path_tracing"
    assert restored.renderer.total_samples == 128
    assert restored.camera_focal_length == 35
    assert restored.assets["table"].visual_material.shader == "omnipbr"
    assert restored.assets["table"].visual_material.roughness_texture == tmp_path / "rough.jpg"
    material = restored.assets["table"].visual_material
    assert material.color == original.assets["table"].visual_material.color
    assert material.roughness == 0.7
    assert material.metallic == 0.0
    assert tuple(material.texture_scale) == (1.0, 1.0)
    assert restored.assets["table"].source == tmp_path / "table.usda"
    assert restored.assets["table"].friction == 0.7
