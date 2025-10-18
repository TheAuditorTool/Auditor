"""Control Flow Graph Builder - reads CFG data from database.

This module builds control flow graphs from data stored in the database
during the indexing phase. It provides analysis capabilities including:
- Cyclomatic complexity calculation
- Path analysis
- Dead code detection
- Loop detection
"""

import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple
from collections import defaultdict


class CFGBuilder:
    """Build and analyze control flow graphs from database."""
    
    def __init__(self, db_path: str):
        """Initialize CFG builder with database connection.
        
        Args:
            db_path: Path to the repo_index.db database
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
    
    def get_function_cfg(self, file_path: str, function_name: str) -> Dict[str, Any]:
        """Get control flow graph for a specific function.
        
        Args:
            file_path: Path to the source file
            function_name: Name of the function
            
        Returns:
            CFG dictionary with blocks, edges, and metadata
        """
        cursor = self.conn.cursor()
        
        # Get all blocks for this function
        cursor.execute("""
            SELECT * FROM cfg_blocks 
            WHERE file = ? AND function_name = ?
            ORDER BY start_line
        """, (file_path, function_name))
        
        blocks = []
        block_map = {}
        for row in cursor.fetchall():
            block = {
                'id': row['id'],
                'type': row['block_type'],
                'start_line': row['start_line'],
                'end_line': row['end_line'],
                'condition': row['condition_expr'],
                'statements': []
            }
            blocks.append(block)
            block_map[row['id']] = block
        
        # Get statements for each block
        for block in blocks:
            cursor.execute("""
                SELECT * FROM cfg_block_statements
                WHERE block_id = ?
                ORDER BY line
            """, (block['id'],))
            
            for row in cursor.fetchall():
                block['statements'].append({
                    'type': row['statement_type'],
                    'line': row['line'],
                    'text': row['statement_text']
                })
        
        # Get edges
        cursor.execute("""
            SELECT * FROM cfg_edges
            WHERE file = ? AND function_name = ?
        """, (file_path, function_name))
        
        edges = []
        for row in cursor.fetchall():
            edges.append({
                'source': row['source_block_id'],
                'target': row['target_block_id'],
                'type': row['edge_type']
            })
        
        return {
            'function_name': function_name,
            'file': file_path,
            'blocks': blocks,
            'edges': edges,
            'metrics': self._calculate_metrics(blocks, edges)
        }
    
    def get_all_functions(self, file_path: Optional[str] = None) -> List[Dict[str, str]]:
        """Get list of all functions with CFG data.
        
        Args:
            file_path: Optional filter by file path
            
        Returns:
            List of function metadata dictionaries
        """
        cursor = self.conn.cursor()
        
        if file_path:
            cursor.execute("""
                SELECT DISTINCT file, function_name, COUNT(*) as block_count
                FROM cfg_blocks
                WHERE file = ?
                GROUP BY file, function_name
            """, (file_path,))
        else:
            cursor.execute("""
                SELECT DISTINCT file, function_name, COUNT(*) as block_count
                FROM cfg_blocks
                GROUP BY file, function_name
            """)
        
        functions = []
        for row in cursor.fetchall():
            functions.append({
                'file': row['file'],
                'function_name': row['function_name'],
                'block_count': row['block_count']
            })
        
        return functions
    
    def analyze_complexity(self, file_path: Optional[str] = None, 
                          threshold: int = 10) -> List[Dict[str, Any]]:
        """Find functions with high cyclomatic complexity.
        
        Args:
            file_path: Optional filter by file path
            threshold: Complexity threshold (default 10)
            
        Returns:
            List of complex functions with metrics
        """
        functions = self.get_all_functions(file_path)
        complex_functions = []
        
        for func in functions:
            cfg = self.get_function_cfg(func['file'], func['function_name'])
            complexity = cfg['metrics']['cyclomatic_complexity']
            
            if complexity >= threshold:
                # Get the start and end lines from the CFG blocks
                start_line = min(b['start_line'] for b in cfg['blocks']) if cfg['blocks'] else 0
                end_line = max(b['end_line'] for b in cfg['blocks']) if cfg['blocks'] else 0
                
                complex_functions.append({
                    'file': func['file'],
                    'function': func['function_name'],
                    'complexity': complexity,
                    'start_line': start_line,
                    'end_line': end_line,
                    'block_count': len(cfg['blocks']),
                    'edge_count': len(cfg['edges']),
                    'has_loops': cfg['metrics']['has_loops'],
                    'max_nesting': cfg['metrics']['max_nesting_depth']
                })
        
        # Sort by complexity descending
        complex_functions.sort(key=lambda x: x['complexity'], reverse=True)
        return complex_functions
    
    def find_dead_code(self, file_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """Find unreachable code blocks.
        
        Args:
            file_path: Optional filter by file path
            
        Returns:
            List of unreachable blocks
        """
        functions = self.get_all_functions(file_path)
        dead_blocks = []
        
        for func in functions:
            cfg = self.get_function_cfg(func['file'], func['function_name'])
            unreachable = self._find_unreachable_blocks(cfg['blocks'], cfg['edges'])
            
            for block_id in unreachable:
                block = next((b for b in cfg['blocks'] if b['id'] == block_id), None)
                if block and block['type'] not in ['entry', 'exit']:
                    dead_blocks.append({
                        'file': func['file'],
                        'function': func['function_name'],
                        'block_id': block_id,
                        'block_type': block['type'],
                        'start_line': block['start_line'],
                        'end_line': block['end_line']
                    })
        
        return dead_blocks
    
    def _calculate_metrics(self, blocks: List[Dict], edges: List[Dict]) -> Dict[str, Any]:
        """Calculate CFG metrics.
        
        Args:
            blocks: List of CFG blocks
            edges: List of CFG edges
            
        Returns:
            Dictionary of metrics
        """
        # Cyclomatic complexity = E - N + 2P
        # Where E = edges, N = nodes, P = connected components (usually 1)
        cyclomatic = len(edges) - len(blocks) + 2
        
        # Check for loops (back edges)
        has_loops = any(e['type'] == 'back_edge' for e in edges)
        
        # Calculate maximum nesting depth
        max_nesting = self._calculate_max_nesting(blocks, edges)
        
        # Count decision points
        decision_points = sum(1 for b in blocks if b['type'] in ['condition', 'loop_condition'])
        
        return {
            'cyclomatic_complexity': cyclomatic,
            'has_loops': has_loops,
            'max_nesting_depth': max_nesting,
            'decision_points': decision_points,
            'block_count': len(blocks),
            'edge_count': len(edges)
        }
    
    def _find_unreachable_blocks(self, blocks: List[Dict], edges: List[Dict]) -> Set[int]:
        """Find blocks that cannot be reached from entry.
        
        Args:
            blocks: List of CFG blocks
            edges: List of CFG edges
            
        Returns:
            Set of unreachable block IDs
        """
        # Build adjacency list
        graph = defaultdict(list)
        for edge in edges:
            graph[edge['source']].append(edge['target'])
        
        # Find entry block
        entry_blocks = [b['id'] for b in blocks if b['type'] == 'entry']
        if not entry_blocks:
            return set()
        
        # DFS from entry to find reachable blocks
        reachable = set()
        stack = entry_blocks.copy()
        
        while stack:
            current = stack.pop()
            if current not in reachable:
                reachable.add(current)
                stack.extend(graph[current])
        
        # Find unreachable blocks
        all_blocks = {b['id'] for b in blocks}
        unreachable = all_blocks - reachable
        
        return unreachable
    
    def _calculate_max_nesting(self, blocks: List[Dict], edges: List[Dict]) -> int:
        """Calculate maximum nesting depth in the CFG.
        
        Args:
            blocks: List of CFG blocks
            edges: List of CFG edges
            
        Returns:
            Maximum nesting depth
        """
        # Build adjacency list
        graph = defaultdict(list)
        for edge in edges:
            graph[edge['source']].append(edge['target'])
        
        # Track nesting depth for condition/loop blocks
        max_depth = 0
        entry_blocks = [b['id'] for b in blocks if b['type'] == 'entry']
        
        if not entry_blocks:
            return 0
        
        # BFS with depth tracking
        queue = [(entry_blocks[0], 0)]
        visited = set()
        
        while queue:
            block_id, depth = queue.pop(0)
            
            if block_id in visited:
                continue
            visited.add(block_id)
            
            # Find the block
            block = next((b for b in blocks if b['id'] == block_id), None)
            if not block:
                continue
            
            # Increase depth for nesting structures
            new_depth = depth
            if block['type'] in ['condition', 'loop_condition', 'try']:
                new_depth = depth + 1
                max_depth = max(max_depth, new_depth)
            
            # Add neighbors to queue
            for neighbor in graph[block_id]:
                if neighbor not in visited:
                    queue.append((neighbor, new_depth))
        
        return max_depth
    
    def get_execution_paths(self, file_path: str, function_name: str, 
                           max_paths: int = 100) -> List[List[int]]:
        """Get all execution paths through a function.
        
        Args:
            file_path: Path to the source file
            function_name: Name of the function
            max_paths: Maximum number of paths to return
            
        Returns:
            List of paths (each path is a list of block IDs)
        """
        cfg = self.get_function_cfg(file_path, function_name)
        
        # Build adjacency list
        graph = defaultdict(list)
        for edge in cfg['edges']:
            # Skip back edges to avoid infinite loops
            if edge['type'] != 'back_edge':
                graph[edge['source']].append(edge['target'])
        
        # Find entry and exit blocks
        entry_blocks = [b['id'] for b in cfg['blocks'] if b['type'] == 'entry']
        exit_blocks = [b['id'] for b in cfg['blocks'] if b['type'] in ['exit', 'return']]
        
        if not entry_blocks or not exit_blocks:
            return []
        
        # DFS to find all paths
        paths = []
        stack = [(entry_blocks[0], [entry_blocks[0]])]
        
        while stack and len(paths) < max_paths:
            current, path = stack.pop()
            
            if current in exit_blocks:
                paths.append(path)
                continue
            
            # Add all neighbors
            for neighbor in graph[current]:
                # Avoid cycles in path
                if neighbor not in path:
                    stack.append((neighbor, path + [neighbor]))
        
        return paths
    
    def export_dot(self, file_path: str, function_name: str) -> str:
        """Export CFG as Graphviz DOT format.
        
        Args:
            file_path: Path to the source file
            function_name: Name of the function
            
        Returns:
            DOT format string
        """
        cfg = self.get_function_cfg(file_path, function_name)
        
        dot_lines = ['digraph CFG {']
        dot_lines.append('  rankdir=TB;')
        dot_lines.append('  node [shape=box];')
        
        # Add nodes
        for block in cfg['blocks']:
            label = f"{block['type']}\\n{block['start_line']}-{block['end_line']}"
            if block['condition']:
                label += f"\\n{block['condition'][:20]}..."
            
            color = 'lightblue'
            if block['type'] == 'entry':
                color = 'lightgreen'
            elif block['type'] in ['exit', 'return']:
                color = 'lightcoral'
            elif block['type'] in ['condition', 'loop_condition']:
                color = 'lightyellow'
            
            dot_lines.append(f'  {block["id"]} [label="{label}", fillcolor={color}, style=filled];')
        
        # Add edges
        for edge in cfg['edges']:
            label = edge['type']
            style = 'solid'
            if edge['type'] == 'back_edge':
                style = 'dashed'
            elif edge['type'] in ['true', 'false']:
                label = 'T' if edge['type'] == 'true' else 'F'
            
            dot_lines.append(f'  {edge["source"]} -> {edge["target"]} [label="{label}", style={style}];')
        
        dot_lines.append('}')
        
        return '\n'.join(dot_lines)
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()