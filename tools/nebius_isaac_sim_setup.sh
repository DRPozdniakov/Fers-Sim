#!/bin/bash
# =============================================================================
# Nebius L40S + Isaac Sim 5.1.0 Setup Script
# =============================================================================
# Target: Nebius Cloud GPU 1x NVIDIA L40S (eu-north1, Finland)
# OS: Ubuntu 24.04 + CUDA 13.0 (driver 580.126)
# Isaac Sim: 5.1.0 (driver 580.65+ requirement MET)
# Remote: Sunshine + Moonlight (primary), WebRTC streaming (backup)
#
# USAGE:
#   sudo bash nebius_isaac_sim_setup.sh --diagnose
#   sudo bash nebius_isaac_sim_setup.sh
#   sudo reboot
#   sudo bash nebius_isaac_sim_setup.sh --post-reboot
# =============================================================================

set -euo pipefail

LOG_FILE="/var/log/isaac_sim_setup.log"
exec > >(tee -a "$LOG_FILE") 2>&1

ISAAC_SIM_VERSION="5.1.0"
ISAAC_SIM_IMAGE="nvcr.io/nvidia/isaac-sim:${ISAAC_SIM_VERSION}"
VM_USER="latoff"
VM_HOME="/home/$VM_USER"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"; }
warn() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1"; }
fail() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] FATAL: $1"; exit 1; }

version_gte() { printf '%s\n%s' "$2" "$1" | sort -V -C; }

# Get GPU BusID from nvidia-smi, convert hex to decimal for X server
get_gpu_busid() {
    local hex_id
    hex_id=$(nvidia-smi --query-gpu=pci.bus_id --format=csv,noheader | head -1)
    # Parse 00000000:8D:00.0 -> PCI:141:0:0
    local bus_hex dev_hex fn
    bus_hex=$(echo "$hex_id" | sed -n 's/.*:\([0-9A-Fa-f]\{2,\}\):\([0-9A-Fa-f]\{2,\}\)\.\([0-9]\)/\1/p')
    dev_hex=$(echo "$hex_id" | sed -n 's/.*:\([0-9A-Fa-f]\{2,\}\):\([0-9A-Fa-f]\{2,\}\)\.\([0-9]\)/\2/p')
    fn=$(echo "$hex_id" | sed -n 's/.*:\([0-9A-Fa-f]\{2,\}\):\([0-9A-Fa-f]\{2,\}\)\.\([0-9]\)/\3/p')
    printf "PCI:%d:%d:%s" "0x$bus_hex" "0x$dev_hex" "$fn"
}

PHASE="${1:-initial}"

# =============================================================================
# DIAGNOSE
# =============================================================================
if [[ "$PHASE" == "--diagnose" ]]; then
    log "=== SYSTEM DIAGNOSTIC ==="

    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)
    DRIVER=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)
    VRAM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader | head -1)
    log "GPU: $GPU_NAME | VRAM: $VRAM | Driver: $DRIVER"

    if echo "$GPU_NAME" | grep -qiE "L40S|L40|A40|RTX"; then
        log "RT Cores: YES"
    elif echo "$GPU_NAME" | grep -qiE "A100|H100|H200|V100"; then
        fail "RT Cores: NO — Isaac Sim will NOT work on $GPU_NAME"
    fi

    if version_gte "$DRIVER" "580.65"; then
        log "Driver OK for Isaac Sim 5.1.0 (need 580.65+, have $DRIVER)"
    else
        fail "Driver $DRIVER too old. Need 580.65+ for Isaac Sim 5.1.0"
    fi

    GPU_BUSID=$(get_gpu_busid)
    log "GPU BusID: $GPU_BUSID"

    RAM_TOTAL=$(free -h | awk '/Mem:/{print $2}')
    DISK_FREE=$(df -h / | awk 'NR==2{print $4}')
    log "RAM: $RAM_TOTAL | Disk free: $DISK_FREE"

    command -v docker &>/dev/null && log "Docker: $(docker --version)" || log "Docker: not installed (will install)"
    command -v vulkaninfo &>/dev/null && log "Vulkan: available" || log "Vulkan tools: not installed (will install)"

    PUBLIC_IP=$(curl -s --max-time 5 ifconfig.me 2>/dev/null || echo "no public IP")
    log "Public IP: $PUBLIC_IP"

    log "=== DIAGNOSTIC COMPLETE ==="
    exit 0
fi

