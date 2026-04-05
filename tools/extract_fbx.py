"""Extract FERS robot FBX into URDF-ready STL meshes.

Strategy:
1. Load FBX, get world transforms for all nodes
2. For each real node, compute world position by walking UP through all
   $AssimpFbx$ intermediate nodes to accumulate the full transform
3. Convert Y-up (3ds Max) to Z-up (URDF/Isaac Sim)
4. Export each link mesh centered at its pivot point
5. Generate URDF with correct relative joint offsets
"""

import os
import struct
import numpy as np
import assimp_py

FBX_PATH = os.path.join(os.path.dirname(__file__), "..", "cad", "fers_fbx_01.fbx")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "cad", "meshes")
URDF_PATH = os.path.join(os.path.dirname(__file__), "..", "cad", "fers_robot.urdf")

SCALE = 0.001  # mm to meters


def write_stl_binary(filepath, vertices, faces):
    with open(filepath, "wb") as f:
        f.write(b"\0" * 80)
        f.write(struct.pack("<I", len(faces)))
        for face in faces:
            v0, v1, v2 = vertices[face[0]], vertices[face[1]], vertices[face[2]]
            normal = np.cross(v1 - v0, v2 - v0)
            norm = np.linalg.norm(normal)
            if norm > 0:
                normal /= norm
            f.write(struct.pack("<fff", *normal))
            f.write(struct.pack("<fff", *v0))
            f.write(struct.pack("<fff", *v1))
            f.write(struct.pack("<fff", *v2))
            f.write(struct.pack("<H", 0))


def get_transform(node):
    return np.array(node.transformation).reshape(4, 4)


def collect_world_transforms(node, parent_T=None):
    """Recursively collect world transform for every node."""
    if parent_T is None:
        parent_T = np.eye(4)
    local_T = get_transform(node)
    world_T = parent_T @ local_T
    result = {node.name: world_T}
    for child in node.children:
        result.update(collect_world_transforms(child, world_T))
    return result


