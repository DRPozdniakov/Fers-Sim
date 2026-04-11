"""
FERS Robot — Post-GUI-URDF-import setup + trajectory.

For GUI-imported robots in Isaac Sim 5.1.0 (programmatic import crashes).

THREE-STEP workflow (all via MCP):
  1. Run this script (fixes physics, creates Action Graph)
  2. Press Play in Isaac Sim
  3. Run init_robot_runtime() via MCP execute_script:
       exec(open("/isaac-sim/.local/share/ov/data/simulation/tools/setup_robot_gui_import.py").read())
       init_robot_runtime()

WHY three steps:
  - GUI URDF import creates articulation with 0 DOFs in DC API
  - Physics step callbacks registered via MCP don't fire during Play
  - Articulation API needs World.initialize_physics() which only works during Play
  - Solution: ScriptNode (fires every frame) + Articulation init via MCP during Play

Ground plane: Z=-1.80 (Interior facility scene)
Robot root:   Z=-1.81 (1cm into ground for solid wheel contact)
base_link:    Z=0.4828
localPos0:    Z=-0.4116
Wheel bottom: -1.81 + 0.4828 + (-0.4116) - 0.0712 = -1.81 (matches ground)
"""
import omni.usd
import omni.kit.commands
from pxr import UsdPhysics, PhysxSchema, UsdGeom, Gf, Sdf

stage = omni.usd.get_context().get_stage()

ROBOT = "/fers_robot"
WHEEL_RADIUS = 0.0712
WHEEL_JOINT_Z = 0.34128
LOCAL_POS0_Z = -0.4116
BASE_LINK_Z = 0.4828
ROOT_Z = -1.81

# ── 1. Base link position ─────────────────────────────────────────────────────

bl = stage.GetPrimAtPath(f"{ROBOT}/base_link")
if not bl.IsValid():
    print(f"[setup] ERROR: {ROBOT}/base_link not found. Import robot via GUI first.")
else:
    xf = UsdGeom.Xformable(bl)
    ops = {op.GetOpName(): op for op in xf.GetOrderedXformOps()}
    if "xformOp:translate" in ops:
        ops["xformOp:translate"].Set(Gf.Vec3d(0, 0, BASE_LINK_Z))
    else:
        xf.AddTranslateOp().Set(Gf.Vec3d(0, 0, BASE_LINK_Z))
    print(f"[setup] base_link Z = {BASE_LINK_Z}")

# ── 2. Wheel joint localPos0 + velocity drives ────────────────────────────────

for jn in ("left_wheel_joint", "right_wheel_joint"):
    j = stage.GetPrimAtPath(f"{ROBOT}/joints/{jn}")
    if j.IsValid():
        lp = j.GetAttribute("physics:localPos0")
        if lp.IsValid():
            o = lp.Get()
            lp.Set(Gf.Vec3f(o[0], o[1], LOCAL_POS0_Z))
        drv = UsdPhysics.DriveAPI.Apply(j, "angular")
        drv.GetStiffnessAttr().Set(0.0)
        drv.GetDampingAttr().Set(5000.0)
        drv.GetMaxForceAttr().Set(500.0)
print(f"[setup] Wheel joints: localPos0 Z={LOCAL_POS0_Z}, drives damping=5000")

# ── 3. Wheel sphere colliders ─────────────────────────────────────────────────

for side in ("left", "right"):
    sp = f"{ROBOT}/{side}_wheel/wheel_sphere"
    if stage.GetPrimAtPath(sp).IsValid():
        stage.RemovePrim(sp)
    sph = UsdGeom.Sphere.Define(stage, sp)
    sph.GetRadiusAttr().Set(WHEEL_RADIUS)
    p = sph.GetPrim()
    UsdPhysics.CollisionAPI.Apply(p)
    px = PhysxSchema.PhysxCollisionAPI.Apply(p)
    px.GetContactOffsetAttr().Set(0.002)
    px.GetRestOffsetAttr().Set(0.001)
    mat = UsdPhysics.MaterialAPI.Apply(p)
    mat.GetStaticFrictionAttr().Set(1.0)
    mat.GetDynamicFrictionAttr().Set(0.8)
    mat.GetRestitutionAttr().Set(0.0)
print(f"[setup] Wheel spheres: r={WHEEL_RADIUS}, friction=1.0/0.8")

# ── 4. Stabilizers ────────────────────────────────────────────────────────────

