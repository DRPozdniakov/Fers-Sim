"""
FERS Robot — closed-loop trajectory: 1m forward, turn left 90°, 10m straight.

Uses DifferentialController kinematics + pose feedback so distance and heading
are measured from actual robot state — not time. The turn completes at exactly
90° regardless of wheel slip or speed.

Load this in Isaac Sim's Script Editor:
  Window > Script Editor > Open > (navigate here) > Run

Then press Play (or Stop → Play if already playing).
The robot will:
  - Wait 1.5 s   (settle on wheels)
  - Drive 1 m    forward  (pose-tracked)
  - Turn 90°     left     (yaw-tracked, handles angle wrapping)
  - Drive 10 m   straight (pose-tracked)
  - Stop

All phases use a velocity ramp-up and ramp-down for smooth motion.
Progress is printed to the Script Editor output / console.
"""

import omni.physx
import omni.usd
import omni.isaac.dynamic_control._dynamic_control as dc_module
import builtins
import math
from pxr import UsdGeom, Gf

# ── Tunable parameters ────────────────────────────────────────────────────────
WHEEL_RADIUS   = 0.0712   # m
WHEELBASE      = 0.328    # m
LINEAR_VEL     = 0.03     # m/s  forward cruising speed
ANGULAR_VEL    = 0.03     # rad/s  turn rate (~1.7 deg/s heading)
RAMP_T         = 0.3      # s  acceleration / deceleration ramp duration
KP_YAW         = 0.08     # rad/s per rad — gentle heading hold (FORWARD2 only)

FORWARD1_DIST  = 2.0      # m
TURN_ANGLE     = math.radians(50)  # rad  (exit at 50°, momentum carries to ~90°)
FORWARD2_DIST  = 10.0     # m

WARMUP_T       = 1.5      # s  let robot settle before moving
START_Z        = 0.4942   # base_link Z so wheels rest on ground (world Z = -1.8)

# ── DifferentialController kinematics ────────────────────────────────────────
def _diff_drive(lin, ang):
    """Convert (m/s, rad/s) → (left_deg_s, right_deg_s) for DC API."""
    vl = (2.0 * lin - ang * WHEELBASE) / (2.0 * WHEEL_RADIUS)  # rad/s
    vr = (2.0 * lin + ang * WHEELBASE) / (2.0 * WHEEL_RADIUS)
    return vl * (180.0 / math.pi), vr * (180.0 / math.pi)      # → deg/s

def _yaw(r):
    """Extract yaw (Z rotation) from a DC quaternion."""
    siny = 2.0 * (r.w * r.z + r.x * r.y)
    cosy = 1.0 - 2.0 * (r.y * r.y + r.z * r.z)
    return math.atan2(siny, cosy)

def _dist2d(p1, p2):
    return math.sqrt((p2.x - p1.x)**2 + (p2.y - p1.y)**2)

def _ramp_scale(elapsed, total, ramp_t=RAMP_T):
    """Trapezoidal velocity profile: ramp up, cruise, ramp down."""
    ramp_t = min(ramp_t, total / 2.0)
    if elapsed < ramp_t:
        return elapsed / ramp_t
    elif elapsed > total - ramp_t:
        return (total - elapsed) / ramp_t
    return 1.0


# ── State (nested lists so closures can mutate them) ─────────────────────────
_st        = [["INIT"]]
_el        = [[0.0]]
_dc        = [[None]]
_ld        = [[None]]
_rd        = [[None]]
_rb        = [[None]]
_sp        = [[None]]   # start position for current forward phase
_acc_yaw   = [[0.0]]    # accumulated heading change during turn
_prev_yaw  = [[None]]   # yaw at previous step (for incremental tracking)
_tgt_yaw   = [[None]]   # locked heading for FORWARD2 straight hold


def _sv(l, r):
    if _ld[0][0]: _dc[0][0].set_dof_velocity_target(_ld[0][0], l)
    if _rd[0][0]: _dc[0][0].set_dof_velocity_target(_rd[0][0], r)


