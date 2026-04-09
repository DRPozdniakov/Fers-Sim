"""
FERS Robot Joint Control for Isaac Sim 5.1.0
Run in Script Editor (Window > Script Editor) AFTER loading the robot.

Three API approaches provided (from lowest to highest level):
  1. USD API  - UsdPhysics.DriveAPI (works everywhere, no initialization needed)
  2. Core API - SingleArticulation (high-level, needs world.reset/play)
  3. Core API - Articulation view (batch/tensor, needs world.reset/play)

The USD API (Approach 1) is the most reliable for Script Editor one-shots.
The Core API (Approaches 2-3) is better for physics callbacks and loops.

Isaac Sim 5.1.0 namespace: isaacsim.core.* (replaces old omni.isaac.core.*)
"""
import logging
import math

import numpy as np
import omni.usd
from pxr import UsdPhysics

logger = logging.getLogger("[FERS]")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(name)s %(message)s"))
    logger.addHandler(handler)

ROBOT_PRIM_PATH = "/World/fers_robot"


# =============================================================================
# UTILITY: Discover all joints on the robot
# =============================================================================

def list_joints(robot_path=ROBOT_PRIM_PATH):
    """
    Enumerate all physics joints under the robot prim.
    Returns a list of dicts with joint info.
    Works without simulation running.
    """
    stage = omni.usd.get_context().get_stage()
    robot_prim = stage.GetPrimAtPath(robot_path)
    if not robot_prim.IsValid():
        logger.error("Robot prim not found at %s", robot_path)
        return []

    joints = []
    for prim in stage.Traverse():
        if not prim.IsA(UsdPhysics.Joint):
            continue
        prim_path = str(prim.GetPath())
        if robot_path not in prim_path:
            continue

        joint_type = "revolute"
        drive_type = "angular"
        if prim.IsA(UsdPhysics.PrismaticJoint):
            joint_type = "prismatic"
            drive_type = "linear"

        drive_api = UsdPhysics.DriveAPI.Get(prim, drive_type)
        has_drive = drive_api and drive_api.GetStiffnessAttr().Get() is not None

        info = {
            "name": prim.GetName(),
            "path": prim_path,
            "type": joint_type,
            "drive_type": drive_type,
            "has_drive": has_drive,
        }

        if has_drive:
            info["stiffness"] = drive_api.GetStiffnessAttr().Get()
            info["damping"] = drive_api.GetDampingAttr().Get()
            info["max_force"] = drive_api.GetMaxForceAttr().Get()
            target_pos = drive_api.GetTargetPositionAttr().Get()
            info["target_position"] = target_pos

        joints.append(info)

    logger.info("Found %d joints under %s:", len(joints), robot_path)
    for j in joints:
        drive_info = ""
        if j["has_drive"]:
            drive_info = (
                f"  stiff={j['stiffness']}, damp={j['damping']}, "
                f"max_f={j['max_force']}, target={j['target_position']}"
            )
        logger.info(
            "  [%s] %s (%s)%s",
            j["type"][:3], j["name"], j["drive_type"], drive_info,
        )
    return joints


# =============================================================================
# APPROACH 1: USD API (UsdPhysics.DriveAPI) - works in Script Editor directly
# =============================================================================

def set_joint_target_usd(joint_name, target_value, robot_path=ROBOT_PRIM_PATH):
    """
    Set target position on a joint using UsdPhysics.DriveAPI.
    - For revolute joints: target_value in degrees.
    - For prismatic joints: target_value in stage length units (meters).
    Works both before and during simulation.
    """
    stage = omni.usd.get_context().get_stage()

    for prim in stage.Traverse():
        if not prim.IsA(UsdPhysics.Joint):
            continue
        if prim.GetName() != joint_name:
            continue
        if robot_path not in str(prim.GetPath()):
            continue

        drive_type = "linear" if prim.IsA(UsdPhysics.PrismaticJoint) else "angular"
        drive_api = UsdPhysics.DriveAPI.Get(prim, drive_type)
        if not drive_api:
            drive_api = UsdPhysics.DriveAPI.Apply(prim, drive_type)

        drive_api.GetTargetPositionAttr().Set(float(target_value))
        logger.info("%s -> target %s (%s)", joint_name, target_value, drive_type)
        return True

    logger.error("Joint '%s' not found under %s", joint_name, robot_path)
    return False


