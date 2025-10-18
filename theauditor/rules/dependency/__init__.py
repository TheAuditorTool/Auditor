"""Dependency analysis and package security rules."""

from .ghost_dependencies import analyze as detect_ghost_dependencies
from .unused_dependencies import analyze as detect_unused_dependencies
from .suspicious_versions import analyze as detect_suspicious_versions
from .typosquatting import analyze as detect_typosquatting
from .version_pinning import analyze as detect_version_pinning
from .dependency_bloat import analyze as detect_dependency_bloat
from .update_lag import analyze as detect_update_lag
from .peer_conflicts import analyze as detect_peer_conflicts
from .bundle_size import analyze as detect_bundle_size

__all__ = [
    "detect_ghost_dependencies",
    "detect_unused_dependencies",
    "detect_suspicious_versions",
    "detect_typosquatting",
    "detect_version_pinning",
    "detect_dependency_bloat",
    "detect_update_lag",
    "detect_peer_conflicts",
    "detect_bundle_size"
]
