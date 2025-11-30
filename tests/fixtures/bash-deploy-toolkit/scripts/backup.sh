#!/bin/bash
# Backup script for application data
# Usage: ./scripts/backup.sh [options]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Source libraries
. "$SCRIPT_DIR/lib/common.sh"
. "$SCRIPT_DIR/lib/database.sh"

# Backup options
BACKUP_DATABASE=false
BACKUP_FILES=false
BACKUP_LOGS=false
UPLOAD_TO_S3=false
RETENTION_DAYS=30

# Parse arguments
parse_backup_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --database|-d)
                BACKUP_DATABASE=true
                ;;
            --files|-f)
                BACKUP_FILES=true
                ;;
            --logs|-l)
                BACKUP_LOGS=true
                ;;
            --all|-a)
                BACKUP_DATABASE=true
                BACKUP_FILES=true
                BACKUP_LOGS=true
                ;;
            --upload-s3)
                UPLOAD_TO_S3=true
                ;;
            --retention)
                RETENTION_DAYS="$2"
                shift
                ;;
            --help|-h)
                show_backup_help
                exit 0
                ;;
            *)
                log_warn "Unknown option: $1"
                ;;
        esac
        shift
    done

    # Default to all if nothing specified
    if [[ "$BACKUP_DATABASE" == "false" && "$BACKUP_FILES" == "false" && "$BACKUP_LOGS" == "false" ]]; then
        BACKUP_DATABASE=true
        BACKUP_FILES=true
    fi
}

show_backup_help() {
    echo "Backup Script"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -d, --database      Backup database"
    echo "  -f, --files         Backup application files"
    echo "  -l, --logs          Backup log files"
    echo "  -a, --all           Backup everything"
    echo "  --upload-s3         Upload to S3 after backup"
    echo "  --retention DAYS    Keep backups for N days (default: 30)"
    echo "  -h, --help          Show this help"
}

# Create backup directory structure
setup_backup_dir() {
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_path="${BACKUP_DIR}/${timestamp}"

    mkdir -p $backup_path/{database,files,logs}
    echo $backup_path
}

# Backup database
do_database_backup() {
    local backup_path="$1"

    log_info "Backing up database..."

    local db_backup_file="${backup_path}/database/${DB_NAME}_$(date +%Y%m%d_%H%M%S).sql.gz"

    # Use pg_dump with password from environment
    PGPASSWORD="$DB_PASSWORD" pg_dump \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -Fc \
        "$DB_NAME" | gzip > $db_backup_file

    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        local size=$(du -h $db_backup_file | cut -f1)
        log_info "Database backup complete: $db_backup_file ($size)"
        echo $db_backup_file
    else
        log_error "Database backup failed!"
        return 1
    fi
}

# Backup application files
do_files_backup() {
    local backup_path="$1"

    log_info "Backing up application files..."

    local files_backup="${backup_path}/files/${APP_NAME}_files_$(date +%Y%m%d_%H%M%S).tar.gz"

    # Backup current release
    if [[ -d "${APP_DIR}/current" ]]; then
        tar -czf $files_backup \
            --exclude='*.log' \
            --exclude='node_modules' \
            --exclude='__pycache__' \
            --exclude='.git' \
            -C "${APP_DIR}" current

        local size=$(du -h $files_backup | cut -f1)
        log_info "Files backup complete: $files_backup ($size)"
        echo $files_backup
    else
        log_warn "Application directory not found: ${APP_DIR}/current"
    fi

    # Backup uploads/user data
    if [[ -d "${APP_DIR}/shared/uploads" ]]; then
        local uploads_backup="${backup_path}/files/${APP_NAME}_uploads_$(date +%Y%m%d_%H%M%S).tar.gz"
        tar -czf $uploads_backup -C "${APP_DIR}/shared" uploads
        log_info "Uploads backup complete: $uploads_backup"
    fi
}

# Backup log files
do_logs_backup() {
    local backup_path="$1"

    log_info "Backing up log files..."

    local logs_backup="${backup_path}/logs/${APP_NAME}_logs_$(date +%Y%m%d_%H%M%S).tar.gz"

    if [[ -d "$LOG_DIR" ]]; then
        # Only backup logs from last 7 days
        find $LOG_DIR -name "*.log" -mtime -7 -print0 | \
            tar -czvf $logs_backup --null -T -

        local size=$(du -h $logs_backup | cut -f1)
        log_info "Logs backup complete: $logs_backup ($size)"
        echo $logs_backup
    else
        log_warn "Log directory not found: $LOG_DIR"
    fi
}

