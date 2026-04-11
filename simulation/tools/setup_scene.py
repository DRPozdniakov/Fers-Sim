"""
Scene setup script for Isaac Sim.
Run via MCP reload_script or paste into Script Editor.

Two modes:
  1. Quick: loads saved USD scene (fers_facility.usd) if it exists
  2. Full: rebuilds from scratch (physics, Interior NuRec, ground, camera)

Ground plane at Z=-1.80 (aligned with robot wheels on facility floor).
"""
import zipfile
import os

from pxr import Usd, UsdGeom, UsdPhysics, Gf, Sdf

stage = omni.usd.get_context().get_stage()

# --- Try loading saved scene first ---
SAVED_SCENE = "/isaac-sim/.local/share/ov/data/simulation/scene/fers_facility.usd"
if os.path.exists(SAVED_SCENE) and stage.GetRootLayer().GetNumSubLayerPaths() == 0:
    result, _ = omni.usd.get_context().open_stage(SAVED_SCENE)
    if result:
        print(f"Loaded saved scene: {SAVED_SCENE}")
        print("=== Scene setup complete (from saved USD) ===")
    else:
        print("Failed to open saved scene, rebuilding from scratch...")
else:
    print("Building scene from scratch...")

stage = omni.usd.get_context().get_stage()

# --- Physics Scene ---
if not stage.GetPrimAtPath("/World/PhysicsScene").IsValid():
    scene_prim = stage.DefinePrim("/World/PhysicsScene", "PhysicsScene")
    gravity_attr = scene_prim.CreateAttribute("physics:gravityDirection", Sdf.ValueTypeNames.Vector3f)
    gravity_attr.Set(Gf.Vec3f(0, 0, -1))
    gravity_mag = scene_prim.CreateAttribute("physics:gravityMagnitude", Sdf.ValueTypeNames.Float)
    gravity_mag.Set(9.81)
    print("Created PhysicsScene")

# --- Ground Plane at Z=-1.80 (robot wheel level) ---
if not stage.GetPrimAtPath("/World/GroundPlane").IsValid():
    plane = UsdGeom.Mesh.Define(stage, "/World/GroundPlane")
    plane.GetPointsAttr().Set([(-50, -50, 0), (50, -50, 0), (50, 50, 0), (-50, 50, 0)])
    plane.GetFaceVertexCountsAttr().Set([4])
    plane.GetFaceVertexIndicesAttr().Set([0, 1, 2, 3])
    UsdPhysics.CollisionAPI.Apply(plane.GetPrim())
    xformable = UsdGeom.Xformable(plane.GetPrim())
    xformable.AddTranslateOp().Set(Gf.Vec3d(0, 0, -1.80))
    print("Created GroundPlane at Z=-1.80")

# --- Dome Light ---
if not stage.GetPrimAtPath("/World/DomeLight").IsValid():
    light = UsdGeom.Xformable(stage.DefinePrim("/World/DomeLight", "DomeLight"))
    stage.GetPrimAtPath("/World/DomeLight").CreateAttribute("inputs:intensity", Sdf.ValueTypeNames.Float).Set(1000.0)
    print("Created DomeLight")

# --- Interior NuRec Volume ---
USDZ_PATH = "/isaac-sim/.local/share/ov/data/simulation/scene/Interior.usdz"
EXTRACT_DIR = "/isaac-sim/.local/share/ov/data/simulation/scene/Interior_extracted"
NUREC_PATH = os.path.join(EXTRACT_DIR, "Interior.nurec")

if os.path.exists(USDZ_PATH):
    if not os.path.exists(NUREC_PATH):
        os.makedirs(EXTRACT_DIR, exist_ok=True)
        with zipfile.ZipFile(USDZ_PATH, 'r') as z:
            z.extractall(EXTRACT_DIR)
        print("Extracted USDZ")

    if not stage.GetPrimAtPath("/World/Interior").IsValid():
        prim = stage.DefinePrim("/World/Interior", "Xform")
        prim.GetReferences().AddReference(
            os.path.join(EXTRACT_DIR, "default.usda"), "/World"
        )

        for field in ["density_field", "emissive_color_field"]:
            fp = stage.GetPrimAtPath(f"/World/Interior/gauss/gauss/{field}")
            if fp.IsValid():
                fp.GetAttribute("filePath").Set(Sdf.AssetPath(NUREC_PATH))

        xformable = UsdGeom.Xformable(prim)
        xformable.ClearXformOpOrder()
        xformable.AddRotateXYZOp().Set(Gf.Vec3f(270, 0, 0))

        print("Loaded Interior (rotated 270,0,0)")
    else:
        print("Interior already loaded")
else:
    print(f"Interior.usdz not found at {USDZ_PATH}")

# --- Camera at facility viewpoint ---
if not stage.GetPrimAtPath("/World/InteriorCamera").IsValid():
    cam = UsdGeom.Camera.Define(stage, "/World/InteriorCamera")
    xformable = UsdGeom.Xformable(cam.GetPrim())
    xformable.AddTranslateOp().Set(Gf.Vec3d(-5.98, -1.54, 1.31))
    xformable.AddRotateXYZOp().Set(Gf.Vec3f(75.79, 0, -92.63))
    print("Created InteriorCamera at facility viewpoint")

print("\n=== Scene setup complete ===")
print("Note: FERS robot must be imported via GUI: Isaac Utils > URDF Importer")
print("URDF path: /isaac-sim/.local/share/ov/data/simulation/fers_robot.urdf")
