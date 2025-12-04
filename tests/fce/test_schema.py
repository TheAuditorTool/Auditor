"""Tests for FCE schema models."""

import json

import pytest
from pydantic import ValidationError

from theauditor.fce.schema import (
    AIContextBundle,
    ConvergencePoint,
    Fact,
    Vector,
    VectorSignal,
)


class TestVector:
    """Tests for Vector enum."""

    def test_vector_values(self):
        """Vector enum has exactly 4 values."""
        assert len(Vector) == 4
        assert Vector.STATIC.value == "static"
        assert Vector.FLOW.value == "flow"
        assert Vector.PROCESS.value == "process"
        assert Vector.STRUCTURAL.value == "structural"

    def test_vector_is_string_enum(self):
        """Vector inherits from str for JSON serialization."""
        assert isinstance(Vector.STATIC, str)
        assert Vector.STATIC == "static"

    def test_vector_from_string(self):
        """Can create Vector from string value."""
        assert Vector("static") == Vector.STATIC
        assert Vector("flow") == Vector.FLOW


class TestFact:
    """Tests for Fact model."""

    def test_fact_creation(self):
        """Can create a Fact with all required fields."""
        fact = Fact(
            vector=Vector.STATIC,
            source="ruff",
            file_path="src/auth/login.py",
            line=42,
            observation="B101: assert used in production code",
            raw_data={"rule": "B101", "severity": "warning"},
        )
        assert fact.vector == Vector.STATIC
        assert fact.source == "ruff"
        assert fact.file_path == "src/auth/login.py"
        assert fact.line == 42
        assert fact.observation == "B101: assert used in production code"
        assert fact.raw_data == {"rule": "B101", "severity": "warning"}

    def test_fact_line_optional(self):
        """Fact.line can be None for file-level findings."""
        fact = Fact(
            vector=Vector.PROCESS,
            source="churn-analysis",
            file_path="src/utils/helpers.py",
            line=None,
            observation="High churn: 45 commits in 90 days",
            raw_data={"commits_90d": 45},
        )
        assert fact.line is None

    def test_fact_serialization(self):
        """Fact serializes to dict with enum as string value."""
        fact = Fact(
            vector=Vector.FLOW,
            source="taint_flows",
            file_path="api/users.py",
            line=100,
            observation="User input flows to SQL query",
            raw_data={"source_type": "http_request"},
        )
        data = fact.model_dump()
        assert data["vector"] == "flow"
        assert isinstance(data["raw_data"], dict)


class TestVectorSignal:
    """Tests for VectorSignal model."""

    def test_density_zero_vectors(self):
        """Density is 0.0 when no vectors present."""
        signal = VectorSignal(file_path="clean.py", vectors_present=set())
        assert signal.density == 0.0
        assert signal.density_label == "0/4 vectors"
        assert signal.vector_count == 0

    def test_density_one_vector(self):
        """Density is 0.25 for single vector."""
        signal = VectorSignal(
            file_path="linted.py",
            vectors_present={Vector.STATIC},
        )
        assert signal.density == 0.25
        assert signal.density_label == "1/4 vectors"
        assert signal.vector_count == 1

    def test_density_two_vectors(self):
        """Density is 0.5 for two vectors."""
        signal = VectorSignal(
            file_path="medium.py",
            vectors_present={Vector.STATIC, Vector.FLOW},
        )
        assert signal.density == 0.5
        assert signal.density_label == "2/4 vectors"
        assert signal.vector_count == 2

    def test_density_three_vectors(self):
        """Density is 0.75 for three vectors."""
        signal = VectorSignal(
            file_path="hot.py",
            vectors_present={Vector.STATIC, Vector.FLOW, Vector.STRUCTURAL},
        )
        assert signal.density == 0.75
        assert signal.density_label == "3/4 vectors"
        assert signal.vector_count == 3

    def test_density_four_vectors(self):
        """Density is 1.0 for all four vectors."""
        signal = VectorSignal(
            file_path="critical.py",
            vectors_present={Vector.STATIC, Vector.FLOW, Vector.PROCESS, Vector.STRUCTURAL},
        )
        assert signal.density == 1.0
        assert signal.density_label == "4/4 vectors"
        assert signal.vector_count == 4

    def test_density_is_pure_math(self):
        """Density calculation has no thresholds or magic numbers."""
        for count in range(5):
            vectors = set(list(Vector)[:count])
            signal = VectorSignal(file_path="test.py", vectors_present=vectors)
            assert signal.density == count / 4

    def test_vector_signal_serialization(self):
        """VectorSignal serializes with enum values as strings."""
        signal = VectorSignal(
            file_path="test.py",
            vectors_present={Vector.STATIC, Vector.FLOW},
        )
        data = signal.model_dump()
        assert data["file_path"] == "test.py"
        assert "static" in data["vectors_present"]
        assert "flow" in data["vectors_present"]


