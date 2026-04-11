"""
FERS Sim — Full Scene Setup
Run once in Isaac Sim's Script Editor after a fresh launch.

  exec(open("/home/spir4l/simulation/tools/setup_scene.py").read())

Sets up:
  1. Physics scene + infinite ground plane (invisible)
  2. Visual grey grid floor (20x20 m, 1 m squares)
  3. Lighting (dome + sun)
  4. FERS robot (URDF import, fix_base=False)
  5. Robot physics (base_link height, mass, locked axes, wheel spheres, drives)
  6. Square trajectory action graph
"""

import omni.kit.commands
import omni.usd
import os
from pxr import (
    UsdPhysics, PhysxSchema, UsdGeom, UsdShade, UsdLux,
    Gf, Sdf, Vt
)

URDF_PATH    = "/isaac-sim/.local/share/ov/data/simulation/fers_robot.urdf"
TRAJ_SCRIPT  = "/isaac-sim/simulation/tools/square_trajectory.py"

WHEEL_RADIUS  = 0.0712    # m — outer rolling radius (from URDF mesh)
WHEEL_JOINT_Z = 0.34128   # m — wheel joint Z above base_link (from URDF joint origin)
START_Z       = WHEEL_RADIUS - WHEEL_JOINT_Z   # = -0.2701 m


# ── 1. Physics scene ──────────────────────────────────────────────────────────

def setup_physics_scene():
    stage = omni.usd.get_context().get_stage()
    if stage.GetPrimAtPath("/World/PhysicsScene").IsValid():
        print("[scene] PhysicsScene already exists")
        return
    UsdPhysics.Scene.Define(stage, "/World/PhysicsScene")
    scene = stage.GetPrimAtPath("/World/PhysicsScene")
    scene.GetAttribute("physics:gravityDirection").Set(Gf.Vec3f(0, 0, -1))
    scene.GetAttribute("physics:gravityMagnitude").Set(9.81)
    print("[scene] PhysicsScene created")


# ── 2. Ground (visual mesh + invisible physics plane) ────────────────────────

def setup_ground():
    stage = omni.usd.get_context().get_stage()

    # Invisible infinite physics plane
    if not stage.GetPrimAtPath("/World/PhysicsGround").IsValid():
        phys_plane = UsdGeom.Plane.Define(stage, "/World/PhysicsGround")
        phys_plane.GetAxisAttr().Set("Z")
        p = phys_plane.GetPrim()
        p.GetAttribute("visibility").Set("invisible")
        UsdPhysics.CollisionAPI.Apply(p)
        px = PhysxSchema.PhysxCollisionAPI.Apply(p)
        px.GetContactOffsetAttr().Set(0.002)
        px.GetRestOffsetAttr().Set(0.001)
        mat = UsdPhysics.MaterialAPI.Apply(p)
        mat.GetStaticFrictionAttr().Set(0.9)
        mat.GetDynamicFrictionAttr().Set(0.8)
        mat.GetRestitutionAttr().Set(0.0)
        print("[scene] Invisible physics plane created at Z=0")

    # Visual grey grid mesh
    if stage.GetPrimAtPath("/World/GridFloor").IsValid():
        print("[scene] GridFloor already exists")
        return

    size, subdivs = 20.0, 20
    points, indices, face_counts = [], [], []
    for row in range(subdivs + 1):
        for col in range(subdivs + 1):
            points.append(Gf.Vec3f((col / subdivs - 0.5) * size,
                                   (row / subdivs - 0.5) * size, 0.0))
    for row in range(subdivs):
        for col in range(subdivs):
            i0 = row * (subdivs + 1) + col
            indices.extend([i0, i0 + 1, i0 + subdivs + 2, i0 + subdivs + 1])
            face_counts.append(4)

    mesh = UsdGeom.Mesh.Define(stage, "/World/GridFloor")
    mesh.GetPointsAttr().Set(Vt.Vec3fArray(points))
    mesh.GetFaceVertexIndicesAttr().Set(Vt.IntArray(indices))
    mesh.GetFaceVertexCountsAttr().Set(Vt.IntArray(face_counts))
    mesh.GetDoubleSidedAttr().Set(True)

    # Grey material
    mat_path = "/World/GreyGridMat"
    mat = UsdShade.Material.Define(stage, mat_path)
    sh = UsdShade.Shader.Define(stage, f"{mat_path}/PBR")
    sh.SetSourceAsset("OmniPBR.mdl", "mdl")
    sh.SetSourceAssetSubIdentifier("OmniPBR", "mdl")
    sh.CreateInput("diffuse_color_constant", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.35, 0.35, 0.35))
    sh.CreateInput("reflection_roughness_constant", Sdf.ValueTypeNames.Float).Set(0.9)
    for out in ("surface", "volume", "displacement"):
        mat.CreateOutput(out, Sdf.ValueTypeNames.Token).ConnectToSource(
            sh.ConnectableAPI(), "out")
    UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(mat)

    # White grid lines (2 cm wide, 1 mm above floor)
    lw, z = 0.02, 0.001
    lp, li, lc = [], [], []

    def quad(p0, p1, p2, p3):
        b = len(lp); lp.extend([p0, p1, p2, p3])
        li.extend([b, b+1, b+2, b+3]); lc.append(4)

    for i in range(subdivs + 1):
        t = (i / subdivs - 0.5) * size
        quad(Gf.Vec3f(t-lw/2, -size/2, z), Gf.Vec3f(t+lw/2, -size/2, z),
             Gf.Vec3f(t+lw/2,  size/2, z), Gf.Vec3f(t-lw/2,  size/2, z))
        quad(Gf.Vec3f(-size/2, t-lw/2, z), Gf.Vec3f(size/2, t-lw/2, z),
             Gf.Vec3f( size/2, t+lw/2, z), Gf.Vec3f(-size/2, t+lw/2, z))

    lm_path = "/World/GridLineMat"
    lm = UsdShade.Material.Define(stage, lm_path)
    ls = UsdShade.Shader.Define(stage, f"{lm_path}/PBR")
    ls.SetSourceAsset("OmniPBR.mdl", "mdl")
    ls.SetSourceAssetSubIdentifier("OmniPBR", "mdl")
    ls.CreateInput("diffuse_color_constant", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.7, 0.7, 0.7))
    ls.CreateInput("enable_emission", Sdf.ValueTypeNames.Bool).Set(True)
    ls.CreateInput("emissive_color", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.5, 0.5, 0.5))
    ls.CreateInput("emissive_intensity", Sdf.ValueTypeNames.Float).Set(0.3)
    for out in ("surface", "volume", "displacement"):
        lm.CreateOutput(out, Sdf.ValueTypeNames.Token).ConnectToSource(
            ls.ConnectableAPI(), "out")

    lines = UsdGeom.Mesh.Define(stage, "/World/GridLines")
    lines.GetPointsAttr().Set(Vt.Vec3fArray(lp))
    lines.GetFaceVertexIndicesAttr().Set(Vt.IntArray(li))
    lines.GetFaceVertexCountsAttr().Set(Vt.IntArray(lc))
    lines.GetDoubleSidedAttr().Set(True)
    UsdShade.MaterialBindingAPI.Apply(lines.GetPrim()).Bind(lm)

    print(f"[scene] Grid floor created ({size}m x {size}m, {subdivs} subdivs)")


