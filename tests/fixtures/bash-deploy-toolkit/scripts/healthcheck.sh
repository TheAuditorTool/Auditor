#!/bin/bash
# Health check script for monitoring service status
# Usage: ./scripts/healthcheck.sh [options]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Source libraries
. "$SCRIPT_DIR/lib/common.sh"
. "$SCRIPT_DIR/lib/database.sh"

# Check options
CHECK_HTTP=false
CHECK_DATABASE=false
CHECK_DISK=false
CHECK_MEMORY=false
CHECK_ALL=false
VERBOSE=false
OUTPUT_FORMAT="text"

# Thresholds
DISK_THRESHOLD=90
MEMORY_THRESHOLD=90
HTTP_TIMEOUT=10

# Parse arguments
parse_health_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --http)
                CHECK_HTTP=true
                ;;
            --database|--db)
                CHECK_DATABASE=true
                ;;
            --disk)
                CHECK_DISK=true
                ;;
            --memory|--mem)
                CHECK_MEMORY=true
                ;;
            --all|-a)
                CHECK_ALL=true
                ;;
            --verbose|-v)
                VERBOSE=true
                ;;
            --json)
                OUTPUT_FORMAT="json"
                ;;
            --threshold-disk)
                DISK_THRESHOLD="$2"
                shift
                ;;
            --threshold-memory)
                MEMORY_THRESHOLD="$2"
                shift
                ;;
            *)
                log_warn "Unknown option: $1"
                ;;
        esac
        shift
    done

    # Default to all if nothing specified
    if [[ "$CHECK_HTTP" == "false" && "$CHECK_DATABASE" == "false" && \
          "$CHECK_DISK" == "false" && "$CHECK_MEMORY" == "false" ]]; then
        CHECK_ALL=true
    fi

    if [[ "$CHECK_ALL" == "true" ]]; then
        CHECK_HTTP=true
        CHECK_DATABASE=true
        CHECK_DISK=true
        CHECK_MEMORY=true
    fi
}

# HTTP endpoint health check
check_http_health() {
    local host="${1:-localhost}"
    local endpoint="${HEALTH_ENDPOINT:-/health}"
    local url="http://${host}${endpoint}"

    [[ "$VERBOSE" == "true" ]] && log_info "Checking HTTP health: $url"

    local start_time=$(date +%s%N)
    local response=$(curl -sf -w "%{http_code}" --max-time $HTTP_TIMEOUT "$url" -o /tmp/health_response.json 2>/dev/null)
    local end_time=$(date +%s%N)

    local response_time=$(( (end_time - start_time) / 1000000 ))

    if [[ "$response" == "200" ]]; then
        local status="healthy"
        local details=""

        # Parse response if it's JSON
        if [[ -f /tmp/health_response.json ]]; then
            details=$(cat /tmp/health_response.json | jq -r '.status // empty' 2>/dev/null)
        fi

        echo "http:ok:${response_time}ms:${details:-ok}"
        return 0
    else
        echo "http:failed:${response_time}ms:HTTP ${response:-timeout}"
        return 1
    fi
}

# Database health check
check_database_health() {
    [[ "$VERBOSE" == "true" ]] && log_info "Checking database health..."

    local start_time=$(date +%s%N)

    if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1" > /dev/null 2>&1; then
        local end_time=$(date +%s%N)
        local response_time=$(( (end_time - start_time) / 1000000 ))

        # Get connection count
        local connections=$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT count(*) FROM pg_stat_activity" 2>/dev/null | tr -d ' ')

        echo "database:ok:${response_time}ms:connections=${connections:-unknown}"
        return 0
    else
        echo "database:failed:0ms:connection_error"
        return 1
    fi
}

# Disk space health check
check_disk_health() {
    [[ "$VERBOSE" == "true" ]] && log_info "Checking disk health..."

    local status="ok"
    local details=""

    # Check main filesystem
    local usage=$(df -h / | awk 'NR==2 {print $5}' | tr -d '%')

    if [[ $usage -ge $DISK_THRESHOLD ]]; then
        status="critical"
        details="root=${usage}%"
    else
        details="root=${usage}%"
    fi

    # Check app directory if different filesystem
    if [[ -d "$APP_DIR" ]]; then
        local app_usage=$(df -h "$APP_DIR" | awk 'NR==2 {print $5}' | tr -d '%')
        if [[ $app_usage -ge $DISK_THRESHOLD ]]; then
            status="critical"
        fi
        details="${details},app=${app_usage}%"
    fi

    # Check backup directory
    if [[ -d "$BACKUP_DIR" ]]; then
        local backup_usage=$(df -h "$BACKUP_DIR" | awk 'NR==2 {print $5}' | tr -d '%')
        if [[ $backup_usage -ge $DISK_THRESHOLD ]]; then
            status="warning"
        fi
        details="${details},backup=${backup_usage}%"
    fi

    echo "disk:${status}:${details}"
    [[ "$status" == "ok" ]] && return 0 || return 1
}

