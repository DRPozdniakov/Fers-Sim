# FERS Sim

Simulate the [FERS humanoid robot](https://fers.ai) in [NVIDIA Isaac Sim 5.1.0](https://developer.nvidia.com/isaac-sim) on cloud GPU instances with full interactive GUI access via remote desktop.

**Tested on:** Nebius Cloud (L40S), Shadeform (L40S)

## Pipelines

### 1. Cloud Deployment

Provisions a GPU VM with Isaac Sim, Vulkan, and remote desktop (Sunshine + Moonlight).

```
deploy/deploy.sh <VM_IP>              # Phase 1: system packages, Docker, Sunshine
ssh user@<VM_IP> 'sudo reboot'       # Reboot for kernel modules
deploy/deploy.sh <VM_IP> --phase2     # Phase 2: purge apt nvidia, install .run userspace
deploy/connect.sh <VM_IP> --sunshine  # SSH tunnel + Moonlight pairing
```

**Key constraint:** cloud providers ship headless NVIDIA drivers without Vulkan. The deploy script purges all apt nvidia packages, installs userspace-only via `.run` installer (`--no-kernel-modules`), and backs up kernel modules for reboot resilience.

### 2. FBX to URDF Conversion

Converts the FERS robot FBX model into a URDF with per-link STL meshes.

```
pip install assimp-py numpy
python deploy/extract_fbx.py
```

- Input: `simulation/cad/fers_fbx_02_Tpose.fbx` (T-pose model)
- Output: `simulation/fers_robot.urdf` (27 links, 26 joints) + `simulation/meshes/*.stl`

### 3. Robot Import into Isaac Sim

**GUI method (reliable):** Isaac Utils > URDF Importer > select `fers_robot.urdf`

**Programmatic import is broken in 5.1.0** -- `URDFParseAndImportFile` returns `(False, None)`. The API namespace changed from `omni.isaac.*` to `isaacsim.*` but import still fails silently.

### 4. Joint Control & Animation

Scripts in `simulation/tools/` control the robot via the USD Physics API:

```python
# Set joint target (degrees)
UsdPhysics.DriveAPI.Get(prim, "angular").GetTargetPositionAttr().Set(degrees)
```

**Joint tuning is critical.** The URDF importer sets ~2500:1 stiffness:damping, causing violent shaking. Fix with 10:1 ratio:

| Joint Type | Stiffness | Damping | Max Force |
|------------|-----------|---------|-----------|
| Shoulder   | 500       | 50      | 200       |
| Elbow      | 400       | 40      | 150       |
| Wrist      | 200       | 20      | 50        |
| Wheel      | 0 (vel)   | 50      | 100       |

### 5. MCP Server (Claude Code Integration)

Isaac Sim MCP server enables direct scene control from Claude Code -- 41 tools for scene setup, joint control, simulation stepping, and diagnostics.

#### Installation (on the GPU VM, inside SSH)

```bash
pip install isaacsim-mcp-server
```

The server binary installs to `~/.local/bin/isaacsim-mcp-server`. It communicates with Isaac Sim's built-in MCP extension on port 8766.

#### Configuration (local machine)

Create/edit `.claude.json` in the project root:

```json
{
  "mcpServers": {
    "isaac-sim": {
      "command": "ssh",
      "args": [
        "-i", "C:\\Users\\<you>\\.ssh\\<key>",
        "-o", "StrictHostKeyChecking=no",
        "user@<VM_IP>",
        "/home/<user>/.local/bin/isaacsim-mcp-server"
      ]
    }
  }
}
```

Replace `<you>`, `<key>`, `user`, and `<VM_IP>` with your values. The full path to the binary is required because SSH doesn't load `~/.local/bin` into PATH.

#### Startup sequence

1. Launch Isaac Sim on the VM (Docker or desktop)
2. Wait for Isaac Sim to fully load (~2 min)
3. Start Claude Code -- MCP connects automatically via SSH

#### Available tools (41 total)

| Category | Tools |
|----------|-------|
| **Scene** | `get_scene_info`, `clear_scene`, `list_prims`, `get_prim_info` |
| **Physics** | `create_physics_scene`, `get_physics_state`, `set_physics_params` |
| **Simulation** | `play_simulation`, `pause_simulation`, `stop_simulation`, `step_simulation`, `get_simulation_state` |
| **Objects** | `create_object`, `delete_object`, `clone_object`, `transform_object` |
| **Robot** | `create_robot`, `get_robot_info`, `import_urdf`, `list_available_robots` |
| **Joints** | `get_joint_positions`, `set_joint_positions`, `get_joint_config` |
| **Materials** | `create_material`, `apply_material` |
| **Lights** | `create_light`, `modify_light` |
| **Camera** | `create_camera`, `capture_image` |
| **USD** | `load_usd`, `search_usd`, `load_environment`, `list_environments` |
| **Scripts** | `execute_script`, `reload_script`, `create_action_graph`, `edit_action_graph` |
| **Sensors** | `create_lidar`, `get_lidar_point_cloud` |
| **Logs** | `get_isaac_logs` |

#### Workflow: MCP vs Scripts vs Action Graphs

| Layer | Runs | Use for |
|-------|------|---------|
| **MCP tools** | Between frames (editor-level) | Scene setup, inspection, stepping, joint control, diagnostics |
| **Scripts** (`execute_script`, `reload_script`) | One-shot in editor | Complex USD manipulation, bulk setup, debugging |
| **Action Graphs** (`create_action_graph`) | Every tick at runtime | Control loops, IK solvers, state machines |

#### Typical MCP workflow

```
1. get_scene_info                          # verify connection
2. create_physics_scene                    # gravity, ground plane
3. create_light (DomeLight)                # illumination
4. create_object / load_usd / import_urdf  # populate scene
5. get_prim_info                           # verify positions/sizes
6. play_simulation                         # start physics
7. set_joint_positions                     # control robot
8. step_simulation (with observe_prims)    # debug loop
9. get_isaac_logs                          # check errors
```

#### Limitations

- **URDF import via MCP fails** in 5.1.0 -- use GUI URDF Importer instead
- **Heavy environments can crash Isaac Sim** -- start with simple scenes
- **MCP runs on main thread** -- long-running scripts block the UI
- **No clipboard access** -- use `execute_script` to run code, not copy-paste via Moonlight

### 6. Remote Control Server

TCP server (`simulation/tools/remote_control.py`) for sending Python commands to Isaac Sim from any client. Port 8224. Run once in Script Editor.

### 7. Scene & Environment Setup

Via MCP or GUI: create physics scene, ground plane, lighting. Built-in Isaac Sim environments work. Custom environments must be mesh-based USD -- **Gaussian Splat / NuRec volumes do not render in Isaac Sim 5.1.0** (schema exists but no GPU renderer).

## Docker Volume Mounts

Isaac Sim runs in Docker. Files must go to the **Docker-mounted directory**, not `~/simulation/`:

| Host Path | Container Path |
|-----------|---------------|
| `~/docker/isaac-sim/data/simulation/` | `/isaac-sim/.local/share/ov/data/simulation/` |
| `~/docker/isaac-sim/logs/` | `/isaac-sim/.nvidia-omniverse/logs/` |
| `~/docker/isaac-sim/config/` | `/isaac-sim/.nvidia-omniverse/config/` |

Upload files via SCP to `~/docker/isaac-sim/data/simulation/`, NOT `~/simulation/`.

## Requirements

- **GPU**: NVIDIA L40S, A40, or RTX series (RT cores required -- A100/H100 will NOT work)
- **OS**: Ubuntu 24.04
- **Driver**: 580.65+ (Isaac Sim 5.1.0)
- **Local**: [Moonlight](https://moonlight-stream.org/) client for remote desktop

## Remote Access

| Method | Use Case | How |
|--------|----------|-----|
| **Sunshine + Moonlight** | Full interactive desktop, low latency | `deploy/connect.sh <IP> --sunshine` |
| **WebRTC** | Browser-only, no install needed | `deploy/connect.sh <IP> --webrtc` |
| **Direct Moonlight** | No SSH tunnel (needs open ports) | `deploy/connect.sh <IP> --direct` |

## Proprietary Assets (Not Included)

The FERS robot CAD model, URDF, STL meshes, and scene files are proprietary and excluded from this repository for privacy reasons. The following paths are gitignored:

- `cad/` — original CAD/FBX source models
- `simulation/*.urdf` — generated URDF (27 links, 26 joints)
- `simulation/meshes/` — per-link STL meshes
- `simulation/scene/` — environment USD files

To use this repo, obtain the robot assets separately and place them in the `simulation/` directory.

## Repo Structure

```
scripts/
  load_fers_robot_new.py      # Robot loader (URDF import + physics setup)
  start_teleop.py             # Keyboard teleoperation (WASD + arm control)
  start_trajectory_waypoints.py  # Waypoint trajectory with arm poses
deploy/
  deploy.sh                   # Local deploy orchestrator
  connect.sh                  # SSH tunnel helper
  extract_fbx.py              # FBX to URDF+STL extraction
  nebius_isaac_sim_setup.sh   # Main setup script (2-phase)
  vultr_isaac_sim_setup.sh    # Setup script (Vultr Cloud)
  vultr_manage.sh             # Vultr snapshot/destroy/restore
  DEPLOY.md                   # Step-by-step deploy guide
simulation/                   # (gitignored proprietary assets)
  fers_robot.urdf             # Generated URDF (27 links, 26 joints)
  cad/                        # FBX source models
  meshes/                     # Per-link STL meshes
  scene/                      # Environment files (Interior.usdz)
  tools/
    control_joints.py         # Joint discovery + USD API control
    demo_animation.py         # Timed animation sequence with joint tuning
    find_tpose.py             # T-pose search across arm configurations
    load_fers_robot.py        # Programmatic URDF import (broken in 5.1.0)
    remote_control.py         # TCP server for remote Python execution
md/
  nebius-isaac-sim-deployment.md   # Nebius troubleshooting
  vultr-isaac-sim-deployment.md    # Vultr troubleshooting
  isaac-sim-cloud-gpu-research.md  # GPU/provider research
.vscode/
  launch.json                 # Debugger attach config (port 3000)
```

## Known Issues

- **URDF programmatic import fails** in Isaac Sim 5.1.0 -- use GUI URDF Importer
- **VS Code debugger extension crashes Isaac Sim** -- runs on wrong thread, causes asyncio errors
- **NuRec/Gaussian Splat scenes** -- schema types registered but no GPU renderer in Isaac Sim
- **`apt-get upgrade` breaks nvidia** -- always hold nvidia packages first
- **Docker bridge networking fails** after nvidia purge -- use `--network=host`

## License

MIT
