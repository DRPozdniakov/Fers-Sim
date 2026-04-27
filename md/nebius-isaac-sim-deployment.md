# Nebius Cloud: Isaac Sim 5.1.0 Deployment Guide

## Prerequisites

- Nebius Cloud account with GPU quota
- VM: 1x NVIDIA L40S (RT cores required — A100/H100 will NOT work)
- Image: `ubuntu24.04-cuda13.0` (or `ubuntu24.04-driverless` for cleanest install)
- SSH key configured
- Moonlight client installed locally: https://moonlight-stream.org/

## Quick Deploy

```bash
# 1. Upload setup script
scp deploy/nebius_isaac_sim_setup.sh latoff@<IP>:~/

# 2. Diagnose
ssh latoff@<IP> 'sudo bash ~/nebius_isaac_sim_setup.sh --diagnose'

# 3. Phase 1 (20-30 min)
ssh latoff@<IP> 'sudo bash ~/nebius_isaac_sim_setup.sh'

# 4. Reboot
ssh latoff@<IP> 'sudo reboot'

# 5. Wait 60s, Phase 2
ssh latoff@<IP> 'sudo bash ~/nebius_isaac_sim_setup.sh --post-reboot'

# 6. Connect
bash deploy/connect.sh <IP> --sunshine
# Open https://localhost:47990 → pair Moonlight → connect
```

Or use the deploy helper:
```bash
bash deploy/deploy.sh <IP>
# after reboot:
bash deploy/deploy.sh <IP> --phase2
```

## How the Vulkan Fix Works

### The Problem

Nebius ships `nvidia-driver-580-server` (headless-only). This has CUDA but **no Vulkan userspace**.

The headless `libGLX_nvidia.so` exports `vk_icdGetInstanceProcAddr` but returns NULL for `vkCreateInstance` — the Vulkan implementation is stripped.

### Why apt Packages Don't Work

| Package | Problem |
|---------|---------|
| `libnvidia-gl-580` | Headless libs, 0 Vulkan symbols |
| `libnvidia-gl-580-server` | Has Vulkan libs but `libnvidia-glcore.so` links to X server symbols (`ErrorF`, `miCreateDefColormap`, `xf86ProcessOptions`) — fails in headless |
| `nvidia-driver-580` (full) | Dependency conflicts with pre-installed server packages |

### The Fix

The `.run` installer's userspace libs are **standalone** — no X server dependencies:

1. **Purge** all nvidia apt packages: `dpkg --force-all --purge $(dpkg -l | grep -i nvidia | awk '{print $2}')`
2. **Download** matching .run: `wget https://us.download.nvidia.com/tesla/580.126.09/NVIDIA-Linux-x86_64-580.126.09.run`
3. **Extract**: `bash nvidia.run --extract-only`
4. **Install userspace only**: `nvidia-installer --no-kernel-modules --no-questions --ui=none`

The kernel module (580.126.09, open) stays intact. Only userspace gets replaced.

## Troubleshooting

### Vulkan: "Could not get vkCreateInstance via vk_icdGetInstanceProcAddr"

This is the main error. Debug steps:

```bash
# Check what lib is loaded
LD_DEBUG=libs vulkaninfo --summary 2>&1 | grep -i "error\|undefined"

# If you see "undefined symbol: ErrorF" — the apt package glcore has X deps
# Fix: purge + .run installer (see above)

# Check Vulkan devices
vulkaninfo --summary 2>&1 | grep -A5 "GPU"
```

### nvidia-smi works but vulkaninfo shows only llvmpipe

Same root cause — headless driver. Follow the Vulkan fix above.

### Docker: "open /usr/bin/nvidia-imex: no such file or directory"

The purge removed optional NVIDIA binaries that the container toolkit tries to mount.

```bash
# Create empty stubs
for bin in nvidia-imex nvidia-imex-ctl nvidia-fabricmanager nvidia-fabricmanager-ctl; do
    sudo touch /usr/bin/$bin && sudo chmod +x /usr/bin/$bin
done
```

### Docker: "open libnvidia-nscq.so: no such file or directory"

NVSwitch fabric library — not in the .run installer, not needed.

```bash
sudo touch /usr/lib/x86_64-linux-gnu/libnvidia-nscq.so.580.126.09
```

**Better fix:** Use specific driver capabilities instead of `all`:
```bash
docker run --gpus all -e NVIDIA_DRIVER_CAPABILITIES=graphics,compute,utility ...
```

