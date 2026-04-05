# FERS Sim

Simulate the [FERS humanoid robot](https://fers.ai) in [NVIDIA Isaac Sim](https://developer.nvidia.com/isaac-sim) on cloud GPU instances with full interactive GUI access via remote desktop.

**Tested on:** Nebius Cloud (L40S)

## What This Does

1. **Cloud deploy** -- sets up a Nebius GPU VM with Isaac Sim, Vulkan, and remote desktop in two phases
2. **URDF generation** -- extracts an FBX robot model into URDF with per-link STL meshes for physics simulation

## The Problem

Cloud GPU providers ship headless NVIDIA drivers -- CUDA works, but **Vulkan doesn't**. Isaac Sim requires Vulkan for rendering. Every `apt` package approach fails:

| Approach | Result |
|----------|--------|
| `libnvidia-gl-580` | Headless libs, no Vulkan symbols |
| `libnvidia-gl-580-server` | Has Vulkan libs but `libnvidia-glcore.so` links against X server internals -- fails in headless |
| `nvidia-driver-580` (full) | Dependency conflicts with pre-installed server packages |

## The Solution

Purge all NVIDIA apt packages, then install userspace-only via the `.run` installer:

```bash
# Purge headless packages (kernel module stays loaded in memory)
dpkg --force-all --purge $(dpkg -l | grep -i nvidia | awk '{print $2}')

# Install standalone userspace (no X server deps)
bash NVIDIA-Linux-x86_64-580.126.09.run --extract-only
./NVIDIA-Linux-x86_64-580.126.09/nvidia-installer --no-kernel-modules --no-questions --ui=none
```

**Critical**: this must happen AFTER the last reboot. The script backs up and restores kernel modules so the VM can survive future reboots.

## Quick Start

```bash
# 1. Deploy Phase 1 (~20-30 min)
bash tools/deploy.sh <VM_IP>

# 2. Reboot
ssh latoff@<VM_IP> 'sudo reboot'

# 3. Deploy Phase 2 (~5 min)
bash tools/deploy.sh <VM_IP> --phase2

# 4. Connect via Moonlight
bash tools/connect.sh <VM_IP> --sunshine
# Open https://localhost:47990, pair Moonlight, connect to desktop

# 5. Launch Isaac Sim from remote desktop
~/isaac-sim/start.sh
```

## URDF Generation

Extract an FBX robot model into a URDF with separate STL meshes per link:

```bash
pip install assimp-py numpy
python tools/extract_fbx.py
```

This reads `cad/fers_fbx_01.fbx`, outputs:
- `cad/fers_robot.urdf` -- 27 links, 26 joints (7-DOF arms, gripper, head, mobile base)
- `cad/meshes/*.stl` -- per-link mesh files centered at joint pivots

Import in Isaac Sim: **Isaac Utils > URDF Importer** > select the `.urdf` file.

## Requirements

- **GPU**: NVIDIA L40S, A40, or RTX series (must have RT cores -- A100/H100 will NOT work)
- **OS**: Ubuntu 24.04
- **Driver**: 580.65+ (Isaac Sim 5.1.0 requirement)
- **Local**: [Moonlight](https://moonlight-stream.org/) client for remote desktop

## Remote Access

| Method | Use Case | How |
|--------|----------|-----|
| **Sunshine + Moonlight** | Full interactive desktop, low latency | `bash tools/connect.sh <IP> --sunshine` |
| **WebRTC** | Browser-only, no install needed | `bash tools/connect.sh <IP> --webrtc` |
| **Direct Moonlight** | No SSH tunnel (needs open ports) | `bash tools/connect.sh <IP> --direct` |

## Repo Structure

```
tools/
  nebius_isaac_sim_setup.sh   # Main setup script (2-phase: install + Vulkan fix)
  deploy.sh                   # Local deploy orchestrator
  connect.sh                  # SSH tunnel helper
  extract_fbx.py              # FBX to URDF+STL extraction
  vultr_isaac_sim_setup.sh    # Setup script (Vultr Cloud)
  vultr_manage.sh             # Vultr snapshot/destroy/restore
  DEPLOY.md                   # Step-by-step deploy guide
cad/                          # Robot model (gitignored, proprietary)
md/
  nebius-isaac-sim-deployment.md   # Nebius troubleshooting guide
  vultr-isaac-sim-deployment.md    # Vultr troubleshooting guide
  isaac-sim-cloud-gpu-research.md  # GPU/provider research
```

## What the Setup Script Does

**Phase 1** (before reboot -- apt still works):
1. Holds nvidia packages, runs system upgrade
2. Installs XFCE, Vulkan tools, X server, Docker, NVIDIA Container Toolkit
3. Installs Sunshine with systemd service for auto-restart
4. Configures LightDM with autologin
5. Creates Isaac Sim launch scripts
6. Pre-downloads NVIDIA `.run` installer
7. Pulls Isaac Sim Docker image (~20GB)

**Phase 2** (after reboot -- kernel module loaded):
1. Backs up kernel modules from disk
2. Purges ALL nvidia apt packages
3. Installs full userspace via `.run` installer (`--no-kernel-modules`)
4. Restores kernel modules for reboot resilience
5. Creates stub binaries for container toolkit compatibility
6. Reinstalls NVIDIA Container Toolkit via dpkg
7. Starts LightDM, Sunshine, verifies Vulkan + Docker GPU

## Troubleshooting

See [md/nebius-isaac-sim-deployment.md](md/nebius-isaac-sim-deployment.md) for detailed troubleshooting:

- Vulkan `vk_icdGetInstanceProcAddr` returning NULL
- `apt-get upgrade` breaking nvidia kernel module
- `.run` installer "alternate driver installation detected"
- Docker missing `nvidia-imex`, `libnvidia-nscq.so`
- Sunshine NvFBC "modeset" errors and RTSP port conflicts
- LightDM autologin issues

## License

MIT
