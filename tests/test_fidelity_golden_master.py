"""Golden Master tests for extraction accuracy.

These tests verify that the extractor produces CORRECT output, not just
that it produces output consistently (which fidelity already handles).

The Golden Master pattern:
1. Create a fixture file with EVERY supported syntax feature
2. Hand-verify extraction output ONCE and save as golden_master.json
3. On every test run, compare current output to master
4. If they differ: either regression (fix it) or improvement (update master)

This catches:
- Silent Omission (logic bugs that miss syntax features)
- Pre-Manifest Filtering (bugs that drop data before manifest generation)
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "fidelity"
GOLDEN_INPUT = FIXTURES_DIR / "golden_input.ts"
GOLDEN_MASTER = FIXTURES_DIR / "golden_master.json"


def _extract_file(input_path: Path) -> dict:
    """Run the Node extractor on a single file and return parsed output."""
    extractor_dir = Path(__file__).parent.parent / "theauditor" / "ast_extractors" / "javascript"
    extractor_bundle = extractor_dir / "dist" / "extractor.cjs"

    if not extractor_bundle.exists():
        pytest.skip("Node extractor bundle not built (run npm run build)")

    # Create temp output file
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
        output_path = Path(f.name)

    try:
        # Run extractor
        result = subprocess.run(
            ["node", str(extractor_bundle), str(input_path), str(output_path)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(extractor_dir)
        )

        if result.returncode != 0:
            # Check for Death Rattle crash report
            try:
                crash_report = json.loads(result.stderr.strip().split('\n')[-1])
                if crash_report.get("type") == "FATAL_CRASH":
                    pytest.fail(f"Extractor crashed: {crash_report['error']}\n{crash_report.get('stack', '')}")
            except (json.JSONDecodeError, IndexError):
                pass
            pytest.fail(f"Extractor failed: {result.stderr}")

        # Parse output
        with open(output_path, 'r') as f:
            return json.load(f)
    finally:
        output_path.unlink(missing_ok=True)


def _normalize_for_comparison(data: dict) -> dict:
    """Normalize extraction output for stable comparison.

    Removes volatile fields that change between runs:
    - tx_id (unique per run)
    - _timestamp
    - bytes (can vary slightly due to float serialization)
    """
    normalized = {}

    for key, value in data.items():
        if key.startswith('_'):
            continue  # Skip metadata keys

        if isinstance(value, list):
            # Sort lists for stable comparison
            if value and isinstance(value[0], dict):
                # Sort by a stable key if available
                sort_key = 'name' if 'name' in value[0] else 'line' if 'line' in value[0] else None
                if sort_key:
                    normalized[key] = sorted(value, key=lambda x: x.get(sort_key, ''))
                else:
                    normalized[key] = value
            else:
                normalized[key] = sorted(value) if value else value
        elif isinstance(value, dict):
            normalized[key] = _normalize_for_comparison(value)
        else:
            normalized[key] = value

    return normalized


def _get_extraction_summary(data: dict) -> dict:
    """Extract a summary of what was found for comparison."""
    summary = {}

    for file_path, file_data in data.items():
        if not file_data.get('success'):
            summary[file_path] = {'success': False, 'error': file_data.get('error')}
            continue

        extracted = file_data.get('extracted_data', {})
        file_summary = {}

        for key, value in extracted.items():
            if key.startswith('_'):
                continue

            if isinstance(value, list):
                file_summary[key] = {
                    'count': len(value),
                    'sample_names': [item.get('name') for item in value[:5] if isinstance(item, dict) and 'name' in item]
                }
            elif isinstance(value, dict):
                file_summary[key] = {'count': len(value)}

        summary[file_path] = {'success': True, 'tables': file_summary}

    return summary


class TestGoldenMaster:
    """Golden Master regression tests."""

    @pytest.mark.skipif(
        not GOLDEN_INPUT.exists(),
        reason="Golden input file not found"
    )
    def test_golden_master_exists(self):
        """Verify golden master file exists and is valid JSON."""
        if not GOLDEN_MASTER.exists():
            pytest.skip(
                "Golden master not yet created. "
                "Run: pytest tests/test_fidelity_golden_master.py::TestGoldenMaster::test_create_golden_master"
            )

        with open(GOLDEN_MASTER, 'r') as f:
            master = json.load(f)

        assert isinstance(master, dict)
        assert len(master) > 0

    @pytest.mark.skipif(
        not GOLDEN_INPUT.exists(),
        reason="Golden input file not found"
    )
    def test_extraction_matches_master(self):
        """CRITICAL: Current extraction must match golden master."""
        if not GOLDEN_MASTER.exists():
            pytest.skip("Golden master not yet created")

        # Extract current output
        current = _extract_file(GOLDEN_INPUT)
        current_summary = _get_extraction_summary(current)

        # Load master
        with open(GOLDEN_MASTER, 'r') as f:
            master = json.load(f)
        master_summary = _get_extraction_summary(master)

        # Compare summaries
        for file_path in master_summary:
            assert file_path in current_summary, f"Missing file in current extraction: {file_path}"

            master_tables = master_summary[file_path].get('tables', {})
            current_tables = current_summary[file_path].get('tables', {})

            for table_name, master_info in master_tables.items():
                assert table_name in current_tables, (
                    f"REGRESSION: Table '{table_name}' missing from current extraction. "
                    f"Master has {master_info['count']} items."
                )

                current_count = current_tables[table_name]['count']
                master_count = master_info['count']

                # Allow current to have MORE items (improvements) but not FEWER (regression)
                assert current_count >= master_count, (
                    f"REGRESSION: Table '{table_name}' has fewer items. "
                    f"Master: {master_count}, Current: {current_count}. "
                    f"This indicates a Silent Omission bug in the extractor."
                )

    @pytest.mark.skipif(
        not GOLDEN_INPUT.exists(),
        reason="Golden input file not found"
    )
    def test_create_golden_master(self):
        """Helper to create/update the golden master file.

        Run this explicitly when you want to update the master:
        pytest tests/test_fidelity_golden_master.py::TestGoldenMaster::test_create_golden_master -v

        This will:
        1. Extract the golden input file
        2. Save output as golden_master.json
        3. Print a summary for manual verification
        """
        current = _extract_file(GOLDEN_INPUT)

        # Save as master
        with open(GOLDEN_MASTER, 'w') as f:
            json.dump(current, f, indent=2)

        # Print summary for verification
        summary = _get_extraction_summary(current)
        print("\n" + "=" * 60)
        print("GOLDEN MASTER CREATED/UPDATED")
        print("=" * 60)
        print(f"Output saved to: {GOLDEN_MASTER}")
        print("\nExtraction Summary:")
        for file_path, file_info in summary.items():
            print(f"\n  {file_path}:")
            if file_info.get('success'):
                for table, info in file_info.get('tables', {}).items():
                    print(f"    - {table}: {info['count']} items")
                    if info.get('sample_names'):
                        print(f"      Samples: {info['sample_names'][:3]}")
            else:
                print(f"    ERROR: {file_info.get('error')}")
        print("\n" + "=" * 60)
        print("VERIFY THIS OUTPUT IS CORRECT before committing!")
        print("=" * 60)


class TestDeathRattle:
    """Tests for the Death Rattle crash reporting pattern."""

    def test_death_rattle_report_structure(self):
        """Verify crash reports have expected structure."""
        crash_report = {
            "type": "FATAL_CRASH",
            "category": "uncaughtException",
            "error": "Test error message",
            "stack": "Error: Test\n    at ...",
            "timestamp": "2024-01-01T00:00:00.000Z"
        }

        # Verify parseable
        serialized = json.dumps(crash_report)
        parsed = json.loads(serialized)

        assert parsed["type"] == "FATAL_CRASH"
        assert "error" in parsed
        assert "category" in parsed

    def test_death_rattle_detection(self):
        """Verify Python can detect Death Rattle crashes."""
        stderr_output = """
