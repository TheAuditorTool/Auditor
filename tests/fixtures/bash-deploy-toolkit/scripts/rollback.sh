#!/bin/bash
# Rollback script for reverting deployments
# Usage: ./scripts/rollback.sh <environment> [options]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Source libraries
. "$SCRIPT_DIR/lib/common.sh"
. "$SCRIPT_DIR/lib/database.sh"

# Rollback options
ROLLBACK_STEPS=1
RESTORE_DATABASE=false
TARGET_RELEASE=""
FORCE=false

# Parse arguments
parse_rollback_args() {
    if [[ $# -lt 1 ]]; then
        echo "Usage: $0 <environment> [options]"
        echo ""
        echo "Options:"
        echo "  --steps N           Roll back N releases (default: 1)"
        echo "  --release ID        Roll back to specific release"
        echo "  --with-database     Also restore database backup"
        echo "  --force             Skip confirmation prompts"
        echo ""
        exit 1
    fi

    ENVIRONMENT="$1"
    shift

    while [[ $# -gt 0 ]]; do
        case $1 in
            --steps)
                ROLLBACK_STEPS="$2"
                shift
                ;;
            --release)
                TARGET_RELEASE="$2"
                shift
                ;;
            --with-database)
                RESTORE_DATABASE=true
                ;;
            --force)
                FORCE=true
                ;;
            *)
                log_warn "Unknown option: $1"
                ;;
        esac
        shift
    done
}

# Get list of available releases
get_releases() {
    local host="$1"

    remote_exec $host "ls -1t ${APP_DIR}/releases 2>/dev/null | head -20"
}

# Get current release
get_current_release() {
    local host="$1"

    remote_exec $host "readlink ${APP_DIR}/current 2>/dev/null | xargs basename"
}

# Find previous release
get_previous_release() {
    local host="$1"
    local steps="${2:-1}"

    local releases=$(get_releases $host)
    local current=$(get_current_release $host)

    # Find current position and get the one N steps before
    local position=0
    local found=false

    for release in $releases; do
        if [[ "$found" == "true" ]]; then
            position=$((position + 1))
            if [[ $position -eq $steps ]]; then
                echo $release
                return 0
            fi
        elif [[ "$release" == "$current" ]]; then
            found=true
        fi
    done

    return 1
}

