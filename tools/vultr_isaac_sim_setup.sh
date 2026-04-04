#!/bin/bash
# =============================================================================
# Vultr L40S + Isaac Sim Setup Script
# =============================================================================
# Target: Vultr Cloud GPU 1x NVIDIA L40S (passthrough, $1.67/hr)
# OS: Ubuntu 22.04 LTS
# Remote Desktop: Sunshine + Moonlight (Parsec has NO Linux host support)
# Simulation View: Isaac Sim WebRTC streaming (primary), Sunshine desktop (backup)
#
# USAGE:
#   1. Deploy Vultr Cloud GPU: 1x L40S, Ubuntu 22.04
#   2. SSH in: ssh root@<VULTR_IP>
#   3. Upload and run: bash vultr_isaac_sim_setup.sh
#   4. Reboot when prompted
#   5. After reboot: bash vultr_isaac_sim_setup.sh --post-reboot
#   6. Connect via Moonlight from your local machine
#
# WHAT THIS DOES NOT DO (untested territory - expect manual fixes):
#   - Vultr is NOT officially supported by NVIDIA for Isaac Sim
#   - No one has publicly documented this exact setup
#   - Virtual display on headless server can be finicky
#   - Driver version may need manual upgrade for Isaac Sim 5.1+
# =============================================================================

set -euo pipefail

LOG_FILE="/var/log/isaac_sim_setup.log"
exec > >(tee -a "$LOG_FILE") 2>&1

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# Start with 4.5.0 (needs driver 535+, Vultr ships ~550.x)
# Upgrade to 5.1.0 later (needs driver 580.65+)
ISAAC_SIM_VERSION="4.5.0"
ISAAC_SIM_IMAGE="nvcr.io/nvidia/isaac-sim:${ISAAC_SIM_VERSION}"
UBUNTU_USER="isaac"
MIN_DRIVER_VERSION_45="535.129"   # Minimum for Isaac Sim 4.5.0
MIN_DRIVER_VERSION_51="580.65"    # Minimum for Isaac Sim 5.1.0

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"; }
warn() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1"; }
fail() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] FATAL: $1"; exit 1; }

# ---------------------------------------------------------------------------
# Diagnostic: compare version strings (returns 0 if $1 >= $2)
# ---------------------------------------------------------------------------
version_gte() {
    printf '%s\n%s' "$2" "$1" | sort -V -C
}

# ---------------------------------------------------------------------------
# Phase detection
# ---------------------------------------------------------------------------
if [[ "${1:-}" == "--post-reboot" ]]; then
    PHASE="post-reboot"
elif [[ "${1:-}" == "--diagnose" ]]; then
    PHASE="diagnose"
else
    PHASE="initial"
fi