# =============================================================================
# PHASE 1: Install everything
# =============================================================================
if [[ "$PHASE" == "initial" || "$PHASE" == "--resume" ]]; then

    log "=== PHASE 1: Installing everything ==="

    # ----- System update (skip on resume) -----
    if [[ "$PHASE" == "initial" ]]; then
        log "Updating packages..."
        apt-get update && apt-get upgrade -y
    else
        log "Resuming — skipping apt update/upgrade"
        apt-get update -y
    fi

    # ----- Essential packages (no xfce4-goodies — broken dep on Nebius) -----
    log "Installing essentials..."
    apt-get install -y \
        xfce4 dbus-x11 \
        vulkan-tools libvulkan1 \
        xorg x11-xserver-utils \
        curl wget git unzip \
        ca-certificates gnupg \
        libgl1 libegl1 libxkbcommon0 || {
        warn "Some packages failed. Trying without optional ones..."
        apt-get install -y xfce4 dbus-x11 xorg x11-xserver-utils curl wget
    }

    # ----- Fix Nebius headless-only drivers: .run installer userspace replacement -----
    #
    # PROBLEM: Nebius ships nvidia-driver-580-server (headless) which has CUDA but NO Vulkan.
    # The headless libGLX_nvidia.so exports vk_icdGetInstanceProcAddr but returns NULL
    # for vkCreateInstance — Vulkan implementation is stripped from the headless userspace.
    #
    # ROOT CAUSE (discovered 2026-04-03):
    # - libnvidia-gl-580-server .deb has full Vulkan libs BUT its libnvidia-glcore.so
    #   links against X server symbols (ErrorF, miCreateDefColormap, xf86ProcessOptions)
    #   that don't exist in headless userspace → Vulkan init fails silently
    # - .run extract + manual lib copy doesn't work either (same NULL return)
    # - The ONLY working fix: purge all nvidia apt packages, then use the .run installer
    #   with --no-kernel-modules to install FULL standalone userspace while keeping
    #   the working Nebius kernel module intact
    #
    # WHAT DOESN'T WORK (tried 2026-04-02/03):
    # - libnvidia-gl-580 (non-server) → dep conflicts with server packages
    # - libnvidia-gl-580-server → installs but glcore has X server deps, Vulkan NULL
    # - nvidia-driver-580 (full desktop) → dep conflicts
    # - .run extract + manual lib copy → same NULL vkCreateInstance
    # - .run --silent/--force → blocked by existing package detection
    # - Stubbing X symbols (ErrorF etc.) → dozens of deps, never-ending chain
    #
    # WHAT WORKS (confirmed 2026-04-03):
    # 1. Purge ALL nvidia apt packages (dpkg --force-all --purge)
    # 2. .run installer --no-kernel-modules --no-questions --ui=none
    # 3. This installs standalone userspace libs that don't depend on X server
    # 4. Kernel module stays intact (580.126.09 open module from Nebius)
    log "Fixing Vulkan drivers (Nebius headless workaround)..."

    DRIVER_VER=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)
    log "Kernel driver version: $DRIVER_VER"

    # Check if Vulkan already works
    if vulkaninfo --summary 2>&1 | grep -q "NVIDIA"; then
        log "Vulkan NVIDIA device already detected — skipping driver fix."
    else
        log "No NVIDIA Vulkan device. Replacing headless userspace with full .run installer..."

        # Step 1: Download .run installer (try tesla/ then XFree86/ URL)
        RUN_FILE="/tmp/nvidia-driver.run"
        RUN_DIR="/tmp/NVIDIA-Linux-x86_64-${DRIVER_VER}"
        DOWNLOADED=false

        for BASE_URL in \
            "https://us.download.nvidia.com/tesla/${DRIVER_VER}" \
            "https://download.nvidia.com/XFree86/Linux-x86_64/${DRIVER_VER}"; do
            RUN_URL="${BASE_URL}/NVIDIA-Linux-x86_64-${DRIVER_VER}.run"
            log "Downloading from $RUN_URL ..."
            if wget -q --show-progress -O "$RUN_FILE" "$RUN_URL" 2>/dev/null; then
                DOWNLOADED=true
                log "Downloaded .run installer."
                break
            fi
        done

        if [[ "$DOWNLOADED" != "true" ]]; then
            fail "Could not download .run installer for driver $DRIVER_VER"
        fi

        # Step 2: Extract the .run installer
        chmod +x "$RUN_FILE"
        bash "$RUN_FILE" --extract-only
        rm -f "$RUN_FILE"

        if [ ! -f "$RUN_DIR/nvidia-installer" ]; then
            fail ".run extract failed — nvidia-installer not found in $RUN_DIR"
        fi
        log ".run installer extracted to $RUN_DIR"

        # Step 3: Purge ALL nvidia apt packages (required — installer refuses otherwise)
        log "Purging nvidia apt packages (keeping kernel module)..."
        NVIDIA_PKGS=$(dpkg -l | grep -i nvidia | awk '{print $2}' || true)
        if [ -n "$NVIDIA_PKGS" ]; then
            # shellcheck disable=SC2086
            dpkg --force-all --purge $NVIDIA_PKGS 2>/dev/null || true
            log "Nvidia apt packages purged."
        else
            log "No nvidia apt packages to purge."
        fi

        # Step 4: Install userspace only (keep Nebius kernel module)
        log "Installing NVIDIA userspace via .run installer (--no-kernel-modules)..."
        if "$RUN_DIR/nvidia-installer" \
            --no-kernel-modules \
            --no-questions \
            --ui=none 2>&1 | tee -a "$LOG_FILE" | tail -5; then
            log ".run userspace install completed."
        else
            fail ".run installer failed. Check $LOG_FILE for details."
        fi

        # Step 5: Start nvidia-persistenced (purge removed it)
        if command -v nvidia-persistenced &>/dev/null; then
            nvidia-persistenced 2>/dev/null || true
            nvidia-smi -pm 1 2>/dev/null || true
            log "nvidia-persistenced started."
        fi

        # Step 6: Create stubs for optional binaries the container toolkit expects
        for stub in nvidia-imex nvidia-imex-ctl nvidia-fabricmanager nvidia-fabricmanager-ctl; do
            if [ ! -f "/usr/bin/$stub" ]; then
                touch "/usr/bin/$stub" && chmod +x "/usr/bin/$stub"
            fi
        done
        # Stub for libnvidia-nscq.so (NVSwitch fabric — not in .run, not needed)
        if [ ! -f "/usr/lib/x86_64-linux-gnu/libnvidia-nscq.so.${DRIVER_VER}" ]; then
            touch "/usr/lib/x86_64-linux-gnu/libnvidia-nscq.so.${DRIVER_VER}"
        fi

        ldconfig 2>/dev/null || true

        # Step 7: Verify Vulkan
        if vulkaninfo --summary 2>&1 | grep -q "NVIDIA"; then
            log "Vulkan: NVIDIA GPU detected!"
            vulkaninfo --summary 2>&1 | grep "deviceName" | head -1 | xargs | \
                while read -r line; do log "  $line"; done
        else
            warn "Vulkan: NVIDIA GPU NOT detected after .run install."
            warn "Debug: LD_DEBUG=libs vulkaninfo --summary 2>&1 | grep error"
            warn "Debug: nm -D /usr/lib/x86_64-linux-gnu/libGLX_nvidia.so.0 | grep vk_icd"
        fi

        # Cleanup
        rm -rf "$RUN_DIR"
    fi

    # ----- X server config -----
    log "Configuring X server..."
    GPU_BUSID=$(get_gpu_busid)
    log "GPU BusID: $GPU_BUSID"

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
    log "xorg.conf written."

    # ----- Docker -----
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

    # ----- NVIDIA Container Toolkit -----
    # NOTE: The nvidia package purge above removes container toolkit too.
    # We must reinstall it — use dpkg --force-all to bypass broken deps from purge.
    log "Installing NVIDIA Container Toolkit..."
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
        gpg --batch --yes --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
        sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' > /etc/apt/sources.list.d/nvidia-container-toolkit.list
    apt-get update
    # apt install may fail due to broken deps from purge — fall back to dpkg --force
    if ! apt-get install -y --allow-change-held-packages nvidia-container-toolkit 2>/dev/null; then
        log "apt install failed (expected after purge). Using dpkg --force..."
        cd /tmp
        apt-get download nvidia-container-toolkit nvidia-container-toolkit-base \
            libnvidia-container-tools libnvidia-container1 2>/dev/null || true
        dpkg --force-all -i nvidia-container-toolkit*.deb libnvidia-container*.deb 2>/dev/null || true
        rm -f /tmp/nvidia-container-toolkit*.deb /tmp/libnvidia-container*.deb
    fi
    nvidia-ctk runtime configure --runtime=docker
    systemctl restart docker
    log "NVIDIA Container Toolkit installed."

    usermod -aG docker "$VM_USER"

    # ----- Sunshine (remote desktop) -----
    log "Installing Sunshine..."
    apt-get install -y libfuse2t64 2>/dev/null || apt-get install -y libfuse2 2>/dev/null || true
    if ! command -v sunshine &>/dev/null; then
        INSTALLED=false
        for VARIANT in "sunshine-ubuntu-24.04-amd64.deb" "sunshine-ubuntu-22.04-amd64.deb"; do
            URL="https://github.com/LizardByte/Sunshine/releases/latest/download/${VARIANT}"
            log "Trying $VARIANT..."
            if curl -fsSL "$URL" -o /tmp/sunshine.deb 2>/dev/null; then
                if dpkg -i /tmp/sunshine.deb 2>/dev/null; then
                    INSTALLED=true
                    log "Sunshine installed from $VARIANT"
                    break
                fi
            fi
        done
        # Install missing Sunshine deps (miniupnpc, libminiupnpc17)
        if [[ "$INSTALLED" == "true" ]]; then
            apt-get install -y -f 2>/dev/null || {
                # Broken deps from nvidia purge may block apt -f. Force-install Sunshine deps.
                for dep in miniupnpc libminiupnpc17; do
                    if ! dpkg -l | grep -q "$dep"; then
                        apt-get download "$dep" 2>/dev/null && \
                            dpkg --force-all -i ${dep}*.deb 2>/dev/null && \
                            rm -f ${dep}*.deb || true
                    fi
                done
            }
        fi
        rm -f /tmp/sunshine.deb
        if [[ "$INSTALLED" == "false" ]]; then
            warn "Sunshine install failed. Install manually after setup."
        fi
    else
        log "Sunshine already installed."
    fi

    if command -v sunshine &>/dev/null; then
        setcap cap_sys_admin+p "$(readlink -f "$(which sunshine)")" 2>/dev/null || true
    fi

    # ----- LightDM display manager with autologin -----
    log "Configuring display manager with autologin..."
    apt-get install -y lightdm
    # Write main lightdm.conf (not just conf.d — some versions ignore conf.d)
    cat > /etc/lightdm/lightdm.conf << LIGHTDM_EOF
