"""Performance-focused AST rules for TheAuditor.

This module contains AST-based rules to detect performance anti-patterns
and inefficient code patterns that can cause application bottlenecks.
"""

import ast
import re
from typing import List, Dict, Any


def find_queries_in_loops(tree: Any) -> List[Dict[str, Any]]:
    """Find database queries executed inside loops (language-aware).
    
    This is one of the most common and costly performance bugs. Each query
    in a loop causes a network round-trip to the database, leading to N+1
    query problems that can severely degrade application performance.
    
    Detects:
    - Database operations inside for loops
    - Database operations inside while loops
    - Nested loops with queries (even worse performance impact)
    
    Supports:
    - Python (native ast.AST)
    - JavaScript/TypeScript (tree-sitter or regex fallback)
    
    Args:
        tree: Either a Python ast.AST object (legacy) or a wrapped AST dict from ast_parser.py
    
    Returns:
        List of findings with line, column, loop type, and suggested fix
    """
    # Handle both legacy (direct ast.AST) and new wrapped format
    if isinstance(tree, ast.AST):
        # Legacy format - direct Python AST
        return _find_queries_in_loops_python(tree)
    elif isinstance(tree, dict):
        # New wrapped format from ast_parser.py
        tree_type = tree.get("type")
        language = tree.get("language", "")  # Empty not unknown
        
        if tree_type == "python_ast":
            return _find_queries_in_loops_python(tree["tree"])
        elif tree_type == "tree_sitter":
            return _find_queries_in_loops_tree_sitter(tree)
        elif tree_type == "regex_ast":
            return _find_queries_in_loops_regex_ast(tree)
        else:
            # Unknown tree type
            return []
    else:
        # Unknown format
        return []