# =============================================================================
# DIAGNOSE: Run this first to check if the system is viable
# =============================================================================
if [[ "$PHASE" == "diagnose" ]]; then
    log "=== SYSTEM DIAGNOSTIC ==="
    echo ""

    # GPU check
    if command -v nvidia-smi &>/dev/null; then
        GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)
        DRIVER_VERSION=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)
        VRAM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader | head -1)
        log "GPU: $GPU_NAME"
        log "VRAM: $VRAM"
        log "Driver: $DRIVER_VERSION"

        # Check RT core support (L40S, A40 = good; A100, H100 = bad)
        if echo "$GPU_NAME" | grep -qiE "L40S|A40|RTX|L40"; then
            log "RT Cores: YES (Isaac Sim compatible)"
        elif echo "$GPU_NAME" | grep -qiE "A100|H100|V100"; then
            fail "RT Cores: NO ($GPU_NAME has no RT cores - Isaac Sim WILL NOT WORK)"
        else
            warn "RT Cores: UNKNOWN for $GPU_NAME - check manually"
        fi

        # Check driver version
        if version_gte "$DRIVER_VERSION" "$MIN_DRIVER_VERSION_45"; then
            log "Driver OK for Isaac Sim 4.5.0 (needs $MIN_DRIVER_VERSION_45+)"
        else
            warn "Driver $DRIVER_VERSION is BELOW minimum $MIN_DRIVER_VERSION_45 for Isaac Sim 4.5.0"
        fi

        if version_gte "$DRIVER_VERSION" "$MIN_DRIVER_VERSION_51"; then
            log "Driver OK for Isaac Sim 5.1.0 (needs $MIN_DRIVER_VERSION_51+)"
        else
            warn "Driver $DRIVER_VERSION is BELOW minimum $MIN_DRIVER_VERSION_51 for Isaac Sim 5.1.0"
            log "  -> Start with Isaac Sim 4.5.0, upgrade driver later for 5.1.0"
        fi
    else
        fail "nvidia-smi not found. NVIDIA drivers not installed."
    fi

    # Vulkan check
    if command -v vulkaninfo &>/dev/null; then
        VULKAN_VERSION=$(vulkaninfo --summary 2>/dev/null | grep "apiVersion" | head -1 || echo "unknown")
        log "Vulkan: $VULKAN_VERSION"
    else
        warn "vulkaninfo not found. Install: apt install vulkan-tools"
    fi

    # Docker check
    if command -v docker &>/dev/null; then
        log "Docker: $(docker --version)"
        if docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi &>/dev/null; then
            log "Docker NVIDIA runtime: OK"
        else
            warn "Docker NVIDIA runtime: FAILED"
        fi
    else
        log "Docker: not installed (will be installed by setup)"
    fi

    # Network
    PUBLIC_IP=$(curl -s --max-time 5 ifconfig.me 2>/dev/null || echo "unknown")
    log "Public IP: $PUBLIC_IP"

    # Disk
    DISK_FREE=$(df -h / | awk 'NR==2{print $4}')
    log "Disk free: $DISK_FREE (need ~50GB for Isaac Sim image)"

    # RAM
    RAM_TOTAL=$(free -h | awk '/Mem:/{print $2}')
    log "RAM: $RAM_TOTAL (need 32GB+, 64GB+ recommended)"

    echo ""
    log "=== DIAGNOSTIC COMPLETE ==="
    exit 0
fi

# =============================================================================
# PHASE 1: Initial Setup (before reboot)
# =============================================================================
if [[ "$PHASE" == "initial" ]]; then

    log "=== PHASE 1: Initial system setup ==="
    log "Run --diagnose first if you haven't already."
    echo ""

    # -----------------------------------------------------------------------
    # 1. System update
    # -----------------------------------------------------------------------
    log "Updating system packages..."
    apt-get update && apt-get upgrade -y

    # -----------------------------------------------------------------------
    # 2. Create non-root user
    # -----------------------------------------------------------------------
    log "Creating user: $UBUNTU_USER"
    if ! id "$UBUNTU_USER" &>/dev/null; then
        adduser --disabled-password --gecos "" "$UBUNTU_USER"
        usermod -aG sudo "$UBUNTU_USER"
        echo "$UBUNTU_USER ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/$UBUNTU_USER
        log "Set a password later: sudo passwd $UBUNTU_USER"
    else
        log "User $UBUNTU_USER already exists."
    fi

    # -----------------------------------------------------------------------
    # 3. Verify NVIDIA drivers
    # -----------------------------------------------------------------------
    log "Checking NVIDIA drivers..."
    if command -v nvidia-smi &>/dev/null; then
        nvidia-smi
        DRIVER_VERSION=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)
        log "NVIDIA driver: $DRIVER_VERSION"

        if ! version_gte "$DRIVER_VERSION" "$MIN_DRIVER_VERSION_45"; then
            fail "Driver $DRIVER_VERSION is too old for Isaac Sim 4.5.0 (need $MIN_DRIVER_VERSION_45+). Upgrade manually."
        fi
    else
        fail "nvidia-smi not found. Vultr GPU images should have drivers pre-installed. Check instance type."
    fi

    # -----------------------------------------------------------------------
    # 4. Install essential packages
    # -----------------------------------------------------------------------
    log "Installing essential packages..."
    apt-get install -y \
        xfce4 xfce4-goodies dbus-x11 \
        vulkan-tools libvulkan1 mesa-vulkan-drivers \
        xorg x11-xserver-utils \
        curl wget git unzip \
        ca-certificates gnupg \
        libgl1 libegl1 libxkbcommon0 \
        ufw

    # -----------------------------------------------------------------------
    # 5. Configure X server for NVIDIA GPU (headless virtual display)
    # -----------------------------------------------------------------------
    log "Configuring X server with virtual display..."
    mkdir -p /etc/X11/xorg.conf.d

    # Generate base config
    nvidia-xconfig --preserve-busid --enable-all-gpus

    # Get GPU BusID
    GPU_BUSID=$(nvidia-xconfig --query-gpu-info | grep "PCI BusID" | head -1 | sed 's/.*PCI BusID : //')
    log "GPU BusID: $GPU_BUSID"

    # Write xorg.conf that tricks GPU into thinking a monitor is attached
    cat > /etc/X11/xorg.conf << XORG_EOF