[Seat:*]
autologin-user=$VM_USER
autologin-user-timeout=0
user-session=xfce
LIGHTDM_EOF
    # Also write to conf.d for redundancy
    mkdir -p /etc/lightdm/lightdm.conf.d
    cp /etc/lightdm/lightdm.conf /etc/lightdm/lightdm.conf.d/50-autologin.conf

    # Add user to autologin group (required by some PAM configs)
    groupadd -f autologin
    usermod -aG autologin "$VM_USER"

    echo "/usr/sbin/lightdm" > /etc/X11/default-display-manager
    dpkg-reconfigure -f noninteractive lightdm 2>/dev/null || true

    # Set password for VM user (Nebius VMs use SSH keys only, no password set)
    echo "$VM_USER:isaac2026" | chpasswd
    log "Password set for $VM_USER (isaac2026)"

    # ----- Sunshine autostart for VM_USER -----
    AUTOSTART_DIR="$VM_HOME/.config/autostart"
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
    chown -R "$VM_USER":"$VM_USER" "$VM_HOME/.config"

    # ----- Create Isaac Sim directories -----
    ISAAC_HOME="$VM_HOME/isaac-sim"
    mkdir -p "$ISAAC_HOME"
    su - "$VM_USER" -c "mkdir -p ~/docker/isaac-sim/{cache/main,cache/computecache,config,data/documents,data/Kit,logs,pkg}"
    # Fix permissions — Docker with -u 0:0 writes as root, host user needs access too
    chmod -R 777 "$VM_HOME/docker/isaac-sim"

    # ----- Launch scripts -----
    # With libnvidia-gl-580-server installed on host, nvidia-container-toolkit
    # should auto-mount Vulkan libs into containers via NVIDIA_DRIVER_CAPABILITIES=all.
    cat > "$ISAAC_HOME/launch_gui.sh" << 'EOF'
