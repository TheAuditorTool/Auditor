"""Vue.js reactivity and props mutation analyzer - Hybrid Database/AST Implementation.

This module detects Vue-specific anti-patterns that require semantic understanding:
1. Direct props mutation (violates one-way data flow)
2. Non-reactive data initialization (shared state bug)

REQUIRES HYBRID APPROACH: The database doesn't capture Vue component semantics
like props definitions, data() functions, or component boundaries. These require
semantic AST analysis via js_semantic_parser.
"""

import sqlite3
from typing import List, Dict, Any, Set, Optional
from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity


def find_vue_reactivity_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """
    Detect Vue.js reactivity and props mutation issues using hybrid approach.

    This function uses database for file filtering, then semantic AST for Vue-specific
    pattern detection since the database lacks Vue component semantics.

    Args:
        context: StandardRuleContext with database path and file info

    Returns:
        List of Vue reactivity findings
    """
    findings = []

    # First, check if this is a Vue file worth analyzing
    if not _should_analyze_file(context):
        return findings

    # Try database-based detection first (limited but fast)
    findings.extend(_find_obvious_mutations_via_database(context))

    # Fallback to semantic AST for comprehensive Vue detection
    # This is REQUIRED because database doesn't track:
    # - Which variables are props vs data vs computed
    # - Component boundaries (Options API vs Composition API)
    # - data() function return patterns
    semantic_ast = context.get_ast("semantic_ast")
    if semantic_ast:
        findings.extend(_find_vue_issues_via_ast(semantic_ast, context.file_path))

    return findings


