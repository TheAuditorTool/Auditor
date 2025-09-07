"""TheAuditor utilities package."""

from .error_handler import handle_exceptions
from .exit_codes import ExitCodes
from .helpers import (
    compute_file_hash,
    load_json_file,
    save_json_file,
    count_lines_in_file,
    extract_data_array,
)

__all__ = [
    "handle_exceptions",
    "ExitCodes",
    "compute_file_hash",
    "load_json_file",
    "save_json_file",
    "count_lines_in_file",
    "extract_data_array",
]