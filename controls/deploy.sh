#!/bin/bash
# =============================================================================
# LOCAL DEPLOY SCRIPT — Run from your Windows/WSL machine
# =============================================================================
# Uploads setup script to Vultr, runs diagnose, then phases 1 & 2.
#
# PREREQUISITES:
#   - Vultr Cloud GPU instance deployed (1x L40S, Ubuntu 22.04)
#   - SSH key added to the instance (or password auth enabled)
#
# USAGE:
#   bash tools/deploy.sh <VULTR_IP>
#   bash tools/deploy.sh <VULTR_IP> --diagnose-only
#   bash tools/deploy.sh <VULTR_IP> --phase2-only
# =============================================================================

set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "Usage: bash tools/deploy.sh <VULTR_IP> [--diagnose-only|--phase2-only]"
    echo ""
    echo "  <VULTR_IP>       Public IP of your Vultr GPU instance"
    echo "  --diagnose-only  Just run diagnostics, don't install anything"
    echo "  --phase2-only    Skip phase 1, run post-reboot setup only"
    exit 1
fi

VULTR_IP="$1"
MODE="${2:-full}"
SSH_USER="root"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETUP_SCRIPT="$SCRIPT_DIR/vultr_isaac_sim_setup.sh"

log() { echo "[deploy] $1"; }

# Verify setup script exists
if [ ! -f "$SETUP_SCRIPT" ]; then
    echo "ERROR: $SETUP_SCRIPT not found."
    exit 1
fi

# ---------------------------------------------------------------------------
# Upload setup script
# ---------------------------------------------------------------------------
log "Uploading setup script to $SSH_USER@$VULTR_IP..."
scp -o StrictHostKeyChecking=accept-new "$SETUP_SCRIPT" "$SSH_USER@$VULTR_IP:/root/vultr_isaac_sim_setup.sh"
log "Upload complete."

# ---------------------------------------------------------------------------
# Diagnose only
# ---------------------------------------------------------------------------
if [[ "$MODE" == "--diagnose-only" ]]; then
    log "Running diagnostics..."
    ssh "$SSH_USER@$VULTR_IP" "bash /root/vultr_isaac_sim_setup.sh --diagnose"
    exit 0
fi

# ---------------------------------------------------------------------------
# Phase 2 only (after manual reboot)
# ---------------------------------------------------------------------------
if [[ "$MODE" == "--phase2-only" ]]; then
    log "Running post-reboot setup (phase 2)..."
    ssh "$SSH_USER@$VULTR_IP" "bash /root/vultr_isaac_sim_setup.sh --post-reboot"
    exit 0
fi

# ---------------------------------------------------------------------------
# Full deployment
# ---------------------------------------------------------------------------

# Step 1: Diagnose
log "=== Step 1/4: Running diagnostics ==="
ssh "$SSH_USER@$VULTR_IP" "bash /root/vultr_isaac_sim_setup.sh --diagnose"
echo ""
read -p "Diagnostics OK? Proceed with install? (y/n): " PROCEED
if [[ "$PROCEED" != "y" ]]; then
    log "Aborted."
    exit 0
fi

# Step 2: Phase 1
log "=== Step 2/4: Running phase 1 (install) ==="
log "This takes ~20-30 min. You'll be prompted to reboot at the end."
ssh -t "$SSH_USER@$VULTR_IP" "bash /root/vultr_isaac_sim_setup.sh"

# Step 3: Wait for reboot
log "=== Step 3/4: Waiting for server to come back after reboot ==="
log "Waiting 30 seconds..."
sleep 30

RETRIES=0
MAX_RETRIES=20
until ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new "$SSH_USER@$VULTR_IP" "echo 'Server is back'" 2>/dev/null; do
    RETRIES=$((RETRIES + 1))
    if [[ $RETRIES -ge $MAX_RETRIES ]]; then
        log "Server didn't come back after $MAX_RETRIES attempts."
        log "Run manually: bash tools/deploy.sh $VULTR_IP --phase2-only"
        exit 1
    fi
    log "Attempt $RETRIES/$MAX_RETRIES - waiting 10s..."
    sleep 10
done

# Step 4: Phase 2
log "=== Step 4/4: Running post-reboot setup ==="
ssh "$SSH_USER@$VULTR_IP" "bash /root/vultr_isaac_sim_setup.sh --post-reboot"

log ""
log "============================================================"
log " DEPLOYMENT COMPLETE"
log "============================================================"
log ""
log " Now run:  bash tools/connect.sh $VULTR_IP"
log "============================================================"