Section "ServerLayout"
    Identifier     "Layout0"
    Screen      0  "Screen0"
EndSection

Section "Device"
    Identifier     "Device0"
    Driver         "nvidia"
    BusID          "$GPU_BUSID"
    Option         "AllowEmptyInitialConfiguration" "True"
EndSection

Section "Monitor"
    Identifier     "Monitor0"
    HorizSync       28.0-80.0
    VertRefresh     48.0-75.0
    Option         "DPMS"
    Modeline       "1920x1080_60" 148.50 1920 2008 2052 2200 1080 1084 1089 1125 +hsync +vsync
EndSection

Section "Screen"
    Identifier     "Screen0"
    Device         "Device0"
    Monitor        "Monitor0"
    DefaultDepth    24
    Option         "ConnectedMonitor" "DFP-0"
    Option         "ModeValidation" "NoEdidModes"
    Option         "MetaModes" "1920x1080_60"
    Option         "AllowEmptyInitialConfiguration" "True"
    SubSection     "Display"
        Depth       24
        Modes      "1920x1080_60"
        Virtual     1920 1080
    EndSubSection
EndSection
XORG_EOF

    log "xorg.conf written with virtual display at 1920x1080."

    # -----------------------------------------------------------------------
    # 6. Install Docker + NVIDIA Container Toolkit
    # -----------------------------------------------------------------------
    log "Installing Docker..."
    if ! command -v docker &>/dev/null; then
        install -m 0755 -d /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        chmod a+r /etc/apt/keyrings/docker.gpg
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list
        apt-get update
        apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    else
        log "Docker already installed."
    fi

    log "Installing NVIDIA Container Toolkit..."
    if ! dpkg -l | grep -q nvidia-container-toolkit; then
        curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
        curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
            sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' > /etc/apt/sources.list.d/nvidia-container-toolkit.list
        apt-get update
        apt-get install -y nvidia-container-toolkit
        nvidia-ctk runtime configure --runtime=docker
        systemctl restart docker
    else
        log "NVIDIA Container Toolkit already installed."
    fi

    usermod -aG docker "$UBUNTU_USER"

    # -----------------------------------------------------------------------
    # 7. Install Sunshine (remote desktop host - Parsec has NO Linux hosting)
    # -----------------------------------------------------------------------
    log "Installing Sunshine (GPU-accelerated remote desktop)..."
    if ! command -v sunshine &>/dev/null; then
        # Sunshine from official release
        SUNSHINE_DEB="sunshine-ubuntu-22.04-amd64.deb"
        SUNSHINE_URL="https://github.com/LizardByte/Sunshine/releases/latest/download/${SUNSHINE_DEB}"
        curl -fsSL "$SUNSHINE_URL" -o /tmp/sunshine.deb || {
            warn "Failed to download latest Sunshine. Trying apt..."
            apt-get install -y sunshine 2>/dev/null || warn "Sunshine apt install failed. Install manually after reboot."
        }
        if [ -f /tmp/sunshine.deb ]; then
            dpkg -i /tmp/sunshine.deb || apt-get install -f -y
            rm -f /tmp/sunshine.deb
        fi
    else
        log "Sunshine already installed."
    fi

    # Give Sunshine permissions for KMS/DRM capture (best performance)
    if command -v sunshine &>/dev/null; then
        setcap cap_sys_admin+p $(readlink -f $(which sunshine)) 2>/dev/null || true
    fi

    # -----------------------------------------------------------------------
    # 8. Configure LightDM auto-login
    # -----------------------------------------------------------------------
    log "Configuring display manager with auto-login..."
    apt-get install -y lightdm
    mkdir -p /etc/lightdm/lightdm.conf.d
    cat > /etc/lightdm/lightdm.conf.d/50-autologin.conf << LIGHTDM_EOF
