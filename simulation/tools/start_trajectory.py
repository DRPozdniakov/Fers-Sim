"""
FERS Robot — square trajectory using direct force on base_link.

Bypasses wheel-ground friction entirely. Applies linear force
and torque directly to base_link rigid body for reliable motion
regardless of wheel/ground contact setup.

Load via MCP or Script Editor, then press Play.
"""

import omni.physx
import omni.usd
import omni.isaac.dynamic_control._dynamic_control as dc_module
import builtins
import math
from pxr import UsdGeom, Gf

# ── Constants ────────────────────────────────────────────────────────────────
FORWARD_SPEED = 0.25     # m/s
TURN_DEG_S    = 45.0     # deg/s of robot heading
FORWARD_FORCE = 80.0     # N  (enough to move 80kg robot)
TURN_TORQUE   = 40.0     # Nm (around Z axis)

WARMUP_T  = 2.0
FORWARD_T = 1.0 / FORWARD_SPEED   # 4.0 s → 1 m
TURN_T    = 90.0 / TURN_DEG_S     # 2.0 s → 90°

# ── State ────────────────────────────────────────────────────────────────────
_st = ["INIT"]; _el = [0.0]; _lg = [0]
_dc = [None]; _rb = [None]; _heading = [0.0]
_ld = [None]; _rd = [None]

FWD_DEG  = (FORWARD_SPEED / 0.0712) * (180.0 / math.pi)  # wheel visual spin rate
TURN_DEG = (TURN_DEG_S * math.pi / 180.0) * (0.328 / 2.0) / 0.0712 * (180.0 / math.pi)


def _init_dc():
    dc = dc_module.acquire_dynamic_control_interface()
    _dc[0] = dc
    rb = dc.get_rigid_body("/fers_robot/base_link")
    if rb == dc_module.INVALID_HANDLE:
        print("[sq] ERROR: rigid body not found at /fers_robot/base_link")
        return False
    _rb[0] = rb
    _heading[0] = 0.0
    # Also grab wheel DOFs for visual spinning
    art = dc.get_articulation("/fers_robot/base_link")
    if art != dc_module.INVALID_HANDLE:
        for i in range(dc.get_articulation_dof_count(art)):
            dof = dc.get_articulation_dof(art, i)
            name = dc.get_dof_name(dof)
            if name == "left_wheel_joint": _ld[0] = dof
            elif name == "right_wheel_joint": _rd[0] = dof
        if _ld[0] and _rd[0]:
            for dof in (_ld[0], _rd[0]):
                p = dc.get_dof_properties(dof)
                p.stiffness = 0.0
                p.damping = 87.27
                p.max_effort = 20.0
                dc.set_dof_properties(dof, p)
    print("[sq] DC ready — force-based drive + wheel spin")
    return True


def _spin_wheels(left_deg, right_deg):
    """Spin wheels visually."""
    if _ld[0]:
        _dc[0].set_dof_velocity_target(_ld[0], left_deg)
    if _rd[0]:
        _dc[0].set_dof_velocity_target(_rd[0], right_deg)


def _apply_force(forward, turn_z):
    """Apply forward force along robot heading + torque around Z."""
    if not _rb[0]:
        return
    dc = _dc[0]
    h = _heading[0]
    # Forward force in world frame based on heading
    fx = forward * math.sin(h)
    fy = forward * math.cos(h)
    dc.apply_body_force(_rb[0], (fx, fy, 0.0), (0.0, 0.0, 0.0), False)
    if abs(turn_z) > 0.01:
        dc.apply_body_torque(_rb[0], (0.0, 0.0, turn_z), False)


def _on_step(dt):
    if _st[0] == "INIT":
        if not _init_dc():
            return
        _el[0] = 0.0; _lg[0] = 0; _st[0] = "WARMUP"
        print("[sq] WARMUP — settling 2.0 s...")
        return

    _el[0] += dt

    if _st[0] == "WARMUP":
        _spin_wheels(0.0, 0.0)
        if _el[0] >= WARMUP_T:
            _st[0] = "FORWARD"; _el[0] = 0.0
            print("[sq] leg 1/4  FORWARD")

    elif _st[0] == "FORWARD":
        _apply_force(FORWARD_FORCE, 0.0)
        _spin_wheels(FWD_DEG, FWD_DEG)
        if _el[0] >= FORWARD_T:
            _st[0] = "TURN"; _el[0] = 0.0
            print(f"[sq] leg {_lg[0]+1}/4  TURN")

    elif _st[0] == "TURN":
        _apply_force(0.0, TURN_TORQUE)
        _spin_wheels(-TURN_DEG, TURN_DEG)
        _heading[0] += math.radians(TURN_DEG_S) * dt
        if _el[0] >= TURN_T:
            _lg[0] += 1; _el[0] = 0.0
            _heading[0] = math.radians(90.0 * _lg[0])
            if _lg[0] >= 4:
                _st[0] = "DONE"; _spin_wheels(0.0, 0.0)
                print("[sq] DONE — square complete!")
            else:
                _st[0] = "FORWARD"
                print(f"[sq] leg {_lg[0]+1}/4  FORWARD")

    elif _st[0] == "DONE":
        _spin_wheels(0.0, 0.0)


# ── Setup ─────────────────────────────────────────────────────────────────────

# 1. Clear any previous callbacks
for _attr in ['_fers_sub', '_fers_sq_sub', '_fers_tl_sub']:
    _h = getattr(builtins, _attr, None)
    if _h:
        try: _h.unsubscribe()
        except: pass
        setattr(builtins, _attr, None)

# 2. Reset state
_st[0] = "INIT"; _el[0] = 0.0; _lg[0] = 0
_dc[0] = None; _rb[0] = None; _heading[0] = 0.0

# 3. Register callback
builtins._fers_sq_sub = omni.physx.get_physx_interface().subscribe_physics_step_events(_on_step)

print("[sq] Ready — press Play (force-based drive, no wheel contact needed)")
