"""
FERS Robot Loader for Isaac Sim 5.1.0 — working version
Run this in Isaac Sim's Script Editor (Window > Script Editor)

Key differences from original:
  - fix_base=False  : robot is free-floating (can drive around)
  - No dest_path    : imports directly into current stage at /fers_robot
  - base_link Z=-0.2701 : positions wheel bottoms exactly on the ground plane
  - Wheel collision spheres + velocity drives pre-configured

Geometry (from URDF):
  wheel joint xyz Z = +0.34128 above base_link
  wheel radius     = 0.0712 m
  START_Z          = WHEEL_RADIUS - WHEEL_JOINT_Z = -0.2701 m
"""
import omni.kit.commands
import omni.usd
import os
from pxr import UsdPhysics, PhysxSchema, UsdGeom, Gf

URDF_PATH     = "/isaac-sim/.local/share/ov/data/simulation/fers_robot.urdf"
WHEEL_RADIUS  = 0.0712   # m — outer rolling radius
WHEEL_JOINT_Z = 0.34128  # m — wheel joint Z offset ABOVE base_link (from URDF joint origin)
START_Z       = WHEEL_RADIUS - WHEEL_JOINT_Z   # = -0.2701 m


def import_robot():
    from isaacsim.asset.importer.urdf import _urdf

    cfg = _urdf.ImportConfig()
    cfg.set_merge_fixed_joints(False)
    cfg.set_fix_base(False)
    cfg.set_make_default_prim(True)
    cfg.set_create_physics_scene(False)
    cfg.set_self_collision(False)
    cfg.set_convex_decomp(False)
    cfg.set_density(0.0)
    cfg.set_distance_scale(1.0)
    cfg.set_default_drive_type(1)
    cfg.set_default_drive_strength(1e4)
    cfg.set_default_position_drive_damping(1e3)

    result, prim_path = omni.kit.commands.execute(
        "URDFParseAndImportFile",
        urdf_path=URDF_PATH,
        import_config=cfg,
    )

    if not result:
        print(f"[FERS] ERROR: import failed for {URDF_PATH}")
        return None

    print(f"[FERS] Imported at {prim_path}")
    return prim_path


def setup_physics(robot_path):
    stage = omni.usd.get_context().get_stage()
    bl = stage.GetPrimAtPath(f"{robot_path}/base_link")

    # Position so wheel bottoms touch Z=0
    xf = UsdGeom.Xformable(bl)
    ops = {op.GetOpName(): op for op in xf.GetOrderedXformOps()}
    if "xformOp:translate" in ops:
        ops["xformOp:translate"].Set(Gf.Vec3d(0.0, 0.0, START_Z))
    else:
        xf.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, START_Z))
    print(f"[FERS] base_link Z = {START_Z:.4f}  (wheel center at Z={WHEEL_RADIUS:.4f}, bottom at Z=0)")

    # Mass
    if not bl.HasAPI(UsdPhysics.MassAPI):
        UsdPhysics.MassAPI.Apply(bl)
    bl.GetAttribute("physics:mass").Set(40.0)

    # PhysX rigid body settings
    px_rb = PhysxSchema.PhysxRigidBodyAPI.Apply(bl)
    px_rb.GetAngularDampingAttr().Set(2.0)
    px_rb.GetLinearDampingAttr().Set(0.5)
    px_rb.GetMaxDepenetrationVelocityAttr().Set(1.0)
    px_rb.GetLockedRotAxisAttr().Set(3)   # lock X+Y tilt; Z free for turning
    px_rb.GetDisableGravityAttr().Set(False)
    print("[FERS] base_link: 40kg, gravity ON, tilt-locked")

    # Wheel collision spheres
    for side in ("left", "right"):
        sph_path = f"{robot_path}/{side}_wheel/wheel_sphere"
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
    print(f"[FERS] Wheel spheres added (r={WHEEL_RADIUS}, friction=0.9/0.8)")

    # Wheel velocity drives
    for jname in ("left_wheel_joint", "right_wheel_joint"):
        j = stage.GetPrimAtPath(f"{robot_path}/joints/{jname}")
        drv = UsdPhysics.DriveAPI.Apply(j, "angular")
        drv.GetStiffnessAttr().Set(0.0)
        drv.GetDampingAttr().Set(5000.0)
        drv.GetMaxForceAttr().Set(500.0)
    print("[FERS] Wheel drives: velocity mode (stiffness=0, damping=5000)")


# ── Main ──────────────────────────────────────────────────────────────────────
print(f"[FERS] URDF exists: {os.path.exists(URDF_PATH)}")
robot_path = import_robot()

if robot_path:
    setup_physics(robot_path)
    print("\n[FERS] Ready — press Play to simulate")
    print("[FERS] Trajectory: load simulation/tools/square_trajectory.py as action graph")
