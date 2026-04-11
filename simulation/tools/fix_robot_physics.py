"""
Post-URDF-import physics fixes for FERS robot.
Run via MCP or Script Editor AFTER importing the robot via GUI URDF Importer.

Fixes:
  1. Raises base_link so wheel bottoms sit at Z=0
  2. Sets base_link mass (40 kg), locks X/Y tilt, applies damping
  3. Adds sphere colliders on wheels with high friction
  4. Adds passive stabilizer spheres (front/back) for 4-point contact
  5. Configures wheel joints as velocity drives
  6. Tunes all joint drives (10:1 stiffness:damping ratio)
"""
import omni.usd
from pxr import UsdPhysics, PhysxSchema, UsdGeom, Gf, Sdf

stage = omni.usd.get_context().get_stage()

ROBOT_PATH = "/fers_robot"

# --- Constants from URDF geometry ---
WHEEL_RADIUS = 0.0712       # m (outer rolling radius from mesh)
WHEEL_JOINT_Z = 0.34128     # m (wheel joint Z above base_link origin)
START_Z = 0.4828            # m (base_link Z so wheel bottoms at Z=0)

# --- Joint drive tuning (10:1 stiffness:damping) ---
JOINT_DRIVES = {
    "shoulder_yaw":   (500.0, 50.0, 200.0),
    "shoulder_pitch": (500.0, 50.0, 200.0),
    "shoulder_roll":  (500.0, 50.0, 200.0),
    "elbow":          (400.0, 40.0, 150.0),
    "forearm":        (300.0, 30.0, 100.0),
    "wrist_pitch":    (200.0, 20.0, 50.0),
    "wrist_yaw":      (200.0, 20.0, 50.0),
    "wrist_roll":     (150.0, 15.0, 30.0),
    "gripper":        (100.0, 10.0, 50.0),
    "head_pan":       (200.0, 20.0, 30.0),
    "eye":            (50.0, 5.0, 10.0),
    "wheel":          (0.0, 50.0, 100.0),
    "torso":          (1000.0, 100.0, 500.0),
    "wheel_cover":    (100.0, 10.0, 50.0),
}


def _get_drive_params(joint_name):
    for key, params in JOINT_DRIVES.items():
        if key in joint_name.lower():
            return params
    return (200.0, 20.0, 50.0)


# ── 1. Raise base_link ──────────────────────────────────────────────────────

bl = stage.GetPrimAtPath(f"{ROBOT_PATH}/base_link")
if not bl.IsValid():
    print(f"[fix] ERROR: {ROBOT_PATH}/base_link not found")
else:
    xf = UsdGeom.Xformable(bl)
    ops = {op.GetOpName(): op for op in xf.GetOrderedXformOps()}
    if "xformOp:translate" in ops:
        ops["xformOp:translate"].Set(Gf.Vec3d(0.0, 0.0, START_Z))
    else:
        xf.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, START_Z))
    print(f"[fix] base_link Z = {START_Z:.4f} m (wheel bottoms at Z=0)")


# ── 2. Base link mass + rigid body ──────────────────────────────────────────

    if not bl.HasAPI(UsdPhysics.MassAPI):
        UsdPhysics.MassAPI.Apply(bl)
    bl.GetAttribute("physics:mass").Set(40.0)

    px_rb = PhysxSchema.PhysxRigidBodyAPI.Apply(bl)
    px_rb.GetAngularDampingAttr().Set(2.0)
    px_rb.GetLinearDampingAttr().Set(0.5)
    px_rb.GetMaxDepenetrationVelocityAttr().Set(1.0)
    px_rb.GetLockedRotAxisAttr().Set(3)  # lock X+Y tilt
    px_rb.GetDisableGravityAttr().Set(False)
    print("[fix] base_link: 40 kg, gravity ON, X+Y tilt locked")


# ── 3. Wheel sphere colliders ───────────────────────────────────────────────