def set_joint_velocity_usd(joint_name, target_velocity, robot_path=ROBOT_PRIM_PATH):
    """
    Set target velocity on a joint using UsdPhysics.DriveAPI.
    - For revolute joints: target_velocity in degrees/second.
    - For prismatic joints: target_velocity in stage length units/second.
    Useful for wheels (stiffness=0, damping>0).
    """
    stage = omni.usd.get_context().get_stage()

    for prim in stage.Traverse():
        if not prim.IsA(UsdPhysics.Joint):
            continue
        if prim.GetName() != joint_name:
            continue
        if robot_path not in str(prim.GetPath()):
            continue

        drive_type = "linear" if prim.IsA(UsdPhysics.PrismaticJoint) else "angular"
        drive_api = UsdPhysics.DriveAPI.Get(prim, drive_type)
        if not drive_api:
            drive_api = UsdPhysics.DriveAPI.Apply(prim, drive_type)

        drive_api.GetTargetVelocityAttr().Set(float(target_velocity))
        logger.info("%s -> velocity %s (%s)", joint_name, target_velocity, drive_type)
        return True

    logger.error("Joint '%s' not found under %s", joint_name, robot_path)
    return False


def set_pose_usd(targets, robot_path=ROBOT_PRIM_PATH):
    """
    Set multiple joint targets at once using USD API.
    targets: dict of {joint_name: target_degrees}
    """
    for joint_name, value in targets.items():
        set_joint_target_usd(joint_name, value, robot_path)


# =============================================================================
# APPROACH 2: Core API (SingleArticulation) - for physics callbacks
# =============================================================================

def create_single_articulation(robot_path=ROBOT_PRIM_PATH):
    """
    Wrap existing robot prim with SingleArticulation (isaacsim.core.prims).
    Returns the articulation object.

    IMPORTANT: Call this AFTER world.reset_async() or world.reset().
    The robot must already exist in the stage.

    Usage in Script Editor:
        import asyncio
        from isaacsim.core.api.world import World
        from isaacsim.core.prims import SingleArticulation
        from isaacsim.core.utils.types import ArticulationAction

        async def control():
            world = World()
            await world.initialize_simulation_context_async()
            await world.reset_async()

            robot = SingleArticulation(prim_path="/World/fers_robot", name="fers")
            robot.initialize()

            print("DOFs:", robot.num_dof)
            print("Joint positions:", robot.get_joint_positions())

            await world.play_async()

            action = ArticulationAction(
                joint_positions=np.zeros(robot.num_dof)
            )
            robot.apply_action(action)

        asyncio.ensure_future(control())
    """
    from isaacsim.core.prims import SingleArticulation

    robot = SingleArticulation(prim_path=robot_path, name="fers_robot")
    robot.initialize()
    logger.info("SingleArticulation created at %s", robot_path)
    logger.info("  num_dof: %d", robot.num_dof)
    logger.info("  joint_positions: %s", robot.get_joint_positions())
    return robot


def create_articulation_view(robot_path=ROBOT_PRIM_PATH):
    """
    Wrap existing robot prim with Articulation view (isaacsim.core.prims).
    Returns the articulation view object.

    IMPORTANT: Requires world.reset() first to initialize the physics backend.

    Usage in Script Editor:
        import asyncio
        from isaacsim.core.api.world import World
        from isaacsim.core.prims import Articulation

        async def control():
            world = World()
            await world.initialize_simulation_context_async()
            await world.reset_async()

            arm = Articulation(prim_paths_expr="/World/fers_robot", name="fers")

            print("Joints:", arm.num_joints)
            print("Names:", arm.joint_names)
            print("Limits:", arm.get_dof_limits())
            print("Positions:", arm.get_joint_positions())

            # Set positions directly (tensor API, note double brackets)
            arm.set_joint_positions([[-45.0, -45.0, 0, -60.0, -60.0, 0, 0, 0, 0]])

        asyncio.ensure_future(control())
    """
    from isaacsim.core.prims import Articulation

    arm = Articulation(prim_paths_expr=robot_path, name="fers_robot_view")
    logger.info("Articulation view created at %s", robot_path)
    logger.info("  num_joints: %d", arm.num_joints)
    logger.info("  joint_names: %s", arm.joint_names)
    return arm


# =============================================================================
# APPROACH 3: Physics stepping and callbacks
# =============================================================================

def start_simulation_and_control():
    """
    Full async example: start physics, apply joint targets in a callback.
    Paste this entire function + the asyncio.ensure_future call into Script Editor.

    Usage in Script Editor:
        # Copy-paste this block:
        import asyncio
        asyncio.ensure_future(start_simulation_and_control())
    """
    import asyncio

    async def _run():
        from isaacsim.core.api.world import World
        from isaacsim.core.prims import SingleArticulation
        from isaacsim.core.utils.types import ArticulationAction

        world = World(stage_units_in_meters=1.0)
        await world.initialize_simulation_context_async()
        await world.reset_async()

        robot = SingleArticulation(
            prim_path=ROBOT_PRIM_PATH, name="fers_ctrl",
        )
        robot.initialize()

        logger.info("DOFs: %d", robot.num_dof)
        logger.info("Joint positions: %s", robot.get_joint_positions())

        # Define a pose (adjust indices to match your robot's DOF order)
        # Use list_joints() first to see the joint order
        target_positions = np.zeros(robot.num_dof)

        step_count = [0]

        def physics_callback(step_size):
            step_count[0] += 1
            if step_count[0] == 1:
                # Apply pose on first physics step
                action = ArticulationAction(joint_positions=target_positions)
                robot.apply_action(action)
                logger.info("Applied initial pose")

            if step_count[0] % 120 == 0:
                pos = robot.get_joint_positions()
                logger.info("Step %d, positions: %s", step_count[0], pos)

        world.add_physics_callback("fers_control", callback_fn=physics_callback)
        await world.play_async()
        logger.info("Simulation playing - robot under callback control")

    import asyncio
    return asyncio.ensure_future(_run())


