#!/bin/bash
# =============================================================================
# Local-side connection helper for Nebius Isaac Sim
# Run this from your LOCAL machine (not the server)
# =============================================================================
# USAGE:
#   bash tools/connect.sh <NEBIUS_IP> --sunshine    # Pair Sunshine via web UI
#   bash tools/connect.sh <NEBIUS_IP> --webrtc      # WebRTC streaming tunnels
#   bash tools/connect.sh --kill                     # Kill existing tunnels
# =============================================================================

set -euo pipefail

if [ -z "${1:-}" ]; then
    echo "Usage: bash tools/connect.sh <NEBIUS_IP> <MODE>"
    echo ""
    echo "Modes:"
    echo "  --sunshine   SSH tunnel to Sunshine web UI (port 47984)"
    echo "               Then open: https://localhost:47984"
    echo ""
    echo "  --webrtc     SSH tunnels for Isaac Sim WebRTC (ports 49100 + 8211)"
    echo "               Then open: http://127.0.0.1:8211/streaming/webrtc-client/?server=127.0.0.1"
    echo ""
    echo "  --kill       Kill all existing SSH tunnels to Nebius"
    exit 1
fi

USER="latoff"

# --kill mode (no IP needed)
if [[ "$1" == "--kill" ]]; then
    echo "Killing existing SSH tunnels..."
    pkill -f "ssh.*-L.*47984" 2>/dev/null && echo "Killed Sunshine tunnel" || echo "No Sunshine tunnel found"
    pkill -f "ssh.*-L.*49100" 2>/dev/null && echo "Killed WebRTC tunnel" || echo "No WebRTC tunnel found"
    pkill -f "ssh.*-L.*8211" 2>/dev/null && echo "Killed viewer tunnel" || echo "No viewer tunnel found"
    exit 0
fi

IP="$1"
MODE="${2:-}"

case "$MODE" in
    --sunshine)
        echo "=== Sunshine SSH tunnel ==="
        echo "Tunneling ports 47990 (web UI) + 47989 + 47984..."
        echo ""
        echo "Once connected, open in browser:"
        echo "  https://localhost:47990"
        echo ""
        echo "Credentials: $USER / isaac2026"
        echo "(If 401 error: ssh $USER@$IP 'sunshine --creds $USER isaac2026')"
        echo ""
        echo "After pairing, open Moonlight and add host: $IP"
        echo ""
        echo "Press Ctrl+C to close tunnel."
        ssh -o StrictHostKeyChecking=no -L 47990:localhost:47990 -L 47989:localhost:47989 -L 47984:localhost:47984 "$USER@$IP"
        ;;
    --webrtc)
        echo "=== WebRTC SSH tunnels ==="
        echo "Tunneling ports 49100 (signaling) + 8211 (web viewer)..."
        echo ""
        echo "First, start Isaac Sim on the server:"
        echo "  ssh $USER@$IP '~/isaac-sim/launch_webrtc.sh'"
        echo ""
        echo "Then open in Chrome/Edge:"
        echo "  http://127.0.0.1:8211/streaming/webrtc-client/?server=127.0.0.1"
        echo ""
        echo "Press Ctrl+C to close tunnels."
        ssh -o StrictHostKeyChecking=no -N -L 49100:localhost:49100 -L 8211:localhost:8211 "$USER@$IP"
        ;;
    *)
        echo "Unknown mode: $MODE"
        echo "Use --sunshine, --webrtc, or --kill"
        exit 1
        ;;
esac
