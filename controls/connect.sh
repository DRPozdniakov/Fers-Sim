#!/bin/bash
# =============================================================================
# LOCAL CONNECT SCRIPT — Run from your Windows/WSL machine
# =============================================================================
# Sets up SSH tunnels and prints connection instructions.
#
# USAGE:
#   bash tools/connect.sh <VULTR_IP>
#   bash tools/connect.sh <VULTR_IP> --webrtc     # Isaac Sim WebRTC mode
#   bash tools/connect.sh <VULTR_IP> --sunshine    # Sunshine pairing mode
#   bash tools/connect.sh <VULTR_IP> --kill        # Kill existing tunnels
# =============================================================================

set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "Usage: bash tools/connect.sh <VULTR_IP> [--webrtc|--sunshine|--kill]"
    echo ""
    echo "  --webrtc    Set up SSH tunnels for Isaac Sim WebRTC streaming"
    echo "  --sunshine  Set up SSH tunnel to Sunshine web UI for initial pairing"
    echo "  --kill      Kill all existing SSH tunnels to this server"
    echo "  (default)   Show connection options menu"
    exit 1
fi

VULTR_IP="$1"
MODE="${2:-menu}"
SSH_USER="isaac"

log() { echo "[connect] $1"; }

kill_tunnels() {
    log "Killing existing SSH tunnels to $VULTR_IP..."
    pkill -f "ssh.*$VULTR_IP.*-L" 2>/dev/null && log "Tunnels killed." || log "No active tunnels found."
}

# ---------------------------------------------------------------------------
# Kill tunnels
# ---------------------------------------------------------------------------
if [[ "$MODE" == "--kill" ]]; then
    kill_tunnels
    exit 0
fi

# ---------------------------------------------------------------------------
# Sunshine pairing (first-time setup)
# ---------------------------------------------------------------------------
if [[ "$MODE" == "--sunshine" ]]; then
    log "Setting up SSH tunnel to Sunshine web UI..."
    kill_tunnels

    ssh -N -f -L 47984:localhost:47984 "root@$VULTR_IP"

    log ""
    log "============================================================"
    log " SUNSHINE PAIRING"
    log "============================================================"
    log ""
    log " 1. Open in your browser:"
    log "      https://localhost:47984"
    log ""
    log " 2. Accept the self-signed certificate warning"
    log ""
    log " 3. Create a username and password"
    log ""
    log " 4. Then open Moonlight (https://moonlight-stream.org/)"
    log "    Add host: $VULTR_IP"
    log "    Enter the PIN from Moonlight into the Sunshine web UI"
    log ""
    log " 5. Once paired, connect to Desktop in Moonlight"
    log ""
    log " Kill tunnel when done: bash tools/connect.sh $VULTR_IP --kill"
    log "============================================================"
    exit 0
fi

# ---------------------------------------------------------------------------
# WebRTC streaming
# ---------------------------------------------------------------------------
if [[ "$MODE" == "--webrtc" ]]; then
    log "Setting up SSH tunnels for Isaac Sim WebRTC..."
    kill_tunnels

    # Tunnel WebRTC signaling + web viewer
    ssh -N -f -L 49100:localhost:49100 -L 8211:localhost:8211 "$SSH_USER@$VULTR_IP"

    log ""
    log "============================================================"
    log " ISAAC SIM WEBRTC STREAMING"
    log "============================================================"
    log ""
    log " SSH tunnels active: 49100 (signaling), 8211 (web viewer)"
    log ""
    log " 1. On the SERVER (SSH in separately):"
    log "      ssh $SSH_USER@$VULTR_IP"
    log "      ~/isaac-sim/launch_webrtc.sh"
    log ""
    log " 2. Wait for Isaac Sim to start (10-15 min first time)"
    log ""
    log " 3. Open in Chrome/Edge on your PC:"
    log "      http://127.0.0.1:8211/streaming/webrtc-client/?server=127.0.0.1"
    log ""
    log " Kill tunnels: bash tools/connect.sh $VULTR_IP --kill"
    log "============================================================"
    exit 0
fi

# ---------------------------------------------------------------------------
# Menu (default)
# ---------------------------------------------------------------------------
log ""
log "============================================================"
log " CONNECTION OPTIONS — $VULTR_IP"
log "============================================================"
log ""
log " METHOD 1: Sunshine + Moonlight (full desktop)"
log "   First time:  bash tools/connect.sh $VULTR_IP --sunshine"
log "   After pair:  Open Moonlight → connect to $VULTR_IP"
log "   Then run:    ~/isaac-sim/launch_gui.sh (from desktop terminal)"
log ""
log " METHOD 2: Isaac Sim WebRTC (browser-based, no desktop)"
log "   Local:       bash tools/connect.sh $VULTR_IP --webrtc"
log "   Server:      ssh $SSH_USER@$VULTR_IP '~/isaac-sim/launch_webrtc.sh'"
log "   Browser:     http://127.0.0.1:8211/streaming/webrtc-client/?server=127.0.0.1"
log ""
log " UTILITIES:"
log "   SSH in:      ssh $SSH_USER@$VULTR_IP"
log "   Diagnose:    ssh $SSH_USER@$VULTR_IP '~/isaac-sim/check_gpu.sh'"
log "   Kill tunnels: bash tools/connect.sh $VULTR_IP --kill"
log "============================================================"