[Seat:*]
autologin-user=$UBUNTU_USER
autologin-user-timeout=0
user-session=xfce
LIGHTDM_EOF

    echo "/usr/sbin/lightdm" > /etc/X11/default-display-manager
    dpkg-reconfigure -f noninteractive lightdm 2>/dev/null || true

    # -----------------------------------------------------------------------
    # 9. Configure firewall
    # -----------------------------------------------------------------------
    log "Configuring firewall..."
    ufw allow 22/tcp        # SSH
    # Sunshine/Moonlight ports
    ufw allow 47984/tcp     # Sunshine HTTPS web UI
    ufw allow 47989/tcp     # Sunshine HTTPS API
    ufw allow 47990/tcp     # Sunshine RTSP
    ufw allow 48010/udp     # Sunshine video stream
    ufw allow 48010/tcp     # Sunshine video stream
    ufw allow 48012/udp     # Sunshine audio stream (optional)
    # Isaac Sim WebRTC ports
    ufw allow 49100/tcp     # WebRTC signaling
    ufw allow 47998/udp     # WebRTC media stream
    ufw allow 8211/tcp      # WebRTC web viewer
    echo "y" | ufw enable || true
    log "Firewall configured."

    # -----------------------------------------------------------------------
    # 10. Pre-pull Isaac Sim Docker image (background)
    # -----------------------------------------------------------------------
    log "Pre-pulling Isaac Sim Docker image: $ISAAC_SIM_IMAGE"
    log "This downloads ~15-20GB and takes a while..."
    docker pull "$ISAAC_SIM_IMAGE" &
    PULL_PID=$!

    # -----------------------------------------------------------------------
    # 11. Create launch scripts
    # -----------------------------------------------------------------------
    ISAAC_HOME="/home/$UBUNTU_USER/isaac-sim"
    mkdir -p "$ISAAC_HOME"

    su - "$UBUNTU_USER" -c "
        mkdir -p ~/docker/isaac-sim/{cache/main,cache/computecache,config,data/documents,data/Kit,logs,pkg}
    "

    # ---- Launch: Full GUI via Sunshine desktop ----
    cat > "$ISAAC_HOME/launch_gui.sh" << 'EOF'
#!/bin/bash
# Launch Isaac Sim with full native GUI inside the Sunshine remote desktop.
# Run this from a terminal WITHIN the Moonlight/Sunshine session.
set -euo pipefail

echo "=== Isaac Sim GUI Launch ==="
echo "Checking prerequisites..."

# Verify we have a display
if [ -z "${DISPLAY:-}" ]; then
    export DISPLAY=:0
    echo "Set DISPLAY=:0"
fi

# Allow Docker to access X display
xhost +local:docker 2>/dev/null || true

echo "Starting Isaac Sim 4.5.0 with full GUI..."
echo "First launch takes 10-15 minutes (shader compilation)."
echo ""

