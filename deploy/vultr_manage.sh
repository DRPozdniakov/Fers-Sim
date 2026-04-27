#!/bin/bash
# =============================================================================
# VULTR INSTANCE MANAGEMENT — Snapshot, destroy, restore
# =============================================================================
# Vultr charges hourly even when stopped. To save money:
#   1. Snapshot the instance (saves disk state)
#   2. Destroy the instance (stops billing)
#   3. Later: restore from snapshot (resume work)
#
# REQUIRES: Vultr CLI (https://github.com/vultr/vultr-cli)
#   Install: https://github.com/vultr/vultr-cli#installation
#   Auth:    export VULTR_API_KEY="your-api-key"
#
# USAGE:
#   bash deploy/vultr_manage.sh list               # List GPU instances
#   bash deploy/vultr_manage.sh snapshot <ID>       # Create snapshot
#   bash deploy/vultr_manage.sh snapshots           # List snapshots
#   bash deploy/vultr_manage.sh destroy <ID>        # Destroy instance (STOPS BILLING)
#   bash deploy/vultr_manage.sh restore <SNAP_ID>   # Restore from snapshot
#   bash deploy/vultr_manage.sh status <ID>         # Check instance status
#   bash deploy/vultr_manage.sh cost                # Show current billing estimate
# =============================================================================

set -euo pipefail

ACTION="${1:-help}"
INSTANCE_ID="${2:-}"

log() { echo "[vultr] $1"; }

# Check vultr-cli is installed
check_cli() {
    if ! command -v vultr-cli &>/dev/null; then
        echo "ERROR: vultr-cli not found."
        echo ""
        echo "Install:"
        echo "  Windows (scoop): scoop install vultr-cli"
        echo "  Windows (choco): choco install vultr-cli"
        echo "  Linux:           curl -sL https://github.com/vultr/vultr-cli/releases/latest/download/vultr-cli_linux_amd64.tar.gz | tar xz"
        echo ""
        echo "Then: export VULTR_API_KEY='your-api-key'"
        echo "Get API key: https://my.vultr.com/settings/#settingsapi"
        exit 1
    fi
    if [[ -z "${VULTR_API_KEY:-}" ]]; then
        echo "ERROR: VULTR_API_KEY not set."
        echo "  export VULTR_API_KEY='your-api-key'"
        echo "  Get it from: https://my.vultr.com/settings/#settingsapi"
        exit 1
    fi
}

case "$ACTION" in

    # -----------------------------------------------------------------------
    list)
        check_cli
        log "GPU instances:"
        vultr-cli instance list | head -20
        ;;

    # -----------------------------------------------------------------------
    status)
        check_cli
        if [[ -z "$INSTANCE_ID" ]]; then
            echo "Usage: bash deploy/vultr_manage.sh status <INSTANCE_ID>"
            exit 1
        fi
        vultr-cli instance get "$INSTANCE_ID"
        ;;

    # -----------------------------------------------------------------------
    snapshot)
        check_cli
        if [[ -z "$INSTANCE_ID" ]]; then
            echo "Usage: bash deploy/vultr_manage.sh snapshot <INSTANCE_ID>"
            echo "Get ID from: bash deploy/vultr_manage.sh list"
            exit 1
        fi
        SNAP_DESC="isaac-sim-$(date +%Y%m%d-%H%M)"
        log "Creating snapshot '$SNAP_DESC' of instance $INSTANCE_ID..."
        log "This takes 5-15 minutes depending on disk size."
        vultr-cli snapshot create -i "$INSTANCE_ID" -d "$SNAP_DESC"
        log "Snapshot creation started. Check progress:"
        log "  bash deploy/vultr_manage.sh snapshots"
        ;;

    # -----------------------------------------------------------------------
    snapshots)
        check_cli
        log "Available snapshots:"
        vultr-cli snapshot list
        ;;

    # -----------------------------------------------------------------------
    destroy)
        check_cli
        if [[ -z "$INSTANCE_ID" ]]; then
            echo "Usage: bash deploy/vultr_manage.sh destroy <INSTANCE_ID>"
            exit 1
        fi
        log "Instance $INSTANCE_ID will be DESTROYED. This stops billing."
        log "Make sure you created a snapshot first!"
        echo ""
        read -p "Are you sure? (yes/no): " CONFIRM
        if [[ "$CONFIRM" == "yes" ]]; then
            vultr-cli instance delete "$INSTANCE_ID"
            log "Instance destroyed. Billing stopped."
        else
            log "Aborted."
        fi
        ;;

    # -----------------------------------------------------------------------
    restore)
        check_cli
        SNAP_ID="${2:-}"
        if [[ -z "$SNAP_ID" ]]; then
            echo "Usage: bash deploy/vultr_manage.sh restore <SNAPSHOT_ID>"
            echo "Get ID from: bash deploy/vultr_manage.sh snapshots"
            exit 1
        fi

        log "Creating new L40S instance from snapshot $SNAP_ID..."
        log ""
        log "Available regions (pick closest):"
        log "  ewr  = New Jersey"
        log "  lax  = Los Angeles"
        log "  lhr  = London"
        log "  fra  = Frankfurt"
        log "  nrt  = Tokyo"
        log "  sgp  = Singapore"
        log "  syd  = Sydney"
        echo ""
        read -p "Region code (e.g. lhr): " REGION

        # vcg-a16-2c-4g-3vram = A16
        # vcg-l40s-1c-48g = L40S 1 GPU
        PLAN="vcg-l40s-1c-48g"

        log "Deploying $PLAN in $REGION from snapshot $SNAP_ID..."
        vultr-cli instance create \
            --region "$REGION" \
            --plan "$PLAN" \
            --snapshot "$SNAP_ID" \
            --label "isaac-sim-restored"

        log "Instance creating. Check status:"
        log "  bash deploy/vultr_manage.sh list"
        ;;

    # -----------------------------------------------------------------------
    cost)
        check_cli
        log "Current billing:"
        vultr-cli account
        log ""
        log "L40S cost: \$1.67/hr = \$40.08/day = \$1,219/mo (24/7)"
        log "At 8hr/day: ~\$13.36/day = ~\$294/mo"
        ;;

    # -----------------------------------------------------------------------
    help|*)
        echo "Vultr Instance Management"
        echo ""
        echo "Usage: bash deploy/vultr_manage.sh <command> [args]"
        echo ""
        echo "Commands:"
        echo "  list                List all instances"
        echo "  status <ID>         Instance details"
        echo "  snapshot <ID>       Create snapshot (save state before destroy)"
        echo "  snapshots           List all snapshots"
        echo "  destroy <ID>        Destroy instance (STOPS BILLING)"
        echo "  restore <SNAP_ID>   Create new instance from snapshot"
        echo "  cost                Show billing info"
        echo ""
        echo "Workflow to save money:"
        echo "  1. bash deploy/vultr_manage.sh list              # Get instance ID"
        echo "  2. bash deploy/vultr_manage.sh snapshot <ID>     # Save state"
        echo "  3. bash deploy/vultr_manage.sh snapshots         # Wait until complete"
        echo "  4. bash deploy/vultr_manage.sh destroy <ID>      # Stop billing"
        echo "  5. (later) bash deploy/vultr_manage.sh restore <SNAP_ID>  # Resume"
        echo ""
        echo "Prerequisites:"
        echo "  - Install vultr-cli: https://github.com/vultr/vultr-cli"
        echo "  - export VULTR_API_KEY='your-key'"
        ;;
esac
