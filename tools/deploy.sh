#!/bin/bash
# =============================================================================
# Local-side deploy orchestrator for Nebius Isaac Sim setup
# Run this from your LOCAL machine (not the server)
# =============================================================================
# USAGE:
#   bash tools/deploy.sh <NEBIUS_IP> [--phase2]
# =============================================================================

set -euo pipefail

if [ -z "${1:-}" ]; then
    echo "Usage: bash tools/deploy.sh <NEBIUS_IP> [--phase2]"
    echo ""
    echo "  <NEBIUS_IP>   Public IP of your Nebius VM"
    echo "  --phase2      Skip upload+phase1, run post-reboot only"
    exit 1
fi

IP="$1"
PHASE="${2:-}"
USER="latoff"
SCRIPT="nebius_isaac_sim_setup.sh"
SCRIPT_PATH="tools/$SCRIPT"

ssh_cmd() { ssh -o StrictHostKeyChecking=no "$USER@$IP" "$@"; }

if [[ "$PHASE" == "--phase2" ]]; then
    echo "=== Phase 2: Post-reboot verification ==="
    ssh_cmd "sudo bash ~/$SCRIPT --post-reboot"
    echo ""
    echo "=== Done. Now run: bash tools/connect.sh $IP --sunshine ==="
    exit 0
fi

echo "=== Step 1: Upload setup script ==="
scp -o StrictHostKeyChecking=no "$SCRIPT_PATH" "$USER@$IP:~/$SCRIPT"
echo "Uploaded."

echo ""
echo "=== Step 2: Run diagnostic ==="
ssh_cmd "sudo bash ~/$SCRIPT --diagnose"

echo ""
echo "=== Step 3: Run Phase 1 (install everything) ==="
echo "This takes ~20-30 min. Watch for errors."
ssh_cmd "sudo bash ~/$SCRIPT"

echo ""
echo "============================================================"
echo " Phase 1 complete. Now reboot the VM:"
echo "   ssh $USER@$IP 'sudo reboot'"
echo ""
echo " Wait ~60 seconds, then run:"
echo "   bash tools/deploy.sh $IP --phase2"
echo "============================================================"
