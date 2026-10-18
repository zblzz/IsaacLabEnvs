"""Kinematic replay of a physical state trace; does not evaluate a policy."""

import argparse
import time
from dataclasses import replace
from itertools import count
from pathlib import Path

from isaaclab_envs import RendererCfg, ResetState, load_scene, make_scene
from isaaclab_envs.recording import Video, load_trace
from isaaclab_envs.runtime import Runtime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--env-index", type=int, default=0)
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--screenshot", type=Path)
    parser.add_argument("--video", type=Path)
    parser.add_argument("--video-every", type=int, default=2)
    parser.add_argument("--livestream", type=int, choices=(0, 2), default=0)
    parser.add_argument("--loop", action="store_true", help="Repeat in GUI/WebRTC until closed")
    parser.add_argument(
        "--rendering-mode", choices=("performance", "balanced", "quality"), default="balanced"
    )
    parser.add_argument(
        "--renderer", choices=("realtime", "path_tracing"), help="Override the scene capture renderer"
    )
    parser.add_argument("--resolution", type=int, nargs=2, metavar=("WIDTH", "HEIGHT"))
    parser.add_argument(
        "--screenshot-frames", type=int, default=32, help="Render-only settling frames before PNG"
    )
    args = parser.parse_args()
    if args.screenshot_frames < 1 or (args.resolution and min(args.resolution) < 1):
        parser.error("Screenshot frames and resolution must be positive")
    if args.loop and (not (args.gui or args.livestream) or args.video):
        parser.error("--loop requires GUI/WebRTC and cannot be combined with --video")
    metadata, arrays = load_trace(args.trace)
    if not 0 <= args.env_index < metadata["num_envs"]:
        parser.error("--env-index is outside the recorded environment batch")
    cfg = replace(load_scene(args.config), num_envs=1)
    if args.resolution:
        cfg = replace(cfg, resolution=tuple(args.resolution))
    if args.renderer:
        cfg = replace(cfg, renderer=replace(cfg.renderer or RendererCfg(), mode=args.renderer))
    with Runtime(
        device=cfg.device,
        headless=not args.gui,
        cameras=bool(args.screenshot or args.video),
        livestream=args.livestream,
        rendering_mode=args.rendering_mode,
    ) as runtime:
        import torch

        with (
            make_scene(cfg) as scene,
            Video(args.video, control_dt=metadata["control_dt"], every=args.video_every) as video,
        ):
            if set(scene.describe()["assets"]) != set(metadata["assets"]):
                raise ValueError("Replay scene entities differ from the recorded scene")
            frames = len(next(iter(arrays.values())))
            played = 0
            for index in count() if args.loop else range(frames):
                if not runtime.app.is_running():
                    break
                started = time.monotonic()
                frame = index % frames
                states = {}
                for name, asset in metadata["assets"].items():
                    values = {
                        field: torch.tensor(
                            arrays[f"{name}/{field}"][frame, args.env_index : args.env_index + 1],
                            device=cfg.device,
                        )
                        for field in ("root", "joint_position", "joint_velocity")
                        if f"{name}/{field}" in arrays
                    }
                    states[name] = ResetState(
                        **values, joints=tuple(asset["joints"]) if "joints" in asset else None
                    )
                scene.write_state(states)
                video.capture(scene.render, index)
                played += 1
                if args.gui or args.livestream:
                    scene.present()
                    time.sleep(max(0, metadata["control_dt"] - (time.monotonic() - started)))
            if args.screenshot:
                from PIL import Image

                args.screenshot.parent.mkdir(parents=True, exist_ok=True)
                Image.fromarray(scene.render(settle_frames=args.screenshot_frames)).save(args.screenshot)
            print(
                f"REPLAY_OK: {played} played frames, {video.frames} video frames; "
                "kinematic state replay, not policy evaluation",
                flush=True,
            )


if __name__ == "__main__":
    main()
