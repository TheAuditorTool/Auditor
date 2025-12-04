"""Tests for FCE Formatter.

The formatter now handles JSON serialization only.
Text rendering is done in the command using Rich.
"""

import json

import pytest

from theauditor.fce.formatter import FCEFormatter
from theauditor.fce.schema import (
    ConvergencePoint,
    Fact,
    Vector,
    VectorSignal,
)


class TestGetVectorCodeString:
    """Tests for get_vector_code_string() static method."""

    def test_full_density(self):
        """4/4 vectors shows all codes."""
        signal = VectorSignal(
            file_path="src/auth/login.py",
            vectors_present={Vector.STATIC, Vector.FLOW, Vector.PROCESS, Vector.STRUCTURAL},
        )
        result = FCEFormatter.get_vector_code_string(signal)
        assert result == "SFPT"

    def test_partial_density(self):
        """2/4 vectors shows dashes for missing."""
        signal = VectorSignal(
            file_path="utils/helpers.py",
            vectors_present={Vector.STATIC, Vector.STRUCTURAL},
        )
        result = FCEFormatter.get_vector_code_string(signal)
        assert result == "S--T"

    def test_single_vector(self):
        """1/4 vector shows correctly."""
        signal = VectorSignal(
            file_path="test.py",
            vectors_present={Vector.FLOW},
        )
        result = FCEFormatter.get_vector_code_string(signal)
        assert result == "-F--"

    def test_zero_vectors(self):
        """0/4 vectors shows all dashes."""
        signal = VectorSignal(
            file_path="empty.py",
            vectors_present=set(),
        )
        result = FCEFormatter.get_vector_code_string(signal)
        assert result == "----"

    def test_no_emojis_in_output(self):
        """Output contains no emojis."""
        signal = VectorSignal(
            file_path="test.py",
            vectors_present={Vector.STATIC, Vector.FLOW},
        )
        result = FCEFormatter.get_vector_code_string(signal)
        for char in result:
            assert ord(char) < 0x1F600, f"Found potential emoji: {char}"


class TestPointToDict:
    """Tests for point_to_dict() method."""

    def test_basic_conversion(self):
        """Basic convergence point converts to dict."""
        formatter = FCEFormatter()
        point = ConvergencePoint(
            file_path="src/auth/login.py",
            line_start=42,
            line_end=58,
            signal=VectorSignal(
                file_path="src/auth/login.py",
                vectors_present={Vector.STATIC, Vector.FLOW},
            ),
            facts=[
                Fact(
                    vector=Vector.STATIC,
                    source="ruff",
                    file_path="src/auth/login.py",
                    line=45,
                    observation="B101: assert used",
                    raw_data={"rule": "B101"},
                ),
            ],
        )
        result = formatter.point_to_dict(point)

        assert result["file_path"] == "src/auth/login.py"
        assert result["line_start"] == 42
        assert result["line_end"] == 58
        assert result["signal"]["file_path"] == "src/auth/login.py"
        assert result["signal"]["vector_count"] == 2
        assert result["signal"]["density"] == 0.5
        assert "static" in result["signal"]["vectors_present"]
        assert "flow" in result["signal"]["vectors_present"]
        assert len(result["facts"]) == 1
        assert result["facts"][0]["source"] == "ruff"
        assert result["facts"][0]["vector"] == "static"

    def test_empty_facts(self):
        """Point with no facts converts correctly."""
        formatter = FCEFormatter()
        point = ConvergencePoint(
            file_path="test.py",
            line_start=1,
            line_end=10,
            signal=VectorSignal(file_path="test.py", vectors_present={Vector.STATIC}),
            facts=[],
        )
        result = formatter.point_to_dict(point)

        assert result["facts"] == []
        assert result["signal"]["vector_count"] == 1

    def test_multiple_facts_multiple_vectors(self):
        """Point with multiple facts across vectors converts correctly."""
        formatter = FCEFormatter()
        point = ConvergencePoint(
            file_path="test.py",
            line_start=1,
            line_end=100,
            signal=VectorSignal(
                file_path="test.py",
                vectors_present={Vector.STATIC, Vector.FLOW, Vector.STRUCTURAL},
            ),
            facts=[
                Fact(
                    vector=Vector.STATIC,
                    source="ruff",
                    file_path="test.py",
                    line=10,
                    observation="Static issue",
                    raw_data={},
                ),
                Fact(
                    vector=Vector.FLOW,
                    source="taint_flows",
                    file_path="test.py",
                    line=20,
                    observation="Flow issue",
                    raw_data={},
                ),
                Fact(
                    vector=Vector.STRUCTURAL,
                    source="cfg-analysis",
                    file_path="test.py",
                    line=30,
                    observation="Structural issue",
                    raw_data={},
                ),
            ],
        )
        result = formatter.point_to_dict(point)

        assert len(result["facts"]) == 3
        vectors = {f["vector"] for f in result["facts"]}
        assert vectors == {"static", "flow", "structural"}


