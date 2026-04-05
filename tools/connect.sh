#!/bin/bash
# =============================================================================
# Local-side connection helper for Nebius Isaac Sim
# Run this from your LOCAL machine (not the server)
# =============================================================================
# USAGE:
#   bash tools/connect.sh <IP> --sunshine    # SSH tunnel for Sunshine web UI
#   bash tools/connect.sh <IP> --webrtc      # SSH tunnel for WebRTC streaming
#   bash tools/connect.sh <IP> --direct      # Open Moonlight directly (no tunnel)
#   bash tools/connect.sh --kill             # Kill existing tunnels
# =============================================================================

set -euo pipefail

if [ -z "${1:-}" ]; then
    echo "Usage: bash tools/connect.sh <IP> <MODE>"
    echo ""
    echo "Modes:"
    echo "  --sunshine   SSH tunnel to Sunshine web UI"
    echo "               Then open: https://localhost:47990"
    echo "               Then pair Moonlight to the VM IP"
    echo ""
    echo "  --webrtc     SSH tunnels for Isaac Sim WebRTC"
    echo "               Then open: http://127.0.0.1:8211/streaming/webrtc-client/?server=127.0.0.1"
    echo ""
    echo "  --direct     Just print Moonlight instructions (no SSH tunnel)"
    echo ""
    echo "  --kill       Kill all existing SSH tunnels"
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
        echo "=== Sunshine Connection ==="
        echo ""
        echo "Step 1: SSH tunnel is starting..."
        echo "Step 2: Open https://localhost:47990 in browser"
        echo "Step 3: Login: $USER / isaac2026"
        echo "Step 4: Open Moonlight → Add host: $IP → Enter PIN from web UI"
        echo "Step 5: Connect to Desktop in Moonlight"
        echo "Step 6: Open terminal → ~/isaac-sim/start.sh"
        echo ""
        echo "Press Ctrl+C to close tunnel."
        ssh -o StrictHostKeyChecking=no \
            -L 47990:localhost:47990 \
            -L 47989:localhost:47989 \
            -L 47984:localhost:47984 \
            "$USER@$IP"
        ;;
    --webrtc)
        echo "=== WebRTC Connection ==="
        echo ""
        echo "Step 1: Start Isaac Sim on server:"
        echo "  ssh $USER@$IP '~/isaac-sim/launch_webrtc.sh'"
        echo ""
        echo "Step 2: SSH tunnel is starting..."
        echo "Step 3: Open Chrome/Edge:"
        echo "  http://127.0.0.1:8211/streaming/webrtc-client/?server=127.0.0.1"
        echo ""
        echo "Press Ctrl+C to close tunnels."
        ssh -o StrictHostKeyChecking=no -N \
            -L 49100:localhost:49100 \
            -L 8211:localhost:8211 \
            "$USER@$IP"
        ;;
    --direct)
        echo "=== Direct Moonlight Connection ==="
        echo ""
        echo "1. Open Moonlight"
        echo "2. Add host: $IP"
        echo "3. If prompted for PIN, get it from: https://$IP:47990"
        echo "4. Connect to Desktop"
        echo "5. Open terminal → ~/isaac-sim/start.sh"
        echo ""
        echo "Note: Requires Sunshine ports (47984,47989,47990,48010) open in Nebius firewall"
        ;;
    *)
        echo "Unknown mode: $MODE"
        echo "Use --sunshine, --webrtc, --direct, or --kill"
        exit 1
        ;;
esac