# Find backup for a release
find_backup_for_release() {
    local release="$1"

    # Extract timestamp from release ID (deploy-YYYYMMDDHHMMSS-xxx)
    local release_date=$(echo $release | grep -oE '[0-9]{14}' | head -1)

    if [[ -z "$release_date" ]]; then
        log_warn "Could not extract date from release: $release"
        return 1
    fi

    # Find backup with closest timestamp
    local formatted_date="${release_date:0:8}_${release_date:8:6}"

    local backup=$(ls -1 ${BACKUP_DIR}/*/${database}/*${formatted_date}* 2>/dev/null | head -1)

    if [[ -z "$backup" ]]; then
        # Try to find any backup from the same day
        local day="${release_date:0:8}"
        backup=$(ls -1 ${BACKUP_DIR}/${day}*/database/*.sql.gz 2>/dev/null | tail -1)
    fi

    if [[ -f "$backup" ]]; then
        echo $backup
    fi
}

# Perform rollback
do_rollback() {
    local host="$1"
    local target_release="$2"

    log_info "Rolling back to release: $target_release"

    # Verify target release exists
    if ! remote_exec $host "test -d ${APP_DIR}/releases/${target_release}"; then
        log_error "Release not found: $target_release"
        return 1
    fi

    # Get current release for backup reference
    local current_release=$(get_current_release $host)
    log_info "Current release: $current_release"

    # Switch symlink to target release
    log_info "Switching to target release..."
    remote_exec $host "ln -sfn ${APP_DIR}/releases/${target_release} ${APP_DIR}/current"

    # Restart application
    restart_app $host

    # Verify health
    local health_url="http://${host}${HEALTH_ENDPOINT}"
    if wait_for_healthy "$health_url" "$HEALTH_TIMEOUT"; then
        log_info "Rollback successful!"
        return 0
    else
        log_error "Health check failed after rollback!"

        # Try to recover by going back to original
        log_warn "Attempting to restore original release..."
        remote_exec $host "ln -sfn ${APP_DIR}/releases/${current_release} ${APP_DIR}/current"
        restart_app $host

        return 1
    fi
}

# Rollback database
do_database_rollback() {
    local backup_file="$1"

    if [[ ! -f "$backup_file" ]]; then
        log_error "Backup file not found: $backup_file"
        return 1
    fi

    log_warn "This will restore the database from: $backup_file"

    if [[ "$FORCE" != "true" ]]; then
        read -p "Are you sure you want to restore the database? (yes/no): " confirm
        if [[ "$confirm" != "yes" ]]; then
            log_info "Database rollback cancelled"
            return 0
        fi
    fi

    restore_database "$backup_file" "--force"
}

# Main rollback function
main() {
    parse_rollback_args "$@"
    load_config

    validate_environment "$ENVIRONMENT"

    local target_host=$(get_target_host $ENVIRONMENT)

    log_info "Starting rollback on $ENVIRONMENT ($target_host)"

    # Determine target release
    if [[ -n "$TARGET_RELEASE" ]]; then
        # Use specified release
        ROLLBACK_TARGET="$TARGET_RELEASE"
    else
        # Calculate previous release
        ROLLBACK_TARGET=$(get_previous_release $target_host $ROLLBACK_STEPS)

        if [[ -z "$ROLLBACK_TARGET" ]]; then
            log_error "Could not find a release to roll back to"
            log_info "Available releases:"
            get_releases $target_host
            exit 1
        fi
    fi

    log_info "Rolling back to: $ROLLBACK_TARGET"

    # Confirmation
    if [[ "$FORCE" != "true" ]]; then
        local current=$(get_current_release $target_host)
        echo ""
        echo "Rollback Summary:"
        echo "  Environment: $ENVIRONMENT"
        echo "  Current:     $current"
        echo "  Target:      $ROLLBACK_TARGET"
        echo "  Database:    $([ "$RESTORE_DATABASE" == "true" ] && echo "Will restore" || echo "No change")"
        echo ""
        read -p "Proceed with rollback? (yes/no): " confirm
        if [[ "$confirm" != "yes" ]]; then
            log_info "Rollback cancelled"
            exit 0
        fi
    fi

    # Perform database rollback first if requested
    if [[ "$RESTORE_DATABASE" == "true" ]]; then
        local backup=$(find_backup_for_release $ROLLBACK_TARGET)

        if [[ -n "$backup" ]]; then
            log_info "Found database backup: $backup"
            if ! do_database_rollback $backup; then
                log_error "Database rollback failed!"
                exit 1
            fi
        else
            log_warn "No database backup found for release $ROLLBACK_TARGET"
            if [[ "$FORCE" != "true" ]]; then
                read -p "Continue without database rollback? (yes/no): " confirm
                if [[ "$confirm" != "yes" ]]; then
                    exit 1
                fi
            fi
        fi
    fi

    # Perform code rollback
    if ! do_rollback $target_host $ROLLBACK_TARGET; then
        log_error "Rollback failed!"
        notify_slack "Rollback FAILED on $ENVIRONMENT!" "danger"
        exit 1
    fi

    # Send notification
    notify_slack "Rollback completed on $ENVIRONMENT. Now running: $ROLLBACK_TARGET" "warning"

    log_info "Rollback complete!"
    log_info "Current release is now: $(get_current_release $target_host)"
}

# Restart application helper
restart_app() {
    local host="$1"

    log_info "Restarting application..."

    if remote_exec $host "command -v systemctl &> /dev/null"; then
        remote_exec $host "sudo systemctl restart ${APP_NAME}"
    else
        remote_exec $host "sudo service ${APP_NAME} restart"
    fi
}

# Run main function
main "$@"
