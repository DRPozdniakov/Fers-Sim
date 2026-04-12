"""
FERS Robot — waypoint trajectory with arm poses.

Based EXACTLY on colleague's working start_trajectory.py:
  Same speed (0.03), same heading hold (KP=0.08, max ±0.015), same structure.
  Extended for multiple waypoints + arm poses.
"""

import omni.physx
import omni.usd
import omni.isaac.dynamic_control._dynamic_control as dc_module
import builtins
import math
from pxr import UsdGeom, Gf

# ── Arm poses: {joint_key: (L_deg, R_deg)} ──────────────────────────────────
# Confirmed sign conventions (tested individually in sim with fixed axes):
#   sh_pitch (Y):  L=-30 forward, R=-30 forward (same sign!)
#   sh_roll  (Y fixed): L=-30 arm down, R=+30 arm down (opposite signs)
#   elbow    (X fixed): L=+45 bend, R=-45 bend (opposite signs)
#   wr_yaw   (Z):  L=-30 bend, R=+30 bend (opposite signs)
ARM_POSES = {
    "rest": {},                            # all joints at 0 — natural relaxed

    "lift": {                              # shoulder lift 15°
        "sh_roll":  (-15, 15),
    },

    "grip": {                              # small wrist bend — signs flipped
        "wr_yaw":   (12, -12),
    },

    "lift_grip": {                         # lift + wrist — only wr_yaw flipped
        "sh_roll":  (-6, 6),
        "wr_yaw":   (10, -10),
    },
}

# ── Waypoints: (x, y, start_pose, end_pose) ─────────────────────────────────
# Arms smoothly interpolate from start_pose to end_pose during each DRIVE
WAYPOINTS = [
    (21.9144, -0.3576, "rest",      "rest"),       # start — stay relaxed
    (21.0203,  1.7113, "rest",      "lift"),       # gentle arm lift
    (10.0465, -0.1282, "lift",      "rest"),       # return to rest
    ( 4.9930, -1.1215, "rest",      "grip"),       # wrist gesture
    ( 3.3623, -3.7983, "grip",      "lift_grip"),  # lift + grip
    (-0.0915, -2.2579, "lift_grip", "rest"),       # return to relaxed at end
]

# ── Tunable — COLLEAGUE'S EXACT VALUES ──────────────────────────────────────
WHEEL_RADIUS   = 0.0712
WHEELBASE      = 0.328
LINEAR_VEL     = 0.03     # m/s  — colleague's value
ANGULAR_VEL    = 0.03     # rad/s — colleague's value
RAMP_T         = 0.3      # s
KP_YAW         = 0.15     # rad/s per rad — tighter heading hold
MAX_YAW_CORR   = 0.03     # max correction — doubled for straighter lines
WARMUP_T       = 1.5
BRAKE_T        = 1.0      # s — colleague uses 1.0
LOG_T          = 2.0

# ── Helpers ──────────────────────────────────────────────────────────────────
def _diff_drive(lin, ang):
    vl = (2.0 * lin - ang * WHEELBASE) / (2.0 * WHEEL_RADIUS)
    vr = (2.0 * lin + ang * WHEELBASE) / (2.0 * WHEEL_RADIUS)
    return vl * (180.0 / math.pi), vr * (180.0 / math.pi)

def _yaw(r):
    siny = 2.0 * (r.w * r.z + r.x * r.y)
    cosy = 1.0 - 2.0 * (r.y * r.y + r.z * r.z)
    return math.atan2(siny, cosy)

def _dist2d(ax, ay, bx, by):
    return math.sqrt((bx - ax)**2 + (by - ay)**2)

def _wrap(a):
    while a > math.pi: a -= 2.0 * math.pi
    while a < -math.pi: a += 2.0 * math.pi
    return a

def _ramp_scale(elapsed, total):
    rt = min(RAMP_T, total / 2.0)
    if elapsed < rt:
        return elapsed / rt
    elif elapsed > total - rt:
        return max(0.0, (total - elapsed) / rt)
    return 1.0