#!/bin/bash
set -euo pipefail
echo "=== Isaac Sim 5.1.0 GUI ==="
export DISPLAY=${DISPLAY:-:0}
xhost +local:docker 2>/dev/null || true
echo "Starting... (first launch takes 10-15 min for shaders)"
docker run --name isaac-sim-gui \
    --entrypoint bash -it --gpus all -u 0:0 \
    -e "ACCEPT_EULA=Y" -e "PRIVACY_CONSENT=Y" \
    -e "NVIDIA_VISIBLE_DEVICES=all" \
    -e "NVIDIA_DRIVER_CAPABILITIES=graphics,compute,utility" \
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
    nvcr.io/nvidia/isaac-sim:5.1.0 \
    -c "./runapp.sh"
EOF

    cat > "$ISAAC_HOME/launch_webrtc.sh" << 'EOF'
#!/bin/bash
set -euo pipefail
PUBLIC_IP=$(curl -s ifconfig.me)
echo "=== Isaac Sim 5.1.0 WebRTC Streaming ==="
echo ""
echo "On your LOCAL machine, run:"
echo "  ssh -N -f -L 49100:localhost:49100 -L 8211:localhost:8211 latoff@$PUBLIC_IP"
echo ""
echo "Then open Chrome/Edge:"
echo "  http://127.0.0.1:8211/streaming/webrtc-client/?server=127.0.0.1"
echo ""
echo "Starting... (first launch takes 10-15 min)"
docker run --name isaac-sim-stream \
    --entrypoint bash -it --gpus all -u 0:0 \
    -e "ACCEPT_EULA=Y" -e "PRIVACY_CONSENT=Y" \
    -e "NVIDIA_VISIBLE_DEVICES=all" \
    -e "NVIDIA_DRIVER_CAPABILITIES=graphics,compute,utility" \
    -e "LIVESTREAM=2" \
    --rm --network=host \
    -v ~/docker/isaac-sim/cache/main:/isaac-sim/.cache:rw \
    -v ~/docker/isaac-sim/cache/computecache:/isaac-sim/.nv/ComputeCache:rw \
    -v ~/docker/isaac-sim/logs:/isaac-sim/.nvidia-omniverse/logs:rw \
    -v ~/docker/isaac-sim/config:/isaac-sim/.nvidia-omniverse/config:rw \
    -v ~/docker/isaac-sim/data:/isaac-sim/.local/share/ov/data:rw \
    -v ~/docker/isaac-sim/pkg:/isaac-sim/.local/share/ov/pkg:rw \
    nvcr.io/nvidia/isaac-sim:5.1.0 \
    -c "./runheadless.sh"
