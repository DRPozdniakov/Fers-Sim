"""
FERS Robot Loader for Isaac Sim 5.1.0
Run this in Isaac Sim's Script Editor (Window > Script Editor)
or via: ./python.sh tools/load_fers_robot.py
"""
import omni.kit.commands
import omni.usd
from pxr import UsdPhysics, PhysxSchema, Gf, UsdGeom

URDF_PATH = "/isaac-sim/.local/share/ov/data/simulation/fers_robot.urdf"
ROBOT_PRIM_PATH = "/World/fers_robot"

# Joint drive configs: (stiffness, damping, max_force)
DRIVE_CONFIGS = {
    # Arms - heavy joints
    "shoulder_yaw": (1e5, 1e4, 200.0),
    "shoulder_pitch": (1e5, 1e4, 200.0),
    "shoulder_roll": (1e5, 1e4, 200.0),
    "elbow": (8e4, 8e3, 150.0),
    # Arms - lighter joints
    "forearm": (5e4, 5e3, 100.0),
    "wrist_pitch": (3e4, 3e3, 50.0),
    "wrist_yaw": (3e4, 3e3, 50.0),
    "wrist_roll": (2e4, 2e3, 30.0),
    # Gripper (linear drive)
    "gripper": (1e4, 1e3, 50.0),
    # Head
    "head_pan": (2e4, 2e3, 30.0),
    "eye": (5e3, 5e2, 10.0),
    # Wheels (velocity drive: stiffness=0)
    "wheel": (0.0, 1e3, 100.0),
}


def get_drive_config(joint_name):
    """Match joint name to drive config."""
    name_lower = joint_name.lower()
    for key, config in DRIVE_CONFIGS.items():
        if key in name_lower:
            return config
    return (1e4, 1e3, 50.0)


def setup_ground_plane():
    """Add a ground plane with physics collider."""
    stage = omni.usd.get_context().get_stage()

    ground_path = "/World/GroundPlane"
    if stage.GetPrimAtPath(ground_path).IsValid():
        return

    omni.kit.commands.execute(
        "CreatePrimCommand",
        prim_type="Xform",
        prim_path=ground_path,
    )

    plane_path = f"{ground_path}/CollisionPlane"
    omni.kit.commands.execute(
        "CreatePrimCommand",
        prim_type="Plane",
        prim_path=plane_path,
    )

    plane_prim = stage.GetPrimAtPath(plane_path)
    xformable = UsdGeom.Xformable(plane_prim)
    xformable.ClearXformOpOrder()
    xformable.AddScaleOp(precision=UsdGeom.XformOp.PrecisionDouble).Set(Gf.Vec3d(50.0, 50.0, 1.0))

    UsdPhysics.CollisionAPI.Apply(plane_prim)


def setup_physics_scene():
    """Create physics scene if not present."""
    stage = omni.usd.get_context().get_stage()

    scene_path = "/World/PhysicsScene"
    if stage.GetPrimAtPath(scene_path).IsValid():
        return

    UsdPhysics.Scene.Define(stage, scene_path)
    scene_prim = stage.GetPrimAtPath(scene_path)

    gravity_attr = scene_prim.GetAttribute("physics:gravityDirection")
    if gravity_attr:
        gravity_attr.Set(Gf.Vec3f(0.0, 0.0, -1.0))

    gravity_mag = scene_prim.GetAttribute("physics:gravityMagnitude")
    if gravity_mag:
        gravity_mag.Set(9.81)


def import_urdf():
    """Import URDF using Isaac Sim 5.1.0 URDF importer (isaacsim.asset.importer.urdf)."""
    from isaacsim.asset.importer.urdf import _urdf

    import_config = _urdf.ImportConfig()
    import_config.set_merge_fixed_joints(False)
    import_config.set_fix_base(True)
    import_config.set_make_default_prim(True)
    import_config.set_create_physics_scene(False)
    import_config.set_self_collision(False)
    import_config.set_convex_decomp(False)
    import_config.set_density(0.0)
    import_config.set_distance_scale(1.0)
    import_config.set_default_drive_type(1)  # 1 = position drive
    import_config.set_default_drive_strength(1e4)
    import_config.set_default_position_drive_damping(1e3)

    result, prim_path = omni.kit.commands.execute(
        "URDFParseAndImportFile",
        urdf_path=URDF_PATH,
        import_config=import_config,
        dest_path=ROBOT_PRIM_PATH,
    )

    if not result:
        print(f"[FERS] URDF import failed for {URDF_PATH}")
        return None

    print(f"[FERS] Robot imported at {prim_path}")
    return prim_path


