"""Boundary Analysis Module."""

from theauditor.boundaries.chain_tracer import (
    ChainHop,
    ValidationChain,
    detect_validation_in_chain,
    detect_validation_library,
    get_validation_output_info,
    is_type_safe_validation,
    is_type_unsafe,
    trace_validation_chain,
    trace_validation_chains,
)
from theauditor.boundaries.distance import (
    calculate_distance,
    find_all_paths_to_controls,
    measure_boundary_quality,
)
from theauditor.boundaries.security_audit import (
    AUDIT_CATEGORIES,
    AuditFinding,
    AuditResult,
    SecurityAuditReport,
    check_database_safety,
    check_file_safety,
    check_output_sanitization,
    format_security_audit,
    run_security_audit,
)

__all__ = [
    # Distance analysis
    "calculate_distance",
    "find_all_paths_to_controls",
    "measure_boundary_quality",
    # Validation chain tracing
    "ChainHop",
    "ValidationChain",
    "is_type_unsafe",
    "trace_validation_chain",
    "trace_validation_chains",
    # Validation source detection
    "detect_validation_library",
    "detect_validation_in_chain",
    "get_validation_output_info",
    "is_type_safe_validation",
    # Security audit
    "AUDIT_CATEGORIES",
    "AuditFinding",
    "AuditResult",
    "SecurityAuditReport",
    "run_security_audit",
    "format_security_audit",
    "check_output_sanitization",
    "check_database_safety",
    "check_file_safety",
]
