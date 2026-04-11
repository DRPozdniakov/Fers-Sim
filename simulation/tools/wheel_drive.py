"""
FERS Robot — ScriptNode wheel controller (Action Graph).
Uses Articulation API via builtins._fers_robot.

REQUIRES: Robot initialized via MCP execute_script AFTER Play:
    from omni.isaac.core import World
    from omni.isaac.core.articulations import Articulation
    import builtins
    world = World.instance() or World()
    world.initialize_physics()
    robot = Articulation("/fers_robot")
    robot.initialize()
    builtins._fers_robot = robot

Drives a 1m x 1m square trajectory (4 legs: forward + 90° turn).
"""
import math
import numpy as np
import builtins

FWD_VEL = 0.40 / 0.0712       # 5.618 rad/s
TURN_VEL = (50.0 * math.pi / 180) * (0.328 / 2) / 0.0712  # 2.01 rad/s

WARMUP_F = 90
FORWARD_F = 156
TURN_F = 110

_state = "WAIT"
_frame = 0
_leg = 0

def setup(db):
    global _state, _frame, _leg
    _state = "WAIT"
    _frame = 0
    _leg = 0
    print("[drive] setup - waiting for robot init via MCP")

def compute(db):
    global _state, _frame, _leg

    robot = getattr(builtins, '_fers_robot', None)
    if robot is None:
        return

    _frame += 1

    if _state == "WAIT":
        _state = "WARMUP"
        _frame = 0
        print("[drive] Robot found! WARMUP")
        return

    if _state == "WARMUP":
        _sv(robot, 0, 0)
        if _frame >= WARMUP_F:
            _state = "FWD"
            _frame = 0
            print(f"[drive] leg {_leg+1}/4 FORWARD")

    elif _state == "FWD":
        _sv(robot, FWD_VEL, FWD_VEL)
        if _frame >= FORWARD_F:
            _state = "TURN"
            _frame = 0
            print(f"[drive] leg {_leg+1}/4 TURN")

    elif _state == "TURN":
        _sv(robot, -TURN_VEL, TURN_VEL)
        if _frame >= TURN_F:
            _leg += 1
            _frame = 0
            if _leg >= 4:
                _state = "DONE"
                _sv(robot, 0, 0)
                print("[drive] DONE!")
            else:
                _state = "FWD"
                print(f"[drive] leg {_leg+1}/4 FORWARD")

    elif _state == "DONE":
        _sv(robot, 0, 0)

def _sv(robot, left, right):
    try:
        from omni.isaac.core.utils.types import ArticulationAction
        action = ArticulationAction(
            joint_velocities=np.array([left, right]),
            joint_indices=np.array([0, 1])
        )
        robot.apply_action(action)
    except Exception:
        pass
