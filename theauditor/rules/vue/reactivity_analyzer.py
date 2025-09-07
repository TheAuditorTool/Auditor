"""Vue.js reactivity and props mutation analyzer.

This module analyzes Vue components for common anti-patterns:
1. Direct props mutation (violates one-way data flow)
2. Non-reactive data initialization (shared state bug)
"""

from typing import List, Dict, Any, Set, Optional


def find_vue_reactivity_issues(tree: Any, file_path: str) -> List[Dict[str, Any]]:
    """
    Detect Vue.js reactivity and props mutation issues using semantic AST.
    
    This function analyzes both Options API and Composition API components to detect:
    1. Direct props mutations (props.x = value)
    2. Non-reactive data initialization (shared objects/arrays)
    
    Args:
        tree: Semantic AST from js_semantic_parser.py
        file_path: Path to the Vue file being analyzed
        
    Returns:
        List of issues found with normalized format
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
                # First child is left operand, second is operator, third is right operand
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
    
    # Helper function to extract props from Options API
    def extract_options_api_props(node):
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
                                            prop_text = get_node_text(item).strip('"\'')
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
            child_props = extract_options_api_props(child)
            props.update(child_props)
        
        return props
    
    # Helper function to extract props from Composition API
    def extract_composition_api_props(node):
        """Extract props from Composition API defineProps call."""
        props = set()
        
        if not isinstance(node, dict):
            return props
        
        kind = node.get('kind', '')
        text = get_node_text(node)
        
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
            child_props = extract_composition_api_props(child)
            props.update(child_props)
        
        return props
    
    # Helper function to check for non-reactive data
    def check_data_function(node):
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
                            prop_value = None
                            for child in prop.get('children', []):
                                if isinstance(child, dict):
                                    value_kind = child.get('kind', '')
                                    value_text = get_node_text(child)
                                    
                                    # Detect empty object literal
                                    if value_kind == 'ObjectLiteralExpression' and value_text.strip() in ['{}', '{ }']:
                                        issues.append({
                                            'property': prop_name,
                                            'type': 'object',
                                            'line': get_node_line(prop)
                                        })
                                    # Detect empty array literal
                                    elif value_kind == 'ArrayLiteralExpression' and value_text.strip() in ['[]', '[ ]']:
                                        issues.append({
                                            'property': prop_name,
                                            'type': 'array',
                                            'line': get_node_line(prop)
                                        })
        
        # Recursively check children
        children = node.get('children', [])
        for child in children:
            child_issues = check_data_function(child)
            issues.extend(child_issues)
        
        return issues
    
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
            findings.append({
                'pattern_name': 'VUE_PROPS_MUTATION',
                'message': f'Direct mutation of prop "{mutated_prop}" violates one-way data flow',
                'file': file_path,
                'line': get_node_line(node),
                'column': node.get('column', 0),
                'severity': 'high',
                'category': 'vue',
                'confidence': 0.90,
                'details': {
                    'prop': mutated_prop,
                    'api_type': api_type,
                    'recommendation': f'Use a local data property or emit an event to update parent state'
                }
            })
        
        # Detection 2: Non-reactive data (Options API only)
        if not is_composition_api:
            data_issues = check_data_function(node)
            for issue in data_issues:
                findings.append({
                    'pattern_name': 'VUE_NON_REACTIVE_DATA',
                    'message': f'Non-reactive {issue["type"]} initialization in data() will be shared across component instances',
                    'file': file_path,
                    'line': issue['line'],
                    'column': 0,
                    'severity': 'high',
                    'category': 'vue',
                    'confidence': 0.85,
                    'details': {
                        'property': issue['property'],
                        'type': issue['type'],
                        'recommendation': f'Initialize {issue["type"]} in data() using a factory function or return new instance'
                    }
                })
        
        # Recursively traverse children
        children = node.get('children', [])
        for child in children:
            traverse_ast(child, depth + 1)
    
    # Extract props based on API style
    # First pass: identify props
    if '<script setup>' in str(tree) or 'defineProps' in get_node_text(ast_root):
        is_composition_api = True
        component_props = extract_composition_api_props(ast_root)
    else:
        component_props = extract_options_api_props(ast_root)
    
    # Second pass: find issues
    traverse_ast(ast_root)
    
    return findings