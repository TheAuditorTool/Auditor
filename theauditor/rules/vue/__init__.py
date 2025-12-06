"""Vue.js-specific rule detectors for TheAuditor."""

from .component_analyze import METADATA as component_metadata
from .component_analyze import analyze as component_analyze
from .hooks_analyze import METADATA as hooks_metadata
from .hooks_analyze import analyze as hooks_analyze
from .lifecycle_analyze import METADATA as lifecycle_metadata
from .lifecycle_analyze import analyze as lifecycle_analyze
from .reactivity_analyze import METADATA as reactivity_metadata
from .reactivity_analyze import analyze as reactivity_analyze
from .render_analyze import METADATA as render_metadata
from .render_analyze import analyze as render_analyze
from .state_analyze import METADATA as state_metadata
from .state_analyze import analyze as state_analyze

__all__ = [
    "component_analyze",
    "component_metadata",
    "hooks_analyze",
    "hooks_metadata",
    "lifecycle_analyze",
    "lifecycle_metadata",
    "reactivity_analyze",
    "reactivity_metadata",
    "render_analyze",
    "render_metadata",
    "state_analyze",
    "state_metadata",
]
