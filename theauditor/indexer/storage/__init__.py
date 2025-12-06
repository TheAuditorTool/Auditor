"""Storage layer: Domain-specific handler modules."""

from typing import Any

from theauditor.utils.logging import logger

from ..fidelity_utils import FidelityToken
from .bash_storage import BashStorage
from .core_storage import CoreStorage
from .go_storage import GoStorage
from .infrastructure_storage import InfrastructureStorage
from .node_storage import NodeStorage
from .python_storage import PythonStorage
from .rust_storage import RustStorage

PRIORITY_ORDER = [
    "react_hooks",
    "react_hook_dependencies",
    "vue_components",
    "vue_component_props",
    "vue_component_emits",
    "vue_component_setup_returns",
    "angular_modules",
    "angular_module_declarations",
    "angular_module_imports",
    "angular_module_providers",
    "angular_module_exports",
    "angular_components",
    "angular_component_styles",
    "cdk_constructs",
    "cdk_construct_properties",
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
        self.rust = RustStorage(db_manager, counts)
        self.go = GoStorage(db_manager, counts)
        self.bash = BashStorage(db_manager, counts)

        self.handlers = {
            **self.core.handlers,
            **self.python.handlers,
            **self.node.handlers,
            **self.infrastructure.handlers,
            **self.rust.handlers,
            **self.go.handlers,
            **self.bash.handlers,
        }

    def store(
        self, file_path: str, extracted: dict[str, Any], jsx_pass: bool = False
    ) -> dict[str, int]:
        """Store extracted data via domain-specific handlers.

        Uses PRIORITY_ORDER to ensure parents are processed before children,
        enabling gatekeeper sets to be populated before child validation.
        """

        file_path = file_path.replace("\\", "/")

        self.core.begin_file_processing()
        self.python.begin_file_processing()
        self.node.begin_file_processing()
        self.infrastructure.begin_file_processing()
        self.rust.begin_file_processing()
        self.go.begin_file_processing()
        self.bash.begin_file_processing()

        self._current_extracted = extracted

        self.core._current_extracted = extracted
        self.python._current_extracted = extracted
        self.node._current_extracted = extracted
        self.infrastructure._current_extracted = extracted
        self.rust._current_extracted = extracted
        self.go._current_extracted = extracted
        self.bash._current_extracted = extracted

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

                manifest = extracted.get("_extraction_manifest", {})
                table_manifest = manifest.get(data_type, {})
                tx_id = table_manifest.get("tx_id") if isinstance(table_manifest, dict) else None

                if isinstance(data, list):
                    if len(data) > 0 and isinstance(data[0], dict):
                        columns = sorted(data[0].keys())
                        data_bytes = sum(len(str(v)) for row in data for v in row.values())
                        receipt[data_type] = FidelityToken.create_receipt(
                            count=len(data), columns=columns, tx_id=tx_id, data_bytes=data_bytes
                        )
                    else:
                        receipt[data_type] = FidelityToken.create_receipt(
                            count=len(data), columns=[], tx_id=tx_id, data_bytes=0
                        )
                elif isinstance(data, dict):
                    receipt[data_type] = FidelityToken.create_receipt(
                        count=len(data),
                        columns=sorted(data.keys()) if data else [],
                        tx_id=tx_id,
                        data_bytes=len(str(data)),
                    )
                else:
                    receipt[data_type] = FidelityToken.create_receipt(
                        count=1 if data else 0,
                        columns=[],
                        tx_id=tx_id,
                        data_bytes=len(str(data)) if data else 0,
                    )
            else:
                logger.warning(f"No handler for data type '{data_type}' - data dropped")

        for priority_key in PRIORITY_ORDER:
            if priority_key in extracted:
                process_key(priority_key, extracted[priority_key])

        priority_set = set(PRIORITY_ORDER)
        for data_type, data in extracted.items():
            if data_type not in priority_set:
                process_key(data_type, data)

        return receipt


__all__ = ["DataStorer"]
