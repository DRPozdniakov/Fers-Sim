# Isaac Sim on Nebius Cloud - Deploy Guide

## What You Need

- **Nebius Cloud** account with GPU quota (L40S)
- **Moonlight** client: https://moonlight-stream.org/
- **SSH key** configured for Nebius VMs
- VM user: `latoff`, password: `isaac2026`

## Files

| File | Where to run | What it does |
|------|-------------|--------------|
| `nebius_isaac_sim_setup.sh` | VM (remote) | Full setup: drivers, Vulkan, Docker, Isaac Sim, Sunshine |
| `deploy.sh` | Local PC | Uploads script + runs phases automatically |
| `connect.sh` | Local PC | SSH tunnels for Sunshine/WebRTC |

---

## Deploy (Fresh VM)

### Option A: Automated (deploy.sh)

```bash
# Phase 1: upload + diagnose + install (20-30 min)
bash tools/deploy.sh <IP>

# Reboot VM
ssh latoff@<IP> 'sudo reboot'

# Wait 60s, then Phase 2: verify + start services
bash tools/deploy.sh <IP> --phase2
```

### Option B: Manual (step by step)

```bash
# 1. Upload
scp tools/nebius_isaac_sim_setup.sh latoff@<IP>:~/

# 2. Diagnose (verify GPU, driver, disk)
ssh latoff@<IP> 'sudo bash ~/nebius_isaac_sim_setup.sh --diagnose'

# 3. Phase 1 (20-30 min)
ssh latoff@<IP> 'sudo bash ~/nebius_isaac_sim_setup.sh'

# 4. Reboot
ssh latoff@<IP> 'sudo reboot'

# 5. Wait 60s, Phase 2
ssh latoff@<IP> 'sudo bash ~/nebius_isaac_sim_setup.sh --post-reboot'
```

---

## Connect to Desktop (Moonlight)

### First time — pair Moonlight with Sunshine:

```bash
# 1. Open SSH tunnel for Sunshine web UI
bash tools/connect.sh <IP> --sunshine
```

2. Open browser: **https://localhost:47990**
3. Accept the certificate warning
4. Login: `latoff` / `isaac2026`
5. Open **Moonlight**, add host: `<IP>`
6. Moonlight shows a PIN — enter it in Sunshine web UI under **PIN** tab
7. Click "Desktop" in Moonlight to connect

### After pairing (just connect):

Open Moonlight, click the host, click "Desktop".

---

## Run Isaac Sim

### From Moonlight Desktop (recommended)

Open a terminal on the remote desktop and run:

```bash
~/isaac-sim/start.sh
```

First launch takes 10-15 min (shader compilation). The Isaac Sim window appears on the desktop.

### From SSH (WebRTC — browser only)

```bash
# On VM:
~/isaac-sim/launch_webrtc.sh

# On local PC (new terminal):
bash tools/connect.sh <IP> --webrtc

# Open browser:
# http://127.0.0.1:8211/streaming/webrtc-client/?server=127.0.0.1
```

---

## Diagnostics

```bash
# On the VM:
~/isaac-sim/check_gpu.sh    # GPU, Vulkan, Docker, Sunshine status

# Quick checks:
nvidia-smi                                           # GPU status
vulkaninfo --summary 2>&1 | grep -A5 GPU             # Vulkan devices
docker ps                                            # Running containers
cat /tmp/sunshine.log | grep -E "encoder|Fatal"      # Sunshine status
```

---

## Common Issues

| Problem | Fix |
|---------|-----|
| SSH passphrase keeps failing | `eval $(ssh-agent) && ssh-add ~/.ssh/id_ed25519` |
| deploy.sh can't SCP | Upload manually: `scp tools/nebius_isaac_sim_setup.sh latoff@<IP>:~/` |
| Moonlight shows login screen | SSH in, run: `sudo systemctl restart lightdm` |
| Can't type password on login | `echo "latoff:isaac2026" \| sudo chpasswd` via SSH |
| Sunshine not running after reboot | `sudo DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 nohup sunshine > /tmp/sunshine.log 2>&1 &` |
| Isaac Sim start.sh not found | Recreate scripts: `sudo bash ~/nebius_isaac_sim_setup.sh --post-reboot` |
| Docker: nvidia-imex not found | `sudo touch /usr/bin/nvidia-imex /usr/bin/nvidia-imex-ctl && sudo chmod +x /usr/bin/nvidia-imex /usr/bin/nvidia-imex-ctl` |
| Vulkan shows only llvmpipe | Headless driver issue — re-run Phase 1 (it applies the .run fix) |

For detailed troubleshooting see: `md/nebius-isaac-sim-deployment.md`

---

## Kill Tunnels

```bash
bash tools/connect.sh --kill
```

---

## VM Specs

- GPU: NVIDIA L40S (48GB VRAM, RT cores)
- Driver: 580.126.09 (Open Kernel Module)
- OS: Ubuntu 24.04
- Isaac Sim: 5.1.0 (Docker: nvcr.io/nvidia/isaac-sim:5.1.0)
- Remote: Sunshine + Moonlight (NVENC h264/hevc/av1)
