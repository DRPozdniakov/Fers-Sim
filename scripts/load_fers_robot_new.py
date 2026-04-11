"""
FERS Robot Loader for Isaac Sim 5.1.0
Run this in Isaac Sim's Script Editor (Window > Script Editor)

Physics approach based on NVIDIA Carter V1 reference:
  - Cylinder wheel collisions (axis=X) — proper rolling, no lateral slip
  - Wheel drive damping = 17,453 Nm·s/rad (Carter-matched)
  - Angular damping = 0.05, linear damping = 0.0 (Carter-matched)
  - No lockedRotAxis — physical stability via rear caster + mass distribution
  - Rear caster wheel (swivel + axle joints) for 3-point stability
  - Heavy base (160kg), light upper body — CoM at wheel axle level
  - cfmScale = 0.025 for solver stability

After loading, run start_trajectory.py and press Play.
"""

import omni.kit.commands
import omni.usd
import os
import math
from pxr import UsdPhysics, PhysxSchema, UsdGeom, Gf, Sdf

URDF_PATH    = "/isaac-sim/.local/share/ov/data/simulation/fers_robot.urdf"
WHEEL_RADIUS = 0.0712    # m
WHEEL_WIDTH  = 0.05      # m — cylinder height
START_Z      = 0.4942    # base_link Z in /fers_robot local space (wheels on ground)


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

    # ── Position ──────────────────────────────────────────────────────────────
    xf  = UsdGeom.Xformable(bl)
    ops = {op.GetOpName(): op for op in xf.GetOrderedXformOps()}
    if "xformOp:translate" in ops:
        ops["xformOp:translate"].Set(Gf.Vec3d(0.0, 0.0, START_Z))
    else:
        xf.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, START_Z))
    print(f"[FERS] base_link Z = {START_Z}")

    # ── Mass distribution: heavy base, light upper body ───────────────────────
    mass_map = {
        f"{robot_path}/base_link":        160.0,
        f"{robot_path}/left_wheel":         1.0,
        f"{robot_path}/right_wheel":        1.0,
        f"{robot_path}/left_wheel_cover":   0.5,
        f"{robot_path}/right_wheel_cover":  0.5,
        f"{robot_path}/torso":              7.5,
        f"{robot_path}/L_shoulder_yaw":     0.75,
        f"{robot_path}/L_shoulder_pitch":   0.75,
        f"{robot_path}/L_upper_arm":        1.0,
        f"{robot_path}/L_elbow":            0.5,
        f"{robot_path}/L_forearm":          0.75,
        f"{robot_path}/L_wrist_pitch":      0.25,
        f"{robot_path}/L_wrist_yaw":        0.25,
        f"{robot_path}/L_wrist_roll":       0.2,
        f"{robot_path}/L_gripper":          0.25,
        f"{robot_path}/R_shoulder_yaw":     0.75,
        f"{robot_path}/R_shoulder_pitch":   0.75,
        f"{robot_path}/R_upper_arm":        1.0,
        f"{robot_path}/R_elbow":            0.5,
        f"{robot_path}/R_forearm":          0.75,
        f"{robot_path}/R_wrist_pitch":      0.25,
        f"{robot_path}/R_wrist_yaw":        0.25,
        f"{robot_path}/R_wrist_roll":       0.2,
        f"{robot_path}/R_gripper":          0.25,
        f"{robot_path}/head":               1.5,
        f"{robot_path}/left_eye":           0.1,
        f"{robot_path}/right_eye":          0.1,
    }
    for path, mass in mass_map.items():
        p = stage.GetPrimAtPath(path)
        if p.IsValid():
            if not p.HasAPI(UsdPhysics.MassAPI):
                UsdPhysics.MassAPI.Apply(p)
            p.GetAttribute("physics:mass").Set(mass)
    print(f"[FERS] Mass: base=160kg, upper body halved — total ~181kg")

    # ── CoM at wheel axle level ───────────────────────────────────────────────
    UsdPhysics.MassAPI(bl).GetCenterOfMassAttr().Set(Gf.Vec3f(0.0, 0.0, -0.40))
    print(f"[FERS] CoM lowered to Z=-0.40 (wheel axle level)")

    # ── Carter-matched rigid body settings ────────────────────────────────────
    px_rb = PhysxSchema.PhysxRigidBodyAPI.Apply(bl)
    px_rb.GetAngularDampingAttr().Set(0.05)
    px_rb.GetLinearDampingAttr().Set(0.0)
    px_rb.GetLockedRotAxisAttr().Set(0)        # no lock — physical stability
    px_rb.GetDisableGravityAttr().Set(False)
    bl.CreateAttribute("physxRigidBody:cfmScale", Sdf.ValueTypeNames.Float, True).Set(0.025)
    print(f"[FERS] base_link: angDamp=0.05  linDamp=0  lockedRot=0  cfmScale=0.025")

    # ── Cylinder wheel collisions (Carter/EvoBOT approach) ────────────────────
    for side in ("left", "right"):
        # Remove old sphere if present
        for old in (f"{robot_path}/{side}_wheel/wheel_sphere",
                    f"{robot_path}/{side}_wheel/wheel_cylinder"):
            if stage.GetPrimAtPath(old).IsValid():
                stage.RemovePrim(old)

        cyl_path = f"{robot_path}/{side}_wheel/wheel_cylinder"
        cyl = UsdGeom.Cylinder.Define(stage, cyl_path)
        cyl.GetRadiusAttr().Set(WHEEL_RADIUS)
        cyl.GetHeightAttr().Set(WHEEL_WIDTH)
        cyl.GetAxisAttr().Set("X")   # axis = wheel rotation axis
        p = cyl.GetPrim()
        UsdPhysics.CollisionAPI.Apply(p)
        px_col = PhysxSchema.PhysxCollisionAPI.Apply(p)
        px_col.GetContactOffsetAttr().Set(0.002)
        px_col.GetRestOffsetAttr().Set(0.001)
        mat = UsdPhysics.MaterialAPI.Apply(p)
        mat.GetStaticFrictionAttr().Set(1.0)
        mat.GetDynamicFrictionAttr().Set(0.8)
        mat.GetRestitutionAttr().Set(0.0)
    print(f"[FERS] Cylinder wheels: axis=X  r={WHEEL_RADIUS}  w={WHEEL_WIDTH}  friction=1.0/0.8")

    # ── Wheel drives: Carter-matched damping ──────────────────────────────────
    for jname in ("left_wheel_joint", "right_wheel_joint"):
        j = stage.GetPrimAtPath(f"{robot_path}/joints/{jname}")
        if j.IsValid():
            drv = UsdPhysics.DriveAPI.Apply(j, "angular")
            drv.GetStiffnessAttr().Set(0.0)
            drv.GetDampingAttr().Set(17453.0)   # Carter: 17,453 Nm·s/rad
            drv.GetMaxForceAttr().Set(1e7)
    print(f"[FERS] Wheel drives: damping=17453 Nm·s/rad  maxForce=unlimited")

    # ── Rear caster wheel (Carter-style: swivel + axle) ───────────────────────
    # Provides 3-point stability — no lockedRotAxis needed
    # In /fers_robot local space: wheel centers at z=0.082
    PIVOT_POS = Gf.Vec3d(0, -0.30, 0.15)
    WHEEL_POS = Gf.Vec3d(0, -0.35, 0.082)

    # Pivot link (swivel bracket)
    piv_path = f"{robot_path}/rear_caster_pivot"
    if stage.GetPrimAtPath(piv_path).IsValid():
        stage.RemovePrim(piv_path)
    piv = stage.DefinePrim(piv_path, "Xform")
    UsdGeom.Xformable(piv).AddTranslateOp().Set(PIVOT_POS)
    UsdPhysics.RigidBodyAPI.Apply(piv)
    UsdPhysics.MassAPI.Apply(piv).GetMassAttr().Set(0.2)
    px_piv = PhysxSchema.PhysxRigidBodyAPI.Apply(piv)
    px_piv.GetAngularDampingAttr().Set(0.05)
    px_piv.GetLinearDampingAttr().Set(0.0)
    px_piv.GetSolverPositionIterationCountAttr().Set(16)

    # Wheel link
    whl_path = f"{robot_path}/rear_caster_wheel"
    if stage.GetPrimAtPath(whl_path).IsValid():
        stage.RemovePrim(whl_path)
    whl = stage.DefinePrim(whl_path, "Xform")
    UsdGeom.Xformable(whl).AddTranslateOp().Set(WHEEL_POS)
    UsdPhysics.RigidBodyAPI.Apply(whl)
    UsdPhysics.MassAPI.Apply(whl).GetMassAttr().Set(0.3)
    px_whl = PhysxSchema.PhysxRigidBodyAPI.Apply(whl)
    px_whl.GetAngularDampingAttr().Set(0.05)
    px_whl.GetLinearDampingAttr().Set(0.0)
    px_whl.GetSolverPositionIterationCountAttr().Set(16)

    # Sphere collision on wheel (zero friction — rolls freely in any direction)
    sph = UsdGeom.Sphere.Define(stage, f"{whl_path}/sphere")
    sph.GetRadiusAttr().Set(WHEEL_RADIUS)
    UsdPhysics.CollisionAPI.Apply(sph.GetPrim())
    px_c = PhysxSchema.PhysxCollisionAPI.Apply(sph.GetPrim())
    px_c.GetRestOffsetAttr().Set(0.001)
    px_c.GetContactOffsetAttr().Set(0.002)
    cmat = UsdPhysics.MaterialAPI.Apply(sph.GetPrim())
    cmat.GetStaticFrictionAttr().Set(0.0)
    cmat.GetDynamicFrictionAttr().Set(0.0)
    cmat.GetRestitutionAttr().Set(0.0)

    # Swivel joint: base_link → pivot (Z axis = yaw swivel)
    swivel_path = f"{robot_path}/rear_swivel_joint"
    if stage.GetPrimAtPath(swivel_path).IsValid():
        stage.RemovePrim(swivel_path)
    swivel = UsdPhysics.RevoluteJoint.Define(stage, swivel_path)
    swivel.GetBody0Rel().SetTargets([Sdf.Path(f"{robot_path}/base_link")])
    swivel.GetBody1Rel().SetTargets([Sdf.Path(piv_path)])
    swivel.GetAxisAttr().Set("Z")
    swivel.GetLocalPos0Attr().Set(Gf.Vec3f(0, -0.30, -0.3442))  # base_link local
    swivel.GetLocalPos1Attr().Set(Gf.Vec3f(0, 0, 0))
    swivel.GetLowerLimitAttr().Set(-1e6)
    swivel.GetUpperLimitAttr().Set(1e6)

    # Axle joint: pivot → wheel (X axis = rolling)
    axle_path = f"{robot_path}/rear_axle_joint"
    if stage.GetPrimAtPath(axle_path).IsValid():
        stage.RemovePrim(axle_path)
    axle = UsdPhysics.RevoluteJoint.Define(stage, axle_path)
    axle.GetBody0Rel().SetTargets([Sdf.Path(piv_path)])
    axle.GetBody1Rel().SetTargets([Sdf.Path(whl_path)])
    axle.GetAxisAttr().Set("X")
    axle.GetLocalPos0Attr().Set(Gf.Vec3f(0, -0.05, -0.068))
    axle.GetLocalPos1Attr().Set(Gf.Vec3f(0, 0, 0))
    axle.GetLowerLimitAttr().Set(-1e6)
    axle.GetUpperLimitAttr().Set(1e6)

    print(f"[FERS] Rear caster: pivot at {PIVOT_POS}  wheel at {WHEEL_POS}")


# ── Main ───────────────────────────────────────────────────────────────────────
print(f"[FERS] URDF exists: {os.path.exists(URDF_PATH)}")
robot_path = import_robot()

if robot_path:
    setup_physics(robot_path)
    print("\n[FERS] Ready — run start_trajectory.py then press Play")
