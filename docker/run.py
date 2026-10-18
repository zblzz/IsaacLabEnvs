"""Host-only Docker launcher. Configuration travels through files and CLI arguments."""

import argparse
import os
import subprocess
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("build", "run"))
    parser.add_argument("--image", default="isaaclab-envs:2.3.2")
    parser.add_argument("--project", type=Path, default=root, help="Extra project directory to mount")
    parser.add_argument("--install", type=Path, action="append", default=[], help="Project Python package")
    parser.add_argument(
        "--mount-readonly", type=Path, action="append", default=[],
        help="Extra data directory mounted read-only at the same absolute path; repeatable",
    )
    parser.add_argument("--gpu", default="0", help="Host GPU index; inside the container use cuda:0")
    parser.add_argument("--gui", action="store_true", help="Forward an existing X11 display")
    entry = parser.add_mutually_exclusive_group()
    entry.add_argument("--script", type=Path, help="Python entry point; default scripts/smoke.py")
    entry.add_argument("--module", help="Python module entry point, e.g. pytest")
    parser.add_argument("--name", help="Optional container name for status/stop")
    args, forwarded = parser.parse_known_args()
    if forwarded[:1] == ["--"]:
        forwarded = forwarded[1:]
    if args.operation == "build":
        if forwarded:
            parser.error("Unexpected build arguments: " + " ".join(forwarded))
        subprocess.run(
            [
                "docker",
                "build",
                "--network=host",
                "-t",
                args.image,
                "-f",
                str(root / "docker/Dockerfile"),
                str(root),
            ],
            check=True,
        )
        return
    project = args.project.resolve()
    command = [
        "docker",
        "run",
        "--rm",
        "--init",
        "--runtime=nvidia",
        "--gpus",
        "device=" + args.gpu,
        "--network=host",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--group-add",
        "isaac-sim",
        "--env",
        "HOME=/tmp",
        "--env",
        "ACCEPT_EULA=Y",
        "--workdir",
        str(project),
    ]
    for group in os.getgroups():
        command += ["--group-add", str(group)]
    for directory in sorted({root, project}):
        command += ["--mount", f"type=bind,src={directory},dst={directory}"]
    for directory in sorted({path.resolve() for path in args.mount_readonly}):
        if not directory.is_dir():
            parser.error(f"Read-only mount is not a directory: {directory}")
        if directory in {root, project}:
            parser.error(f"Read-only mount conflicts with writable project/module: {directory}")
        command += ["--mount", f"type=bind,src={directory},dst={directory},readonly"]
    cache = Path.home() / ".cache/isaaclab-envs"
    for name in ("cache", "data", "logs"):
        directory = cache / name
        directory.mkdir(parents=True, exist_ok=True)
        command += ["--mount", f"type=bind,src={directory},dst=/isaac-sim/kit/{name}"]
    if args.name:
        command += ["--name", args.name]
    if args.gui:
        display = os.environ.get("DISPLAY")
        if not display:
            parser.error("--gui requires an existing DISPLAY; use --screenshot on a headless server")
        command += ["--env", f"DISPLAY={display}", "--volume", "/tmp/.X11-unix:/tmp/.X11-unix:ro"]
        authority = Path(os.environ.get("XAUTHORITY", str(Path.home() / ".Xauthority")))
        if authority.is_file():
            command += [
                "--mount",
                f"type=bind,src={authority},dst=/tmp/.Xauthority,readonly",
                "--env",
                "XAUTHORITY=/tmp/.Xauthority",
            ]
    command += [args.image, str(root)]
    for package in args.install:
        command += ["--install", str(package.resolve())]
    command += (
        ["-m", args.module] if args.module else [str((args.script or root / "scripts/smoke.py").resolve())]
    )
    command += forwarded
    if args.gui:
        command += ["--gui"]
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
