"""
Control Flow Graph (CFG) Builder for JavaScript/TypeScript.

Constructs a Control Flow Graph from an ESLint-compatible Abstract Syntax Tree (AST)
for a single function or method. This enables deeper analysis of code execution
paths in the Node.js and browser ecosystems.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set

# --- Data Structures (Mirrors the Python CFG) ---

@dataclass
class CFGNode:
    """A Basic Block in the Control Flow Graph."""
    id: int
    statements: List[Dict[str, Any]] = field(default_factory=list)
    predecessors: Set[int] = field(default_factory=set)
    successors: Set[int] = field(default_factory=set)
    type: str = "block"

    def __repr__(self) -> str:
        stmt_types = [s.get('type', 'Unknown') for s in self.statements]
        return f"<CFGNode id={self.id} type='{self.type}' stmts={stmt_types}>"

@dataclass
class CFGEdge:
    """An edge representing control flow between two CFGNodes."""
    source_id: int
    target_id: int
    condition: str = "normal"

    def __repr__(self) -> str:
        return f"<CFGEdge {self.source_id} -> {self.target_id} ({self.condition})>"

class CFG:
    """Represents the complete Control Flow Graph for a JS/TS function."""
    def __init__(self, name: str):
        self.name: str = name
        self.nodes: Dict[int, CFGNode] = {}
        self.edges: List[CFGEdge] = []
        self.entry_node: Optional[CFGNode] = None
        self.exit_node: Optional[CFGNode] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert the CFG to a serializable dictionary."""
        return {
            "name": self.name,
            "nodes": {nid: {
                "id": node.id,
                "type": node.type,
                "statements": node.statements, # AST nodes are already dicts
                "predecessors": sorted(list(node.predecessors)),
                "successors": sorted(list(node.successors)),
            } for nid, node in self.nodes.items()},
            "edges": [e.__dict__ for e in self.edges],
            "entry_node_id": self.entry_node.id if self.entry_node else None,
            "exit_node_id": self.exit_node.id if self.exit_node else None,
        }

# --- The JavaScript/TypeScript Builder ---

