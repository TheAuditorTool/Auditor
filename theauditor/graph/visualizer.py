"""Graph visualizer module - rich Graphviz visualization with visual intelligence."""

from pathlib import Path
from typing import Any


class GraphVisualizer:
    """Transform graph analysis into actionable visualizations."""

    LANGUAGE_COLORS = {
        "python": "#3776AB",
        "javascript": "#F7DF1E",
        "typescript": "#3178C6",
        "java": "#007396",
        "go": "#00ADD8",
        "rust": "#CE4E21",
        "c": "#A8B9CC",
        "c++": "#00599C",
        "c#": "#239120",
        "ruby": "#CC342D",
        "php": "#777BB4",
        "default": "#808080",
    }

    RISK_COLORS = {
        "critical": "#D32F2F",
        "high": "#F57C00",
        "medium": "#FBC02D",
        "low": "#689F38",
        "info": "#1976D2",
    }

    def __init__(self):
        """Initialize the visualizer."""
        self.cycle_edges = set()
        self.node_degrees = {}

    def generate_dot(
        self,
        graph: dict[str, Any],
        analysis: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> str:
        """Generate DOT format with visual intelligence encoding."""
        options = options or {}
        analysis = analysis or {}

        self._process_analysis(graph, analysis)

        dot_lines = ["digraph G {"]

        dot_lines.extend(self._generate_graph_attrs(options))

        dot_lines.extend(self._generate_nodes(graph, analysis, options))

        dot_lines.extend(self._generate_edges(graph, analysis, options))

        dot_lines.append("}")

        return "\n".join(dot_lines)

    def _process_analysis(self, graph: dict[str, Any], analysis: dict[str, Any]) -> None:
        """Pre-process analysis data for quick lookup."""

        self.node_degrees.clear()
        for edge in graph.get("edges", []):
            source = edge.get("source", "")
            target = edge.get("target", "")

            if source not in self.node_degrees:
                self.node_degrees[source] = {"in": 0, "out": 0}
            self.node_degrees[source]["out"] += 1

            if target not in self.node_degrees:
                self.node_degrees[target] = {"in": 0, "out": 0}
            self.node_degrees[target]["in"] += 1

        self.cycle_edges.clear()
        cycles = analysis.get("cycles", [])
        for cycle in cycles:
            cycle_nodes = cycle.get("nodes", [])

            for i in range(len(cycle_nodes)):
                source = cycle_nodes[i]
                target = cycle_nodes[(i + 1) % len(cycle_nodes)]
                self.cycle_edges.add((source, target))

    def _generate_graph_attrs(self, options: dict[str, Any]) -> list[str]:
        """Generate global graph attributes."""
        attrs = []
        attrs.append("  rankdir=LR;")
        attrs.append('  bgcolor="white";')
        attrs.append("  nodesep=0.5;")
        attrs.append("  ranksep=1.0;")
        attrs.append('  fontname="Arial";')

        attrs.append('  node [fontname="Arial", fontsize=10, style=filled];')

        attrs.append('  edge [fontname="Arial", fontsize=8];')

        if options.get("title"):
            attrs.append(f'  label="{options["title"]}";')
            attrs.append("  labelloc=t;")
            attrs.append("  fontsize=14;")

        return attrs

    def _generate_nodes(
        self, graph: dict[str, Any], analysis: dict[str, Any], options: dict[str, Any]
    ) -> list[str]:
        """Generate nodes with visual encoding."""
        node_lines = []
        nodes = graph.get("nodes", [])

        hotspots = analysis.get("hotspots", [])
        hotspot_ids = {h["id"]: h for h in hotspots[:10]}

        max_nodes = options.get("max_nodes", 500)
        if len(nodes) > max_nodes:
            nodes = sorted(
                nodes,
                key=lambda n: self.node_degrees.get(n["id"], {"in": 0, "out": 0})["in"]
                + self.node_degrees.get(n["id"], {"in": 0, "out": 0})["out"],
                reverse=True,
            )[:max_nodes]

        for node in nodes:
            node_id = node.get("id", "")
            node_file = node.get("file", node_id)
            node_lang = node.get("lang", "default")
            node_type = node.get("type", "module")

            safe_id = self._sanitize_id(node_id)

            color = self.LANGUAGE_COLORS.get(node_lang, self.LANGUAGE_COLORS["default"])

            degrees = self.node_degrees.get(node_id, {"in": 0, "out": 0})
            in_degree = degrees["in"]

            if in_degree > 30:
                size = 2.0
            elif in_degree > 20:
                size = 1.5
            elif in_degree > 10:
                size = 1.2
            elif in_degree > 5:
                size = 1.0
            else:
                size = 0.8

            if node_type == "function":
                shape = "ellipse"
            elif node_type == "class":
                shape = "diamond"
            else:
                shape = "box"

            label = self._generate_node_label(node_id, node_file)

            attrs = []
            attrs.append(f'label="{label}"')
            attrs.append(f'fillcolor="{color}"')
            attrs.append(f"shape={shape}")
            attrs.append(f"width={size}")
            attrs.append(f"height={size * 0.7}")

            if node_id in hotspot_ids:
                attrs.append("penwidth=3")
                attrs.append("fontsize=12")
                attrs.append('fontcolor="black"')

                hotspot = hotspot_ids[node_id]
                tooltip = (
                    f"Hotspot: in={hotspot.get('in_degree', 0)}, out={hotspot.get('out_degree', 0)}"
                )
                attrs.append(f'tooltip="{tooltip}"')
            else:
                attrs.append("penwidth=1")
                attrs.append('fontcolor="white"')

            node_line = f"  {safe_id} [{', '.join(attrs)}];"
            node_lines.append(node_line)

        return node_lines

    def _generate_edges(
        self, graph: dict[str, Any], analysis: dict[str, Any], options: dict[str, Any]
    ) -> list[str]:
        """Generate edges with visual encoding."""
        edge_lines = []
        edges = graph.get("edges", [])

        node_ids = {n["id"] for n in graph.get("nodes", [])}
        max_nodes = options.get("max_nodes", 500)
        if len(node_ids) > max_nodes:
            important_nodes = set(list(node_ids)[:max_nodes])
            edges = [
                e
                for e in edges
                if e.get("source") in important_nodes and e.get("target") in important_nodes
            ]

        for edge in edges:
            source = edge.get("source", "")
            target = edge.get("target", "")
            edge_type = edge.get("type", "import")

            if source == target and not options.get("show_self_loops"):
                continue

            safe_source = self._sanitize_id(source)
            safe_target = self._sanitize_id(target)

            attrs = []

            if (source, target) in self.cycle_edges:
                attrs.append('color="#D32F2F"')
                attrs.append("penwidth=2")
                attrs.append('fontcolor="#D32F2F"')
                attrs.append('label="cycle"')
            else:
                attrs.append('color="#666666"')
                attrs.append("penwidth=1")

            if edge_type == "call":
                attrs.append("style=dashed")
            elif edge_type == "extends" or edge_type == "implements":
                attrs.append("style=bold")
            else:
                attrs.append("style=solid")

            if edge_type == "extends":
                attrs.append("arrowhead=empty")
            elif edge_type == "implements":
                attrs.append("arrowhead=odiamond")
            else:
                attrs.append("arrowhead=normal")

            if attrs:
                edge_line = f"  {safe_source} -> {safe_target} [{', '.join(attrs)}];"
            else:
                edge_line = f"  {safe_source} -> {safe_target};"

            edge_lines.append(edge_line)

        return edge_lines

    def _sanitize_id(self, node_id: str) -> str:
        """Sanitize node ID for DOT format."""

        safe_id = node_id.replace(".", "_")
        safe_id = safe_id.replace("/", "_")
        safe_id = safe_id.replace("\\", "_")
        safe_id = safe_id.replace("-", "_")
        safe_id = safe_id.replace(":", "_")
        safe_id = safe_id.replace(" ", "_")
        safe_id = safe_id.replace("(", "_")
        safe_id = safe_id.replace(")", "_")
        safe_id = safe_id.replace("[", "_")
        safe_id = safe_id.replace("]", "_")

        if safe_id and not safe_id[0].isalpha() and safe_id[0] != "_":
            safe_id = "_" + safe_id

        if safe_id and not safe_id.replace("_", "").isalnum():
            safe_id = f'"{safe_id}"'

        return safe_id

    def _generate_node_label(self, node_id: str, node_file: str) -> str:
        """Generate readable label for a node."""

        if "::" in node_id:
            parts = node_id.split("::")
            if len(parts) >= 2:
                module = Path(parts[0]).stem
                function = parts[1]
                return f"{module}::{function}"
            return node_id
        else:
            path = Path(node_file)
            if path.parts:
                if len(path.parts) > 2:
                    return f".../{path.parts[-2]}/{path.name}"
                elif len(path.parts) > 1:
                    return f"{path.parts[-2]}/{path.name}"
                else:
                    return path.name
            return node_id

    def generate_dot_with_layers(
        self,
        graph: dict[str, Any],
        layers: dict[int, list[str]],
        analysis: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> str:
        """Generate DOT format with architectural layers as subgraphs."""
        options = options or {}
        analysis = analysis or {}

        self._process_analysis(graph, analysis)

        node_map = {n["id"]: n for n in graph.get("nodes", []) if n.get("id") is not None}

        dot_lines = ["digraph G {"]

        dot_lines.extend(self._generate_graph_attrs(options))
        dot_lines.append("  rankdir=TB;")

        valid_layer_nums = [k for k in layers if k is not None]
        for layer_num in sorted(valid_layer_nums):
            layer_nodes = layers[layer_num]
            if not layer_nodes:
                continue

            dot_lines.append(f"  subgraph cluster_layer{layer_num} {{")
            dot_lines.append(f'    label="Layer {layer_num}";')
            dot_lines.append("    style=filled;")
            dot_lines.append('    fillcolor="#F0F0F0";')
            dot_lines.append('    color="#CCCCCC";')
            dot_lines.append("    fontsize=12;")
            dot_lines.append("    rank=same;")

            for node_id in layer_nodes:
                if node_id not in node_map:
                    continue

                node = node_map[node_id]
                node_lang = node.get("lang", "default")
                node_type = node.get("type", "module")

                safe_id = self._sanitize_id(node_id)

                color = self.LANGUAGE_COLORS.get(node_lang, self.LANGUAGE_COLORS["default"])

                degrees = self.node_degrees.get(node_id, {"in": 0, "out": 0})
                in_degree = degrees["in"]

                if in_degree > 30:
                    size = 2.0
                elif in_degree > 20:
                    size = 1.5
                elif in_degree > 10:
                    size = 1.2
                elif in_degree > 5:
                    size = 1.0
                else:
                    size = 0.8

                if node_type == "function":
                    shape = "ellipse"
                elif node_type == "class":
                    shape = "diamond"
                else:
                    shape = "box"

                label = self._generate_node_label(node_id, node.get("file", node_id))

                churn = node.get("churn", 0)
                if churn is None:
                    churn = 0
                if churn > 100:
                    penwidth = 4
                elif churn > 50:
                    penwidth = 3
                elif churn > 20:
                    penwidth = 2
                else:
                    penwidth = 1

                attrs = []
                attrs.append(f'label="{label}"')
                attrs.append(f'fillcolor="{color}"')
                attrs.append(f"shape={shape}")
                attrs.append(f"width={size}")
                attrs.append(f"height={size * 0.7}")
                attrs.append(f"penwidth={penwidth}")
                attrs.append('fontcolor="white"')
                attrs.append("style=filled")

                tooltip = f"Layer {layer_num}: {node_id}"
                if churn > 0:
                    tooltip += f" (churn: {churn})"
                attrs.append(f'tooltip="{tooltip}"')

                node_line = f"    {safe_id} [{', '.join(attrs)}];"
                dot_lines.append(node_line)

            dot_lines.append("  }")

        dot_lines.extend(self._generate_edges(graph, analysis, options))

        dot_lines.append("}")

        return "\n".join(dot_lines)

    def generate_impact_visualization(
        self,
        graph: dict[str, Any],
        impact: dict[str, Any],
        options: dict[str, Any] | None = None,
    ) -> str:
        """Generate DOT highlighting impact analysis results."""
        options = options or {}

        targets = set(impact.get("targets", []))
        upstream = set(impact.get("upstream", []))
        downstream = set(impact.get("downstream", []))

        self._process_analysis(graph, {})

        dot_lines = ["digraph G {"]

        dot_lines.extend(self._generate_graph_attrs(options))

        dot_lines.append("  subgraph cluster_legend {")
        dot_lines.append('    label="Impact Analysis Legend";')
        dot_lines.append("    style=filled;")
        dot_lines.append("    fillcolor=white;")
        dot_lines.append("    node [shape=box, style=filled];")
        dot_lines.append('    legend_target [label="Target", fillcolor="#FF0000"];')
        dot_lines.append('    legend_upstream [label="Upstream", fillcolor="#FF9800"];')
        dot_lines.append('    legend_downstream [label="Downstream", fillcolor="#2196F3"];')
        dot_lines.append('    legend_both [label="Both", fillcolor="#9C27B0"];')
        dot_lines.append('    legend_unaffected [label="Unaffected", fillcolor="#808080"];')
        dot_lines.append("  }")

        node_lines = []
        for node in graph.get("nodes", []):
            node_id = node.get("id", "")
            node_file = node.get("file", node_id)
            node_type = node.get("type", "module")

            safe_id = self._sanitize_id(node_id)

            if node_id in targets:
                color = "#FF0000"
                fontcolor = "white"
                penwidth = 3
            elif node_id in upstream and node_id in downstream:
                color = "#9C27B0"
                fontcolor = "white"
                penwidth = 2
            elif node_id in upstream:
                color = "#FF9800"
                fontcolor = "white"
                penwidth = 2
            elif node_id in downstream:
                color = "#2196F3"
                fontcolor = "white"
                penwidth = 2
            else:
                color = "#E0E0E0"
                fontcolor = "black"
                penwidth = 1

            if node_id in targets:
                size = 1.5
            elif node_id in upstream or node_id in downstream:
                size = 1.2
            else:
                size = 0.8

            if node_type == "function":
                shape = "ellipse"
            elif node_type == "class":
                shape = "diamond"
            else:
                shape = "box"

            label = self._generate_node_label(node_id, node_file)

            attrs = []
            attrs.append(f'label="{label}"')
            attrs.append(f'fillcolor="{color}"')
            attrs.append(f"shape={shape}")
            attrs.append(f"width={size}")
            attrs.append(f"height={size * 0.7}")
            attrs.append(f"penwidth={penwidth}")
            attrs.append(f'fontcolor="{fontcolor}"')
            attrs.append("style=filled")

            tooltip_parts = []
            if node_id in targets:
                tooltip_parts.append("TARGET")
            if node_id in upstream:
                tooltip_parts.append("Upstream")
            if node_id in downstream:
                tooltip_parts.append("Downstream")
            if tooltip_parts:
                tooltip = f"{node_id}: {', '.join(tooltip_parts)}"
            else:
                tooltip = f"{node_id}: Unaffected"
            attrs.append(f'tooltip="{tooltip}"')

            node_line = f"  {safe_id} [{', '.join(attrs)}];"
            node_lines.append(node_line)

        dot_lines.extend(node_lines)

        edge_lines = []
        for edge in graph.get("edges", []):
            source = edge.get("source", "")
            target = edge.get("target", "")

            if source == target and not options.get("show_self_loops"):
                continue

            safe_source = self._sanitize_id(source)
            safe_target = self._sanitize_id(target)

            attrs = []

            if source in targets and target in downstream:
                attrs.append('color="#FF0000"')
                attrs.append("penwidth=3")
            elif source in upstream and target in targets:
                attrs.append('color="#FF9800"')
                attrs.append("penwidth=2")
            elif (source in targets or source in upstream or source in downstream) and (
                target in targets or target in upstream or target in downstream
            ):
                attrs.append('color="#666666"')
                attrs.append("penwidth=1.5")
            else:
                attrs.append('color="#E0E0E0"')
                attrs.append("penwidth=0.5")
                attrs.append("style=dashed")

            attrs.append("arrowhead=normal")

            if attrs:
                edge_line = f"  {safe_source} -> {safe_target} [{', '.join(attrs)}];"
            else:
                edge_line = f"  {safe_source} -> {safe_target};"

            edge_lines.append(edge_line)

        dot_lines.extend(edge_lines)

        dot_lines.append("}")

        return "\n".join(dot_lines)

    def generate_cycles_only_view(
        self,
        graph: dict[str, Any],
        cycles: list[dict[str, Any]],
        options: dict[str, Any] | None = None,
    ) -> str:
        """Generate DOT format showing only nodes and edges involved in cycles."""
        options = options or {}

        cycle_nodes = set()
        cycle_edges = set()

        for cycle in cycles:
            nodes = cycle.get("nodes", [])
            cycle_nodes.update(nodes)

            for i in range(len(nodes)):
                source = nodes[i]
                target = nodes[(i + 1) % len(nodes)]
                cycle_edges.add((source, target))

        if not cycle_nodes:
            return 'digraph G {\n  label="No cycles detected";\n}'

        filtered_graph = {
            "nodes": [n for n in graph.get("nodes", []) if n["id"] in cycle_nodes],
            "edges": [
                e for e in graph.get("edges", []) if (e["source"], e["target"]) in cycle_edges
            ],
        }

        self.cycle_edges = cycle_edges
        self._process_analysis(filtered_graph, {})

        dot_lines = ["digraph G {"]

        dot_lines.append('  label="Dependency Cycles Visualization";')
        dot_lines.append("  labelloc=t;")
        dot_lines.append("  fontsize=14;")
        dot_lines.append('  bgcolor="white";')
        dot_lines.append("  rankdir=LR;")
        dot_lines.append('  node [fontname="Arial", fontsize=10, style=filled];')
        dot_lines.append('  edge [fontname="Arial", fontsize=8];')

        for idx, cycle in enumerate(cycles):
            cycle_node_set = set(cycle.get("nodes", []))

            dot_lines.append(f"  subgraph cluster_cycle{idx} {{")
            dot_lines.append(f'    label="Cycle {idx + 1} (size: {len(cycle_node_set)})";')
            dot_lines.append("    style=filled;")
            dot_lines.append('    fillcolor="#FFE0E0";')
            dot_lines.append('    color="#D32F2F";')

            for node in filtered_graph["nodes"]:
                if node["id"] not in cycle_node_set:
                    continue

                node_id = node["id"]
                safe_id = self._sanitize_id(node_id)
                label = self._generate_node_label(node_id, node.get("file", node_id))

                attrs = []
                attrs.append(f'label="{label}"')
                attrs.append('fillcolor="#FF5252"')
                attrs.append('fontcolor="white"')
                attrs.append("shape=box")
                attrs.append("penwidth=2")

                node_line = f"    {safe_id} [{', '.join(attrs)}];"
                dot_lines.append(node_line)

            dot_lines.append("  }")

        for edge in filtered_graph["edges"]:
            source = edge["source"]
            target = edge["target"]

            safe_source = self._sanitize_id(source)
            safe_target = self._sanitize_id(target)

            attrs = []
            attrs.append('color="#D32F2F"')
            attrs.append("penwidth=2")
            attrs.append("arrowhead=normal")

            edge_line = f"  {safe_source} -> {safe_target} [{', '.join(attrs)}];"
            dot_lines.append(edge_line)

        dot_lines.append("}")

        return "\n".join(dot_lines)

    def generate_hotspots_only_view(
        self,
        graph: dict[str, Any],
        hotspots: list[dict[str, Any]],
        options: dict[str, Any] | None = None,
        top_n: int = 10,
    ) -> str:
        """Generate DOT format showing only hotspot nodes and their connections."""
        options = options or {}

        top_hotspots = hotspots[:top_n]
        hotspot_ids = {h["id"] for h in top_hotspots}

        if not hotspot_ids:
            return 'digraph G {\n  label="No hotspots detected";\n}'

        connected_nodes = set(hotspot_ids)
        for edge in graph.get("edges", []):
            if edge["source"] in hotspot_ids:
                connected_nodes.add(edge["target"])
            if edge["target"] in hotspot_ids:
                connected_nodes.add(edge["source"])

        filtered_graph = {
            "nodes": [n for n in graph.get("nodes", []) if n["id"] in connected_nodes],
            "edges": [
                e
                for e in graph.get("edges", [])
                if e["source"] in connected_nodes and e["target"] in connected_nodes
            ],
        }

        self._process_analysis(filtered_graph, {})

        dot_lines = ["digraph G {"]

        dot_lines.append(f'  label="Top {top_n} Hotspots Visualization";')
        dot_lines.append("  labelloc=t;")
        dot_lines.append("  fontsize=14;")
        dot_lines.append('  bgcolor="white";')
        dot_lines.append("  rankdir=LR;")
        dot_lines.append('  node [fontname="Arial", fontsize=10, style=filled];')
        dot_lines.append('  edge [fontname="Arial", fontsize=8];')

        hotspot_map = {h["id"]: h for h in top_hotspots}

        for node in filtered_graph["nodes"]:
            node_id = node["id"]
            safe_id = self._sanitize_id(node_id)
            label = self._generate_node_label(node_id, node.get("file", node_id))

            if node_id in hotspot_ids:
                hotspot = hotspot_map[node_id]
                in_degree = hotspot.get("in_degree", 0)
                out_degree = hotspot.get("out_degree", 0)

                total = in_degree + out_degree
                if total > 50:
                    size = 2.5
                elif total > 30:
                    size = 2.0
                elif total > 20:
                    size = 1.5
                else:
                    size = 1.2

                rank = list(hotspot_ids).index(node_id)
                if rank == 0:
                    color = "#D32F2F"
                elif rank < 3:
                    color = "#F44336"
                elif rank < 5:
                    color = "#FF5722"
                else:
                    color = "#FF9800"

                attrs = []
                attrs.append(f'label="{label}\\n[in:{in_degree} out:{out_degree}]"')
                attrs.append(f'fillcolor="{color}"')
                attrs.append('fontcolor="white"')
                attrs.append("shape=box")
                attrs.append(f"width={size}")
                attrs.append(f"height={size * 0.7}")
                attrs.append("penwidth=3")

                tooltip = f"Hotspot #{rank + 1}: in={in_degree}, out={out_degree}"
                attrs.append(f'tooltip="{tooltip}"')
            else:
                attrs = []
                attrs.append(f'label="{label}"')
                attrs.append('fillcolor="#E0E0E0"')
                attrs.append('fontcolor="black"')
                attrs.append("shape=box")
                attrs.append("width=0.8")
                attrs.append("height=0.6")
                attrs.append("penwidth=1")

            node_line = f"  {safe_id} [{', '.join(attrs)}];"
            dot_lines.append(node_line)

        for edge in filtered_graph["edges"]:
            source = edge["source"]
            target = edge["target"]

            safe_source = self._sanitize_id(source)
            safe_target = self._sanitize_id(target)

            if source in hotspot_ids or target in hotspot_ids:
                attrs = ['color="#666666"', "penwidth=1.5"]
            else:
                attrs = ['color="#CCCCCC"', "penwidth=0.5"]

            attrs.append("arrowhead=normal")

            edge_line = f"  {safe_source} -> {safe_target} [{', '.join(attrs)}];"
            dot_lines.append(edge_line)

        dot_lines.append("}")

        return "\n".join(dot_lines)