def _should_analyze_file(context: StandardRuleContext) -> bool:
    """Check if file should be analyzed for Vue patterns."""

    # Skip test files
    if any(pattern in context.file_path.lower() for pattern in ['test', 'spec', '__mocks__']):
        return False

    # Check file extension
    if not any(context.file_path.endswith(ext) for ext in ['.vue', '.js', '.ts', '.jsx', '.tsx']):
        return False

    # If we have database, check for Vue indicators
    if context.db_path:
        conn = sqlite3.connect(context.db_path)
        cursor = conn.cursor()

        try:
            # Check if file imports Vue or uses Vue patterns
            cursor.execute("""
                SELECT COUNT(*)
                FROM refs
                WHERE src = ?
                  AND (value LIKE '%vue%' OR value LIKE '%@vue%')
            """, (context.file_path,))

            has_vue_imports = cursor.fetchone()[0] > 0

            if not has_vue_imports:
                # Check for Vue-specific symbols
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM symbols
                    WHERE path = ?
                      AND (name LIKE '%defineProps%'
                           OR name LIKE '%defineEmits%'
                           OR name LIKE '%$emit%'
                           OR name LIKE '%$refs%')
                """, (context.file_path,))

                has_vue_symbols = cursor.fetchone()[0] > 0

                if not has_vue_symbols:
                    return False

        finally:
            conn.close()

    return True


def _find_obvious_mutations_via_database(context: StandardRuleContext) -> List[StandardFinding]:
    """Find obvious prop mutations using database (limited detection)."""
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        # Look for assignments to common prop patterns
        # This will have false positives but is fast
        cursor.execute("""
            SELECT line, target_var, source_expr
            FROM assignments
            WHERE file = ?
              AND (target_var LIKE 'this.props.%'
                   OR target_var LIKE 'props.%'
                   OR target_var LIKE 'this.$props.%')
        """, (context.file_path,))

        for line, target, source in cursor.fetchall():
            findings.append(StandardFinding(
                rule_name='vue-props-mutation-obvious',
                message=f'Direct mutation of props detected: {target}',
                file_path=context.file_path,
                line=line,
                severity=Severity.HIGH,
                category='vue',
                snippet=f'{target} = {source[:50]}...' if len(source) > 50 else f'{target} = {source}',
                fix_suggestion='Use local data property or emit event to parent',
                confidence=0.7  # Lower confidence since we can't verify it's actually a prop
            ))

    finally:
        conn.close()

    return findings


def _find_vue_issues_via_ast(tree: Any, file_path: str) -> List[StandardFinding]:
    """
    Detect Vue issues using semantic AST (comprehensive detection).

    This is the original logic adapted to return StandardFinding objects.
    We MUST use AST here because the database doesn't capture:
    - Component structure (Options vs Composition API)
    - Props definitions (array syntax, object syntax, defineProps)
    - data() function semantics
    """
    findings = []

    # Validate AST structure
    if not tree or not isinstance(tree, dict):
        return findings

    # Extract root AST node
    ast_root = tree.get('ast')
    if not ast_root:
        return findings

    # Track component's props for mutation detection
    component_props = set()
    is_composition_api = False

    # Helper function to extract text from node
    def get_node_text(node):
        """Extract text content from an AST node."""
        if isinstance(node, dict):
            return node.get('text', '')
        return str(node)

    # Helper function to get line number
    def get_node_line(node):
        """Extract line number from an AST node."""
        if isinstance(node, dict):
            return node.get('line', 0)
        return 0

    # Helper function to check if node is a props mutation
    def is_props_mutation(node, props_list):
        """Check if node represents a mutation of component props."""
        if not isinstance(node, dict):
            return False, None

        kind = node.get('kind', '')

        # Check for assignment expressions
        if kind == 'BinaryExpression':
            children = node.get('children', [])
            if len(children) >= 3:
                left = children[0] if children else None
                operator = children[1] if len(children) > 1 else None

                # Check if operator is assignment
                if operator and isinstance(operator, dict):
                    op_text = get_node_text(operator)
                    if '=' in op_text and '==' not in op_text and '!=' not in op_text:
                        # Check if left side references props
                        if left:
                            left_text = get_node_text(left)
                            # Check for this.propName or props.propName patterns
                            for prop in props_list:
                                if f'this.{prop}' in left_text or f'props.{prop}' in left_text:
                                    return True, prop

        return False, None

    # Extract props based on API style
    if '<script setup>' in str(tree) or 'defineProps' in get_node_text(ast_root):
        is_composition_api = True
        component_props = _extract_composition_api_props(ast_root, get_node_text)
    else:
        component_props = _extract_options_api_props(ast_root, get_node_text)

    # Main traversal function
    def traverse_ast(node, depth=0):
        """Traverse AST to find Vue reactivity issues."""
        nonlocal is_composition_api

        if depth > 100 or not isinstance(node, dict):
            return

        kind = node.get('kind', '')
        text = get_node_text(node)

        # Detect Composition API
        if 'defineProps' in text or 'defineEmits' in text or '<script setup>' in str(tree):
            is_composition_api = True

        # Detection 1: Props mutations
        is_mutation, mutated_prop = is_props_mutation(node, component_props)
        if is_mutation:
            api_type = 'Composition API' if is_composition_api else 'Options API'
            findings.append(StandardFinding(
                rule_name='vue-props-mutation',
                message=f'Direct mutation of prop "{mutated_prop}" violates one-way data flow',
                file_path=file_path,
                line=get_node_line(node),
                column=node.get('column', 0),
                severity=Severity.HIGH,
                category='vue',
                confidence=0.90,
                snippet=text[:100] if len(text) > 100 else text,
                fix_suggestion=f'Use local data property or emit event to update parent state',
                metadata={
                    'prop': mutated_prop,
                    'api_type': api_type
                }
            ))

        # Detection 2: Non-reactive data (Options API only)
        if not is_composition_api:
            data_issues = _check_data_function(node, get_node_text, get_node_line)
            for issue in data_issues:
                findings.append(StandardFinding(
                    rule_name='vue-non-reactive-data',
                    message=f'Non-reactive {issue["type"]} initialization in data() will be shared across component instances',
                    file_path=file_path,
                    line=issue['line'],
                    column=0,
                    severity=Severity.HIGH,
                    category='vue',
                    confidence=0.85,
                    snippet=f'data() {{ return {{ {issue["property"]}: {issue["type"]} }} }}',
                    fix_suggestion=f'Initialize {issue["type"]} in data() using factory function or return new instance',
                    metadata={
                        'property': issue['property'],
                        'type': issue['type']
                    }
                ))

        # Recursively traverse children
        children = node.get('children', [])
        for child in children:
            traverse_ast(child, depth + 1)

    # Run the traversal
    traverse_ast(ast_root)

    return findings


def _extract_options_api_props(node, get_text_func):
    """Extract props from Options API component definition."""
    props = set()

    if not isinstance(node, dict):
        return props

    kind = node.get('kind', '')

    # Look for export default { props: {...} }
    if kind == 'ObjectLiteralExpression':
        children = node.get('children', [])
        for child in children:
            if isinstance(child, dict) and child.get('kind') == 'PropertyAssignment':
                prop_name = child.get('name', '')
                if prop_name == 'props':
                    # Extract prop definitions
                    prop_children = child.get('children', [])
                    for prop_child in prop_children:
                        if isinstance(prop_child, dict):
                            # Handle props: ['prop1', 'prop2'] array syntax
                            if prop_child.get('kind') == 'ArrayLiteralExpression':
                                array_children = prop_child.get('children', [])
                                for item in array_children:
                                    if isinstance(item, dict) and item.get('kind') == 'StringLiteral':
                                        prop_text = get_text_func(item).strip('"\'')
                                        props.add(prop_text)
                            # Handle props: { prop1: Type, prop2: {...} } object syntax
                            elif prop_child.get('kind') == 'ObjectLiteralExpression':
                                obj_children = prop_child.get('children', [])
                                for prop_def in obj_children:
                                    if isinstance(prop_def, dict) and prop_def.get('kind') == 'PropertyAssignment':
                                        props.add(prop_def.get('name', ''))

    # Recursively check children
    children = node.get('children', [])
    for child in children:
        child_props = _extract_options_api_props(child, get_text_func)
        props.update(child_props)

    return props


def _extract_composition_api_props(node, get_text_func):
    """Extract props from Composition API defineProps call."""
    props = set()

    if not isinstance(node, dict):
        return props

    kind = node.get('kind', '')
    text = get_text_func(node)

    # Look for defineProps call
    if kind == 'CallExpression' and 'defineProps' in text:
        children = node.get('children', [])
        # First child after function name is the props object
        for child in children:
            if isinstance(child, dict) and child.get('kind') == 'ObjectLiteralExpression':
                obj_children = child.get('children', [])
                for prop_def in obj_children:
                    if isinstance(prop_def, dict) and prop_def.get('kind') == 'PropertyAssignment':
                        props.add(prop_def.get('name', ''))

    # Recursively check children
    children = node.get('children', [])
    for child in children:
        child_props = _extract_composition_api_props(child, get_text_func)
        props.update(child_props)

    return props


def _check_data_function(node, get_text_func, get_line_func):
    """Check data() function for non-reactive initialization patterns."""
    issues = []

    if not isinstance(node, dict):
        return issues

    kind = node.get('kind', '')

    # Look for data() method in Options API
    if kind == 'MethodDeclaration' or kind == 'PropertyAssignment':
        name = node.get('name', '')
        if name == 'data':
            # Analyze the return statement
            def find_return_object(n):
                if not isinstance(n, dict):
                    return None
                if n.get('kind') == 'ReturnStatement':
                    children = n.get('children', [])
                    if children and isinstance(children[0], dict):
                        return children[0]
                # Recursively check children
                for child in n.get('children', []):
                    result = find_return_object(child)
                    if result:
                        return result
                return None

            return_obj = find_return_object(node)
            if return_obj and return_obj.get('kind') == 'ObjectLiteralExpression':
                # Check properties of returned object
                obj_children = return_obj.get('children', [])
                for prop in obj_children:
                    if isinstance(prop, dict) and prop.get('kind') == 'PropertyAssignment':
                        prop_name = prop.get('name', '')
                        # Check for object/array literal initializers
                        for child in prop.get('children', []):
                            if isinstance(child, dict):
                                value_kind = child.get('kind', '')
                                value_text = get_text_func(child)

                                # Detect empty object literal
                                if value_kind == 'ObjectLiteralExpression' and value_text.strip() in ['{}', '{ }']:
                                    issues.append({
                                        'property': prop_name,
                                        'type': 'object',
                                        'line': get_line_func(prop)
                                    })
                                # Detect empty array literal
                                elif value_kind == 'ArrayLiteralExpression' and value_text.strip() in ['[]', '[ ]']:
                                    issues.append({
                                        'property': prop_name,
                                        'type': 'array',
                                        'line': get_line_func(prop)
                                    })

    # Recursively check children
    children = node.get('children', [])
    for child in children:
        child_issues = _check_data_function(child, get_text_func, get_line_func)
        issues.extend(child_issues)

    return issues