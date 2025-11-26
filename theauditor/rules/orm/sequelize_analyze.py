"""Sequelize ORM Analyzer - Database-First Approach.

Detects Sequelize ORM anti-patterns and performance issues using ONLY
indexed database data. NO AST traversal. NO file I/O. Pure SQL queries.

This analyzer uses function_call_args table since orm_queries is not
populated by the standard indexer.

Follows schema contract architecture (v1.1+):
- Frozensets for all patterns (O(1) lookups)
- Schema-validated queries via build_query()
- Assume all contracted tables exist (crash if missing)
- Proper confidence levels
"""


import sqlite3
from dataclasses import dataclass

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence, RuleMetadata
from theauditor.indexer.schema import build_query


# ============================================================================
# RULE METADATA - SMART FILTERING
# ============================================================================

METADATA = RuleMetadata(
    name="sequelize_orm_issues",
    category="orm",

    # Target JavaScript/TypeScript files (Sequelize supports both)
    target_extensions=['.js', '.ts', '.mjs', '.cjs'],

    # Exclude patterns - skip tests, migrations, build, TheAuditor folders
    exclude_patterns=[
        '__tests__/',
        'test/',
        'tests/',
        'node_modules/',
        'dist/',
        'build/',
        '.next/',
        'migrations/',
        'seeders/',            # Sequelize-specific seeders
        '.pf/',                # TheAuditor output directory
        '.auditor_venv/'       # TheAuditor sandboxed tools
    ],

    # This is a DATABASE-ONLY rule (no JSX required)
    requires_jsx_pass=False
)


# ============================================================================
# PATTERN DEFINITIONS (Golden Standard: Frozen Dataclass)
# ============================================================================

@dataclass(frozen=True)
class SequelizePatterns:
    """Immutable pattern definitions for Sequelize ORM detection."""

    # Query methods that need pagination
    UNBOUNDED_METHODS = frozenset([
        'findAll', 'findAndCountAll', 'scope', 'findAllWithScopes'
    ])

    # Write operations that may need transactions
    WRITE_METHODS = frozenset([
        'create', 'bulkCreate', 'update', 'bulkUpdate',
        'destroy', 'bulkDestroy', 'upsert', 'save',
        'increment', 'decrement', 'restore', 'bulkRestore',
        'set', 'add', 'remove', 'setAttributes'
    ])

    # Methods prone to race conditions
    RACE_CONDITION_METHODS = frozenset([
        'findOrCreate', 'findOrBuild', 'findCreateFind'
    ])

    # Raw query methods vulnerable to SQL injection
    RAW_QUERY_METHODS = frozenset([
        'sequelize.query', 'query', 'Sequelize.literal',
        'literal', 'sequelize.fn', 'Sequelize.fn',
        'sequelize.col', 'Sequelize.col', 'sequelize.where',
        'Sequelize.where', 'sequelize.cast', 'Sequelize.cast'
    ])

    # Transaction-related methods
    TRANSACTION_METHODS = frozenset([
        'transaction', 'commit', 'rollback', 't.commit', 't.rollback',
        'sequelize.transaction', 'startTransaction', 'commitTransaction'
    ])

    # Include patterns that indicate death queries
    DEATH_QUERY_PATTERNS = frozenset([
        'all: true', 'all:true', 'nested: true', 'nested:true',
        'include: { all: true', 'include:[{all:true'
    ])

    # Patterns indicating SQL injection risk
    SQL_INJECTION_PATTERNS = frozenset([
        '${', '"+', '" +', '` +', 'concat(', '+ req.',
        '+ params.', '+ body.', '${req.', '${params.',
        '.replace(', '.replaceAll(', 'eval('
    ])

    # Common Sequelize models (for detection)
    COMMON_MODELS = frozenset([
        'User', 'Account', 'Product', 'Order', 'Customer',
        'Post', 'Comment', 'Category', 'Tag', 'Role',
        'Permission', 'Session', 'Token', 'File', 'Image',
        'Plant', 'Worker', 'Facility', 'Zone', 'Batch'
    ])


