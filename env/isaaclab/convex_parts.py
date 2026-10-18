"""Preserve dataset-provided convex parts instead of decomposing the whole mesh again."""

import hashlib
from pathlib import Path

import numpy as np
import trimesh
from pxr import Usd, UsdGeom, UsdPhysics, Vt


def convex_parts_usd(source: Path, cache: Path, scale: float) -> Path:
    digest = hashlib.sha256(source.read_bytes() + str(scale).encode()).hexdigest()[:16]
    destination = cache / f"convex_parts_{digest}.usd"
    if destination.is_file():
        return destination
    scene = trimesh.load(source, force="scene", process=False, group_material=False)
    if not scene.geometry or not all(geometry.is_convex for geometry in scene.geometry.values()):
        raise ValueError(f"Expected nonempty pre-decomposed convex parts: {source}")
    cache.mkdir(parents=True, exist_ok=True)
    stage = Usd.Stage.CreateNew(str(destination))
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    root = UsdGeom.Xform.Define(stage, "/Object")
    stage.SetDefaultPrim(root.GetPrim())
    UsdPhysics.RigidBodyAPI.Apply(root.GetPrim())
    UsdPhysics.MassAPI.Apply(root.GetPrim())
    for index, node in enumerate(scene.graph.nodes_geometry):
        transform, geometry_name = scene.graph[node]
        geometry = scene.geometry[geometry_name]
        points = trimesh.transform_points(geometry.vertices, transform) * scale
        mesh = UsdGeom.Mesh.Define(stage, f"/Object/part_{index:04d}")
        mesh.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(np.asarray(points, dtype=np.float32)))
        mesh.CreateFaceVertexCountsAttr([3] * len(geometry.faces))
        mesh.CreateFaceVertexIndicesAttr(geometry.faces.flatten().tolist())
        mesh.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
        UsdPhysics.CollisionAPI.Apply(mesh.GetPrim())
        UsdPhysics.MeshCollisionAPI.Apply(mesh.GetPrim()).CreateApproximationAttr("convexHull")
    stage.GetRootLayer().Save()
    return destination
