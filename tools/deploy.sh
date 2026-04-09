#!/bin/bash
# =============================================================================
# Local-side deploy orchestrator for Nebius Isaac Sim setup
# Run this from your LOCAL machine (not the server)
# =============================================================================
# USAGE:
#   bash tools/deploy.sh <IP>                    # Full deploy (Phase 1 + instructions)
#   bash tools/deploy.sh <IP> --phase2           # Post-reboot (Phase 2)
#   bash tools/deploy.sh <IP> --upload           # Upload script only
#   bash tools/deploy.sh <IP> --diagnose         # Run diagnostic only
#   bash tools/deploy.sh <IP> --status           # Check VM status
# =============================================================================

set -euo pipefail

if [ -z "${1:-}" ]; then
    echo "Usage: bash tools/deploy.sh <IP> [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  (none)       Full deploy: upload + diagnose + Phase 1"
    echo "  --phase2     Post-reboot: Vulkan fix + start services"
    echo "  --upload     Upload setup script only"
    echo "  --diagnose   Run GPU/system diagnostic"
    echo "  --status     Check GPU, Vulkan, Docker, Sunshine status"
    echo ""
    echo "Full workflow:"
    echo "  bash tools/deploy.sh <IP>              # ~20-30 min"
    echo "  ssh <user>@<IP> 'sudo reboot'           # wait ~60s"
    echo "  bash tools/deploy.sh <IP> --phase2     # ~5 min"
    echo "  bash tools/connect.sh <IP> --sunshine   # connect Moonlight"
    exit 1
fi

IP="$1"
CMD="${2:-full}"
SCRIPT="nebius_isaac_sim_setup.sh"
SCRIPT_PATH="tools/$SCRIPT"

# Auto-detect user and SSH key based on IP
case "$IP" in
    216.81.245.44) USER="shadeform"; SSH_KEY="$HOME/.ssh/KGXB" ;;
    *)             USER="latoff";    SSH_KEY="" ;;
esac

SSH_OPTS="-o StrictHostKeyChecking=no"
[ -n "$SSH_KEY" ] && SSH_OPTS="$SSH_OPTS -i $SSH_KEY"

ssh_cmd() { ssh $SSH_OPTS "$USER@$IP" "$@"; }
scp_cmd() { scp $SSH_OPTS "$@"; }

upload() {
    echo "=== Uploading setup script ==="
    scp_cmd "$SCRIPT_PATH" "$USER@$IP:~/$SCRIPT"
    echo "=== Uploading simulation folder ==="
    scp_cmd -r simulation "$USER@$IP:~/"
    echo "Uploaded."
}

case "$CMD" in
    --upload)
        upload
        ;;
    --diagnose)
        upload
        ssh_cmd "sudo bash ~/$SCRIPT --diagnose"
        ;;
    --phase2)
        echo "=== Phase 2: Post-reboot Vulkan fix ==="
        # Re-upload in case script was updated
        upload
        ssh_cmd "sudo bash ~/$SCRIPT --post-reboot"
        echo ""
        echo "============================================================"
        echo " Done. Connect with:"
        echo "   bash tools/connect.sh $IP --sunshine"
        echo "============================================================"
        ;;
    --status)
        echo "=== VM Status ==="
        ssh_cmd "nvidia-smi 2>/dev/null | head -5 || echo 'GPU: FAILED'"
        ssh_cmd "vulkaninfo --summary 2>&1 | grep -A2 'GPU' || echo 'Vulkan: FAILED'"
        ssh_cmd "systemctl is-active lightdm 2>/dev/null || echo 'LightDM: not running'"
        ssh_cmd "pgrep -a sunshine 2>/dev/null || echo 'Sunshine: not running'"
        ssh_cmd "docker image inspect nvcr.io/nvidia/isaac-sim:5.1.0 &>/dev/null && echo 'Isaac Sim: ready' || echo 'Isaac Sim: not pulled'"
        ;;
    full|*)
        upload
        echo ""
        echo "=== Diagnostic ==="
        ssh_cmd "sudo bash ~/$SCRIPT --diagnose"
        echo ""
        echo "=== Phase 1: Install everything (~20-30 min) ==="
        ssh_cmd "sudo bash ~/$SCRIPT"
        echo ""
        echo "============================================================"
        echo " Phase 1 complete. Now:"
        echo "   ssh $USER@$IP 'sudo reboot'"
        echo "   # wait ~60 seconds"
        echo "   bash tools/deploy.sh $IP --phase2"
        echo "============================================================"
        ;;
esac