def _get_pose():
    return _dc[0][0].get_rigid_body_pose(_rb[0][0])


def _init_dc():
    import omni.isaac.dynamic_control._dynamic_control as dc_module
    dc = dc_module.acquire_dynamic_control_interface()
    _dc[0][0] = dc
    art = dc.get_articulation("/fers_robot/base_link")
    if art == dc_module.INVALID_HANDLE:
        print("[sq] ERROR: articulation not found at /fers_robot/base_link")
        return False
    for i in range(dc.get_articulation_dof_count(art)):
        dof  = dc.get_articulation_dof(art, i)
        name = dc.get_dof_name(dof)
        if   name == "left_wheel_joint":  _ld[0][0] = dof
        elif name == "right_wheel_joint": _rd[0][0] = dof
    if not (_ld[0][0] and _rd[0][0]):
        print("[sq] ERROR: wheel DOFs not found")
        return False
    for dof in (_ld[0][0], _rd[0][0]):
        p = dc.get_dof_properties(dof)
        p.stiffness  = 0.0
        p.damping    = 304.6      # 17453 Nm·s/rad in DC deg/s units (Carter-matched)
        p.max_effort = 1e7        # unlimited (like EvoBOT)
        dc.set_dof_properties(dof, p)
        dc.set_dof_velocity_target(dof, 0.0)
    _rb[0][0] = dc.get_rigid_body("/fers_robot/base_link")
    print(f"[sq] DC ready — linear={LINEAR_VEL}m/s  angular={math.degrees(ANGULAR_VEL):.1f}deg/s  ramp={RAMP_T}s")
    return True


def _on_step(dt):
    if _st[0][0] == "INIT":
        if not _init_dc(): return
        _el[0][0] = 0.0
        _st[0][0] = "WARMUP"
        print("[sq] WARMUP — settling..."); return

    _el[0][0] += dt
    e = _el[0][0]

    if _st[0][0] == "WARMUP":
        _sv(0.0, 0.0)
        if e >= WARMUP_T:
            _sp[0][0] = _get_pose().p
            _el[0][0] = 0.0
            _st[0][0] = "FORWARD1"
            print("[sq] FORWARD 1 m...")

    elif _st[0][0] == "FORWARD1":
        dist = _dist2d(_sp[0][0], _get_pose().p)
        scale = _ramp_scale(e, FORWARD1_DIST / LINEAR_VEL)
        l, r  = _diff_drive(LINEAR_VEL * scale, 0.0)
        _sv(l, r)
        if dist >= FORWARD1_DIST:
            pose = _get_pose()
            _acc_yaw[0][0]  = 0.0
            _prev_yaw[0][0] = _yaw(pose.r)
            _el[0][0] = 0.0
            _st[0][0] = "TURN"
            print(f"[sq] TURN LEFT 90°  (traveled {dist:.2f} m)")

    elif _st[0][0] == "TURN":
        cur = _yaw(_get_pose().r)
        dy  = cur - _prev_yaw[0][0]
        if dy < -math.pi: dy += 2.0 * math.pi
        if dy >  math.pi: dy -= 2.0 * math.pi
        _acc_yaw[0][0]  += dy
        _prev_yaw[0][0]  = cur
        scale = _ramp_scale(e, TURN_ANGLE / ANGULAR_VEL)
        l, r  = _diff_drive(0.0, -ANGULAR_VEL * scale)
        _sv(l, r)
        if abs(_acc_yaw[0][0]) >= TURN_ANGLE:
            _sv(0.0, 0.0)
            _el[0][0] = 0.0
            _st[0][0] = "TURN_BRAKE"
            print(f"[sq] Braking after turn ({math.degrees(_acc_yaw[0][0]):.1f}°)...")

    elif _st[0][0] == "TURN_BRAKE":
        _sv(0.0, 0.0)
        if _el[0][0] >= 1.0:   # wait 1s for rotation to fully settle
            _sp[0][0] = _get_pose().p
            _tgt_yaw[0][0] = _yaw(_get_pose().r)
            _el[0][0] = 0.0
            _st[0][0] = "FORWARD2"
            print("[sq] FORWARD 10 m")

    elif _st[0][0] == "FORWARD2":
        dist  = _dist2d(_sp[0][0], _get_pose().p)
        scale = _ramp_scale(e, FORWARD2_DIST / LINEAR_VEL)
        yaw_err = _yaw(_get_pose().r) - _tgt_yaw[0][0]
        if yaw_err >  math.pi: yaw_err -= 2*math.pi
        if yaw_err < -math.pi: yaw_err += 2*math.pi
        correction = max(-0.015, min(0.015, KP_YAW * yaw_err))   # clamp ±0.015 rad/s
        l, r  = _diff_drive(LINEAR_VEL * scale, correction)
        _sv(l, r)
        if dist >= FORWARD2_DIST:
            _sv(0.0, 0.0)
            _st[0][0] = "DONE"
            print(f"[sq] DONE!  (traveled {dist:.2f} m)")

    elif _st[0][0] == "DONE":
        _sv(0.0, 0.0)


