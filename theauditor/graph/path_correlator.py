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
        
        Reports factual control flow conditions, not interpretations.
        """
        clusters = []
        
        # Get all execution paths through function
        try:
            # CFGBuilder returns List[List[int]] - just block IDs
            path_lists = self.cfg_builder.get_execution_paths(
                cfg["file"],
                cfg["function_name"],
                max_paths=100
            )
        except Exception:
            # If path enumeration fails, fall back to simple paths
            path_lists = self._enumerate_simple_paths(cfg)
        
        # Check each path for findings
        for path_blocks in path_lists:
            path_blocks_set = set(path_blocks)
            findings_on_path = []
            
            # Collect all findings on this path
            for block_id, block_findings in findings_to_blocks.items():
                if block_id in path_blocks_set:
                    findings_on_path.extend(block_findings)
            
            # Create cluster if multiple findings on same path
            if len(findings_on_path) >= 2:
                # Extract path conditions for this execution path
                path_conditions = self._extract_path_conditions(cfg, path_blocks)
                
                # Build factual description
                description = f"{len(findings_on_path)} findings on same execution path"
                if path_conditions:
                    # Report the actual control flow conditions as facts
                    description += f" when: {' AND '.join(path_conditions)}"
                
                # Create cluster with factual information
                clusters.append({
                    "type": "path_cluster",
                    "confidence": 0.95,  # High confidence - same execution path
                    "path_blocks": path_blocks,
                    "conditions": path_conditions,  # Factual code conditions
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
    
    def _enumerate_simple_paths(self, cfg: Dict) -> List[List[int]]:
        """Simple path enumeration fallback using edges.
        
        Returns List[List[int]] to match CFGBuilder API.
        """
        edges = cfg.get("edges", [])
        
        # Build adjacency list
        graph = defaultdict(list)
        for edge in edges:
            # Skip back edges to avoid infinite loops
            if edge["type"] != "back_edge":
                graph[edge["source"]].append(edge["target"])
        
        # Find entry blocks
        all_targets = {e["target"] for e in edges}
        all_sources = {e["source"] for e in edges}
        entry_blocks = all_sources - all_targets
        
        # If no clear entry, use blocks with type='entry'
        if not entry_blocks:
            for block in cfg.get("blocks", []):
                if block.get("type") == "entry":
                    entry_blocks.add(block["id"])
                    break
            else:
                # Use first block as entry
                if cfg.get("blocks"):
                    entry_blocks.add(cfg["blocks"][0]["id"])
        
        # Find exit blocks
        exit_blocks = {b["id"] for b in cfg.get("blocks", []) 
                      if b.get("type") == "exit"}
        if not exit_blocks:
            # Blocks with no outgoing edges
            exit_blocks = all_targets - all_sources
        
        # DFS to find paths
        paths = []
        for entry in entry_blocks:
            stack = [(entry, [entry])]
            
            while stack and len(paths) < 20:  # Limit paths for performance
                node, path = stack.pop()
                
                if node in exit_blocks or node not in graph:
                    paths.append(path)  # Return List[int] format
                else:
                    for neighbor in graph[node]:
                        if neighbor not in path:  # Avoid cycles
                            stack.append((neighbor, path + [neighbor]))
        
        return paths
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
        if self.cfg_builder:
            self.cfg_builder.close()