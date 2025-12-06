#!/bin/bash
# Main deployment script for web application
# Usage: ./deploy.sh <environment> [options]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source libraries
. "$SCRIPT_DIR/lib/common.sh"
. "$SCRIPT_DIR/lib/database.sh"

# Default options
WITH_BACKUP=false
SKIP_MIGRATIONS=false
FORCE_DEPLOY=false
BRANCH="main"

# Parse command line arguments
parse_args() {
    if [[ $# -lt 1 ]]; then
        echo "Usage: $0 <environment> [options]"
        echo ""
        echo "Environments: staging, production, dev"
        echo ""
        echo "Options:"
        echo "  --with-backup       Create backup before deploy"
        echo "  --skip-migrations   Skip database migrations"
        echo "  --force             Force deploy even if checks fail"
        echo "  --branch <name>     Deploy specific branch (default: main)"
        echo ""
        exit 1
    fi

    ENVIRONMENT="$1"
    shift

    while [[ $# -gt 0 ]]; do
        case $1 in
            --with-backup)
                WITH_BACKUP=true
                ;;
            --skip-migrations)
                SKIP_MIGRATIONS=true
                ;;
            --force)
                FORCE_DEPLOY=true
                ;;
            --branch)
                BRANCH="$2"
                shift
                ;;
            *)
                log_warn "Unknown option: $1"
                ;;
        esac
        shift
    done
}

# Pre-deployment checks
pre_deploy_checks() {
    local env="$1"

    log_info "Running pre-deployment checks..."

    # Validate environment
    validate_environment "$env"

    # Check dependencies
    check_dependencies curl git rsync jq ssh

    # Check SSH connectivity
    local target_host=$(get_target_host $env)
    if ! ssh -i "$SSH_KEY" -o ConnectTimeout=5 -o StrictHostKeyChecking=no "${APP_USER}@${target_host}" "echo ok" > /dev/null 2>&1; then
        log_error "Cannot connect to $target_host"
        return 1
    fi

    # Check database connection
    if ! check_db_connection; then
        log_error "Database connection failed"
        return 1
    fi

    # Check for uncommitted changes
    if [[ $(git status --porcelain) ]]; then
        log_warn "You have uncommitted changes!"
        if [[ "$FORCE_DEPLOY" != "true" ]]; then
            return 1
        fi
    fi

    log_info "Pre-deployment checks passed"
    return 0
}

# Build application
build_app() {
    log_info "Building application..."

    local build_dir=$(create_temp_dir "build")

    # Clone repository
    git clone --depth 1 --branch $BRANCH "git@github.com:example/${APP_NAME}.git" $build_dir

    cd $build_dir

    # Install dependencies
    if [[ -f "package.json" ]]; then
        log_info "Installing Node.js dependencies..."
        npm ci --production
    elif [[ -f "requirements.txt" ]]; then
        log_info "Installing Python dependencies..."
        pip install -r requirements.txt
    elif [[ -f "Gemfile" ]]; then
        log_info "Installing Ruby dependencies..."
        bundle install --deployment
    fi

    # Run build command if exists
    if [[ -f "Makefile" ]]; then
        make build
    elif [[ -f "package.json" ]]; then
        npm run build 2>/dev/null || true
    fi

    # Create artifact
    local artifact="/tmp/${APP_NAME}_${DEPLOY_ID}.tar.gz"
    tar -czf $artifact --exclude='.git' --exclude='node_modules' --exclude='__pycache__' .

    echo $artifact
}

# Deploy to server
deploy_to_server() {
    local env="$1"
    local artifact="$2"

    local target_host=$(get_target_host $env)
    local release_dir="${APP_DIR}/releases/${DEPLOY_ID}"

    log_info "Deploying to $target_host..."

    # Create release directory
    remote_exec $target_host "mkdir -p $release_dir"

    # Upload artifact
    log_info "Uploading artifact..."
    scp -i "$SSH_KEY" $artifact "${APP_USER}@${target_host}:/tmp/"

    # Extract on server
    remote_exec $target_host "cd $release_dir && tar -xzf /tmp/$(basename $artifact)"

    # Run post-deploy scripts
    if remote_exec $target_host "test -f $release_dir/scripts/post-deploy.sh"; then
        log_info "Running post-deploy script..."
        remote_exec $target_host "cd $release_dir && chmod +x scripts/post-deploy.sh && ./scripts/post-deploy.sh"
    fi

    # Update symlink
    remote_exec $target_host "ln -sfn $release_dir ${APP_DIR}/current"

    # Restart application
    restart_app $target_host

    log_info "Deploy complete!"
}