def configure_articulation(robot_path):
    """Set up articulation root and tune joint drives."""
    stage = omni.usd.get_context().get_stage()
    robot_prim = stage.GetPrimAtPath(robot_path)

    if not robot_prim.IsValid():
        print(f"[FERS] Robot prim not found at {robot_path}")
        return

    # Articulation root (URDF importer usually adds this, but verify)
    if not robot_prim.HasAPI(UsdPhysics.ArticulationRootAPI):
        UsdPhysics.ArticulationRootAPI.Apply(robot_prim)

    # Disable self-collision
    physx_art = PhysxSchema.PhysxArticulationAPI.Apply(robot_prim)
    physx_art.GetEnabledSelfCollisionsAttr().Set(False)
    physx_art.GetSolverPositionIterationCountAttr().Set(64)
    physx_art.GetSolverVelocityIterationCountAttr().Set(16)

    # Tune each joint drive
    joint_count = 0
    for prim in stage.Traverse():
        if not prim.IsA(UsdPhysics.Joint):
            continue

        prim_path = str(prim.GetPath())
        if robot_path not in prim_path:
            continue

        joint_name = prim.GetName()
        stiffness, damping, max_force = get_drive_config(joint_name)

        # Determine drive type based on joint type
        if prim.IsA(UsdPhysics.PrismaticJoint):
            drive_api = UsdPhysics.DriveAPI.Get(prim, "linear")
            if not drive_api:
                drive_api = UsdPhysics.DriveAPI.Apply(prim, "linear")
        else:
            drive_api = UsdPhysics.DriveAPI.Get(prim, "angular")
            if not drive_api:
                drive_api = UsdPhysics.DriveAPI.Apply(prim, "angular")

        drive_api.GetStiffnessAttr().Set(stiffness)
        drive_api.GetDampingAttr().Set(damping)
        drive_api.GetMaxForceAttr().Set(max_force)

        joint_count += 1
        print(f"[FERS] Joint '{joint_name}': stiffness={stiffness}, damping={damping}, max_force={max_force}")

    print(f"[FERS] Configured {joint_count} joints")


def set_joint_target(joint_name, target_degrees):
    """
    Set target position for a joint by name.
    Use after pressing Play.

    Examples:
        set_joint_target("L_shoulder_yaw_joint", 45.0)
        set_joint_target("head_pan", -30.0)
        set_joint_target("L_elbow_joint", -90.0)
    """
    stage = omni.usd.get_context().get_stage()

    for prim in stage.Traverse():
        if not prim.IsA(UsdPhysics.Joint):
            continue
        if prim.GetName() != joint_name:
            continue

        if prim.IsA(UsdPhysics.PrismaticJoint):
            drive_api = UsdPhysics.DriveAPI.Get(prim, "linear")
            if drive_api:
                drive_api.GetTargetPositionAttr().Set(target_degrees)  # meters for prismatic
        else:
            drive_api = UsdPhysics.DriveAPI.Get(prim, "angular")
            if drive_api:
                drive_api.GetTargetPositionAttr().Set(target_degrees)

        print(f"[FERS] {joint_name} target -> {target_degrees}")
        return

    print(f"[FERS] Joint '{joint_name}' not found")


def demo_pose():
    """Set a demo pose - arms slightly raised."""
    targets = {
        "L_shoulder_pitch_joint": -45.0,
        "R_shoulder_pitch_joint": -45.0,
        "L_elbow_joint": -60.0,
        "R_elbow_joint": -60.0,
        "head_pan": 30.0,
    }
    for joint, angle in targets.items():
        set_joint_target(joint, angle)
    print("[FERS] Demo pose set - press Play to see motion")


# --- Main execution ---
import os
print(f"[FERS] URDF exists: {os.path.exists(URDF_PATH)}")
if os.path.exists(os.path.dirname(URDF_PATH) + '/meshes/'):
    meshes = os.listdir(os.path.dirname(URDF_PATH) + '/meshes/')
    print(f"[FERS] Meshes found: {len(meshes)} files")
else:
    print("[FERS] WARNING: meshes/ directory not found!")

print("[FERS] Setting up physics scene...")
setup_physics_scene()

print("[FERS] Adding ground plane...")
setup_ground_plane()

print("[FERS] Importing URDF...")
try:
    robot_path = import_urdf()
except Exception as e:
    robot_path = None
    print(f"[FERS] Import exception: {e}")

print(f"[FERS] import_urdf returned: {robot_path} (type: {type(robot_path)})")

if robot_path:
    print("[FERS] Configuring articulation and joint drives...")
    configure_articulation(robot_path)

    print("\n" + "=" * 60)
    print("[FERS] Robot loaded successfully!")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Press PLAY to start simulation")
    print("  2. Use Physics Inspector: Tools > Physics > Physics Inspector")
    print("  3. Or call from Script Editor:")
    print('     set_joint_target("L_shoulder_pitch_joint", -45.0)')
    print('     set_joint_target("head_pan", 30.0)')
    print('     demo_pose()  # sets a demo pose')
    print("\nAvailable joints:")
    print("  Arms: L/R_shoulder_yaw_joint, L/R_shoulder_pitch_joint,")
    print("        L/R_shoulder_roll_joint, L/R_elbow_joint,")
    print("        L/R_wrist_pitch_joint, L/R_wrist_yaw_joint,")
    print("        L/R_wrist_roll_joint, L/R_gripper_joint")
    print("  Head: head_pan, left_eye_joint, right_eye_joint")
    print("  Base: left_wheel_joint, right_wheel_joint")
