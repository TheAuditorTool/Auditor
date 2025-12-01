"""TheAuditor utilities package."""

from .constants import (
    DATABASE_FILE,
    DEFAULT_MEMORY_LIMIT_MB,
    ENV_MEMORY_LIMIT,
    ERROR_LOG_FILE,
    MAX_MEMORY_LIMIT_MB,
    MEMORY_ALLOCATION_RATIO,
    MIN_MEMORY_LIMIT_MB,
    PF_DIR,
    PIPELINE_LOG_FILE,
    RAW_DIR,
)
from .error_handler import handle_exceptions
from .exit_codes import ExitCodes
from .finding_priority import (
    PRIORITY_ORDER,
    SEVERITY_MAPPINGS,
    TOOL_IMPORTANCE,
    get_sort_key,
    normalize_severity,
    sort_findings,
)
from .helpers import (
    compute_file_hash,
    count_lines_in_file,
    extract_data_array,
    get_self_exclusion_patterns,
    load_json_file,
    save_json_file,
)
from .logging import logger
from .memory import get_available_memory, get_recommended_memory_limit
from .temp_manager import TempManager, cleanup_project_temp, get_project_temp_dir

__all__ = [
    "PF_DIR",
    "ERROR_LOG_FILE",
    "PIPELINE_LOG_FILE",
    "RAW_DIR",
    "DATABASE_FILE",
    "DEFAULT_MEMORY_LIMIT_MB",
    "MIN_MEMORY_LIMIT_MB",
    "MAX_MEMORY_LIMIT_MB",
    "MEMORY_ALLOCATION_RATIO",
    "ENV_MEMORY_LIMIT",
    "handle_exceptions",
    "ExitCodes",
    "compute_file_hash",
    "load_json_file",
    "save_json_file",
    "count_lines_in_file",
    "extract_data_array",
    "get_self_exclusion_patterns",
    "logger",
    "get_recommended_memory_limit",
    "get_available_memory",
    "TempManager",
    "get_project_temp_dir",
    "cleanup_project_temp",
    "normalize_severity",
    "get_sort_key",
    "sort_findings",
    "PRIORITY_ORDER",
    "TOOL_IMPORTANCE",
    "SEVERITY_MAPPINGS",
]
