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
#   sudo bash nebius_isaac_sim_setup.sh          # Phase 1: install everything
#   sudo reboot
#   sudo bash nebius_isaac_sim_setup.sh --post-reboot  # Phase 2: Vulkan fix + verify
#
# ARCHITECTURE:
#   Phase 1 installs all software WHILE apt still works (before nvidia purge).
#   Phase 2 does the nvidia surgery AFTER reboot (kernel module loaded, never reboot again).
# =============================================================================

set -euo pipefail

LOG_FILE="/var/log/isaac_sim_setup.log"
exec > >(tee -a "$LOG_FILE") 2>&1

ISAAC_SIM_VERSION="5.1.0"
ISAAC_SIM_IMAGE="nvcr.io/nvidia/isaac-sim:${ISAAC_SIM_VERSION}"
VM_USER="${ISAAC_USER:-$(logname 2>/dev/null || echo "${SUDO_USER:-latoff}")}"
VM_HOME="/home/$VM_USER"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"; }
warn() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1"; }
fail() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] FATAL: $1"; exit 1; }

version_gte() { printf '%s\n%s' "$2" "$1" | sort -V -C; }

get_gpu_busid() {
    local hex_id
    hex_id=$(nvidia-smi --query-gpu=pci.bus_id --format=csv,noheader | head -1)
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

    if ! nvidia-smi &>/dev/null; then
        fail "nvidia-smi failed. NVIDIA driver not loaded. VM may need recreation."
    fi

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
# PHASE 1: Install all software (BEFORE nvidia purge — apt still works)
# =============================================================================
if [[ "$PHASE" == "initial" || "$PHASE" == "--resume" ]]; then

    log "=== PHASE 1: Installing software (apt still clean) ==="

    log "Updating packages..."
    apt-get update -y
    if [[ "$PHASE" == "initial" ]]; then
        # Hold ALL nvidia packages during upgrade — apt-get upgrade can break
        # the kernel module on Nebius custom kernels (6.11.0-*-nvidia) where
        # headers are unavailable for DKMS rebuild. After reboot: nvidia-smi fails.
        log "Holding nvidia packages to protect kernel module..."
        dpkg -l | grep -i nvidia | awk '{print $2}' | xargs -r apt-mark hold 2>/dev/null || true
        apt-get upgrade -y || true
        # Unhold — Phase 2 needs to purge userspace packages later
        dpkg -l | grep -i nvidia | awk '{print $2}' | xargs -r apt-mark unhold 2>/dev/null || true
    fi

    # ----- Essential packages -----
    log "Installing essentials..."
    apt-get install -y \
        xfce4 xfce4-terminal dbus-x11 \
        vulkan-tools libvulkan1 \
        xorg x11-xserver-utils \
        curl wget git unzip \
        ca-certificates gnupg \
        libgl1 libegl1 libxkbcommon0 \
        lightdm || {
        warn "Some packages failed. Trying minimal set..."
        apt-get install -y xfce4 dbus-x11 xorg x11-xserver-utils curl wget lightdm || true
    }

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
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
            gpg --batch --yes --dearmor -o /etc/apt/keyrings/docker.gpg
        chmod a+r /etc/apt/keyrings/docker.gpg
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list
        apt-get update
        apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    else
        log "Docker already installed."
    fi
    usermod -aG docker "$VM_USER"

    # ----- NVIDIA Container Toolkit (install while apt works) -----
    log "Installing NVIDIA Container Toolkit..."
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
        gpg --batch --yes --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
        sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' > /etc/apt/sources.list.d/nvidia-container-toolkit.list
    apt-get update
    apt-get install -y nvidia-container-toolkit
    nvidia-ctk runtime configure --runtime=docker
    systemctl restart docker
    log "NVIDIA Container Toolkit installed."

    # ----- Sunshine (remote desktop) -----
    log "Installing Sunshine..."
    apt-get install -y libfuse2t64 miniupnpc libminiupnpc17 2>/dev/null || \
        apt-get install -y libfuse2 2>/dev/null || true
    if ! command -v sunshine &>/dev/null; then
        for VARIANT in "sunshine-ubuntu-24.04-amd64.deb" "sunshine-ubuntu-22.04-amd64.deb"; do
            URL="https://github.com/LizardByte/Sunshine/releases/latest/download/${VARIANT}"
            log "Trying $VARIANT..."
            if curl -fsSL "$URL" -o /tmp/sunshine.deb 2>/dev/null; then
                if dpkg -i /tmp/sunshine.deb 2>/dev/null; then
                    apt-get install -y -f 2>/dev/null || true
                    log "Sunshine installed from $VARIANT"
                    break
                fi
            fi
        done
        rm -f /tmp/sunshine.deb
    else
        log "Sunshine already installed."
    fi
    command -v sunshine &>/dev/null && \
        setcap cap_sys_admin+p "$(readlink -f "$(which sunshine)")" 2>/dev/null || true

    # ----- LightDM with autologin -----
    log "Configuring LightDM autologin..."
    cat > /etc/lightdm/lightdm.conf << LIGHTDM_EOF
[Seat:*]
autologin-user=$VM_USER
autologin-user-timeout=0
user-session=xfce
LIGHTDM_EOF
    mkdir -p /etc/lightdm/lightdm.conf.d
    cp /etc/lightdm/lightdm.conf /etc/lightdm/lightdm.conf.d/50-autologin.conf
    groupadd -f autologin
    usermod -aG autologin "$VM_USER"
    echo "/usr/sbin/lightdm" > /etc/X11/default-display-manager
    dpkg-reconfigure -f noninteractive lightdm 2>/dev/null || true
    echo "$VM_USER:isaac2026" | chpasswd
    log "LightDM configured. Password set for $VM_USER."

    # ----- Sunshine autostart (via systemd, needs root for NvFBC) -----
    cat > /etc/systemd/system/sunshine.service << 'SYSTEMD_EOF'
[Unit]
Description=Sunshine Remote Desktop
After=lightdm.service
Requires=lightdm.service

[Service]
Type=simple
Environment=DISPLAY=:0
Environment=XAUTHORITY=/var/run/lightdm/root/:0
ExecStartPre=/bin/sleep 5
ExecStart=/usr/bin/sunshine
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical.target
SYSTEMD_EOF
    systemctl daemon-reload
    systemctl enable sunshine.service 2>/dev/null || true

    # ----- Isaac Sim directories + launch scripts -----
    ISAAC_HOME="$VM_HOME/isaac-sim"
    mkdir -p "$ISAAC_HOME"
    su - "$VM_USER" -c "mkdir -p ~/docker/isaac-sim/{cache/main,cache/computecache,config,data/documents,data/Kit,logs,pkg}"
    chmod -R 777 "$VM_HOME/docker/isaac-sim"

    cat > "$ISAAC_HOME/start.sh" << 'EOF'
#!/bin/bash
xhost +local:docker 2>/dev/null
docker rm -f isaac-sim-gui 2>/dev/null
echo "Starting Isaac Sim GUI... (first launch takes 10-15 min)"
docker run --name isaac-sim-gui --gpus all \
    -e ACCEPT_EULA=Y -e PRIVACY_CONSENT=Y \
    -e NVIDIA_VISIBLE_DEVICES=all \
    -e NVIDIA_DRIVER_CAPABILITIES=graphics,compute,utility \
    -e DISPLAY=:0 \
    --rm --network=host \
    --entrypoint /isaac-sim/runapp.sh \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -v ~/docker/isaac-sim/cache/main:/isaac-sim/.cache:rw \
    -v ~/docker/isaac-sim/cache/computecache:/isaac-sim/.nv/ComputeCache:rw \
    -v ~/docker/isaac-sim/logs:/isaac-sim/.nvidia-omniverse/logs:rw \
    -v ~/docker/isaac-sim/config:/isaac-sim/.nvidia-omniverse/config:rw \
    -v ~/docker/isaac-sim/data:/isaac-sim/.local/share/ov/data:rw \
    -v ~/simulation:/isaac-sim/simulation:ro \
    nvcr.io/nvidia/isaac-sim:5.1.0
EOF

    cat > "$ISAAC_HOME/launch_webrtc.sh" << 'EOF'
#!/bin/bash
set -euo pipefail
PUBLIC_IP=$(curl -s ifconfig.me)
echo "=== Isaac Sim 5.1.0 WebRTC Streaming ==="
echo ""
echo "On your LOCAL machine, run:"
echo "  ssh -N -f -L 49100:localhost:49100 -L 8211:localhost:8211 \$USER@$PUBLIC_IP"
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
    nvcr.io/nvidia/isaac-sim:5.1.0 \
    -c "./runheadless.sh"
EOF

    cat > "$ISAAC_HOME/check_gpu.sh" << 'EOF'
#!/bin/bash
echo "=== GPU ===" && nvidia-smi
echo ""
echo "=== Vulkan ===" && (vulkaninfo --summary 2>&1 | grep -A5 "GPU" || echo "Vulkan broken")
echo ""
echo "=== Display ===" && echo "DISPLAY=${DISPLAY:-not set}" && (xdpyinfo -display :0 2>/dev/null | head -5 || echo "No X on :0")
echo ""
echo "=== Docker GPU ===" && (docker run --rm --gpus all -e NVIDIA_DRIVER_CAPABILITIES=graphics,compute,utility nvidia/cuda:12.6.0-base-ubuntu22.04 nvidia-smi 2>/dev/null && echo "OK" || echo "FAILED")
echo ""
echo "=== Sunshine ===" && (pgrep -a sunshine 2>/dev/null || echo "Not running")
EOF

    chmod +x "$ISAAC_HOME"/*.sh
    chown -R "$VM_USER":"$VM_USER" "$ISAAC_HOME"
    chown -R "$VM_USER":"$VM_USER" "$VM_HOME/docker"

    # ----- Pre-download .run installer for Phase 2 -----
    DRIVER_VER=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)
    RUN_FILE="/tmp/nvidia-driver.run"
    log "Pre-downloading NVIDIA .run installer for Phase 2..."
    for BASE_URL in \
        "https://us.download.nvidia.com/tesla/${DRIVER_VER}" \
        "https://download.nvidia.com/XFree86/Linux-x86_64/${DRIVER_VER}"; do
        RUN_URL="${BASE_URL}/NVIDIA-Linux-x86_64-${DRIVER_VER}.run"
        if wget -q --show-progress -O "$RUN_FILE" "$RUN_URL" 2>/dev/null; then
            log "Downloaded .run installer ($DRIVER_VER)."
            break
        fi
    done

    # ----- Pull Isaac Sim Docker image -----
    log "Pulling Isaac Sim $ISAAC_SIM_VERSION Docker image (~20GB)..."
    docker pull "$ISAAC_SIM_IMAGE"
    docker image inspect "$ISAAC_SIM_IMAGE" &>/dev/null && \
        log "Isaac Sim image ready." || \
        warn "Pull may have failed. Run after reboot: docker pull $ISAAC_SIM_IMAGE"

    log ""
    log "============================================================"
    log " PHASE 1 COMPLETE — REBOOT NOW"
    log "============================================================"
    log "   sudo reboot"
    log "   # then: sudo bash nebius_isaac_sim_setup.sh --post-reboot"
    log "============================================================"
fi

# =============================================================================
# PHASE 2: Vulkan fix + start services (AFTER reboot — never reboot again)
# =============================================================================
# WHY Phase 2: The nvidia purge removes kernel module packages. If we reboot
# after purge, nvidia-smi fails. By doing the purge AFTER the last reboot,
# the kernel module stays loaded in memory and everything works.
# =============================================================================
if [[ "$PHASE" == "--post-reboot" ]]; then

    log "=== PHASE 2: Vulkan fix + services ==="

    # 1. Verify GPU is alive
    log "1/6 Verifying GPU..."
    nvidia-smi || fail "nvidia-smi failed. GPU not available."
    DRIVER_VER=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)
    log "GPU OK. Driver: $DRIVER_VER"

    # 2. Fix Vulkan (the main event)
    log "2/6 Fixing Vulkan..."
    if vulkaninfo --summary 2>&1 | grep -q "NVIDIA"; then
        log "Vulkan already working — skipping."
    else
        log "Vulkan broken. Replacing headless userspace with .run installer..."
        # Nebius ships headless NVIDIA drivers — CUDA only, no Vulkan.
        # Fix: purge userspace apt packages → .run installer --no-kernel-modules
        # The .run installer's libs are standalone (no X server deps).
        # Kernel module stays loaded in memory — DO NOT REBOOT after this.

        # 2a. Get .run installer (pre-downloaded in Phase 1, or re-download)
        RUN_FILE="/tmp/nvidia-driver.run"
        RUN_DIR="/tmp/NVIDIA-Linux-x86_64-${DRIVER_VER}"
        if [ ! -f "$RUN_FILE" ]; then
            log "Re-downloading .run installer..."
            for BASE_URL in \
                "https://us.download.nvidia.com/tesla/${DRIVER_VER}" \
                "https://download.nvidia.com/XFree86/Linux-x86_64/${DRIVER_VER}"; do
                RUN_URL="${BASE_URL}/NVIDIA-Linux-x86_64-${DRIVER_VER}.run"
                wget -q --show-progress -O "$RUN_FILE" "$RUN_URL" 2>/dev/null && break
            done
        fi
        [ -f "$RUN_FILE" ] || fail "Could not get .run installer"

        # 2b. Extract
        chmod +x "$RUN_FILE"
        cd /tmp && bash "$RUN_FILE" --extract-only
        rm -f "$RUN_FILE"
        [ -f "$RUN_DIR/nvidia-installer" ] || fail ".run extract failed"
        log ".run extracted."

        # 2c. Stop X before install (.run installer fails if X is running)
        systemctl stop lightdm 2>/dev/null || true
        killall Xorg 2>/dev/null || true
        sleep 2

        # 2d. Backup kernel modules before purge
        #     Purge removes module files from disk, but module stays loaded in memory.
        #     We restore them after install so VM can survive reboots.
        log "Backing up kernel modules..."
        KVER=$(uname -r)
        KMOD_BACKUP="/tmp/nvidia-kmod-backup"
        rm -rf "$KMOD_BACKUP"
        mkdir -p "$KMOD_BACKUP"
        find /lib/modules/"$KVER" -name "nvidia*" -exec cp -a {} "$KMOD_BACKUP/" \; 2>/dev/null || true
        log "Backed up $(ls "$KMOD_BACKUP" 2>/dev/null | wc -l) kernel module files."

        # 2e. Purge ALL nvidia packages
        #     The .run installer refuses to install if ANY nvidia apt packages remain
        #     ("alternate driver installation detected"). Must purge everything.
        #     Kernel module stays loaded in memory — DO NOT reboot between purge and restore.
        log "Purging ALL nvidia packages..."
        NVIDIA_PKGS=$(dpkg -l | grep -i nvidia | awk '{print $2}' || true)
        if [ -n "$NVIDIA_PKGS" ]; then
            # shellcheck disable=SC2086
            dpkg --force-all --purge $NVIDIA_PKGS 2>/dev/null || true
        fi
        # Clean up broken apt state from purge
        dpkg --configure -a 2>/dev/null || true
        log "All nvidia packages purged."

        # 2f. Install full userspace via .run (kernel module stays in memory)
        log "Installing NVIDIA userspace..."
        "$RUN_DIR/nvidia-installer" \
            --no-kernel-modules \
            --no-questions \
            --ui=none 2>&1 | tee -a "$LOG_FILE" | tail -5
        log ".run install completed."

        # 2g. Restore kernel modules for reboot resilience
        log "Restoring kernel modules..."
        for kmod_dir in "/lib/modules/$KVER/updates/dkms" "/lib/modules/$KVER/kernel/drivers/video"; do
            mkdir -p "$kmod_dir"
            cp -a "$KMOD_BACKUP"/nvidia* "$kmod_dir/" 2>/dev/null || true
        done
        depmod -a 2>/dev/null || true
        rm -rf "$KMOD_BACKUP"
        log "Kernel modules restored."

        # 2h. Stubs for container toolkit (optional binaries removed by purge)
        for stub in nvidia-imex nvidia-imex-ctl nvidia-fabricmanager nvidia-fabricmanager-ctl; do
            [ -f "/usr/bin/$stub" ] || { touch "/usr/bin/$stub" && chmod +x "/usr/bin/$stub"; }
        done
        [ -f "/usr/lib/x86_64-linux-gnu/libnvidia-nscq.so.${DRIVER_VER}" ] || \
            touch "/usr/lib/x86_64-linux-gnu/libnvidia-nscq.so.${DRIVER_VER}"

        # 2i. Restore services
        nvidia-persistenced 2>/dev/null || true
        nvidia-smi -pm 1 2>/dev/null || true
        ldconfig 2>/dev/null || true

        # 2j. Reinstall container toolkit (purge removed it)
        log "Reinstalling NVIDIA Container Toolkit..."
        cd /tmp
        apt-get update 2>/dev/null || true
        apt-get download nvidia-container-toolkit nvidia-container-toolkit-base \
            libnvidia-container-tools libnvidia-container1 2>/dev/null || true
        dpkg --force-all -i nvidia-container-toolkit*.deb libnvidia-container*.deb 2>/dev/null || true
        rm -f /tmp/nvidia-container-toolkit*.deb /tmp/libnvidia-container*.deb
        nvidia-ctk runtime configure --runtime=docker
        systemctl restart docker

        # Cleanup
        rm -rf "$RUN_DIR"

        # 2i. Verify
        if vulkaninfo --summary 2>&1 | grep -q "NVIDIA"; then
            log "Vulkan: NVIDIA GPU detected!"
        else
            warn "Vulkan still broken. Debug: LD_DEBUG=libs vulkaninfo --summary 2>&1 | grep error"
        fi
    fi

    # 3. Start LightDM and wait for desktop session
    log "3/6 Starting display manager..."
    systemctl start lightdm
    # Wait for X session to fully initialize (prevents NvFBC "modeset" errors)
    for i in $(seq 1 15); do
        if DISPLAY=:0 xdpyinfo &>/dev/null; then
            log "LightDM: running, X display :0 ready"
            break
        fi
        sleep 1
    done
    systemctl is-active --quiet lightdm || warn "LightDM failed to start"

    # 4. Docker GPU test (use --network=host — bridge networking broken after purge)
    log "4/6 Docker GPU..."
    if docker run --rm --network=host --gpus all \
        -e NVIDIA_DRIVER_CAPABILITIES=graphics,compute,utility \
        nvidia/cuda:12.6.0-base-ubuntu22.04 nvidia-smi &>/dev/null; then
        log "Docker GPU: OK"
    else
        warn "Docker GPU: failed. Check stubs and container toolkit."
    fi

    # 5. Isaac Sim image
    log "5/6 Isaac Sim..."
    if docker image inspect "$ISAAC_SIM_IMAGE" &>/dev/null; then
        log "Isaac Sim: ready"
    else
        log "Pulling Isaac Sim..."
        docker pull "$ISAAC_SIM_IMAGE"
    fi

    # 6. Start Sunshine
    log "6/6 Starting Sunshine..."
    if command -v sunshine &>/dev/null; then
        # Kill any existing Sunshine and free ports
        pkill -f sunshine 2>/dev/null || true
        fuser -k 48010/tcp 2>/dev/null || true
        fuser -k 48010/udp 2>/dev/null || true
        sleep 2

        # Set credentials
        sunshine --creds "$VM_USER" "isaac2026" 2>/dev/null || true

        # Start via systemd (handles DISPLAY, XAUTHORITY, restarts)
        if [ -f /etc/systemd/system/sunshine.service ]; then
            systemctl start sunshine.service
            sleep 5
            if systemctl is-active --quiet sunshine.service; then
                log "Sunshine: running (systemd)"
            else
                warn "Sunshine systemd failed. Trying manual start..."
                rm -f /tmp/sunshine.log
                DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 nohup sunshine > /tmp/sunshine.log 2>&1 &
                sleep 5
                pgrep sunshine > /dev/null && log "Sunshine: running (manual)" || warn "Sunshine failed. Check: cat /tmp/sunshine.log"
            fi
        else
            rm -f /tmp/sunshine.log
            DISPLAY=:0 XAUTHORITY=/var/run/lightdm/root/:0 nohup sunshine > /tmp/sunshine.log 2>&1 &
            sleep 5
            pgrep sunshine > /dev/null && log "Sunshine: running (manual)" || warn "Sunshine failed"
        fi
    else
        warn "Sunshine not installed."
    fi

    PUBLIC_IP=$(curl -s --max-time 5 ifconfig.me 2>/dev/null || echo "<IP>")

    log ""
    log "============================================================"
    log " SETUP COMPLETE"
    log "============================================================"
    log ""
    log " Server: $PUBLIC_IP"
    log " Desktop login: $VM_USER / isaac2026"
    log ""
    log " --- CONNECT ---"
    log " 1. Local:      bash tools/connect.sh $PUBLIC_IP --sunshine"
    log " 2. Browser:    https://localhost:47990"
    log " 3. Moonlight:  add host $PUBLIC_IP, enter PIN in web UI"
    log " 4. Desktop:    ~/isaac-sim/start.sh"
    log ""
    log " --- WEBRTC (browser-only) ---"
    log " 1. Server:  ~/isaac-sim/launch_webrtc.sh"
    log " 2. Local:   ssh -N -f -L 49100:localhost:49100 -L 8211:localhost:8211 $VM_USER@$PUBLIC_IP"
    log " 3. Browser: http://127.0.0.1:8211/streaming/webrtc-client/?server=127.0.0.1"
    log ""
    log " NOTE: Kernel modules restored — VM can survive reboot."
    log "       After reboot, re-run --post-reboot to fix Vulkan userspace."
    log "============================================================"
fi
