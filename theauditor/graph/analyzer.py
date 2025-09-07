"""Graph analyzer module - pure graph algorithms for dependency and call graphs.

This module provides ONLY non-interpretive graph algorithms:
- Cycle detection (DFS)
- Shortest path finding (BFS)
- Layer identification (topological sort)
- Impact analysis (graph traversal)
- Statistical summaries (counts and grouping)

For interpretive metrics like health scores, recommendations, and weighted
rankings, see the optional graph.insights module.
"""

from collections import defaultdict
from pathlib import Path
from typing import Any


class XGraphAnalyzer:
    """Analyze cross-project dependency and call graphs using pure algorithms."""
    
    def detect_cycles(self, graph: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Detect cycles in the dependency graph using DFS.
        
        This is a pure graph algorithm that returns raw cycle data
        without any interpretation or scoring.
        
        Args:
            graph: Graph with 'nodes' and 'edges' keys
            
        Returns:
            List of cycles, each with nodes and size
        """
        # Build adjacency list
        adj = defaultdict(list)
        for edge in graph.get("edges", []):
            adj[edge["source"]].append(edge["target"])
        
        # Track visited nodes and recursion stack
        visited = set()
        rec_stack = set()
        cycles = []
        
        def dfs(node: str, path: list[str]) -> None:
            """DFS to detect cycles."""
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in adj[node]:
                if neighbor not in visited:
                    dfs(neighbor, path.copy())
                elif neighbor in rec_stack:
                    # Found a cycle
                    cycle_start = path.index(neighbor)
                    cycle_nodes = path[cycle_start:] + [neighbor]
                    cycles.append({
                        "nodes": cycle_nodes,
                        "size": len(cycle_nodes) - 1,  # Don't count repeated node
                    })
            
            rec_stack.remove(node)
        
        # Run DFS from all unvisited nodes
        for node in graph.get("nodes", []):
            node_id = node["id"]
            if node_id not in visited:
                dfs(node_id, [])
        
        # Sort cycles by size (largest first)
        cycles.sort(key=lambda c: c["size"], reverse=True)
        
        return cycles
    
    def impact_of_change(
        self,
        targets: list[str],
        import_graph: dict[str, Any],
        call_graph: dict[str, Any] | None = None,
        max_depth: int = 3,
    ) -> dict[str, Any]:
        """
        Calculate the impact of changing target files using graph traversal.
        
        This is a pure graph algorithm that finds affected nodes
        without interpreting or scoring the impact.
        
        Args:
            targets: List of file/module IDs that will change
            import_graph: Import/dependency graph
            call_graph: Optional call graph
            max_depth: Maximum traversal depth
            
        Returns:
            Raw impact data with upstream and downstream effects
        """
        # Build adjacency lists
        upstream = defaultdict(list)  # Who depends on X
        downstream = defaultdict(list)  # What X depends on
        
        for edge in import_graph.get("edges", []):
            downstream[edge["source"]].append(edge["target"])
            upstream[edge["target"]].append(edge["source"])
        
        if call_graph:
            for edge in call_graph.get("edges", []):
                downstream[edge["source"]].append(edge["target"])
                upstream[edge["target"]].append(edge["source"])
        
        # Find upstream impact (what depends on targets)
        upstream_impact = set()
        to_visit = [(t, 0) for t in targets]
        visited = set()
        
        while to_visit:
            node, depth = to_visit.pop(0)
            if node in visited or depth >= max_depth:
                continue
            visited.add(node)
            
            for dependent in upstream[node]:
                upstream_impact.add(dependent)
                to_visit.append((dependent, depth + 1))
        
        # Find downstream impact (what targets depend on)
        downstream_impact = set()
        to_visit = [(t, 0) for t in targets]
        visited = set()
        
        while to_visit:
            node, depth = to_visit.pop(0)
            if node in visited or depth >= max_depth:
                continue
            visited.add(node)
            
            for dependency in downstream[node]:
                downstream_impact.add(dependency)
                to_visit.append((dependency, depth + 1))
        
        # Return raw counts without ratios or interpretations
        all_impacted = set(targets) | upstream_impact | downstream_impact
        
        return {
            "targets": targets,
            "upstream": sorted(upstream_impact),
            "downstream": sorted(downstream_impact),
            "total_impacted": len(all_impacted),
            "graph_nodes": len(import_graph.get("nodes", [])),
        }
    
    def find_shortest_path(
        self, 
        source: str, 
        target: str, 
        graph: dict[str, Any]
    ) -> list[str] | None:
        """
        Find shortest path between two nodes using BFS.
        
        Pure pathfinding algorithm without interpretation.
        
        Args:
            source: Source node ID
            target: Target node ID
            graph: Graph with edges
            
        Returns:
            List of node IDs forming the path, or None if no path exists
        """
        # Build adjacency list
        adj = defaultdict(list)
        for edge in graph.get("edges", []):
            adj[edge["source"]].append(edge["target"])
        
        # BFS
        queue = [(source, [source])]
        visited = {source}
        
        while queue:
            node, path = queue.pop(0)
            
            if node == target:
                return path
            
            for neighbor in adj[node]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        
        return None
    
    def identify_layers(self, graph: dict[str, Any]) -> dict[str, list[str]]:
        """
        Identify architectural layers using topological sorting.
        
        Pure graph layering algorithm without interpretation.
        
        Args:
            graph: Import/dependency graph
            
        Returns:
            Dict mapping layer number to list of node IDs
        """
        # Calculate in-degrees
        in_degree = defaultdict(int)
        nodes = {node["id"] for node in graph.get("nodes", [])}
        
        for edge in graph.get("edges", []):
            in_degree[edge["target"]] += 1
        
        # Find nodes with no dependencies (layer 0)
        layers = {}
        current_layer = []
        
        for node_id in nodes:
            if in_degree[node_id] == 0:
                current_layer.append(node_id)
        
        # Build layers using modified topological sort
        layer_num = 0
        adj = defaultdict(list)
        
        for edge in graph.get("edges", []):
            adj[edge["source"]].append(edge["target"])
        
        while current_layer:
            layers[layer_num] = current_layer
            next_layer = []
            
            for node in current_layer:
                for neighbor in adj[node]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        next_layer.append(neighbor)
            
            current_layer = next_layer
            layer_num += 1
        
        return layers
    
    def get_graph_summary(self, graph_data: dict[str, Any]) -> dict[str, Any]:
        """
        Extract basic statistics from a graph without interpretation.
        
        This method provides raw counts and statistics only,
        no subjective metrics or labels.
        
        Args:
            graph_data: Large graph dict with 'nodes' and 'edges'
            
        Returns:
            Concise summary with raw statistics only
        """
        # Basic statistics
        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])
        
        # Calculate in/out degrees
        in_degree = defaultdict(int)
        out_degree = defaultdict(int)
        for edge in edges:
            out_degree[edge["source"]] += 1
            in_degree[edge["target"]] += 1
        
        # Find most connected nodes (raw data only)
        connection_counts = []
        for node in nodes:  # Process all nodes
            node_id = node["id"]
            total = in_degree[node_id] + out_degree[node_id]
            if total > 0:
                connection_counts.append({
                    "id": node_id,
                    "in_degree": in_degree[node_id],
                    "out_degree": out_degree[node_id],
                    "total_connections": total
                })
        
        # Sort and get top 10
        connection_counts.sort(key=lambda x: x["total_connections"], reverse=True)
        top_connected = connection_counts[:10]
        
        # Detect cycles (complete search)
        cycles = self.detect_cycles({"nodes": nodes, "edges": edges})
        
        # Calculate graph metrics
        node_count = len(nodes)
        edge_count = len(edges)
        density = edge_count / (node_count * (node_count - 1)) if node_count > 1 else 0
        
        # Find isolated nodes
        connected_nodes = set()
        for edge in edges:
            connected_nodes.add(edge["source"])
            connected_nodes.add(edge["target"])
        isolated_count = len([n for n in nodes if n["id"] not in connected_nodes])
        
        # Create summary with raw data only
        summary = {
            "statistics": {
                "total_nodes": node_count,
                "total_edges": edge_count,
                "graph_density": round(density, 4),
                "isolated_nodes": isolated_count,
                "average_connections": round(edge_count / node_count, 2) if node_count > 0 else 0
            },
            "top_connected_nodes": top_connected,
            "cycles_found": [
                {
                    "size": cycle["size"],
                    "nodes": cycle["nodes"][:5] + (["..."] if len(cycle["nodes"]) > 5 else [])
                }
                for cycle in cycles[:5]
            ],
            "file_types": self._count_file_types(nodes),
            "connection_distribution": {
                "nodes_with_20_plus_connections": len([c for c in connection_counts if c["total_connections"] > 20]),
                "nodes_with_30_plus_inbound": len([c for c in connection_counts if c["in_degree"] > 30]),
                "cycle_count": len(cycles) if len(nodes) < 500 else f"{len(cycles)}+ (limited search)",
            }
        }
        
        return summary
    
    def _count_file_types(self, nodes: list[dict]) -> dict[str, int]:
        """Count nodes by file extension - pure counting, no interpretation."""
        ext_counts = defaultdict(int)
        for node in nodes:  # Process all nodes
            if "file" in node:
                ext = Path(node["file"]).suffix or "no_ext"
                ext_counts[ext] += 1
        # Return top 10 extensions
        sorted_exts = sorted(ext_counts.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_exts[:10])
    
    def identify_hotspots(self, graph: dict[str, Any], top_n: int = 10) -> list[dict[str, Any]]:
        """
        Identify hotspot nodes based on connectivity (in/out degree).
        
        Pure graph algorithm that identifies most connected nodes
        without interpretation or scoring.
        
        Args:
            graph: Graph with 'nodes' and 'edges'
            top_n: Number of top hotspots to return
            
        Returns:
            List of hotspot nodes with their degree counts
        """
        # Calculate in/out degrees
        in_degree = defaultdict(int)
        out_degree = defaultdict(int)
        
        for edge in graph.get("edges", []):
            out_degree[edge["source"]] += 1
            in_degree[edge["target"]] += 1
        
        # Calculate total connections for each node
        hotspots = []
        for node in graph.get("nodes", []):
            node_id = node["id"]
            in_deg = in_degree[node_id]
            out_deg = out_degree[node_id]
            total = in_deg + out_deg
            
            if total > 0:  # Only include connected nodes
                hotspots.append({
                    "id": node_id,
                    "in_degree": in_deg,
                    "out_degree": out_deg,
                    "total_connections": total,
                    "file": node.get("file", node_id),
                    "lang": node.get("lang", "unknown")
                })
        
        # Sort by total connections and return top N
        hotspots.sort(key=lambda x: x["total_connections"], reverse=True)
        return hotspots[:top_n]
    
    def calculate_node_degrees(self, graph: dict[str, Any]) -> dict[str, dict[str, int]]:
        """
        Calculate in-degree and out-degree for all nodes.
        
        Pure counting algorithm without interpretation.
        
        Args:
            graph: Graph with edges
            
        Returns:
            Dict mapping node IDs to degree counts
        """
        degrees = defaultdict(lambda: {"in_degree": 0, "out_degree": 0})
        
        for edge in graph.get("edges", []):
            degrees[edge["source"]]["out_degree"] += 1
            degrees[edge["target"]]["in_degree"] += 1
        
        return dict(degrees)
    
    def analyze_impact(self, graph: dict[str, Any], targets: list[str], max_depth: int = 3) -> dict[str, Any]:
        """
        Analyze impact of changes to target nodes.
        
        Wrapper method for impact_of_change to match expected API.
        
        Args:
            graph: Graph with 'nodes' and 'edges'
            targets: List of target node IDs
            max_depth: Maximum traversal depth
            
        Returns:
            Impact analysis results with upstream/downstream effects
        """
        # Use existing impact_of_change method
        result = self.impact_of_change(targets, graph, None, max_depth)
        
        # Add all_impacted field for compatibility
        all_impacted = set(targets) | set(result.get("upstream", [])) | set(result.get("downstream", []))
        result["all_impacted"] = sorted(all_impacted)
        
        return result