class CFGBuilderJS:
    """Builds a CFG from a JavaScript/TypeScript function's AST."""

    def build(self, name: str, func_ast: Dict[str, Any]) -> CFG:
        """
        Builds the CFG for a given function's ESLint-compatible AST.

        Args:
            name: The name of the function.
            func_ast: The AST node for the function (e.g., FunctionDeclaration,
                      ArrowFunctionExpression, FunctionExpression).

        Returns:
            The constructed CFG object.
        """
        self.cfg = CFG(name)
        self._node_counter = 0
        self._loop_stack = []  # For handling break/continue in nested loops
        self._switch_stack = [] # For handling break in switch statements

        entry_block = self._new_block(block_type='entry')
        exit_block = self._new_block(block_type='exit')
        self.cfg.entry_node = entry_block
        self.cfg.exit_node = exit_block

        # The function body is typically in a 'body' property which is a BlockStatement
        body_node = func_ast.get('body', {})
        if body_node.get('type') == 'BlockStatement':
            statements = body_node.get('body', [])
        else:
            # Handle concise arrow functions, e.g., () => value
            # Treat the expression as a return statement
            statements = [{'type': 'ReturnStatement', 'argument': body_node}]

        final_block = self._visit_statements(statements, entry_block)

        if final_block and not final_block.successors:
            self._add_edge(final_block.id, exit_block.id)

        return self.cfg

    # --- Graph Construction Helpers ---

    def _new_block(self, block_type: str = "block") -> CFGNode:
        """Creates a new basic block."""
        node_id = self._node_counter
        self._node_counter += 1
        block = CFGNode(id=node_id, type=block_type)
        self.cfg.nodes[node_id] = block
        return block

    def _add_edge(self, from_id: Optional[int], to_id: Optional[int], condition: str = "normal"):
        """Adds a directed edge."""
        if from_id is None or to_id is None:
            return
        self.cfg.edges.append(CFGEdge(from_id, to_id, condition))
        self.cfg.nodes[from_id].successors.add(to_id)
        self.cfg.nodes[to_id].predecessors.add(from_id)

    def _add_statement(self, block: CFGNode, statement: Dict[str, Any]):
        """Adds an AST statement to a block."""
        block.statements.append(statement)

    # --- AST Visitor Logic for JavaScript/TypeScript ---

    def _visit_statements(self, statements: List[Dict[str, Any]], current_block: CFGNode) -> Optional[CFGNode]:
        """Iteratively processes a list of statements."""
        block = current_block
        for stmt in statements:
            if not block or block.successors:
                return None  # Unreachable code path
            block = self._visit(stmt, block)
        return block

    def _visit(self, node: Dict[str, Any], current_block: CFGNode) -> CFGNode:
        """Dynamically dispatches to the correct visitor for a given AST node type."""
        node_type = node.get('type')
        method_name = f'_visit_{node_type}'
        visitor = getattr(self, method_name, self._visit_generic)
        return visitor(node, current_block)

    def _visit_generic(self, node: Dict[str, Any], current_block: CFGNode) -> CFGNode:
        """Handles any statement that doesn't alter control flow."""
        self._add_statement(current_block, node)
        return current_block

    def _visit_ReturnStatement(self, node: Dict[str, Any], current_block: CFGNode) -> CFGNode:
        """Handles `return`, connecting the path to the function's exit node."""
        self._add_statement(current_block, node)
        self._add_edge(current_block.id, self.cfg.exit_node.id)
        return current_block

    def _visit_ThrowStatement(self, node: Dict[str, Any], current_block: CFGNode) -> CFGNode:
        """Handles `throw`, which also terminates a path (simplified to exit)."""
        # In a more advanced implementation, this could connect to a global
        # 'unhandled_exception' node or the nearest 'catch' block.
        self._add_statement(current_block, node)
        self._add_edge(current_block.id, self.cfg.exit_node.id, condition='throw')
        return current_block

    def _visit_IfStatement(self, node: Dict[str, Any], current_block: CFGNode) -> CFGNode:
        """Handles `if/else`, creating branches and a merge point."""
        self._add_statement(current_block, node.get('test', {}))
        current_block.type = 'if_condition'

        # 'consequent' is the 'if' body
        if_body_block = self._new_block(block_type='if_body')
        self._add_edge(current_block.id, if_body_block.id, condition='True')
        final_if_block = self._visit_statements(node.get('consequent', {}).get('body', []), if_body_block)

        # 'alternate' is the 'else' body
        final_else_block = None
        if node.get('alternate'):
            else_body_block = self._new_block(block_type='else_body')
            self._add_edge(current_block.id, else_body_block.id, condition='False')
            
            # 'else' can be another 'if' or a block
            alt_body = node.get('alternate', {})
            alt_stmts = alt_body.get('body', []) if alt_body.get('type') == 'BlockStatement' else [alt_body]
            final_else_block = self._visit_statements(alt_stmts, else_body_block)

        merge_block = self._new_block(block_type='merge')

        if final_if_block and not final_if_block.successors:
            self._add_edge(final_if_block.id, merge_block.id)

        if node.get('alternate'):
            if final_else_block and not final_else_block.successors:
                self._add_edge(final_else_block.id, merge_block.id)
        else:
            self._add_edge(current_block.id, merge_block.id, condition='False')

        return merge_block

    def _visit_loop(self, node: Dict[str, Any], current_block: CFGNode, header_stmts_keys: List[str]) -> CFGNode:
        """Generic handler for `for`, `while`, and `do-while` loops."""
        loop_header = self._new_block(block_type='loop_header')
        for key in header_stmts_keys:
            if node.get(key):
                self._add_statement(loop_header, node.get(key))
        self._add_edge(current_block.id, loop_header.id)

        loop_body_block = self._new_block(block_type='loop_body')
        self._add_edge(loop_header.id, loop_body_block.id, condition='enter_loop')
        
        loop_exit_block = self._new_block(block_type='loop_exit')
        self._loop_stack.append((loop_header, loop_exit_block))

        body_stmts = node.get('body', {}).get('body', [])
        final_body_block = self._visit_statements(body_stmts, loop_body_block)

        if final_body_block and not final_body_block.successors:
            # Connect end of loop body back to the header
            self._add_edge(final_body_block.id, loop_header.id, condition='continue_loop')

        self._loop_stack.pop()
        self._add_edge(loop_header.id, loop_exit_block.id, condition='exit_loop')
        
        return loop_exit_block

    def _visit_ForStatement(self, node: Dict[str, Any], current_block: CFGNode) -> CFGNode:
        return self._visit_loop(node, current_block, ['init', 'test', 'update'])

    def _visit_WhileStatement(self, node: Dict[str, Any], current_block: CFGNode) -> CFGNode:
        return self._visit_loop(node, current_block, ['test'])
        
    def _visit_ForInStatement(self, node: Dict[str, Any], current_block: CFGNode) -> CFGNode:
        return self._visit_loop(node, current_block, ['left', 'right'])

    def _visit_ForOfStatement(self, node: Dict[str, Any], current_block: CFGNode) -> CFGNode:
        return self._visit_loop(node, current_block, ['left', 'right'])

    def _visit_BreakStatement(self, node: Dict[str, Any], current_block: CFGNode) -> CFGNode:
        """Handles `break`, jumping to the exit of the current loop or switch."""
        self._add_statement(current_block, node)
        # Prioritize breaking from a switch if inside one
        if self._switch_stack:
            _, exit_block = self._switch_stack[-1]
            self._add_edge(current_block.id, exit_block.id, condition='break')
        elif self._loop_stack:
            _, exit_block = self._loop_stack[-1]
            self._add_edge(current_block.id, exit_block.id, condition='break')
        return current_block

    def _visit_ContinueStatement(self, node: Dict[str, Any], current_block: CFGNode) -> CFGNode:
        """Handles `continue`, jumping to the header of the current loop."""
        self._add_statement(current_block, node)
        if self._loop_stack:
            header_block, _ = self._loop_stack[-1]
            self._add_edge(current_block.id, header_block.id, condition='continue')
        return current_block

    def _visit_SwitchStatement(self, node: Dict[str, Any], current_block: CFGNode) -> CFGNode:
        """Handles `switch`, creating branches for each `case`."""
        self._add_statement(current_block, node.get('discriminant', {}))
        current_block.type = 'switch_discriminant'

        switch_exit_block = self._new_block(block_type='switch_exit')
        self._switch_stack.append((current_block, switch_exit_block))

        last_case_block = current_block
        has_default = False

        for case in node.get('cases', []):
            case_block = self._new_block(block_type='case_body')
            condition = 'default' if case.get('test') is None else 'case'
            if condition == 'default':
                has_default = True
            
            self._add_edge(last_case_block.id, case_block.id, condition=condition)
            
            final_case_block = self._visit_statements(case.get('consequent', []), case_block)
            
            # If the case doesn't break, it falls through to the next one
            if final_case_block and not final_case_block.successors:
                last_case_block = final_case_block
            else: # It broke, so the next case branches from the discriminant
                last_case_block = current_block

        # Unbroken paths and the main path connect to the exit
        if last_case_block.id != current_block.id and not last_case_block.successors:
             self._add_edge(last_case_block.id, switch_exit_block.id)
        if not has_default:
             self._add_edge(current_block.id, switch_exit_block.id, condition='no_case_match')

        self._switch_stack.pop()
        return switch_exit_block


    def _visit_TryStatement(self, node: Dict[str, Any], current_block: CFGNode) -> CFGNode:
        """Handles `try/catch/finally` blocks."""
        try_body_block = self._new_block(block_type='try_body')
        self._add_edge(current_block.id, try_body_block.id)
        final_try_block = self._visit_statements(node.get('block', {}).get('body', []), try_body_block)

        # The 'handler' is the 'catch' block
        final_catch_block = None
        if node.get('handler'):
            catch_block = self._new_block(block_type='catch_clause')
            # Exception can happen anywhere in 'try' block. Connect from start.
            self._add_edge(try_body_block.id, catch_block.id, condition='exception')
            catch_body_stmts = node.get('handler', {}).get('body', {}).get('body', [])
            final_catch_block = self._visit_statements(catch_body_stmts, catch_block)

        merge_block = self._new_block(block_type='merge')

        if final_try_block and not final_try_block.successors:
            self._add_edge(final_try_block.id, merge_block.id)
        if final_catch_block and not final_catch_block.successors:
            self._add_edge(final_catch_block.id, merge_block.id)
        
        # If there's no catch, exceptions from try still need a path
        if not node.get('handler') and final_try_block and not final_try_block.successors:
             self._add_edge(final_try_block.id, merge_block.id)

        # The 'finalizer' is the 'finally' block
        if node.get('finalizer'):
            finally_block = self._new_block(block_type='finally_body')
            # All paths (try, catch) go through finally
            self._add_edge(merge_block.id, finally_block.id)
            final_finally_block = self._visit_statements(node.get('finalizer', {}).get('body', []), finally_block)
            return final_finally_block

        return merge_block

