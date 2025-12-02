# Server Deploy Toolkit

A collection of bash scripts for deploying and managing web applications.

## Features

- Zero-downtime deployments with health checks
- Database migrations with automatic rollback
- Automated backups with rotation
- Service health monitoring
- Log aggregation and rotation

## Quick Start

```bash
# Configure your deployment
cp config/deploy.conf.example config/deploy.conf
vim config/deploy.conf

# Deploy to staging
./deploy.sh staging

# Deploy to production
./deploy.sh production --with-backup

# Check service health
./scripts/healthcheck.sh --all

# Manual backup
./scripts/backup.sh --database --files

# Rollback to previous version
./scripts/rollback.sh production
```

## Directory Structure

```
bash-deploy-toolkit/
├── deploy.sh           # Main deployment script
├── config/
│   └── deploy.conf     # Deployment configuration
├── lib/
│   ├── common.sh       # Shared functions
│   └── database.sh     # Database operations
└── scripts/
    ├── backup.sh       # Backup script
    ├── healthcheck.sh  # Health monitoring
    └── rollback.sh     # Rollback script
```

## Requirements

- Bash 4.0+
- curl, jq, rsync
- PostgreSQL client (for database operations)
- SSH access to target servers

## License

MIT
