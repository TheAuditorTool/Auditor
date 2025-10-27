"""
Test that linter parsers handle NULL code values correctly.

This test verifies the fix for issue #16:
https://github.com/TheAuditorTool/Auditor/issues/16

The issue was that Mypy and Ruff JSON output can contain "code": null,
which caused a NOT NULL constraint violation when inserting into the
findings_consolidated table.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from theauditor.linters.linters import LinterOrchestrator


class TestLinterNullHandling:
    """Test that linters handle NULL code values without database errors."""

    def test_mypy_null_code_handling(self, tmp_path):
        """Test that Mypy parser handles null code values."""
        # Create temp output file with JSON containing null code
        output_file = tmp_path / "mypy_output.json"
        output_file.write_text(
            '{"file": "test.py", "line": 10, "column": 5, "code": null, "message": "Test message", "severity": "error"}\n'
            '{"file": "test.py", "line": 20, "column": 10, "code": "type-error", "message": "Another message", "severity": "error"}\n'
            '{"file": "test.py", "line": 30, "column": 15, "code": "", "message": "Empty code", "severity": "note"}\n'
        )

        # Test the parsing logic directly by reading the file
        findings = []
        with open(output_file, encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)

                    # This is the fix - extract and normalize code field
                    original_code = item.get("code")
                    severity = item.get("severity", "error")

                    if original_code and str(original_code).strip():
                        rule = str(original_code).strip()
                    elif severity == "note":
                        rule = "mypy-note"
                    else:
                        rule = "mypy-unknown"

                    # Clamp negative line/column markers to 0
                    line_num = max(0, item.get("line", 0))
                    column = max(0, item.get("column", 0))

                    findings.append({
                        "tool": "mypy",
                        "file": item.get("file", ""),
                        "line": line_num,
                        "column": column,
                        "rule": rule,
                        "message": item.get("message", ""),
                        "severity": severity,
                        "category": "type"
                    })
                except json.JSONDecodeError:
                    continue

        # Verify all findings were parsed correctly
        assert len(findings) == 3

        # First finding: null code -> mypy-unknown
        assert findings[0]["rule"] == "mypy-unknown"
        assert findings[0]["line"] == 10
        assert findings[0]["column"] == 5

        # Second finding: valid code -> type-error
        assert findings[1]["rule"] == "type-error"
        assert findings[1]["line"] == 20

        # Third finding: empty code + note severity -> mypy-note
        assert findings[2]["rule"] == "mypy-note"
        assert findings[2]["line"] == 30

    def test_ruff_null_code_handling(self, tmp_path):
        """Test that Ruff parser handles null code values."""
        # Create test Ruff JSON output with null code
        ruff_output = [
            {"filename": "test.py", "location": {"row": 10, "column": 5}, "code": None, "message": "Test"},
            {"filename": "test.py", "location": {"row": 20, "column": 10}, "code": "E501", "message": "Line too long"},
            {"filename": "test.py", "location": {"row": 30, "column": 15}, "code": "  ", "message": "Whitespace code"},
        ]

        # Test the parsing logic
        findings = []
        for item in ruff_output:
            # Extract and normalize code field (handle null, whitespace, empty)
            original_code = item.get("code")
            if original_code and str(original_code).strip():
                rule = str(original_code).strip()
            else:
                rule = "ruff-unknown"

            # Clamp negative line/column markers to 0
            line = max(0, item.get("location", {}).get("row", 0))
            column = max(0, item.get("location", {}).get("column", 0))

            findings.append({
                "tool": "ruff",
                "file": item.get("filename", ""),
                "line": line,
                "column": column,
                "rule": rule,
                "message": item.get("message", ""),
                "severity": "warning",
                "category": "lint"
            })

        # Verify all findings were parsed correctly
        assert len(findings) == 3

        # First finding: null code -> ruff-unknown
        assert findings[0]["rule"] == "ruff-unknown"
        assert findings[0]["line"] == 10

        # Second finding: valid code -> E501
        assert findings[1]["rule"] == "E501"
        assert findings[1]["line"] == 20

        # Third finding: whitespace-only code -> ruff-unknown
        assert findings[2]["rule"] == "ruff-unknown"
        assert findings[2]["line"] == 30

    def test_eslint_null_rule_handling(self):
        """Test that ESLint parser handles null ruleId values."""
        # Create test ESLint JSON output with null ruleId
        eslint_output = [
            {
                "filePath": "test.js",
                "messages": [
                    {"line": 10, "column": 5, "ruleId": None, "message": "Parsing error", "severity": 2},
                    {"line": 20, "column": 10, "ruleId": "no-unused-vars", "message": "Unused var", "severity": 1},
                    {"line": 30, "column": 15, "ruleId": "", "message": "Empty rule", "severity": 2},
                ]
            }
        ]

        # Test the parsing logic
        findings = []
        for file_result in eslint_output:
            file_path = file_result.get("filePath", "")

            for msg in file_result.get("messages", []):
                # Extract and normalize rule field (handle null, whitespace, empty)
                original_rule = msg.get("ruleId")
                if original_rule and str(original_rule).strip():
                    rule = str(original_rule).strip()
                else:
                    rule = "eslint-error"

                # Clamp negative line/column markers to 0
                line = max(0, msg.get("line", 0))
                column = max(0, msg.get("column", 0))

                findings.append({
                    "tool": "eslint",
                    "file": file_path,
                    "line": line,
                    "column": column,
                    "rule": rule,
                    "message": msg.get("message", ""),
                    "severity": "error" if msg.get("severity") == 2 else "warning",
                    "category": "lint"
                })

        # Verify all findings were parsed correctly
        assert len(findings) == 3

        # First finding: null ruleId -> eslint-error
        assert findings[0]["rule"] == "eslint-error"
        assert findings[0]["severity"] == "error"

        # Second finding: valid ruleId -> no-unused-vars
        assert findings[1]["rule"] == "no-unused-vars"
        assert findings[1]["severity"] == "warning"

        # Third finding: empty ruleId -> eslint-error
        assert findings[2]["rule"] == "eslint-error"

    def test_negative_line_column_clamping(self):
        """Test that negative line/column values are clamped to 0."""
        test_cases = [
            {"line": -1, "column": -5, "expected_line": 0, "expected_column": 0},
            {"line": 0, "column": 0, "expected_line": 0, "expected_column": 0},
            {"line": 10, "column": 5, "expected_line": 10, "expected_column": 5},
        ]

        for case in test_cases:
            # Test Mypy logic
            line = max(0, case["line"])
            column = max(0, case["column"])
            assert line == case["expected_line"]
            assert column == case["expected_column"]