# ============================================================================
# ANALYZER CLASS (Golden Standard)
# ============================================================================

class SequelizeAnalyzer:
    """Analyzer for Sequelize ORM anti-patterns and security issues."""

    def __init__(self, context: StandardRuleContext):
        """Initialize analyzer with database context.

        Args:
            context: Rule context containing database path
        """
        self.context = context
        self.patterns = SequelizePatterns()
        self.findings = []

    def analyze(self) -> list[StandardFinding]:
        """Main analysis entry point.

        Returns:
            List of Sequelize ORM issues found
        """
        if not self.context.db_path:
            return []

        conn = sqlite3.connect(self.context.db_path)
        self.cursor = conn.cursor()

        try:
            # Run all checks
            self._check_death_queries()
            self._check_n_plus_one_patterns()
            self._check_unbounded_queries()
            self._check_race_conditions()
            self._check_missing_transactions()
            self._check_sql_injection()
            self._check_excessive_eager_loading()
            self._check_hard_deletes()
            self._check_raw_sql_bypass()

        finally:
            conn.close()

        return self.findings

    def _check_death_queries(self):
        """Detect death queries with all:true and nested:true."""
        # Fetch all function_call_args, filter in Python
        query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                           where="argument_expr IS NOT NULL",
                           order_by="file, line")
        self.cursor.execute(query)

        for file, line, method, args in self.cursor.fetchall():
            # Check for death query methods in Python
            if not any(method.endswith(f'.{m}') for m in ['findAll', 'findOne', 'findAndCountAll']):
                continue
            if not args:
                continue

            args_str = str(args).lower()

            # Check for death query pattern
            has_all = any(pattern in args_str for pattern in ['all: true', 'all:true'])
            has_nested = any(pattern in args_str for pattern in ['nested: true', 'nested:true'])

            if has_all and has_nested:
                self.findings.append(StandardFinding(
                    rule_name='sequelize-death-query',
                    message=f'Death query detected: {method} with all:true and nested:true',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    category='orm-performance',
                    snippet=f'{method}({{ include: {{ all: true, nested: true }} }})',
                    confidence=Confidence.HIGH,
                    cwe_id='CWE-400'
                ))

    def _check_n_plus_one_patterns(self):
        """Detect potential N+1 query patterns."""
        # Fetch all function_call_args, filter in Python
        query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                           order_by="file, line")
        self.cursor.execute(query)
        # Store results before loop (avoid cursor state bug)
        findall_queries = self.cursor.fetchall()

        for file, line, method, args in findall_queries:
            # Check for findAll/findAndCountAll in Python
            if not (method.endswith('.findAll') or method.endswith('.findAndCountAll')):
                continue
            # Extract model name
            model = method.split('.')[0] if '.' in method else 'Model'

            # Skip if not a known model
            if model not in self.patterns.COMMON_MODELS and not model[0].isupper():
                continue

            # Check if includes are present
            has_include = args and 'include' in str(args)

            if not has_include:
                # Check if there are associations defined nearby
                confidence = self._check_associations_nearby(file, line, model)

                if confidence > 0:
                    self.findings.append(StandardFinding(
                        rule_name='sequelize-n-plus-one',
                        message=f'Potential N+1 query: {method} without include option',
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category='orm-performance',
                        snippet=f'{method}() without eager loading',
                        confidence=Confidence.MEDIUM if confidence == 1 else Confidence.HIGH,
                        cwe_id='CWE-400'
                    ))

    def _check_associations_nearby(self, file: str, line: int, model: str) -> int:
        """Check if model has associations defined nearby.

        Returns:
            0 if no associations, 1 if maybe, 2 if definitely
        """
        # Fetch all function_call_args in file, filter in Python
        query = build_query('function_call_args', ['callee_function'],
                           where="file = ?")
        self.cursor.execute(query, (file,))

        # Check for association methods in Python
        association_methods = ['.belongsTo', '.hasOne', '.hasMany', '.belongsToMany']
        count = 0
        for (callee,) in self.cursor.fetchall():
            if callee.startswith(f'{model}.') and any(callee.endswith(m) for m in association_methods):
                count += 1

        return 2 if count > 0 else 1

    def _check_unbounded_queries(self):
        """Check for queries without limits that could cause memory issues."""
        # Fetch all function_call_args, filter in Python
        query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                           order_by="file, line")
        self.cursor.execute(query)

        for file, line, func, args in self.cursor.fetchall():
            # Check if any unbounded method is in callee_function
            if not any(f'.{method}' in func for method in self.patterns.UNBOUNDED_METHODS):
                continue
            # Check if limit/offset/pagination is present
            has_limit = False
            if args:
                args_str = str(args).lower()
                has_limit = any(p in args_str for p in ['limit:', 'limit :', 'take:', 'offset:', 'page:'])

                if not has_limit:
                    self.findings.append(StandardFinding(
                        rule_name='sequelize-unbounded-query',
                        message=f'Unbounded query: {func} without limit',
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        category='orm-performance',
                        snippet=f'{func}() without pagination',
                        confidence=Confidence.HIGH,
                        cwe_id='CWE-400'
                    ))

    def _check_race_conditions(self):
        """Check for race condition vulnerabilities."""
        # Fetch all function_call_args, filter in Python
        query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                           order_by="file, line")
        self.cursor.execute(query)
        # Store results before nested loop (avoid cursor state bug)
        all_calls = self.cursor.fetchall()

        for file, line, func, args in all_calls:
            # Check if any race condition method is in callee_function
            if not any(f'.{method}' in func for method in self.patterns.RACE_CONDITION_METHODS):
                continue
            # Check for transaction nearby
            has_transaction = self._check_transaction_nearby(file, line)

            if not has_transaction:
                    self.findings.append(StandardFinding(
                        rule_name='sequelize-race-condition',
                        message=f'Race condition risk: {func} without transaction',
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category='orm-concurrency',
                        snippet=f'{func}() outside transaction',
                        confidence=Confidence.MEDIUM,
                        cwe_id='CWE-362'
                    ))

    def _check_transaction_nearby(self, file: str, line: int) -> bool:
        """Check if there's a transaction nearby."""
        # Check in function_call_args - fetch and filter in Python
        query = build_query('function_call_args', ['callee_function'],
                           where="file = ? AND ABS(line - ?) <= 30")
        self.cursor.execute(query, (file, line))

        for (callee,) in self.cursor.fetchall():
            if 'transaction' in callee.lower() or callee in ['t.commit', 't.rollback']:
                return True

        # Check in assignments - fetch and filter in Python
        query = build_query('assignments', ['target_var', 'source_expr'],
                           where="file = ? AND ABS(line - ?) <= 30")
        self.cursor.execute(query, (file, line))

        for target, source in self.cursor.fetchall():
            if 'transaction' in target.lower() or (source and 'transaction' in source.lower()):
                return True

        return False

    def _check_missing_transactions(self):
        """Check for multiple write operations without transactions."""
        # Fetch all function_call_args, filter in Python
        query = build_query('function_call_args', ['file', 'line', 'callee_function'],
                           order_by="file, line")
        self.cursor.execute(query)

        # Filter for write methods in Python
        write_ops = []
        for file, line, func in self.cursor.fetchall():
            if any(f'.{method}' in func for method in self.patterns.WRITE_METHODS):
                write_ops.append((file, line, func))

        # Group by file
        file_ops = {}
        for file, line, func in write_ops:
            if file not in file_ops:
                file_ops[file] = []
            file_ops[file].append({'line': line, 'func': func})

        # Check for operations close together without transaction
        for file, ops in file_ops.items():
            if len(ops) < 2:
                continue

            ops.sort(key=lambda x: x['line'])

            for i in range(len(ops) - 1):
                op1 = ops[i]
                op2 = ops[i + 1]

                # Operations within 20 lines
                if op2['line'] - op1['line'] <= 20:
                    # Check for transaction
                    has_transaction = self._check_transaction_between(
                        file, op1['line'], op2['line']
                    )

                    if not has_transaction:
                        self.findings.append(StandardFinding(
                            rule_name='sequelize-missing-transaction',
                            message=f"Multiple writes without transaction: {op1['func']} and {op2['func']}",
                            file_path=file,
                            line=op1['line'],
                            severity=Severity.HIGH,
                            category='orm-data-integrity',
                            snippet=f"Multiple operations at lines {op1['line']} and {op2['line']}",
                            confidence=Confidence.HIGH,
                            cwe_id='CWE-662'
                        ))
                        break  # One finding per cluster

    def _check_transaction_between(self, file: str, start_line: int, end_line: int) -> bool:
        """Check if there's a transaction between two lines."""
        # Fetch and filter in Python
        query = build_query('function_call_args', ['callee_function'],
                           where="file = ? AND line BETWEEN ? AND ?")
        self.cursor.execute(query, (file, start_line - 5, end_line + 5))

        for (callee,) in self.cursor.fetchall():
            if 'transaction' in callee.lower() or callee in ['t.commit', 't.rollback']:
                return True

        return False

    def _check_sql_injection(self):
        """Check for potential SQL injection vulnerabilities."""
        # Fetch all function_call_args, filter in Python
        query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                           order_by="file, line")
        self.cursor.execute(query)

        for file, line, func, args in self.cursor.fetchall():
            # Check if any raw query method is in callee_function
            func_lower = func.lower()
            if not any(method.lower() in func_lower for method in self.patterns.RAW_QUERY_METHODS):
                continue
            if not args:
                continue

            args_str = str(args)

            # Check for dangerous patterns
            has_injection = any(pattern in args_str for pattern in self.patterns.SQL_INJECTION_PATTERNS)

            # Higher severity for literal() as it's commonly misused
            is_literal = 'literal' in func.lower()

            if has_injection:
                self.findings.append(StandardFinding(
                    rule_name='sequelize-sql-injection',
                    message=f'Potential SQL injection in {func}',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL if is_literal else Severity.HIGH,
                    category='orm-security',
                    snippet=f'{func} with string concatenation',
                    confidence=Confidence.HIGH if is_literal else Confidence.MEDIUM,
                    cwe_id='CWE-89'
                ))

    def _check_excessive_eager_loading(self):
        """Check for excessive eager loading that could cause performance issues."""
        # Fetch all function_call_args, filter in Python
        query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                           order_by="file, line")
        self.cursor.execute(query)

        for file, line, method, args in self.cursor.fetchall():
            # Check for query methods and include keyword
            if not any(method.endswith(f'.{m}') for m in ['findAll', 'findOne', 'findAndCountAll']):
                continue
            if not args or 'include' not in str(args):
                continue

            args_str = str(args)

            # Count include depth and breadth
            include_count = args_str.count('include:')
            bracket_depth = args_str.count('[{')

            # Check for excessive includes
            if include_count > 3:
                self.findings.append(StandardFinding(
                    rule_name='sequelize-excessive-eager-loading',
                    message=f'Excessive eager loading: {include_count} includes in {method}',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category='orm-performance',
                    snippet=f'{method} with {include_count} associations',
                    confidence=Confidence.MEDIUM,
                    cwe_id='CWE-400'
                ))

            # Check for deeply nested includes
            if bracket_depth > 3:
                self.findings.append(StandardFinding(
                    rule_name='sequelize-deep-nesting',
                    message=f'Deeply nested includes in {method}',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category='orm-performance',
                    snippet=f'{method} with {bracket_depth} levels of nesting',
                    confidence=Confidence.LOW,
                    cwe_id='CWE-400'
                ))

    def _check_hard_deletes(self):
        """Check for hard deletes that bypass soft delete."""
        # Fetch all function_call_args, filter in Python
        query = build_query('function_call_args', ['file', 'line', 'callee_function', 'argument_expr'],
                           order_by="file, line")
        self.cursor.execute(query)

        for file, line, method, args in self.cursor.fetchall():
            # Check for destroy methods in Python
            if not (method.endswith('.destroy') or method.endswith('.bulkDestroy')):
                continue
            if args and 'paranoid: false' in str(args):
                self.findings.append(StandardFinding(
                    rule_name='sequelize-hard-delete',
                    message=f'Hard delete with paranoid:false in {method}',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category='orm-data-integrity',
                    snippet=f'{method}({{ paranoid: false }})',
                    confidence=Confidence.HIGH,
                    cwe_id='CWE-471'
                ))
            elif args and 'force: true' in str(args):
                self.findings.append(StandardFinding(
                    rule_name='sequelize-force-delete',
                    message=f'Force delete with force:true in {method}',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    category='orm-data-integrity',
                    snippet=f'{method}({{ force: true }})',
                    confidence=Confidence.HIGH,
                    cwe_id='CWE-471'
                ))

    def _check_raw_sql_bypass(self):
        """Check for raw SQL that bypasses ORM protections."""
        # Fetch all sql_queries with specified commands, filter file paths in Python
        query = build_query('sql_queries', ['file_path', 'line_number', 'query_text', 'command'],
                           where="command IN ('SELECT', 'INSERT', 'UPDATE', 'DELETE')",
                           order_by="file_path, line_number")
        self.cursor.execute(query)

        for file, line, query, command in self.cursor.fetchall():
            # Filter file paths in Python (skip migrations, seeds, non-JS files)
            if 'migration' in file.lower() or 'seed' in file.lower():
                continue
            if not file.endswith(('.js', '.mjs', '.cjs', '.ts')):
                continue
            # Check if it's likely a Sequelize raw query
            query_lower = query.lower()

            # Skip if it looks like Sequelize query
            if 'sequelize' in query_lower or 'replacements' in query_lower:
                continue

            self.findings.append(StandardFinding(
                rule_name='sequelize-bypass',
                message=f'Raw {command} query bypassing ORM',
                file_path=file,
                line=line,
                severity=Severity.LOW,
                category='orm-consistency',
                snippet=f'{command} query outside ORM',
                confidence=Confidence.LOW,
                cwe_id='CWE-213'
            ))


