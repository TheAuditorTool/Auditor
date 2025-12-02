"""Storage layer: Domain-specific handler modules."""

import logging
from typing import Any

from .core_storage import CoreStorage
from .infrastructure_storage import InfrastructureStorage
from .node_storage import NodeStorage
from .python_storage import PythonStorage

logger = logging.getLogger(__name__)

# Priority order for parent-child relationships.
# Parents MUST be processed before their children to populate gatekeeper sets.
# Keys in this list are processed first (in order), then remaining keys.
PRIORITY_ORDER = [
    # React: hooks before dependencies
    "react_hooks",
    "react_hook_dependencies",
    # Vue: components before props/emits/setup_returns
    "vue_components",
    "vue_component_props",
    "vue_component_emits",
    "vue_component_setup_returns",
    # Angular: modules/components before children
    "angular_modules",
    "angular_module_declarations",
    "angular_module_imports",
    "angular_module_providers",
    "angular_module_exports",
    "angular_components",
    "angular_component_styles",
    # CDK: constructs before properties
    "cdk_constructs",
    "cdk_construct_properties",
    # Sequelize: models before fields/associations
    "sequelize_models",
    "sequelize_model_fields",
    "sequelize_associations",
]


class DataStorer:
    """Main storage orchestrator - aggregates domain-specific handlers."""

    def __init__(self, db_manager, counts: dict[str, int]):
        """Initialize DataStorer with database manager and counts dict."""
        self.db_manager = db_manager
        self.counts = counts

        self.core = CoreStorage(db_manager, counts)
        self.python = PythonStorage(db_manager, counts)
        self.node = NodeStorage(db_manager, counts)
        self.infrastructure = InfrastructureStorage(db_manager, counts)

        self.handlers = {
            **self.core.handlers,
            **self.python.handlers,
            **self.node.handlers,
            **self.infrastructure.handlers,
        }

    def store(
        self, file_path: str, extracted: dict[str, Any], jsx_pass: bool = False
    ) -> dict[str, int]:
        """Store extracted data via domain-specific handlers.

        Uses PRIORITY_ORDER to ensure parents are processed before children,
        enabling gatekeeper sets to be populated before child validation.
        """
        # Force POSIX paths to match 'files' table normalized format
        file_path = file_path.replace("\\", "/")

        # Reset per-file gatekeeper state in all storage engines
        self.core.begin_file_processing()
        self.python.begin_file_processing()
        self.node.begin_file_processing()
        self.infrastructure.begin_file_processing()

        self._current_extracted = extracted

        self.core._current_extracted = extracted
        self.python._current_extracted = extracted
        self.node._current_extracted = extracted
        self.infrastructure._current_extracted = extracted

        jsx_only_types = {
            "symbols",
            "assignments",
            "function_calls",
            "returns",
            "cfg",
            "cfg_blocks",
            "cfg_edges",
            "cfg_block_statements",
            "assignment_source_vars",
            "return_source_vars",
        }

        receipt = {}

        def process_key(data_type: str, data: Any) -> None:
            """Process a single data type with its handler."""
            if data_type.startswith("_"):
                return

            if jsx_pass and data_type not in jsx_only_types:
                return

            handler = self.handlers.get(data_type)
            if handler:
                handler(file_path, data, jsx_pass)

                if isinstance(data, list):
                    receipt[data_type] = len(data)
                else:
                    receipt[data_type] = 1 if data else 0
            else:
                # WARNING: Data being dropped - no handler registered
                # This exposes schema/handler mismatches immediately
                logger.warning(f"No handler for data type '{data_type}' - data dropped")

        # PASS 1: Process priority keys in order (parents before children)
        for priority_key in PRIORITY_ORDER:
            if priority_key in extracted:
                process_key(priority_key, extracted[priority_key])

        # PASS 2: Process remaining keys (not in PRIORITY_ORDER)
        priority_set = set(PRIORITY_ORDER)
        for data_type, data in extracted.items():
            if data_type not in priority_set:
                process_key(data_type, data)

        return receipt


__all__ = ["DataStorer"]