# ── Arm joint mapping ───────────────────────────────────────────────────────
_ARM_JOINTS = {
    "sh_yaw":   ("L_shoulder_yaw_joint",   "R_shoulder_yaw_joint"),
    "sh_pitch": ("L_shoulder_pitch_joint",  "R_shoulder_pitch_joint"),
    "sh_roll":  ("L_shoulder_roll_joint",   "R_shoulder_roll_joint"),
    "elbow":    ("L_elbow_joint",           "R_elbow_joint"),
    "wr_pitch": ("L_wrist_pitch_joint",     "R_wrist_pitch_joint"),
    "wr_yaw":   ("L_wrist_yaw_joint",      "R_wrist_yaw_joint"),
    "wr_roll":  ("L_wrist_roll_joint",      "R_wrist_roll_joint"),
}

# ── State ────────────────────────────────────────────────────────────────────
_st        = [["INIT"]]
_el        = [[0.0]]
_dc        = [[None]]
_ld        = [[None]]
_rd        = [[None]]
_rb        = [[None]]
_arm_dofs  = [{}]
_wp_idx    = [[0]]
_start_pos = [[None]]   # (x, y) at start of DRIVE
_tgt_yaw   = [[None]]   # locked heading for DRIVE (colleague's approach)
_log_timer = [[0.0]]
_acc_yaw   = [[0.0]]    # accumulated turn (incremental)
_prev_yaw  = [[None]]
_turn_dir  = [[1.0]]
_turn_amt  = [[0.0]]
_drive_dist = [[0.0]]
_prev_dist  = [[999.0]]   # previous distance to target (for closest-approach detection)

def _sv(l, r):
    if _ld[0][0]: _dc[0][0].set_dof_velocity_target(_ld[0][0], l)
    if _rd[0][0]: _dc[0][0].set_dof_velocity_target(_rd[0][0], r)

def _set_pose(pose_name):
    pose = ARM_POSES.get(pose_name, {})
    for key, (l_name, r_name) in _ARM_JOINTS.items():
        l_val, r_val = pose.get(key, (0.0, 0.0))
        if l_name in _arm_dofs[0]:
            _dc[0][0].set_dof_position_target(_arm_dofs[0][l_name], l_val)
        if r_name in _arm_dofs[0]:
            _dc[0][0].set_dof_position_target(_arm_dofs[0][r_name], r_val)

def _lerp_pose(pose_a_name, pose_b_name, t):
    """Smoothly interpolate between two poses. t=0→pose_a, t=1→pose_b."""
    pose_a = ARM_POSES.get(pose_a_name, {})
    pose_b = ARM_POSES.get(pose_b_name, {})
    t = max(0.0, min(1.0, t))
    for key, (l_name, r_name) in _ARM_JOINTS.items():
        la, ra = pose_a.get(key, (0.0, 0.0))
        lb, rb = pose_b.get(key, (0.0, 0.0))
        l_val = la + (lb - la) * t
        r_val = ra + (rb - ra) * t
        if l_name in _arm_dofs[0]:
            _dc[0][0].set_dof_position_target(_arm_dofs[0][l_name], l_val)
        if r_name in _arm_dofs[0]:
            _dc[0][0].set_dof_position_target(_arm_dofs[0][r_name], r_val)

def _get_pose():
    return _dc[0][0].get_rigid_body_pose(_rb[0][0])

def _init_dc():
    dc = dc_module.acquire_dynamic_control_interface()
    _dc[0][0] = dc
    art = dc.get_articulation("/fers_robot/base_link")
    if art == dc_module.INVALID_HANDLE:
        print("[traj] ERROR: articulation not found")
        return False
    arm_names = set()
    for l_n, r_n in _ARM_JOINTS.values():
        arm_names.add(l_n)
        arm_names.add(r_n)
    _arm_dofs[0] = {}
    for i in range(dc.get_articulation_dof_count(art)):
        dof = dc.get_articulation_dof(art, i)
        name = dc.get_dof_name(dof)
        if name == "left_wheel_joint":    _ld[0][0] = dof
        elif name == "right_wheel_joint": _rd[0][0] = dof
        if name in arm_names:
            _arm_dofs[0][name] = dof
    if not (_ld[0][0] and _rd[0][0]):
        print("[traj] ERROR: wheel DOFs not found")
        return False
    # Wheel drive properties — same as colleague
    for dof in (_ld[0][0], _rd[0][0]):
        p = dc.get_dof_properties(dof)
        p.stiffness = 0.0
        p.damping = 304.6
        p.max_effort = 1e7
        dc.set_dof_properties(dof, p)
        dc.set_dof_velocity_target(dof, 0.0)
    _rb[0][0] = dc.get_rigid_body("/fers_robot/base_link")
    pose = dc.get_rigid_body_pose(_rb[0][0])
    print(f"[traj] DC ready — {len(_arm_dofs[0])} arm DOFs  pos=({pose.p.x:.2f}, {pose.p.y:.2f})")
    return True


