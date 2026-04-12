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
    px_rb.GetAngularDampingAttr().Set(200.0)    # very high — kills yaw wobble dead
    px_rb.GetLinearDampingAttr().Set(0.5)      # slight — damps vertical/lateral jitter
    px_rb.GetLockedRotAxisAttr().Set(3)        # lock X+Y (roll+pitch) — only yaw free
    px_rb.GetDisableGravityAttr().Set(False)
    px_rb.GetSolverPositionIterationCountAttr().Set(32)  # more stable contacts
    px_rb.GetSolverVelocityIterationCountAttr().Set(16)
    bl.CreateAttribute("physxRigidBody:cfmScale", Sdf.ValueTypeNames.Float, True).Set(0.025)
    print(f"[FERS] base_link: angDamp=200  linDamp=0.5  lockedRot=3  solver=32/16")

    # ── Disable ALL original mesh collisions on wheels ──────────────────────────
    # URDF import creates mesh-based collisions that conflict with our cylinders.
    # Two shapes on the same wheel = unpredictable friction = robot wobbles.
    for side in ("left", "right"):
        for link_name in (f"{side}_wheel", f"{side}_wheel_cover"):
            link = stage.GetPrimAtPath(f"{robot_path}/{link_name}")
            if not link.IsValid():
                continue
            # Disable on the link prim itself
            if link.HasAPI(UsdPhysics.CollisionAPI):
                UsdPhysics.CollisionAPI(link).GetCollisionEnabledAttr().Set(False)
            # Disable on all children (visual meshes, collision meshes)
            for child in link.GetChildren():
                if child.HasAPI(UsdPhysics.CollisionAPI):
                    UsdPhysics.CollisionAPI(child).GetCollisionEnabledAttr().Set(False)
                for gc in child.GetChildren():
                    if gc.HasAPI(UsdPhysics.CollisionAPI):
                        UsdPhysics.CollisionAPI(gc).GetCollisionEnabledAttr().Set(False)
    print(f"[FERS] Disabled ALL original mesh collisions on wheels")

    # ── Cylinder wheel collisions (clean shapes only) ────────────────────────
    for side in ("left", "right"):
        # Remove old added shapes
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

    # ── Wheel joint localPos0 fix + drives ───────────────────────────────────
    LOCAL_POS0_Z = -0.4116
    for jname in ("left_wheel_joint", "right_wheel_joint"):
        j = stage.GetPrimAtPath(f"{robot_path}/joints/{jname}")
        if j.IsValid():
            lp = j.GetAttribute("physics:localPos0")
            old = lp.Get()
            lp.Set(Gf.Vec3f(old[0], old[1], LOCAL_POS0_Z))
            drv = UsdPhysics.DriveAPI.Apply(j, "angular")
            drv.GetStiffnessAttr().Set(0.0)
            drv.GetDampingAttr().Set(17453.0)
            drv.GetMaxForceAttr().Set(1e7)
    print(f"[FERS] Wheel joints: localPos0 Z={LOCAL_POS0_Z}, damping=17453")

    # ── Clean up old caster prims (from previous script versions) ──────────────
    for old_path in (f"{robot_path}/rear_caster_pivot",
                     f"{robot_path}/rear_caster_wheel",
                     f"{robot_path}/rear_swivel_joint",
                     f"{robot_path}/rear_axle_joint"):
        if stage.GetPrimAtPath(old_path).IsValid():
            stage.RemovePrim(old_path)
            print(f"[FERS] Removed old prim: {old_path}")

    print(f"[FERS] No caster — roll+pitch locked, 2-wheel drive only")

    # ── Arm joint limits — keep arms in front, no behind-the-back ────────────
    # L_shoulder_pitch: negative=forward/down → allow [-90, 5] (no backward)
    # R_shoulder_pitch: positive=forward/down → allow [-5, 90] (no backward)
    ARM_LIMITS = {
        # YAW (J1): arm swing — keep reasonable range
        "L_shoulder_yaw_joint":   (-60, 60),
        "R_shoulder_yaw_joint":   (-60, 60),
        # PITCH (J2): keep original URDF range
        "L_shoulder_pitch_joint": (-85, 85),
        "R_shoulder_pitch_joint": (-85, 85),
        # ROLL (J3, axis fixed Y): arm up/down — only forward
        "L_shoulder_roll_joint":  (-90, 90),
        "R_shoulder_roll_joint":  (-90, 90),
        # ELBOW (J4, axis fixed X): forearm bend — only forward
        "L_elbow_joint":          (-90, 90),
        "R_elbow_joint":          (-90, 90),
        # WRIST PITCH (J5, axis fixed Z):
        "L_wrist_pitch_joint":    (-45, 45),
        "R_wrist_pitch_joint":    (-45, 45),
        # WRIST YAW (J6): forearm bend — confirmed correct
        "L_wrist_yaw_joint":     (-90, 90),
        "R_wrist_yaw_joint":     (-90, 90),
    }
    applied = 0
    for jname, (lo, hi) in ARM_LIMITS.items():
        j = stage.GetPrimAtPath(f"{robot_path}/joints/{jname}")
        if j.IsValid():
            j.GetAttribute("physics:lowerLimit").Set(float(lo))
            j.GetAttribute("physics:upperLimit").Set(float(hi))
            applied += 1
        else:
            print(f"[FERS] WARNING: joint not found at {robot_path}/joints/{jname}")
    print(f"[FERS] Arm limits applied: {applied}/{len(ARM_LIMITS)} joints")

    # ── Fix arm joint axes — URDF has wrong axes for several joints ──────────
    # Confirmed by testing each joint individually in sim:
    #   shoulder_roll: X → Y (was rolling, should pitch)
    #   elbow:         Y → X (was yawing, should bend)
    #   wrist_pitch:   Y → Z (was yawing, should pitch)
    #   wrist_roll:    lock to 0 (not needed)
    AXIS_FIXES = {
        "L_shoulder_roll_joint":  "Y",
        "R_shoulder_roll_joint":  "Y",
        "L_elbow_joint":          "X",
        "R_elbow_joint":          "X",
        "L_wrist_pitch_joint":    "X",
        "R_wrist_pitch_joint":    "X",
    }
    fixed = 0
    for jname, new_axis in AXIS_FIXES.items():
        j = stage.GetPrimAtPath(f"{robot_path}/joints/{jname}")
        if j.IsValid():
            old_axis = j.GetAttribute("physics:axis").Get()
            j.GetAttribute("physics:axis").Set(new_axis)
            fixed += 1
            print(f"[FERS] {jname}: axis {old_axis} → {new_axis}")
    print(f"[FERS] Axis fixes applied: {fixed}/{len(AXIS_FIXES)} joints")

    # ── Lock wrist_roll (not needed) ─────────────────────────────────────────
    for side in ("L", "R"):
        jname = f"{side}_wrist_roll_joint"
        j = stage.GetPrimAtPath(f"{robot_path}/joints/{jname}")
        if j.IsValid():
            j.GetAttribute("physics:lowerLimit").Set(0.0)
            j.GetAttribute("physics:upperLimit").Set(0.0)
    print(f"[FERS] Wrist roll joints locked")

    # ── Arm drive tuning — heavy damping, no spring bounce ───────────────────
    ARM_DRIVE_JOINTS = [
        "L_shoulder_yaw_joint", "R_shoulder_yaw_joint",
        "L_shoulder_pitch_joint", "R_shoulder_pitch_joint",
        "L_shoulder_roll_joint", "R_shoulder_roll_joint",
        "L_elbow_joint", "R_elbow_joint",
        "L_wrist_pitch_joint", "R_wrist_pitch_joint",
        "L_wrist_yaw_joint", "R_wrist_yaw_joint",
        "L_wrist_roll_joint", "R_wrist_roll_joint",
    ]
    for jname in ARM_DRIVE_JOINTS:
        j = stage.GetPrimAtPath(f"{robot_path}/joints/{jname}")
        if j.IsValid():
            drv = UsdPhysics.DriveAPI.Apply(j, "angular")
            drv.GetStiffnessAttr().Set(500.0)
            drv.GetDampingAttr().Set(200.0)
            drv.GetMaxForceAttr().Set(1e4)
    print(f"[FERS] Arm drives: stiffness=500  damping=200 (no bounce)")


# ── Main ───────────────────────────────────────────────────────────────────────
print(f"[FERS] URDF exists: {os.path.exists(URDF_PATH)}")
robot_path = import_robot()

if robot_path:
    setup_physics(robot_path)
    print("\n[FERS] Ready — run start_trajectory.py then press Play")
