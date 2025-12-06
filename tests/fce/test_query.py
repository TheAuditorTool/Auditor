"""Integration tests for FCE Query Engine."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from theauditor.fce.query import FCEQueryEngine
from theauditor.fce.schema import (
    AIContextBundle,
    ConvergencePoint,
    Fact,
    Vector,
    VectorSignal,
)


class TestFCEQueryEngineInit:
    """Tests for FCEQueryEngine initialization."""

    def test_init_raises_if_no_database(self, tmp_path):
        """FCEQueryEngine raises FileNotFoundError if repo_index.db missing."""
        with pytest.raises(FileNotFoundError) as exc_info:
            FCEQueryEngine(tmp_path)

        assert "repo_index.db" in str(exc_info.value)
        assert "aud full" in str(exc_info.value)

    def test_init_connects_to_repo_db(self, tmp_path):
        """FCEQueryEngine connects to repo_index.db."""
        pf_dir = tmp_path / ".pf"
        pf_dir.mkdir()

        # Create minimal database
        db_path = pf_dir / "repo_index.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE findings_consolidated (file TEXT, line INT, tool TEXT)")
        conn.execute("CREATE TABLE taint_flows (source_file TEXT, sink_file TEXT)")
        conn.close()

        engine = FCEQueryEngine(tmp_path)
        assert engine.repo_db is not None
        assert engine.graph_db is None  # No graphs.db created
        engine.close()

    def test_init_connects_to_graphs_db_if_exists(self, tmp_path):
        """FCEQueryEngine connects to graphs.db if it exists."""
        pf_dir = tmp_path / ".pf"
        pf_dir.mkdir()

        # Create both databases
        repo_path = pf_dir / "repo_index.db"
        conn = sqlite3.connect(str(repo_path))
        conn.execute("CREATE TABLE findings_consolidated (file TEXT)")
        conn.execute("CREATE TABLE taint_flows (source_file TEXT)")
        conn.close()

        graph_path = pf_dir / "graphs.db"
        conn = sqlite3.connect(str(graph_path))
        conn.execute("CREATE TABLE edges (source TEXT, target TEXT)")
        conn.close()

        engine = FCEQueryEngine(tmp_path)
        assert engine.repo_db is not None
        assert engine.graph_db is not None
        engine.close()


class TestVectorDetection:
    """Tests for vector detection methods."""

    @pytest.fixture
    def engine_with_data(self, tmp_path):
        """Create engine with test data in all vectors."""
        pf_dir = tmp_path / ".pf"
        pf_dir.mkdir()

        db_path = pf_dir / "repo_index.db"
        conn = sqlite3.connect(str(db_path))

        # Create tables
        conn.execute("""
            CREATE TABLE findings_consolidated (
                file TEXT, line INT, tool TEXT, rule TEXT,
                message TEXT, severity TEXT, category TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE taint_flows (
                source_file TEXT, source_line INT,
                sink_file TEXT, sink_line INT,
                source_pattern TEXT, sink_pattern TEXT, vulnerability_type TEXT
            )
        """)

        # Insert test data for different vectors
        # STATIC: ruff finding
        conn.execute(
            "INSERT INTO findings_consolidated VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("src/auth.py", 10, "ruff", "B101", "Assert used", "warning", "security"),
        )

        # STRUCTURAL: cfg-analysis finding
        conn.execute(
            "INSERT INTO findings_consolidated VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("src/auth.py", 20, "cfg-analysis", "complexity", "High complexity: 25", "info", "complexity"),
        )

        # PROCESS: churn-analysis finding
        conn.execute(
            "INSERT INTO findings_consolidated VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("src/utils.py", 1, "churn-analysis", "high-churn", "45 commits in 90d", "info", "churn"),
        )

        # FLOW: taint flow
        conn.execute(
            "INSERT INTO taint_flows VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("src/auth.py", 15, "src/db.py", 30, "http_request", "sql_query", "sqli"),
        )

        conn.commit()
        conn.close()

        engine = FCEQueryEngine(tmp_path)
        yield engine
        engine.close()

    def test_has_static_findings_true(self, engine_with_data):
        """_has_static_findings returns True for files with linter findings."""
        assert engine_with_data._has_static_findings("src/auth.py") is True

    def test_has_static_findings_false(self, engine_with_data):
        """_has_static_findings returns False for files without linter findings."""
        assert engine_with_data._has_static_findings("src/nonexistent.py") is False

    def test_has_static_excludes_cfg_analysis(self, engine_with_data):
        """_has_static_findings excludes cfg-analysis (STRUCTURAL vector)."""
        # src/utils.py only has churn-analysis, no static findings
        assert engine_with_data._has_static_findings("src/utils.py") is False

    def test_has_flow_findings_source_file(self, engine_with_data):
        """_has_flow_findings returns True for taint source files."""
        assert engine_with_data._has_flow_findings("src/auth.py") is True

    def test_has_flow_findings_sink_file(self, engine_with_data):
        """_has_flow_findings returns True for taint sink files."""
        assert engine_with_data._has_flow_findings("src/db.py") is True

    def test_has_flow_findings_false(self, engine_with_data):
        """_has_flow_findings returns False for files not in taint flows."""
        assert engine_with_data._has_flow_findings("src/utils.py") is False

    def test_has_process_data_true(self, engine_with_data):
        """_has_process_data returns True for files with churn-analysis."""
        assert engine_with_data._has_process_data("src/utils.py") is True

    def test_has_process_data_false(self, engine_with_data):
        """_has_process_data returns False for files without churn-analysis."""
        assert engine_with_data._has_process_data("src/auth.py") is False

    def test_has_structural_data_true(self, engine_with_data):
        """_has_structural_data returns True for files with cfg-analysis."""
        assert engine_with_data._has_structural_data("src/auth.py") is True

    def test_has_structural_data_false(self, engine_with_data):
        """_has_structural_data returns False for files without cfg-analysis."""
        assert engine_with_data._has_structural_data("src/utils.py") is False


class TestGetVectorDensity:
    """Tests for get_vector_density method."""

    @pytest.fixture
    def engine_with_multi_vector(self, tmp_path):
        """Create engine with file having multiple vectors."""
        pf_dir = tmp_path / ".pf"
        pf_dir.mkdir()

        db_path = pf_dir / "repo_index.db"
        conn = sqlite3.connect(str(db_path))

        conn.execute("""
            CREATE TABLE findings_consolidated (
                file TEXT, line INT, tool TEXT, rule TEXT,
                message TEXT, severity TEXT, category TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE taint_flows (
                source_file TEXT, source_line INT,
                sink_file TEXT, sink_line INT,
                source_pattern TEXT, sink_pattern TEXT, vulnerability_type TEXT
            )
        """)

        # File with 3 vectors: STATIC, STRUCTURAL, FLOW
        conn.execute(
            "INSERT INTO findings_consolidated VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("src/critical.py", 10, "ruff", "B101", "Assert", "warning", "security"),
        )
        conn.execute(
            "INSERT INTO findings_consolidated VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("src/critical.py", 20, "cfg-analysis", "complexity", "High", "info", "complexity"),
        )
        conn.execute(
            "INSERT INTO taint_flows VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("src/critical.py", 15, "src/sink.py", 30, "input", "output", "sqli"),
        )

        # File with 1 vector: STATIC only
        conn.execute(
            "INSERT INTO findings_consolidated VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("src/simple.py", 5, "eslint", "no-unused-vars", "Unused", "warning", "style"),
        )

        conn.commit()
        conn.close()

        engine = FCEQueryEngine(tmp_path)
        yield engine
        engine.close()

    def test_returns_vector_signal(self, engine_with_multi_vector):
        """get_vector_density returns VectorSignal object."""
        signal = engine_with_multi_vector.get_vector_density("src/critical.py")
        assert isinstance(signal, VectorSignal)

    def test_density_three_vectors(self, engine_with_multi_vector):
        """File with 3 vectors has density 0.75."""
        signal = engine_with_multi_vector.get_vector_density("src/critical.py")
        assert signal.density == 0.75
        assert signal.density_label == "3/4 vectors"
        assert Vector.STATIC in signal.vectors_present
        assert Vector.STRUCTURAL in signal.vectors_present
        assert Vector.FLOW in signal.vectors_present
        assert Vector.PROCESS not in signal.vectors_present

    def test_density_one_vector(self, engine_with_multi_vector):
        """File with 1 vector has density 0.25."""
        signal = engine_with_multi_vector.get_vector_density("src/simple.py")
        assert signal.density == 0.25
        assert signal.density_label == "1/4 vectors"
        assert signal.vector_count == 1

    def test_density_zero_vectors(self, engine_with_multi_vector):
        """File with no findings has density 0.0."""
        signal = engine_with_multi_vector.get_vector_density("src/clean.py")
        assert signal.density == 0.0
        assert signal.density_label == "0/4 vectors"
        assert signal.vector_count == 0


class TestGetConvergencePoints:
    """Tests for get_convergence_points method."""

    @pytest.fixture
    def engine_with_convergence(self, tmp_path):
        """Create engine with files at different convergence levels."""
        pf_dir = tmp_path / ".pf"
        pf_dir.mkdir()

        db_path = pf_dir / "repo_index.db"
        conn = sqlite3.connect(str(db_path))

        conn.execute("""
            CREATE TABLE findings_consolidated (
                file TEXT, line INT, tool TEXT, rule TEXT,
                message TEXT, severity TEXT, category TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE taint_flows (
                source_file TEXT, source_line INT,
                sink_file TEXT, sink_line INT,
                source_pattern TEXT, sink_pattern TEXT, vulnerability_type TEXT
            )
        """)

        # 3-vector file
        conn.execute("INSERT INTO findings_consolidated VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("high.py", 10, "ruff", "B101", "Assert", "warning", "security"))
        conn.execute("INSERT INTO findings_consolidated VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("high.py", 20, "cfg-analysis", "complexity", "High", "info", "complexity"))
        conn.execute("INSERT INTO taint_flows VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("high.py", 15, "sink.py", 30, "input", "output", "sqli"))

        # 2-vector file
        conn.execute("INSERT INTO findings_consolidated VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("medium.py", 5, "ruff", "B102", "Exec", "warning", "security"))
        conn.execute("INSERT INTO findings_consolidated VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("medium.py", 25, "cfg-analysis", "complexity", "Medium", "info", "complexity"))

        # 1-vector file
        conn.execute("INSERT INTO findings_consolidated VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("low.py", 1, "eslint", "no-var", "Use let", "warning", "style"))

        conn.commit()
        conn.close()

        engine = FCEQueryEngine(tmp_path)
        yield engine
        engine.close()

    def test_returns_convergence_points(self, engine_with_convergence):
        """get_convergence_points returns list of ConvergencePoint."""
        points = engine_with_convergence.get_convergence_points(min_vectors=2)
        assert isinstance(points, list)
        assert all(isinstance(p, ConvergencePoint) for p in points)

    def test_filters_by_min_vectors(self, engine_with_convergence):
        """get_convergence_points filters by minimum vector count."""
        points_2 = engine_with_convergence.get_convergence_points(min_vectors=2)
        points_3 = engine_with_convergence.get_convergence_points(min_vectors=3)
        points_1 = engine_with_convergence.get_convergence_points(min_vectors=1)

        assert len(points_2) == 2  # high.py, medium.py
        assert len(points_3) == 1  # high.py only
        assert len(points_1) == 4  # high.py, medium.py, low.py, sink.py (taint sink)

    def test_sorted_by_density_desc(self, engine_with_convergence):
        """Results are sorted by density DESC."""
        points = engine_with_convergence.get_convergence_points(min_vectors=1)
        densities = [p.signal.density for p in points]
        assert densities == sorted(densities, reverse=True)

    def test_convergence_point_has_facts(self, engine_with_convergence):
        """ConvergencePoint includes facts from all vectors."""
        points = engine_with_convergence.get_convergence_points(min_vectors=3)
        assert len(points) == 1

        point = points[0]
        assert len(point.facts) >= 2  # At least static + structural
        vectors_in_facts = {f.vector for f in point.facts}
        assert Vector.STATIC in vectors_in_facts
        assert Vector.STRUCTURAL in vectors_in_facts

    def test_min_vectors_validation(self, engine_with_convergence):
        """min_vectors must be 1-4."""
        with pytest.raises(ValueError):
            engine_with_convergence.get_convergence_points(min_vectors=0)
        with pytest.raises(ValueError):
            engine_with_convergence.get_convergence_points(min_vectors=5)


class TestGetContextBundle:
    """Tests for get_context_bundle method."""

    @pytest.fixture
    def engine_with_context(self, tmp_path):
        """Create engine with context data."""
        pf_dir = tmp_path / ".pf"
        pf_dir.mkdir()

        db_path = pf_dir / "repo_index.db"
        conn = sqlite3.connect(str(db_path))

        conn.execute("""
            CREATE TABLE findings_consolidated (
                file TEXT, line INT, tool TEXT, rule TEXT,
                message TEXT, severity TEXT, category TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE taint_flows (
                source_file TEXT, source_line INT,
                sink_file TEXT, sink_line INT,
                source_pattern TEXT, sink_pattern TEXT, vulnerability_type TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE python_decorators (
                file TEXT, line INT, decorator_name TEXT, target_name TEXT
            )
        """)

        # Add findings
        conn.execute("INSERT INTO findings_consolidated VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("app.py", 10, "ruff", "B101", "Assert", "warning", "security"))

        # Add context
        conn.execute("INSERT INTO python_decorators VALUES (?, ?, ?, ?)",
            ("app.py", 5, "login_required", "view_func"))

        conn.commit()
        conn.close()

        engine = FCEQueryEngine(tmp_path)
        yield engine
        engine.close()

    def test_returns_ai_context_bundle(self, engine_with_context):
        """get_context_bundle returns AIContextBundle."""
        bundle = engine_with_context.get_context_bundle("app.py")
        assert isinstance(bundle, AIContextBundle)

    def test_bundle_has_convergence(self, engine_with_context):
        """Bundle contains convergence point."""
        bundle = engine_with_context.get_context_bundle("app.py")
        assert isinstance(bundle.convergence, ConvergencePoint)
        assert bundle.convergence.file_path == "app.py"

    def test_bundle_has_context_layers(self, engine_with_context):
        """Bundle contains context layers for Python file."""
        bundle = engine_with_context.get_context_bundle("app.py")
        # python_decorators should be included for .py file
        assert "python_decorators" in bundle.context_layers
        assert len(bundle.context_layers["python_decorators"]) == 1

    def test_to_prompt_context_returns_json(self, engine_with_context):
        """to_prompt_context returns valid JSON."""
        bundle = engine_with_context.get_context_bundle("app.py")
        json_str = bundle.to_prompt_context()
        import json
        data = json.loads(json_str)
        assert "convergence" in data
        assert "context_layers" in data


class TestParameterizedQueries:
    """Tests to verify SQL injection prevention."""

    @pytest.fixture
    def engine(self, tmp_path):
        """Create minimal engine."""
        pf_dir = tmp_path / ".pf"
        pf_dir.mkdir()

        db_path = pf_dir / "repo_index.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE findings_consolidated (
                file TEXT, line INT, tool TEXT, rule TEXT,
                message TEXT, severity TEXT, category TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE taint_flows (
                source_file TEXT, source_line INT,
                sink_file TEXT, sink_line INT,
                source_pattern TEXT, sink_pattern TEXT, vulnerability_type TEXT
            )
        """)
        conn.close()

        engine = FCEQueryEngine(tmp_path)
        yield engine
        engine.close()

    def test_malicious_path_static(self, engine):
        """Malicious file path doesn't cause SQL injection in static check."""
        # Should not raise, just return False
        result = engine._has_static_findings("'; DROP TABLE findings_consolidated; --")
        assert result is False

    def test_malicious_path_flow(self, engine):
        """Malicious file path doesn't cause SQL injection in flow check."""
        result = engine._has_flow_findings("'; DROP TABLE taint_flows; --")
        assert result is False

    def test_malicious_path_vector_density(self, engine):
        """Malicious file path doesn't cause SQL injection in vector density."""
        signal = engine.get_vector_density("'; DROP TABLE findings_consolidated; --")
        assert signal.vector_count == 0


class TestClose:
    """Tests for close method."""

    def test_close_closes_connections(self, tmp_path):
        """close() closes database connections."""
        pf_dir = tmp_path / ".pf"
        pf_dir.mkdir()

        db_path = pf_dir / "repo_index.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE findings_consolidated (file TEXT)")
        conn.execute("CREATE TABLE taint_flows (source_file TEXT)")
        conn.close()

        engine = FCEQueryEngine(tmp_path)
        engine.close()

        # Verify connection is closed by trying to use it
        with pytest.raises(sqlite3.ProgrammingError):
            engine.repo_db.execute("SELECT 1")
