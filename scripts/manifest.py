"""Seal/check a completed run and explicitly selected project inputs. Host Python only.

The manifest identifies bytes; it does not load a policy, rewrite project configuration,
copy assets, or infer an observation/action contract from a checkpoint.
"""

import argparse
import fnmatch
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

IGNORED = {".git", ".cache", "__pycache__", ".pytest_cache", ".ruff_cache"}
MODULE_ROOT = Path(__file__).resolve().parents[1]
MODULE_INPUTS = ("env", "scripts", "docker", "pyproject.toml")
TRANSIENT_ARTIFACTS = ("events.out.tfevents*", "*.tmp", "*.partial")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inventory(root: Path, selections, *, exclude=(), transient=False):
    result = {}
    for selection in selections:
        path = (root / selection).resolve()
        path.relative_to(root)  # Reject missing root mappings or escaping symlinks.
        files = sorted(path.rglob("*")) if path.is_dir() else [path]
        for file in files:
            relative = file.relative_to(root)
            if set(relative.parts) & IGNORED or str(relative) in exclude:
                continue
            if transient and any(fnmatch.fnmatch(file.name, pattern) for pattern in TRANSIENT_ARTIFACTS):
                continue
            if file.is_file():
                file.resolve().relative_to(root)
                result[relative.as_posix()] = digest(file)
            elif not file.exists():
                raise FileNotFoundError(file)
    return result


def git_revision(project):
    result = subprocess.run(["git", "-C", str(project), "rev-parse", "HEAD"], capture_output=True, text=True)
    if result.returncode:
        return None
    status = subprocess.check_output(["git", "-C", str(project), "status", "--porcelain"], text=True)
    return {"commit": result.stdout.strip(), "dirty": bool(status.strip())}


def image_id(image):
    return subprocess.check_output(
        ["docker", "image", "inspect", "--format={{.Id}}", image], text=True
    ).strip()


def create(project, run, inputs, *, image=None, contract=None):
    if (run / "manifest.json").exists():
        raise FileExistsError("Run is already sealed; write a new run directory")
    if any(run.is_relative_to((project / item).resolve()) for item in inputs):
        raise ValueError("Select code/config/asset directories separately; inputs must not contain the run")
    artifacts = inventory(run, ["."], transient=True)
    if not artifacts:
        raise ValueError("Cannot seal an empty run")
    manifest = {
        "version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git": git_revision(project),
        "inputs": list(inputs),
        "input_sha256": inventory(project, inputs),
        "module_sha256": inventory(MODULE_ROOT, MODULE_INPUTS),
        "artifact_sha256": artifacts,
        "image": {"name": image, "id": image_id(image)} if image else None,
        "contract": json.loads(contract.read_text()) if contract else None,
    }
    (run / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return manifest


def check(project, run, *, image=None):
    manifest = json.loads((run / "manifest.json").read_text())
    if manifest["version"] != 1:
        raise ValueError("Unsupported manifest version")
    problems = []
    for label, expected, actual in (
        ("module", manifest["module_sha256"], inventory(MODULE_ROOT, MODULE_INPUTS)),
        ("input", manifest["input_sha256"], inventory(project, manifest["inputs"])),
        (
            "artifact",
            manifest["artifact_sha256"],
            inventory(run, ["."], exclude=("manifest.json",), transient=True),
        ),
    ):
        for name in sorted(set(expected) | set(actual)):
            if expected.get(name) != actual.get(name):
                problems.append(f"{label} changed/missing/added: {name}")
    if manifest["image"] and image_id(image or manifest["image"]["name"]) != manifest["image"]["id"]:
        problems.append("Docker image differs from the recorded image ID")
    if problems:
        raise ValueError("\n".join(problems))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("create", "check"))
    parser.add_argument(
        "--project", type=Path, required=True, help="Local project root; may differ by machine"
    )
    parser.add_argument(
        "--run", type=Path, required=True, help="Completed run, containing configs/checkpoint/media"
    )
    parser.add_argument(
        "--input", action="append", default=[], help="Code/config/asset path relative to project"
    )
    parser.add_argument("--image", help="Docker image tag or digest; create records its local image ID")
    parser.add_argument("--contract", type=Path, help="Project JSON describing observation/action semantics")
    args = parser.parse_args()
    project, run = args.project.resolve(), args.run.resolve()
    if args.operation == "create":
        if not args.input:
            parser.error("Specify --input for code, configs and all assets required by this run")
        manifest = create(project, run, args.input, image=args.image, contract=args.contract)
    else:
        manifest = check(project, run, image=args.image)
    print(
        f"MANIFEST_OK: {len(manifest['input_sha256'])} inputs, {len(manifest['artifact_sha256'])} artifacts"
    )


if __name__ == "__main__":
    main()
