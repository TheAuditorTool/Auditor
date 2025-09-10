"""
Control Flow Graph (CFG) Builder.

Constructs a Control Flow Graph from an Abstract Syntax Tree (AST) for a single
function or method. This enables deeper analysis of code execution paths for
detecting resource leaks, unreachable code, and complex logical errors.
"""

import ast
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set, Tuple

# --- Data Structures ---

@dataclass
class CFGNode:
    """A Basic Block in the Control Flow Graph."""
    id: int
    statements: List[ast.AST] = field(default_factory=list)
    predecessors: Set[int] = field(default_factory=set)
    successors: Set[int] = field(default_factory=set)
    # Type provides context: 'entry', 'exit', 'if', 'loop_header', 'try', etc.
    type: str = "block"

    def __repr__(self) -> str:
        # Represent the AST nodes as their class names for readability
        stmt_types = [s.__class__.__name__ for s in self.statements]
        return f"<CFGNode id={self.id} type='{self.type}' stmts={stmt_types}>"

@dataclass
class CFGEdge:
    """An edge representing control flow between two CFGNodes."""
    source_id: int
    target_id: int
    # Condition provides context for the branch: 'True', 'False', 'exception', etc.
    condition: str = "normal"

    def __repr__(self) -> str:
        return f"<CFGEdge {self.source_id} -> {self.target_id} ({self.condition})>"

