"""Centralized constants for TheAuditor utils package.

This module provides a single source of truth for paths, directories,
and configuration values used across utility modules.
"""

from pathlib import Path

# ============================================================================
# OUTPUT DIRECTORIES
# ============================================================================

# Primary output directory for all TheAuditor artifacts
PF_DIR = Path("./.pf")

# Log files
ERROR_LOG_FILE = PF_DIR / "error.log"
PIPELINE_LOG_FILE = PF_DIR / "pipeline.log"

# Output subdirectories
RAW_DIR = PF_DIR / "raw"
READTHIS_DIR = PF_DIR / "readthis"
DATABASE_FILE = PF_DIR / "repo_index.db"

# ============================================================================
# MEMORY CONFIGURATION
# ============================================================================

# Default memory limits (in MB)
DEFAULT_MEMORY_LIMIT_MB = 12000  # 12GB fallback
MIN_MEMORY_LIMIT_MB = 2000       # 2GB minimum
MAX_MEMORY_LIMIT_MB = 48000      # 48GB maximum

# Memory allocation percentage (60% of system RAM)
MEMORY_ALLOCATION_RATIO = 0.60

# ============================================================================
# FILE PROCESSING LIMITS
# ============================================================================

# Maximum file size to analyze (default: 2MB)
DEFAULT_MAX_FILE_SIZE = 2 * 1024 * 1024

# Maximum chunk size for readthis output (default: 65KB)
DEFAULT_MAX_CHUNK_SIZE = 65 * 1024

# Maximum chunks per file (default: 3)
DEFAULT_MAX_CHUNKS_PER_FILE = 3

# ============================================================================
# ENVIRONMENT VARIABLES
# ============================================================================

# Environment variable names for configuration
ENV_MEMORY_LIMIT = "THEAUDITOR_MEMORY_LIMIT_MB"
ENV_MAX_FILE_SIZE = "THEAUDITOR_LIMITS_MAX_FILE_SIZE"
ENV_MAX_CHUNK_SIZE = "THEAUDITOR_LIMITS_MAX_CHUNK_SIZE"
ENV_MAX_CHUNKS = "THEAUDITOR_LIMITS_MAX_CHUNKS_PER_FILE"
ENV_DB_BATCH_SIZE = "THEAUDITOR_DB_BATCH_SIZE"
ENV_DEBUG = "THEAUDITOR_DEBUG"
