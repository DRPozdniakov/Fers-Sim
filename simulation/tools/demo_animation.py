"""
FERS Robot Demo Animation for Isaac Sim 5.1.0
Run in Script Editor AFTER loading the robot and control_joints.py

Moves the robot through a sequence of poses with timing.
"""
import asyncio
import omni.usd
import omni.timeline
from pxr import UsdPhysics


ROBOT_PRIM_PATH = "/World/fers_robot"

# Joint drive tuning: (stiffness, damping, max_force)
# Rule of thumb: damping ~= stiffness / 10
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
    "wheel":          (0.0, 50.0, 100.0),  # velocity drive
    "torso":          (1000.0, 100.0, 500.0),
    "wheel_cover":    (100.0, 10.0, 50.0),
}


def _get_drive_params(joint_name):
    name_lower = joint_name.lower()
    for key, params in JOINT_DRIVES.items():
        if key in name_lower:
            return params
    return (200.0, 20.0, 50.0)


def tune_all_joints():
    """Fix stiffness/damping ratio on all joints to stop shaking."""
    stage = omni.usd.get_context().get_stage()
    count = 0
    for prim in stage.Traverse():
        if not prim.IsA(UsdPhysics.Joint):
            continue
        if ROBOT_PRIM_PATH not in str(prim.GetPath()):
            continue

        drive_type = "linear" if prim.IsA(UsdPhysics.PrismaticJoint) else "angular"
        drive_api = UsdPhysics.DriveAPI.Get(prim, drive_type)
        if not drive_api:
            drive_api = UsdPhysics.DriveAPI.Apply(prim, drive_type)

        stiffness, damping, max_force = _get_drive_params(prim.GetName())
        drive_api.GetStiffnessAttr().Set(stiffness)
        drive_api.GetDampingAttr().Set(damping)
        drive_api.GetMaxForceAttr().Set(max_force)
        count += 1

    print(f"[FERS] Tuned {count} joints (stiffness:damping = 10:1)")


def _set_target(joint_name, value):
    stage = omni.usd.get_context().get_stage()
    for prim in stage.Traverse():
        if not prim.IsA(UsdPhysics.Joint):
            continue
        if prim.GetName() != joint_name:
            continue
        if ROBOT_PRIM_PATH not in str(prim.GetPath()):
            continue
        drive_type = "linear" if prim.IsA(UsdPhysics.PrismaticJoint) else "angular"
        drive_api = UsdPhysics.DriveAPI.Get(prim, drive_type)
        if not drive_api:
            drive_api = UsdPhysics.DriveAPI.Apply(prim, drive_type)
        drive_api.GetTargetPositionAttr().Set(float(value))
        return


def _set_velocity(joint_name, value):
    stage = omni.usd.get_context().get_stage()
    for prim in stage.Traverse():
        if not prim.IsA(UsdPhysics.Joint):
            continue
        if prim.GetName() != joint_name:
            continue
        if ROBOT_PRIM_PATH not in str(prim.GetPath()):
            continue
        drive_type = "linear" if prim.IsA(UsdPhysics.PrismaticJoint) else "angular"
        drive_api = UsdPhysics.DriveAPI.Get(prim, drive_type)
        if not drive_api:
            drive_api = UsdPhysics.DriveAPI.Apply(prim, drive_type)
        drive_api.GetTargetVelocityAttr().Set(float(value))
        return


def apply_pose(targets):
    for joint, value in targets.items():
        _set_target(joint, value)


# --- Pose definitions ---

POSE_ZERO = {
    "L_shoulder_yaw_joint": 0, "L_shoulder_pitch_joint": 0,
    "L_shoulder_roll_joint": 0, "L_elbow_joint": 0,
    "L_forearm_joint": 0, "L_wrist_pitch_joint": 0,
    "L_wrist_yaw_joint": 0, "L_wrist_roll_joint": 0,
    "R_shoulder_yaw_joint": 0, "R_shoulder_pitch_joint": 0,
    "R_shoulder_roll_joint": 0, "R_elbow_joint": 0,
    "R_forearm_joint": 0, "R_wrist_pitch_joint": 0,
    "R_wrist_yaw_joint": 0, "R_wrist_roll_joint": 0,
    "head_pan": 0,
}

POSE_WAVE_UP = {
    "R_shoulder_pitch_joint": -120.0,
    "R_shoulder_yaw_joint": 20.0,
    "R_elbow_joint": -40.0,
    "R_wrist_yaw_joint": 30.0,
}

POSE_WAVE_DOWN = {
    "R_shoulder_pitch_joint": -120.0,
    "R_shoulder_yaw_joint": 20.0,
    "R_elbow_joint": -90.0,
    "R_wrist_yaw_joint": -30.0,
}

POSE_ARMS_OUT = {
    "L_shoulder_pitch_joint": -90.0,
    "R_shoulder_pitch_joint": -90.0,
    "L_elbow_joint": 0.0,
    "R_elbow_joint": 0.0,
}

POSE_ARMS_FLEX = {
    "L_shoulder_pitch_joint": -90.0,
    "R_shoulder_pitch_joint": -90.0,
    "L_elbow_joint": -90.0,
    "R_elbow_joint": -90.0,
}

POSE_BOW = {
    "L_shoulder_pitch_joint": -10.0,
    "R_shoulder_pitch_joint": -10.0,
    "L_elbow_joint": -5.0,
    "R_elbow_joint": -5.0,
    "head_pan": 0.0,
}

# --- Animation sequence ---

SEQUENCE = [
    ("Starting position",    POSE_ZERO,      1.5),
    ("Look left",            {"head_pan": 45.0}, 1.0),
    ("Look right",           {"head_pan": -45.0}, 1.0),
    ("Look center",          {"head_pan": 0.0}, 0.5),
    ("Wave hello (up)",      POSE_WAVE_UP,   0.8),
    ("Wave hello (down)",    POSE_WAVE_DOWN, 0.6),
    ("Wave hello (up)",      POSE_WAVE_UP,   0.6),
    ("Wave hello (down)",    POSE_WAVE_DOWN, 0.6),
    ("Wave hello (up)",      POSE_WAVE_UP,   0.6),
    ("Return to zero",       POSE_ZERO,      1.5),
    ("Arms out",             POSE_ARMS_OUT,  1.5),
    ("Flex!",                POSE_ARMS_FLEX, 1.0),
    ("Arms out",             POSE_ARMS_OUT,  0.8),
    ("Flex!",                POSE_ARMS_FLEX, 1.0),
    ("Return to zero",       POSE_ZERO,      1.5),
    ("Bow",                  POSE_BOW,       2.0),
    ("Stand up",             POSE_ZERO,      1.5),
    ("Done!",                POSE_ZERO,      0.5),
]


async def run_demo():
    """Run the full animation sequence."""
    print("[FERS] Tuning joints to stop shaking...")
    tune_all_joints()

    timeline = omni.timeline.get_timeline_interface()
    if not timeline.is_playing():
        timeline.play()
        await asyncio.sleep(2.0)  # let physics settle

    print("[FERS] === Demo Animation Starting ===")

    for step_name, pose, duration in SEQUENCE:
        print(f"[FERS] {step_name}")
        apply_pose(pose)
        await asyncio.sleep(duration)

    print("[FERS] === Demo Animation Complete ===")


# --- Run ---
asyncio.ensure_future(run_demo())
