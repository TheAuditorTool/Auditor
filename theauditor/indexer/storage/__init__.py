"""Storage layer: Domain-specific handler modules."""

import os
from typing import Any

from .bash_storage import BashStorage
from .core_storage import CoreStorage
from .go_storage import GoStorage
from .infrastructure_storage import InfrastructureStorage
from .node_storage import NodeStorage
from .python_storage import PythonStorage
from .rust_storage import RustStorage
from theauditor.utils.logging import logger


class DataStorer:
    """Main storage orchestrator - aggregates domain-specific handlers."""

    def __init__(self, db_manager, counts: dict[str, int]):
        """Initialize DataStorer with database manager and counts dict."""
        self.db_manager = db_manager
        self.counts = counts

        self.core = CoreStorage(db_manager, counts)
        self.python = PythonStorage(db_manager, counts)
        self.node = NodeStorage(db_manager, counts)
        self.go = GoStorage(db_manager, counts)
        self.rust = RustStorage(db_manager, counts)
        self.bash = BashStorage(db_manager, counts)
        self.infrastructure = InfrastructureStorage(db_manager, counts)

        self.handlers = {
            **self.core.handlers,
            **self.python.handlers,
            **self.node.handlers,
            **self.go.handlers,
            **self.rust.handlers,
            **self.bash.handlers,
            **self.infrastructure.handlers,
        }

    def store(
        self, file_path: str, extracted: dict[str, Any], jsx_pass: bool = False
    ) -> dict[str, int]:
        """Store extracted data via domain-specific handlers."""

        self._current_extracted = extracted

        self.core._current_extracted = extracted
        self.python._current_extracted = extracted
        self.node._current_extracted = extracted
        self.go._current_extracted = extracted
        self.rust._current_extracted = extracted
        self.bash._current_extracted = extracted
        self.infrastructure._current_extracted = extracted

        jsx_only_types = {
            "symbols",
            "assignments",
            "function_calls",
            "returns",
            "cfg",
            "assignment_source_vars",
            "return_source_vars",
        }

        receipt = {}

        for data_type, data in extracted.items():
            if data_type.startswith("_"):
                continue

            if jsx_pass and data_type not in jsx_only_types:
                continue

            handler = self.handlers.get(data_type)
            if handler:
                handler(file_path, data, jsx_pass)

                if isinstance(data, list):
                    receipt[data_type] = len(data)
                else:
                    receipt[data_type] = 1 if data else 0
            else:
                logger.debug(f"No handler for data type: {data_type}")

        return receipt


__all__ = ["DataStorer"]