# ── 3. Lighting ───────────────────────────────────────────────────────────────

def setup_lighting():
    stage = omni.usd.get_context().get_stage()
    if stage.GetPrimAtPath("/World/DomeLight").IsValid():
        print("[scene] Lights already exist")
        return
    dome = UsdLux.DomeLight.Define(stage, "/World/DomeLight")
    dome.CreateIntensityAttr().Set(800)
    dome.CreateColorAttr().Set(Gf.Vec3f(0.9, 0.9, 1.0))
    dist = UsdLux.DistantLight.Define(stage, "/World/SunLight")
    dist.CreateIntensityAttr().Set(3000)
    dist.CreateAngleAttr().Set(0.53)
    UsdGeom.Xformable(dist.GetPrim()).AddRotateXYZOp().Set(Gf.Vec3f(-45, 0, 45))
    print("[scene] Dome + sun lights added")


# ── 4 + 5. Robot import + physics ────────────────────────────────────────────

def import_robot():
    from isaacsim.asset.importer.urdf import _urdf

    cfg = _urdf.ImportConfig()
    cfg.set_merge_fixed_joints(False)
    cfg.set_fix_base(False)
    cfg.set_make_default_prim(True)
    cfg.set_create_physics_scene(False)
    cfg.set_self_collision(False)
    cfg.set_convex_decomp(False)
    cfg.set_density(0.0)
    cfg.set_distance_scale(1.0)
    cfg.set_default_drive_type(1)
    cfg.set_default_drive_strength(1e4)
    cfg.set_default_position_drive_damping(1e3)

    result, prim_path = omni.kit.commands.execute(
        "URDFParseAndImportFile",
        urdf_path=URDF_PATH,
        import_config=cfg,
    )
    if not result:
        print(f"[robot] ERROR: import failed")
        return None
    print(f"[robot] Imported at {prim_path}")
    return prim_path