EOF

    cat > "$ISAAC_HOME/check_gpu.sh" << 'EOF'
#!/bin/bash
echo "=== GPU ===" && nvidia-smi
echo ""
echo "=== Vulkan ICD ===" && (ls -la /usr/share/vulkan/icd.d/nvidia_icd.json 2>/dev/null && echo "OK" || echo "MISSING — run: sudo apt-get install -y --allow-change-held-packages libnvidia-gl-580")
echo ""
echo "=== Vulkan ===" && (vulkaninfo --summary 2>/dev/null || echo "vulkaninfo not available or Vulkan broken")
echo ""
echo "=== Display ===" && echo "DISPLAY=${DISPLAY:-not set}" && (xdpyinfo -display :0 2>/dev/null | head -5 || echo "No X on :0")
echo ""
echo "=== Docker GPU ===" && (docker run --rm --gpus all nvidia/cuda:12.6.0-base-ubuntu22.04 nvidia-smi 2>/dev/null && echo "OK" || echo "FAILED")
echo ""
echo "=== Sunshine ===" && (pgrep -a sunshine 2>/dev/null || echo "Not running")
echo ""
echo "=== xorg.conf ===" && (head -3 /etc/X11/xorg.conf 2>/dev/null || echo "No xorg.conf")
echo ""
echo "=== NVIDIA GL libs ===" && (ldconfig -p | grep -c "nvidia" && echo "NVIDIA libs found" || echo "WARNING: No NVIDIA libs in ldconfig")
EOF

    # start.sh — simple desktop launcher (run from Moonlight terminal)
    cat > "$ISAAC_HOME/start.sh" << 'EOF'