def _find_queries_in_loops_python(tree: ast.AST) -> List[Dict[str, Any]]:
    """Find database queries executed inside loops in Python AST (original implementation).
    
    This is the original Python-specific implementation.
    """
    findings = []
    
    # Database operation indicators - function names that suggest DB operations
    db_operations = {
        # Generic database operations
        'query', 'execute', 'fetch', 'fetchone', 'fetchall', 'fetchmany',
        'select', 'insert', 'update', 'delete', 'find', 'find_one', 'find_all',
        
        # ORM operations (SQLAlchemy, Django ORM, etc.)
        'filter', 'filter_by', 'get', 'all', 'first', 'one', 'one_or_none',
        'count', 'exists', 'scalar', 'save', 'create', 'update_or_create',
        'get_or_create', 'bulk_create', 'bulk_update',
        
        # MongoDB operations
        'find_one', 'find_one_and_update', 'find_one_and_delete',
        'insert_one', 'insert_many', 'update_one', 'update_many',
        'delete_one', 'delete_many', 'aggregate',
        
        # Redis operations
        'get', 'set', 'hget', 'hset', 'lpush', 'rpush', 'sadd', 'zadd',
        
        # Elasticsearch operations
        'search', 'index', 'get', 'update', 'delete',
        
        # Raw SQL execution
        'execute', 'executemany', 'executescript',
    }
    
    # Helper function to check if a node contains database operations
    def contains_db_operation(node: ast.AST, loop_depth: int = 0) -> List[Dict[str, Any]]:
        """Recursively check if a node contains database operations."""
        local_findings = []
        
        # Database context indicators that suggest actual DB operations
        db_context_keywords = [
            'db.', 'database.', 'session.', 'cursor.', 
            'query(', 'session(', 'engine.', 'connection.',
            'model.', 'orm.', 'sql', '.execute(',
            'mongo', 'redis', 'elastic', 'postgres', 'mysql',
            '_db.', 'db_', 'database_', '.commit(', '.rollback('
        ]
        
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                # Check for method calls (e.g., cursor.execute())
                if isinstance(child.func, ast.Attribute):
                    method_name = child.func.attr.lower()
                    if method_name in db_operations:
                        # Secondary validation: check for database context
                        try:
                            # Get the source code of the call node
                            call_source = ast.unparse(child).lower()
                            
                            # Check if the source contains database context keywords
                            has_db_context = any(keyword in call_source for keyword in db_context_keywords)
                            
                            # Special check for MongoDB-style calls (e.g., collection.find_one())
                            if not has_db_context and method_name in ['find_one', 'find_one_and_update', 
                                                                       'update_one', 'update_many', 
                                                                       'delete_one', 'delete_many']:
                                # These are very likely MongoDB operations
                                has_db_context = True
                            
                            if has_db_context:
                                # Try to get the full operation name from the call source
                                # Extract the part before the final parenthesis
                                operation_name = call_source.rstrip(')')
                                # If it's too long, try to get a shorter version
                                if len(operation_name) > 50:
                                    # Try to get the object being called
                                    obj_name = "db_object"
                                    if isinstance(child.func.value, ast.Name):
                                        obj_name = child.func.value.id
                                    elif isinstance(child.func.value, ast.Attribute):
                                        # For chained calls, try to get the base object
                                        base = child.func.value
                                        while isinstance(base, ast.Attribute):
                                            base = base.value
                                        if isinstance(base, ast.Name):
                                            obj_name = base.id
                                    operation_name = f"{obj_name}.{method_name}"
                                else:
                                    # Use the full call for short operations
                                    operation_name = operation_name.split('(')[0]
                                
                                local_findings.append({
                                    'line': getattr(child, 'lineno', 0),
                                    'column': getattr(child, 'col_offset', 0),
                                    'operation': f"{operation_name}()",
                                    'loop_depth': loop_depth,
                                })
                        except (AttributeError, TypeError):
                            # If ast.unparse fails (Python < 3.9), fall back to checking object name
                            obj_name = "unknown"
                            if isinstance(child.func.value, ast.Name):
                                obj_name = child.func.value.id.lower()
                                # Check if object name suggests database context
                                if any(keyword in obj_name for keyword in ['db', 'database', 'session', 'cursor', 
                                                                            'conn', 'query', 'model', 'engine']):
                                    local_findings.append({
                                        'line': getattr(child, 'lineno', 0),
                                        'column': getattr(child, 'col_offset', 0),
                                        'operation': f"{obj_name}.{method_name}()",
                                        'loop_depth': loop_depth,
                                    })
                            elif isinstance(child.func.value, ast.Attribute):
                                # Handle chained calls like db.session.query()
                                # Try to get the base object
                                base = child.func.value
                                parts = [method_name]
                                while isinstance(base, ast.Attribute):
                                    parts.append(base.attr)
                                    base = base.value
                                if isinstance(base, ast.Name):
                                    base_name = base.id.lower()
                                    full_chain = f"{base_name}.{'.'.join(reversed(parts))}"
                                    # Check if the chain suggests database context
                                    if any(keyword in base_name for keyword in ['db', 'database', 'session', 
                                                                                 'cursor', 'conn', 'engine']):
                                        local_findings.append({
                                            'line': getattr(child, 'lineno', 0),
                                            'column': getattr(child, 'col_offset', 0),
                                            'operation': f"{full_chain}()",
                                            'loop_depth': loop_depth,
                                        })
                
                # Check for function calls (e.g., query())
                elif isinstance(child.func, ast.Name):
                    func_name = child.func.id.lower()
                    if func_name in db_operations:
                        # Secondary validation: check for database context
                        try:
                            # Get the source code of the call node
                            call_source = ast.unparse(child).lower()
                            
                            # Check if the source contains database context keywords
                            has_db_context = any(keyword in call_source for keyword in db_context_keywords)
                            
                            if has_db_context:
                                local_findings.append({
                                    'line': getattr(child, 'lineno', 0),
                                    'column': getattr(child, 'col_offset', 0),
                                    'operation': f"{func_name}()",
                                    'loop_depth': loop_depth,
                                })
                        except (AttributeError, TypeError):
                            # If ast.unparse fails (Python < 3.9), only flag obvious DB functions
                            if func_name in ['query', 'execute', 'fetch', 'fetchone', 'fetchall']:
                                local_findings.append({
                                    'line': getattr(child, 'lineno', 0),
                                    'column': getattr(child, 'col_offset', 0),
                                    'operation': f"{func_name}()",
                                    'loop_depth': loop_depth,
                                })
        
        return local_findings
    
    # Helper function to analyze loop bodies
    def analyze_loop_body(body: List[ast.AST], loop_type: str, loop_line: int, 
                          loop_depth: int = 0) -> None:
        """Analyze the body of a loop for database operations."""
        for node in body:
            # Check for nested loops (even worse performance)
            if isinstance(node, (ast.For, ast.While)):
                nested_loop_type = "for" if isinstance(node, ast.For) else "while"
                analyze_loop_body(
                    node.body if isinstance(node, ast.For) else node.body,
                    nested_loop_type,
                    getattr(node, 'lineno', 0),
                    loop_depth + 1
                )
            
            # Check for database operations
            db_ops = contains_db_operation(node, loop_depth)
            for op in db_ops:
                # Determine severity based on loop depth
                if op['loop_depth'] > 0:
                    severity = 'CRITICAL'  # Nested loop with query
                    hint = 'CRITICAL: Query in nested loop! Extract queries outside all loops and use batch operations'
                else:
                    severity = 'HIGH'
                    hint = 'Move query outside loop. Consider using batch fetch or JOIN operations'
                
                # Create a descriptive snippet
                if op['loop_depth'] > 0:
                    snippet = f"Nested {loop_type} loop (depth {op['loop_depth']+1}) with {op['operation']}"
                else:
                    snippet = f"{loop_type} loop with {op['operation']}"
                
                findings.append({
                    'line': op['line'],
                    'column': op.get('col', 0),
                    'loop_line': loop_line,
                    'loop_type': loop_type,
                    'snippet': snippet,
                    'operation': op['operation'],
                    'severity': severity,
                    'confidence': 0.90,  # High confidence since we're matching specific patterns
                    'type': 'query_in_loop',
                    'hint': hint
                })
    
    # Walk the AST looking for loops
    for node in ast.walk(tree):
        if isinstance(node, ast.For):
            # Analyze for loop body
            analyze_loop_body(node.body, "for", getattr(node, 'lineno', 0))
        
        elif isinstance(node, ast.While):
            # Analyze while loop body
            analyze_loop_body(node.body, "while", getattr(node, 'lineno', 0))
        
        # Also check for comprehensions with database operations
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            # Check if the comprehension contains database operations
            for generator in node.generators:
                if isinstance(generator.iter, ast.Call):
                    # Check if the iterator is a database operation
                    if isinstance(generator.iter.func, ast.Attribute):
                        method_name = generator.iter.func.attr.lower()
                        if method_name in db_operations:
                            findings.append({
                                'line': getattr(node, 'lineno', 0),
                                'column': getattr(node, 'col_offset', 0),
                                'loop_line': getattr(node, 'lineno', 0),
                                'loop_type': 'comprehension',
                                'snippet': f"Comprehension with {method_name}()",
                                'operation': method_name,
                                'severity': 'HIGH',
                                'confidence': 0.85,
                                'type': 'query_in_loop',
                                'hint': 'Comprehensions with DB queries create hidden loops. Fetch data first, then process'
                            })
    
    return findings


