## 0. Verification (Pre-Implementation)

- [ ] 0.1 Read `theauditor/indexer/extractors/go.py` - confirm current state (no assignments/calls tables)
- [ ] 0.2 Read `theauditor/indexer/extractors/go_impl.py` - understand existing AST processing
- [ ] 0.3 Read `theauditor/indexer/extractors/python.py` as reference - see how assignments are extracted
- [ ] 0.4 Read `theauditor/indexer/extractors/rust.py` as reference - see recent integration pattern
- [ ] 0.5 Read `rules/go/injection_analyze.py` - confirm source/sink patterns exist
- [ ] 0.6 Query database to confirm 0 Go rows in language-agnostic tables

## 1. Assignment Extraction

- [ ] 1.1 Add tree-sitter queries for `short_var_declaration` nodes (`:=` syntax)
- [ ] 1.2 Add tree-sitter queries for `assignment_statement` nodes (`=` syntax)
- [ ] 1.3 Handle compound assignments (`+=`, `-=`, `*=`, etc.)
- [ ] 1.4 Handle multiple assignment targets (`a, b := foo()`)
- [ ] 1.5 Skip blank identifier (`_`) - do NOT create assignment rows for `_`
- [ ] 1.6 Extract source variables from RHS for `assignment_sources` table
- [ ] 1.7 Add logging: `logger.debug(f"Go: extracted {count} assignments from {file}")`
- [ ] 1.8 Write unit tests for assignment extraction

**Implementation Details:**
```python
# In go.py extract() method
def _extract_assignments(self, tree, file_path: str, in_function: str) -> list[dict]:
    """Extract variable assignments for language-agnostic tables."""
    assignments = []

    # Short variable declaration: x := expr
    for node in tree.root_node.descendants:
        if node.type == "short_var_declaration":
            # Left side: identifier_list
            # Right side: expression_list
            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")

            if left and right:
                targets = [c for c in left.children if c.type == "identifier"]
                sources = right.text.decode("utf-8")

                for target in targets:
                    target_name = target.text.decode("utf-8")
                    if target_name == "_":
                        continue  # Skip blank identifier

                    assignments.append({
                        "file": file_path,
                        "line": node.start_point[0] + 1,
                        "col": node.start_point[1],
                        "target_var": target_name,
                        "source_expr": sources,
                        "in_function": in_function,
                    })

    return assignments
```

## 2. Function Call Extraction

- [ ] 2.1 Add tree-sitter queries for `call_expression` nodes
- [ ] 2.2 Handle simple function calls: `foo(a, b)`
- [ ] 2.3 Handle method calls: `obj.Method(x)`
- [ ] 2.4 Handle chained calls: `a.B().C()`
- [ ] 2.5 Extract argument expressions with correct indices
- [ ] 2.6 Resolve callee file path when possible (using import analysis)
- [ ] 2.7 Add logging: `logger.debug(f"Go: extracted {count} function calls from {file}")`
- [ ] 2.8 Write unit tests for call extraction

**Implementation Details:**
```python
# In go.py extract() method
def _extract_function_calls(self, tree, file_path: str, in_function: str) -> list[dict]:
    """Extract function calls for language-agnostic tables."""
    calls = []

    for node in tree.root_node.descendants:
        if node.type == "call_expression":
            func_node = node.child_by_field_name("function")
            args_node = node.child_by_field_name("arguments")

            if func_node:
                callee = func_node.text.decode("utf-8")

                # Extract arguments
                if args_node:
                    arg_idx = 0
                    for child in args_node.children:
                        if child.type not in ("(", ")", ","):
                            calls.append({
                                "file": file_path,
                                "line": node.start_point[0] + 1,
                                "caller_function": in_function,
                                "callee_function": callee,
                                "argument_index": arg_idx,
                                "argument_expr": child.text.decode("utf-8"),
                            })
                            arg_idx += 1

    return calls
```

## 3. Return Statement Extraction

- [ ] 3.1 Add tree-sitter queries for `return_statement` nodes
- [ ] 3.2 Handle single return value: `return x`
- [ ] 3.3 Handle multiple return values: `return a, b, nil`
- [ ] 3.4 Handle naked returns (named return values)
- [ ] 3.5 Extract source variables for `function_return_sources` table
- [ ] 3.6 Add logging: `logger.debug(f"Go: extracted {count} returns from {file}")`
- [ ] 3.7 Write unit tests for return extraction

## 4. Function Parameter Extraction

- [ ] 4.1 Add tree-sitter queries for `parameter_declaration` nodes
- [ ] 4.2 Handle simple params: `func foo(a int)`
- [ ] 4.3 Handle grouped params: `func foo(a, b int)`
- [ ] 4.4 Handle variadic params: `func foo(args ...string)`
- [ ] 4.5 Populate `func_params` table with param_name, param_index
- [ ] 4.6 Add logging: `logger.debug(f"Go: extracted {count} function params from {file}")`
- [ ] 4.7 Write unit tests for param extraction

## 5. Integration

- [ ] 5.1 Wire new extraction methods into main `extract()` return dict
- [ ] 5.2 Ensure storage layer handles new data (check `node_storage.py` or `python_storage.py` pattern)
- [ ] 5.3 Run `aud full --offline` on TheAuditor dogfood
- [ ] 5.4 Query database to verify Go rows appear in language-agnostic tables
- [ ] 5.5 Run `aud full --offline` on a Go project (if available)

## 6. Taint Verification

- [ ] 6.1 Verify existing Go source/sink patterns still work with new DFG edges
- [ ] 6.2 Run taint analysis on Go code, confirm flows are detected
- [ ] 6.3 Document any pattern adjustments needed

## 7. Documentation

- [ ] 7.1 Update extractor docstrings with new capability
- [ ] 7.2 Add logging messages following existing pattern: `from theauditor.utils.logging import logger`
