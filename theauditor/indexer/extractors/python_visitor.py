"""Unified Python AST Visitor - Single-Pass Extraction Engine.

ARCHITECTURE: Visitor Pattern (2025 Modernization)
====================================================

This module replaces the sequential multi-pass extraction approach with a single
AST traversal. Instead of calling 100+ extractor functions that each walk the tree,
we visit each node ONCE and extract all relevant patterns simultaneously.

PERFORMANCE IMPACT:
- BEFORE: 100 separate ast.walk() calls per file = 100N node visits
- AFTER: 1 ast.NodeVisitor.visit() call per file = N node visits
- Expected speedup: ~100x for extraction phase

DESIGN PRINCIPLES:
1. Single Pass: Tree traversed exactly once
2. Type Safe: Dataclasses for internal state (not dict soup)
3. Domain Focused: Organize by concept (Route, Model, Task) not table
4. AST Pure: No text parsing, no regex extraction
5. Fail Loud: No try/except swallowing (ZERO FALLBACK policy)

DATA FLOW:
    AST Tree → UnifiedPythonVisitor.visit() → State Buckets → Adapter → Database

The visitor populates "state buckets" (definitions, calls, imports, issues).
The adapter layer (in python.py) maps these to the 150+ legacy table schemas
during Phase 2 transition. Once all consumers migrate, we can simplify the schema.
"""
from __future__ import annotations


import ast
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field


@dataclass
class AnalysisContext:
    """Tracks current position in the AST for scope-aware extraction.

    Maintains a stack of scopes (function/class names) to provide accurate
    'in_function' and 'in_class' metadata for extracted patterns.

    Example scope progression:
        global → MyClass → MyClass.my_method
    """
    scope_stack: list[str] = field(default_factory=list)
    current_class: str | None = None

    @property
    def current_scope_name(self) -> str:
        """Get current scope as dot-separated string."""
        return ".".join(self.scope_stack) if self.scope_stack else "global"

    @property
    def current_function(self) -> str | None:
        """Get innermost function name (for 'in_function' field)."""
        # Return last scope item if it's a function (not a class)
        if self.scope_stack:
            last_scope = self.scope_stack[-1]
            # Simple heuristic: if current_class exists and scope contains it,
            # the last part is a method name
            if self.current_class and self.current_class in self.scope_stack:
                return last_scope
            # Otherwise, if scope_stack has items and we're not in a class,
            # it's a function
            elif not self.current_class:
                return last_scope
        return None


