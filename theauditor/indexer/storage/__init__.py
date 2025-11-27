"""Storage layer: Domain-specific handler modules.

This module provides the DataStorer class that dispatches extracted data
to domain-specific storage modules (core, python, node, infrastructure).

Architecture:
- DataStorer: Main orchestrator, delegates to domain modules
- BaseStorage: Shared logic (db_manager, counts, _current_extracted)
- CoreStorage: Language-agnostic handlers (symbols, cfg, assignments)
- PythonStorage: Python framework handlers (django, flask, pytest)
- NodeStorage: JavaScript framework handlers (react, vue, angular)
- InfrastructureStorage: IaC handlers (terraform, cdk, graphql)

Design Pattern:
- Handler dispatch via registry dict (data_type -> handler method)
- Domain modules inherit from BaseStorage
- DataStorer aggregates all domain handlers into unified registry

Usage:
    from theauditor.indexer.storage import DataStorer
    storer = DataStorer(db_manager, counts)
    storer.store(file_path, extracted, jsx_pass=False)
"""

import os
from typing import Any, Dict
from .core_storage import CoreStorage
from .python_storage import PythonStorage
from .node_storage import NodeStorage
from .infrastructure_storage import InfrastructureStorage


class DataStorer:
    """Main storage orchestrator - aggregates domain-specific handlers.

    ARCHITECTURE:
    - Single entry point: store(file_path, extracted, jsx_pass)
    - Handler map: data_type -> handler method
    - Each handler: 10-40 lines, focused, testable

    CRITICAL: Assumes db_manager and counts are provided by orchestrator.
    DO NOT instantiate directly - only used by IndexerOrchestrator.
    """

    def __init__(self, db_manager, counts: dict[str, int]):
        """Initialize DataStorer with database manager and counts dict.

        Args:
            db_manager: DatabaseManager instance from orchestrator
            counts: Shared counts dictionary for statistics tracking
        """
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
    ) -> Dict[str, int]:
        """Store extracted data via domain-specific handlers.

        Args:
            file_path: Path to the file being indexed
            extracted: Dictionary of extracted data (data_type -> data list)
            jsx_pass: True if this is JSX preserved mode (second pass)

        Returns:
            Receipt dict mapping data_type -> count of items passed to handlers.
            Used by fidelity control to verify no data loss.
        """

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
                if os.environ.get("THEAUDITOR_DEBUG"):
                    print(f"[DEBUG] No handler for data type: {data_type}")

        return receipt


__all__ = ["DataStorer"]