### Docker: "open /run/nvidia-persistenced/socket: no such file or directory"

```bash
sudo nvidia-persistenced
sudo nvidia-smi -pm 1
```

### nvidia-container-toolkit install fails (broken deps)

After purging nvidia packages, apt dependencies break. Force-install:

```bash
sudo apt-get download nvidia-container-toolkit nvidia-container-toolkit-base \
    libnvidia-container-tools libnvidia-container1
sudo dpkg --force-all -i nvidia-container-toolkit*.deb libnvidia-container*.deb
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

### Sunshine: "Unable to find display or encoder"

1. **Display not accessible** — Sunshine needs X auth:
   ```bash
   sudo DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 nohup sunshine > /tmp/sunshine.log 2>&1 &
   ```

2. **NVENC not detected** — check encoder log:
   ```bash
   grep -E "encoder|nvenc" /tmp/sunshine.log
   ```

3. **Port conflict** (RTSP 48010):
   ```bash
   sudo fuser -k 48010/tcp
   # restart sunshine
   ```

### Moonlight shows login screen (no autologin)

LightDM is showing the greeter instead of auto-logging in. Full fix:

```bash
# Write main lightdm.conf
sudo tee /etc/lightdm/lightdm.conf > /dev/null << 'EOF'
[Seat:*]
autologin-user=latoff
autologin-user-timeout=0
user-session=xfce
EOF

# Add user to autologin group (required by PAM)
sudo groupadd -f autologin
sudo usermod -aG autologin latoff

# Set password (backup — some PAM configs still need it)
echo "latoff:isaac2026" | sudo chpasswd

# Restart lightdm
sudo systemctl restart lightdm
sleep 5

# Restart Sunshine on the new session
sudo DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 nohup sunshine > /tmp/sunshine.log 2>&1 &
```

### Sunshine: "Failed to start session"

Desktop environment missing (xfce4 purged or not installed):
```bash
sudo apt-get install -y xfce4 xfce4-terminal
sudo systemctl restart lightdm
```

### .run installer: "alternate driver installation detected"

Remaining nvidia apt packages. Purge everything:
```bash
sudo dpkg --force-all --purge $(dpkg -l | grep -i nvidia | awk '{print $2}')
# then retry installer
```

### GPG error during container toolkit install

Add `--batch --yes` to gpg command:
```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
    gpg --batch --yes --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
```

## Architecture

```
Local PC                          Nebius VM (L40S)
─────────                         ────────────────
Moonlight ──── Sunshine ──── LightDM/Xfce ──── NVIDIA GPU
                  │
                  ├── NVENC h264/hevc/av1 encoding
                  └── DVI-D-0 virtual display
                  
Isaac Sim (Docker) ──── Vulkan ──── NVIDIA L40S
  │
  ├── GUI mode: X11 forwarding via --network=host
  └── WebRTC mode: port 8211 + 49100
```

## Files

| File | Purpose |
|------|---------|
| `deploy/nebius_isaac_sim_setup.sh` | Main setup (diagnose → phase1 → reboot → phase2) |
| `deploy/deploy.sh` | Local deploy orchestrator |
| `deploy/connect.sh` | Local SSH tunnel helper (--sunshine / --webrtc / --kill) |
| `~/isaac-sim/launch_gui.sh` | Launch Isaac Sim with GUI (on VM) |
| `~/isaac-sim/launch_webrtc.sh` | Launch Isaac Sim WebRTC streaming (on VM) |
| `~/isaac-sim/check_gpu.sh` | GPU/Vulkan/Docker diagnostics (on VM) |

## Key Lessons Learned

1. **Never use `NVIDIA_DRIVER_CAPABILITIES=all` on Nebius** — it tries to mount nscq/fabricmanager libs that don't exist. Use `graphics,compute,utility`.
2. **The `-server` apt GL package has X server deps** — its `libnvidia-glcore.so` can't be loaded outside Xorg.
3. **The `.run` installer is the only reliable way** to get full Vulkan on Nebius headless VMs.
4. **`--no-kernel-modules` is critical** — keeps the working Nebius kernel module, only replaces userspace.
5. **After purging nvidia packages**, you must reinstall nvidia-container-toolkit, nvidia-persistenced, and create stub binaries.
6. **Sunshine web UI is port 47990** (not 47984). Pair via SSH tunnel.
7. **Nebius VMs have no password** — set one via `chpasswd` or configure autologin.
