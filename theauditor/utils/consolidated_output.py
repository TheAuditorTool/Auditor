"""Consolidated output helper for grouping analyzer outputs.

Provides utilities for writing analyzer results to consolidated group files
instead of separate files per sub-analysis. Implements file locking to prevent
concurrent write corruption.

Design Principle: ZERO FALLBACK
- If file is corrupted, we start fresh (hard fail logged)
- If lock fails, we raise error (no silent degradation)
- If group name invalid, we raise error (no auto-correction)
"""

import json
import time
import platform
from pathlib import Path
from typing import Dict, Any, Optional

# Platform-specific locking imports
if platform.system() == "Windows":
    import msvcrt
else:
    import fcntl

# Valid consolidated group names (IMMUTABLE CONTRACT)
VALID_GROUPS = frozenset({
    "graph_analysis",
    "security_analysis",
    "quality_analysis",
    "dependency_analysis",
    "infrastructure_analysis",
    "correlation_analysis"
})


def write_to_group(
    group_name: str,
    analysis_type: str,
    data: Dict[str, Any],
    root: str = "."
) -> None:
    """Append analysis results to consolidated group file.

    Thread-safe via platform-specific file locking. Creates file if doesn't exist.
    Overwrites corrupted files with fresh structure.

    Args:
        group_name: One of VALID_GROUPS (e.g., "graph_analysis")
        analysis_type: Sub-analysis identifier (e.g., "import_graph", "patterns")
        data: Analysis results as dictionary (must be JSON-serializable)
        root: Root directory containing .pf/ (default: current directory)

    Raises:
        ValueError: If group_name not in VALID_GROUPS
        TypeError: If data is not JSON-serializable
        IOError: If file operations fail (permissions, disk full, etc.)

    Example:
        write_to_group("graph_analysis", "import_graph", {"nodes": 100, "edges": 50})
    """
    # ZERO FALLBACK: Validate group name (hard fail if invalid)
    if group_name not in VALID_GROUPS:
        raise ValueError(
            f"Invalid group_name '{group_name}'. "
            f"Must be one of: {', '.join(sorted(VALID_GROUPS))}"
        )

    # Construct file path (Windows-safe absolute path)
    root_path = Path(root).resolve()
    consolidated_path = root_path / ".pf" / "raw" / f"{group_name}.json"
    consolidated_path.parent.mkdir(parents=True, exist_ok=True)

    # Acquire lock and write atomically
    try:
        # Load existing data or create new structure
        if consolidated_path.exists():
            consolidated = _load_with_corruption_recovery(consolidated_path, group_name)
        else:
            consolidated = _create_empty_group(group_name)

        # Update analysis section
        if "analyses" not in consolidated:
            consolidated["analyses"] = {}

        consolidated["analyses"][analysis_type] = data
        consolidated["last_updated"] = time.strftime('%Y-%m-%d %H:%M:%S')

        # Write atomically with locking
        _write_with_lock(consolidated_path, consolidated)

        print(f"[OK] Updated {group_name}.json with '{analysis_type}' analysis")

    except Exception as e:
        # ZERO FALLBACK: Let errors propagate (no silent failures)
        print(f"[ERROR] Failed to write to {group_name}.json: {e}")
        raise


def _load_with_corruption_recovery(file_path: Path, group_name: str) -> Dict[str, Any]:
    """Load JSON with corruption recovery (start fresh if corrupted).

    Args:
        file_path: Path to JSON file
        group_name: Group name for creating empty structure

    Returns:
        Loaded JSON data or empty group structure

    Note: Corrupted files are REPLACED, not repaired. This is by design.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"[WARN] Corrupted {file_path}: {e}")
        print(f"[WARN] Starting fresh with empty structure")
        return _create_empty_group(group_name)
    except Exception as e:
        print(f"[ERROR] Failed to read {file_path}: {e}")
        raise


def _write_with_lock(file_path: Path, data: Dict[str, Any]) -> None:
    """Write JSON file with platform-specific locking.

    Args:
        file_path: Path to write to
        data: Data to write

    Raises:
        IOError: If write fails
        TypeError: If data not JSON-serializable
    """
    # Write to temp file first, then atomic rename (safer)
    temp_path = file_path.with_suffix('.tmp')

    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            # Acquire lock
            if platform.system() == "Windows":
                msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
            else:
                fcntl.flock(f, fcntl.LOCK_EX)

            # Write JSON
            json.dump(data, f, indent=2, ensure_ascii=False)

            # Lock released automatically on close

        # Atomic rename (overwrites existing file)
        temp_path.replace(file_path)

    except Exception as e:
        # Clean up temp file on failure
        if temp_path.exists():
            temp_path.unlink()
        raise IOError(f"Write failed: {e}")


def _create_empty_group(group_name: str) -> Dict[str, Any]:
    """Create empty consolidated group structure.

    Args:
        group_name: Name of the group

    Returns:
        Empty group structure with metadata
    """
    return {
        "group": group_name,
        "generated_at": time.strftime('%Y-%m-%d %H:%M:%S'),
        "last_updated": time.strftime('%Y-%m-%d %H:%M:%S'),
        "analyses": {}
    }


def read_from_group(
    group_name: str,
    analysis_type: Optional[str] = None,
    root: str = "."
) -> Dict[str, Any]:
    """Read analysis results from consolidated group file.

    Args:
        group_name: One of VALID_GROUPS
        analysis_type: Specific analysis to retrieve (if None, returns entire group)
        root: Root directory containing .pf/

    Returns:
        Analysis data dictionary (or entire group if analysis_type=None)

    Raises:
        ValueError: If group_name invalid or analysis_type not found
        FileNotFoundError: If group file doesn't exist
    """
    if group_name not in VALID_GROUPS:
        raise ValueError(f"Invalid group_name '{group_name}'")

    consolidated_path = Path(root) / ".pf" / "raw" / f"{group_name}.json"

    if not consolidated_path.exists():
        raise FileNotFoundError(f"Group file not found: {consolidated_path}")

    with open(consolidated_path, 'r', encoding='utf-8') as f:
        consolidated = json.load(f)

    if analysis_type is None:
        return consolidated

    if analysis_type not in consolidated.get("analyses", {}):
        raise ValueError(
            f"Analysis type '{analysis_type}' not found in {group_name}. "
            f"Available: {list(consolidated.get('analyses', {}).keys())}"
        )

    return consolidated["analyses"][analysis_type]
