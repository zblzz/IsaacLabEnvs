"""Compose YAML mappings before constructing simulator-independent config types.

``ref`` selects a file-relative preset; sibling fields override it. Mappings
merge recursively, while scalars, lists and null replace the inherited value.
An explicit nested ref selects a fresh preset, rather than merging two presets.
Resource paths are resolved where written, before merging across files.
"""

from pathlib import Path

import yaml

_PATH_FIELDS = {"source", "cache", "environment_texture", "roughness_texture"}


def load_mapping(path: str | Path) -> dict:
    """Read a composed configuration, rejecting reference cycles and non-mappings."""
    return _load(Path(path).resolve(), ())


def _load(path: Path, stack: tuple[Path, ...]) -> dict:
    if path in stack:
        chain = " -> ".join(str(item) for item in (*stack, path))
        raise ValueError(f"Preset reference cycle: {chain}")
    values = yaml.safe_load(path.read_text())
    if not isinstance(values, dict):
        raise ValueError(f"Preset must contain a YAML mapping: {path}")
    return _resolve(values, path, (*stack, path))


def _resolve(value, origin: Path, stack: tuple[Path, ...], inherited=None):
    if not isinstance(value, dict):
        return value
    if "ref" in value:
        reference = value["ref"]
        if not isinstance(reference, str) or not reference:
            raise ValueError(f"ref must be a nonempty file path: {origin}")
        inherited = _load((origin.parent / reference).resolve(), stack)
    result = dict(inherited) if isinstance(inherited, dict) else {}
    for key, item in value.items():
        if key == "ref":
            continue
        if key in _PATH_FIELDS and isinstance(item, str):
            result[key] = (origin.parent / item).resolve()
        else:
            result[key] = _resolve(item, origin, stack, result.get(key))
    return result
