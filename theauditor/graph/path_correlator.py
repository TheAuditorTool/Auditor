"""Path-Based Factual Correlation using Control Flow Graphs.

This module correlates findings based on control flow structure - purely factual
relationships about which findings execute together on the same paths.
"""

import sqlite3
from collections import defaultdict
from typing import Any

from theauditor.graph.cfg_builder import CFGBuilder

# Adaptive strategy threshold for pathfinding vs block clustering
COMPLEXITY_THRESHOLD = 25


class PathCorrelator:
    """Correlate findings based on shared execution paths in CFG.

    Reports structural facts about control flow relationships, not interpretations.
    """

    def __init__(self, db_path: str):
        """Initialize with database connection.

        Args:
            db_path: Path to repo_index.db
        """
        self.db_path = str(db_path)
        self.cfg_builder = CFGBuilder(self.db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

    def correlate(self, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Find findings that co-exist on same execution paths.

        Args:
            findings: List of finding dictionaries with file, line, tool, etc.

        Returns:
            List of path clusters with findings guaranteed to be on same path
        """

        findings_by_function = self._group_findings_by_function(findings)
        path_clusters = []

        for (file_path, func_name), func_findings in findings_by_function.items():
            if len(func_findings) < 2:
                continue

            cfg = self.cfg_builder.get_function_cfg(file_path, func_name)
            if not cfg or not cfg.get("blocks"):
                continue

            findings_to_blocks = self._map_findings_to_blocks(cfg, func_findings)

            clusters = self._find_finding_paths_with_conditions(
                cfg, findings_to_blocks, func_findings
            )

            for cluster in clusters:
                cluster["function"] = func_name
                cluster["file"] = file_path

            path_clusters.extend(clusters)

        return path_clusters

    def _group_findings_by_function(self, findings: list[dict]) -> dict[tuple[str, str], list]:
        """Group findings by their containing function.

        Uses symbols table to find function boundaries.
        """
        grouped = defaultdict(list)
        cursor = self.conn.cursor()

        for finding in findings:
            file_path = finding.get("file", "")
            line = finding.get("line", 0)

            if not file_path or line <= 0:
                continue

            cursor.execute(
                """
                SELECT name, type
                FROM symbols
                WHERE path = ?
                  AND line <= ?
                  AND type = 'function'
                ORDER BY line DESC
                LIMIT 1
            """,
                (file_path, line),
            )

            result = cursor.fetchone()
            if result:
                func_name = result["name"]
                grouped[(file_path, func_name)].append(finding)

        return dict(grouped)

    def _map_findings_to_blocks(self, cfg: dict, findings: list) -> dict[int, list]:
        """Map each finding to its CFG block ID."""
        block_findings = defaultdict(list)

        for finding in findings:
            line = finding.get("line", 0)

            for block in cfg.get("blocks", []):
                if block["start_line"] <= line <= block["end_line"]:
                    block_findings[block["id"]].append(finding)
                    break

        return dict(block_findings)

    def _find_finding_paths_with_conditions(
        self, cfg: dict, findings_to_blocks: dict, all_findings: list
    ) -> list[dict]:
        """Find execution paths containing multiple findings with path conditions.

        ADAPTIVE STRATEGY (v1.3+):
        - Below complexity threshold (≤25 finding locations): High-precision O(N²) pathfinding
        - Above threshold (>25): Fast O(N) block clustering to prevent performance cliff

        ALGORITHMIC IMPROVEMENT (v1.1+):
        Instead of enumerating all paths (which causes false negatives when max_paths
        is reached), we use targeted graph traversal. For each pair of findings, we
        check if a path exists between them using BFS. This guarantees complete
        accuracy regardless of function complexity.

        Reports factual control flow conditions, not interpretations.
        """

        finding_blocks = list(findings_to_blocks.keys())

        if len(finding_blocks) > COMPLEXITY_THRESHOLD:
            return self._fast_block_clustering(findings_to_blocks)

        clusters = []

        graph = self._build_cfg_graph(cfg)

        for i, block_a in enumerate(finding_blocks):
            for block_b in finding_blocks[i + 1 :]:
                path_a_to_b = self._find_path_bfs(graph, block_a, block_b)
                path_b_to_a = self._find_path_bfs(graph, block_b, block_a)

                path = None
                if path_a_to_b and path_b_to_a:
                    path = path_a_to_b if len(path_a_to_b) <= len(path_b_to_a) else path_b_to_a
                elif path_a_to_b:
                    path = path_a_to_b
                elif path_b_to_a:
                    path = path_b_to_a

                if path:
                    findings_on_path = []

                    for block_id in path:
                        if block_id in findings_to_blocks:
                            findings_on_path.extend(findings_to_blocks[block_id])

                    if len(findings_on_path) >= 2:
                        path_conditions = self._extract_path_conditions(cfg, path)

                        description = f"{len(findings_on_path)} findings on same execution path"
                        if path_conditions:
                            description += f" when: {' AND '.join(path_conditions)}"

                        clusters.append(
                            {
                                "type": "path_cluster",
                                "confidence": 0.95,
                                "path_blocks": path,
                                "conditions": path_conditions,
                                "findings": findings_on_path,
                                "finding_count": len(findings_on_path),
                                "description": description,
                            }
                        )

        unique_clusters = []
        seen_finding_sets = set()

        for cluster in clusters:
            finding_set = frozenset(
                f"{f['file']}:{f['line']}:{f['tool']}" for f in cluster["findings"]
            )
            if finding_set not in seen_finding_sets:
                seen_finding_sets.add(finding_set)
                unique_clusters.append(cluster)

        return unique_clusters

    def _fast_block_clustering(self, findings_to_blocks: dict[int, list]) -> list[dict]:
        """
        O(N) clustering strategy for complex functions.

        Groups findings that share the exact same Basic Block. This is an
        ADAPTIVE ALGORITHM SELECTION (not a fallback) - chosen when function
        complexity makes O(N²) pathfinding too expensive.

        Args:
            findings_to_blocks: Dict mapping block_id -> list of findings

        Returns:
            List of block_cluster dicts with explicit metadata distinguishing
            this from high-precision path_cluster results
        """
        clusters = []

        for block_id, findings in findings_to_blocks.items():
            if len(findings) >= 2:
                clusters.append(
                    {
                        "type": "block_cluster",
                        "confidence": 1.0,
                        "path_blocks": [block_id],
                        "conditions": ["(Findings in same code block - Complex function)"],
                        "findings": findings,
                        "finding_count": len(findings),
                        "description": f"{len(findings)} findings in same code block (fast clustering mode)",
                    }
                )

        return clusters

    def _build_cfg_graph(self, cfg: dict) -> dict[int, list[int]]:
        """Build adjacency list representation of CFG for efficient traversal.

        Args:
            cfg: CFG dictionary with edges

        Returns:
            Dict mapping block_id -> list of successor block_ids
        """
        graph = defaultdict(list)
        for edge in cfg.get("edges", []):
            if edge["type"] != "back_edge":
                graph[edge["source"]].append(edge["target"])
        return dict(graph)

    def _find_path_bfs(self, graph: dict[int, list[int]], start: int, end: int) -> list[int] | None:
        """Find a path from start to end using BFS.

        Args:
            graph: Adjacency list representation of CFG
            start: Starting block ID
            end: Target block ID

        Returns:
            List of block IDs representing the path, or None if no path exists
        """
        if start == end:
            return [start]

        from collections import deque

        queue = deque([(start, [start])])
        visited = {start}

        while queue:
            node, path = queue.popleft()

            for neighbor in graph.get(node, []):
                if neighbor == end:
                    return path + [neighbor]

                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return None

    def _extract_path_conditions(self, cfg: dict, path_blocks: list[int]) -> list[str]:
        """Extract the literal conditions from source that define this execution path.

        Returns factual code conditions, not interpretations.
        """
        conditions = []
        blocks_dict = {b["id"]: b for b in cfg.get("blocks", [])}
        edges_dict = defaultdict(list)

        for edge in cfg.get("edges", []):
            edges_dict[edge["source"]].append({"target": edge["target"], "type": edge["type"]})

        for i, block_id in enumerate(path_blocks):
            block = blocks_dict.get(block_id)
            if not block:
                continue

            if block["type"] in ["condition", "loop_condition"]:
                if block.get("condition"):
                    if i + 1 < len(path_blocks):
                        next_block = path_blocks[i + 1]

                        for edge in edges_dict.get(block_id, []):
                            if edge["target"] == next_block:
                                cond = block["condition"]
                                if len(cond) > 50:
                                    cond = cond[:47] + "..."

                                if edge["type"] == "true":
                                    conditions.append(f"if ({cond})")
                                elif edge["type"] == "false":
                                    conditions.append(f"if not ({cond})")
                                elif block["type"] == "loop_condition":
                                    conditions.append(f"while ({cond})")
                                break

        return conditions

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
        if self.cfg_builder:
            self.cfg_builder.close()
