"""Relocation, selective transfers, run mismatch detection and simulation-time video."""

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from isaaclab_envs import AssetCfg, SceneCfg, load_scene
from isaaclab_envs.config import save_scene
from isaaclab_envs.recording import Video

ROOT = Path(__file__).resolve().parents[1]


def script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_manifest_relocation_and_semantic_input_changes(tmp_path):
    manifest = script("manifest")
    server = tmp_path / "server"
    server.mkdir()
    (server / "policy.py").write_text("joint_names = ['a', 'b']")
    run = server / "outputs/run1"
    run.mkdir(parents=True)
    (run / "checkpoint.pt").write_bytes(b"opaque algorithm checkpoint")
    manifest.create(server, run, ["policy.py"])
    local = tmp_path / "different-machine"
    shutil.copytree(server, local)
    manifest.check(local, local / "outputs/run1")
    (local / "policy.py").write_text("joint_names = ['b', 'a']")
    with pytest.raises(ValueError, match="input changed"):
        manifest.check(local, local / "outputs/run1")
    (local / "policy.py").write_text((server / "policy.py").read_text())
    (local / "outputs/run1/checkpoint.pt").write_bytes(b"truncated")
    with pytest.raises(ValueError, match="artifact changed"):
        manifest.check(local, local / "outputs/run1")


def test_scene_snapshot_relocates_assets(tmp_path):
    server = tmp_path / "server"
    cfg = SceneCfg(
        assets={"hand": AssetCfg(kind="articulation", source=server / "assets/hand.urdf")},
        cache=server / ".cache",
    )
    save_scene(cfg, server / "outputs/run1/trace.scene.yaml")
    local = tmp_path / "local"
    shutil.copytree(server, local)
    loaded = load_scene(local / "outputs/run1/trace.scene.yaml")
    assert loaded.assets["hand"].source == local / "assets/hand.urdf"
    assert loaded.cache == local / ".cache"


@pytest.mark.skipif(shutil.which("rsync") is None, reason="Host rsync required")
def test_selective_sync_and_no_deletion(tmp_path):
    sync = script("sync")
    remote = tmp_path / "remote with spaces"
    run = remote / "run1"
    run.mkdir(parents=True)
    for name in ("video.mp4", "checkpoint.pt", "params.yaml", "manifest.json", "events.out.tfevents.1"):
        (run / name).write_text("sample")
    local = tmp_path / "local"
    local.mkdir()
    cfg = sync.SyncConfig(str(remote), str(local))
    command, destination = sync.command_for(cfg, "run1", media=True)
    subprocess.run(command, check=True, capture_output=True)
    assert sorted(p.name for p in destination.iterdir()) == ["manifest.json", "video.mp4"]
    (destination / "keep.txt").write_text("local notes")
    subprocess.run(sync.command_for(cfg, "run1")[0], check=True, capture_output=True)
    assert (destination / "checkpoint.pt").exists()
    assert (destination / "params.yaml").exists()
    assert (destination / "keep.txt").exists()
    assert not (destination / "events.out.tfevents.1").exists()
    with pytest.raises(ValueError):
        sync.command_for(cfg, "../escape")


def test_video_duration_matches_simulation_time(tmp_path):
    iio = pytest.importorskip("imageio.v2")
    pytest.importorskip("imageio_ffmpeg")
    path = tmp_path / "video.mp4"
    with Video(path, control_dt=0.02, every=2) as video:
        for step in range(50):
            video.capture(lambda: np.full((32, 32, 3), step * 4, dtype=np.uint8), step)
        assert video.frames == 25
        assert video.fps == 25
    reader = iio.get_reader(path)
    assert reader.count_frames() == 25
    assert reader.get_meta_data()["duration"] == pytest.approx(1, abs=0.05)
    reader.close()


def test_sync_example_is_explicit():
    values = json.loads((ROOT / "configs/sync.example.json").read_text())
    assert set(values) == {"host", "remote_root", "local_root"}