docker run --name isaac-sim-gui \
    --entrypoint bash -it --gpus all \
    -e "ACCEPT_EULA=Y" \
    -e "PRIVACY_CONSENT=Y" \
    --rm --network=host \
    -e DISPLAY=$DISPLAY \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -v $HOME/.Xauthority:/root/.Xauthority \
    -v ~/docker/isaac-sim/cache/main:/isaac-sim/.cache:rw \
    -v ~/docker/isaac-sim/cache/computecache:/isaac-sim/.nv/ComputeCache:rw \
    -v ~/docker/isaac-sim/logs:/isaac-sim/.nvidia-omniverse/logs:rw \
    -v ~/docker/isaac-sim/config:/isaac-sim/.nvidia-omniverse/config:rw \
    -v ~/docker/isaac-sim/data:/isaac-sim/.local/share/ov/data:rw \
    -v ~/docker/isaac-sim/pkg:/isaac-sim/.local/share/ov/pkg:rw \
    nvcr.io/nvidia/isaac-sim:4.5.0 \
    -c "./runapp.sh"
EOF

    # ---- Launch: WebRTC streaming (no desktop needed) ----
    cat > "$ISAAC_HOME/launch_webrtc.sh" << 'EOF'
#!/bin/bash
# Launch Isaac Sim headless with WebRTC streaming.
# This is the NVIDIA-recommended approach for cloud.
# You see and interact with the full GUI through your browser.
set -euo pipefail

PUBLIC_IP=$(curl -s ifconfig.me)

echo "=== Isaac Sim WebRTC Streaming ==="
echo ""
echo "RECOMMENDED: Use SSH tunnel for reliable connection:"
echo "  On your LOCAL machine run:"
echo "    ssh -N -f -L 49100:localhost:49100 -L 8211:localhost:8211 isaac@$PUBLIC_IP"
echo "  Then open in Chrome/Edge:"
echo "    http://127.0.0.1:8211/streaming/webrtc-client/?server=127.0.0.1"
echo ""
echo "ALTERNATIVE (may grey-screen due to NAT):"
echo "  http://$PUBLIC_IP:8211/streaming/webrtc-client/?server=$PUBLIC_IP"
echo ""
echo "Starting Isaac Sim... (first launch takes 10-15 min for shader compilation)"
echo ""

docker run --name isaac-sim-stream \
    --entrypoint bash -it --gpus all \
    -e "ACCEPT_EULA=Y" \
    -e "PRIVACY_CONSENT=Y" \
    -e "LIVESTREAM=2" \
    --rm --network=host \
    -v ~/docker/isaac-sim/cache/main:/isaac-sim/.cache:rw \
    -v ~/docker/isaac-sim/cache/computecache:/isaac-sim/.nv/ComputeCache:rw \
    -v ~/docker/isaac-sim/logs:/isaac-sim/.nvidia-omniverse/logs:rw \
    -v ~/docker/isaac-sim/config:/isaac-sim/.nvidia-omniverse/config:rw \
    -v ~/docker/isaac-sim/data:/isaac-sim/.local/share/ov/data:rw \
    -v ~/docker/isaac-sim/pkg:/isaac-sim/.local/share/ov/pkg:rw \
    nvcr.io/nvidia/isaac-sim:4.5.0 \
    -c "./runheadless.webrtc.sh"
EOF

    # ---- Diagnostic script ----
    cat > "$ISAAC_HOME/check_gpu.sh" << 'EOF'
#!/bin/bash
# Quick GPU and display diagnostic
echo "=== GPU Status ==="
nvidia-smi

echo ""
echo "=== Vulkan Support ==="
vulkaninfo --summary 2>/dev/null || echo "vulkaninfo not available"

echo ""
echo "=== Display ==="
echo "DISPLAY=$DISPLAY"
xdpyinfo -display :0 2>/dev/null | head -5 || echo "No X display on :0"

