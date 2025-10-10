"""TheAuditor utilities package."""

from .constants import (
    PF_DIR,
    ERROR_LOG_FILE,
    PIPELINE_LOG_FILE,
    RAW_DIR,
    READTHIS_DIR,
    DATABASE_FILE,
    DEFAULT_MEMORY_LIMIT_MB,
    MIN_MEMORY_LIMIT_MB,
    MAX_MEMORY_LIMIT_MB,
    MEMORY_ALLOCATION_RATIO,
    ENV_MEMORY_LIMIT,
)
from .error_handler import handle_exceptions
from .exit_codes import ExitCodes
from .helpers import (
    compute_file_hash,
    load_json_file,
    save_json_file,
    count_lines_in_file,
    extract_data_array,
    get_self_exclusion_patterns,
)
from .logger import setup_logger
from .memory import get_recommended_memory_limit, get_available_memory
from .temp_manager import TempManager, get_project_temp_dir, cleanup_project_temp
from .finding_priority import (
    normalize_severity,
    get_sort_key,
    sort_findings,
    PRIORITY_ORDER,
    TOOL_IMPORTANCE,
    SEVERITY_MAPPINGS,
)

__all__ = [
    # Constants
    "PF_DIR",
    "ERROR_LOG_FILE",
    "PIPELINE_LOG_FILE",
    "RAW_DIR",
    "READTHIS_DIR",
    "DATABASE_FILE",
    "DEFAULT_MEMORY_LIMIT_MB",
    "MIN_MEMORY_LIMIT_MB",
    "MAX_MEMORY_LIMIT_MB",
    "MEMORY_ALLOCATION_RATIO",
    "ENV_MEMORY_LIMIT",
    # Error handling
    "handle_exceptions",
    "ExitCodes",
    # File operations
    "compute_file_hash",
    "load_json_file",
    "save_json_file",
    "count_lines_in_file",
    "extract_data_array",
    "get_self_exclusion_patterns",
    # Logging
    "setup_logger",
    # Memory management
    "get_recommended_memory_limit",
    "get_available_memory",
    # Temp file management
    "TempManager",
    "get_project_temp_dir",
    "cleanup_project_temp",
    # Finding prioritization
    "normalize_severity",
    "get_sort_key",
    "sort_findings",
    "PRIORITY_ORDER",
    "TOOL_IMPORTANCE",
    "SEVERITY_MAPPINGS",
]