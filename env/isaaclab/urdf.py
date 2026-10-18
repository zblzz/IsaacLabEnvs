"""Explicit URDF normalization policies; source assets are never modified."""

import xml.etree.ElementTree as ET
from pathlib import Path

from ..config import AssetCfg


def prepare_urdf(source: Path, destination: Path, cfg: AssetCfg) -> Path:
    tree = ET.parse(source)
    root = tree.getroot()
    if cfg.mimic == "independent":
        for joint in root.findall("joint"):
            mimic = joint.find("mimic")
            if mimic is not None:
                joint.remove(mimic)
    if cfg.marker_mass is not None:
        for link in root.findall("link"):
            if link.find("inertial") is None and link.find("collision") is None:
                inertia = ET.SubElement(link, "inertial")
                ET.SubElement(inertia, "mass", value=str(cfg.marker_mass))
                ET.SubElement(
                    inertia,
                    "inertia",
                    ixx=str(cfg.marker_inertia),
                    iyy=str(cfg.marker_inertia),
                    izz=str(cfg.marker_inertia),
                    ixy="0",
                    ixz="0",
                    iyz="0",
                )
    for element in [*root.iter("mesh"), *root.iter("texture")]:
        filename = element.get("filename")
        if filename and "://" not in filename:
            element.set("filename", str((source.parent / filename).resolve()))
    content = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists() or destination.read_bytes() != content:
        destination.write_bytes(content)
    return destination
