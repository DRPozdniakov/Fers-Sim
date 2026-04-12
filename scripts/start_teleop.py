"""
FERS Robot — keyboard teleoperation.

Load in Isaac Sim's Script Editor, then press Play.

Controls:
  W / Up       — forward
  S / Down     — backward
  A / Left     — turn left
  D / Right    — turn right
  Q            — strafe left (turn + forward)
  E            — strafe right (turn + forward)
  Shift        — boost (3x speed)
  Space        — emergency stop
  R            — arms up
  V            — arms down
  T            — record waypoint (prints position to console)

Speed is ramped for smooth acceleration. Release key to decelerate.
Heading hold keeps the robot driving straight when no turn keys are pressed.
"""

import omni.physx
import omni.usd
import omni.appwindow
import omni.isaac.dynamic_control._dynamic_control as dc_module
import carb.input
import builtins
import math
from pxr import UsdGeom, Gf, UsdPhysics

# ── Tunable ──────────────────────────────────────────────────────────────────
WHEEL_RADIUS  = 0.0712
WHEELBASE     = 0.328
LINEAR_VEL    = 0.05      # m/s  base forward speed
ANGULAR_VEL   = 0.08      # rad/s  base turn rate
BOOST_MULT    = 3.0        # speed multiplier when Shift held
RAMP_RATE     = 2.0        # acceleration factor (1/s to full speed)
KP_YAW        = 0.12       # heading correction P gain (softer)
KP_YAW_MAX    = 0.025      # max correction (rad/s) — halved to prevent sudden turns
KI_YAW        = 0.01       # integral gain — very gentle drift correction
CASTER_SWIVEL_DAMPING = 50.0  # Nm·s/rad — reduces caster shimmy
ARM_SPEED     = 30.0    # deg/s  shoulder pitch rate
ARM_MIN       = 0.0     # deg  arms horizontal (NO backward motion)
ARM_MAX       = 85.0    # deg  arms fully down
START_Z       = 0.4942

# ── Differential drive kinematics ────────────────────────────────────────────
def _diff_drive(lin, ang):
    """(m/s, rad/s) → (left_deg_s, right_deg_s) for DC API."""
    vl = (2.0 * lin - ang * WHEELBASE) / (2.0 * WHEEL_RADIUS)
    vr = (2.0 * lin + ang * WHEELBASE) / (2.0 * WHEEL_RADIUS)
    return vl * (180.0 / math.pi), vr * (180.0 / math.pi)

def _yaw(r):
    """Extract yaw from DC quaternion."""
    siny = 2.0 * (r.w * r.z + r.x * r.y)
    cosy = 1.0 - 2.0 * (r.y * r.y + r.z * r.z)
    return math.atan2(siny, cosy)

def _wrap_angle(a):
    """Wrap angle to [-pi, pi]."""
    while a > math.pi: a -= 2.0 * math.pi
    while a < -math.pi: a += 2.0 * math.pi
    return a

# ── Key state ────────────────────────────────────────────────────────────────
_keys = {
    "forward": False, "backward": False,
    "left": False, "right": False,
    "strafe_l": False, "strafe_r": False,
    "boost": False, "stop": False,
    "arms_up": False, "arms_down": False,
    "record": False,
}

_KEY_MAP = {
    carb.input.KeyboardInput.W:     "forward",
    carb.input.KeyboardInput.UP:    "forward",
    carb.input.KeyboardInput.S:     "backward",
    carb.input.KeyboardInput.DOWN:  "backward",
    carb.input.KeyboardInput.A:     "left",
    carb.input.KeyboardInput.LEFT:  "left",
    carb.input.KeyboardInput.D:     "right",
    carb.input.KeyboardInput.RIGHT: "right",
    carb.input.KeyboardInput.Q:     "strafe_l",
    carb.input.KeyboardInput.E:     "strafe_r",
    carb.input.KeyboardInput.SPACE: "stop",
    carb.input.KeyboardInput.R:     "arms_up",
    carb.input.KeyboardInput.V:     "arms_down",
    carb.input.KeyboardInput.T:     "record",
}

_SHIFT_KEYS = {
    carb.input.KeyboardInput.LEFT_SHIFT,
    carb.input.KeyboardInput.RIGHT_SHIFT,
}

def _on_key(event, *args):
    pressed = event.type == carb.input.KeyboardEventType.KEY_PRESS
    released = event.type == carb.input.KeyboardEventType.KEY_RELEASE
    if event.input in _KEY_MAP:
        if pressed:
            _keys[_KEY_MAP[event.input]] = True
        elif released:
            _keys[_KEY_MAP[event.input]] = False
    if event.input in _SHIFT_KEYS:
        _keys["boost"] = pressed
    return True