def _start_turn(idx):
    """Set up TURN to face waypoint idx."""
    pose = _get_pose()
    cur_yaw = _yaw(pose.r)
    tx, ty = WAYPOINTS[idx][0], WAYPOINTS[idx][1]
    # Robot forward = -Y at yaw=0. Bearing = atan2(dx, -dy)
    bearing = math.atan2(tx - pose.p.x, pose.p.y - ty)
    needed = _wrap(bearing - cur_yaw)
    # negative ang in _diff_drive = left turn for this robot (wheels reversed)
    _turn_dir[0][0] = -1.0 if needed >= 0 else 1.0
    _turn_amt[0][0] = abs(needed)
    _acc_yaw[0][0] = 0.0
    _prev_yaw[0][0] = cur_yaw
    _el[0][0] = 0.0
    _drive_dist[0][0] = _dist2d(pose.p.x, pose.p.y, tx, ty)
    _set_pose(WAYPOINTS[idx][2])  # set start pose for this segment
    print(f"[traj] → wp{idx}: turn {math.degrees(needed):.1f}° then drive {_drive_dist[0][0]:.1f}m")


def _on_step(dt):
    if _st[0][0] == "INIT":
        if not _init_dc(): return
        _el[0][0] = 0.0
        _st[0][0] = "WARMUP"
        _set_pose(WAYPOINTS[0][2])
        print("[traj] WARMUP...")
        return

    _el[0][0] += dt

    # ── WARMUP ───────────────────────────────────────────────────────────
    if _st[0][0] == "WARMUP":
        _sv(0.0, 0.0)
        if _el[0][0] >= WARMUP_T:
            _wp_idx[0][0] = 1
            _st[0][0] = "TURN"
            _start_turn(1)

    # ── TURN — identical to colleague's approach ─────────────────────────
    elif _st[0][0] == "TURN":
        cur = _yaw(_get_pose().r)
        dy = cur - _prev_yaw[0][0]
        if dy < -math.pi: dy += 2.0 * math.pi
        if dy >  math.pi: dy -= 2.0 * math.pi
        _acc_yaw[0][0] += dy
        _prev_yaw[0][0] = cur
        est_t = _turn_amt[0][0] / ANGULAR_VEL
        scale = _ramp_scale(_el[0][0], est_t)
        l, r = _diff_drive(0.0, _turn_dir[0][0] * ANGULAR_VEL * scale)
        _sv(l, r)
        if abs(_acc_yaw[0][0]) >= _turn_amt[0][0]:
            _sv(0.0, 0.0)
            _el[0][0] = 0.0
            _st[0][0] = "BRAKE"

    # ── BRAKE — 1s settle (colleague uses 1.0s) ─────────────────────────
    elif _st[0][0] == "BRAKE":
        _sv(0.0, 0.0)
        if _el[0][0] >= BRAKE_T:
            pose = _get_pose()
            # Lock CURRENT heading — colleague's approach (not bearing)
            _tgt_yaw[0][0] = _yaw(pose.r)
            _start_pos[0][0] = (pose.p.x, pose.p.y)
            _drive_dist[0][0] = _dist2d(pose.p.x, pose.p.y,
                                        WAYPOINTS[_wp_idx[0][0]][0],
                                        WAYPOINTS[_wp_idx[0][0]][1])
            _log_timer[0][0] = 0.0
            _el[0][0] = 0.0
            _st[0][0] = "DRIVE"
            _prev_dist[0][0] = _drive_dist[0][0]
            idx = _wp_idx[0][0]
            print(f"[traj] DRIVE {_drive_dist[0][0]:.1f}m → target=({WAYPOINTS[idx][0]:.2f},{WAYPOINTS[idx][1]:.2f})  heading={math.degrees(_tgt_yaw[0][0]):.1f}°")

    # ── DRIVE — heading hold + smooth arm interpolation ────────────────
    elif _st[0][0] == "DRIVE":
        pose = _get_pose()
        cx, cy = pose.p.x, pose.p.y
        idx = _wp_idx[0][0]
        tx, ty = WAYPOINTS[idx][0], WAYPOINTS[idx][1]
        d_rem = _dist2d(cx, cy, tx, ty)

        # Trapezoidal speed profile
        est_t = _drive_dist[0][0] / LINEAR_VEL
        scale = _ramp_scale(_el[0][0], est_t)

        # Heading hold
        yaw_err = _yaw(pose.r) - _tgt_yaw[0][0]
        yaw_err = _wrap(yaw_err)
        correction = max(-MAX_YAW_CORR, min(MAX_YAW_CORR, KP_YAW * yaw_err))
        l, r = _diff_drive(LINEAR_VEL * scale, correction)
        _sv(l, r)

        # Smooth arm interpolation: lerp from start_pose to end_pose
        d_traveled = _dist2d(_start_pos[0][0][0], _start_pos[0][0][1], cx, cy)
        arm_t = min(1.0, d_traveled / max(0.1, _drive_dist[0][0]))
        _lerp_pose(WAYPOINTS[idx][2], WAYPOINTS[idx][3], arm_t)

        # Log
        _log_timer[0][0] += dt
        if _log_timer[0][0] >= LOG_T:
            _log_timer[0][0] = 0.0
            print(f"[traj] wp{idx} pos=({cx:.2f},{cy:.2f}) → tgt=({tx:.2f},{ty:.2f}) rem={d_rem:.2f}m "
                  f"yerr={math.degrees(yaw_err):.1f}° corr={correction:.4f}")

        # Arrival: close enough OR passed closest approach (distance increasing)
        passed = d_rem > _prev_dist[0][0] + 0.05 and _prev_dist[0][0] < _drive_dist[0][0] * 0.5
        _prev_dist[0][0] = min(_prev_dist[0][0], d_rem)
        if d_rem < 0.5 or passed:
            _sv(0.0, 0.0)
            _wp_idx[0][0] = idx + 1
            print(f"[traj] ✓ wp{idx} reached at ({cx:.2f},{cy:.2f})  closest={_prev_dist[0][0]:.2f}m")
            if idx + 1 < len(WAYPOINTS):
                _st[0][0] = "TURN"
                _start_turn(idx + 1)
            else:
                _st[0][0] = "DONE"
                print("[traj] ALL WAYPOINTS DONE")

    elif _st[0][0] == "DONE":
        _sv(0.0, 0.0)