for nm, (sx, sy) in {"front_stab": (0, 0.20), "back_stab": (0, -0.20)}.items():
    pa = f"{ROBOT}/base_link/{nm}"
    if stage.GetPrimAtPath(pa).IsValid():
        stage.RemovePrim(pa)
    sph = UsdGeom.Sphere.Define(stage, pa)
    sph.GetRadiusAttr().Set(WHEEL_RADIUS)
    UsdGeom.Xformable(sph.GetPrim()).AddTranslateOp().Set(Gf.Vec3d(sx, sy, LOCAL_POS0_Z))
    UsdPhysics.CollisionAPI.Apply(sph.GetPrim())
    PhysxSchema.PhysxCollisionAPI.Apply(sph.GetPrim()).GetContactOffsetAttr().Set(0.002)
    mat = UsdPhysics.MaterialAPI.Apply(sph.GetPrim())
    mat.GetStaticFrictionAttr().Set(0.05)
    mat.GetDynamicFrictionAttr().Set(0.05)
    mat.GetRestitutionAttr().Set(0.0)
print("[setup] Stabilizers: front/back, low friction")

# ── 5. Base mass + rigid body ─────────────────────────────────────────────────

if bl.IsValid():
    if not bl.HasAPI(UsdPhysics.MassAPI):
        UsdPhysics.MassAPI.Apply(bl)
    bl.GetAttribute("physics:mass").Set(80.0)
    px_rb = PhysxSchema.PhysxRigidBodyAPI.Apply(bl)
    px_rb.GetAngularDampingAttr().Set(2.0)
    px_rb.GetLinearDampingAttr().Set(0.5)
    px_rb.GetMaxDepenetrationVelocityAttr().Set(1.0)
    px_rb.GetLockedRotAxisAttr().Set(3)
    px_rb.GetDisableGravityAttr().Set(False)
    print("[setup] base_link: 80kg, tilt-locked, gravity ON")

# ── 6. Robot root position ────────────────────────────────────────────────────

rt = stage.GetPrimAtPath(ROBOT)
xfr = UsdGeom.Xformable(rt)
ro = {op.GetOpName(): op for op in xfr.GetOrderedXformOps()}
if "xformOp:translate" in ro:
    ro["xformOp:translate"].Set(Gf.Vec3d(0, 0, ROOT_Z))
else:
    xfr.AddTranslateOp().Set(Gf.Vec3d(0, 0, ROOT_Z))
print(f"[setup] Root Z = {ROOT_Z}")

# ── 7. Arm shoulder pitch ─────────────────────────────────────────────────────

for jn, ang in [("L_shoulder_pitch_joint", -90.0), ("R_shoulder_pitch_joint", 90.0)]:
    j = stage.GetPrimAtPath(f"{ROBOT}/joints/{jn}")
    if j.IsValid():
        d = UsdPhysics.DriveAPI.Apply(j, "angular")
        d.GetTargetPositionAttr().Set(ang)
        d.GetStiffnessAttr().Set(500.0)
        d.GetDampingAttr().Set(50.0)
print("[setup] Arms: shoulder pitch +/-90 deg")

# ── 8. Action Graph ───────────────────────────────────────────────────────────

SCRIPT_PATH = "/isaac-sim/.local/share/ov/data/simulation/tools/wheel_drive.py"

for gp in ["/World/DriveGraph", "/World/ActionGraph", "/World/SquareTrajectory"]:
    if stage.GetPrimAtPath(gp).IsValid():
        omni.kit.commands.execute("DeletePrimsCommand", paths=[gp])

import omni.graph.core as og
keys = og.Controller.Keys
og.Controller.edit(
    {"graph_path": "/World/DriveGraph", "evaluator_name": "execution"},
    {
        keys.CREATE_NODES: [
            ("OnPlaybackTick", "omni.graph.action.OnPlaybackTick"),
            ("ScriptNode", "omni.graph.scriptnode.ScriptNode"),
        ],
        keys.SET_VALUES: [
            ("ScriptNode.inputs:scriptPath", SCRIPT_PATH),
        ],
        keys.CONNECT: [
            ("OnPlaybackTick.outputs:tick", "ScriptNode.inputs:execIn"),
        ],
    },
)
print(f"[setup] Action Graph: /World/DriveGraph -> {SCRIPT_PATH}")

wbz = ROOT_Z + BASE_LINK_Z + LOCAL_POS0_Z - WHEEL_RADIUS
print(f"\n[setup] Wheel bottom Z = {wbz:.4f} (ground at -1.80)")
print("\n=== Setup complete ===")
print("NEXT: Press Play, then run init_robot_runtime() via MCP")


def init_robot_runtime():
    """Call via MCP execute_script AFTER pressing Play."""
    import builtins
    from omni.isaac.core import World
    from omni.isaac.core.articulations import Articulation
    world = World.instance()
    if world is None:
        world = World()
    world.initialize_physics()
    robot = Articulation("/fers_robot")
    robot.initialize()
    builtins._fers_robot = robot
    print(f"[runtime] Robot ready: {robot.num_dof} DOFs — trajectory starting!")