# ── State ────────────────────────────────────────────────────────────────────
_dc_h     = [[None]]
_ld       = [[None]]
_rd       = [[None]]
_rb       = [[None]]   # base_link rigid body for pose
_ready    = [[False]]
_cur_lin  = [[0.0]]   # current smoothed linear velocity
_cur_ang  = [[0.0]]   # current smoothed angular velocity
_locked_yaw = [[None]]  # heading lock when driving straight
_yaw_int    = [[0.0]]   # heading integral accumulator
_l_shoulder = [[None]]  # L_shoulder_pitch DOF handle
_r_shoulder = [[None]]  # R_shoulder_pitch DOF handle
_arm_pos    = [[0.0]]   # current arm target (deg, shared L/R)
_waypoints  = []        # recorded waypoints [(x, y, yaw), ...]
_rec_prev   = [[False]] # previous record key state (edge detect)


def _init_dc():
    dc = dc_module.acquire_dynamic_control_interface()
    _dc_h[0][0] = dc
    art = dc.get_articulation("/fers_robot/base_link")
    if art == dc_module.INVALID_HANDLE:
        print("[kb] ERROR: articulation not found")
        return False
    for i in range(dc.get_articulation_dof_count(art)):
        dof = dc.get_articulation_dof(art, i)
        name = dc.get_dof_name(dof)
        if name == "left_wheel_joint":
            _ld[0][0] = dof
        elif name == "right_wheel_joint":
            _rd[0][0] = dof
        elif name == "L_shoulder_roll_joint":
            _l_shoulder[0][0] = dof
        elif name == "R_shoulder_roll_joint":
            _r_shoulder[0][0] = dof
    if not (_ld[0][0] and _rd[0][0]):
        print("[kb] ERROR: wheel DOFs not found")
        return False
    for dof in (_ld[0][0], _rd[0][0]):
        p = dc.get_dof_properties(dof)
        p.stiffness = 0.0
        p.damping = 304.6
        p.max_effort = 1e7
        dc.set_dof_properties(dof, p)
        dc.set_dof_velocity_target(dof, 0.0)
    _rb[0][0] = dc.get_rigid_body("/fers_robot/base_link")
    print(f"[kb] DC ready — lin={LINEAR_VEL}m/s  ang={math.degrees(ANGULAR_VEL):.1f}deg/s  boost={BOOST_MULT}x")
    return True


def _sv(l, r):
    if _ld[0][0]:
        _dc_h[0][0].set_dof_velocity_target(_ld[0][0], l)
    if _rd[0][0]:
        _dc_h[0][0].set_dof_velocity_target(_rd[0][0], r)


