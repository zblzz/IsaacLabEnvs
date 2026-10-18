"""Run a configured scene without an algorithm; write a reproducible physics report."""

import argparse
import json
import time
from dataclasses import replace
from pathlib import Path


def tensors(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from tensors(item)
    else:
        yield value


def main():
    from isaaclab_envs import RendererCfg, load_scene, make_scene
    from isaaclab_envs.recording import Video
    from isaaclab_envs.runtime import Runtime

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=Path(__file__).resolve().parents[1] / "configs/drop.yaml"
    )
    parser.add_argument("--steps", type=int, default=120)
    parser.add_argument("--num-envs", type=int)
    parser.add_argument("--output", type=Path, default=Path("outputs/smoke.json"))
    parser.add_argument("--screenshot", type=Path)
    parser.add_argument("--record", type=Path, help="Save a physical state trace (.npz) for replay")
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--video", type=Path, help="Record viewport as MP4")
    parser.add_argument("--video-every", type=int, default=2, help="Control steps per video frame")
    parser.add_argument("--livestream", type=int, choices=(0, 2), default=0)
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
    if args.steps < 2:
        parser.error("--steps must be at least 2")
    config = load_scene(args.config)
    if args.num_envs is not None:
        config = replace(config, num_envs=args.num_envs)
    if args.resolution:
        config = replace(config, resolution=tuple(args.resolution))
    if args.renderer:
        config = replace(config, renderer=replace(config.renderer or RendererCfg(), mode=args.renderer))
    with Runtime(
        device=config.device,
        headless=not args.gui,
        cameras=bool(args.screenshot or args.video),
        livestream=args.livestream,
        rendering_mode=args.rendering_mode,
    ) as runtime:
        import torch
        from isaaclab_envs import Command

        with (
            make_scene(config) as scene,
            Video(args.video, control_dt=config.control_dt, every=args.video_every) as video,
        ):
            from isaaclab_envs.recording import Trace

            trace = Trace(scene.describe()) if args.record else None
            initial = scene.state()
            commands = {
                name: Command(joint_position=value["joint_position"])
                for name, value in initial.items()
                if "joint_position" in value
            }
            max_contact = 0.0
            for step in range(args.steps):
                started = time.monotonic()
                if not runtime.app.is_running():
                    raise RuntimeError("Window closed before the smoke completed")
                state = scene.step(commands)
                if trace:
                    trace.append(state)
                video.capture(scene.render, step)
                if args.livestream:
                    scene.present()
                if not all(torch.isfinite(item).all() for item in tensors(state)):
                    raise RuntimeError(f"Nonfinite physics state at step {step}")
                for contact in state["contacts"].values():
                    max_contact = max(max_contact, float(contact["net_force"].norm(dim=-1).max()))
                if step == args.steps // 2:
                    ids = torch.arange(0, config.num_envs, 2, device=config.device)
                    before = {name: item["root"].clone() for name, item in state.items() if "root" in item}
                    after = scene.reset(env_ids=ids)
                    remaining = torch.arange(1, config.num_envs, 2, device=config.device)
                    for name, value in before.items():
                        torch.testing.assert_close(after[name]["root"][remaining], value[remaining])
                        torch.testing.assert_close(state[name]["root"], value)  # owned snapshots
                if args.gui or args.livestream:
                    time.sleep(max(0, config.control_dt - (time.monotonic() - started)))
            if args.screenshot:
                from PIL import Image

                args.screenshot.parent.mkdir(parents=True, exist_ok=True)
                Image.fromarray(scene.render(settle_frames=args.screenshot_frames)).save(args.screenshot)
            if trace:
                trace.save(args.record)
                from isaaclab_envs.config import save_scene

                save_scene(config, args.record.with_suffix(".scene.yaml"))
            report = dict(
                kind="physics_smoke_not_task_success",
                steps=args.steps,
                finite=True,
                subset_reset=True,
                snapshot_ownership=True,
                max_contact_force_N=max_contact,
                rendering_mode=args.rendering_mode,
                renderer=config.renderer.mode if config.renderer else "realtime",
                resolution=list(config.resolution),
                video_frames=video.frames,
                video_fps=video.fps if args.video else None,
                **scene.describe(),
            )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2) + "\n")
            print("SCENE_SMOKE", json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