echo ""
echo "=== Docker NVIDIA ==="
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi 2>/dev/null && echo "Docker GPU: OK" || echo "Docker GPU: FAILED"

echo ""
echo "=== Sunshine Status ==="
systemctl is-active sunshine 2>/dev/null || echo "Sunshine not running as service"
pgrep -a sunshine 2>/dev/null || echo "No sunshine process found"
EOF

    chmod +x "$ISAAC_HOME"/*.sh
    chown -R "$UBUNTU_USER":"$UBUNTU_USER" "$ISAAC_HOME"
    chown -R "$UBUNTU_USER":"$UBUNTU_USER" "/home/$UBUNTU_USER/docker"

    # -----------------------------------------------------------------------
    # 12. Create Sunshine autostart for the isaac user
    # -----------------------------------------------------------------------
    AUTOSTART_DIR="/home/$UBUNTU_USER/.config/autostart"
    mkdir -p "$AUTOSTART_DIR"
    cat > "$AUTOSTART_DIR/sunshine.desktop" << 'DESKTOP_EOF'
[Desktop Entry]
Type=Application
Name=Sunshine
Exec=sunshine
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
DESKTOP_EOF
    chown -R "$UBUNTU_USER":"$UBUNTU_USER" "/home/$UBUNTU_USER/.config"

    # -----------------------------------------------------------------------
    # Wait for Docker pull
    # -----------------------------------------------------------------------
    log "Waiting for Isaac Sim Docker image pull..."
    if wait $PULL_PID; then
        log "Isaac Sim image pulled successfully."
    else
        warn "Docker pull may have failed. After reboot run: docker pull $ISAAC_SIM_IMAGE"
    fi

    # -----------------------------------------------------------------------
    # Done Phase 1
    # -----------------------------------------------------------------------
    log ""
    log "============================================================"
    log " PHASE 1 COMPLETE - REBOOT REQUIRED"
    log "============================================================"
    log ""
    log " After reboot, run:"
    log "   bash vultr_isaac_sim_setup.sh --post-reboot"
    log ""
    log " Then set a password for the user:"
    log "   sudo passwd $UBUNTU_USER"
    log "============================================================"
    echo ""
    read -p "Reboot now? (y/n): " REBOOT_CHOICE
    if [[ "$REBOOT_CHOICE" == "y" ]]; then
        reboot
    fi

fi

# =============================================================================
# PHASE 2: Post-reboot verification and final setup
# =============================================================================
if [[ "$PHASE" == "post-reboot" ]]; then

    log "=== PHASE 2: Post-reboot verification ==="

    # -----------------------------------------------------------------------
    # 1. Verify GPU
    # -----------------------------------------------------------------------
    log "Step 1/6: Verifying GPU..."
    nvidia-smi || fail "nvidia-smi failed after reboot"
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)
    DRIVER_VERSION=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)
    log "GPU: $GPU_NAME, Driver: $DRIVER_VERSION"

    # -----------------------------------------------------------------------
    # 2. Verify display manager
    # -----------------------------------------------------------------------
    log "Step 2/6: Checking display manager..."
    if systemctl is-active --quiet lightdm; then
        log "LightDM: running"
    else
        log "Starting LightDM..."
        systemctl start lightdm
        sleep 3
        if systemctl is-active --quiet lightdm; then
            log "LightDM: started OK"
        else
            warn "LightDM failed to start. Check: journalctl -u lightdm"
            warn "This may mean xorg.conf needs adjustment. Check /var/log/Xorg.0.log"
        fi
    fi

    # -----------------------------------------------------------------------
    # 3. Verify Vulkan
    # -----------------------------------------------------------------------
    log "Step 3/6: Checking Vulkan support..."
    if command -v vulkaninfo &>/dev/null; then
        if vulkaninfo --summary &>/dev/null; then
            log "Vulkan: OK"
        else
            warn "Vulkan check failed. Isaac Sim needs Vulkan. Check GPU drivers."
        fi
    else
        warn "vulkaninfo not found. Install with: apt install vulkan-tools"
    fi

    # -----------------------------------------------------------------------
    # 4. Verify Docker NVIDIA runtime
    # -----------------------------------------------------------------------
    log "Step 4/6: Testing Docker NVIDIA runtime..."
    if docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi &>/dev/null; then
        log "Docker NVIDIA runtime: OK"
    else
        warn "Docker NVIDIA runtime failed. Run: nvidia-ctk runtime configure --runtime=docker && systemctl restart docker"
    fi

    # -----------------------------------------------------------------------
    # 5. Verify Isaac Sim image
    # -----------------------------------------------------------------------
    log "Step 5/6: Checking Isaac Sim Docker image..."
    if docker image inspect "$ISAAC_SIM_IMAGE" &>/dev/null; then
        log "Isaac Sim image: present"
    else
        log "Isaac Sim image not found. Pulling now..."
        docker pull "$ISAAC_SIM_IMAGE"
    fi

    # -----------------------------------------------------------------------
    # 6. Start Sunshine
    # -----------------------------------------------------------------------
    log "Step 6/6: Starting Sunshine remote desktop..."
    # Sunshine needs to run as the desktop user
    su - "$UBUNTU_USER" -c "
        export DISPLAY=:0
        xhost +local: 2>/dev/null || true
        nohup sunshine > /tmp/sunshine.log 2>&1 &
        sleep 2
        if pgrep -u $UBUNTU_USER sunshine > /dev/null; then
            echo 'Sunshine: running'
        else
            echo 'Sunshine: failed to start. Check /tmp/sunshine.log'
        fi
    "

    # -----------------------------------------------------------------------
    # Final instructions
    # -----------------------------------------------------------------------
    PUBLIC_IP=$(curl -s --max-time 5 ifconfig.me 2>/dev/null || echo "<VULTR_IP>")

    log ""
    log "============================================================"
    log " SETUP COMPLETE"
    log "============================================================"
    log ""
    log " Server: $PUBLIC_IP"
    log " User:   $UBUNTU_USER"
    log ""
    log " --- METHOD 1: Sunshine + Moonlight (full desktop) ---"
    log ""
    log " 1. Set Sunshine password (first time only):"
    log "      SSH tunnel: ssh -L 47984:localhost:47984 root@$PUBLIC_IP"
    log "      Open: https://localhost:47984"
    log "      Create username/password in the Sunshine web UI"
    log ""
    log " 2. Install Moonlight on your PC:"
    log "      https://moonlight-stream.org/"
    log ""
    log " 3. In Moonlight, add host: $PUBLIC_IP"
    log "      Enter the PIN shown in Moonlight into Sunshine web UI"
    log ""
    log " 4. Connect - you get the full XFCE desktop"
    log "      Open terminal and run: ~/isaac-sim/launch_gui.sh"
    log ""
    log " --- METHOD 2: WebRTC streaming (no desktop needed) ---"
    log ""
    log " 1. Start the stream on the server:"
    log "      ssh isaac@$PUBLIC_IP"
    log "      ~/isaac-sim/launch_webrtc.sh"
    log ""
    log " 2. Create SSH tunnel on your LOCAL machine:"
    log "      ssh -N -f -L 49100:localhost:49100 -L 8211:localhost:8211 isaac@$PUBLIC_IP"
    log ""
    log " 3. Open Chrome/Edge:"
    log "      http://127.0.0.1:8211/streaming/webrtc-client/?server=127.0.0.1"
    log ""
    log " --- DIAGNOSTICS ---"
    log "      ~/isaac-sim/check_gpu.sh"
    log "      journalctl -u lightdm  (display manager logs)"
    log "      cat /var/log/Xorg.0.log (X server logs)"
    log "      cat /tmp/sunshine.log   (Sunshine logs)"
    log "============================================================"

fi