# Memory health check
check_memory_health() {
    [[ "$VERBOSE" == "true" ]] && log_info "Checking memory health..."

    local total=$(free -m | awk 'NR==2 {print $2}')
    local used=$(free -m | awk 'NR==2 {print $3}')
    local usage=$((used * 100 / total))

    local status="ok"
    if [[ $usage -ge $MEMORY_THRESHOLD ]]; then
        status="critical"
    elif [[ $usage -ge $((MEMORY_THRESHOLD - 10)) ]]; then
        status="warning"
    fi

    # Get swap usage
    local swap_total=$(free -m | awk 'NR==3 {print $2}')
    local swap_used=$(free -m | awk 'NR==3 {print $3}')
    local swap_usage=0
    if [[ $swap_total -gt 0 ]]; then
        swap_usage=$((swap_used * 100 / swap_total))
    fi

    echo "memory:${status}:ram=${usage}%,swap=${swap_usage}%"
    [[ "$status" == "ok" ]] && return 0 || return 1
}

# Check running processes
check_process_health() {
    local process_name="$1"

    [[ "$VERBOSE" == "true" ]] && log_info "Checking process: $process_name"

    if pgrep -f "$process_name" > /dev/null; then
        local pid=$(pgrep -f "$process_name" | head -1)
        local cpu=$(ps -p $pid -o %cpu= 2>/dev/null | tr -d ' ')
        local mem=$(ps -p $pid -o %mem= 2>/dev/null | tr -d ' ')

        echo "process:ok:pid=${pid},cpu=${cpu:-0}%,mem=${mem:-0}%"
        return 0
    else
        echo "process:failed:not_running"
        return 1
    fi
}

# Output results as JSON
output_json() {
    local results=("$@")

    echo "{"
    echo "  \"timestamp\": \"$(date -Iseconds)\","
    echo "  \"hostname\": \"$(hostname)\","
    echo "  \"app_name\": \"${APP_NAME}\","
    echo "  \"checks\": {"

    local first=true
    for result in "${results[@]}"; do
        local check=$(echo $result | cut -d: -f1)
        local status=$(echo $result | cut -d: -f2)
        local details=$(echo $result | cut -d: -f3-)

        [[ "$first" == "false" ]] && echo ","
        first=false

        echo -n "    \"${check}\": {\"status\": \"${status}\", \"details\": \"${details}\"}"
    done

    echo ""
    echo "  }"
    echo "}"
}

# Output results as text
output_text() {
    local results=("$@")
    local overall="healthy"

    echo "=== Health Check Report ==="
    echo "Timestamp: $(date)"
    echo "Hostname: $(hostname)"
    echo "App: ${APP_NAME}"
    echo ""

    for result in "${results[@]}"; do
        local check=$(echo $result | cut -d: -f1)
        local status=$(echo $result | cut -d: -f2)
        local details=$(echo $result | cut -d: -f3-)

        local icon="[OK]"
        if [[ "$status" == "failed" || "$status" == "critical" ]]; then
            icon="[FAIL]"
            overall="unhealthy"
        elif [[ "$status" == "warning" ]]; then
            icon="[WARN]"
        fi

        printf "%-12s %s %s\n" "$check" "$icon" "$details"
    done

    echo ""
    echo "Overall Status: $overall"

    [[ "$overall" == "healthy" ]] && return 0 || return 1
}

# Main health check function
main() {
    parse_health_args "$@"
    load_config

    local results=()
    local exit_code=0

    # Run health checks
    if [[ "$CHECK_HTTP" == "true" ]]; then
        local http_result=$(check_http_health "$PRODUCTION_HOST")
        results+=("$http_result")
        [[ "$http_result" == *":failed:"* || "$http_result" == *":critical:"* ]] && exit_code=1
    fi

    if [[ "$CHECK_DATABASE" == "true" ]]; then
        local db_result=$(check_database_health)
        results+=("$db_result")
        [[ "$db_result" == *":failed:"* || "$db_result" == *":critical:"* ]] && exit_code=1
    fi

    if [[ "$CHECK_DISK" == "true" ]]; then
        local disk_result=$(check_disk_health)
        results+=("$disk_result")
        [[ "$disk_result" == *":failed:"* || "$disk_result" == *":critical:"* ]] && exit_code=1
    fi

    if [[ "$CHECK_MEMORY" == "true" ]]; then
        local mem_result=$(check_memory_health)
        results+=("$mem_result")
        [[ "$mem_result" == *":failed:"* || "$mem_result" == *":critical:"* ]] && exit_code=1
    fi

    # Output results
    if [[ "$OUTPUT_FORMAT" == "json" ]]; then
        output_json "${results[@]}"
    else
        output_text "${results[@]}"
    fi

    # Send alert if unhealthy
    if [[ $exit_code -ne 0 ]]; then
        notify_slack "Health check FAILED for ${APP_NAME}!" "danger"
    fi

    return $exit_code
}

# Run main function
main "$@"