def _on_step(dt):
    if not _ready[0][0]:
        if not _init_dc():
            return
        _ready[0][0] = True

    # Compute target from keys
    tgt_lin = 0.0
    tgt_ang = 0.0
    turning = False

    if _keys["stop"]:
        _locked_yaw[0][0] = None
    else:
        if _keys["forward"]:
            tgt_lin += LINEAR_VEL
        if _keys["backward"]:
            tgt_lin -= LINEAR_VEL
        if _keys["left"]:
            tgt_ang -= ANGULAR_VEL
            turning = True
        if _keys["right"]:
            tgt_ang += ANGULAR_VEL
            turning = True
        if _keys["strafe_l"]:
            tgt_lin += LINEAR_VEL * 0.5
            tgt_ang -= ANGULAR_VEL
            turning = True
        if _keys["strafe_r"]:
            tgt_lin += LINEAR_VEL * 0.5
            tgt_ang += ANGULAR_VEL
            turning = True

        if _keys["boost"]:
            tgt_lin *= BOOST_MULT
            tgt_ang *= BOOST_MULT

    # Heading hold: PI controller — P corrects drift, I eliminates steady-state arc
    moving = abs(tgt_lin) > 0.001
    if turning:
        _locked_yaw[0][0] = None
        _yaw_int[0][0] = 0.0      # reset integral when turning
    elif moving and _rb[0][0]:
        cur_yaw = _yaw(_dc_h[0][0].get_rigid_body_pose(_rb[0][0]).r)
        if _locked_yaw[0][0] is None:
            _locked_yaw[0][0] = cur_yaw
            _yaw_int[0][0] = 0.0
        else:
            err = _wrap_angle(cur_yaw - _locked_yaw[0][0])
            _yaw_int[0][0] += err * dt
            _yaw_int[0][0] = max(-0.3, min(0.3, _yaw_int[0][0]))  # tight anti-windup
            correction = KP_YAW * err + KI_YAW * _yaw_int[0][0]
            correction = max(-KP_YAW_MAX, min(KP_YAW_MAX, correction))
            tgt_ang += correction
    else:
        _locked_yaw[0][0] = None
        _yaw_int[0][0] = 0.0

    # Smooth ramp toward target
    rate = RAMP_RATE * dt
    _cur_lin[0][0] += max(-rate, min(rate, tgt_lin - _cur_lin[0][0]))
    _cur_ang[0][0] += max(-rate, min(rate, tgt_ang - _cur_ang[0][0]))

    # Deadzone — fully stop below threshold
    if abs(_cur_lin[0][0]) < 0.001 and abs(tgt_lin) < 0.001:
        _cur_lin[0][0] = 0.0
    if abs(_cur_ang[0][0]) < 0.001 and abs(tgt_ang) < 0.001:
        _cur_ang[0][0] = 0.0

    l, r = _diff_drive(_cur_lin[0][0], _cur_ang[0][0])
    _sv(l, r)

    # Arm control: R=up, F=down (position target via DC API)
    if _keys["arms_up"]:
        _arm_pos[0][0] = max(ARM_MIN, _arm_pos[0][0] - ARM_SPEED * dt)
    elif _keys["arms_down"]:
        _arm_pos[0][0] = min(ARM_MAX, _arm_pos[0][0] + ARM_SPEED * dt)
    if _l_shoulder[0][0]:
        _dc_h[0][0].set_dof_position_target(_l_shoulder[0][0], -_arm_pos[0][0])
    if _r_shoulder[0][0]:
        _dc_h[0][0].set_dof_position_target(_r_shoulder[0][0], _arm_pos[0][0])

    # Waypoint recording: T key (edge-triggered — one waypoint per press)
    if _keys["record"] and not _rec_prev[0][0] and _rb[0][0]:
        pose = _dc_h[0][0].get_rigid_body_pose(_rb[0][0])
        yaw = _yaw(pose.r)
        wp = (round(pose.p.x, 4), round(pose.p.y, 4), round(math.degrees(yaw), 1))
        _waypoints.append(wp)
        print(f"[wp] #{len(_waypoints)}: x={wp[0]}  y={wp[1]}  yaw={wp[2]}deg")
    _rec_prev[0][0] = _keys["record"]


# ── Setup ────────────────────────────────────────────────────────────────────

# Clear previous subscriptions
for _attr in ['_fers_sub', '_fers_sq_sub', '_fers_tl_sub', '_fers_kb_sub', '_fers_kb_input']:
    _h = getattr(builtins, _attr, None)
    if _h:
        try:
            _h.unsubscribe()
        except Exception:
            pass
        setattr(builtins, _attr, None)

# Reset state
_ready[0][0] = False
_cur_lin[0][0] = 0.0
_cur_ang[0][0] = 0.0
for k in _keys:
    _keys[k] = False

# Register keyboard
_app_window = omni.appwindow.get_default_app_window()
_keyboard = _app_window.get_keyboard()
_input_iface = carb.input.acquire_input_interface()
builtins._fers_kb_input = _input_iface.subscribe_to_keyboard_events(_keyboard, _on_key)

# Register physics step
builtins._fers_sq_sub = omni.physx.get_physx_interface().subscribe_physics_step_events(_on_step)

# Timeline STOP auto-reset
import omni.timeline
def _on_timeline_stop(e):
    import omni.timeline as _tl
    if e.type == int(_tl.TimelineEventType.STOP):
        _ready[0][0] = False
        _cur_lin[0][0] = 0.0
        _cur_ang[0][0] = 0.0
        _locked_yaw[0][0] = None
        _yaw_int[0][0] = 0.0
        _arm_pos[0][0] = 0.0
        _dc_h[0][0] = None
        _ld[0][0] = None
        _rd[0][0] = None
        _rb[0][0] = None
        _l_shoulder[0][0] = None
        _r_shoulder[0][0] = None
        for k in _keys:
            _keys[k] = False
        print("[kb] Stopped — state reset. Press Play to drive again.")

builtins._fers_tl_sub = (
    omni.timeline.get_timeline_interface()
    .get_timeline_event_stream()
    .create_subscription_to_pop(_on_timeline_stop, name="fers_kb_reset")
)

print("[kb] Keyboard drive ready — press Play")
print("[kb]   W/Up=fwd  S/Down=back  A/Left=left  D/Right=right")
print("[kb]   Q=strafe-left  E=strafe-right  Shift=boost  Space=stop")
print("[kb]   R=arms up  V=arms down  T=record waypoint")