# =============================================================================
# CONVENIENCE: timeline play/pause from Script Editor
# =============================================================================

def play_simulation():
    """Start the simulation timeline (equivalent to pressing Play)."""
    import omni.timeline
    timeline = omni.timeline.get_timeline_interface()
    timeline.play()
    logger.info("Simulation PLAY")


def pause_simulation():
    """Pause the simulation timeline."""
    import omni.timeline
    timeline = omni.timeline.get_timeline_interface()
    timeline.pause()
    logger.info("Simulation PAUSE")


def stop_simulation():
    """Stop the simulation timeline (equivalent to pressing Stop)."""
    import omni.timeline
    timeline = omni.timeline.get_timeline_interface()
    timeline.stop()
    logger.info("Simulation STOP")


# =============================================================================
# DEMO POSES
# =============================================================================

DEMO_POSES = {
    "zero": {},  # all joints to 0 via list_joints
    "arms_up": {
        "L_shoulder_pitch_joint": -45.0,
        "R_shoulder_pitch_joint": -45.0,
        "L_elbow_joint": -60.0,
        "R_elbow_joint": -60.0,
    },
    "wave": {
        "R_shoulder_pitch_joint": -90.0,
        "R_shoulder_yaw_joint": 30.0,
        "R_elbow_joint": -90.0,
        "R_wrist_yaw_joint": 45.0,
    },
    "look_left": {
        "head_pan": 45.0,
    },
    "look_right": {
        "head_pan": -45.0,
    },
}


def demo_pose(pose_name="arms_up"):
    """
    Apply a named demo pose using USD API.
    Available poses: zero, arms_up, wave, look_left, look_right
    """
    if pose_name == "zero":
        joints = list_joints()
        targets = {j["name"]: 0.0 for j in joints if j["type"] == "revolute"}
        set_pose_usd(targets)
        logger.info("All revolute joints set to 0")
        return

    if pose_name not in DEMO_POSES:
        logger.error("Unknown pose '%s'. Available: %s", pose_name, list(DEMO_POSES.keys()))
        return

    set_pose_usd(DEMO_POSES[pose_name])
    logger.info("Pose '%s' applied - press Play if not running", pose_name)


def drive_wheels(left_velocity=150.0, right_velocity=150.0):
    """
    Set wheel velocity targets (degrees/second).
    Wheels use velocity drive (stiffness=0, damping>0).
    """
    set_joint_velocity_usd("left_wheel_joint", left_velocity)
    set_joint_velocity_usd("right_wheel_joint", right_velocity)


# =============================================================================
# MAIN - run when pasted into Script Editor
# =============================================================================

if __name__ == "__main__" or True:  # always run in Script Editor
    logger.info("=" * 60)
    logger.info("FERS Joint Control Script")
    logger.info("=" * 60)

    # Step 1: List all joints
    joints = list_joints()

    if not joints:
        logger.error("No joints found. Is the robot loaded at %s?", ROBOT_PRIM_PATH)
    else:
        logger.info("")
        logger.info("Quick reference - copy/paste into Script Editor:")
        logger.info("  # List joints:")
        logger.info("  list_joints()")
        logger.info("")
        logger.info("  # Set single joint (USD API, works anytime):")
        logger.info('  set_joint_target_usd("L_shoulder_pitch_joint", -45.0)')
        logger.info('  set_joint_target_usd("head_pan", 30.0)')
        logger.info("")
        logger.info("  # Set wheel velocity:")
        logger.info("  drive_wheels(150.0, 150.0)")
        logger.info("")
        logger.info("  # Demo poses:")
        logger.info('  demo_pose("arms_up")')
        logger.info('  demo_pose("wave")')
        logger.info('  demo_pose("zero")')
        logger.info("")
        logger.info("  # Start/stop simulation:")
        logger.info("  play_simulation()")
        logger.info("  pause_simulation()")
        logger.info("  stop_simulation()")
        logger.info("")
        logger.info("  # Core API (async, for callbacks):")
        logger.info("  import asyncio")
        logger.info("  asyncio.ensure_future(start_simulation_and_control())")