class TestFormatJson:
    """Tests for format_json()."""

    def test_valid_json_output(self):
        """Output is valid JSON."""
        formatter = FCEFormatter()
        data = {"key": "value", "number": 42}
        result = formatter.format_json(data)
        parsed = json.loads(result)
        assert parsed["key"] == "value"
        assert parsed["number"] == 42

    def test_handles_pydantic_models(self):
        """Pydantic models are serialized correctly."""
        formatter = FCEFormatter()
        signal = VectorSignal(
            file_path="test.py",
            vectors_present={Vector.STATIC, Vector.FLOW},
        )
        result = formatter.format_json(signal)
        parsed = json.loads(result)
        assert parsed["file_path"] == "test.py"
        assert "static" in parsed["vectors_present"]
        assert "flow" in parsed["vectors_present"]

    def test_handles_sets(self):
        """Sets are converted to sorted lists."""
        formatter = FCEFormatter()
        data = {"items": {3, 1, 2}}
        result = formatter.format_json(data)
        parsed = json.loads(result)
        assert parsed["items"] == [1, 2, 3]

    def test_handles_enums(self):
        """Enums are converted to their values."""
        formatter = FCEFormatter()
        data = {"vector": Vector.STATIC}
        result = formatter.format_json(data)
        parsed = json.loads(result)
        assert parsed["vector"] == "static"

    def test_handles_nested_structures(self):
        """Nested structures are handled correctly."""
        formatter = FCEFormatter()
        point = ConvergencePoint(
            file_path="test.py",
            line_start=1,
            line_end=10,
            signal=VectorSignal(
                file_path="test.py",
                vectors_present={Vector.STATIC},
            ),
            facts=[
                Fact(
                    vector=Vector.STATIC,
                    source="ruff",
                    file_path="test.py",
                    line=5,
                    observation="Test",
                    raw_data={"key": "value"},
                ),
            ],
        )
        result = formatter.format_json(point)
        parsed = json.loads(result)
        assert parsed["file_path"] == "test.py"
        assert parsed["line_start"] == 1
        assert len(parsed["facts"]) == 1
        assert parsed["facts"][0]["source"] == "ruff"

    def test_handles_none(self):
        """None values are handled."""
        formatter = FCEFormatter()
        data = {"value": None}
        result = formatter.format_json(data)
        parsed = json.loads(result)
        assert parsed["value"] is None

    def test_indented_output(self):
        """Output is indented for readability."""
        formatter = FCEFormatter()
        data = {"key": "value"}
        result = formatter.format_json(data)
        assert "\n" in result
        assert "  " in result


class TestNoEmojis:
    """Verify no emojis in formatter constants."""

    @pytest.fixture
    def formatter(self):
        return FCEFormatter()

    def test_vector_labels_no_emojis(self, formatter):
        """Vector labels contain no emojis."""
        for label in formatter.VECTOR_LABELS.values():
            for char in label:
                assert ord(char) < 0x1F600

    def test_vector_codes_no_emojis(self, formatter):
        """Vector codes contain no emojis."""
        for code in formatter.VECTOR_CODES.values():
            for char in code:
                assert ord(char) < 0x1F600

    def test_get_vector_code_string_no_emojis(self):
        """get_vector_code_string output has no emojis."""
        signal = VectorSignal(
            file_path="test.py",
            vectors_present={Vector.STATIC, Vector.FLOW, Vector.PROCESS, Vector.STRUCTURAL},
        )
        result = FCEFormatter.get_vector_code_string(signal)
        for char in result:
            assert ord(char) < 0x1F600

    def test_format_json_no_emojis(self, formatter):
        """format_json output has no emojis."""
        point = ConvergencePoint(
            file_path="test.py",
            line_start=1,
            line_end=100,
            signal=VectorSignal(
                file_path="test.py",
                vectors_present={Vector.STATIC, Vector.FLOW},
            ),
            facts=[
                Fact(
                    vector=Vector.STATIC,
                    source="ruff",
                    file_path="test.py",
                    line=10,
                    observation="Test observation",
                    raw_data={"rule": "B101"},
                ),
            ],
        )
        result = formatter.format_json(point)
        for char in result:
            assert ord(char) < 0x1F600