def _find_queries_in_loops_tree_sitter(tree_wrapper: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Find database queries executed inside loops in JavaScript/TypeScript using tree-sitter AST.
    
    Uses tree-sitter queries to find loops and database operations within them.
    """
    findings = []
    
    # Database operation indicators for JavaScript/TypeScript
    db_operations = {
        # Generic database operations
        'query', 'execute', 'exec', 'fetch', 'find', 'findOne', 'findMany',
        'select', 'insert', 'update', 'delete', 'create', 'save',
        
        # ORM operations (Sequelize, TypeORM, Prisma, etc.)
        'findAll', 'findByPk', 'findOrCreate', 'findAndCountAll',
        'findUnique', 'findFirst', 'findMany', 'create', 'createMany',
        'update', 'updateMany', 'upsert', 'delete', 'deleteMany',
        'count', 'aggregate', 'groupBy',
        
        # MongoDB operations
        'find', 'findOne', 'findOneAndUpdate', 'findOneAndDelete',
        'insertOne', 'insertMany', 'updateOne', 'updateMany',
        'deleteOne', 'deleteMany', 'aggregate', 'countDocuments',
        
        # Redis operations
        'get', 'set', 'hget', 'hset', 'lpush', 'rpush', 'sadd', 'zadd',
        'mget', 'mset', 'hmget', 'hmset',
        
        # SQL query builders
        'where', 'join', 'leftJoin', 'rightJoin', 'innerJoin',
        'orderBy', 'groupBy', 'having', 'limit', 'offset',
        
        # Knex.js methods
        'from', 'into', 'returning', 'pluck', 'first',
    }
    
    # Database context indicators for JavaScript
    db_context_keywords = [
        'db.', 'database.', 'sql.', 'knex.', 'prisma.', 'sequelize.',
        'model.', 'models.', 'mongoose.', 'typeorm.', 'redis.', 'cache.',
        'query(', 'execute(', '.query(', '.exec(', '.execute(',
        'mongodb', 'postgres', 'mysql', 'sqlite', 'mssql',
        'collection.', 'repository.', 'entityManager.', 'queryBuilder.',
        '.save(', '.find(', '.create(', '.update(', '.delete(',
    ]
    
    tree = tree_wrapper.get("tree")
    content = tree_wrapper.get("content", "")
    language = tree_wrapper.get("language", "javascript")
    
    if not tree:
        return findings
    
    # Try to use tree-sitter for proper traversal
    try:
        # Import tree-sitter dynamically
        import tree_sitter
        from tree_sitter_language_pack import get_language
        
        lang = get_language(language)
        
        # Query for loop constructs
        loop_query = lang.query("""
            [
                (for_statement) @for_loop
                (for_in_statement) @for_in_loop
                (for_of_statement) @for_of_loop
                (while_statement) @while_loop
                (do_statement) @do_while_loop
            ]
        """)
        
        # Query for call expressions (to find DB operations)
        call_query = lang.query("""
            (call_expression) @call
        """)
        
        # Process each loop
        for loop_capture in loop_query.captures(tree.root_node):
            loop_node, loop_type = loop_capture
            loop_line = loop_node.start_point[0] + 1
            
            # Determine loop type for reporting
            if "for_in" in loop_type:
                loop_type_str = "for...in"
            elif "for_of" in loop_type:
                loop_type_str = "for...of"
            elif "while" in loop_type:
                loop_type_str = "while"
            elif "do" in loop_type:
                loop_type_str = "do...while"
            else:
                loop_type_str = "for"
            
            # Find all call expressions within this loop
            for call_capture in call_query.captures(loop_node):
                call_node, _ = call_capture
                
                # Check if call is within the loop's range
                if (call_node.start_point[0] >= loop_node.start_point[0] and 
                    call_node.end_point[0] <= loop_node.end_point[0]):
                    
                    # Extract the call text
                    call_text = call_node.text.decode("utf-8", errors="ignore")
                    call_text_lower = call_text.lower()
                    
                    # Check if this looks like a database operation
                    is_db_operation = False
                    matched_operation = None
                    
                    # Check for method names that match DB operations
                    for op in db_operations:
                        if f".{op.lower()}(" in call_text_lower or f" {op.lower()}(" in call_text_lower:
                            # Secondary validation: check for database context
                            has_db_context = any(keyword in call_text_lower for keyword in db_context_keywords)
                            
                            # Special check for common ORM patterns
                            if not has_db_context and op in ['find', 'findOne', 'save', 'create', 
                                                             'update', 'delete', 'count']:
                                # Check if preceded by model/collection name pattern
                                if re.search(r'\b(user|post|comment|order|product|model|collection|repository)\s*\.\s*' + op, 
                                           call_text_lower, re.IGNORECASE):
                                    has_db_context = True
                            
                            if has_db_context:
                                is_db_operation = True
                                matched_operation = op
                                break
                    
                    if is_db_operation:
                        # Get the operation name for reporting
                        operation_name = call_text.split('(')[0].strip()
                        if len(operation_name) > 50:
                            operation_name = f"...{operation_name[-47:]}"
                        
                        # Check for nested loops (by checking if there's another loop between this and parent)
                        loop_depth = 0
                        parent = loop_node.parent
                        while parent:
                            if parent.type in ["for_statement", "for_in_statement", "for_of_statement", 
                                              "while_statement", "do_statement"]:
                                loop_depth += 1
                            parent = parent.parent
                        
                        # Determine severity
                        if loop_depth > 0:
                            severity = 'CRITICAL'
                            hint = 'CRITICAL: Query in nested loop! Extract queries outside all loops and use batch operations'
                        else:
                            severity = 'HIGH'
                            hint = 'Move query outside loop. Consider using batch fetch or JOIN operations'
                        
                        # Create snippet
                        if loop_depth > 0:
                            snippet = f"Nested {loop_type_str} loop (depth {loop_depth+1}) with {operation_name}()"
                        else:
                            snippet = f"{loop_type_str} loop with {operation_name}()"
                        
                        findings.append({
                            'line': call_node.start_point[0] + 1,
                            'column': call_node.start_point[1],
                            'loop_line': loop_line,
                            'loop_type': loop_type_str,
                            'snippet': snippet,
                            'operation': f"{operation_name}()",
                            'severity': severity,
                            'confidence': 0.90,
                            'type': 'query_in_loop',
                            'hint': hint
                        })
        
        # Also check for array methods with DB operations (forEach, map, etc.)
        array_method_query = lang.query("""
            (call_expression
              function: (member_expression
                property: (property_identifier) @method)
              arguments: (arguments
                (arrow_function) @callback))
        """)
        
        for capture in array_method_query.captures(tree.root_node):
            node, capture_name = capture
            
            if capture_name == "method":
                method_name = node.text.decode("utf-8", errors="ignore")
                if method_name in ["forEach", "map", "filter", "reduce", "some", "every", "find"]:
                    # Get the callback function node
                    parent_call = node.parent.parent
                    
                    # Look for DB operations within the callback
                    for call_capture in call_query.captures(parent_call):
                        call_node, _ = call_capture
                        call_text = call_node.text.decode("utf-8", errors="ignore")
                        call_text_lower = call_text.lower()
                        
                        # Check if this is a DB operation
                        for op in db_operations:
                            if f".{op.lower()}(" in call_text_lower:
                                has_db_context = any(keyword in call_text_lower for keyword in db_context_keywords)
                                
                                if has_db_context:
                                    operation_name = call_text.split('(')[0].strip()
                                    if len(operation_name) > 50:
                                        operation_name = f"...{operation_name[-47:]}"
                                    
                                    findings.append({
                                        'line': call_node.start_point[0] + 1,
                                        'column': call_node.start_point[1],
                                        'loop_line': node.start_point[0] + 1,
                                        'loop_type': f'array.{method_name}',
                                        'snippet': f"Array {method_name} with {operation_name}()",
                                        'operation': f"{operation_name}()",
                                        'severity': 'HIGH',
                                        'confidence': 0.85,
                                        'type': 'query_in_loop',
                                        'hint': f'Array {method_name} creates implicit loop. Fetch data first, then process'
                                    })
                                    break
    
    except (ImportError, Exception):
        # Tree-sitter not available or query failed, fall back to regex_ast logic
        return _find_queries_in_loops_regex_ast(tree_wrapper)
    
    return findings


def _find_queries_in_loops_regex_ast(tree_wrapper: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Find database queries in loops using regex-based fallback AST.
    
    This is used when tree-sitter is not available for JavaScript/TypeScript.
    """
    findings = []
    
    # Database operation indicators for JavaScript
    db_operations = [
        'query', 'execute', 'exec', 'fetch', 'find', 'findOne', 'findMany',
        'select', 'insert', 'update', 'delete', 'create', 'save',
        'findAll', 'findByPk', 'findOrCreate', 'findUnique', 'findFirst',
        'updateMany', 'deleteMany', 'count', 'aggregate',
        'insertOne', 'insertMany', 'updateOne', 'updateMany',
        'deleteOne', 'deleteMany', 'countDocuments',
    ]
    
    # Database context indicators
    db_context_keywords = [
        'db', 'database', 'sql', 'knex', 'prisma', 'sequelize',
        'model', 'mongoose', 'typeorm', 'redis', 'cache',
        'mongodb', 'postgres', 'mysql', 'sqlite',
        'collection', 'repository', 'entityManager', 'queryBuilder'
    ]
    
    content = tree_wrapper.get("content", "")
    
    if not content:
        return findings
    
    lines = content.split('\n')
    
    # Track loop boundaries (simplified)
    loop_stack = []  # Stack of (loop_type, line_start, line_end)
    
    # First pass: identify loop boundaries
    for line_num, line in enumerate(lines, 1):
        line_stripped = line.strip()
        
        # Detect loop starts
        if re.match(r'^\s*(for|while|do)\s*\(', line_stripped):
            # Simple heuristic: assume loop body starts on next line
            if 'for' in line_stripped:
                loop_type = 'for'
            elif 'while' in line_stripped:
                loop_type = 'while'
            else:
                loop_type = 'do...while'
            
            loop_stack.append((loop_type, line_num, None))
        
        # Detect array method loops
        elif re.search(r'\.(forEach|map|filter|reduce|some|every)\s*\(', line_stripped):
            match = re.search(r'\.(\w+)\s*\(', line_stripped)
            if match:
                method_name = match.group(1)
                loop_stack.append((f'array.{method_name}', line_num, None))
    
    # Second pass: find database operations and check if they're in loops
    for line_num, line in enumerate(lines, 1):
        # Look for database operations
        for op in db_operations:
            # Pattern to match method calls
            pattern = r'\.(' + re.escape(op) + r')\s*\('
            match = re.search(pattern, line, re.IGNORECASE)
            
            if match:
                # Check for database context
                line_lower = line.lower()
                has_db_context = any(keyword in line_lower for keyword in db_context_keywords)
                
                # Additional check: if the line contains common model names
                if not has_db_context:
                    if re.search(r'\b(user|post|comment|order|product|item|customer)\s*\.', line_lower):
                        has_db_context = True
                
                if has_db_context:
                    # Check if we're inside a loop
                    in_loop = False
                    loop_info = None
                    
                    # Simple heuristic: check if line is after any loop start in stack
                    for loop_type, loop_start, _ in loop_stack:
                        if line_num > loop_start:
                            in_loop = True
                            loop_info = (loop_type, loop_start)
                            break
                    
                    if in_loop:
                        operation_name = f"{match.group(1)}"
                        
                        # Check if nested (multiple loops in stack at this line)
                        nested_count = sum(1 for lt, ls, _ in loop_stack if line_num > ls)
                        
                        if nested_count > 1:
                            severity = 'CRITICAL'
                            hint = 'CRITICAL: Query in nested loop! Extract queries outside all loops'
                            snippet = f"Nested {loop_info[0]} loop (depth {nested_count}) with {operation_name}()"
                        else:
                            severity = 'HIGH'
                            hint = 'Move query outside loop. Consider batch operations'
                            snippet = f"{loop_info[0]} loop with {operation_name}()"
                        
                        findings.append({
                            'line': line_num,
                            'column': match.start(),
                            'loop_line': loop_info[1],
                            'loop_type': loop_info[0],
                            'snippet': snippet,
                            'operation': f"{operation_name}()",
                            'severity': severity,
                            'confidence': 0.75,  # Lower confidence for regex-based detection
                            'type': 'query_in_loop',
                            'hint': hint
                        })
                        break  # Only report once per line
    
    return findings


def find_inefficient_string_concatenation(tree: ast.AST) -> List[Dict[str, Any]]:
    """Find inefficient string concatenation in loops.
    
    String concatenation with + in loops is O(n²) complexity because
    strings are immutable in Python. Each concatenation creates a new
    string object.
    
    Returns:
        List of findings with suggestions to use join() or list append
    """
    findings = []
    
    # Walk the AST looking for loops
    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.While)):
            # Check loop body for string concatenation
            for body_node in ast.walk(node):
                if isinstance(body_node, ast.AugAssign):
                    # Check for += operation
                    if isinstance(body_node.op, ast.Add):
                        # Check if target might be a string
                        if isinstance(body_node.target, ast.Name):
                            var_name = body_node.target.id
                            
                            # Look for string indicators
                            if isinstance(body_node.value, (ast.Constant, ast.Str)):
                                # This is likely string concatenation
                                loop_type = "for" if isinstance(node, ast.For) else "while"
                                
                                findings.append({
                                    'line': getattr(body_node, 'lineno', 0),
                                    'column': getattr(body_node, 'col_offset', 0),
                                    'variable': var_name,
                                    'snippet': f"{var_name} += ... in {loop_type} loop",
                                    'severity': 'MEDIUM',
                                    'confidence': 0.80,
                                    'type': 'inefficient_string_concat',
                                    'hint': 'Use list.append() in loop, then "".join(list) after loop for O(n) performance'
                                })
    
    return findings


