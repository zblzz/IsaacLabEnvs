"""Check bundled asset integrity and local mesh/texture references without Isaac Sim."""

import argparse
import hashlib
import json
import shlex
import xml.etree.ElementTree as ET
from pathlib import Path


def local_file(root, parent, reference):
    if "://" in reference or Path(reference).is_absolute():
        raise ValueError(f"Asset must be offline and file-relative: {reference}")
    path = (parent / reference).resolve()
    path.relative_to(root)
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def check(root):
    root = root.resolve()
    catalog = json.loads((root / "assets/catalog.json").read_text())
    if catalog["version"] != 1:
        raise ValueError("Unsupported asset catalog version")
    results = []
    for asset in catalog["assets"]:
        source = local_file(root, root / "assets", asset["source"])
        local_file(root, root, asset["preset"])
        receipt = json.loads((source.parent / "source.json").read_text())
        for relative, expected in receipt["sha256"].items():
            path = local_file(root, source.parent, relative)
            with path.open("rb") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual != expected:
                raise ValueError(f"Asset content differs from source.json: {path}")
            if path.suffix == ".obj":
                for line in path.read_text().splitlines():
                    if line.startswith("mtllib "):
                        for name in shlex.split(line)[1:]:
                            local_file(root, path.parent, name)
            elif path.suffix == ".mtl":
                for line in path.read_text().splitlines():
                    if line.startswith(("map_", "bump ")):
                        local_file(root, path.parent, shlex.split(line)[-1])
            elif path.suffix == ".dae":
                for item in ET.parse(path).findall(".//{*}library_images/{*}image/{*}init_from"):
                    local_file(root, path.parent, item.text.strip())
        result = {"id": asset["id"], "files": len(receipt["sha256"]), "integrity": True}
        if source.suffix == ".urdf":
            tree = ET.parse(source)
            local_file(root, source.parent, "LICENSE")
            for mesh in tree.iter("mesh"):
                local_file(root, source.parent, mesh.get("filename"))
            joints = [j for j in tree.findall("joint") if j.get("type") != "fixed"]
            if len(joints) != asset["expected_joints"]:
                raise ValueError(f"Unexpected joint count for {asset['id']}")
            result.update(joints=len(joints), links=len(tree.findall("link")))
        results.append(result)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = {"assets": check(args.root), "physics_tested": False}
    encoded = json.dumps(result, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(encoded + "\n")
    print(encoded)


if __name__ == "__main__":
    main()
