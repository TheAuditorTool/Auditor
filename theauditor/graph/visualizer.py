"""Graph visualizer module - rich Graphviz visualization with visual intelligence.

This module transforms raw graph data and analysis results into actionable
visualizations using Graphviz DOT format with intelligent visual encoding.

Visual encoding strategy:
- Node color: Programming language
- Node size: Importance/connectivity (in-degree)
- Edge color: Red for cycles, gray for normal
- Edge style: Import type (solid/dashed/dotted)
- Node shape: Type (box=module, ellipse=function)
"""
from __future__ import annotations


from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set, Optional


class GraphVisualizer:
    """Transform graph analysis into actionable visualizations."""
    
    # Language colors - high contrast, colorblind-friendly palette
    LANGUAGE_COLORS = {
        'python': '#3776AB',      # Python blue
        'javascript': '#F7DF1E',   # JS yellow  
        'typescript': '#3178C6',   # TS blue
        'java': '#007396',         # Java blue-green
        'go': '#00ADD8',           # Go cyan
        'rust': '#CE4E21',         # Rust orange
        'c': '#A8B9CC',           # C gray-blue
        'c++': '#00599C',         # C++ dark blue
        'c#': '#239120',          # C# green
        'ruby': '#CC342D',        # Ruby red
        'php': '#777BB4',         # PHP purple
        'default': '#808080',     # Gray for unknown
    }
    
    # Risk level colors for severity encoding
    RISK_COLORS = {
        'critical': '#D32F2F',    # Deep red
        'high': '#F57C00',        # Orange
        'medium': '#FBC02D',      # Yellow
        'low': '#689F38',         # Green
        'info': '#1976D2',        # Blue
    }
    
    def __init__(self):
        """Initialize the visualizer."""
        self.cycle_edges = set()  # Track edges that are part of cycles
        self.node_degrees = {}    # Track in/out degrees for sizing
        
    def generate_dot(
        self,
        graph: dict[str, Any],
        analysis: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> str:
        """
        Generate DOT format with visual intelligence encoding.
        
        Args:
            graph: Graph dict with 'nodes' and 'edges'
            analysis: Optional analysis results with cycles, hotspots, etc.
            options: Optional visualization options
            
        Returns:
            DOT format string ready for Graphviz
        """
        options = options or {}
        analysis = analysis or {}
        
        # Pre-process analysis data
        self._process_analysis(graph, analysis)
        
        # Start DOT file
        dot_lines = ['digraph G {']
        
        # Global graph attributes
        dot_lines.extend(self._generate_graph_attrs(options))
        
        # Generate nodes with visual encoding
        dot_lines.extend(self._generate_nodes(graph, analysis, options))
        
        # Generate edges with visual encoding
        dot_lines.extend(self._generate_edges(graph, analysis, options))
        
        # Close graph
        dot_lines.append('}')
        
        return '\n'.join(dot_lines)
    
    def _process_analysis(
        self,
        graph: dict[str, Any],
        analysis: dict[str, Any]
    ) -> None:
        """Pre-process analysis data for quick lookup."""
        # Calculate node degrees
        self.node_degrees.clear()
        for edge in graph.get('edges', []):
            source = edge.get('source', '')
            target = edge.get('target', '')
            
            # Track out-degree
            if source not in self.node_degrees:
                self.node_degrees[source] = {'in': 0, 'out': 0}
            self.node_degrees[source]['out'] += 1
            
            # Track in-degree
            if target not in self.node_degrees:
                self.node_degrees[target] = {'in': 0, 'out': 0}
            self.node_degrees[target]['in'] += 1
        
        # Identify edges that are part of cycles
        self.cycle_edges.clear()
        cycles = analysis.get('cycles', [])
        for cycle in cycles:
            cycle_nodes = cycle.get('nodes', [])
            # Mark edges between consecutive nodes in cycle
            for i in range(len(cycle_nodes)):
                source = cycle_nodes[i]
                target = cycle_nodes[(i + 1) % len(cycle_nodes)]
                self.cycle_edges.add((source, target))
    
    def _generate_graph_attrs(self, options: dict[str, Any]) -> list[str]:
        """Generate global graph attributes."""
        attrs = []
        attrs.append('  rankdir=LR;')  # Left to right layout
        attrs.append('  bgcolor="white";')
        attrs.append('  nodesep=0.5;')
        attrs.append('  ranksep=1.0;')
        attrs.append('  fontname="Arial";')
        
        # Default node attributes
        attrs.append('  node [fontname="Arial", fontsize=10, style=filled];')
        
        # Default edge attributes
        attrs.append('  edge [fontname="Arial", fontsize=8];')
        
        # Add title if provided
        if options.get('title'):
            attrs.append(f'  label="{options["title"]}";')
            attrs.append('  labelloc=t;')
            attrs.append('  fontsize=14;')
        
        return attrs
    
    def _generate_nodes(
        self,
        graph: dict[str, Any],
        analysis: dict[str, Any],
        options: dict[str, Any]
    ) -> list[str]:
        """Generate nodes with visual encoding."""
        node_lines = []
        nodes = graph.get('nodes', [])
        
        # Get hotspots for special highlighting
        hotspots = analysis.get('hotspots', [])
        hotspot_ids = {h['id']: h for h in hotspots[:10]}  # Top 10 hotspots
        
        # Limit nodes if requested
        max_nodes = options.get('max_nodes', 500)
        if len(nodes) > max_nodes:
            # Sort by importance (in-degree + out-degree)
            nodes = sorted(
                nodes,
                key=lambda n: self.node_degrees.get(
                    n['id'], {'in': 0, 'out': 0}
                )['in'] + self.node_degrees.get(
                    n['id'], {'in': 0, 'out': 0}
                )['out'],
                reverse=True
            )[:max_nodes]
        
        for node in nodes:
            node_id = node.get('id', '')
            node_file = node.get('file', node_id)
            node_lang = node.get('lang', 'default')
            node_type = node.get('type', 'module')
            
            # Sanitize node ID for DOT format
            safe_id = self._sanitize_id(node_id)
            
            # Determine node color based on language
            color = self.LANGUAGE_COLORS.get(node_lang, self.LANGUAGE_COLORS['default'])
            
            # Determine node size based on in-degree (hotspot detection)
            degrees = self.node_degrees.get(node_id, {'in': 0, 'out': 0})
            in_degree = degrees['in']
            
            # Scale size based on in-degree (min 0.5, max 2.0)
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
            
            # Determine shape based on type
            if node_type == 'function':
                shape = 'ellipse'
            elif node_type == 'class':
                shape = 'diamond'
            else:  # module
                shape = 'box'
            
            # Generate label (shortened for readability)
            label = self._generate_node_label(node_id, node_file)
            
            # Build node attributes
            attrs = []
            attrs.append(f'label="{label}"')
            attrs.append(f'fillcolor="{color}"')
            attrs.append(f'shape={shape}')
            attrs.append(f'width={size}')
            attrs.append(f'height={size * 0.7}')
            
            # Special styling for hotspots
            if node_id in hotspot_ids:
                attrs.append('penwidth=3')
                attrs.append('fontsize=12')
                attrs.append('fontcolor="black"')
                # Add tooltip with hotspot info
                hotspot = hotspot_ids[node_id]
                tooltip = f"Hotspot: in={hotspot.get('in_degree', 0)}, out={hotspot.get('out_degree', 0)}"
                attrs.append(f'tooltip="{tooltip}"')
            else:
                attrs.append('penwidth=1')
                attrs.append('fontcolor="white"')
            
            # Create node line
            node_line = f'  {safe_id} [{", ".join(attrs)}];'
            node_lines.append(node_line)
        
        return node_lines
    
    def _generate_edges(
        self,
        graph: dict[str, Any],
        analysis: dict[str, Any],
        options: dict[str, Any]
    ) -> list[str]:
        """Generate edges with visual encoding."""
        edge_lines = []
        edges = graph.get('edges', [])
        
        # Get node IDs for filtering
        node_ids = {n['id'] for n in graph.get('nodes', [])}
        max_nodes = options.get('max_nodes', 500)
        if len(node_ids) > max_nodes:
            # Keep only edges between displayed nodes
            important_nodes = set(list(node_ids)[:max_nodes])
            edges = [
                e for e in edges
                if e.get('source') in important_nodes and e.get('target') in important_nodes
            ]
        
        for edge in edges:
            source = edge.get('source', '')
            target = edge.get('target', '')
            edge_type = edge.get('type', 'import')
            
            # Skip self-loops unless in options
            if source == target and not options.get('show_self_loops'):
                continue
            
            # Sanitize IDs
            safe_source = self._sanitize_id(source)
            safe_target = self._sanitize_id(target)
            
            # Build edge attributes
            attrs = []
            
            # Color red if part of a cycle
            if (source, target) in self.cycle_edges:
                attrs.append('color="#D32F2F"')  # Red for cycles
                attrs.append('penwidth=2')
                attrs.append('fontcolor="#D32F2F"')
                attrs.append('label="cycle"')
            else:
                attrs.append('color="#666666"')  # Gray for normal
                attrs.append('penwidth=1')
            
            # Style based on edge type
            if edge_type == 'call':
                attrs.append('style=dashed')
            elif edge_type == 'extends' or edge_type == 'implements':
                attrs.append('style=bold')
            else:  # import
                attrs.append('style=solid')
            
            # Arrowhead style
            if edge_type == 'extends':
                attrs.append('arrowhead=empty')  # Inheritance
            elif edge_type == 'implements':
                attrs.append('arrowhead=odiamond')  # Interface
            else:
                attrs.append('arrowhead=normal')
            
            # Create edge line
            if attrs:
                edge_line = f'  {safe_source} -> {safe_target} [{", ".join(attrs)}];'
            else:
                edge_line = f'  {safe_source} -> {safe_target};'
            
            edge_lines.append(edge_line)
        
        return edge_lines
    
    def _sanitize_id(self, node_id: str) -> str:
        """Sanitize node ID for DOT format."""
        # Replace problematic characters
        safe_id = node_id.replace('.', '_')
        safe_id = safe_id.replace('/', '_')
        safe_id = safe_id.replace('\\', '_')
        safe_id = safe_id.replace('-', '_')
        safe_id = safe_id.replace(':', '_')
        safe_id = safe_id.replace(' ', '_')
        safe_id = safe_id.replace('(', '_')
        safe_id = safe_id.replace(')', '_')
        safe_id = safe_id.replace('[', '_')
        safe_id = safe_id.replace(']', '_')
        
        # Ensure it starts with a letter or underscore
        if safe_id and not safe_id[0].isalpha() and safe_id[0] != '_':
            safe_id = '_' + safe_id
        
        # Quote if necessary
        if safe_id and not safe_id.replace('_', '').isalnum():
            safe_id = f'"{safe_id}"'
        
        return safe_id
    
    def _generate_node_label(self, node_id: str, node_file: str) -> str:
        """Generate readable label for a node."""
        # Use filename for modules, full ID for functions
        if '::' in node_id:  # Function node
            # Show module::function
            parts = node_id.split('::')
            if len(parts) >= 2:
                module = Path(parts[0]).stem  # Just filename without extension
                function = parts[1]
                return f"{module}::{function}"
            return node_id
        else:  # Module node
            # Show just the filename without path
            path = Path(node_file)
            if path.parts:
                # Show last 2 parts of path for context
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
        """
        Generate DOT format with architectural layers as subgraphs.
        
        Args:
            graph: Graph dict with 'nodes' and 'edges'
            layers: Dict mapping layer number to list of node IDs
            analysis: Optional analysis results
            options: Optional visualization options
            
        Returns:
            DOT format string with layer subgraphs
        """
        options = options or {}
        analysis = analysis or {}
        
        # Pre-process analysis data
        self._process_analysis(graph, analysis)
        
        # Build node lookup for efficiency  
        node_map = {n['id']: n for n in graph.get('nodes', []) if n.get('id') is not None}
        
        # Start DOT file
        dot_lines = ['digraph G {']
        
        # Global graph attributes
        dot_lines.extend(self._generate_graph_attrs(options))
        dot_lines.append('  rankdir=TB;')  # Top-to-bottom for layers
        
        # Generate layer subgraphs
        # Filter out None keys and ensure all keys are comparable
        valid_layer_nums = [k for k in layers.keys() if k is not None]
        for layer_num in sorted(valid_layer_nums):
            layer_nodes = layers[layer_num]
            if not layer_nodes:
                continue
                
            # Create subgraph for this layer
            dot_lines.append(f'  subgraph cluster_layer{layer_num} {{')
            dot_lines.append(f'    label="Layer {layer_num}";')
            dot_lines.append(f'    style=filled;')
            dot_lines.append(f'    fillcolor="#F0F0F0";')
            dot_lines.append(f'    color="#CCCCCC";')
            dot_lines.append(f'    fontsize=12;')
            dot_lines.append(f'    rank=same;')  # Keep nodes at same level
            
            # Add nodes for this layer
            for node_id in layer_nodes:
                if node_id not in node_map:
                    continue
                    
                node = node_map[node_id]
                node_lang = node.get('lang', 'default')
                node_type = node.get('type', 'module')
                
                # Sanitize node ID
                safe_id = self._sanitize_id(node_id)
                
                # Determine node color based on language
                color = self.LANGUAGE_COLORS.get(node_lang, self.LANGUAGE_COLORS['default'])
                
                # Determine node size based on in-degree
                degrees = self.node_degrees.get(node_id, {'in': 0, 'out': 0})
                in_degree = degrees['in']
                
                # Scale size based on in-degree
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
                
                # Determine shape based on type
                if node_type == 'function':
                    shape = 'ellipse'
                elif node_type == 'class':
                    shape = 'diamond'
                else:  # module
                    shape = 'box'
                
                # Generate label
                label = self._generate_node_label(node_id, node.get('file', node_id))
                
                # Check if node has churn data for border thickness
                churn = node.get('churn', 0)
                if churn is None:
                    churn = 0
                if churn > 100:
                    penwidth = 4  # Very high churn
                elif churn > 50:
                    penwidth = 3  # High churn
                elif churn > 20:
                    penwidth = 2  # Medium churn
                else:
                    penwidth = 1  # Low/no churn
                
                # Build node attributes
                attrs = []
                attrs.append(f'label="{label}"')
                attrs.append(f'fillcolor="{color}"')
                attrs.append(f'shape={shape}')
                attrs.append(f'width={size}')
                attrs.append(f'height={size * 0.7}')
                attrs.append(f'penwidth={penwidth}')
                attrs.append('fontcolor="white"')
                attrs.append('style=filled')
                
                # Add tooltip with layer info
                tooltip = f"Layer {layer_num}: {node_id}"
                if churn > 0:
                    tooltip += f" (churn: {churn})"
                attrs.append(f'tooltip="{tooltip}"')
                
                # Create node line
                node_line = f'    {safe_id} [{", ".join(attrs)}];'
                dot_lines.append(node_line)
            
            dot_lines.append('  }')  # Close subgraph
        
        # Generate edges (outside of subgraphs)
        dot_lines.extend(self._generate_edges(graph, analysis, options))
        
        # Close graph
        dot_lines.append('}')
        
        return '\n'.join(dot_lines)
    
    def generate_impact_visualization(
        self,
        graph: dict[str, Any],
        impact: dict[str, Any],
        options: dict[str, Any] | None = None,
    ) -> str:
        """
        Generate DOT highlighting impact analysis results.
        
        Args:
            graph: Graph dict with 'nodes' and 'edges'
            impact: Impact analysis with targets, upstream, downstream
            options: Optional visualization options
            
        Returns:
            DOT format string with impact highlighting
        """
        options = options or {}
        
        # Extract impact sets
        targets = set(impact.get('targets', []))
        upstream = set(impact.get('upstream', []))
        downstream = set(impact.get('downstream', []))
        
        # Pre-process analysis data
        self._process_analysis(graph, {})
        
        # Start DOT file
        dot_lines = ['digraph G {']
        
        # Global graph attributes
        dot_lines.extend(self._generate_graph_attrs(options))
        
        # Add legend for impact visualization
        dot_lines.append('  subgraph cluster_legend {')
        dot_lines.append('    label="Impact Analysis Legend";')
        dot_lines.append('    style=filled;')
        dot_lines.append('    fillcolor=white;')
        dot_lines.append('    node [shape=box, style=filled];')
        dot_lines.append('    legend_target [label="Target", fillcolor="#FF0000"];')
        dot_lines.append('    legend_upstream [label="Upstream", fillcolor="#FF9800"];')
        dot_lines.append('    legend_downstream [label="Downstream", fillcolor="#2196F3"];')
        dot_lines.append('    legend_both [label="Both", fillcolor="#9C27B0"];')
        dot_lines.append('    legend_unaffected [label="Unaffected", fillcolor="#808080"];')
        dot_lines.append('  }')
        
        # Generate nodes with impact highlighting
        node_lines = []
        for node in graph.get('nodes', []):
            node_id = node.get('id', '')
            node_file = node.get('file', node_id)
            node_lang = node.get('lang', 'default')
            node_type = node.get('type', 'module')
            
            # Sanitize node ID
            safe_id = self._sanitize_id(node_id)
            
            # Determine impact color
            if node_id in targets:
                color = '#FF0000'  # Red for target
                fontcolor = 'white'
                penwidth = 3
            elif node_id in upstream and node_id in downstream:
                color = '#9C27B0'  # Purple for both upstream and downstream
                fontcolor = 'white'
                penwidth = 2
            elif node_id in upstream:
                color = '#FF9800'  # Orange for upstream
                fontcolor = 'white'
                penwidth = 2
            elif node_id in downstream:
                color = '#2196F3'  # Blue for downstream
                fontcolor = 'white'
                penwidth = 2
            else:
                color = '#E0E0E0'  # Light gray for unaffected
                fontcolor = 'black'
                penwidth = 1
            
            # Determine node size based on impact radius
            degrees = self.node_degrees.get(node_id, {'in': 0, 'out': 0})
            if node_id in targets:
                size = 1.5  # Targets are emphasized
            elif node_id in upstream or node_id in downstream:
                size = 1.2  # Affected nodes are slightly larger
            else:
                size = 0.8  # Unaffected nodes are smaller
            
            # Determine shape based on type
            if node_type == 'function':
                shape = 'ellipse'
            elif node_type == 'class':
                shape = 'diamond'
            else:  # module
                shape = 'box'
            
            # Generate label
            label = self._generate_node_label(node_id, node_file)
            
            # Build node attributes
            attrs = []
            attrs.append(f'label="{label}"')
            attrs.append(f'fillcolor="{color}"')
            attrs.append(f'shape={shape}')
            attrs.append(f'width={size}')
            attrs.append(f'height={size * 0.7}')
            attrs.append(f'penwidth={penwidth}')
            attrs.append(f'fontcolor="{fontcolor}"')
            attrs.append('style=filled')
            
            # Add tooltip with impact info
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
            
            # Create node line
            node_line = f'  {safe_id} [{", ".join(attrs)}];'
            node_lines.append(node_line)
        
        dot_lines.extend(node_lines)
        
        # Generate edges with impact highlighting
        edge_lines = []
        for edge in graph.get('edges', []):
            source = edge.get('source', '')
            target = edge.get('target', '')
            edge_type = edge.get('type', 'import')
            
            # Skip self-loops unless in options
            if source == target and not options.get('show_self_loops'):
                continue
            
            # Sanitize IDs
            safe_source = self._sanitize_id(source)
            safe_target = self._sanitize_id(target)
            
            # Build edge attributes
            attrs = []
            
            # Color edges based on impact path
            if source in targets and target in downstream:
                attrs.append('color="#FF0000"')  # Red for direct impact
                attrs.append('penwidth=3')
            elif source in upstream and target in targets:
                attrs.append('color="#FF9800"')  # Orange for upstream to target
                attrs.append('penwidth=2')
            elif (source in targets or source in upstream or source in downstream) and \
                 (target in targets or target in upstream or target in downstream):
                attrs.append('color="#666666"')  # Gray for affected connections
                attrs.append('penwidth=1.5')
            else:
                attrs.append('color="#E0E0E0"')  # Light gray for unaffected
                attrs.append('penwidth=0.5')
                attrs.append('style=dashed')
            
            # Arrowhead style
            attrs.append('arrowhead=normal')
            
            # Create edge line
            if attrs:
                edge_line = f'  {safe_source} -> {safe_target} [{", ".join(attrs)}];'
            else:
                edge_line = f'  {safe_source} -> {safe_target};'
            
            edge_lines.append(edge_line)
        
        dot_lines.extend(edge_lines)
        
        # Close graph
        dot_lines.append('}')
        
        return '\n'.join(dot_lines)
    
    def generate_cycles_only_view(
        self,
        graph: dict[str, Any],
        cycles: list[dict[str, Any]],
        options: dict[str, Any] | None = None,
    ) -> str:
        """
        Generate DOT format showing only nodes and edges involved in cycles.
        
        Args:
            graph: Graph dict with 'nodes' and 'edges'
            cycles: List of cycle dicts with 'nodes' lists
            options: Optional visualization options
            
        Returns:
            DOT format string with only cycle-related elements
        """
        options = options or {}
        
        # Collect all nodes involved in cycles
        cycle_nodes = set()
        cycle_edges = set()
        
        for cycle in cycles:
            nodes = cycle.get('nodes', [])
            cycle_nodes.update(nodes)
            
            # Mark edges between consecutive nodes in cycle
            for i in range(len(nodes)):
                source = nodes[i]
                target = nodes[(i + 1) % len(nodes)]
                cycle_edges.add((source, target))
        
        if not cycle_nodes:
            # No cycles found
            return 'digraph G {\n  label="No cycles detected";\n}'
        
        # Filter graph to only cycle-related elements
        filtered_graph = {
            'nodes': [n for n in graph.get('nodes', []) if n['id'] in cycle_nodes],
            'edges': [e for e in graph.get('edges', []) 
                     if (e['source'], e['target']) in cycle_edges]
        }
        
        # Pre-process for visualization
        self.cycle_edges = cycle_edges  # Mark for red highlighting
        self._process_analysis(filtered_graph, {})
        
        # Start DOT file
        dot_lines = ['digraph G {']
        
        # Global graph attributes
        dot_lines.append('  label="Dependency Cycles Visualization";')
        dot_lines.append('  labelloc=t;')
        dot_lines.append('  fontsize=14;')
        dot_lines.append('  bgcolor="white";')
        dot_lines.append('  rankdir=LR;')
        dot_lines.append('  node [fontname="Arial", fontsize=10, style=filled];')
        dot_lines.append('  edge [fontname="Arial", fontsize=8];')
        
        # Group nodes by cycle for better visualization
        for idx, cycle in enumerate(cycles):
            cycle_node_set = set(cycle.get('nodes', []))
            
            dot_lines.append(f'  subgraph cluster_cycle{idx} {{')
            dot_lines.append(f'    label="Cycle {idx + 1} (size: {len(cycle_node_set)})";')
            dot_lines.append('    style=filled;')
            dot_lines.append('    fillcolor="#FFE0E0";')  # Light red background
            dot_lines.append('    color="#D32F2F";')  # Red border
            
            # Add nodes for this cycle
            for node in filtered_graph['nodes']:
                if node['id'] not in cycle_node_set:
                    continue
                    
                node_id = node['id']
                safe_id = self._sanitize_id(node_id)
                label = self._generate_node_label(node_id, node.get('file', node_id))
                
                # Node styling
                attrs = []
                attrs.append(f'label="{label}"')
                attrs.append('fillcolor="#FF5252"')  # Red for cycle nodes
                attrs.append('fontcolor="white"')
                attrs.append('shape=box')
                attrs.append('penwidth=2')
                
                node_line = f'    {safe_id} [{", ".join(attrs)}];'
                dot_lines.append(node_line)
            
            dot_lines.append('  }')
        
        # Add edges
        for edge in filtered_graph['edges']:
            source = edge['source']
            target = edge['target']
            
            safe_source = self._sanitize_id(source)
            safe_target = self._sanitize_id(target)
            
            attrs = []
            attrs.append('color="#D32F2F"')  # Red for cycle edges
            attrs.append('penwidth=2')
            attrs.append('arrowhead=normal')
            
            edge_line = f'  {safe_source} -> {safe_target} [{", ".join(attrs)}];'
            dot_lines.append(edge_line)
        
        dot_lines.append('}')
        
        return '\n'.join(dot_lines)
    
    def generate_hotspots_only_view(
        self,
        graph: dict[str, Any],
        hotspots: list[dict[str, Any]],
        options: dict[str, Any] | None = None,
        top_n: int = 10,
    ) -> str:
        """
        Generate DOT format showing only hotspot nodes and their connections.
        
        Args:
            graph: Graph dict with 'nodes' and 'edges'
            hotspots: List of hotspot dicts with 'id' and metrics
            options: Optional visualization options
            top_n: Number of top hotspots to show (default: 10)
            
        Returns:
            DOT format string with only hotspot-related elements
        """
        options = options or {}
        
        # Get top N hotspots
        top_hotspots = hotspots[:top_n]
        hotspot_ids = {h['id'] for h in top_hotspots}
        
        if not hotspot_ids:
            return 'digraph G {\n  label="No hotspots detected";\n}'
        
        # Collect nodes connected to hotspots (1 degree of separation)
        connected_nodes = set(hotspot_ids)
        for edge in graph.get('edges', []):
            if edge['source'] in hotspot_ids:
                connected_nodes.add(edge['target'])
            if edge['target'] in hotspot_ids:
                connected_nodes.add(edge['source'])
        
        # Filter graph
        filtered_graph = {
            'nodes': [n for n in graph.get('nodes', []) if n['id'] in connected_nodes],
            'edges': [e for e in graph.get('edges', []) 
                     if e['source'] in connected_nodes and e['target'] in connected_nodes]
        }
        
        # Pre-process
        self._process_analysis(filtered_graph, {})
        
        # Start DOT file
        dot_lines = ['digraph G {']
        
        # Global graph attributes
        dot_lines.append(f'  label="Top {top_n} Hotspots Visualization";')
        dot_lines.append('  labelloc=t;')
        dot_lines.append('  fontsize=14;')
        dot_lines.append('  bgcolor="white";')
        dot_lines.append('  rankdir=LR;')
        dot_lines.append('  node [fontname="Arial", fontsize=10, style=filled];')
        dot_lines.append('  edge [fontname="Arial", fontsize=8];')
        
        # Create hotspot lookup
        hotspot_map = {h['id']: h for h in top_hotspots}
        
        # Generate nodes
        for node in filtered_graph['nodes']:
            node_id = node['id']
            safe_id = self._sanitize_id(node_id)
            label = self._generate_node_label(node_id, node.get('file', node_id))
            
            # Determine styling based on whether it's a hotspot
            if node_id in hotspot_ids:
                hotspot = hotspot_map[node_id]
                in_degree = hotspot.get('in_degree', 0)
                out_degree = hotspot.get('out_degree', 0)
                
                # Size based on total connections
                total = in_degree + out_degree
                if total > 50:
                    size = 2.5
                elif total > 30:
                    size = 2.0
                elif total > 20:
                    size = 1.5
                else:
                    size = 1.2
                
                # Color intensity based on ranking
                rank = list(hotspot_ids).index(node_id)
                if rank == 0:
                    color = '#D32F2F'  # Darkest red for #1
                elif rank < 3:
                    color = '#F44336'  # Red for top 3
                elif rank < 5:
                    color = '#FF5722'  # Deep orange for top 5
                else:
                    color = '#FF9800'  # Orange for rest
                
                attrs = []
                attrs.append(f'label="{label}\\n[in:{in_degree} out:{out_degree}]"')
                attrs.append(f'fillcolor="{color}"')
                attrs.append('fontcolor="white"')
                attrs.append('shape=box')
                attrs.append(f'width={size}')
                attrs.append(f'height={size * 0.7}')
                attrs.append('penwidth=3')
                
                # Tooltip
                tooltip = f"Hotspot #{rank+1}: in={in_degree}, out={out_degree}"
                attrs.append(f'tooltip="{tooltip}"')
            else:
                # Connected node (not a hotspot)
                attrs = []
                attrs.append(f'label="{label}"')
                attrs.append('fillcolor="#E0E0E0"')
                attrs.append('fontcolor="black"')
                attrs.append('shape=box')
                attrs.append('width=0.8')
                attrs.append('height=0.6')
                attrs.append('penwidth=1')
            
            node_line = f'  {safe_id} [{", ".join(attrs)}];'
            dot_lines.append(node_line)
        
        # Generate edges
        for edge in filtered_graph['edges']:
            source = edge['source']
            target = edge['target']
            
            safe_source = self._sanitize_id(source)
            safe_target = self._sanitize_id(target)
            
            # Highlight edges connected to hotspots
            if source in hotspot_ids or target in hotspot_ids:
                attrs = ['color="#666666"', 'penwidth=1.5']
            else:
                attrs = ['color="#CCCCCC"', 'penwidth=0.5']
            
            attrs.append('arrowhead=normal')
            
            edge_line = f'  {safe_source} -> {safe_target} [{", ".join(attrs)}];'
            dot_lines.append(edge_line)
        
        dot_lines.append('}')
        
        return '\n'.join(dot_lines)