class UnifiedPythonVisitor(ast.NodeVisitor):
    """The 2025 Single-Pass Extraction Engine.

    Replaces 100+ sequential extractor calls with a single AST traversal.
    Organizes extraction by domain (routes, models, tasks) instead of by table.

    USAGE:
        visitor = UnifiedPythonVisitor(file_path)
        visitor.visit(tree)
        results = visitor.get_results()

    INTERNAL STATE:
        - definitions: Functions, classes, methods
        - calls: Function call sites
        - imports: Import statements
        - issues: Security findings (SQLi, command injection, etc.)

    DOMAIN DETECTORS:
        - _is_route(): Flask/FastAPI/Django route detection
        - _is_task(): Celery task detection
        - _is_orm_model(): SQLAlchemy/Django ORM model detection
        - _check_security_sinks(): SQL injection, command injection, etc.
    """

    def __init__(self, file_path: str):
        """Initialize visitor with file context.

        Args:
            file_path: Absolute path to Python file being analyzed
        """
        self.file_path = file_path
        self.context = AnalysisContext()

        # =================================================================
        # STATE BUCKETS - The Output
        # =================================================================
        # These map to domain concepts, not specific database tables.
        # The adapter layer (in python.py) will map these to legacy schemas.

        self.definitions: list[dict[str, Any]] = []  # Classes, functions, methods
        self.calls: list[dict[str, Any]] = []        # Function calls
        self.imports: list[dict[str, Any]] = []      # Import statements
        self.issues: list[dict[str, Any]] = []       # Security findings

        # =================================================================
        # DOMAIN DETECTORS - Pre-compiled Pattern Sets
        # =================================================================
        # Compiled once at init for O(1) lookups during traversal.

        # Route decorators (Flask, FastAPI, Django)
        self._route_decorators: set[str] = {
            'route', 'get', 'post', 'put', 'delete', 'patch', 'head', 'options',
            'api_route',  # FastAPI
        }

        # Task decorators (Celery)
        self._task_decorators: set[str] = {
            'task', 'shared_task', 'periodic_task'
        }

        # Auth/permission decorators
        self._auth_decorators: set[str] = {
            'login_required', 'auth_required', 'permission_required',
            'require_auth', 'authenticated', 'authorize', 'requires_auth',
            'jwt_required', 'token_required', 'verify_jwt', 'check_auth'
        }

        # ORM base classes
        self._orm_bases: set[str] = {
            'Model', 'Base', 'db.Model', 'models.Model'  # SQLAlchemy, Django
        }

        # SQL execution methods (for injection detection)
        self._sql_methods: set[str] = {
            'execute', 'executemany', 'exec_driver_sql', 'raw', 'query'
        }

        # Command execution functions (for injection detection)
        self._command_functions: set[str] = {
            'system', 'popen', 'exec', 'eval', 'run', 'call', 'check_output'
        }

    # =================================================================
    # VISITOR METHODS - Called by ast.NodeVisitor
    # =================================================================

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Extract function definitions and detect domain patterns (routes, tasks, tests).

        This single visit replaces:
        - framework_extractors.extract_routes()
        - framework_extractors.extract_celery_tasks()
        - framework_extractors.extract_pytest_fixtures()
        - ... 10+ other function-level extractors
        """
        self.context.scope_stack.append(node.name)

        # 1. BASE DEFINITION
        # Extract fundamental function info (applies to all functions)
        func_def = {
            "type": "function",
            "name": node.name,
            "line": node.lineno,
            "scope": self.context.current_scope_name,
            "is_async": isinstance(node, ast.AsyncFunctionDef),
            "decorators": [self._get_decorator_name(d) for d in node.decorator_list],
            "file": self.file_path,
        }

        # 2. DOMAIN CHECKS
        # Instead of calling 10 external functions, check attributes right here.

        # Check: Is this a Flask/FastAPI/Django route?
        if self._is_route(node):
            func_def["is_route"] = True
            func_def["route_meta"] = self._extract_route_meta(node)

        # Check: Is this a Celery task?
        if self._is_task(node):
            func_def["is_task"] = True
            func_def["task_meta"] = self._extract_task_meta(node)

        # Check: Is this a pytest fixture/test?
        if self._is_test(node):
            func_def["is_test"] = True
            func_def["test_meta"] = self._extract_test_meta(node)

        # Check: Does this have auth decorators?
        if self._has_auth(node):
            func_def["has_auth"] = True

        self.definitions.append(func_def)

        # 3. CONTINUE TRAVERSAL
        # Visit child nodes (function body)
        self.generic_visit(node)

        # 4. RESTORE CONTEXT
        self.context.scope_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Async functions use same logic as regular functions."""
        self.visit_FunctionDef(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        """Extract class definitions and detect ORM models, validators, etc.

        This single visit replaces:
        - framework_extractors.extract_orm_models()
        - framework_extractors.extract_pydantic_validators()
        - framework_extractors.extract_django_forms()
        - ... 10+ other class-level extractors
        """
        self.context.current_class = node.name
        self.context.scope_stack.append(node.name)

        # 1. BASE DEFINITION
        class_def = {
            "type": "class",
            "name": node.name,
            "line": node.lineno,
            "scope": self.context.current_scope_name,
            "bases": [self._get_name(b) for b in node.bases],
            "decorators": [self._get_decorator_name(d) for d in node.decorator_list],
            "file": self.file_path,
        }

        # 2. DOMAIN CHECKS

        # Check: Is this a Django/SQLAlchemy ORM model?
        if self._is_orm_model(node):
            class_def["is_orm_model"] = True
            class_def["orm_meta"] = self._extract_orm_meta(node)

        # Check: Is this a Pydantic validator?
        if self._is_pydantic_model(node):
            class_def["is_validator"] = True

        # Check: Is this a dataclass?
        if self._is_dataclass(node):
            class_def["is_dataclass"] = True

        self.definitions.append(class_def)

        # 3. CONTINUE TRAVERSAL
        self.generic_visit(node)

        # 4. RESTORE CONTEXT
        self.context.scope_stack.pop()
        self.context.current_class = None

    def visit_Call(self, node: ast.Call):
        """Extract function calls and detect security sinks (SQLi, command injection).

        This single visit replaces:
        - ast_parser.extract_calls()
        - security_extractors.extract_sql_injection()
        - security_extractors.extract_command_injection()
        - ... 10+ other call-site extractors
        """
        # 1. EXTRACT CALL
        func_name = self._get_name(node.func)
        if func_name:
            call_record = {
                "name": func_name,
                "line": node.lineno,
                "scope": self.context.current_scope_name,
                "in_function": self.context.current_function or "global",
                "file": self.file_path,
            }
            self.calls.append(call_record)

            # 2. SECURITY CHECKS (Sinks)
            # Check for SQL injection patterns
            if self._is_sql_call(func_name):
                sql_issue = self._check_sql_injection(node, func_name)
                if sql_issue:
                    self.issues.append(sql_issue)

            # Check for command injection patterns
            if self._is_command_call(func_name):
                cmd_issue = self._check_command_injection(node, func_name)
                if cmd_issue:
                    self.issues.append(cmd_issue)

        # 3. CONTINUE TRAVERSAL
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import):
        """Extract import statements."""
        for alias in node.names:
            self.imports.append({
                "type": "import",
                "module": alias.name,
                "alias": alias.asname,
                "line": node.lineno,
                "file": self.file_path,
            })
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Extract from...import statements."""
        for alias in node.names:
            self.imports.append({
                "type": "from",
                "module": node.module or "",
                "name": alias.name,
                "alias": alias.asname,
                "level": node.level,
                "line": node.lineno,
                "file": self.file_path,
            })
        self.generic_visit(node)

    # =================================================================
    # HELPER METHODS - Pure Logic, No Side Effects
    # =================================================================

    def _get_name(self, node: Any) -> str | None:
        """Safely extract name from AST node.

        Handles:
        - ast.Name: variable name
        - ast.Attribute: obj.attr chains
        - ast.Call: function calls (recurse to func)
        """
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            base = self._get_name(node.value)
            if base:
                return f"{base}.{node.attr}"
            return node.attr
        elif isinstance(node, ast.Call):
            return self._get_name(node.func)
        return None

    def _get_decorator_name(self, node: Any) -> str | None:
        """Extract decorator name from decorator node.

        Handles:
        - @decorator
        - @decorator()
        - @obj.decorator
        - @obj.decorator()
        """
        if isinstance(node, ast.Call):
            return self._get_name(node.func)
        return self._get_name(node)

    # =================================================================
    # DOMAIN DETECTORS - Pattern Recognition
    # =================================================================

    def _is_route(self, node: ast.FunctionDef) -> bool:
        """Check if function has route decorators (Flask/FastAPI/Django)."""
        for decorator in node.decorator_list:
            name = self._get_decorator_name(decorator)
            if name:
                # Handle @app.route, @router.get, @api.post
                decorator_suffix = name.split('.')[-1]
                if decorator_suffix in self._route_decorators:
                    return True
        return False

    def _extract_route_meta(self, node: ast.FunctionDef) -> dict[str, Any]:
        """Extract route metadata (HTTP method, URL pattern, framework, dependencies).

        Analyzes decorators to identify:
        - Flask: @app.route('/path', methods=['POST'])
        - FastAPI: @app.get('/path'), @router.post('/path')
        - Blueprint: @bp.route('/path')
        - Dependencies: FastAPI Depends() in function parameters

        Args:
            node: FunctionDef node representing the route handler

        Returns:
            Dict with keys: pattern, method, framework, blueprint, dependencies

        Example Flask:
            @app.route('/users/<id>', methods=['GET', 'POST'])
            def get_user(id):
                ...
            → {"pattern": "/users/<id>", "method": "GET", "framework": "flask", "blueprint": "app"}

        Example FastAPI:
            @router.post('/users')
            async def create_user(db: Session = Depends(get_db)):
                ...
            → {"pattern": "/users", "method": "POST", "framework": "fastapi", "blueprint": "router", "dependencies": ["get_db"]}
        """
        method = "GET"
        pattern = ""
        framework = None
        blueprint_name = None
        dependencies = []

        # STEP 1: Scan decorators for route patterns
        for decorator in node.decorator_list:
            # Handle @app.route(), @app.get(), @router.post(), etc.
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                method_name = decorator.func.attr  # 'route', 'get', 'post', etc.
                owner_name = self._get_name(decorator.func.value)  # 'app', 'router', 'bp'

                # Check if this is a route decorator
                if method_name in self._route_decorators:
                    # Extract URL pattern from first positional argument
                    if decorator.args:
                        path_arg = decorator.args[0]
                        if isinstance(path_arg, ast.Constant):
                            pattern = str(path_arg.value)

                    # Determine HTTP method and framework
                    if method_name == 'route':
                        # Flask @app.route('/path', methods=['POST'])
                        framework = 'flask'
                        # Check methods= keyword argument
                        for keyword in decorator.keywords:
                            if keyword.arg == 'methods':
                                if isinstance(keyword.value, ast.List) and keyword.value.elts:
                                    first_method = keyword.value.elts[0]
                                    if isinstance(first_method, ast.Constant):
                                        method = str(first_method.value).upper()
                                    # Note: Only extract first method for simplicity
                                    # Multiple methods will create separate route records in adapter layer
                    else:
                        # FastAPI @app.get(), @router.post(), etc.
                        framework = 'fastapi'
                        method = method_name.upper()

                    blueprint_name = owner_name
                    break  # Found route decorator, stop scanning

        # STEP 2: Extract FastAPI dependencies (only if FastAPI route)
        if framework == 'fastapi':
            dependencies = self._extract_fastapi_dependencies(node)

        return {
            "pattern": pattern,
            "method": method,
            "framework": framework or "flask",  # Default to flask if unclear
            "blueprint": blueprint_name,
            "dependencies": dependencies,
        }

    def _extract_fastapi_dependencies(self, func_node: ast.FunctionDef) -> list[str]:
        """Extract dependency injection targets from FastAPI route function parameters.

        FastAPI routes use Depends() in default parameter values:
            def route(db: Session = Depends(get_db), user = Depends(get_user)):
                                       ^^^^^^^^^^^^^^^       ^^^^^^^^^^^^^^^^^

        Args:
            func_node: FunctionDef node representing a FastAPI route

        Returns:
            List of dependency target names (e.g., ["get_db", "get_user"])
        """
        dependencies = []

        def _extract_depends_target(call: ast.Call) -> str | None:
            """Extract target from Depends() call."""
            func_name = self._get_name(call.func)
            if not (func_name and func_name.endswith("Depends")):
                return None

            # Get dependency target from first positional arg
            if call.args:
                return self._get_name(call.args[0])

            # Or from dependency= keyword arg
            for keyword in call.keywords:
                if keyword.arg == "dependency":
                    return self._get_name(keyword.value)

            return "Depends"  # Bare Depends() with no target

        # Scan positional parameters with defaults
        args = func_node.args
        positional = list(args.args)
        defaults = list(args.defaults)
        defaults_start_idx = len(positional) - len(defaults)

        for idx, arg in enumerate(positional):
            if idx >= defaults_start_idx:
                default_value = defaults[idx - defaults_start_idx]
                if isinstance(default_value, ast.Call):
                    target = _extract_depends_target(default_value)
                    if target:
                        dependencies.append(target)

        # Scan keyword-only parameters
        for kw_arg, default_value in zip(args.kwonlyargs, args.kw_defaults):
            if isinstance(default_value, ast.Call):
                target = _extract_depends_target(default_value)
                if target:
                    dependencies.append(target)

        return dependencies

    def _is_task(self, node: ast.FunctionDef) -> bool:
        """Check if function is a Celery task."""
        for decorator in node.decorator_list:
            name = self._get_decorator_name(decorator)
            if name:
                decorator_suffix = name.split('.')[-1]
                if decorator_suffix in self._task_decorators:
                    return True
        return False

    def _extract_task_meta(self, node: ast.FunctionDef) -> dict[str, Any]:
        """Extract Celery task metadata."""
        return {}  # Placeholder

    def _is_test(self, node: ast.FunctionDef) -> bool:
        """Check if function is a test (pytest/unittest)."""
        # Test function naming convention
        if node.name.startswith('test_'):
            return True
        # Pytest fixture decorator
        for decorator in node.decorator_list:
            name = self._get_decorator_name(decorator)
            if name and 'fixture' in name:
                return True
        return False

    def _extract_test_meta(self, node: ast.FunctionDef) -> dict[str, Any]:
        """Extract test metadata (fixtures, parametrize, etc.)."""
        return {}  # Placeholder

    def _has_auth(self, node: ast.FunctionDef) -> bool:
        """Check if function has authentication decorators."""
        for decorator in node.decorator_list:
            name = self._get_decorator_name(decorator)
            if name:
                decorator_suffix = name.split('.')[-1]
                if decorator_suffix in self._auth_decorators:
                    return True
        return False

    def _is_orm_model(self, node: ast.ClassDef) -> bool:
        """Check if class inherits from ORM base (SQLAlchemy/Django)."""
        for base in node.bases:
            base_name = self._get_name(base)
            if base_name and base_name in self._orm_bases:
                return True
        return False

    def _extract_orm_meta(self, node: ast.ClassDef) -> dict[str, Any]:
        """Extract ORM metadata (table name, fields) from SQLAlchemy/Django models.

        Scans class body for:
        - __tablename__ attribute (table name)
        - Column() assignments (fields with types)
        - Primary keys and foreign keys

        Args:
            node: ClassDef node representing an ORM model

        Returns:
            Dict with keys: table_name, fields, orm_type

        Example SQLAlchemy:
            class User(Base):
                __tablename__ = 'users'
                id = Column(Integer, primary_key=True)
                name = Column(String(100))
            → {"table_name": "users", "fields": [...], "orm_type": "sqlalchemy"}

        Example Django:
            class User(models.Model):
                name = models.CharField(max_length=100)
            → {"table_name": "user", "fields": [...], "orm_type": "django"}
        """
        table_name = None
        fields = []
        orm_type = "sqlalchemy"  # Default assumption

        # STEP 1: Detect ORM type from base classes
        for base in node.bases:
            base_name = self._get_name(base)
            if base_name and 'django' in base_name.lower():
                orm_type = "django"
                break

        # STEP 2: Extract table name from __tablename__ attribute (SQLAlchemy)
        for stmt in node.body:
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name) and target.id == "__tablename__":
                        if isinstance(stmt.value, ast.Constant):
                            table_name = str(stmt.value.value)
                        break

        # STEP 3: Extract fields from Column() or models.* assignments
        for stmt in node.body:
            # Get attribute name (field name)
            attr_name = None
            value = None

            if isinstance(stmt, ast.Assign):
                # Regular assignment: id = Column(Integer)
                targets = [t for t in stmt.targets if isinstance(t, ast.Name)]
                if targets:
                    attr_name = targets[0].id
                    value = stmt.value
            elif isinstance(stmt, ast.AnnAssign):
                # Annotated assignment: id: int = Column(Integer)
                if isinstance(stmt.target, ast.Name):
                    attr_name = stmt.target.id
                    value = stmt.value

            # Skip if not a field assignment
            if not attr_name or not isinstance(value, ast.Call):
                continue

            # Skip private attributes and relationships
            if attr_name.startswith('_'):
                continue

            func_name = self._get_name(value.func)
            if not func_name:
                continue

            # STEP 4: Check if this is a Column() call (SQLAlchemy) or models.*Field (Django)
            is_column = func_name.endswith('Column')
            is_django_field = 'Field' in func_name and orm_type == 'django'
            is_relationship = func_name.endswith('relationship') or 'ForeignKey' in func_name or 'ManyToMany' in func_name

            # Skip relationship() calls - those are handled separately
            if is_relationship and func_name.endswith('relationship'):
                continue

            if is_column or is_django_field:
                # Extract field type from first positional argument
                field_type = None
                if value.args:
                    first_arg = value.args[0]
                    if isinstance(first_arg, ast.Constant):
                        field_type = str(first_arg.value)
                    elif isinstance(first_arg, ast.Name):
                        field_type = first_arg.id
                    elif isinstance(first_arg, ast.Attribute):
                        field_type = self._get_name(first_arg)
                    elif isinstance(first_arg, ast.Call):
                        # Handle String(100), Integer(), etc.
                        field_type = self._get_name(first_arg.func)

                # Detect primary key
                is_primary_key = False
                for keyword in value.keywords:
                    if keyword.arg == 'primary_key':
                        if isinstance(keyword.value, ast.Constant):
                            is_primary_key = bool(keyword.value.value)

                # Detect foreign key (from ForeignKey() in Column args)
                is_foreign_key = False
                foreign_key_target = None
                for arg in value.args:
                    if isinstance(arg, ast.Call):
                        fk_func_name = self._get_name(arg.func)
                        if fk_func_name and fk_func_name.endswith('ForeignKey'):
                            is_foreign_key = True
                            if arg.args:
                                if isinstance(arg.args[0], ast.Constant):
                                    foreign_key_target = str(arg.args[0].value)

                # Django-style ForeignKey is the field itself
                if is_django_field and 'ForeignKey' in func_name:
                    is_foreign_key = True
                    if value.args:
                        if isinstance(value.args[0], ast.Constant):
                            foreign_key_target = str(value.args[0].value)
                        elif isinstance(value.args[0], ast.Name):
                            foreign_key_target = value.args[0].id

                fields.append({
                    "field_name": attr_name,
                    "field_type": field_type,
                    "is_primary_key": is_primary_key,
                    "is_foreign_key": is_foreign_key,
                    "foreign_key_target": foreign_key_target,
                    "line": getattr(stmt, "lineno", node.lineno),
                })

        return {
            "table_name": table_name or node.name.lower(),  # Default to lowercase class name
            "fields": fields,
            "orm_type": orm_type,
        }

    def _is_pydantic_model(self, node: ast.ClassDef) -> bool:
        """Check if class is a Pydantic model."""
        for base in node.bases:
            base_name = self._get_name(base)
            if base_name and 'BaseModel' in base_name:
                return True
        return False

    def _is_dataclass(self, node: ast.ClassDef) -> bool:
        """Check if class has @dataclass decorator."""
        for decorator in node.decorator_list:
            name = self._get_decorator_name(decorator)
            if name and 'dataclass' in name:
                return True
        return False

    # =================================================================
    # SECURITY DETECTORS - Vulnerability Pattern Recognition
    # =================================================================

    def _is_sql_call(self, func_name: str) -> bool:
        """Check if function call is a SQL execution method."""
        # Handle db.execute, cursor.execute, session.query, etc.
        method = func_name.split('.')[-1]
        return method in self._sql_methods

    def _check_sql_injection(self, node: ast.Call, func_name: str) -> dict[str, Any] | None:
        """Detect SQL injection vulnerabilities in SQL execution calls.

        Looks for string formatting in SQL queries (vulnerable patterns):
        - f-strings: f"SELECT * FROM users WHERE id = {user_id}"
        - % formatting: "SELECT * FROM users WHERE id = %s" % user_id
        - .format(): "SELECT * FROM users WHERE id = {}".format(user_id)
        - String concatenation: "SELECT * FROM users WHERE id = " + user_id

        Safe patterns (parameterized queries):
        - cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        - cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))

        Args:
            node: Call node representing SQL execution (e.g., cursor.execute())
            func_name: Name of the SQL execution method

        Returns:
            Dict with issue details if vulnerable pattern found, None if safe
        """
        # SQL call must have at least one argument (the query)
        if not node.args:
            return None

        query_arg = node.args[0]

        # VULNERABLE PATTERN 1: f-string with expressions
        # f"SELECT * FROM users WHERE id = {user_id}"
        if isinstance(query_arg, ast.JoinedStr):
            # JoinedStr represents f-strings with FormattedValue nodes
            has_dynamic_content = any(isinstance(val, ast.FormattedValue) for val in query_arg.values)
            if has_dynamic_content:
                return {
                    "type": "sql_injection",
                    "severity": "high",
                    "line": node.lineno,
                    "function_call": func_name,
                    "vulnerability": "f-string formatting in SQL query",
                    "pattern": "f-string",
                    "scope": self.context.current_scope_name,
                }

        # VULNERABLE PATTERN 2: .format() method call
        # "SELECT * FROM users WHERE id = {}".format(user_id)
        if isinstance(query_arg, ast.Call):
            if isinstance(query_arg.func, ast.Attribute):
                if query_arg.func.attr == 'format':
                    # Check if base string is a SQL-like query
                    if self._looks_like_sql(query_arg.func.value):
                        return {
                            "type": "sql_injection",
                            "severity": "high",
                            "line": node.lineno,
                            "function_call": func_name,
                            "vulnerability": ".format() method in SQL query",
                            "pattern": ".format()",
                            "scope": self.context.current_scope_name,
                        }

        # VULNERABLE PATTERN 3: % formatting
        # "SELECT * FROM users WHERE id = %s" % user_id
        if isinstance(query_arg, ast.BinOp) and isinstance(query_arg.op, ast.Mod):
            # Check if left side is a string (the SQL query)
            if self._looks_like_sql(query_arg.left):
                return {
                    "type": "sql_injection",
                    "severity": "high",
                    "line": node.lineno,
                    "function_call": func_name,
                    "vulnerability": "% formatting in SQL query",
                    "pattern": "% operator",
                    "scope": self.context.current_scope_name,
                }

        # VULNERABLE PATTERN 4: String concatenation with +
        # "SELECT * FROM users WHERE id = " + user_id
        if isinstance(query_arg, ast.BinOp) and isinstance(query_arg.op, ast.Add):
            if self._looks_like_sql(query_arg.left) or self._looks_like_sql(query_arg.right):
                return {
                    "type": "sql_injection",
                    "severity": "high",
                    "line": node.lineno,
                    "function_call": func_name,
                    "vulnerability": "String concatenation in SQL query",
                    "pattern": "+ operator",
                    "scope": self.context.current_scope_name,
                }

        # SAFE: Parameterized query with tuple as second argument
        # cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        # This is the recommended pattern - no issue to report
        return None

    def _looks_like_sql(self, node: ast.AST) -> bool:
        """Check if AST node contains SQL keywords (heuristic).

        Simple heuristic to detect if a string looks like SQL.
        Used to reduce false positives in injection detection.

        Args:
            node: AST node to check (usually Constant or Name)

        Returns:
            True if node appears to contain SQL keywords
        """
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            sql_keywords = {'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'FROM', 'WHERE', 'JOIN'}
            query_upper = node.value.upper()
            return any(keyword in query_upper for keyword in sql_keywords)
        return False

    def _is_command_call(self, func_name: str) -> bool:
        """Check if function call is a command execution function."""
        # Handle os.system, subprocess.run, etc.
        func_parts = func_name.split('.')
        if len(func_parts) >= 2:
            # Check module.function pattern (os.system, subprocess.run)
            if func_parts[0] in {'os', 'subprocess'} and func_parts[-1] in self._command_functions:
                return True
        # Check bare function (system, exec, eval)
        if func_parts[-1] in self._command_functions:
            return True
        return False

    def _check_command_injection(self, node: ast.Call, func_name: str) -> dict[str, Any] | None:
        """Detect command injection vulnerabilities in system command execution.

        Looks for shell=True with dynamic input in subprocess calls:
        - subprocess.run(f"ls {user_input}", shell=True)  # VULNERABLE
        - os.system(f"rm {filename}")                     # VULNERABLE
        - subprocess.run(["ls", user_input])               # SAFE (no shell)

        Args:
            node: Call node representing command execution
            func_name: Name of the command execution function

        Returns:
            Dict with issue details if vulnerable pattern found, None if safe
        """
        # Command call must have at least one argument
        if not node.args:
            return None

        command_arg = node.args[0]

        # Check if shell=True is present (subprocess functions)
        has_shell_true = False
        if 'subprocess' in func_name:
            for keyword in node.keywords:
                if keyword.arg == 'shell':
                    if isinstance(keyword.value, ast.Constant):
                        has_shell_true = bool(keyword.value.value)
                    elif isinstance(keyword.value, ast.Name) and keyword.value.id == 'True':
                        has_shell_true = True

        # VULNERABLE PATTERN 1: f-string in command (always dangerous)
        # os.system(f"ls {user_input}") or subprocess.run(f"rm {file}", shell=True)
        if isinstance(command_arg, ast.JoinedStr):
            has_dynamic_content = any(isinstance(val, ast.FormattedValue) for val in command_arg.values)
            if has_dynamic_content:
                return {
                    "type": "command_injection",
                    "severity": "critical",
                    "line": node.lineno,
                    "function_call": func_name,
                    "vulnerability": "f-string formatting in shell command",
                    "pattern": "f-string",
                    "scope": self.context.current_scope_name,
                    "has_shell": has_shell_true or 'system' in func_name or 'popen' in func_name,
                }

        # VULNERABLE PATTERN 2: .format() in command
        # os.system("ls {}".format(user_input))
        if isinstance(command_arg, ast.Call):
            if isinstance(command_arg.func, ast.Attribute):
                if command_arg.func.attr == 'format':
                    return {
                        "type": "command_injection",
                        "severity": "critical",
                        "line": node.lineno,
                        "function_call": func_name,
                        "vulnerability": ".format() method in shell command",
                        "pattern": ".format()",
                        "scope": self.context.current_scope_name,
                        "has_shell": has_shell_true or 'system' in func_name,
                    }

        # VULNERABLE PATTERN 3: % formatting in command
        # os.system("ls %s" % user_input)
        if isinstance(command_arg, ast.BinOp) and isinstance(command_arg.op, ast.Mod):
            return {
                "type": "command_injection",
                "severity": "critical",
                "line": node.lineno,
                "function_call": func_name,
                "vulnerability": "% formatting in shell command",
                "pattern": "% operator",
                "scope": self.context.current_scope_name,
                "has_shell": has_shell_true or 'system' in func_name,
            }

        # VULNERABLE PATTERN 4: String concatenation in command
        # os.system("ls " + user_input)
        if isinstance(command_arg, ast.BinOp) and isinstance(command_arg.op, ast.Add):
            return {
                "type": "command_injection",
                "severity": "critical",
                "line": node.lineno,
                "function_call": func_name,
                "vulnerability": "String concatenation in shell command",
                "pattern": "+ operator",
                "scope": self.context.current_scope_name,
                "has_shell": has_shell_true or 'system' in func_name,
            }

        # VULNERABLE PATTERN 5: Variable passed to shell command (potential injection)
        # This is less certain but worth flagging if shell=True
        if has_shell_true and isinstance(command_arg, ast.Name):
            return {
                "type": "command_injection",
                "severity": "medium",
                "line": node.lineno,
                "function_call": func_name,
                "vulnerability": "Variable passed to shell=True (verify input sanitization)",
                "pattern": "variable with shell=True",
                "scope": self.context.current_scope_name,
                "has_shell": True,
            }

        # SAFE: subprocess.run(['ls', user_input]) - list with separate args
        # No shell parsing, safe from injection
        return None

    # =================================================================
    # OUTPUT - Convert State Buckets to Results
    # =================================================================

    def get_results(self) -> dict[str, list[dict[str, Any]]]:
        """Return extracted data as dictionary.

        This is the "new schema" that the adapter layer will map to legacy tables.

        Returns:
            Dict with keys: definitions, calls, imports, issues
        """
        return {
            "definitions": self.definitions,
            "calls": self.calls,
            "imports": self.imports,
            "issues": self.issues,
        }