def find_expensive_operations_in_loops(tree: ast.AST) -> List[Dict[str, Any]]:
    """Find expensive operations that should be moved outside loops.
    
    Detects:
    - File I/O operations in loops
    - Network requests in loops
    - Regular expression compilation in loops
    - Heavy computations that could be cached
    
    Returns:
        List of findings with optimization suggestions
    """
    findings = []
    
    # Expensive operation indicators
    expensive_operations = {
        # File I/O
        'open', 'read', 'write', 'close',
        'readlines', 'writelines', 'readline',
        
        # Network operations
        'urlopen', 'urlretrieve', 'get', 'post', 'put', 'delete', 'patch',
        'request', 'send', 'recv', 'connect',
        
        # Regular expressions
        'compile', 're.compile',
        
        # Expensive computations
        'sleep', 'time.sleep',
        'sort', 'sorted',  # If called repeatedly on same data
    }
    
    # Walk the AST looking for loops
    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.While)):
            loop_type = "for" if isinstance(node, ast.For) else "while"
            loop_line = getattr(node, 'lineno', 0)
            
            # Check loop body for expensive operations
            for body_node in ast.walk(node):
                if isinstance(body_node, ast.Call):
                    operation = None
                    severity = 'HIGH'
                    hint = ''
                    
                    # Check for function calls
                    if isinstance(body_node.func, ast.Name):
                        func_name = body_node.func.id
                        if func_name in expensive_operations:
                            operation = f"{func_name}()"
                            
                            if func_name == 'open':
                                hint = 'File operations in loops are expensive. Consider batch processing or caching'
                            elif func_name in ['compile', 're.compile']:
                                hint = 'Compile regex once outside the loop and reuse'
                            elif func_name in ['sleep', 'time.sleep']:
                                severity = 'CRITICAL'
                                hint = 'Sleep in loop blocks execution. Consider async/await or event-driven approach'
                            else:
                                hint = 'Move expensive operation outside loop or cache results'
                    
                    # Check for method calls
                    elif isinstance(body_node.func, ast.Attribute):
                        method_name = body_node.func.attr
                        if method_name in expensive_operations:
                            obj_name = "object"
                            if isinstance(body_node.func.value, ast.Name):
                                obj_name = body_node.func.value.id
                            
                            operation = f"{obj_name}.{method_name}()"
                            
                            if method_name in ['get', 'post', 'put', 'delete', 'patch']:
                                severity = 'CRITICAL'
                                hint = 'HTTP requests in loops cause severe performance issues. Use batch APIs or async requests'
                            else:
                                hint = 'Consider moving operation outside loop or using batch processing'
                    
                    if operation:
                        findings.append({
                            'line': getattr(body_node, 'lineno', 0),
                            'column': getattr(body_node, 'col_offset', 0),
                            'loop_line': loop_line,
                            'loop_type': loop_type,
                            'snippet': f"{operation} in {loop_type} loop",
                            'operation': operation,
                            'severity': severity,
                            'confidence': 0.85,
                            'type': 'expensive_operation_in_loop',
                            'hint': hint
                        })
    
    return findings