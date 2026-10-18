"""Pull one explicit run with rsync. Host Python only; no simulator dependency."""

import argparse
import json
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


@dataclass(frozen=True)
class SyncConfig:
    remote_root: str
    local_root: str
    host: str | None = None  # SSH config alias; None also permits local transfer tests.


def command_for(config: SyncConfig, run: str, *, media=False, dry_run=False):
    relative = PurePosixPath(run)
    if not relative.parts or relative.is_absolute() or ".." in relative.parts:
        raise ValueError("--run must be a relative run directory without '..'")
    if config.host and (config.host.startswith("-") or ":" in config.host):
        raise ValueError("host must be an SSH alias or user@hostname")
    source = str(PurePosixPath(config.remote_root) / relative) + "/"
    if config.host:
        source = config.host + ":" + source
    destination = Path(config.local_root).expanduser().resolve() / str(relative)
    command = ["rsync", "--archive", "--partial", "--delay-updates", "--protect-args", "--itemize-changes"]
    if dry_run:
        command.append("--dry-run")
    if media:
        command += ["--include=*/", "--include=*.mp4", "--include=*.png", "--include=*.json", "--exclude=*"]
    else:
        command += ["--exclude=events.out.tfevents*", "--exclude=*.tmp", "--exclude=*.partial"]
    command += ["--", source, str(destination) + "/"]
    return command, destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--run", required=True, help="Run directory relative to configured roots")
    parser.add_argument("--mode", choices=("run", "media"), default="run")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    values = json.loads(args.config.read_text())
    values["local_root"] = str(args.config.resolve().parent / Path(values["local_root"]).expanduser())
    command, destination = command_for(
        SyncConfig(**values), args.run, media=args.mode == "media", dry_run=args.dry_run
    )
    print(shlex.join(command), flush=True)
    # rsync requires the parent even for a dry run. Never delete local files.
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