#!/bin/bash
xhost +local:docker 2>/dev/null
docker rm -f isaac-sim-gui 2>/dev/null
echo "Starting Isaac Sim GUI... (first launch takes 10-15 min)"
docker run --name isaac-sim-gui \
    --entrypoint bash -it --gpus all -u 0:0 \
    -e "ACCEPT_EULA=Y" -e "PRIVACY_CONSENT=Y" \
    -e "NVIDIA_VISIBLE_DEVICES=all" \
    -e "NVIDIA_DRIVER_CAPABILITIES=graphics,compute,utility" \
    -e "DISPLAY=:0" \
    --rm --network=host \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -v ~/docker/isaac-sim/cache/main:/isaac-sim/.cache:rw \
    -v ~/docker/isaac-sim/cache/computecache:/isaac-sim/.nv/ComputeCache:rw \
    -v ~/docker/isaac-sim/logs:/isaac-sim/.nvidia-omniverse/logs:rw \
    -v ~/docker/isaac-sim/config:/isaac-sim/.nvidia-omniverse/config:rw \
    -v ~/docker/isaac-sim/data:/isaac-sim/.local/share/ov/data:rw \
    nvcr.io/nvidia/isaac-sim:5.1.0 \
    -c "./runapp.sh"
EOF

    chmod +x "$ISAAC_HOME"/*.sh
    chown -R "$VM_USER":"$VM_USER" "$ISAAC_HOME"
    chown -R "$VM_USER":"$VM_USER" "$VM_HOME/docker"

    # ----- Pull Isaac Sim Docker image -----
    log "Pulling Isaac Sim $ISAAC_SIM_VERSION Docker image (~20GB)..."
    log "This will take a few minutes..."
    docker pull "$ISAAC_SIM_IMAGE"
    if docker image inspect "$ISAAC_SIM_IMAGE" &>/dev/null; then
        log "Isaac Sim image ready."
    else
        warn "Pull may have failed. Run after reboot: docker pull $ISAAC_SIM_IMAGE"
    fi

    log ""
    log "============================================================"
    log " PHASE 1 COMPLETE — REBOOT NOW"
    log "============================================================"
    log "   sudo reboot"
    log "   # then: sudo bash nebius_isaac_sim_setup.sh --post-reboot"
    log "============================================================"
fi

# =============================================================================
# PHASE 2: Post-reboot verification
# =============================================================================
if [[ "$PHASE" == "--post-reboot" ]]; then

    log "=== PHASE 2: Post-reboot verification ==="

    # 1. GPU
    log "1/7 GPU..."
    nvidia-smi || fail "nvidia-smi failed"

    # 2. Vulkan ICD
    log "2/7 Vulkan ICD..."
    if [ -f /usr/share/vulkan/icd.d/nvidia_icd.json ]; then
        log "Vulkan ICD: present"
    else
        warn "Vulkan ICD MISSING — Isaac Sim will crash. Re-run Phase 1 or manually install libnvidia-gl-580."
    fi
    if vulkaninfo --summary &>/dev/null; then
        log "Vulkan: working ($(vulkaninfo --summary 2>&1 | grep 'deviceName' | head -1 | xargs))"
    else
        warn "vulkaninfo failed — Vulkan may not be functional yet (check after LightDM starts)."
    fi

    # 3. xorg.conf
    log "3/7 X config..."
    if [ -f /etc/X11/xorg.conf ]; then
        log "xorg.conf: exists"
    else
        warn "xorg.conf missing — recreating..."
        GPU_BUSID=$(get_gpu_busid)
        cat > /etc/X11/xorg.conf << XORG_EOF
Section "ServerLayout"
    Identifier "Layout0"
    Screen 0 "Screen0"
EndSection
Section "Device"
    Identifier "Device0"
    Driver "nvidia"
    BusID "$GPU_BUSID"
    Option "AllowEmptyInitialConfiguration" "True"
EndSection
Section "Monitor"
    Identifier "Monitor0"
    HorizSync 28.0-80.0
    VertRefresh 48.0-75.0
    Modeline "1920x1080_60" 148.50 1920 2008 2052 2200 1080 1084 1089 1125 +hsync +vsync
EndSection
Section "Screen"
    Identifier "Screen0"
    Device "Device0"
    Monitor "Monitor0"
    DefaultDepth 24
    Option "ConnectedMonitor" "DFP-0"
    Option "ModeValidation" "NoEdidModes"
    Option "MetaModes" "1920x1080_60"
    Option "AllowEmptyInitialConfiguration" "True"
    SubSection "Display"
        Depth 24
        Modes "1920x1080_60"
        Virtual 1920 1080
    EndSubSection
EndSection
XORG_EOF
    fi

    # 4. Display manager
    log "4/7 Display manager..."
    if systemctl is-active --quiet lightdm; then
        log "LightDM: running"
    else
        log "Starting LightDM..."
        systemctl start lightdm
        sleep 3
        systemctl is-active --quiet lightdm && log "LightDM: started" || warn "LightDM failed — check: journalctl -u lightdm -n 30"
    fi

    # 5. Docker NVIDIA
    log "5/7 Docker GPU..."
    if docker run --rm --gpus all nvidia/cuda:12.6.0-base-ubuntu22.04 nvidia-smi &>/dev/null; then
        log "Docker GPU: OK"
    else
        log "Reconfiguring Docker NVIDIA runtime..."
        nvidia-ctk runtime configure --runtime=docker
        systemctl restart docker
        sleep 2
        docker run --rm --gpus all nvidia/cuda:12.6.0-base-ubuntu22.04 nvidia-smi &>/dev/null && log "Docker GPU: OK after fix" || warn "Docker GPU: still failing"
    fi

    # 6. Isaac Sim image
    log "6/7 Isaac Sim image..."
    if docker image inspect "$ISAAC_SIM_IMAGE" &>/dev/null; then
        log "Isaac Sim: ready"
    else
        log "Pulling Isaac Sim..."
        docker pull "$ISAAC_SIM_IMAGE"
    fi

    # 7. Start Sunshine
    log "7/7 Starting Sunshine..."
    if command -v sunshine &>/dev/null; then
        # Set credentials via CLI
        sunshine --creds "$VM_USER" "isaac2026" 2>/dev/null || true
        log "Sunshine credentials set ($VM_USER / isaac2026)"

        # Wait for LightDM to create xauth
        sleep 3
        XAUTH_FILE="/var/run/lightdm/root/:0"
        if [ -f "$XAUTH_FILE" ]; then
            # Run as root with lightdm's xauth (most reliable on cloud VMs)
            DISPLAY=:0 XAUTHORITY="$XAUTH_FILE" nohup sunshine > /tmp/sunshine.log 2>&1 &
            sleep 3
            if pgrep sunshine > /dev/null; then
                # Check if encoder was found
                if grep -q "Trying encoder \[nvenc\]" /tmp/sunshine.log 2>/dev/null; then
                    log "Sunshine: running with NVENC encoder"
                else
                    log "Sunshine: running (check /tmp/sunshine.log for encoder status)"
                fi
            else
                warn "Sunshine: failed to start — check /tmp/sunshine.log"
            fi
        else
            warn "X auth not ready. Start Sunshine manually:"
            warn "  sudo DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 nohup sunshine > /tmp/sunshine.log 2>&1 &"
        fi
    else
        warn "Sunshine not installed. Install manually:"
        warn "  wget -O /tmp/sunshine.deb https://github.com/LizardByte/Sunshine/releases/latest/download/sunshine-ubuntu-24.04-amd64.deb"
        warn "  sudo dpkg -i /tmp/sunshine.deb && sudo apt-get install -f -y"
    fi

    PUBLIC_IP=$(curl -s --max-time 5 ifconfig.me 2>/dev/null || echo "<PUBLIC_IP>")

    log ""
    log "============================================================"
    log " SETUP COMPLETE"
    log "============================================================"
    log ""
    log " Server: $PUBLIC_IP"
    log " Desktop login: $VM_USER / isaac2026"
    log ""
    log " --- SUNSHINE + MOONLIGHT (full desktop) ---"
    log " 1. SSH tunnel:  ssh -L 47990:localhost:47990 latoff@$PUBLIC_IP"
    log " 2. Browser:     https://localhost:47990"
    log "    Credentials: $VM_USER / isaac2026"
    log " 3. Install Moonlight: https://moonlight-stream.org/"
    log " 4. Add host: $PUBLIC_IP, enter PIN in Sunshine web UI"
    log " 5. Connect → open terminal → ~/isaac-sim/launch_gui.sh"
    log ""
    log " --- WEBRTC (browser-only, no desktop) ---"
    log " 1. Server:  ~/isaac-sim/launch_webrtc.sh"
    log " 2. Local:   ssh -N -f -L 49100:localhost:49100 -L 8211:localhost:8211 latoff@$PUBLIC_IP"
    log " 3. Browser: http://127.0.0.1:8211/streaming/webrtc-client/?server=127.0.0.1"
    log ""
    log " --- DIAGNOSTICS ---"
    log "    ~/isaac-sim/check_gpu.sh"
    log "============================================================"
fi
