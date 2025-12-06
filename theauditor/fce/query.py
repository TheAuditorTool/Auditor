"""FCE Query Engine for vector-based convergence analysis.

Follows the proven CodeQueryEngine pattern from theauditor/context/query.py.
"""

import sqlite3
from collections import defaultdict
from pathlib import Path

from theauditor.fce.registry import SemanticTableRegistry
from theauditor.fce.schema import (
    AIContextBundle,
    ConvergencePoint,
    Fact,
    Vector,
    VectorSignal,
)
from theauditor.utils.helpers import normalize_path_for_db


class FCEQueryEngine:
    """Query engine for vector-based convergence analysis.

    Identifies WHERE multiple independent analysis vectors converge,
    without imposing subjective risk judgments.

    Philosophy: "I am not the judge, I am the evidence locker."
    """

    def __init__(self, root: Path):
        """Initialize with project root.

        Args:
            root: Project root directory containing .pf/ folder

        Raises:
            FileNotFoundError: If repo_index.db doesn't exist
        """

        self.root = Path(root).resolve()
        pf_dir = self.root / ".pf"

        repo_db_path = pf_dir / "repo_index.db"
        if not repo_db_path.exists():
            raise FileNotFoundError(f"Database not found: {repo_db_path}\nRun 'aud full' first.")

        self.repo_db = sqlite3.connect(str(repo_db_path))

        self.repo_db.execute("PRAGMA journal_mode=WAL;")
        self.repo_db.execute("PRAGMA synchronous=NORMAL;")
        self.repo_db.execute("PRAGMA cache_size=-64000;")
        self.repo_db.row_factory = sqlite3.Row

        graph_db_path = pf_dir / "graphs.db"
        if graph_db_path.exists():
            self.graph_db = sqlite3.connect(str(graph_db_path))
            self.graph_db.execute("PRAGMA journal_mode=WAL;")
            self.graph_db.execute("PRAGMA synchronous=NORMAL;")
            self.graph_db.execute("PRAGMA cache_size=-64000;")
            self.graph_db.row_factory = sqlite3.Row
        else:
            self.graph_db = None

        self.registry = SemanticTableRegistry()

        self._table_columns: dict[str, set[str]] = {}
        self._load_table_schema()

    def _load_table_schema(self) -> None:
        """Load actual tables from DB and cache their columns.

        Called once at init. Validates registry against actual schema.
        No try/except - if DB is corrupt, fail loud.
        """
        cursor = self.repo_db.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        actual_tables = {row[0] for row in cursor.fetchall()}

        all_context = self.registry.get_all_context_tables()
        for table in all_context:
            if table in actual_tables:
                cursor.execute(f"PRAGMA table_info({table})")
                self._table_columns[table] = {row[1] for row in cursor.fetchall()}

    def _normalize_path(self, file_path: str) -> str:
        """Normalize file path for database queries."""
        return normalize_path_for_db(file_path, self.root)

    def _build_vector_index(self) -> dict[str, set[Vector]]:
        """Build file->vectors index in 2 queries (fixes N+1 pattern).

        Returns:
            Dict mapping file_path to set of Vectors present for that file
        """
        index: dict[str, set[Vector]] = defaultdict(set)
        cursor = self.repo_db.cursor()

        cursor.execute("SELECT file, tool FROM findings_consolidated")
        for row in cursor.fetchall():
            file_path = row["file"]
            if not file_path:
                continue
            tool = row["tool"]
            if tool == "cfg-analysis":
                index[file_path].add(Vector.STRUCTURAL)
            elif tool == "churn-analysis":
                index[file_path].add(Vector.PROCESS)
            elif tool != "graph-analysis":
                index[file_path].add(Vector.STATIC)

        cursor.execute("SELECT source_file, sink_file FROM taint_flows")
        for row in cursor.fetchall():
            if row["source_file"]:
                index[row["source_file"]].add(Vector.FLOW)
            if row["sink_file"]:
                index[row["sink_file"]].add(Vector.FLOW)

        return dict(index)

    def _has_static_findings(self, file_path: str) -> bool:
        """Check if file has any linter findings (STATIC vector).

        STATIC vector includes all linter tools EXCEPT:
        - cfg-analysis (STRUCTURAL vector)
        - churn-analysis (PROCESS vector)
        - graph-analysis (not a findings source)
        """
        normalized = self._normalize_path(file_path)
        cursor = self.repo_db.cursor()
        cursor.execute(
            """
            SELECT 1 FROM findings_consolidated
            WHERE file = ?
              AND tool NOT IN ('cfg-analysis', 'churn-analysis', 'graph-analysis')
            LIMIT 1
        """,
            (normalized,),
        )
        return cursor.fetchone() is not None

    def _has_flow_findings(self, file_path: str) -> bool:
        """Check if file has taint flows (FLOW vector)."""
        normalized = self._normalize_path(file_path)
        cursor = self.repo_db.cursor()
        cursor.execute(
            """
            SELECT 1 FROM taint_flows
            WHERE source_file = ? OR sink_file = ?
            LIMIT 1
        """,
            (normalized, normalized),
        )
        return cursor.fetchone() is not None

    def _has_process_data(self, file_path: str) -> bool:
        """Check if file has churn data (PROCESS vector)."""
        normalized = self._normalize_path(file_path)
        cursor = self.repo_db.cursor()
        cursor.execute(
            """
            SELECT 1 FROM findings_consolidated
            WHERE file = ? AND tool = 'churn-analysis'
            LIMIT 1
        """,
            (normalized,),
        )
        return cursor.fetchone() is not None

    def _has_structural_data(self, file_path: str) -> bool:
        """Check if file has CFG/complexity data (STRUCTURAL vector)."""
        normalized = self._normalize_path(file_path)
        cursor = self.repo_db.cursor()
        cursor.execute(
            """
            SELECT 1 FROM findings_consolidated
            WHERE file = ? AND tool = 'cfg-analysis'
            LIMIT 1
        """,
            (normalized,),
        )
        return cursor.fetchone() is not None

    def get_vector_density(self, file_path: str) -> VectorSignal:
        """Calculate which analysis vectors have data for this file.

        Args:
            file_path: Path to file (relative or absolute)

        Returns:
            VectorSignal with vectors_present set and density calculated
        """
        vectors: set[Vector] = set()

        if self._has_static_findings(file_path):
            vectors.add(Vector.STATIC)
        if self._has_flow_findings(file_path):
            vectors.add(Vector.FLOW)
        if self._has_process_data(file_path):
            vectors.add(Vector.PROCESS)
        if self._has_structural_data(file_path):
            vectors.add(Vector.STRUCTURAL)

        normalized = self._normalize_path(file_path)
        return VectorSignal(file_path=normalized, vectors_present=vectors)

    def _get_facts_for_file(self, file_path: str) -> list[Fact]:
        """Collect all facts for a file from risk source tables.

        Returns facts from:
        - findings_consolidated (STATIC, PROCESS, STRUCTURAL vectors)
        - taint_flows (FLOW vector)
        """
        normalized = self._normalize_path(file_path)
        facts: list[Fact] = []
        cursor = self.repo_db.cursor()

        cursor.execute(
            """
            SELECT file, line, tool, rule, message, severity, category
            FROM findings_consolidated
            WHERE file = ?
            ORDER BY line
        """,
            (normalized,),
        )

        for row in cursor.fetchall():
            tool = row["tool"]

            if tool == "cfg-analysis":
                vector = Vector.STRUCTURAL
            elif tool == "churn-analysis":
                vector = Vector.PROCESS
            else:
                vector = Vector.STATIC

            facts.append(
                Fact(
                    vector=vector,
                    source=tool,
                    file_path=row["file"],
                    line=row["line"],
                    observation=row["message"] or f"{row['rule']}: {row['category']}",
                    raw_data={
                        "rule": row["rule"],
                        "severity": row["severity"],
                        "category": row["category"],
                    },
                )
            )

        cursor.execute(
            """
            SELECT source_file, source_line, sink_file, sink_line,
                   source_pattern, sink_pattern, vulnerability_type
            FROM taint_flows
            WHERE source_file = ? OR sink_file = ?
            ORDER BY source_line
        """,
            (normalized, normalized),
        )

        for row in cursor.fetchall():
            line = row["source_line"] if row["source_file"] == normalized else row["sink_line"]

            facts.append(
                Fact(
                    vector=Vector.FLOW,
                    source="taint_flows",
                    file_path=normalized,
                    line=line,
                    observation=f"Taint flow: {row['source_pattern']} -> {row['sink_pattern']}",
                    raw_data={
                        "source_file": row["source_file"],
                        "source_line": row["source_line"],
                        "sink_file": row["sink_file"],
                        "sink_line": row["sink_line"],
                        "source_pattern": row["source_pattern"],
                        "sink_pattern": row["sink_pattern"],
                        "vulnerability_type": row["vulnerability_type"],
                    },
                )
            )

        return facts

    def get_convergence_points(self, min_vectors: int = 2) -> list[ConvergencePoint]:
        """Find all locations where multiple vectors converge.

        Uses bulk loading (2 queries) instead of N+1 pattern.

        Args:
            min_vectors: Minimum number of vectors required (1-4, default 2)

        Returns:
            List of ConvergencePoint objects sorted by density DESC
        """
        if min_vectors < 1 or min_vectors > 4:
            raise ValueError("min_vectors must be between 1 and 4")

        convergence_points: list[ConvergencePoint] = []

        vector_index = self._build_vector_index()

        for file_path, vectors in vector_index.items():
            if len(vectors) >= min_vectors:
                facts = self._get_facts_for_file(file_path)

                if facts:
                    lines = [f.line for f in facts if f.line is not None]
                    line_start = min(lines) if lines else 1
                    line_end = max(lines) if lines else 1

                    signal = VectorSignal(file_path=file_path, vectors_present=vectors)

                    convergence_points.append(
                        ConvergencePoint(
                            file_path=file_path,
                            line_start=line_start,
                            line_end=line_end,
                            signal=signal,
                            facts=facts,
                        )
                    )

        convergence_points.sort(key=lambda p: (-p.signal.density, p.file_path))

        return convergence_points

    def get_context_bundle(self, file_path: str, line: int | None = None) -> AIContextBundle:
        """Package convergence + context for AI consumption.

        Args:
            file_path: Path to file
            line: Optional line number to focus on

        Returns:
            AIContextBundle with convergence and context_layers
        """
        normalized = self._normalize_path(file_path)
        signal = self.get_vector_density(file_path)
        facts = self._get_facts_for_file(file_path)

        if line is not None:
            facts = [f for f in facts if f.line is None or abs(f.line - line) <= 10]

        lines = [f.line for f in facts if f.line is not None]
        line_start = min(lines) if lines else (line or 1)
        line_end = max(lines) if lines else (line or 1)

        convergence = ConvergencePoint(
            file_path=normalized,
            line_start=line_start,
            line_end=line_end,
            signal=signal,
            facts=facts,
        )

        context_layers: dict[str, list[dict]] = {}
        context_tables = self.registry.get_context_tables_for_file(file_path)

        cursor = self.repo_db.cursor()

        for table in context_tables:
            columns = self._table_columns.get(table)
            if columns is None:
                continue

            if "file" in columns:
                cursor.execute(
                    f"SELECT * FROM {table} WHERE file LIKE ? LIMIT 50",
                    (f"%{normalized}",),
                )
            elif "path" in columns:
                cursor.execute(
                    f"SELECT * FROM {table} WHERE path LIKE ? LIMIT 50",
                    (f"%{normalized}",),
                )
            else:
                continue

            rows = cursor.fetchall()
            if rows:
                context_layers[table] = [dict(row) for row in rows]

        return AIContextBundle(
            convergence=convergence,
            context_layers=context_layers,
        )

    def get_files_with_vectors(self) -> dict[str, VectorSignal]:
        """Get all files that have at least one vector.

        Uses bulk loading (2 queries) instead of N+1 pattern.

        Returns:
            Dict mapping file_path to VectorSignal
        """

        vector_index = self._build_vector_index()

        return {
            file_path: VectorSignal(file_path=file_path, vectors_present=vectors)
            for file_path, vectors in vector_index.items()
            if vectors
        }

    def get_summary(self) -> dict:
        """Get summary statistics for FCE analysis.

        Returns:
            Dict with summary stats (no opinions, just counts)
        """
        files_with_vectors = self.get_files_with_vectors()

        density_counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
        max_density = 0.0

        for signal in files_with_vectors.values():
            count = signal.vector_count
            density_counts[count] = density_counts.get(count, 0) + 1
            if signal.density > max_density:
                max_density = signal.density

        return {
            "files_analyzed": len(files_with_vectors),
            "files_by_vector_count": density_counts,
            "max_vector_density": max_density,
        }

    def close(self) -> None:
        """Close database connections."""
        if self.repo_db:
            self.repo_db.close()
        if self.graph_db:
            self.graph_db.close()