# ── Setup ─────────────────────────────────────────────────────────────────────

# 1. Clear any previous callbacks
for _attr in ['_fers_sub', '_fers_sq_sub', '_fers_tl_sub']:
    _h = getattr(builtins, _attr, None)
    if _h:
        try: _h.unsubscribe()
        except: pass
        setattr(builtins, _attr, None)

# 2. Reset robot to start position
_stage = omni.usd.get_context().get_stage()
_bl = _stage.GetPrimAtPath("/fers_robot/base_link")
if _bl.IsValid():
    _xf  = UsdGeom.Xformable(_bl)
    _ops = {op.GetOpName(): op for op in _xf.GetOrderedXformOps()}
    if "xformOp:translate" in _ops:
        _ops["xformOp:translate"].Set(Gf.Vec3d(0.0, 0.0, START_Z))
    if "xformOp:orient" in _ops:
        _ops["xformOp:orient"].Set(Gf.Quatd(1, 0, 0, 0))
    print(f"[sq] Robot reset to (0, 0, {START_Z})")
else:
    print("[sq] WARNING: /fers_robot/base_link not found — load the robot first")

# 3. Reset state
_st[0][0]       = "INIT"
_el[0][0]       = 0.0
_dc[0][0]       = None
_ld[0][0]       = None
_rd[0][0]       = None
_rb[0][0]       = None
_sp[0][0]       = None
_acc_yaw[0][0]  = 0.0
_prev_yaw[0][0] = None
_tgt_yaw[0][0]  = None
# 4. Register physics-step callback
builtins._fers_sq_sub = omni.physx.get_physx_interface().subscribe_physics_step_events(_on_step)

# 5. Subscribe to timeline STOP — auto-reset state so Stop → Play works
#    without needing to re-run this script each time
import omni.timeline
def _on_timeline_stop(e):
    import omni.timeline as _tl
    if e.type == int(_tl.TimelineEventType.STOP):
        _st[0][0]       = "INIT"
        _el[0][0]       = 0.0
        _dc[0][0]       = None
        _ld[0][0]       = None
        _rd[0][0]       = None
        _rb[0][0]       = None
        _sp[0][0]       = None
        _acc_yaw[0][0]  = 0.0
        _prev_yaw[0][0] = None
        _tgt_yaw[0][0]  = None
        print("[sq] Stopped — state reset. Press Play to restart trajectory.")

builtins._fers_tl_sub = (
    omni.timeline.get_timeline_interface()
    .get_timeline_event_stream()
    .create_subscription_to_pop(_on_timeline_stop, name="fers_traj_reset")
)

print("[sq] Ready — press Play (or Stop → Play at any time)")
