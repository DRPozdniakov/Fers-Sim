# Isaac Sim on Cloud GPU Instances: Real User Experiences Research

**Research Date:** 2026-03-30
**Sources:** NVIDIA Developer Forums, GitHub Issues, Medium, Dev.to, AWS/Azure docs, personal blogs, community guides

---

## Table of Contents

1. [Critical Finding: GPU Requirements](#1-critical-finding-gpu-requirements)
2. [Cloud Providers With Real User Experiences](#2-cloud-providers-with-real-user-experiences)
3. [Remote Access / Display Methods](#3-remote-access--display-methods)
4. [Common Problems and Failures](#4-common-problems-and-failures)
5. [Success Stories](#5-success-stories)
6. [GPU Performance Comparisons](#6-gpu-performance-comparisons)
7. [Cost Analysis](#7-cost-analysis)
8. [Official Tools and Deployment Methods](#8-official-tools-and-deployment-methods)
9. [Practical Tips and Gotchas](#9-practical-tips-and-gotchas)
10. [Summary Recommendations](#10-summary-recommendations)

---

## 1. Critical Finding: GPU Requirements

**Isaac Sim REQUIRES GPUs with RT (Ray Tracing) cores.** This is the single most important constraint for cloud deployment.

### Supported GPUs (have RT cores):
- RTX 3070, 3080, 3090 (minimum tier)
- RTX 4060, 4070, 4080, 4090
- RTX 5080, 5090 (newest, some driver issues)
- RTX A6000, RTX 6000 Ada
- **NVIDIA A10** (works, has RT cores)
- **NVIDIA L4** (works, has RT cores)
- **NVIDIA L40, L40S** (works, has RT cores -- best cloud options)
- **NVIDIA T4** (works for basic headless, has limited RT cores)

### NOT Supported (no RT cores):
- **NVIDIA A100** -- NOT supported (no RT cores, no NVENC)
- **NVIDIA H100** -- NOT supported (no RT cores)
- **NVIDIA V100** -- NOT supported
- **NVIDIA P100** -- NOT supported

**This is devastating for cloud users** because A100 and H100 are the most common and cheapest high-end GPUs on cloud platforms. Multiple forum users have expressed frustration:

> "Not providing support for server cards as the A100, H100, and upcoming B100 severely hampers the adoption of Isaac Sim by companies and universities."
> -- NVIDIA Forum user, 2024

> Error on V100: "No device could be created. Your GPUs do not support RayTracing: DXR or Vulkan ray_tracing"

**Source:** [Can I launch Isaac Sim with Tesla V100?](https://forums.developer.nvidia.com/t/can-i-launch-isaac-sim-with-tesla-v100/288953)
**Source:** [Isaac Sim A100](https://forums.developer.nvidia.com/t/isaac-sim-a100/291492)
**Source:** [IsaacLab on Cloud GPUs](https://forums.developer.nvidia.com/t/isaaclab-on-cloud-gpus/330101)
**Source:** [GPU Requirement](https://forums.developer.nvidia.com/t/gpu-requirement/305727)

---

## 2. Cloud Providers With Real User Experiences

### AWS (Amazon Web Services) -- Most Documented

**Officially supported.** NVIDIA provides marketplace AMIs.

**Instance types that work:**
| Instance | GPU | VRAM | On-Demand $/hr | Notes |
|----------|-----|------|-----------------|-------|
| g4dn.2xlarge | T4 | 16GB | ~$0.94 | Cheapest option, bare minimum |
| g5.2xlarge | A10G | 24GB | ~$1.21 | Good mid-range |
| g5.4xlarge | A10G | 24GB | ~$2.03 | More CPU/RAM |
| g6.2xlarge | L4 | 24GB | ~$0.98 | Good price/performance |
| g6e.2xlarge | L40S | 48GB | ~$1.86 | NVIDIA recommended, 2x perf over A10G |

**Real user experience (yasunori.jp blog, Oct 2025):**
- Used g4dn.2xlarge ($0.94/hr) as a budget option instead of official g5.4xlarge ($2.03/hr)
- Setup: NVIDIA GPU-Optimized AMI + Amazon DCV for remote desktop
- DCV required: install drivers, run nvidia-xconfig, configure /etc/dcv/dcv.conf
- Reboot required after DCV installation
- Isaac Sim pip install worked perfectly after DCV setup
- Monthly cost estimate: ~$715/month running 24/7
- **Gotcha:** IAM role for S3 license requires creating empty role first before adding policies

**Real user experience (mikelikesrobots blog):**
- Used g4dn.2xlarge with Spot Instances at ~$0.30/hr (70% savings)
- NICE DCV for remote desktop (pre-installed in Robotec AI AMI)
- Created EBS snapshots for Isaac Sim (1+ hour initial setup)
- CDK-based infrastructure for reproducibility
- S3 for persistent storage, automated start/stop scripts

**Real user experience (NVIDIA Forum, Nov 2024):**
- User aravindsairam1995 used NVIDIA Omniverse GPU AMI with A10G
- Isaac Sim crashed with segfault: "VkResult: ERROR_OUT_OF_DEVICE_MEMORY vkCreateSwapchainKHR failed"
- GUI deployment via NICE DCV was NOT supported for this configuration
- NVIDIA confirmed: "The Isaac Sim container supports running Python apps and standalone examples in headless mode only"

**Source:** [How to Set Up Isaac Sim on Non-Officially Supported AWS Instances](https://yasunori.jp/en/2025/10/15/aws-isaacsim.html)
**Source:** [Cost-Effective Robotics Simulation in the Cloud](https://mikelikesrobots.github.io/blog/ec2-spot-sims/)
**Source:** [Isaac Sim not working in AWS via NICE DCV](https://forums.developer.nvidia.com/t/isaac-sim-is-not-working-in-aws-cloud-via-nice-dcv/312300)
**Source:** [AWS Deployment Docs](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/install_advanced_cloud_setup_aws.html)

---

### Microsoft Azure

**Officially supported.** NVIDIA provides marketplace VMI.

**Recommended instance:** Standard_NV36ads_A10_v5 (NVIDIA A10 GPU)

**Real user experience (Microsoft Q&A, 2024):**
- GPU: NVIDIA A10-24Q with 24GB VRAM, driver 550.127.05
- CUDA error 46 (cudaErrorDevicesUnavailable) inside Docker container
- GPU visible on host but NOT accessible from within container
- Confusion between Azure's GPU Driver Extension vs manual .run installation
- **Unresolved** -- directed to Microsoft Technical Support

**Remote access:** ThinLinc is the officially documented method for Linux VMs on Azure.
- A comprehensive tutorial exists at ThinLinc Community forums
- Alternative: noVNC via Isaac Automator

**Source:** [Isaac Sim installation on Azure A10 VM](https://learn.microsoft.com/en-gb/answers/questions/2120267/isaac-sim-installation-on-azure-a10-vm)
**Source:** [Azure Deployment Docs](https://docs.isaacsim.omniverse.nvidia.com/latest/installation/install_advanced_cloud_setup_azure.html)
**Source:** [ThinLinc Setup Guide](https://forums.developer.nvidia.com/t/guide-how-to-set-up-and-run-isaac-sim-on-azure-using-thinlinc-video-tutorial/360546)

---

### Google Cloud Platform (GCP)

**Officially supported.**

**Instance types:** G2 (L4 GPU), N1 (T4 GPU)

**Real user experience (NVIDIA Forum, 2025):**
- User ran Isaac Sim 4.2.0 Docker on GCP VM with NVIDIA L4 (driver 535.183.01)
- WebRTC streaming showed persistent GREY SCREEN with no content
- Tried: port verification, firewall disable, UFW rules -- none worked
- **SOLUTION:** Switched from WebRTC web interface to "Omniverse Web Streaming Client" AND created specific GCP firewall ingress rules opening TCP/UDP ports 47995-48014 and 49003-49006

**Source:** [Grey Screen Issue with Isaac Sim on GCP VM](https://forums.developer.nvidia.com/t/grey-screen-issue-with-isaac-sim-headless-webrtc-on-gcp-vm/330086)
**Source:** [GCP Deployment Docs](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/install_advanced_cloud_setup_gcp.html)

---

### Alibaba Cloud

**Officially supported** via Isaac Automator.

**Real user experience (GitHub guide, sunnyspot114514):**
- Used A10 GPU Spot Instances on Alibaba Cloud
- Ubuntu 22.04, Docker-based deployment
- VNC desktop on port 6080 for remote visualization
- Total cost: ~$4 USD using spot instances
- Setup time: 2-3 hours
- Documented flash-attn compilation issues, Docker network config problems, VNC issues
- **Critical tip:** "Strongly recommend using the same versions. Other combinations may require adjustments."

**Source:** [isaaclab-groot-cloud-guide](https://github.com/sunnyspot114514/isaaclab-groot-cloud-guide)

---

### Vast.ai

**NOT officially supported.** User-tested.

**Real user experience (NVIDIA Forum, Apr 2025):**
- User lehoangtrung2000 used Vast.ai with RTX 4090 (24GB VRAM, 64 cores)
- Isaac Sim 4.5.0 headless loaded successfully
- WebRTC streaming showed BLANK SCREEN from laptop
- Root cause: WebRTC Streaming Client "is recommended to be used within the same network"
- Cloud servers on different networks require STUN/TURN server configuration

**Source:** [Isaac Sim development on cloud server](https://forums.developer.nvidia.com/t/isaac-sim-development-on-cloud-server/329048)

---

### NVIDIA Brev

**Officially supported** as of Isaac Sim 5.0.

- One-click access to L40S GPU instances
- Expose ports 49100 and 47998 to your IP
- Launch: `./runheadless.sh --/app/livestream/publicEndpointAddress=$PUBLIC_IP --/app/livestream/port=49100`
- Connect via Isaac Sim WebRTC Streaming Client

**Source:** [Brev Deployment Docs](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/install_advanced_cloud_setup_brev.html)

---

### Lambda Cloud

**Not officially supported, but tested.**

- Lambda Labs created an isaac-sim-benchmarking repository
- NVIDIA Container Toolkit pre-installed on Lambda Cloud
- **Key limitation:** "For livestreaming to work, the GPU instance must have an RTX card"
- Multi-GPU training supported via RL-Games and SKRL libraries
- WebRTC streaming has "documented compatibility issues"

**Source:** [Lambda Labs Isaac Sim Benchmarking](https://github.com/LambdaLabsML/isaac-sim-benchmarking)

---

### RunPod

**Not officially tested with Isaac Sim specifically.** General GPU cloud.

- Offers RTX 4090, A6000, L40S, H100 instances
- Per-second billing
- Could work for headless Isaac Lab training on RTX-equipped instances
- No documented Isaac Sim success stories found

---

### University/Institutional (Strato, Run:ai)

**Real user experience (AAU Space Robotics, GitHub):**
- Used Strato (university cloud) with T4 and A40 GPUs
- SSH port forwarding for ports 8211 and 8899
- Browser-based GUI via WebSocket: `http://localhost:8211/streaming/client`
- A40 frequently unavailable due to demand

**Real user experience (j3soon tutorial for Run:ai):**
- Pre-built Docker images: `j3soon/runai-isaac-sim:4.5.0`, `5.0.0`
- Supports SSH, VNC, Jupyter Lab, VSCode, TensorBoard
- **Critical gotcha:** "Any data stored outside the persistent NFS volume will be deleted when the container is terminated"
- Recommended workflow: build/test Docker images locally first before deploying

**Source:** [AAU Rover Isaac Sim Cloud Setup](https://github.com/AAU-Space-Robotics/aau-rover-isaac-sim/issues/1)
**Source:** [Running Isaac Sim on Run:ai](https://tutorial.j3soon.com/robotics/runai-isaac/)

---

## 3. Remote Access / Display Methods

### Method 1: WebRTC Streaming Client (RECOMMENDED by NVIDIA)

**How it works:** Isaac Sim runs headless on cloud, streams pixels via WebRTC to a native app or browser.

**Pros:**
- No GPU required on client
- Works in browser (Chromium-based)
- Native app available for Windows/macOS/Linux

**Cons:**
- Blank/grey screen is the #1 reported problem
- Requires same-network or TURN server for internet access
- WebRTC ICE negotiation fails across NAT/firewalls without STUN/TURN
- In Isaac Sim 5.0, TURN server config was broken (no way to configure ICE servers)

**Required ports:** 49100 (TCP), 47998 (UDP)

### Method 2: NICE DCV (Amazon DCV)

**How it works:** Full remote desktop to the cloud instance, then run Isaac Sim GUI natively.

**Pros:**
- Full Ubuntu desktop experience
- Low latency, GPU-accelerated streaming
- Pre-installed in some AWS AMIs

**Cons:**
- Some users report Isaac Sim crashes (VkCreateSwapchainKHR fails)
- NVIDIA container mode only supports headless (not GUI) -- so you need workstation install, not container
- Requires manual DCV setup: nvidia-xconfig, dcv.conf configuration, reboot

**Required port:** 8443 (TCP)

### Method 3: VNC (noVNC / TigerVNC)

**How it works:** Standard VNC remote desktop, often web-based via noVNC.

**Pros:**
- Simple, well-understood technology
- Supported by Isaac Automator
- Works through SSH tunnels easily

**Cons:**
- Lower performance than DCV
- May have latency issues for 3D work
- Some users report display configuration issues

### Method 4: NoMachine

**How it works:** High-performance remote desktop protocol.

**Pros:**
- Better compression than VNC
- Supported by Isaac Automator

**Cons:**
- Additional software installation
- Less commonly documented for Isaac Sim

### Method 5: ThinLinc

**How it works:** Enterprise remote desktop, officially recommended for Azure Linux VMs.

**Pros:**
- Officially documented for Azure Isaac Sim deployment
- Works on-premises and cloud
- Good for institutional deployments

### Method 6: Omniverse Streaming Client (DEPRECATED)

- **Deprecated** as of Isaac Sim 4.5+
- Replaced by WebRTC Streaming Client
- Required dedicated GPU on client machine
- Some users still use it as fallback when WebRTC fails
- Required ports: 47995-48012 (TCP/UDP), 49000-49007

---

## 4. Common Problems and Failures

### Problem 1: WebRTC Blank/Grey Screen (MOST COMMON)

Affects virtually every cloud deployment attempt.

**Root cause:** WebRTC cannot negotiate peer-to-peer connection through NAT/firewall.

**Symptoms:**
- Isaac Sim loads successfully ("Isaac Sim Full Streaming App is loaded")
- Client connects but shows blank black screen or grey screen
- Works on localhost (127.0.0.1) but not on public IP

**Solution:** Deploy a COTURN relay server:
```
sudo apt install coturn
# Edit /etc/turnserver.conf with external IP, credentials, port ranges
# Edit Isaac Sim extension.toml with ICE servers config
```

**Critical detail (Isaac Sim 5.0.0):** The TURN/ICE configuration mechanism was removed when the old WebRTC extension was deprecated. NVIDIA created an internal ticket but no fix was available as of early 2025.

**Sources:**
- [WebRTC blank screen via public IP](https://forums.developer.nvidia.com/t/isaac-sim-webrtc-streaming-client-shows-blank-screen-when-accessing-isaac-sim-via-public-ip/332119)
- [WebRTC Streaming over Internet (Medium)](https://medium.com/@BeingOttoman/scalable-streaming-nvidia-omniverse-applications-over-the-internet-using-webrtc-8946a574fef2)
- [Unable to configure TURN in Isaac Sim 5.0](https://forums.developer.nvidia.com/t/isaac-sim-5-0-0-unable-to-configure-turn-server-for-webrtc-tcp-only-setup-no-udp-allowed/347641)

### Problem 2: "Failed to acquire IWindow interface"

**When:** Running Isaac Sim with GUI on headless servers.

**Solution:** Use `./isaac-sim.headless.native.sh` or `./runheadless.sh` instead. Isaac Sim detects no display and fails unless explicitly run in headless mode.

**Source:** [Running Isaac Sim on a cloud server](https://forums.developer.nvidia.com/t/running-the-isaac-sim-on-a-cloud-server/239902)

### Problem 3: CUDA Devices Unavailable in Docker

**When:** Running Isaac Sim container on Azure A10 VMs.

**Symptoms:** `CUDA error 46: cudaErrorDevicesUnavailable`

**Potential causes:**
- Conflicting GPU driver installation (Azure GPU Extension vs manual install)
- NVIDIA Container Toolkit version mismatch (minimum 1.16.2 required)
- Docker runtime not configured for GPU access

**Source:** [Isaac Sim on Azure A10 VM](https://learn.microsoft.com/en-gb/answers/questions/2120267/isaac-sim-installation-on-azure-a10-vm)

### Problem 4: Vulkan Errors in Docker

**When:** Running Isaac Sim container with GPU passthrough.

**Symptoms:** "VkResult: ERROR_INCOMPATIBLE_DRIVER" or "Failed to CreateInstance in ICD"

**Solutions:**
- Test with `vulkaninfo` (not nvidia-smi) to verify Vulkan works in container
- Ensure NVIDIA Container Toolkit >= 1.16.2
- Reinstall drivers following Linux troubleshooting guides
- Test: `docker run --rm --runtime=nvidia --gpus all ubuntu nvidia-smi`

**Source:** [GPU and Vulkan issues in container](https://forums.developer.nvidia.com/t/gpu-and-vulkan-issues-when-opening-isaac-sim-in-the-container/327310)

### Problem 5: Docker Bridge Networking Breaks WebRTC

**When:** Using `-p` port mapping with Docker containers for WebRTC streaming.

**Root cause:** Host IP is not reachable from inside Docker's bridge network namespace.

**Solution:** Use Docker Compose with host networking or proper network configuration instead of simple `-p` port mapping.

### Problem 6: RTX A6000 Streaming Empty Content

**User experience (NVIDIA Forum):**
- Ran Isaac Sim 4.2.0 in Docker on RTX A6000
- NGX initialization errors, Vulkan detection failures
- Expected streaming ports (47995-48012) not listening
- Tried drivers 535, 550.120, 560 -- none worked
- **User gave up on A6000, switched to A10 instance**

**Source:** [RTX A6000 streaming empty content](https://forums.developer.nvidia.com/t/rtx-a6000-running-isaac-sim-container-not-able-to-connect-with-streaming-client-gui-shows-empty-content/311586)

### Problem 7: Multi-GPU Streaming Only Works on 1 of 8 GPUs

**User experience (GitHub, 2025):**
- 8x RTX 4090 system, Isaac Sim 5.1.0
- Only 1 GPU worked with WebRTC, other 7 produced sync errors
- Suspected driver regression with NVIDIA driver 580+
- Previously worked with driver 560

**Source:** [Livestream GPU sync issues](https://github.com/isaac-sim/IsaacSim/issues/348)

---

## 5. Success Stories

### Success 1: AWS g4dn + DCV (Budget Setup)
- **Provider:** AWS, g4dn.2xlarge
- **GPU:** T4
- **Cost:** ~$0.94/hr on-demand, ~$0.30/hr spot
- **Remote access:** Amazon DCV
- **What worked:** Full desktop GUI via DCV, Isaac Sim pip install
- **Key:** Used NVIDIA GPU-Optimized AMI (drivers pre-installed)

### Success 2: GCP L4 + Omniverse Streaming Client
- **Provider:** GCP
- **GPU:** L4
- **Remote access:** Omniverse Web Streaming Client (NOT WebRTC web interface)
- **What worked:** After switching from WebRTC to Omniverse Streaming Client and opening correct firewall ports (47995-48014, 49003-49006)
- **Key:** Had to create specific GCP firewall ingress rules

### Success 3: Alibaba Cloud A10 Spot + VNC
- **Provider:** Alibaba Cloud
- **GPU:** A10 (spot instance)
- **Cost:** ~$4 USD total for testing session
- **Remote access:** VNC desktop on port 6080
- **What worked:** Docker-based deployment, Isaac Sim 4.2.0 + Isaac Lab 1.4.1
- **Key:** Strict version pinning was critical

### Success 4: AWS g6e + NVIDIA AMI (Official Path)
- **Provider:** AWS, g6e.2xlarge
- **GPU:** L40S (48GB VRAM)
- **Remote access:** NICE DCV
- **What worked:** Official NVIDIA Isaac Sim Development Workstation AMI
- **Key:** Uses latest recommended instance type with best performance

### Success 5: WebRTC Over Internet with COTURN (Medium Article)
- **Provider:** AWS, g5.2xlarge
- **GPU:** A10G
- **Remote access:** WebRTC via browser with COTURN relay
- **What worked:** Multiple Kit instances on single GPU (2 optimal, 3-4 possible)
- **GPU util:** 100%, 6.8GB/23GB VRAM for 2 instances
- **Key:** COTURN server on separate machine, proper ICE configuration

### Success 6: University Strato Cloud with SSH Tunneling
- **Provider:** University Strato cloud
- **GPU:** T4 or A40
- **Remote access:** SSH port forwarding + WebSocket browser client
- **What worked:** `http://localhost:8211/streaming/client` via SSH tunnel
- **Key:** Simple, no firewall issues since everything tunnels through SSH

---

## 6. GPU Performance Comparisons

### Isaac Sim Benchmarks (Official, v4.5.0)

**Full Warehouse Scene (FPS):**
| GPU | Windows | Ubuntu |
|-----|---------|--------|
| RTX 3070 | 88.7 | 85.9 |
| RTX 4080 | 113.6 | 119.1 |
| RTX 6000 Ada | 113.1 | 119.1 |

**Isaac ROS Sample Scene (FPS, more demanding):**
| GPU | Windows | Ubuntu |
|-----|---------|--------|
| RTX 3070 | 14.4 | 14.2 |
| RTX 4080 | 27.7 | 27.4 |
| RTX 6000 Ada | 37.7 | 37.8 |

### Isaac Lab RL Training (Community Benchmarks)

| GPU | G1 Training FPS | VRAM | Notes |
|-----|-----------------|------|-------|
| RTX 4090 | 94,000 | 24GB | Best single-GPU |
| RTX 4060 Laptop | ~47,000 | 8GB | ~50% of 4090 |
| L40 (single) | 72,000 | 48GB | Slower than 4090 per-GPU |
| L40 (4x) | 290,000 | 48GB ea | Near-linear multi-GPU scaling |
| RTX 4090 (Cartpole) | ~510,000 | 24GB | 4096 parallel envs |

### Key Insight: RTX 4090 vs L40

The RTX 4090 is FASTER per-GPU than the L40 despite being a consumer card. However, the L40's 48GB VRAM allows more parallel environments, and it supports multi-GPU scaling. For cost-effective cloud training, multiple L40s beat a single 4090.

### Cloud GPU Value Ranking for Isaac Sim

1. **L40S** -- Best overall (48GB, RT cores, 2x perf over A10G), from ~$0.32/hr on cheapest providers
2. **L4** -- Best budget option (24GB, RT cores), from ~$0.24/hr
3. **A10G** -- Good mid-range (24GB, RT cores), ~$0.24/hr
4. **T4** -- Bare minimum (16GB, limited RT), from ~$0.27/hr
5. **RTX 4090** (Vast.ai, RunPod) -- Best raw performance if available

### CPU Bottleneck Warning

Physics simulation in Isaac Sim is largely CPU-bound. Cloud instances with high-throughput server CPUs (Xeon, EPYC) may underperform compared to high-frequency desktop CPUs (e.g., AMD 9800X3D). GPU utilization during RL training typically stays around 80% with one CPU core at 100%.

---

## 7. Cost Analysis

### Hourly Rates (On-Demand)

| Provider | GPU | Instance | $/hr |
|----------|-----|----------|------|
| AWS | T4 | g4dn.2xlarge | $0.94 |
| AWS | A10G | g5.2xlarge | $1.21 |
| AWS | L4 | g6.2xlarge | $0.98 |
| AWS | L40S | g6e.2xlarge | $1.86 |
| Azure | A10 | NV36ads_A10_v5 | ~$1.80 |
| Brev | L40S | -- | Varies |
| Vast.ai | RTX 4090 | -- | ~$0.30-0.50 |
| RunPod | L40S | -- | ~$0.69 |

### Spot Instance Savings (AWS)

- g4dn.2xlarge spot: ~$0.30/hr (68% savings)
- EBS snapshot storage: ~$0.05/GB/month
- S3 storage: ~$0.023/GB/month

### Monthly Cost Estimates

| Usage Pattern | Instance | Monthly Cost |
|---------------|----------|-------------|
| 24/7 g4dn.2xlarge | T4 | ~$715 |
| 8hr/day g5.2xlarge | A10G | ~$290 |
| Spot g4dn, 8hr/day | T4 | ~$72 |
| Alibaba spot (testing) | A10 | ~$4/session |

### No Free Options

NVIDIA forum moderator confirmed: "I'm not aware of a completely free option for cloud deployment of Isaac Sim."

---

## 8. Official Tools and Deployment Methods

### Isaac Automator (Terraform + Ansible)

**GitHub:** [isaac-sim/IsaacAutomator](https://github.com/isaac-sim/IsaacAutomator)

- Supports: AWS, GCP, Azure, Alibaba Cloud
- Deploys fully configured remote desktop workstation
- Access via: SSH, noVNC, NoMachine
- Stop/start functionality for cost savings
- Requires: Docker >= 26.0.0, NGC API key
- Maps folders: /uploads, /results, /workspace
- Supports autorun.sh for startup automation

### NVIDIA Marketplace AMIs/VMIs

- **AWS:** "NVIDIA Isaac Sim Development Workstation" (Linux & Windows)
- **Azure:** "NVIDIA Isaac Sim Development Workstation" (NV36ads_A10_v5)
- Software is free; infrastructure costs apply

### Container Installation

- Docker image: `nvcr.io/nvidia/isaac-sim:<version>`
- Requires NGC API key for pull
- Headless mode: `./runheadless.sh`
- WebRTC streaming: `./runheadless.webrtc.sh`
- Requires NVIDIA Container Toolkit >= 1.16.2

### NVIDIA Brev

- One-click deployment for Isaac Sim 5.0+
- L40S GPU instances
- Simplest official cloud option

---

## 9. Practical Tips and Gotchas

### Setup Tips

1. **Always test Vulkan (not just nvidia-smi):** Run `vulkaninfo` inside the container to verify GPU rendering works
2. **Use GPU-Optimized AMIs:** Pre-installed drivers save hours of debugging
3. **Pin exact versions:** Isaac Sim version changes frequently break setups
4. **Allocate 32GB+ RAM:** Isaac Sim is memory-hungry
5. **Use 128GB+ storage:** Isaac Sim + assets + Docker images are large (~50GB+ downloads)
6. **Pre-cache shaders:** Can save 5+ minutes per startup (from ReSim blog)
7. **Set CPU governor to performance:** Can significantly impact physics simulation speed

### Networking Tips

1. **SSH tunneling is the safest remote access:** Avoids all firewall/NAT issues
2. **For WebRTC over internet:** You MUST set up a COTURN/TURN server
3. **Open these port ranges for Omniverse streaming:** TCP/UDP 47995-48014, 49003-49006
4. **WebRTC port:** 49100 (TCP), 47998 (UDP)
5. **DCV port:** 8443 (TCP)
6. **Docker host networking is preferred over bridge mode for WebRTC**
7. **WebRTC resolution:** Edit client HTML to change from 1280x720 to 1920x1080

### Gotchas

1. **Omniverse Streaming Client is DEPRECATED** -- use WebRTC Streaming Client instead
2. **Isaac Sim container = headless only** -- you cannot run the GUI inside a container via remote desktop
3. **Workstation install = GUI possible** -- if you want full GUI, install Isaac Sim natively (not container) and use DCV/VNC
4. **A100/H100 DO NOT WORK** -- no matter what you try, no RT cores = no Isaac Sim
5. **Isaac Sim 4.5 is very different from 4.2** -- "My previous knowledge is completely useless" (forum user)
6. **6GB VRAM GPUs may not work with 4.5+** -- worked with 4.2 but not newer versions
7. **vGPU instances are NOT supported** (specifically noted for Alibaba Cloud)
8. **First startup takes minutes** due to shader compilation and asset loading
9. **NFS data persistence is critical** when using container orchestrators (Run:ai, Kubernetes)
10. **RTX 50-series has driver compatibility issues** as of early 2025

### Version-Specific Issues

| Version | Known Issue |
|---------|------------|
| 4.2.0 | D3D12 rendering, different from newer versions |
| 4.5.0 | Switched to Vulkan, broke many workflows |
| 4.5.0 | 8GB VRAM minimum (up from 6GB in 4.2) |
| 5.0.0 | TURN server config removed, no way to configure ICE |
| 5.0.0 | Open source (Apache 2.0), pip installable |
| 5.1.0 | DGX Spark support, ARM/aarch64 Docker images |
| 5.1.0 | Multi-GPU streaming regression with driver 580+ |

---

## 10. Summary Recommendations

### Best Cloud Setup for GUI Development (Interactive)

**Option A (Easiest):** NVIDIA Brev with L40S
- One-click deployment
- WebRTC streaming client
- Best for quick testing

**Option B (Most Control):** AWS g6e.2xlarge + NICE DCV
- Install Isaac Sim natively (not container) on the instance
- Use DCV for full remote desktop
- Best for serious development work

**Option C (Budget):** AWS g4dn.2xlarge Spot + DCV
- ~$0.30/hr with spots
- T4 is bare minimum but functional
- Use S3 + EBS snapshots for persistence

### Best Cloud Setup for Headless Training

**Option A (Official):** AWS g6e.2xlarge with L40S
- 48GB VRAM for maximum parallel environments
- 2x performance over previous generation
- Docker container deployment

**Option B (Budget):** Alibaba Cloud A10 Spot or Vast.ai RTX 4090
- Cheapest GPU with RT cores
- Docker + headless mode
- SSH tunnel for monitoring

**Option C (Scale):** Lambda Cloud or RunPod with L40S
- Multi-GPU available
- Good for distributed RL training
- Pre-installed NVIDIA Container Toolkit (Lambda)

### What to Avoid

- **A100/H100 instances** -- waste of money, Isaac Sim will not run
- **WebRTC over public internet without TURN server** -- guaranteed blank screen
- **Container deployment expecting GUI** -- containers are headless only
- **Mixing GPU architectures** (e.g., A100 + RTX in same machine) -- driver conflicts
- **Running 24/7 without stop/start automation** -- costs add up fast

---

## Source Links

### NVIDIA Developer Forums
- [Isaac Sim development on cloud server](https://forums.developer.nvidia.com/t/isaac-sim-development-on-cloud-server/329048)
- [Running Isaac Sim on a cloud server](https://forums.developer.nvidia.com/t/running-the-isaac-sim-on-a-cloud-server/239902)
- [Isaac Sim headless server deployment requirements](https://forums.developer.nvidia.com/t/isaac-sim-requirements-for-remote-headless-server-deployment/323930)
- [Isaac Sim via SSH and Remote Desktop](https://forums.developer.nvidia.com/t/isaac-sim-via-ssh-and-remote-desktop-connection-windows-and-linux-host/284090)
- [How to use Isaac Sim on cloud free](https://forums.developer.nvidia.com/t/how-can-i-use-nvidia-isaac-sim-on-cloud-free/324541)
- [2025 Feedback Request from Isaac Sim Users](https://forums.developer.nvidia.com/t/2025-feedback-request-from-isaac-sim-users/322175)
- [Isaac Sim not working via NICE DCV](https://forums.developer.nvidia.com/t/isaac-sim-is-not-working-in-aws-cloud-via-nice-dcv/312300)
- [Grey Screen on GCP VM](https://forums.developer.nvidia.com/t/grey-screen-issue-with-isaac-sim-headless-webrtc-on-gcp-vm/330086)
- [RTX A6000 streaming empty content](https://forums.developer.nvidia.com/t/rtx-a6000-running-isaac-sim-container-not-able-to-connect-with-streaming-client-gui-shows-empty-content/311586)
- [WebRTC blank screen via public IP](https://forums.developer.nvidia.com/t/isaac-sim-webrtc-streaming-client-shows-blank-screen-when-accessing-isaac-sim-via-public-ip/332119)
- [Isaac Sim A100 support](https://forums.developer.nvidia.com/t/isaac-sim-a100/291492)
- [V100 support question](https://forums.developer.nvidia.com/t/can-i-launch-isaac-sim-with-tesla-v100/288953)
- [IsaacLab on Cloud GPUs](https://forums.developer.nvidia.com/t/isaaclab-on-cloud-gpus/330101)
- [G6e instance type issues](https://forums.developer.nvidia.com/t/g6e-instance-type/329680)
- [TURN server config broken in 5.0](https://forums.developer.nvidia.com/t/isaac-sim-5-0-0-unable-to-configure-turn-server-for-webrtc-tcp-only-setup-no-udp-allowed/347641)
- [Isaac Sim performance scaling](https://forums.developer.nvidia.com/t/isaac-lab-isaac-sim-how-does-performance-scale-with-cpu-gpu-improvements/346528)
- [Is streaming client deprecated?](https://forums.developer.nvidia.com/t/is-the-streaming-client-deprecated/305850)
- [Isaac Sim ThinLinc Azure guide](https://forums.developer.nvidia.com/t/guide-how-to-set-up-and-run-isaac-sim-on-azure-using-thinlinc-video-tutorial/360546)

### GitHub Issues and Discussions
- [WebRTC Streaming Client not work (Issue #219)](https://github.com/isaac-sim/IsaacSim/issues/219)
- [Multi-GPU livestream issue (Issue #348)](https://github.com/isaac-sim/IsaacSim/issues/348)
- [RTX 4090 vs L40 discussion](https://github.com/isaac-sim/IsaacLab/discussions/1310)
- [GPU performance comparison for RL (Issue #2761)](https://github.com/isaac-sim/IsaacLab/issues/2761)
- [LiveStream bug report (Issue #1399)](https://github.com/isaac-sim/IsaacLab/issues/1399)

### Blog Posts and Tutorials
- [AWS setup on non-supported instances (yasunori.jp)](https://yasunori.jp/en/2025/10/15/aws-isaacsim.html)
- [Cost-effective robotics simulation (mikelikesrobots)](https://mikelikesrobots.github.io/blog/ec2-spot-sims/)
- [WebRTC streaming over internet (Medium)](https://medium.com/@BeingOttoman/scalable-streaming-nvidia-omniverse-applications-over-the-internet-using-webrtc-8946a574fef2)
- [Isaac Sim study notes 2024 (jedyang)](https://jedyang.com/post/omniverse-isaac-sim-study-notes-2024/)
- [Isaac Lab + GR00T cloud guide (GitHub)](https://github.com/sunnyspot114514/isaaclab-groot-cloud-guide)
- [Running Isaac Sim on Run:ai (j3soon)](https://tutorial.j3soon.com/robotics/runai-isaac/)
- [Lambda Labs benchmarking repo](https://github.com/LambdaLabsML/isaac-sim-benchmarking)

### Official Documentation
- [Isaac Sim Cloud Deployment](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/install_cloud.html)
- [AWS Deployment](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/install_advanced_cloud_setup_aws.html)
- [Azure Deployment](https://docs.isaacsim.omniverse.nvidia.com/latest/installation/install_advanced_cloud_setup_azure.html)
- [GCP Deployment](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/install_advanced_cloud_setup_gcp.html)
- [Brev Deployment](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/install_advanced_cloud_setup_brev.html)
- [Isaac Sim Requirements](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/requirements.html)
- [Isaac Sim Benchmarks](https://docs.isaacsim.omniverse.nvidia.com/4.5.0/reference_material/benchmarks.html)
- [Remote Workstation Deployment](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/installation/install_advanced_remote_setup.html)
- [Livestream Clients](https://docs.isaacsim.omniverse.nvidia.com/latest/installation/manual_livestream_clients.html)
- [Isaac Automator (GitHub)](https://github.com/isaac-sim/IsaacAutomator)
- [Isaac Lab Cloud Installation](https://isaac-sim.github.io/IsaacLab/main/source/setup/installation/cloud_installation.html)
- [AAU Rover cloud setup](https://github.com/AAU-Space-Robotics/aau-rover-isaac-sim/issues/1)