# Restart application
restart_app() {
    local host="$1"

    log_info "Restarting application on $host..."

    # Try different service managers
    if remote_exec $host "command -v systemctl &> /dev/null"; then
        remote_exec $host "sudo systemctl restart ${APP_NAME}"
    elif remote_exec $host "command -v service &> /dev/null"; then
        remote_exec $host "sudo service ${APP_NAME} restart"
    else
        # Fallback: use custom restart script
        remote_exec $host "cd ${APP_DIR}/current && ./scripts/restart.sh"
    fi

    # Wait for service to be healthy
    local health_url="http://${host}${HEALTH_ENDPOINT}"
    if ! wait_for_healthy "$health_url" "$HEALTH_TIMEOUT"; then
        log_error "Service failed health check after restart!"
        return 1
    fi
}

# Cleanup old releases
cleanup_old_releases() {
    local host="$1"
    local keep="${2:-5}"

    log_info "Cleaning up old releases (keeping last $keep)..."

    remote_exec $host "cd ${APP_DIR}/releases && ls -t | tail -n +$((keep+1)) | xargs -r rm -rf"
}

# Main deployment function
main() {
    parse_args "$@"
    load_config

    log_info "Starting deployment to $ENVIRONMENT"
    log_info "Branch: $BRANCH"

    # Generate deployment ID
    DEPLOY_ID=$(generate_deploy_id)
    log_info "Deployment ID: $DEPLOY_ID"

    # Acquire deploy lock
    acquire_deploy_lock
    trap release_deploy_lock EXIT

    # Pre-deploy checks
    if ! pre_deploy_checks $ENVIRONMENT; then
        log_error "Pre-deployment checks failed!"
        if [[ "$FORCE_DEPLOY" != "true" ]]; then
            exit 1
        fi
        log_warn "Continuing anyway due to --force flag"
    fi

    # Create backup if requested
    if [[ "$WITH_BACKUP" == "true" ]]; then
        log_info "Creating pre-deploy backup..."
        local backup_file=$(backup_database)
        if [[ $? -ne 0 ]]; then
            log_error "Backup failed!"
            exit 1
        fi
        log_info "Backup saved to: $backup_file"
    fi

    # Build application
    local artifact=$(build_app)
    if [[ ! -f "$artifact" ]]; then
        log_error "Build failed - no artifact created"
        exit 1
    fi
    log_info "Build artifact: $artifact"

    # Run database migrations
    if [[ "$SKIP_MIGRATIONS" != "true" ]]; then
        log_info "Running database migrations..."
        if ! run_migrations; then
            log_error "Database migration failed!"
            if [[ "$ROLLBACK_ON_FAILURE" == "true" ]]; then
                log_info "Rolling back migration..."
                rollback_migration 1
            fi
            exit 1
        fi
    fi

    # Deploy to server
    if ! deploy_to_server $ENVIRONMENT $artifact; then
        log_error "Deployment failed!"

        # Notify on failure
        notify_slack "Deployment to $ENVIRONMENT FAILED! ID: $DEPLOY_ID" "danger"

        exit 1
    fi

    # Cleanup old releases
    local target_host=$(get_target_host $ENVIRONMENT)
    cleanup_old_releases $target_host 5

    # Clean up local temp files
    rm -f $artifact

    # Send success notification
    notify_slack "Deployment to $ENVIRONMENT completed successfully! ID: $DEPLOY_ID" "good"

    log_info "Deployment to $ENVIRONMENT completed successfully!"
}

# Run main function
main "$@"
