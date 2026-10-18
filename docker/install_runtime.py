"""Install the exact URDF importer required by Isaac Lab 2.3.2, independently of Kit's registry."""

import argparse
import hashlib
import tempfile
import urllib.request
import zipfile
from pathlib import Path

PACKAGE = "isaacsim.asset.importer.urdf-2.4.31+107.3.3.lx64.r.cp311"
URL = "https://d4i3qtqj3r0z5.cloudfront.net/" + PACKAGE.replace("+", "%2B") + ".zip"
SHA256 = "665cc13d48842ac6d0c203359819c1d5c767a1d920fb8a00179e147ec2fb5201"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=Path("/isaac-sim/extscache"))
    parser.add_argument("--archive", type=Path, help="Previously downloaded official archive")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as directory:
        archive = args.archive or Path(directory) / "urdf.zip"
        if args.archive is None:
            with urllib.request.urlopen(URL, timeout=120) as response:
                archive.write_bytes(response.read())
        if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
            raise ValueError("URDF importer archive checksum mismatch.")
        with zipfile.ZipFile(archive) as package:
            package.extractall(args.destination / PACKAGE)
    print("Installed", PACKAGE)


if __name__ == "__main__":
    main()