class CFG:
    """Represents the complete Control Flow Graph for a function."""
    def __init__(self, name: str):
        self.name: str = name
        self.nodes: Dict[int, CFGNode] = {}
        self.edges: List[CFGEdge] = []
        self.entry_node: Optional[CFGNode] = None
        self.exit_node: Optional[CFGNode] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert the CFG to a serializable dictionary for analysis or storage."""
        return {
            "name": self.name,
            "nodes": {nid: {
                "id": node.id,
                "type": node.type,
                # ast.dump provides a string representation of the AST node
                "statements": [ast.dump(s) for s in node.statements],
                "predecessors": sorted(list(node.predecessors)),
                "successors": sorted(list(node.successors)),
            } for nid, node in self.nodes.items()},
            "edges": [e.__dict__ for e in self.edges],
            "entry_node_id": self.entry_node.id if self.entry_node else None,
            "exit_node_id": self.exit_node.id if self.exit_node else None,
        }

# --- The Builder ---

class CFGBuilder:
    """Builds a CFG from a function's AST using a visitor pattern."""

    def build(self, name: str, func_ast: ast.FunctionDef) -> CFG:
        """
        Builds the CFG for a given function AST. This is the main public method.

        Args:
            name: The name of the function being analyzed.
            func_ast: The ast.FunctionDef node from Python's `ast` module.

        Returns:
            The constructed CFG object, ready for analysis.
        """
        self.cfg = CFG(name)
        self._node_counter = 0
        self._loop_stack = []  # Stack to manage nested loops (for break/continue)

        # Every function CFG starts with an entry and ends with an exit.
        entry_block = self._new_block(block_type='entry')
        exit_block = self._new_block(block_type='exit')
        self.cfg.entry_node = entry_block
        self.cfg.exit_node = exit_block

        # Start processing from the function body.
        final_block = self._visit_statements(func_ast.body, entry_block)

        # If the function doesn't end with an explicit return, connect its last
        # block to the exit node.
        if final_block and not final_block.successors:
             self._add_edge(final_block.id, exit_block.id)

        return self.cfg

    # --- Graph Construction Helpers ---

    def _new_block(self, block_type: str = "block") -> CFGNode:
        """Creates a new basic block and adds it to the graph."""
        node_id = self._node_counter
        self._node_counter += 1
        block = CFGNode(id=node_id, type=block_type)
        self.cfg.nodes[node_id] = block
        return block

    def _add_edge(self, from_id: int, to_id: int, condition: str = "normal"):
        """Adds a directed edge between two blocks."""
        if from_id is None or to_id is None:
            return
        self.cfg.edges.append(CFGEdge(from_id, to_id, condition))
        self.cfg.nodes[from_id].successors.add(to_id)
        self.cfg.nodes[to_id].predecessors.add(from_id)

    def _add_statement(self, block: CFGNode, statement: ast.AST):
        """Adds an AST statement to a basic block."""
        block.statements.append(statement)

    # --- AST Visitor Logic ---

    def _visit_statements(self, statements: List[ast.AST], current_block: CFGNode) -> Optional[CFGNode]:
        """Iteratively processes a list of statements, handling control flow."""
        block = current_block
        for stmt in statements:
            # If a block is terminated (e.g., by a return), subsequent statements
            # in the same list are unreachable from this path.
            if not block or block.successors:
                # We could optionally create and track unreachable code blocks.
                # For now, we just stop processing this path.
                return None
            block = self._visit(stmt, block)
        return block

    def _visit(self, node: ast.AST, current_block: CFGNode) -> CFGNode:
        """Dynamically dispatches to the correct visitor based on AST node type."""
        method_name = f'_visit_{node.__class__.__name__}'
        visitor = getattr(self, method_name, self._visit_generic)
        return visitor(node, current_block)

    def _visit_generic(self, node: ast.AST, current_block: CFGNode) -> CFGNode:
        """Handles any statement that doesn't alter control flow."""
        self._add_statement(current_block, node)
        return current_block

    def _visit_Return(self, node: ast.Return, current_block: CFGNode) -> CFGNode:
        """Handles `return`, which terminates the current path and goes to exit."""
        self._add_statement(current_block, node)
        self._add_edge(current_block.id, self.cfg.exit_node.id)
        return current_block

    def _visit_If(self, node: ast.If, current_block: CFGNode) -> CFGNode:
        """Handles `if/else`, creating true/false branches and a merge point."""
        # The current block ends with the if's test condition.
        self._add_statement(current_block, node.test)
        current_block.type = 'if_condition'

        # Create blocks for the 'true' and 'false' branches.
        if_body_block = self._new_block(block_type='if_body')
        self._add_edge(current_block.id, if_body_block.id, condition='True')
        final_if_block = self._visit_statements(node.body, if_body_block)

        final_else_block = None
        if node.orelse:
            else_body_block = self._new_block(block_type='else_body')
            self._add_edge(current_block.id, else_body_block.id, condition='False')
            final_else_block = self._visit_statements(node.orelse, else_body_block)

        # Create a merge block for the paths to rejoin.
        merge_block = self._new_block(block_type='merge')

        # Connect the end of the 'if' body to the merge block.
        if final_if_block and not final_if_block.successors:
            self._add_edge(final_if_block.id, merge_block.id)

        # Connect the 'else' path to the merge block.
        if node.orelse:
            if final_else_block and not final_else_block.successors:
                self._add_edge(final_else_block.id, merge_block.id)
        else:
            # If no 'else', the false path bypasses the 'if' body to the merge block.
            self._add_edge(current_block.id, merge_block.id, condition='False')

        # The new current block is the merge block.
        return merge_block

    def _visit_For(self, node: ast.For, current_block: CFGNode) -> CFGNode:
        """Handles `for` loops, creating a header, body, and exit path."""
        # A `for` loop without an `else` block is simpler.
        loop_header = self._new_block(block_type='loop_header')
        self._add_statement(loop_header, node.iter)
        self._add_edge(current_block.id, loop_header.id)

        loop_body = self._new_block(block_type='loop_body')
        self._add_edge(loop_header.id, loop_body.id, condition='enter_loop')

        # Push loop header and exit block to the stack for break/continue.
        loop_exit_block = self._new_block(block_type='loop_exit')
        self._loop_stack.append((loop_header, loop_exit_block))

        final_body_block = self._visit_statements(node.body, loop_body)
        if final_body_block and not final_body_block.successors:
            self._add_edge(final_body_block.id, loop_header.id, condition='continue_loop')

        self._loop_stack.pop()

        # The exit path from the loop.
        self._add_edge(loop_header.id, loop_exit_block.id, condition='exit_loop')
        return loop_exit_block

    def _visit_While(self, node: ast.While, current_block: CFGNode) -> CFGNode:
        """Handles `while` loops, with a condition-checking header."""
        loop_header = self._new_block(block_type='loop_header')
        self._add_statement(loop_header, node.test)
        self._add_edge(current_block.id, loop_header.id)

        loop_body = self._new_block(block_type='loop_body')
        self._add_edge(loop_header.id, loop_body.id, condition='True')

        loop_exit_block = self._new_block(block_type='loop_exit')
        self._loop_stack.append((loop_header, loop_exit_block))

        final_body_block = self._visit_statements(node.body, loop_body)
        if final_body_block and not final_body_block.successors:
            self._add_edge(final_body_block.id, loop_header.id, condition='continue_loop')

        self._loop_stack.pop()

        self._add_edge(loop_header.id, loop_exit_block.id, condition='False')
        return loop_exit_block

    def _visit_Break(self, node: ast.Break, current_block: CFGNode) -> CFGNode:
        """Handles `break`, jumping to the current loop's exit block."""
        self._add_statement(current_block, node)
        if self._loop_stack:
            _, exit_block = self._loop_stack[-1]
            self._add_edge(current_block.id, exit_block.id, condition='break')
        return current_block

    def _visit_Continue(self, node: ast.Continue, current_block: CFGNode) -> CFGNode:
        """Handles `continue`, jumping to the current loop's header block."""
        self._add_statement(current_block, node)
        if self._loop_stack:
            header_block, _ = self._loop_stack[-1]
            self._add_edge(current_block.id, header_block.id, condition='continue')
        return current_block

    def _visit_Try(self, node: ast.Try, current_block: CFGNode) -> CFGNode:
        """Handles `try/except/else/finally`, the most complex control flow."""
        # The 'try' block follows the current block.
        try_block = self._new_block(block_type='try_body')
        self._add_edge(current_block.id, try_block.id)
        final_try_block = self._visit_statements(node.body, try_block)

        # The 'else' block executes if no exceptions were raised in 'try'.
        final_else_block = None
        if node.orelse:
            else_block = self._new_block(block_type='else_body')
            if final_try_block and not final_try_block.successors:
                self._add_edge(final_try_block.id, else_block.id)
            final_else_block = self._visit_statements(node.orelse, else_block)

        # Exception handlers branch off from the 'try' block.
        handler_exit_blocks = []
        for handler in node.handlers:
            handler_block = self._new_block(block_type='except_handler')
            # An exception can occur at any point in the 'try' block.
            # Simplified: connect from the start of the 'try' block.
            self._add_edge(try_block.id, handler_block.id, condition='exception')
            final_handler_block = self._visit_statements(handler.body, handler_block)
            if final_handler_block and not final_handler_block.successors:
                handler_exit_blocks.append(final_handler_block)

        # Create a merge block for all normal (non-finally) paths.
        merge_block = self._new_block(block_type='merge')

        # Connect paths that didn't terminate to the merge block.
        if not node.orelse and final_try_block and not final_try_block.successors:
            self._add_edge(final_try_block.id, merge_block.id)
        if final_else_block and not final_else_block.successors:
            self._add_edge(final_else_block.id, merge_block.id)
        for block in handler_exit_blocks:
            self._add_edge(block.id, merge_block.id)

        # The 'finally' block executes on all paths.
        if node.finalbody:
            finally_block = self._new_block(block_type='finally_body')
            # Connect all preceding exit points to 'finally'.
            self._add_edge(merge_block.id, finally_block.id)
            final_finally_block = self._visit_statements(node.finalbody, finally_block)
            return final_finally_block

        return merge_block