# Upload backup to S3
upload_to_s3() {
    local backup_path="$1"

    log_info "Uploading backup to S3..."

    # Configure AWS credentials
    export AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY"
    export AWS_SECRET_ACCESS_KEY="$AWS_SECRET_KEY"

    local s3_path="s3://${S3_BUCKET}/backups/${APP_NAME}/$(basename $backup_path)"

    # Sync entire backup directory
    aws s3 sync $backup_path $s3_path --only-show-errors

    if [[ $? -eq 0 ]]; then
        log_info "Upload complete: $s3_path"
    else
        log_error "S3 upload failed!"
        return 1
    fi
}

# Cleanup old backups
cleanup_old_backups() {
    local retention_days="$1"

    log_info "Cleaning up backups older than $retention_days days..."

    # Local cleanup
    find $BACKUP_DIR -type d -mtime +$retention_days -exec rm -rf {} + 2>/dev/null

    # S3 cleanup (using lifecycle rules is better, but this works)
    if [[ "$UPLOAD_TO_S3" == "true" ]]; then
        local cutoff_date=$(date -d "-${retention_days} days" +%Y-%m-%d)

        aws s3 ls "s3://${S3_BUCKET}/backups/${APP_NAME}/" | while read -r line; do
            local folder_date=$(echo $line | awk '{print $1}')
            local folder_name=$(echo $line | awk '{print $2}')

            if [[ "$folder_date" < "$cutoff_date" ]]; then
                log_info "Deleting old backup: $folder_name"
                aws s3 rm "s3://${S3_BUCKET}/backups/${APP_NAME}/${folder_name}" --recursive
            fi
        done
    fi

    log_info "Cleanup complete"
}

# Create backup manifest
create_manifest() {
    local backup_path="$1"

    log_info "Creating backup manifest..."

    cat > "${backup_path}/manifest.json" << EOF
{
    "app_name": "${APP_NAME}",
    "backup_date": "$(date -Iseconds)",
    "backup_host": "$(hostname)",
    "database_backup": ${BACKUP_DATABASE},
    "files_backup": ${BACKUP_FILES},
    "logs_backup": ${BACKUP_LOGS},
    "files": [
$(find $backup_path -type f -name "*.gz" -o -name "*.sql" | while read f; do
    echo "        \"$(basename $f)\","
done | sed '$ s/,$//')
    ]
}
EOF

    log_info "Manifest created: ${backup_path}/manifest.json"
}

# Main backup function
main() {
    parse_backup_args "$@"
    load_config

    log_info "Starting backup process..."
    log_info "Options: database=$BACKUP_DATABASE, files=$BACKUP_FILES, logs=$BACKUP_LOGS"

    # Create backup directory
    local backup_path=$(setup_backup_dir)
    log_info "Backup directory: $backup_path"

    # Track backup files
    local backup_files=()

    # Backup database
    if [[ "$BACKUP_DATABASE" == "true" ]]; then
        local db_file=$(do_database_backup $backup_path)
        if [[ -n "$db_file" ]]; then
            backup_files+=("$db_file")
        fi
    fi

    # Backup files
    if [[ "$BACKUP_FILES" == "true" ]]; then
        local files_result=$(do_files_backup $backup_path)
        if [[ -n "$files_result" ]]; then
            backup_files+=("$files_result")
        fi
    fi

    # Backup logs
    if [[ "$BACKUP_LOGS" == "true" ]]; then
        local logs_file=$(do_logs_backup $backup_path)
        if [[ -n "$logs_file" ]]; then
            backup_files+=("$logs_file")
        fi
    fi

    # Create manifest
    create_manifest $backup_path

    # Upload to S3 if requested
    if [[ "$UPLOAD_TO_S3" == "true" ]]; then
        upload_to_s3 $backup_path
    fi

    # Cleanup old backups
    cleanup_old_backups $RETENTION_DAYS

    # Calculate total backup size
    local total_size=$(du -sh $backup_path | cut -f1)

    log_info "Backup complete!"
    log_info "Location: $backup_path"
    log_info "Total size: $total_size"
    log_info "Files backed up: ${#backup_files[@]}"

    # Send notification
    notify_slack "Backup completed for ${APP_NAME}. Size: ${total_size}" "good"
}

# Run main function
main "$@"