# --- Example Usage ---

if __name__ == '__main__':
    # You need a JavaScript parser. 'esprima' is a good, lightweight choice.
    # Install it with: pip install esprima
    try:
        import esprima
        import json
    except ImportError:
        print("Please install 'esprima' to run the example: pip install esprima")
        exit(1)

    source_code = """
async function processData(items, client) {
    if (!items || items.length === 0) {
        throw new Error("No items to process");
    }

    let processedCount = 0;
    for (const item of items) {
        try {
            switch (item.type) {
                case 'A':
                    await client.doA(item);
                    break;
                case 'B':
                    await client.doB(item);
                    // fallthrough
                default:
                    processedCount++;
            }
        } catch (e) {
            console.error("Failed to process item", e);
            continue;
        } finally {
            console.log("Processed one item.");
        }
    }
    return processedCount;
}
"""
    print("--- Building CFG for JavaScript function `processData` ---")

    # 1. Parse the JS code into an ESLint-compatible AST.
    parsed_ast = esprima.parseModule(source_code)
    
    # 2. Find the AST for the target function.
    func_def_node = None
    for node in parsed_ast.body:
        if node.type == 'FunctionDeclaration' and node.id.name == 'processData':
            func_def_node = node
            break

    if func_def_node:
        # 3. Instantiate the builder and build the CFG.
        builder = CFGBuilderJS()
        cfg = builder.build("processData", func_def_node)

        # 4. Print the result as a JSON-serializable dictionary.
        cfg_dict = cfg.to_dict()
        print(json.dumps(cfg_dict, indent=2))
        
        print("\n--- CFG construction successful ---")
    else:
        print("Could not find function 'processData' in the source code.")
