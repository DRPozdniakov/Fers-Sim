"""
FERS Robot T-Pose Finder for Isaac Sim 5.1.0
Cycles through arm poses to find the correct T-pose (arms horizontal sideways).
Run in Script Editor AFTER loading the robot.
"""
import asyncio
import omni.usd
import omni.timeline
from pxr import UsdPhysics


ROBOT_PRIM_PATH = "/World/fers_robot"

# Joint drive tuning (same as demo_animation)
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


def tune_joints():
    stage = omni.usd.get_context().get_stage()
    for prim in stage.Traverse():
        if not prim.IsA(UsdPhysics.Joint):
            continue
        if ROBOT_PRIM_PATH not in str(prim.GetPath()):
            continue
        drive_type = "linear" if prim.IsA(UsdPhysics.PrismaticJoint) else "angular"
        drive_api = UsdPhysics.DriveAPI.Get(prim, drive_type)
        if not drive_api:
            drive_api = UsdPhysics.DriveAPI.Apply(prim, drive_type)
        s, d, m = _get_drive_params(prim.GetName())
        drive_api.GetStiffnessAttr().Set(s)
        drive_api.GetDampingAttr().Set(d)
        drive_api.GetMaxForceAttr().Set(m)


def set_target(joint_name, value):
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


def apply_pose(targets):
    for joint, value in targets.items():
        set_target(joint, value)


# All arm joints zero
def zero_arms():
    apply_pose({
        "L_shoulder_yaw_joint": 0, "L_shoulder_pitch_joint": 0,
        "L_shoulder_roll_joint": 0, "L_elbow_joint": 0,
        "R_shoulder_yaw_joint": 0, "R_shoulder_pitch_joint": 0,
        "R_shoulder_roll_joint": 0, "R_elbow_joint": 0,
        "L_wrist_pitch_joint": 0, "L_wrist_yaw_joint": 0, "L_wrist_roll_joint": 0,
        "R_wrist_pitch_joint": 0, "R_wrist_yaw_joint": 0, "R_wrist_roll_joint": 0,
    })


# --- T-Pose candidates ---
# We test different combinations since the FBX mesh orientation is unknown

TPOSE_CANDIDATES = [
    (
        "Test 1: pitch=-90 (arms via pitch only)",
        {
            "L_shoulder_pitch_joint": -90.0,
            "R_shoulder_pitch_joint": -90.0,
            "L_elbow_joint": 0.0,
            "R_elbow_joint": 0.0,
        }
    ),
    (
        "Test 2: yaw=90 (arms via yaw only)",
        {
            "L_shoulder_yaw_joint": 90.0,
            "R_shoulder_yaw_joint": -90.0,
            "L_elbow_joint": 0.0,
            "R_elbow_joint": 0.0,
        }
    ),
    (
        "Test 3: yaw=90 + pitch=-90",
        {
            "L_shoulder_yaw_joint": 90.0,
            "R_shoulder_yaw_joint": -90.0,
            "L_shoulder_pitch_joint": -90.0,
            "R_shoulder_pitch_joint": -90.0,
            "L_elbow_joint": 0.0,
            "R_elbow_joint": 0.0,
        }
    ),
    (
        "Test 4: pitch=-90 + roll=90",
        {
            "L_shoulder_pitch_joint": -90.0,
            "R_shoulder_pitch_joint": -90.0,
            "L_shoulder_roll_joint": 90.0,
            "R_shoulder_roll_joint": -90.0,
            "L_elbow_joint": 0.0,
            "R_elbow_joint": 0.0,
        }
    ),
    (
        "Test 5: pitch=-45 + yaw=45",
        {
            "L_shoulder_yaw_joint": 45.0,
            "R_shoulder_yaw_joint": -45.0,
            "L_shoulder_pitch_joint": -45.0,
            "R_shoulder_pitch_joint": -45.0,
            "L_elbow_joint": 0.0,
            "R_elbow_joint": 0.0,
        }
    ),
    (
        "Test 6: yaw=-90 (opposite direction)",
        {
            "L_shoulder_yaw_joint": -90.0,
            "R_shoulder_yaw_joint": 90.0,
            "L_elbow_joint": 0.0,
            "R_elbow_joint": 0.0,
        }
    ),
    (
        "Test 7: pitch=90 (opposite pitch)",
        {
            "L_shoulder_pitch_joint": 90.0,
            "R_shoulder_pitch_joint": 90.0,
            "L_elbow_joint": 0.0,
            "R_elbow_joint": 0.0,
        }
    ),
]


async def find_tpose():
    """Cycle through T-pose candidates, 4 seconds each."""
    tune_joints()

    timeline = omni.timeline.get_timeline_interface()
    if not timeline.is_playing():
        timeline.play()
        await asyncio.sleep(1.5)

    print("[FERS] === T-Pose Finder ===")
    print("[FERS] Watch the robot arms — remember which test looks like a T-pose")
    print("")

    for i, (name, pose) in enumerate(TPOSE_CANDIDATES):
        zero_arms()
        await asyncio.sleep(1.0)

        print(f"[FERS] >>> {name}")
        apply_pose(pose)
        await asyncio.sleep(4.0)

    zero_arms()
    print("")
    print("[FERS] === Done ===")
    print("[FERS] Which test number had the best T-pose?")
    print("[FERS] Then we can set that as the default starting pose.")


asyncio.ensure_future(find_tpose())
