"""Graph analyzer module - pure graph algorithms for dependency and call graphs."""

from collections import defaultdict, deque
from pathlib import Path
from typing import Any


class XGraphAnalyzer:
    """Analyze cross-project dependency and call graphs using pure algorithms."""

    def __init__(self, graph: dict[str, Any] | None = None):
        """Initialize analyzer with optional graph for caching."""
        self.upstream = defaultdict(list)
        self.downstream = defaultdict(list)
        self.nodes = set()
        self._cached = False

        if graph:
            self._build_index(graph)

    def _build_index(self, graph: dict[str, Any]) -> None:
        """Build adjacency list indices from graph data."""
        self.nodes = {n["id"] for n in graph.get("nodes", [])}

        for edge in graph.get("edges", []):
            source = edge["source"]
            target = edge["target"]
            self.downstream[source].append(target)
            self.upstream[target].append(source)

        self._cached = True

    def detect_cycles(self, graph: dict[str, Any]) -> list[dict[str, Any]]:
        """Detect cycles using ITERATIVE DFS (stack-based).

        GRAPH FIX G3: Filter out _reverse edges to prevent false cycle detection.
        Bidirectional edges (A->B, B->A_reverse) would otherwise report every
        import as a 2-node cycle.
        """

        adj = defaultdict(list)
        for edge in graph.get("edges", []):
            if edge.get("type", "").endswith("_reverse"):
                continue
            adj[edge["source"]].append(edge["target"])

        visited = set()
        cycles = []

        nodes = [n["id"] for n in graph.get("nodes", [])]

        for start_node in nodes:
            if start_node in visited:
                continue

            stack = [(start_node, iter(adj[start_node]))]

            path_set = {start_node}
            path_list = [start_node]
            visited.add(start_node)

            while stack:
                parent, children = stack[-1]

                try:
                    child = next(children)

                    if child in path_set:
                        cycle_start_index = path_list.index(child)
                        cycle_nodes = path_list[cycle_start_index:] + [child]
                        cycles.append({"nodes": cycle_nodes, "size": len(cycle_nodes) - 1})

                    elif child not in visited:
                        visited.add(child)
                        path_set.add(child)
                        path_list.append(child)
                        stack.append((child, iter(adj[child])))

                except StopIteration:
                    stack.pop()
                    if path_list:
                        path_set.discard(parent)
                        path_list.pop()

        cycles.sort(key=lambda c: c["size"], reverse=True)

        return cycles

    def impact_of_change(
        self,
        targets: list[str],
        import_graph: dict[str, Any],
        call_graph: dict[str, Any] | None = None,
        max_depth: int = 3,
    ) -> dict[str, Any]:
        """Calculate the impact of changing target files using graph traversal."""

        if self._cached:
            upstream = self.upstream
            downstream = self.downstream
        else:
            upstream = defaultdict(list)
            downstream = defaultdict(list)

            for edge in import_graph.get("edges", []):
                if edge.get("type", "").endswith("_reverse"):
                    continue
                downstream[edge["source"]].append(edge["target"])
                upstream[edge["target"]].append(edge["source"])

            if call_graph:
                for edge in call_graph.get("edges", []):
                    if edge.get("type", "").endswith("_reverse"):
                        continue
                    downstream[edge["source"]].append(edge["target"])
                    upstream[edge["target"]].append(edge["source"])

        upstream_impact = set()
        to_visit = deque([(t, 0) for t in targets])
        visited = set()

        while to_visit:
            node, depth = to_visit.popleft()
            if node in visited or depth >= max_depth:
                continue
            visited.add(node)

            for dependent in upstream[node]:
                upstream_impact.add(dependent)
                to_visit.append((dependent, depth + 1))

        downstream_impact = set()
        to_visit = deque([(t, 0) for t in targets])
        visited = set()

        while to_visit:
            node, depth = to_visit.popleft()
            if node in visited or depth >= max_depth:
                continue
            visited.add(node)

            for dependency in downstream[node]:
                downstream_impact.add(dependency)
                to_visit.append((dependency, depth + 1))

        all_impacted = set(targets) | upstream_impact | downstream_impact

        return {
            "targets": targets,
            "upstream": sorted(upstream_impact),
            "downstream": sorted(downstream_impact),
            "total_impacted": len(all_impacted),
            "graph_nodes": len(import_graph.get("nodes", [])),
        }

    def find_shortest_path(
        self, source: str, target: str, graph: dict[str, Any]
    ) -> list[str] | None:
        """Find shortest path between two nodes using BFS with deque."""

        adj = defaultdict(list)
        for edge in graph.get("edges", []):
            adj[edge["source"]].append(edge["target"])

        queue = deque([(source, [source])])
        visited = {source}

        while queue:
            node, path = queue.popleft()

            if node == target:
                return path

            for neighbor in adj[node]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return None

    def identify_layers(self, graph: dict[str, Any]) -> dict[str, list[str]]:
        """Identify architectural layers using topological sorting."""

        in_degree = defaultdict(int)
        nodes = {node["id"] for node in graph.get("nodes", [])}

        for edge in graph.get("edges", []):
            in_degree[edge["target"]] += 1

        layers = {}
        current_layer = []

        for node_id in nodes:
            if in_degree[node_id] == 0:
                current_layer.append(node_id)

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
        """Extract basic statistics from a graph without interpretation."""

        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])

        in_degree = defaultdict(int)
        out_degree = defaultdict(int)
        for edge in edges:
            out_degree[edge["source"]] += 1
            in_degree[edge["target"]] += 1

        connection_counts = []
        for node in nodes:
            node_id = node["id"]
            total = in_degree[node_id] + out_degree[node_id]
            if total > 0:
                connection_counts.append(
                    {
                        "id": node_id,
                        "in_degree": in_degree[node_id],
                        "out_degree": out_degree[node_id],
                        "total_connections": total,
                    }
                )

        connection_counts.sort(key=lambda x: x["total_connections"], reverse=True)
        top_connected = connection_counts[:10]

        cycles = self.detect_cycles({"nodes": nodes, "edges": edges})

        node_count = len(nodes)
        edge_count = len(edges)
        density = edge_count / (node_count * (node_count - 1)) if node_count > 1 else 0

        connected_nodes = set()
        for edge in edges:
            connected_nodes.add(edge["source"])
            connected_nodes.add(edge["target"])
        isolated_nodes = [n["id"] for n in nodes if n["id"] not in connected_nodes]
        isolated_count = len(isolated_nodes)

        summary = {
            "statistics": {
                "total_nodes": node_count,
                "total_edges": edge_count,
                "graph_density": round(density, 4),
                "isolated_nodes": isolated_count,
                "isolated_nodes_list": isolated_nodes,
                "average_connections": round(edge_count / node_count, 2) if node_count > 0 else 0,
            },
            "top_connected_nodes": top_connected,
            "cycles_found": [
                {
                    "size": cycle["size"],
                    "nodes": cycle["nodes"][:5] + (["..."] if len(cycle["nodes"]) > 5 else []),
                }
                for cycle in cycles[:5]
            ],
            "file_types": self._count_file_types(nodes),
            "connection_distribution": {
                "nodes_with_20_plus_connections": len(
                    [c for c in connection_counts if c["total_connections"] > 20]
                ),
                "nodes_with_30_plus_inbound": len(
                    [c for c in connection_counts if c["in_degree"] > 30]
                ),
                "cycle_count": len(cycles)
                if len(nodes) < 500
                else f"{len(cycles)}+ (limited search)",
            },
        }

        return summary

    def _count_file_types(self, nodes: list[dict]) -> dict[str, int]:
        """Count nodes by file extension - pure counting, no interpretation."""
        ext_counts = defaultdict(int)
        for node in nodes:
            if "file" in node:
                ext = Path(node["file"]).suffix or "no_ext"
                ext_counts[ext] += 1

        sorted_exts = sorted(ext_counts.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_exts[:10])

    def identify_hotspots(self, graph: dict[str, Any], top_n: int = 10) -> list[dict[str, Any]]:
        """Identify hotspot nodes based on connectivity (in/out degree)."""

        in_degree = defaultdict(int)
        out_degree = defaultdict(int)

        for edge in graph.get("edges", []):
            out_degree[edge["source"]] += 1
            in_degree[edge["target"]] += 1

        hotspots = []
        for node in graph.get("nodes", []):
            node_id = node["id"]
            in_deg = in_degree[node_id]
            out_deg = out_degree[node_id]
            total = in_deg + out_deg

            if total > 0:
                hotspots.append(
                    {
                        "id": node_id,
                        "in_degree": in_deg,
                        "out_degree": out_deg,
                        "total_connections": total,
                        "file": node.get("file", node_id),
                        "lang": node.get("lang", "unknown"),
                    }
                )

        hotspots.sort(key=lambda x: x["total_connections"], reverse=True)
        return hotspots[:top_n]

    def calculate_node_degrees(self, graph: dict[str, Any]) -> dict[str, dict[str, int]]:
        """Calculate in-degree and out-degree for all nodes."""
        degrees = defaultdict(lambda: {"in_degree": 0, "out_degree": 0})

        for edge in graph.get("edges", []):
            degrees[edge["source"]]["out_degree"] += 1
            degrees[edge["target"]]["in_degree"] += 1

        return dict(degrees)

    def analyze_impact(
        self, graph: dict[str, Any], targets: list[str], max_depth: int = 3
    ) -> dict[str, Any]:
        """Analyze impact of changes to target nodes."""

        result = self.impact_of_change(targets, graph, None, max_depth)

        all_impacted = (
            set(targets) | set(result.get("upstream", [])) | set(result.get("downstream", []))
        )
        result["all_impacted"] = sorted(all_impacted)

        return result
