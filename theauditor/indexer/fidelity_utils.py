"""Fidelity utilities for creating transaction tokens.

Shared between Extractors (Manifests) and Storage (Receipts).
Enables transactional integrity verification beyond simple counts.
"""

import uuid
from typing import Any


class FidelityToken:
    """Standardizes fidelity manifest and receipt creation."""

    @staticmethod
    def create_manifest(data: Any) -> dict[str, Any] | None:
        """Generate manifest token from extractor data.

        Polymorphic: handles both lists (standard rows) and dicts (K/V pairs).

        Args:
            data: List of dictionaries OR a dict of key-value pairs.

        Returns:
            Dict with tx_id, columns, count, bytes for fidelity checking.
            None if data type is unsupported.
        """

        if isinstance(data, list):
            if not data:
                return {"count": 0, "columns": [], "tx_id": None, "bytes": 0}

            first_row = data[0]
            if isinstance(first_row, dict):
                return {
                    "count": len(data),
                    "tx_id": str(uuid.uuid4()),
                    "columns": sorted(first_row.keys()),
                    "bytes": sum(len(str(v)) for row in data for v in row.values()),
                }
            else:
                return {"count": len(data), "columns": [], "tx_id": None, "bytes": 0}

        elif isinstance(data, dict):
            return {
                "count": len(data),
                "tx_id": str(uuid.uuid4()),
                "columns": [],
                "bytes": sum(len(str(k)) + len(str(v)) for k, v in data.items()),
            }

        return None

    @staticmethod
    def create_receipt(
        count: int, columns: list[str], tx_id: str | None, data_bytes: int = 0
    ) -> dict[str, Any]:
        """Generate receipt token from storage operation.

        Args:
            count: Number of rows inserted
            columns: Column names actually written
            tx_id: Transaction ID from manifest (echoed back)
            data_bytes: Approximate byte size of data written

        Returns:
            Dict matching manifest structure for comparison.
        """
        return {"count": count, "columns": sorted(columns), "tx_id": tx_id, "bytes": data_bytes}

    @staticmethod
    def attach_manifest(extracted_data: dict[str, Any]) -> dict[str, Any]:
        """Attach manifest to extraction result (one-liner for extractors).

        Polymorphic: handles both lists and dicts automatically.
        Usage: return FidelityToken.attach_manifest(result)
        """
        from datetime import datetime

        manifest = {}
        total_items = 0

        for key, value in extracted_data.items():
            if key.startswith("_"):
                continue

            token = FidelityToken.create_manifest(value)
            if token:
                manifest[key] = token
                total_items += token.get("count", 0)

        manifest["_total"] = total_items
        manifest["_timestamp"] = datetime.utcnow().isoformat()

        extracted_data["_extraction_manifest"] = manifest
        return extracted_data
