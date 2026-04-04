# Isaac Sim Cloud Deploy

Deploy [NVIDIA Isaac Sim](https://developer.nvidia.com/isaac-sim) on cloud GPU instances with full interactive GUI access via remote desktop.

**Tested on:** Nebius Cloud (L40S) and Vultr (L40S)

## The Problem

Cloud GPU providers ship headless NVIDIA drivers — CUDA works, but **Vulkan doesn't**. Isaac Sim requires Vulkan for rendering. Every `apt` package approach fails:

| Approach | Result |
|----------|--------|
| `libnvidia-gl-580` | Headless libs, no Vulkan symbols |
| `libnvidia-gl-580-server` | Has Vulkan libs but `libnvidia-glcore.so` links against X server internals — fails in headless |
| `nvidia-driver-580` (full) | Dependency conflicts with pre-installed server packages |

## The Solution

Purge all NVIDIA apt packages, then install userspace-only via the `.run` installer:

```bash
# Purge headless packages (keeps kernel module intact)
dpkg --force-all --purge $(dpkg -l | grep -i nvidia | awk '{print $2}')

# Download and extract .run installer
wget https://us.download.nvidia.com/tesla/580.126.09/NVIDIA-Linux-x86_64-580.126.09.run
bash NVIDIA-Linux-x86_64-580.126.09.run --extract-only

# Install standalone userspace (no X server deps)
./NVIDIA-Linux-x86_64-580.126.09/nvidia-installer --no-kernel-modules --no-questions --ui=none
```

The `.run` installer's userspace libs are standalone — they don't depend on X server symbols (`ErrorF`, `miCreateDefColormap`, `xf86ProcessOptions`) that cause the headless `vk_icdGetInstanceProcAddr` to return NULL.

## Quick Start (Nebius Cloud)

```bash
# 1. Upload and run setup (20-30 min)
scp tools/nebius_isaac_sim_setup.sh latoff@<VM_IP>:~/
ssh latoff@<VM_IP> 'sudo bash ~/nebius_isaac_sim_setup.sh'

# 2. Reboot
ssh latoff@<VM_IP> 'sudo reboot'

# 3. Post-reboot verification
ssh latoff@<VM_IP> 'sudo bash ~/nebius_isaac_sim_setup.sh --post-reboot'

# 4. Connect via Moonlight
bash tools/connect.sh <VM_IP> --sunshine
# Open https://localhost:47990, pair Moonlight, connect to desktop

# 5. Launch Isaac Sim from remote desktop
~/isaac-sim/start.sh
```

Or use the automated deployer:

```bash
bash tools/deploy.sh <VM_IP>           # Phase 1
ssh latoff@<VM_IP> 'sudo reboot'
bash tools/deploy.sh <VM_IP> --phase2  # Phase 2
```

## Requirements

- **GPU**: NVIDIA L40S, A40, or RTX series (must have RT cores — A100/H100 will NOT work)
- **OS**: Ubuntu 24.04
- **Driver**: 580.65+ (Isaac Sim 5.1.0 requirement)
- **Local**: [Moonlight](https://moonlight-stream.org/) client for remote desktop

## Remote Access

Two methods are set up automatically:

| Method | Use Case | How |
|--------|----------|-----|
| **Sunshine + Moonlight** | Full interactive desktop, low latency | `bash tools/connect.sh <IP> --sunshine` |
| **WebRTC** | Browser-only, no install needed | `bash tools/connect.sh <IP> --webrtc` |

## Repo Structure

```
tools/
  nebius_isaac_sim_setup.sh   # Main setup script (Nebius Cloud)
  vultr_isaac_sim_setup.sh    # Setup script (Vultr Cloud)
  deploy.sh                   # Local deploy orchestrator
  connect.sh                  # SSH tunnel helper
  vultr_manage.sh             # Vultr snapshot/destroy/restore
  DEPLOY.md                   # Step-by-step deploy guide
md/
  nebius-isaac-sim-deployment.md   # Nebius troubleshooting guide
  vultr-isaac-sim-deployment.md    # Vultr troubleshooting guide
  isaac-sim-cloud-gpu-research.md  # GPU/provider research
```

## What the Setup Script Does

1. Installs system packages (xfce4, vulkan-tools, X server)
2. **Fixes Vulkan** — purges headless NVIDIA packages, installs full userspace via `.run`
3. Configures X server with virtual display
4. Installs Docker + NVIDIA Container Toolkit
5. Installs Sunshine (remote desktop streaming with NVENC)
6. Configures LightDM with autologin
7. Pulls Isaac Sim Docker image (~20GB)
8. Creates launcher scripts (`start.sh`, `launch_webrtc.sh`)

## Troubleshooting

See [md/nebius-isaac-sim-deployment.md](md/nebius-isaac-sim-deployment.md) for detailed troubleshooting of every error encountered during development:

- Vulkan `vk_icdGetInstanceProcAddr` returning NULL
- Docker missing `nvidia-imex`, `libnvidia-nscq.so`
- Sunshine encoder detection failures
- LightDM autologin issues
- Container toolkit reinstallation after driver purge

## License

MIT