class TestConvergencePoint:
    """Tests for ConvergencePoint model."""

    def test_convergence_point_creation(self):
        """Can create ConvergencePoint with signal and facts."""
        signal = VectorSignal(
            file_path="auth.py",
            vectors_present={Vector.STATIC, Vector.FLOW},
        )
        fact1 = Fact(
            vector=Vector.STATIC,
            source="ruff",
            file_path="auth.py",
            line=42,
            observation="Security issue",
            raw_data={},
        )
        fact2 = Fact(
            vector=Vector.FLOW,
            source="taint_flows",
            file_path="auth.py",
            line=45,
            observation="Taint flow",
            raw_data={},
        )
        point = ConvergencePoint(
            file_path="auth.py",
            line_start=42,
            line_end=50,
            signal=signal,
            facts=[fact1, fact2],
        )
        assert point.file_path == "auth.py"
        assert point.line_start == 42
        assert point.line_end == 50
        assert point.signal.density == 0.5
        assert len(point.facts) == 2

    def test_convergence_point_serialization(self):
        """ConvergencePoint serializes to valid JSON."""
        signal = VectorSignal(file_path="test.py", vectors_present={Vector.STATIC})
        point = ConvergencePoint(
            file_path="test.py",
            line_start=1,
            line_end=10,
            signal=signal,
            facts=[],
        )
        json_str = point.model_dump_json()
        data = json.loads(json_str)
        assert data["file_path"] == "test.py"
        assert "signal" in data


class TestAIContextBundle:
    """Tests for AIContextBundle model."""

    def test_ai_context_bundle_creation(self):
        """Can create AIContextBundle with convergence and context."""
        signal = VectorSignal(file_path="api.py", vectors_present={Vector.STATIC})
        point = ConvergencePoint(
            file_path="api.py",
            line_start=1,
            line_end=100,
            signal=signal,
            facts=[],
        )
        bundle = AIContextBundle(
            convergence=point,
            context_layers={
                "framework": [{"type": "express", "middleware": ["auth"]}],
                "security": [{"pattern": "jwt_validation"}],
            },
        )
        assert bundle.convergence.file_path == "api.py"
        assert "framework" in bundle.context_layers
        assert "security" in bundle.context_layers

    def test_to_prompt_context_returns_json(self):
        """to_prompt_context() returns valid JSON string."""
        signal = VectorSignal(file_path="test.py", vectors_present=set())
        point = ConvergencePoint(
            file_path="test.py",
            line_start=1,
            line_end=1,
            signal=signal,
            facts=[],
        )
        bundle = AIContextBundle(convergence=point, context_layers={})
        json_str = bundle.to_prompt_context()
        data = json.loads(json_str)
        assert "convergence" in data
        assert "context_layers" in data

    def test_ai_context_bundle_empty_context(self):
        """AIContextBundle works with empty context_layers."""
        signal = VectorSignal(file_path="test.py", vectors_present=set())
        point = ConvergencePoint(
            file_path="test.py",
            line_start=1,
            line_end=1,
            signal=signal,
            facts=[],
        )
        bundle = AIContextBundle(convergence=point, context_layers={})
        assert bundle.context_layers == {}


class TestValidation:
    """Tests for Pydantic validation."""

    def test_fact_requires_vector(self):
        """Fact requires vector field."""
        with pytest.raises(ValidationError):
            Fact(
                source="ruff",
                file_path="test.py",
                line=1,
                observation="test",
                raw_data={},
            )

    def test_fact_requires_file_path(self):
        """Fact requires file_path field."""
        with pytest.raises(ValidationError):
            Fact(
                vector=Vector.STATIC,
                source="ruff",
                line=1,
                observation="test",
                raw_data={},
            )

    def test_vector_signal_requires_file_path(self):
        """VectorSignal requires file_path field."""
        with pytest.raises(ValidationError):
            VectorSignal(vectors_present=set())

    def test_convergence_point_requires_signal(self):
        """ConvergencePoint requires signal field."""
        with pytest.raises(ValidationError):
            ConvergencePoint(
                file_path="test.py",
                line_start=1,
                line_end=10,
                facts=[],
            )
