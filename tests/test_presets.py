"""Composition must survive reuse, preset replacement and project relocation."""

import shutil
from dataclasses import asdict
from pathlib import Path

import pytest
import yaml
from isaaclab_envs import load_scene
from isaaclab_envs.config import save_scene


def test_reference_origins_overrides_and_frozen_export(tmp_path):
    presets = tmp_path / "library"
    presets.mkdir()
    (presets / "robot.yaml").write_text(
        "kind: articulation\nsource: robot.urdf\njoints: {hinge: 0}\n"
        "drives: {all: {stiffness: 100, damping: 10}}\n"
    )
    (presets / "metal.yaml").write_text("shader: omnipbr\nmetallic: 1\nroughness_texture: rough.jpg\n")
    (presets / "lighting.yaml").write_text("environment_texture: studio.hdr\n")
    scene = tmp_path / "scene.yaml"
    scene.write_text(
        "lighting: {ref: library/lighting.yaml}\nassets:\n"
        "  robot:\n    ref: library/robot.yaml\n    position: [1, 2, 3]\n"
        "    drives: {all: {stiffness: 50}}\n"
        "    visual_material: {ref: library/metal.yaml, roughness: 0.2}\n"
        "  object:\n    kind: rigid\n"
        "    visual_material: {ref: library/metal.yaml, roughness_texture: custom.jpg}\n"
    )
    cfg = load_scene(scene)
    robot = cfg.assets["robot"]
    assert robot.source == presets / "robot.urdf"
    assert robot.drives["all"].stiffness == 50
    assert robot.drives["all"].damping == 10
    assert robot.visual_material.roughness == 0.2
    assert robot.visual_material.roughness_texture == presets / "rough.jpg"
    assert cfg.assets["object"].visual_material.roughness_texture == tmp_path / "custom.jpg"
    assert cfg.lighting.environment_texture == presets / "studio.hdr"

    exported = tmp_path / "outputs" / "scene.yaml"
    save_scene(cfg, exported)
    assert "ref:" not in exported.read_text()
    (presets / "metal.yaml").unlink()
    restored = load_scene(exported)
    material = restored.assets["robot"].visual_material
    assert material.roughness_texture == robot.visual_material.roughness_texture
    assert material.roughness == robot.visual_material.roughness
    assert material.metallic == robot.visual_material.metallic
    assert tuple(material.color) == tuple(robot.visual_material.color)
    assert tuple(material.texture_scale) == tuple(robot.visual_material.texture_scale)

    # Copy only the exported config into a relocated project tree: no presets needed.
    relocated = tmp_path / "relocated"
    (relocated / "outputs").mkdir(parents=True)
    shutil.copy(exported, relocated / "outputs/scene.yaml")
    moved = load_scene(relocated / "outputs/scene.yaml")
    assert moved.assets["robot"].source == relocated / "library/robot.urdf"
    assert moved.lighting.environment_texture == relocated / "library/studio.hdr"


def test_explicit_ref_replaces_inherited_robot_and_material(tmp_path):
    (tmp_path / "base.yaml").write_text(
        "assets:\n  robot:\n    kind: articulation\n    source: arm.urdf\n"
        "    joints: {old_joint: 0}\n"
        "    visual_material: {shader: omnipbr, roughness_texture: old.jpg}\n"
        "  table:\n    kind: static\n    visual_material: {metallic: 1}\n"
    )
    (tmp_path / "hand.yaml").write_text("kind: articulation\nsource: hand.urdf\njoints: {new_joint: 1}\n")
    (tmp_path / "scene.yaml").write_text(
        "ref: base.yaml\nassets:\n  robot: {ref: hand.yaml}\n  table: {visual_material: null}\n"
    )
    cfg = load_scene(tmp_path / "scene.yaml")
    assert cfg.assets["robot"].joints == {"new_joint": 1}
    assert cfg.assets["robot"].visual_material is None
    assert cfg.assets["table"].visual_material is None


def test_reference_errors_are_reported(tmp_path):
    scene = tmp_path / "scene.yaml"
    scene.write_text("ref: absent.yaml\n")
    with pytest.raises(FileNotFoundError, match="absent.yaml"):
        load_scene(scene)
    scene.write_text("ref: second.yaml\n")
    (tmp_path / "second.yaml").write_text("ref: scene.yaml\n")
    with pytest.raises(ValueError, match="reference cycle"):
        load_scene(scene)
    scene.write_text("ref: 123\n")
    with pytest.raises(ValueError, match="ref must"):
        load_scene(scene)
    scene.write_text("[]\n")
    with pytest.raises(ValueError, match="YAML mapping"):
        load_scene(scene)
    scene.write_text("assets: {}\nphyscis_dt: 0.01\n")
    with pytest.raises(TypeError, match="physcis_dt"):
        load_scene(scene)


def test_bundled_scenes_and_robot_independent_appearance():
    root = Path(__file__).resolve().parents[1]
    for source in sorted((root / "configs/assets").glob("*.yaml")):
        cfg = load_scene(source)
        for asset in cfg.assets.values():
            if asset.source:
                assert asset.source.is_file()
            material = asset.visual_material
            if material and material.roughness_texture:
                assert material.roughness_texture.is_file()
        if cfg.lighting.environment_texture:
            assert cfg.lighting.environment_texture.is_file()
    # Rendering differences do not change the robot's physical configuration.
    basic = load_scene(root / "configs/assets/franka.yaml")
    hdr = load_scene(root / "configs/assets/franka_hdr.yaml")
    assert asdict(basic.assets["robot"]) == asdict(hdr.assets["robot"])
    for source in (root / "configs/robots").rglob("*.yaml"):
        fields = yaml.safe_load(source.read_text())
        assert not {"position", "visual_material", "lighting", "renderer"} & fields.keys()