# ── Setup ────────────────────────────────────────────────────────────────────
for _attr in ['_fers_sub', '_fers_sq_sub', '_fers_tl_sub', '_fers_kb_sub', '_fers_kb_input']:
    _h = getattr(builtins, _attr, None)
    if _h:
        try: _h.unsubscribe()
        except: pass
        setattr(builtins, _attr, None)

_st[0][0] = "INIT"
_el[0][0] = 0.0
_dc[0][0] = None
_ld[0][0] = None
_rd[0][0] = None
_rb[0][0] = None
_arm_dofs[0] = {}
_wp_idx[0][0] = 0
_start_pos[0][0] = None
_tgt_yaw[0][0] = None
_log_timer[0][0] = 0.0
_acc_yaw[0][0] = 0.0
_prev_yaw[0][0] = None
_prev_dist[0][0] = 999.0

builtins._fers_sq_sub = omni.physx.get_physx_interface().subscribe_physics_step_events(_on_step)

import omni.timeline
def _on_timeline_stop(e):
    import omni.timeline as _tl
    if e.type == int(_tl.TimelineEventType.STOP):
        _st[0][0] = "INIT"
        _el[0][0] = 0.0
        _dc[0][0] = None
        _ld[0][0] = None
        _rd[0][0] = None
        _rb[0][0] = None
        _arm_dofs[0] = {}
        _wp_idx[0][0] = 0
        _start_pos[0][0] = None
        _tgt_yaw[0][0] = None
        _log_timer[0][0] = 0.0
        _acc_yaw[0][0] = 0.0
        _prev_yaw[0][0] = None
        print("[traj] Reset.")

builtins._fers_tl_sub = (
    omni.timeline.get_timeline_interface()
    .get_timeline_event_stream()
    .create_subscription_to_pop(_on_timeline_stop, name="fers_traj_reset")
)

print(f"[traj] Ready — {len(WAYPOINTS)} waypoints, speed={LINEAR_VEL}m/s. Press Play.")
