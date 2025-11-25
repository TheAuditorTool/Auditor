"""
Database-driven source and sink discovery.

Phase 3 implementation that discovers sources and sinks from the database
instead of using hardcoded patterns. This eliminates the need for manual
pattern maintenance and automatically discovers new sources/sinks as the
database evolves.
"""


from typing import Dict, List, Any, Optional, Tuple
import sys
import sqlite3


def _matches_file_io_pattern(func_name: str, patterns: list[str]) -> bool:
    """
    Strict pattern matching for file I/O functions to avoid false positives.

    Prevents substring matches like 'open' in 'openSgIpv4.addIngressRule'.

    Args:
        func_name: Function name to check (e.g., 'fs.readFile', 'open', 'openSgIpv4.addIngressRule')
        patterns: List of file I/O function names (e.g., ['open', 'readFile'])

    Returns:
        True if func_name is a file I/O function, False for false positives

    Examples:
        >>> _matches_file_io_pattern('open', ['open'])
        True
        >>> _matches_file_io_pattern('fs.open', ['open'])
        True
        >>> _matches_file_io_pattern('openSgIpv4.addIngressRule', ['open'])
        False
    """
    if not func_name:
        return False

    for pattern in patterns:
        # Exact match: 'open' == 'open'
        if func_name == pattern:
            return True

        # Module-qualified suffix: 'fs.open', 'path.open'
        # Ensures '.open' exists and function ends with pattern
        if f'.{pattern}' in func_name and func_name.endswith(pattern):
            return True

    return False