def y_up_to_z_up(v):
    """Convert [x, y, z] from Y-up to Z-up: x'=x, y'=-z, z'=y"""
    return np.array([v[0], -v[2], v[1]])


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    print("Loading FBX...")
    scene = assimp_py.import_file(
        os.path.abspath(FBX_PATH),
        assimp_py.Process_Triangulate | assimp_py.Process_JoinIdenticalVertices,
    )
    print(f"Loaded {len(scene.meshes)} meshes")

    # Get world transforms for all nodes
    all_transforms = collect_world_transforms(scene.root_node)

    # Build mesh lookup: name -> [(verts, faces), ...]
    mesh_data = {}
    for mesh in scene.meshes:
        verts = np.array(mesh.vertices).reshape(-1, 3)
        faces = np.array(mesh.indices).reshape(-1, 3)
        mesh_data.setdefault(mesh.name, []).append((verts, faces))

    # For each mesh, compute world-space vertices using the node transform,
    # then get the centroid as pivot estimate.
    # Also convert to Z-up and meters.
    def get_mesh_world_verts(mesh_name):
        """Get all vertices for a mesh name in world space, Z-up, meters."""
        if mesh_name not in mesh_data:
            return None
        T = all_transforms.get(mesh_name, np.eye(4))
        all_v = []
        for verts, _ in mesh_data[mesh_name]:
            ones = np.ones((len(verts), 1))
            v_world = (T @ np.hstack([verts, ones]).T).T[:, :3]
            # Y-up to Z-up
            v_zup = np.column_stack([v_world[:, 0], -v_world[:, 2], v_world[:, 1]])
            all_v.append(v_zup * SCALE)
        return np.vstack(all_v)

    # ========== LINK DEFINITIONS ==========
    # mesh_names: which FBX meshes compose this link
    # The pivot is the centroid of the FIRST mesh listed (the joint body)
    LINKS = {
        "base_link": ["Box007", "Box008", "Hose001", "Object002"],
        "left_wheel": ["Object004"],
        "right_wheel": ["Object005"],
        "left_wheel_cover": ["ChamferCyl004"],
        "right_wheel_cover": ["ChamferCyl005"],
        "torso": ["Body", "Line9003", "Line9004"],
        "head": ["ChamferCyl002", "Lens002", "Line9017", "Line9018",
                 "Object007", "Object008", "Object009", "Object010",
                 "Object011", "Object012"],
        "left_eye": ["Projector", "lens", "Line9019", "Line9020"],
        "right_eye": ["Projector001", "lens001", "Line9023", "Line9024"],
        # Left arm
        "L_shoulder_yaw": ["Cylinder005"],
        "L_shoulder_pitch": ["Cylinder251"],
        "L_upper_arm": ["Cylinder259", "Cylinder252"],
        "L_elbow": ["Cylinder003"],
        "L_forearm": ["Cylinder253", "Cylinder002", "Cylinder254"],
        "L_wrist_pitch": ["Cylinder258"],
        "L_wrist_yaw": ["Cylinder257"],
        "L_wrist_roll": ["Cylinder004", "Cylinder255", "Cylinder256"],
        "L_gripper": ["Cylinder290", "Cylinder291", "Line9026"],
        # Right arm
        "R_shoulder_yaw": ["Cylinder263"],
        "R_shoulder_pitch": ["Cylinder264"],
        "R_upper_arm": ["Cylinder272", "Cylinder265"],
        "R_elbow": ["Cylinder261"],
        "R_forearm": ["Cylinder266", "Cylinder260", "Cylinder267"],
        "R_wrist_pitch": ["Cylinder271"],
        "R_wrist_yaw": ["Cylinder270"],
        "R_wrist_roll": ["Cylinder262", "Cylinder268", "Cylinder269"],
        "R_gripper": ["Cylinder293", "Cylinder294", "Line9027"],
    }

    # ========== COMPUTE PIVOTS ==========
    # Use centroid of the primary mesh (first in list) as the joint pivot
    print("\nComputing pivot points...")
    pivots = {}
    for link_name, mesh_names in LINKS.items():
        primary = mesh_names[0]
        v = get_mesh_world_verts(primary)
        if v is not None and len(v) > 0:
            pivots[link_name] = v.mean(axis=0)
            p = pivots[link_name]
            print(f"  {link_name}: [{p[0]:.4f}, {p[1]:.4f}, {p[2]:.4f}] m")
        else:
            print(f"  WARNING: {primary} not found")
            pivots[link_name] = np.zeros(3)

    # ========== EXPORT MESHES ==========
    # Each mesh is centered at its pivot (so URDF visual origin = 0,0,0)
    print(f"\nExporting {len(LINKS)} meshes...")
    for link_name, mesh_names in LINKS.items():
        pivot = pivots[link_name]
        all_verts = []
        all_faces = []
        offset = 0

        for mname in mesh_names:
            if mname not in mesh_data:
                continue
            T = all_transforms.get(mname, np.eye(4))
            for verts, faces in mesh_data[mname]:
                ones = np.ones((len(verts), 1))
                v_world = (T @ np.hstack([verts, ones]).T).T[:, :3]
                v_zup = np.column_stack([v_world[:, 0], -v_world[:, 2], v_world[:, 1]])
                v_m = v_zup * SCALE
                v_centered = v_m - pivot
                all_verts.append(v_centered)
                all_faces.append(faces + offset)
                offset += len(verts)

        if not all_verts:
            continue
        combined_v = np.vstack(all_verts).astype(np.float32)
        combined_f = np.vstack(all_faces)
        path = os.path.join(OUT_DIR, f"{link_name}.stl")
        write_stl_binary(path, combined_v, combined_f)
        print(f"  {link_name}.stl: {len(combined_f)} faces, {os.path.getsize(path)/1024:.0f} KB")

    # ========== GENERATE URDF ==========
    print("\nGenerating URDF...")

    def rel(parent, child):
        """Relative offset from parent pivot to child pivot."""
        return pivots[child] - pivots[parent]

    def xyz(v):
        return f"{v[0]:.5f} {v[1]:.5f} {v[2]:.5f}"

    # Joint definitions: (parent, child, name, type, axis, lower, upper, effort, vel)
    JOINTS = [
        ("base_link", "left_wheel", "left_wheel_joint", "continuous", "1 0 0", 0, 0, 10, 10),
        ("base_link", "right_wheel", "right_wheel_joint", "continuous", "1 0 0", 0, 0, 10, 10),
        ("base_link", "left_wheel_cover", "left_wheel_cover_joint", "fixed", None, 0, 0, 0, 0),
        ("base_link", "right_wheel_cover", "right_wheel_cover_joint", "fixed", None, 0, 0, 0, 0),
        ("base_link", "torso", "torso_joint", "fixed", None, 0, 0, 0, 0),
        ("torso", "head", "head_pan", "revolute", "0 0 1", -1.57, 1.57, 20, 2),
        ("head", "left_eye", "left_eye_joint", "revolute", "0 1 0", -0.5, 0.5, 5, 2),
        ("head", "right_eye", "right_eye_joint", "revolute", "0 1 0", -0.5, 0.5, 5, 2),
        # Left arm
        ("torso", "L_shoulder_yaw", "L_shoulder_yaw_joint", "revolute", "0 0 1", -2.09, 2.09, 50, 2),
        ("L_shoulder_yaw", "L_shoulder_pitch", "L_shoulder_pitch_joint", "revolute", "0 1 0", -3.14, 1.57, 50, 2),
        ("L_shoulder_pitch", "L_upper_arm", "L_shoulder_roll_joint", "revolute", "1 0 0", -1.57, 1.57, 50, 2),
        ("L_upper_arm", "L_elbow", "L_elbow_joint", "revolute", "0 1 0", -2.36, 0, 40, 2),
        ("L_elbow", "L_forearm", "L_forearm_joint", "fixed", None, 0, 0, 0, 0),
        ("L_forearm", "L_wrist_pitch", "L_wrist_pitch_joint", "revolute", "0 1 0", -1.57, 1.57, 15, 3),
        ("L_wrist_pitch", "L_wrist_yaw", "L_wrist_yaw_joint", "revolute", "0 0 1", -1.57, 1.57, 15, 3),
        ("L_wrist_yaw", "L_wrist_roll", "L_wrist_roll_joint", "revolute", "1 0 0", -3.14, 3.14, 10, 3),
        ("L_wrist_roll", "L_gripper", "L_gripper_joint", "prismatic", "1 0 0", 0, 0.08, 20, 0.5),
        # Right arm
        ("torso", "R_shoulder_yaw", "R_shoulder_yaw_joint", "revolute", "0 0 1", -2.09, 2.09, 50, 2),
        ("R_shoulder_yaw", "R_shoulder_pitch", "R_shoulder_pitch_joint", "revolute", "0 1 0", -3.14, 1.57, 50, 2),
        ("R_shoulder_pitch", "R_upper_arm", "R_shoulder_roll_joint", "revolute", "1 0 0", -1.57, 1.57, 50, 2),
        ("R_upper_arm", "R_elbow", "R_elbow_joint", "revolute", "0 1 0", -2.36, 0, 40, 2),
        ("R_elbow", "R_forearm", "R_forearm_joint", "fixed", None, 0, 0, 0, 0),
        ("R_forearm", "R_wrist_pitch", "R_wrist_pitch_joint", "revolute", "0 1 0", -1.57, 1.57, 15, 3),
        ("R_wrist_pitch", "R_wrist_yaw", "R_wrist_yaw_joint", "revolute", "0 0 1", -1.57, 1.57, 15, 3),
        ("R_wrist_yaw", "R_wrist_roll", "R_wrist_roll_joint", "revolute", "1 0 0", -3.14, 3.14, 10, 3),
        ("R_wrist_roll", "R_gripper", "R_gripper_joint", "prismatic", "1 0 0", 0, 0.08, 20, 0.5),
    ]

    MASSES = {
        "base_link": 30, "left_wheel": 1, "right_wheel": 1,
        "left_wheel_cover": 0.5, "right_wheel_cover": 0.5,
        "torso": 15, "head": 3, "left_eye": 0.2, "right_eye": 0.2,
    }
    for side in ["L_", "R_"]:
        MASSES.update({
            f"{side}shoulder_yaw": 1.5, f"{side}shoulder_pitch": 1.5,
            f"{side}upper_arm": 2.0, f"{side}elbow": 1.0, f"{side}forearm": 1.5,
            f"{side}wrist_pitch": 0.5, f"{side}wrist_yaw": 0.5,
            f"{side}wrist_roll": 0.4, f"{side}gripper": 0.5,
        })

    COLORS = {
        "base_link": "white", "torso": "white", "head": "dark_grey",
        "left_wheel": "dark_grey", "right_wheel": "dark_grey",
        "left_wheel_cover": "dark_grey", "right_wheel_cover": "dark_grey",
        "left_eye": "black", "right_eye": "black",
    }
    for side in ["L_", "R_"]:
        COLORS.update({
            f"{side}shoulder_yaw": "blue", f"{side}shoulder_pitch": "dark_grey",
            f"{side}upper_arm": "white", f"{side}elbow": "blue",
            f"{side}forearm": "white", f"{side}wrist_pitch": "blue",
            f"{side}wrist_yaw": "dark_grey", f"{side}wrist_roll": "blue",
            f"{side}gripper": "blue",
        })

    # Collect all link names
    all_links = {"base_link"}
    for j in JOINTS:
        all_links.add(j[1])

    lines = [
        '<?xml version="1.0" ?>',
        '<robot name="fers_robot">',
        '',
        '  <material name="white"><color rgba="0.9 0.9 0.9 1.0"/></material>',
        '  <material name="dark_grey"><color rgba="0.3 0.3 0.3 1.0"/></material>',
        '  <material name="blue"><color rgba="0.3 0.6 0.9 1.0"/></material>',
        '  <material name="black"><color rgba="0.1 0.1 0.1 1.0"/></material>',
        '',
    ]

    for lname in sorted(all_links):
        m = MASSES.get(lname, 1.0)
        c = COLORS.get(lname, "white")
        ixx = m * 0.01
        lines.extend([
            f'  <link name="{lname}">',
            f'    <visual>',
            f'      <geometry><mesh filename="meshes/{lname}.stl"/></geometry>',
            f'      <material name="{c}"/>',
            f'    </visual>',
            f'    <collision>',
            f'      <geometry><mesh filename="meshes/{lname}.stl"/></geometry>',
            f'    </collision>',
            f'    <inertial>',
            f'      <mass value="{m}"/>',
            f'      <inertia ixx="{ixx:.4f}" ixy="0" ixz="0" iyy="{ixx:.4f}" iyz="0" izz="{ixx:.4f}"/>',
            f'    </inertial>',
            f'  </link>',
            '',
        ])

    for parent, child, jname, jtype, axis, lo, hi, eff, vel in JOINTS:
        o = rel(parent, child)
        lines.extend([
            f'  <joint name="{jname}" type="{jtype}">',
            f'    <parent link="{parent}"/>',
            f'    <child link="{child}"/>',
            f'    <origin xyz="{xyz(o)}" rpy="0 0 0"/>',
        ])
        if axis:
            lines.append(f'    <axis xyz="{axis}"/>')
        if jtype in ("revolute", "prismatic"):
            lines.append(f'    <limit lower="{lo}" upper="{hi}" effort="{eff}" velocity="{vel}"/>')
        lines.extend([f'  </joint>', ''])

    lines.append('</robot>')

    with open(URDF_PATH, "w") as f:
        f.write("\n".join(lines))

    print(f"\nDone. URDF: {URDF_PATH}")
    print(f"Meshes: {OUT_DIR}/")
    print(f"\nJoint offsets (relative, Z-up, meters):")
    for parent, child, jname, *_ in JOINTS:
        o = rel(parent, child)
        print(f"  {jname}: [{o[0]:.4f}, {o[1]:.4f}, {o[2]:.4f}]")


if __name__ == "__main__":
    main()
