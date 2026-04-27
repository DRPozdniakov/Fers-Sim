# Vultr L40S + Isaac Sim Deployment Guide

## Quick Reference

| Item | Value |
|------|-------|
| GPU | 1x NVIDIA L40S (passthrough) |
| VRAM | 48 GB, 142 RT cores (3rd gen), 3x NVENC |
| Cost | $1.67/hr on-demand |
| OS | Ubuntu 22.04 LTS |
| Remote Desktop | **Sunshine + Moonlight** (open-source, Vulkan-capable) |
| Simulation View | WebRTC streaming (primary), Sunshine desktop (alternative) |
| Isaac Sim | **4.5.0** (safe start, driver 535+ OK) -- upgrade to 5.1.0 later |

> **Why not Parsec?** Parsec has NO Linux host support. Only Windows/macOS can host.
> **Why not NoMachine?** NoMachine doesn't support Vulkan rendering (only OpenGL via VirtualGL). Isaac Sim needs Vulkan.
> **Why not 5.1.0?** It needs driver 580.65+. Vultr ships ~550.x. Start with 4.5.0, upgrade driver later.

## Step-by-Step Deployment

### 1. Create Vultr Instance

1. Go to https://my.vultr.com/deploy/
2. Select **Cloud GPU**
3. Choose **NVIDIA L40S** (1 GPU) -- $1.67/hr
4. Region: pick closest to you
5. OS: **Ubuntu 22.04 LTS**
6. Click Deploy

### 2. Run Diagnostic First

```bash
ssh root@<VULTR_IP>

# Upload script
# (from your local machine: scp deploy/vultr_isaac_sim_setup.sh root@<VULTR_IP>:/root/)

# Check if the system is viable BEFORE installing anything
bash vultr_isaac_sim_setup.sh --diagnose
```

This checks: GPU model, driver version, RT cores, Vulkan, disk space, RAM.
If it says FATAL -- stop and investigate before proceeding.

### 3. Run Phase 1 (Install Everything)

```bash
bash vultr_isaac_sim_setup.sh
# Takes ~20-30 min (mostly Docker image pull)
# Reboot when prompted
```

### 4. Run Phase 2 (Post-Reboot Verification)

```bash
ssh root@<VULTR_IP>
bash vultr_isaac_sim_setup.sh --post-reboot
```

This verifies: GPU, LightDM, Vulkan, Docker NVIDIA, Isaac Sim image, starts Sunshine.

### 5. Set User Password

```bash
sudo passwd isaac
```

### 6. Connect with Moonlight (Full Desktop)

**First time -- pair Sunshine:**

```bash
# From your local machine, create SSH tunnel to Sunshine web UI:
ssh -L 47984:localhost:47984 root@<VULTR_IP>
# Open: https://localhost:47984
# Create username and password in the Sunshine web UI
```

**Then connect:**

1. Install Moonlight: https://moonlight-stream.org/
2. Open Moonlight, add host: `<VULTR_IP>`
3. Enter the PIN shown in Moonlight into the Sunshine web UI
4. Click Desktop -- you get a full XFCE desktop with GPU acceleration

### 7. Launch Isaac Sim

**Option A: Full GUI via Sunshine desktop (run from Moonlight session terminal)**
```bash
~/isaac-sim/launch_gui.sh
```

**Option B: WebRTC streaming (no desktop needed, just SSH)**
```bash
# On the server:
~/isaac-sim/launch_webrtc.sh

# On your LOCAL machine (SSH tunnel):
ssh -N -f -L 49100:localhost:49100 -L 8211:localhost:8211 isaac@<VULTR_IP>

# Open in Chrome/Edge:
# http://127.0.0.1:8211/streaming/webrtc-client/?server=127.0.0.1
```

> First launch takes **10-15 minutes** for shader compilation. Be patient.

## Cost Management

- Vultr charges hourly **even when stopped**
- To stop billing: **destroy** the instance
- To save state: create a **snapshot** before destroying (~$0.05/GB/mo)
- At 8 hrs/day, 22 days/month: **~$294/month**

## Upgrading to Isaac Sim 5.1.0

Once 4.5.0 works, upgrade:

```bash
# 1. Upgrade NVIDIA driver to 580.65+
# Follow Vultr's guide: https://docs.vultr.com/how-to-downgrade-or-reinstall-nvidia-drivers-on-vultr-bare-metal-and-passthrough-gpu-instances

# 2. Pull new image
docker pull nvcr.io/nvidia/isaac-sim:5.1.0

# 3. Update launch scripts (change 4.5.0 -> 5.1.0)
sed -i 's/4.5.0/5.1.0/g' ~/isaac-sim/launch_gui.sh ~/isaac-sim/launch_webrtc.sh
```

Note: In 5.1.0, the WebRTC script changed from `runheadless.webrtc.sh` to `runheadless.sh`.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `nvidia-smi` not found | Vultr GPU images should have it. Check instance type. |
| LightDM won't start | Check `cat /var/log/Xorg.0.log` for xorg.conf errors |
| Sunshine won't start | Check `/tmp/sunshine.log`, verify LightDM is running first |
| Moonlight can't find host | Ensure ports 47984,47989,47990/tcp and 48010/udp are open |
| Isaac Sim grey screen (WebRTC) | Use SSH tunneling (not direct IP). NAT breaks WebRTC. |
| Isaac Sim crashes VkError | Run `~/isaac-sim/check_gpu.sh`, verify Vulkan works |
| Docker NVIDIA error | `nvidia-ctk runtime configure --runtime=docker && systemctl restart docker` |
| Slow first launch | Normal -- shader compilation takes 10-15 min on first run |
| Shader cache corruption | `rm -rf ~/docker/isaac-sim/cache/*` and restart |

## GPU Compatibility

| GPU | Isaac Sim? | Reason |
|-----|-----------|--------|
| **L40S** | **YES** | RT cores + NVENC + passthrough on Vultr |
| A40 | Risky | Has RT cores but vGPU on Vultr (not passthrough) |
| A100 | **NO** | No RT cores -- explicitly unsupported |
| H100 | **NO** | No RT cores -- explicitly unsupported |
| A16 | **NO** | Too weak (1,280 CUDA cores per die) |

## Ports Reference

| Port | Protocol | Service |
|------|----------|---------|
| 22 | TCP | SSH |
| 47984 | TCP | Sunshine web UI (HTTPS) |
| 47989 | TCP | Sunshine API |
| 47990 | TCP | Sunshine RTSP |
| 48010 | TCP/UDP | Sunshine video stream |
| 49100 | TCP | Isaac Sim WebRTC signaling |
| 47998 | UDP | Isaac Sim WebRTC media |
| 8211 | TCP | Isaac Sim web viewer |

## What's Untested (Expect Manual Fixes)

This setup has **not been publicly validated** by anyone. Known unknowns:
- Vultr's xorg.conf behavior with virtual display on L40S passthrough
- Whether Sunshine's KMS/DRM capture works on Vultr's virtualization layer
- Exact NVIDIA driver version Vultr ships (affects Isaac Sim version choice)
- WebRTC ICE negotiation through Vultr's network/NAT
- Isaac Sim Docker container Vulkan initialization on this specific environment