class TaintDiscovery:
    """Database-driven discovery of taint sources and sinks."""

    def __init__(self, cache):
        """Initialize with a cache (either old MemoryCache or SchemaMemoryCache)."""
        self.cache = cache

    def discover_sources(self, sources_dict: dict[str, list[str]] | None = None) -> list[dict[str, Any]]:
        """
        Discover taint sources from database.

        Instead of searching for hardcoded patterns, we discover actual sources
        that exist in the codebase by querying the database tables directly.

        Args:
            sources_dict: Dictionary of source patterns by category from TaintRegistry
                         (e.g., {'http_request': ['req.', 'request.'], 'user_input': ['body.', ...]})

        Returns:
            List of source dictionaries with metadata
        """
        sources = []

        # ZERO FALLBACK POLICY: If no sources_dict provided, return empty
        if sources_dict is None:
            sources_dict = {}

        # HTTP Request Sources: Use variable_usage table to find actual variable accesses
        # CRITICAL: IFDS needs variable references (req.query.x), NOT HTTP metadata (GET /api/x)
        # ZERO FALLBACK POLICY: Use sources_dict from registry, no hardcoded patterns
        # FIX: Check BOTH 'http_request' and 'user_input' categories since rules use both
        http_request_patterns = sources_dict.get('http_request', [])
        user_input_patterns = sources_dict.get('user_input', [])
        combined_patterns = http_request_patterns + user_input_patterns

        seen_vars = set()

        # 1. Check Variable Usage (e.g. "const body = req.body")
        for var_usage in self.cache.variable_usage:
            var_name = var_usage.get('variable_name', '')
            # Strict prefix match to avoid 'require' matching 'req'
            if combined_patterns and any(var_name == p or var_name.startswith(p + '.') for p in combined_patterns):
                if var_name not in seen_vars:
                    seen_vars.add(var_name)
                    sources.append({
                        'type': 'http_request',
                        'name': var_name,
                        'file': var_usage.get('file', ''),
                        'line': var_usage.get('line', 0),
                        'pattern': var_name,  # ← Variable reference for IFDS
                        'category': 'http_request',
                        'risk': 'high',  # All user input is high risk
                        'metadata': var_usage
                    })

        # 2. CRITICAL FIX: Check Property Symbols for BOTH categories (e.g. "req.body", "req.query")
        # Discovery was previously blind to these because they live in the symbols table
        for symbol in self.cache.symbols_by_type.get('property', []):
            name = symbol.get('name', '')
            # Check both HTTP and user_input patterns against properties
            if combined_patterns and any(name == p or name.startswith(p + '.') for p in combined_patterns):
                if name not in seen_vars:
                    seen_vars.add(name)
                    sources.append({
                        'type': 'http_request',
                        'name': name,
                        'file': symbol.get('path', ''),
                        'line': symbol.get('line', 0),
                        'pattern': name,
                        'category': 'http_request',
                        'risk': 'high',
                        'metadata': symbol
                    })

        # REMOVED: Function parameter fallback - ZERO FALLBACK POLICY violation
        # This section was adding generic parameters like 'data', 'value' as sources
        # when pattern matching failed. This is CANCER and violates the most important
        # rule in the codebase. If pattern matching fails, FIX THE PATTERNS, don't
        # add fallback logic that creates wrong sources.
        #
        # Previous bug: This code added 'data' parameter from BaseController.sendSuccess
        # as a source, creating wrong taint paths that bypassed middleware validation.

        # REMOVED: File Read Sources
        # Reason: File operations (open, readFile) are SINKS (path traversal), not SOURCES
        # Reading file contents doesn't create user-controlled data - the path is the vulnerability
        # Sources should be things like HTTP request params, user input, environment vars
        # If file contents need to be tracked as tainted, that's a different analysis (second-order)

        # Environment Variable Sources
        for env in self.cache.env_var_usage:
            sources.append({
                'type': 'environment',
                'name': env.get('key', 'unknown'),
                'file': env.get('file', ''),
                'line': env.get('line', 0),
                'pattern': f"process.env.{env.get('key', '')}",
                'category': 'environment',
                'risk': 'low',
                'metadata': env
            })

        # Database Query Results as Sources (for second-order injection)
        for query in self.cache.sql_queries:
            if 'SELECT' in query.get('query_text', '').upper():
                sources.append({
                    'type': 'database_read',
                    'name': 'sql_query_result',
                    'file': query.get('file_path', ''),
                    'line': query.get('line_number', 0),
                    'pattern': query.get('query_text', '')[:50],
                    'category': 'database',
                    'risk': 'low',
                    'metadata': query
                })

        return sources

    def discover_sinks(self, sinks_dict: dict[str, list[str]] | None = None) -> list[dict[str, Any]]:
        """
        Discover security sinks from database.

        Instead of searching for hardcoded patterns, we discover actual sinks
        that exist in the codebase by querying the database tables directly.

        Args:
            sinks_dict: Dictionary of sink patterns by category from TaintRegistry
                       (e.g., {'sql': ['Sequelize.literal', ...], 'command': ['exec', ...]})

        Returns:
            List of sink dictionaries with metadata
        """
        sinks = []

        # ZERO FALLBACK POLICY: If no sinks_dict provided, return empty
        if sinks_dict is None:
            sinks_dict = {}

        # SQL Injection Sinks: Resolve SQL queries to their result variables
        # PHASE 1 FIX: Pattern must be file::scope::variable to match DFG node IDs
        # Join sql_queries with assignments table to find result variable
        conn = sqlite3.connect(self.cache.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        for query in self.cache.sql_queries:
            file_path = query.get('file_path', '')
            line_number = query.get('line_number', 0)
            query_text = query.get('query_text', '')

            # Filter out migration files based on extraction_source tag
            extraction_source = query.get('extraction_source', '')
            if extraction_source == 'migration_file':
                continue  # Skip migrations - they run at deploy time, not runtime

            # Query assignments table to find variable assigned the query result
            # HEURISTIC FIX: SQL queries are often multi-line. The assignment
            # (const x = await db.query(...)) starts 0-5 lines BEFORE the SQL
            # text literal. We search a window and pick the closest match.
            # ORDER BY line DESC ensures we get the nearest assignment.
            cursor.execute("""
                SELECT target_var, in_function
                FROM assignments
                WHERE file = ?
                  AND line >= ? - 5
                  AND line <= ?
                ORDER BY line DESC
                LIMIT 1
            """, (file_path, line_number, line_number))

            result_row = cursor.fetchone()
            if result_row:
                # Found assignment - extract variable name
                target_var = result_row['target_var']

                # ✅ CORRECTED: Pattern is JUST the variable name (access path)
                # IFDS analyzer will use file+line to find scope and construct node_id
                pattern = target_var

                # Assess risk based on query construction
                risk = self._assess_sql_risk(query_text)

                sinks.append({
                    'type': 'sql',
                    'name': target_var,
                    'file': file_path,
                    'line': line_number,
                    'pattern': pattern,  # ✅ BARE VARIABLE NAME (e.g., "result")
                    'category': 'sql',
                    'risk': risk,
                    'is_parameterized': query.get('is_parameterized', False),
                    'metadata': query
                })
            # else: ZERO FALLBACK - skip sinks without assignments

        conn.close()

        # SQL Injection Sinks: Raw SQL functions from registry
        # ZERO FALLBACK POLICY: Use sinks_dict from registry, no hardcoded patterns
        # Open connection for querying assignments
        conn2 = sqlite3.connect(self.cache.db_path)
        conn2.row_factory = sqlite3.Row
        cursor2 = conn2.cursor()

        raw_sql_funcs = sinks_dict.get('sql', [])
        sql_query_count = 0
        for call in self.cache.function_call_args:
            # Filter out migration files
            file_path = call.get('file', '')
            if '/migrations/' in file_path or 'migrations\\' in file_path or '/migrate/' in file_path or 'migrate\\' in file_path:
                continue  # Skip migrations - they run at deploy time, not runtime

            func_name = call.get('callee_function', '')
            if raw_sql_funcs and any(raw_func in func_name for raw_func in raw_sql_funcs):
                arg_expr = call.get('argument_expr', '')
                # Check if argument contains template literal interpolation
                has_interpolation = '${' in arg_expr
                risk = 'critical' if has_interpolation else 'high'

                # Query assignments table to find variable assigned the query result
                # HEURISTIC FIX: Same multi-line fix as above
                file_path = call.get('file', '')
                line_number = call.get('line', 0)

                cursor2.execute("""
                    SELECT target_var, in_function
                    FROM assignments
                    WHERE file = ?
                      AND line >= ? - 5
                      AND line <= ?
                    ORDER BY line DESC
                    LIMIT 1
                """, (file_path, line_number, line_number))

                result_row = cursor2.fetchone()
                if result_row:
                    # Use the target variable as the pattern
                    pattern = result_row['target_var']
                else:
                    # If no assignment, this might be a void call - use func_name
                    pattern = func_name

                sinks.append({
                    'type': 'sql',
                    'name': func_name,
                    'file': file_path,
                    'line': line_number,
                    'pattern': pattern,  # Use target var if assigned, else func_name
                    'category': 'sql',
                    'risk': risk,
                    'is_parameterized': False,
                    'has_interpolation': has_interpolation,
                    'metadata': call
                })
                sql_query_count += 1

        # ORM Query Methods as SQL Sinks
        # Query sequelize_models and python_orm_models tables to determine if caller is a model
        # Use conn2/cursor2 which is already open from SQL sinks section

        # Build set of known model names
        model_names = set()
        cursor2.execute("SELECT model_name FROM sequelize_models")
        for row in cursor2.fetchall():
            model_names.add(row['model_name'])

        cursor2.execute("SELECT model_name FROM python_orm_models")
        for row in cursor2.fetchall():
            model_names.add(row['model_name'])

        # ORM method patterns
        orm_patterns = [
            # Sequelize ORM patterns
            '.findOne', '.findAll', '.findByPk', '.create', '.update',
            '.destroy', '.bulkCreate', '.upsert', '.findOrCreate',
            # Generic ORM patterns
            '.query', '.execute', 'db.query', 'db.execute',
            # Knex patterns
            'knex.select', 'knex.insert', 'knex.update', 'knex.delete'
        ]

        for call in self.cache.function_call_args:
            # Filter out migration files
            file_path = call.get('file', '')
            if '/migrations/' in file_path or 'migrations\\' in file_path or '/migrate/' in file_path or 'migrate\\' in file_path:
                continue  # Skip migrations - they run at deploy time, not runtime

            func_name = call.get('callee_function', '')
            if not func_name:
                continue

            # Check if it's an ORM method call (Model.method pattern)
            is_orm_method = False
            for pattern in orm_patterns:
                if pattern in func_name:
                    # Additional check: ensure it looks like Model.method, not just contains pattern
                    # This avoids false positives like 'findAllMatches'
                    parts = func_name.split('.')
                    if len(parts) >= 2 and parts[-1].startswith(pattern.lstrip('.')):
                        # Query database to check if caller is a known ORM model
                        model_or_service_name = parts[-2]

                        # Only flag as ORM sink if the caller is in sequelize_models or python_orm_models table
                        if model_or_service_name in model_names:
                            is_orm_method = True
                            break

            if is_orm_method:
                arg_expr = call.get('argument_expr')

                # ZERO FALLBACK: Skip ORM calls with no arguments (NULL in DB)
                # Methods like save(), commit() have no injection risk without args
                if arg_expr is None:
                    continue

                # Check for unsafe patterns in ORM arguments
                has_interpolation = '${' in arg_expr or '+' in arg_expr
                risk = 'high' if has_interpolation else 'medium'

                # Query assignments table to find variable assigned the ORM result
                # This is critical - the pattern must be the target variable, not the function name
                file_path = call.get('file', '')
                line_number = call.get('line', 0)

                cursor2.execute("""
                    SELECT target_var, in_function
                    FROM assignments
                    WHERE file = ? AND line = ?
                    LIMIT 1
                """, (file_path, line_number))

                result_row = cursor2.fetchone()
                if result_row:
                    # Use the target variable as the pattern (e.g., "account" not "Account.create")
                    pattern = result_row['target_var']
                else:
                    # If no assignment found, use the function name as fallback
                    # This handles cases like User.create(...).then(...) with no assignment
                    pattern = func_name

                sinks.append({
                    'type': 'sql',  # ORM methods are SQL sinks
                    'name': func_name,
                    'file': file_path,
                    'line': line_number,
                    'pattern': pattern,  # Use target variable from assignments table
                    'category': 'orm',  # Subcategory to distinguish from raw SQL
                    'risk': risk,
                    'is_parameterized': not has_interpolation,  # ORM usually parameterized unless concatenation
                    'has_interpolation': has_interpolation,
                    'metadata': call
                })

        # Close connection used for SQL/ORM sinks
        conn2.close()

        # NoSQL Injection Sinks (optional - language-specific)
        for query in getattr(self.cache, 'nosql_queries', []):
            sinks.append({
                'type': 'nosql',
                'name': query.get('collection', 'unknown'),
                'file': query.get('file', ''),
                'line': query.get('line', 0),
                'pattern': query.get('operation', ''),
                'category': 'nosql',
                'risk': 'medium',
                'metadata': query
            })

        # Command Injection Sinks: From registry
        # ZERO FALLBACK POLICY: Use sinks_dict from registry, no hardcoded patterns
        cmd_funcs = sinks_dict.get('command', [])
        for call in self.cache.function_call_args:
            func_name = call.get('callee_function', '')
            if cmd_funcs and any(cmd in func_name for cmd in cmd_funcs):
                sinks.append({
                    'type': 'command',
                    'name': func_name,
                    'file': call.get('file', ''),
                    'line': call.get('line', 0),
                    'pattern': func_name,
                    'category': 'command',
                    'risk': 'critical',
                    'metadata': call
                })

        # XSS Sinks: React dangerouslySetInnerHTML
        for hook in self.cache.react_hooks:
            # Check if hook uses dangerous HTML setting
            if 'dangerouslySetInnerHTML' in str(hook):
                sinks.append({
                    'type': 'xss',
                    'name': 'dangerouslySetInnerHTML',
                    'file': hook.get('file', ''),
                    'line': hook.get('line', 0),
                    'pattern': 'dangerouslySetInnerHTML',
                    'category': 'xss',
                    'risk': 'high',
                    'metadata': hook
                })

        # XSS Sinks: Direct innerHTML assignments
        for assignment in self.cache.assignments:
            target = assignment.get('target_var', '')
            if 'innerHTML' in target or 'outerHTML' in target:
                sinks.append({
                    'type': 'xss',
                    'name': target,
                    'file': assignment.get('file', ''),
                    'line': assignment.get('line', 0),
                    'pattern': target,
                    'category': 'xss',
                    'risk': 'high',
                    'metadata': assignment
                })

        # XSS Sinks: document.write and document.writeln from registry
        # ZERO FALLBACK POLICY: Use sinks_dict from registry, no hardcoded patterns
        xss_funcs = sinks_dict.get('xss', [])
        for call in self.cache.function_call_args:
            func_name = call.get('callee_function', '')
            if xss_funcs and any(xss_func in func_name for xss_func in xss_funcs):
                arg_expr = call.get('argument_expr', '')
                # Check if argument contains template literal interpolation or concatenation
                has_interpolation = '${' in arg_expr or '+' in arg_expr
                risk = 'critical' if has_interpolation else 'high'

                sinks.append({
                    'type': 'xss',
                    'name': func_name,
                    'file': call.get('file', ''),
                    'line': call.get('line', 0),
                    'pattern': func_name,  # FIX: Use func_name to ensure parsing consistency
                    'category': 'xss',
                    'risk': risk,
                    'has_interpolation': has_interpolation,
                    'metadata': call
                })

        # Path Traversal Sinks: File operations from registry
        # ZERO FALLBACK POLICY: Use sinks_dict from registry, no hardcoded patterns
        # CRITICAL: Use strict matching to avoid false positives like 'open' in 'openSgIpv4'
        file_funcs = sinks_dict.get('path', [])
        for call in self.cache.function_call_args:
            func_name = call.get('callee_function', '')
            if file_funcs and _matches_file_io_pattern(func_name, file_funcs):
                # Check if first argument could be user-controlled
                arg = call.get('argument_expr', '')
                file_path = call.get('file', '')

                if arg and not arg.startswith('"') and not arg.startswith("'"):
                    sinks.append({
                        'type': 'path',
                        'name': func_name,
                        'file': file_path,
                        'line': call.get('line', 0),
                        'pattern': func_name,  # FIX: Use func_name. Complex path args (e.g. path.join(...)) can break parsing
                        'category': 'path',
                        'risk': 'medium',
                        'metadata': call
                    })

        # LDAP Injection Sinks from registry
        # ZERO FALLBACK POLICY: Use sinks_dict from registry, no hardcoded patterns
        ldap_funcs = sinks_dict.get('ldap', [])
        for call in self.cache.function_call_args:
            func_name = call.get('callee_function', '')
            if ldap_funcs and any(f in func_name.lower() and 'ldap' in func_name.lower() for f in ldap_funcs):
                sinks.append({
                    'type': 'ldap',
                    'name': func_name,
                    'file': call.get('file', ''),
                    'line': call.get('line', 0),
                    'pattern': func_name,
                    'category': 'ldap',
                    'risk': 'medium',
                    'metadata': call
                })

        return sinks

    def _assess_sql_risk(self, query_text: str) -> str:
        """
        Assess the risk level of an SQL query based on its construction.

        Args:
            query_text: The SQL query text

        Returns:
            Risk level: 'critical', 'high', 'medium', or 'low'
        """
        query_lower = query_text.lower()

        # Critical: String concatenation with user input
        if any(op in query_text for op in ['+', '${', 'f"', "f'", '`${', '".', "'."]):
            return 'critical'

        # High: Direct string interpolation
        if '%s' in query_text or '%d' in query_text:
            return 'high'

        # Low: Parameterized queries
        if any(param in query_text for param in ['?', '$1', ':param', '@param']):
            return 'low'

        # Medium: Can't determine
        return 'medium'

    def filter_framework_safe_sinks(self, sinks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Filter out sinks that are automatically safe due to framework protections.

        Database-driven approach: Queries framework_safe_sinks table populated during indexing.
        ZERO FALLBACK POLICY: No hardcoded safe patterns.

        Examples from database:
        - Express res.json() (auto-escapes JSON)
        - React components (escape by default)
        - Parameterized SQL queries

        Args:
            sinks: List of discovered sinks

        Returns:
            Filtered list of sinks that are actually vulnerable
        """
        # Query framework_safe_sinks table for safe patterns
        # Build set of safe patterns for fast lookup
        safe_patterns = set()

        # Access framework_safe_sinks through cache
        for safe_sink in getattr(self.cache, 'framework_safe_sinks', []):
            # Only include patterns marked as safe (is_safe = 1)
            if safe_sink.get('is_safe'):
                pattern = safe_sink.get('sink_pattern', '')
                if pattern:
                    safe_patterns.add(pattern.lower())

        filtered = []

        for sink in sinks:
            # Check if sink pattern matches any safe pattern from database
            sink_name = sink.get('name', '').lower()
            sink_pattern = sink.get('pattern', '').lower()

            # Skip if pattern is in safe list
            if sink_name in safe_patterns or sink_pattern in safe_patterns:
                continue

            # Skip if any safe pattern is a substring of the sink
            # (e.g., 'res.json' matches 'res.json(data)')
            if any(safe in sink_name or safe in sink_pattern for safe in safe_patterns):
                continue

            # Additional hardening: Skip parameterized SQL (defensive check)
            # This is a safety net in case framework_safe_sinks table is incomplete
            if sink.get('category') == 'sql' and sink.get('is_parameterized'):
                continue

            # Keep sink if not safe
            filtered.append(sink)

        return filtered

    def discover_sanitizers(self) -> list[dict[str, Any]]:
        """
        Discover sanitizers from framework tables.

        Queries database for:
        - validation_framework_usage (Joi, Yup, etc. validators)
        - python_validators (Pydantic validators)
        - sequelize_models (ORM models with safe parameterization)
        - python_orm_models (SQLAlchemy/Django models)

        Returns:
            List of sanitizer dictionaries to register in TaintRegistry
        """
        sanitizers = []

        # JavaScript validators (Joi, Yup, class-validator, etc.)
        for validator in getattr(self.cache, 'validation_framework_usage', []):
            sanitizers.append({
                'type': 'validator',
                'name': validator.get('function_name', ''),
                'framework': validator.get('framework', 'unknown'),
                'language': 'javascript',
                'file': validator.get('file', ''),
                'line': validator.get('line', 0),
                'pattern': validator.get('function_name', ''),
                'metadata': validator
            })

        # Python validators (Pydantic)
        for validator in getattr(self.cache, 'python_validators', []):
            validator_name = validator.get('validator_name', '')
            sanitizers.append({
                'type': 'validator',
                'name': validator_name,
                'framework': 'pydantic',
                'language': 'python',
                'file': validator.get('file', ''),
                'line': validator.get('line', 0),
                'pattern': validator_name,
                'validator_type': validator.get('validator_type', 'field'),  # field vs root
                'metadata': validator
            })

        # Sequelize ORM models (safe parameterization)
        for model in getattr(self.cache, 'sequelize_models', []):
            model_name = model.get('model_name', '')
            # Register model methods as safe ORM operations
            for method in ['findOne', 'findAll', 'findByPk', 'create', 'update', 'destroy']:
                sanitizers.append({
                    'type': 'orm_model',
                    'name': f'{model_name}.{method}',
                    'framework': 'sequelize',
                    'language': 'javascript',
                    'file': model.get('file', ''),
                    'line': model.get('line', 0),
                    'pattern': f'{model_name}.{method}',
                    'model_name': model_name,
                    'table_name': model.get('table_name'),
                    'metadata': model
                })

        # Python ORM models (SQLAlchemy, Django)
        for model in getattr(self.cache, 'python_orm_models', []):
            model_name = model.get('model_name', '')
            framework = model.get('framework', 'sqlalchemy')
            # Register as safe ORM (parameterized queries)
            sanitizers.append({
                'type': 'orm_model',
                'name': model_name,
                'framework': framework,
                'language': 'python',
                'file': model.get('file', ''),
                'line': model.get('line', 0),
                'pattern': model_name,
                'table_name': model.get('table_name'),
                'metadata': model
            })

        return sanitizers