# ============================================================================
# MAIN RULE FUNCTION (Orchestrator Entry Point)
# ============================================================================

def analyze(context: StandardRuleContext) -> list[StandardFinding]:
    """Detect Sequelize ORM anti-patterns and performance issues.

    Args:
        context: Standardized rule context with database path

    Returns:
        List of Sequelize ORM issues found
    """
    analyzer = SequelizeAnalyzer(context)
    return analyzer.analyze()


# ============================================================================
# TAINT REGISTRATION (For Orchestrator)
# ============================================================================

def register_taint_patterns(taint_registry):
    """Register Sequelize-specific taint patterns.

    Args:
        taint_registry: TaintRegistry instance
    """
    patterns = SequelizePatterns()

    # Register raw query methods as SQL sinks
    for pattern in patterns.RAW_QUERY_METHODS:
        taint_registry.register_sink(pattern, 'sql', 'javascript')

    # Register Sequelize input sources
    SEQUELIZE_SOURCES = frozenset([
        'findAll', 'findOne', 'findByPk', 'findOrCreate',
        'where', 'attributes', 'order', 'group', 'having'
    ])

    for pattern in SEQUELIZE_SOURCES:
        taint_registry.register_source(pattern, 'user_input', 'javascript')

    # Register transaction methods as special sinks
    for pattern in patterns.TRANSACTION_METHODS:
        taint_registry.register_sink(pattern, 'transaction', 'javascript')