# --- Example Usage ---

if __name__ == '__main__':
    # A complex example demonstrating loops, conditionals, and exceptions.
    source_code = """
def process_file(path, force=False):
    if not path:
        return False  # Early exit

    records = []
    try:
        f = open(path, 'r')
        for i in range(10):
            if i % 4 == 0:
                continue # Skip multiples of 4
            line = f.readline()
            if not line:
                break # Exit loop if file ends
            records.append(line)
        else:
            print("Loop completed without break")
    except IOError as e:
        print(f"Error opening or reading file: {e}")
        return False # Exit on error
    finally:
        print("Executing finally block")
        if 'f' in locals() and f:
            f.close()

    if force:
        print("Forced processing")

    return len(records) > 0
"""
    print("--- Building CFG for `process_file` ---")

    # 1. Get the AST for the target function.
    tree = ast.parse(source_code)
    func_def_node = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)), None)

    if func_def_node:
        # 2. Instantiate the builder and build the CFG.
        builder = CFGBuilder()
        cfg = builder.build("process_file", func_def_node)

        # 3. Print the resulting CFG as a JSON-serializable dictionary.
        import json
        cfg_dict = cfg.to_dict()
        print(json.dumps(cfg_dict, indent=2))

        # 4. A simple analysis: find all terminated paths (no successors).
        print("\n--- Simple Analysis: Find Terminal Blocks ---")
        terminal_nodes = [
            node for node in cfg.nodes.values()
            if not node.successors and node.type != 'exit'
        ]
        print(f"Found {len(terminal_nodes)} improperly terminated paths.")
        for node in terminal_nodes:
            print(f"  - Node {node.id} of type '{node.type}' has no successors.")
        print("Note: The builder connects unterminated paths to the exit node, so this should be 0.")