def setup_robot_physics(robot_path):
    stage = omni.usd.get_context().get_stage()
    bl = stage.GetPrimAtPath(f"{robot_path}/base_link")

    # Height: wheel bottoms at Z=0
    xf = UsdGeom.Xformable(bl)
    ops = {op.GetOpName(): op for op in xf.GetOrderedXformOps()}
    if "xformOp:translate" in ops:
        ops["xformOp:translate"].Set(Gf.Vec3d(0.0, 0.0, START_Z))
    else:
        xf.AddTranslateOp().Set(Gf.Vec3d(0.0, 0.0, START_Z))
    print(f"[robot] base_link Z = {START_Z:.4f} m  (wheel bottoms at Z=0)")

    # Mass
    if not bl.HasAPI(UsdPhysics.MassAPI):
        UsdPhysics.MassAPI.Apply(bl)
    bl.GetAttribute("physics:mass").Set(40.0)

    # PhysX rigid body
    px_rb = PhysxSchema.PhysxRigidBodyAPI.Apply(bl)
    px_rb.GetAngularDampingAttr().Set(2.0)
    px_rb.GetLinearDampingAttr().Set(0.5)
    px_rb.GetMaxDepenetrationVelocityAttr().Set(1.0)
    px_rb.GetLockedRotAxisAttr().Set(3)   # lock X+Y tilt
    px_rb.GetDisableGravityAttr().Set(False)
    print("[robot] 40 kg, gravity ON, X+Y tilt locked")

    # Wheel collision spheres (one per drive wheel, at joint center)
    for side in ("left", "right"):
        sph_path = f"{robot_path}/{side}_wheel/wheel_sphere"
        if stage.GetPrimAtPath(sph_path).IsValid():
            stage.RemovePrim(sph_path)
        sph = UsdGeom.Sphere.Define(stage, sph_path)
        sph.GetRadiusAttr().Set(WHEEL_RADIUS)
        p = sph.GetPrim()
        UsdPhysics.CollisionAPI.Apply(p)
        px_col = PhysxSchema.PhysxCollisionAPI.Apply(p)
        px_col.GetContactOffsetAttr().Set(0.002)
        px_col.GetRestOffsetAttr().Set(0.001)
        mat = UsdPhysics.MaterialAPI.Apply(p)
        mat.GetStaticFrictionAttr().Set(0.9)
        mat.GetDynamicFrictionAttr().Set(0.8)
        mat.GetRestitutionAttr().Set(0.0)
    print(f"[robot] Wheel spheres: r={WHEEL_RADIUS} m, friction=0.9/0.8")

    # Wheel velocity drives
    for jname in ("left_wheel_joint", "right_wheel_joint"):
        j = stage.GetPrimAtPath(f"{robot_path}/joints/{jname}")
        drv = UsdPhysics.DriveAPI.Apply(j, "angular")
        drv.GetStiffnessAttr().Set(0.0)
        drv.GetDampingAttr().Set(5000.0)
        drv.GetMaxForceAttr().Set(500.0)
    print("[robot] Wheel drives: velocity mode (stiffness=0, damping=5000)")


# ── 6. Action graph (square trajectory) ──────────────────────────────────────

def setup_action_graph():
    import omni.graph.core as og
    import omni.usd as _usd
    import omni.kit.commands as _kit
    stage = _usd.get_context().get_stage()

    # Remove stale graph if present
    if stage.GetPrimAtPath("/World/SquareTrajectory").IsValid():
        _kit.execute("DeletePrimsCommand", paths=["/World/SquareTrajectory"])

    keys = og.Controller.Keys
    try:
        og.Controller.edit(
            {"graph_path": "/World/SquareTrajectory", "evaluator_name": "execution"},
            {
                keys.CREATE_NODES: [
                    ("OnPlaybackTick", "omni.graph.action.OnPlaybackTick"),
                    ("ScriptNode",     "omni.graph.scriptnode.ScriptNode"),
                ],
                keys.SET_VALUES: [
                    ("ScriptNode.inputs:scriptPath", TRAJ_SCRIPT),
                ],
                keys.CONNECT: [
                    ("OnPlaybackTick.outputs:tick", "ScriptNode.inputs:execIn"),
                ],
            },
        )
        print(f"[traj] Action graph created — script: {TRAJ_SCRIPT}")
    except Exception as e:
        print(f"[traj] Action graph failed ({e})")
        print("[traj] Run setup_action_graph() manually after scene loads")


# ── Main ──────────────────────────────────────────────────────────────────────

print("\n" + "="*60)
print(" FERS Sim — Scene Setup")
print("="*60)

print(f"\n[check] URDF exists: {os.path.exists(URDF_PATH)}")
print(f"[check] Traj script exists: {os.path.exists(TRAJ_SCRIPT)}")

setup_physics_scene()
setup_ground()
setup_lighting()

stage = omni.usd.get_context().get_stage()
if not stage.GetPrimAtPath("/fers_robot").IsValid():
    robot_path = import_robot()
    if robot_path:
        setup_robot_physics(robot_path)
else:
    print("[robot] /fers_robot already in stage — skipping import")

setup_action_graph()

print("\n" + "="*60)
print(" Done — press Play to run the square trajectory")
print("="*60 + "\n")