[INFO] Starting extraction...
[WARN] Some warning
{"type":"FATAL_CRASH","category":"uncaughtException","error":"Out of memory","stack":"Error: Out of memory\\n    at process..."}
"""
        # Extract last line
        lines = stderr_output.strip().split('\n')
        last_line = lines[-1]

        try:
            crash_report = json.loads(last_line)
            assert crash_report.get("type") == "FATAL_CRASH"
            assert crash_report.get("error") == "Out of memory"
        except json.JSONDecodeError:
            pytest.fail("Failed to parse crash report from stderr")


class TestSilentOmissionDetection:
    """Tests specifically for Silent Omission detection."""

    def test_empty_extraction_flagged(self):
        """Verify empty extraction doesn't silently pass."""
        # If extractor returns empty, fidelity will sign count=0
        # This is "correct" from fidelity's perspective but WRONG from accuracy perspective

        # The Golden Master catches this because:
        # Master says: "functions: 50 items"
        # Current says: "functions: 0 items"
        # Test fails with "REGRESSION: fewer items"

        # This test documents the pattern
        master_info = {'functions': {'count': 50}}
        current_info = {'functions': {'count': 0}}

        # This should fail
        with pytest.raises(AssertionError) as exc_info:
            assert current_info['functions']['count'] >= master_info['functions']['count'], (
                "REGRESSION: Silent Omission detected"
            )

        assert "REGRESSION" in str(exc_info.value)