for side in ("left", "right"):
    sph_path = f"{ROBOT_PATH}/{side}_wheel/wheel_sphere"
    if stage.GetPrimAtPath(sph_path).IsValid():
        stage.RemovePrim(sph_path)
    sph = UsdGeom.Sphere.Define(stage, sph_path)
    sph.GetRadiusAttr().Set(WHEEL_RADIUS)
    p = sph.GetPrim()
    UsdPhysics.CollisionAPI.Apply(p)
    px_col = PhysxSchema.PhysxCollisionAPI.Apply(p)
    px_col.GetContactOffsetAttr().Set(0.002)
    px_col.GetRestOffsetAttr().Set(0.001)
    mat = UsdPhysics.MaterialAPI.Apply(p)
    mat.GetStaticFrictionAttr().Set(0.9)
    mat.GetDynamicFrictionAttr().Set(0.8)
    mat.GetRestitutionAttr().Set(0.0)
print(f"[fix] Wheel spheres: r={WHEEL_RADIUS} m, friction=0.9/0.8")


# ── 4. Passive stabilizer spheres ───────────────────────────────────────────

STAB_RADIUS = WHEEL_RADIUS
STAB_LOCAL_Z = -(WHEEL_JOINT_Z - WHEEL_RADIUS)  # same Z as wheel bottoms

stabilizers = {
    "front_stab": (0.0, 0.20),
    "back_stab":  (0.0, -0.20),
}

for name, (sx, sy) in stabilizers.items():
    path = f"{ROBOT_PATH}/base_link/{name}"
    if stage.GetPrimAtPath(path).IsValid():
        stage.RemovePrim(path)
    sph = UsdGeom.Sphere.Define(stage, path)
    sph.GetRadiusAttr().Set(STAB_RADIUS)
    xf = UsdGeom.Xformable(sph.GetPrim())
    xf.AddTranslateOp().Set(Gf.Vec3d(sx, sy, STAB_LOCAL_Z))
    UsdPhysics.CollisionAPI.Apply(sph.GetPrim())
    px_col = PhysxSchema.PhysxCollisionAPI.Apply(sph.GetPrim())
    px_col.GetContactOffsetAttr().Set(0.002)
    px_col.GetRestOffsetAttr().Set(0.001)
    mat = UsdPhysics.MaterialAPI.Apply(sph.GetPrim())
    mat.GetStaticFrictionAttr().Set(0.05)  # low friction — slides freely
    mat.GetDynamicFrictionAttr().Set(0.05)
    mat.GetRestitutionAttr().Set(0.0)

print("[fix] Stabilizers: 4-point contact (2 driven wheels + 2 passive)")


# ── 5. Wheel velocity drives ───────────────────────────────────────────────

for jname in ("left_wheel_joint", "right_wheel_joint"):
    j = stage.GetPrimAtPath(f"{ROBOT_PATH}/joints/{jname}")
    if j.IsValid():
        drv = UsdPhysics.DriveAPI.Apply(j, "angular")
        drv.GetStiffnessAttr().Set(0.0)
        drv.GetDampingAttr().Set(5000.0)
        drv.GetMaxForceAttr().Set(500.0)
print("[fix] Wheel drives: velocity mode (stiffness=0, damping=5000)")


# ── 6. Tune all joint drives ───────────────────────────────────────────────

count = 0
for prim in stage.Traverse():
    if not prim.IsA(UsdPhysics.Joint):
        continue
    if ROBOT_PATH not in str(prim.GetPath()):
        continue
    drive_type = "linear" if prim.IsA(UsdPhysics.PrismaticJoint) else "angular"
    drive_api = UsdPhysics.DriveAPI.Get(prim, drive_type)
    if not drive_api:
        drive_api = UsdPhysics.DriveAPI.Apply(prim, drive_type)
    s, d, m = _get_drive_params(prim.GetName())
    drive_api.GetStiffnessAttr().Set(s)
    drive_api.GetDampingAttr().Set(d)
    drive_api.GetMaxForceAttr().Set(m)
    count += 1

print(f"[fix] Tuned {count} joints (10:1 stiffness:damping)")
print("\n=== Robot physics fixes applied ===")
