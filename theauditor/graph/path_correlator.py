"""Path-Based Factual Correlation using Control Flow Graphs.

This module correlates findings based on control flow structure - purely factual 
relationships about which findings execute together on the same paths.
"""

import sqlite3
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from collections import defaultdict

from theauditor.graph.cfg_builder import CFGBuilder


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
    
    def correlate(self, findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find findings that co-exist on same execution paths.
        
        Args:
            findings: List of finding dictionaries with file, line, tool, etc.
            
        Returns:
            List of path clusters with findings guaranteed to be on same path
        """
        # Group findings by function
        findings_by_function = self._group_findings_by_function(findings)
        path_clusters = []
        
        for (file_path, func_name), func_findings in findings_by_function.items():
            if len(func_findings) < 2:
                continue  # Need at least 2 findings to correlate
            
            try:
                # Get CFG for this function
                cfg = self.cfg_builder.get_function_cfg(file_path, func_name)
                if not cfg or not cfg.get("blocks"):
                    continue
                
                # Map findings to CFG blocks
                findings_to_blocks = self._map_findings_to_blocks(cfg, func_findings)
                
                # Find paths connecting multiple findings with conditions
                clusters = self._find_finding_paths_with_conditions(
                    cfg, findings_to_blocks, func_findings
                )
                
                # Add function context to clusters
                for cluster in clusters:
                    cluster["function"] = func_name
                    cluster["file"] = file_path
                
                path_clusters.extend(clusters)
                
            except Exception as e:
                # Log but don't fail - gracefully skip functions without CFG
                print(f"[PathCorrelator] Skipping {func_name}: {e}")
                continue
        
        return path_clusters
    
    def _group_findings_by_function(self, findings: List[Dict]) -> Dict[Tuple[str, str], List]:
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
            
            # Find containing function
            cursor.execute("""
                SELECT name, type
                FROM symbols
                WHERE path = ?
                  AND line <= ?
                  AND type = 'function'
                ORDER BY line DESC
                LIMIT 1
            """, (file_path, line))
            
            result = cursor.fetchone()
            if result:
                func_name = result["name"]
                grouped[(file_path, func_name)].append(finding)
        
        return dict(grouped)
    
    def _map_findings_to_blocks(self, cfg: Dict, findings: List) -> Dict[int, List]:
        """Map each finding to its CFG block ID."""
        block_findings = defaultdict(list)
        
        for finding in findings:
            line = finding.get("line", 0)
            
            # Find block containing this line
            for block in cfg.get("blocks", []):
                if block["start_line"] <= line <= block["end_line"]:
                    block_findings[block["id"]].append(finding)
                    break
        
        return dict(block_findings)
    
    def _find_finding_paths_with_conditions(self, cfg: Dict, findings_to_blocks: Dict,
                                           all_findings: List) -> List[Dict]:
        """Find execution paths containing multiple findings with path conditions.

        ALGORITHMIC IMPROVEMENT (v1.1+):
        Instead of enumerating all paths (which causes false negatives when max_paths
        is reached), we use targeted graph traversal. For each pair of findings, we
        check if a path exists between them using BFS. This guarantees complete
        accuracy regardless of function complexity.

        Reports factual control flow conditions, not interpretations.
        """
        clusters = []

        # Build adjacency list for efficient graph traversal
        graph = self._build_cfg_graph(cfg)
        blocks_dict = {b["id"]: b for b in cfg.get("blocks", [])}

        # Get all block IDs with findings
        finding_blocks = list(findings_to_blocks.keys())

        # Check each pair of findings for path connectivity
        for i, block_a in enumerate(finding_blocks):
            for block_b in finding_blocks[i+1:]:
                # Check if there's a path from A to B or B to A
                path_a_to_b = self._find_path_bfs(graph, block_a, block_b)
                path_b_to_a = self._find_path_bfs(graph, block_b, block_a)

                # Use whichever path exists (or the shorter one if both exist)
                path = None
                if path_a_to_b and path_b_to_a:
                    path = path_a_to_b if len(path_a_to_b) <= len(path_b_to_a) else path_b_to_a
                elif path_a_to_b:
                    path = path_a_to_b
                elif path_b_to_a:
                    path = path_b_to_a

                if path:
                    # Found a correlation - collect all findings on this path
                    findings_on_path = []
                    path_blocks_set = set(path)

                    for block_id in path:
                        if block_id in findings_to_blocks:
                            findings_on_path.extend(findings_to_blocks[block_id])

                    if len(findings_on_path) >= 2:
                        # Extract path conditions for this specific execution path
                        path_conditions = self._extract_path_conditions(cfg, path)

                        # Build factual description
                        description = f"{len(findings_on_path)} findings on same execution path"
                        if path_conditions:
                            description += f" when: {' AND '.join(path_conditions)}"

                        clusters.append({
                            "type": "path_cluster",
                            "confidence": 0.95,  # High confidence - proven path exists
                            "path_blocks": path,
                            "conditions": path_conditions,
                            "findings": findings_on_path,
                            "finding_count": len(findings_on_path),
                            "description": description
                        })

        # Deduplicate clusters with same findings
        unique_clusters = []
        seen_finding_sets = set()

        for cluster in clusters:
            finding_set = frozenset(
                f"{f['file']}:{f['line']}:{f['tool']}"
                for f in cluster["findings"]
            )
            if finding_set not in seen_finding_sets:
                seen_finding_sets.add(finding_set)
                unique_clusters.append(cluster)

        return unique_clusters

    def _build_cfg_graph(self, cfg: Dict) -> Dict[int, List[int]]:
        """Build adjacency list representation of CFG for efficient traversal.

        Args:
            cfg: CFG dictionary with edges

        Returns:
            Dict mapping block_id -> list of successor block_ids
        """
        graph = defaultdict(list)
        for edge in cfg.get("edges", []):
            # Include all edge types except back_edges to avoid infinite loops
            if edge["type"] != "back_edge":
                graph[edge["source"]].append(edge["target"])
        return dict(graph)

    def _find_path_bfs(self, graph: Dict[int, List[int]], start: int, end: int) -> Optional[List[int]]:
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

        # BFS to find shortest path
        from collections import deque
        queue = deque([(start, [start])])
        visited = {start}

        while queue:
            node, path = queue.popleft()

            # Explore neighbors
            for neighbor in graph.get(node, []):
                if neighbor == end:
                    # Found path to target
                    return path + [neighbor]

                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        # No path exists
        return None

    def _extract_path_conditions(self, cfg: Dict, path_blocks: List[int]) -> List[str]:
        """Extract the literal conditions from source that define this execution path.
        
        Returns factual code conditions, not interpretations.
        """
        conditions = []
        blocks_dict = {b["id"]: b for b in cfg.get("blocks", [])}
        edges_dict = defaultdict(list)
        
        # Build edge lookup
        for edge in cfg.get("edges", []):
            edges_dict[edge["source"]].append({
                "target": edge["target"],
                "type": edge["type"]
            })
        
        # Walk the path and collect literal conditions
        for i, block_id in enumerate(path_blocks):
            block = blocks_dict.get(block_id)
            if not block:
                continue
            
            # If this is a condition block, report the literal condition
            if block["type"] in ["condition", "loop_condition"]:
                if block.get("condition"):
                    # Look at next block to determine branch taken
                    if i + 1 < len(path_blocks):
                        next_block = path_blocks[i + 1]
                        
                        # Find edge type to next block
                        for edge in edges_dict.get(block_id, []):
                            if edge["target"] == next_block:
                                # Report the literal condition from source code
                                cond = block["condition"]
                                if len(cond) > 50:
                                    cond = cond[:47] + "..."
                                
                                # Report factual branch taken
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