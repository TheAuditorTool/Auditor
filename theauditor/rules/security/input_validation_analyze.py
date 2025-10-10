"""Input Validation Analyzer - Schema Contract Compliant Implementation.

Detects input validation vulnerabilities including validation bypasses,
type confusion, prototype pollution, and framework-specific issues using
ONLY indexed database data. NO AST traversal. NO file I/O. Pure SQL queries.

Follows v1.1+ schema contract compliance:
- Frozensets for all patterns (O(1) lookups)
- Direct database queries (assumes all tables exist per schema contract)
- Uses parameterized queries (no SQL injection)
- Proper confidence levels
"""

import sqlite3
import json
from typing import List, Dict, Set, Optional
from dataclasses import dataclass

from theauditor.rules.base import StandardRuleContext, StandardFinding, Severity, Confidence, RuleMetadata

METADATA = RuleMetadata(
    name="input_validation",
    category="security",
    target_extensions=['.py', '.js', '.ts'],
    exclude_patterns=['test/', 'spec.', '__tests__'],
    requires_jsx_pass=False
)


# ============================================================================
# PATTERN DEFINITIONS (Golden Standard: Frozen Dataclass)
# ============================================================================

@dataclass(frozen=True)
class ValidationPatterns:
    """Immutable pattern definitions for input validation detection."""

    # Validation functions by framework
    VALIDATION_FUNCTIONS = frozenset([
        # Generic
        'validate', 'verify', 'sanitize', 'clean', 'check',
        'isValid', 'isEmail', 'isURL', 'isAlphanumeric',
        # Joi
        'joi.validate', 'schema.validate', 'joi.assert', 'joi.attempt',
        # Yup
        'yup.validate', 'schema.validateSync', 'yup.reach', 'yup.cast',
        # Zod
        'z.parse', 'schema.parse', 'schema.safeParse', 'z.string',
        # Express-validator
        'validationResult', 'checkSchema', 'check', 'body',
        # Class-validator
        'validateOrReject', 'validateSync', 'validator.validate',
        # Ajv
        'ajv.compile', 'ajv.validate', 'schema.validate'
    ])

    # Dangerous merge functions (prototype pollution)
    MERGE_FUNCTIONS = frozenset([
        'Object.assign', 'merge', 'extend', 'deepMerge', 'deepExtend',
        '_.merge', '_.extend', '_.assign', '_.defaults',
        'jQuery.extend', '$.extend', 'angular.merge', 'angular.extend',
        'Object.setPrototypeOf', 'Reflect.setPrototypeOf',
        'lodash.merge', 'lodash.assign', 'deep-extend', 'node-extend'
    ])

    # NoSQL operators that bypass validation
    NOSQL_OPERATORS = frozenset([
        '$ne', '$gt', '$lt', '$gte', '$lte',
        '$in', '$nin', '$exists', '$regex', '$not',
        '$where', '$expr', '$jsonSchema', '$text',
        '$or', '$and', '$nor', '$elemMatch'
    ])

    # Template engines (SSTI risk)
    TEMPLATE_ENGINES = frozenset([
        'render', 'compile', 'renderFile', 'renderString',
        'ejs.render', 'ejs.renderFile', 'ejs.compile',
        'pug.render', 'pug.renderFile', 'pug.compile',
        'handlebars.compile', 'hbs.compile', 'hbs.renderView',
        'mustache.render', 'mustache.compile',
        'nunjucks.render', 'nunjucks.renderString',
        'jade.render', 'jade.compile', 'jade.renderFile',
        'doT.template', 'dust.render', 'swig.render'
    ])

    # Type check functions (bypass indicators)
    TYPE_CHECKS = frozenset([
        'typeof', 'instanceof', 'constructor',
        'Array.isArray', 'Number.isInteger', 'Number.isNaN',
        'isNaN', 'isFinite', 'Object.prototype.toString'
    ])

    # GraphQL operations
    GRAPHQL_OPS = frozenset([
        'graphql', 'execute', 'graphqlHTTP', 'GraphQLSchema',
        'apollo-server', 'graphql-yoga', 'makeExecutableSchema',
        'buildSchema', 'parse', 'parseValue', 'graphql-tag'
    ])

    # Database write operations
    DB_WRITE_OPS = frozenset([
        'create', 'insert', 'update', 'save', 'upsert',
        'findOneAndUpdate', 'findByIdAndUpdate', 'updateOne',
        'updateMany', 'bulkWrite', 'bulkCreate', 'insertMany'
    ])

    # User input sources
    INPUT_SOURCES = frozenset([
        'req.body', 'req.query', 'req.params', 'request.body',
        'request.query', 'request.params', 'ctx.request.body',
        'ctx.query', 'ctx.params', 'event.body', 'event.queryStringParameters'
    ])

    # Dangerous sinks
    DANGEROUS_SINKS = frozenset([
        'eval', 'Function', 'exec', 'spawn', 'execFile',
        'vm.runInContext', 'vm.runInNewContext', 'require',
        'setTimeout', 'setInterval', 'setImmediate'
    ])

    # ORM methods that need validation
    ORM_METHODS = frozenset([
        'findOne', 'find', 'findAll', 'findById', 'findByPk',
        'where', 'query', 'raw', 'sequelize.query', 'knex.raw',
        'mongoose.find', 'typeorm.query'
    ])

    # Common weak validation patterns
    WEAK_PATTERNS = frozenset([
        'return true', 'return 1', '() => true',
        'validate: true', 'required: false', 'optional: true'
    ])


# ============================================================================
# ANALYZER CLASS (Golden Standard)
# ============================================================================

class InputValidationAnalyzer:
    """Analyzer for input validation vulnerabilities."""

    def __init__(self, context: StandardRuleContext):
        """Initialize analyzer with database context.

        Args:
            context: Rule context containing database path
        """
        self.context = context
        self.patterns = ValidationPatterns()
        self.findings = []
        self.seen_issues = set()  # Deduplication

    def analyze(self) -> List[StandardFinding]:
        """Main analysis entry point.

        Returns:
            List of input validation vulnerabilities found
        """
        if not self.context.db_path:
            return []

        conn = sqlite3.connect(self.context.db_path)
        self.cursor = conn.cursor()

        try:
            # Direct execution - schema contract guarantees table existence
            # Priority 1: Database Direct (High Confidence)
            self._detect_prototype_pollution()
            self._detect_nosql_injection()
            self._detect_missing_validation()
            self._detect_template_injection()
            self._detect_type_confusion()

            # Priority 2: Cross-Reference (Medium Confidence)
            self._detect_incomplete_validation()
            self._detect_schema_bypass()
            self._detect_validation_library_misuse()
            self._detect_framework_bypasses()
            self._detect_graphql_injection()

            # Priority 3: Advanced (Variable Confidence)
            self._detect_second_order_injection()
            self._detect_business_logic_bypass()
            self._detect_path_traversal()
            self._detect_type_juggling()
            self._detect_orm_injection()

        finally:
            conn.close()

        return self.findings

    def _add_finding(self, rule_name: str, message: str, file: str, line: int,
                    severity: Severity, confidence: Confidence,
                    cwe_id: str, snippet: str = ""):
        """Add finding with deduplication."""
        issue_key = f"{file}:{line}:{rule_name}"
        if issue_key not in self.seen_issues:
            self.seen_issues.add(issue_key)
            self.findings.append(StandardFinding(
                rule_name=rule_name,
                message=message,
                file_path=file,
                line=line,
                severity=severity,
                category='input-validation',
                snippet=snippet,
                confidence=confidence,
                cwe_id=cwe_id
            ))

    # ========================================================================
    # PRIORITY 1: Database Direct Detection (High Confidence)
    # ========================================================================

    def _detect_prototype_pollution(self):
        """Detect prototype pollution vulnerabilities."""
        for merge_func in self.patterns.MERGE_FUNCTIONS:
            self.cursor.execute("""
                SELECT file, line, callee_function, argument_expr
                FROM function_call_args
                WHERE callee_function LIKE ?
                  AND (argument_expr LIKE '%req.body%'
                       OR argument_expr LIKE '%request.body%'
                       OR argument_expr LIKE '%ctx.request.body%'
                       OR argument_expr LIKE '%userInput%'
                       OR argument_expr LIKE '%data%')
                ORDER BY file, line
            """, (f'%{merge_func}%',))

            for file, line, func, args in self.cursor.fetchall():
                # Check if first argument is a config object
                if args and any(x in str(args).lower() for x in ['config', 'settings', 'options', '{}']):
                    self._add_finding(
                        rule_name='prototype-pollution',
                        message=f'Prototype pollution risk via {func} with user input',
                        file=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        confidence=Confidence.HIGH,
                        cwe_id='CWE-1321',  # Improperly Controlled Modification of Object Prototype
                        snippet=f'{func}({args[:50]}...)'
                    )

    def _detect_nosql_injection(self):
        """Detect NoSQL injection vulnerabilities."""
        # Check for NoSQL operators in assignments
        for operator in self.patterns.NOSQL_OPERATORS:
            self.cursor.execute("""
                SELECT file, line, target_var, source_expr
                FROM assignments
                WHERE source_expr LIKE ?
                  AND (source_expr LIKE '%req.%'
                       OR source_expr LIKE '%request.%'
                       OR source_expr LIKE '%body%'
                       OR source_expr LIKE '%query%'
                       OR source_expr LIKE '%params%')
                ORDER BY file, line
            """, (f'%{operator}%',))

            for file, line, var, expr in self.cursor.fetchall():
                self._add_finding(
                    rule_name='nosql-injection',
                    message=f'NoSQL operator "{operator}" detected with user input',
                    file=file,
                    line=line,
                    severity=Severity.HIGH,
                    confidence=Confidence.HIGH,
                    cwe_id='CWE-943',  # Improper Neutralization of Special Elements in Data Query Logic
                    snippet=f'{var} = {expr[:50]}'
                )

        # Check function calls with NoSQL operators
        self.cursor.execute("""
                SELECT file, line, callee_function, argument_expr
                FROM function_call_args
                WHERE (callee_function LIKE '%.find%'
                       OR callee_function LIKE '%.update%'
                       OR callee_function LIKE '%.delete%')
                  AND argument_expr LIKE '%$%'
                ORDER BY file, line
            """)

        for file, line, func, args in self.cursor.fetchall():
            if args and any(op in str(args) for op in self.patterns.NOSQL_OPERATORS):
                self._add_finding(
                    rule_name='nosql-injection-query',
                    message=f'NoSQL injection in {func} with operators in query',
                    file=file,
                    line=line,
                    severity=Severity.HIGH,
                    confidence=Confidence.MEDIUM,
                    cwe_id='CWE-943',
                    snippet=f'{func}({args[:50]})'
                )

    def _detect_missing_validation(self):
        """Detect database operations without validation."""
        # Find DB operations with direct user input
        for db_op in self.patterns.DB_WRITE_OPS:
            self.cursor.execute("""
                SELECT file, line, callee_function, argument_expr
                FROM function_call_args
                WHERE callee_function LIKE ?
                  AND (argument_expr LIKE '%req.body%'
                       OR argument_expr LIKE '%req.query%'
                       OR argument_expr LIKE '%req.params%'
                       OR argument_expr LIKE '%request.body%'
                       OR argument_expr LIKE '%request.query%')
                ORDER BY file, line
            """, (f'%.{db_op}%',))

            for file, line, func, args in self.cursor.fetchall():
                # Check if validation exists nearby
                has_validation = self._check_validation_nearby(file, line)

                if not has_validation:
                    self._add_finding(
                        rule_name='missing-validation',
                        message=f'Database operation {func} with unvalidated user input',
                        file=file,
                        line=line,
                        severity=Severity.HIGH,
                        confidence=Confidence.MEDIUM,
                        cwe_id='CWE-20',  # Improper Input Validation
                        snippet=f'{func}({args[:50]})'
                    )

    def _detect_template_injection(self):
        """Detect server-side template injection vulnerabilities."""
        for template_func in self.patterns.TEMPLATE_ENGINES:
            self.cursor.execute("""
                SELECT file, line, callee_function, argument_expr
                FROM function_call_args
                WHERE callee_function LIKE ?
                  AND (argument_expr LIKE '%req.%'
                       OR argument_expr LIKE '%request.%'
                       OR argument_expr LIKE '%userInput%'
                       OR argument_expr LIKE '%body%'
                       OR argument_expr LIKE '%query%')
                ORDER BY file, line
            """, (f'%{template_func}%',))

            for file, line, func, args in self.cursor.fetchall():
                # Higher severity for compile functions
                is_compile = 'compile' in func.lower()

                self._add_finding(
                    rule_name='template-injection',
                    message=f'Template injection risk in {func} with user input',
                    file=file,
                    line=line,
                    severity=Severity.CRITICAL if is_compile else Severity.HIGH,
                    confidence=Confidence.HIGH,
                    cwe_id='CWE-1336',  # Improper Restriction of Template Inputs
                    snippet=f'{func}({args[:50]})'
                )

    def _detect_type_confusion(self):
        """Detect type confusion vulnerabilities."""
        # Find typeof checks that can be bypassed
        self.cursor.execute("""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE (source_expr LIKE '%typeof %'
                   AND (source_expr LIKE '%=== "string"%'
                        OR source_expr LIKE '%=== "number"%'
                        OR source_expr LIKE '%=== "boolean"%'))
               OR source_expr LIKE '%instanceof %'
            ORDER BY file, line
        """)

        for file, line, var, expr in self.cursor.fetchall():
            # Check if this is validating user input
            if any(src in expr for src in self.patterns.INPUT_SOURCES):
                self._add_finding(
                    rule_name='type-confusion',
                    message='Type check can be bypassed with arrays or objects',
                    file=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    confidence=Confidence.HIGH,
                    cwe_id='CWE-843',  # Access of Resource Using Incompatible Type
                    snippet=f'{var} = {expr[:50]}'
                )

    # ========================================================================
    # PRIORITY 2: Cross-Reference Detection (Medium Confidence)
    # ========================================================================

    def _detect_incomplete_validation(self):
        """Detect validation that doesn't cover all fields."""
        # Find validation followed by dangerous operations
        self.cursor.execute("""
            SELECT f1.file, f1.line, f1.callee_function, f2.callee_function, f2.line
            FROM function_call_args f1
            JOIN function_call_args f2 ON f1.file = f2.file
            WHERE f1.callee_function IN ({})
              AND f2.callee_function IN ({})
              AND f2.line > f1.line
              AND f2.line - f1.line <= 20
            ORDER BY f1.file, f1.line
        """.format(
            ','.join('?' * len(self.patterns.VALIDATION_FUNCTIONS)),
            ','.join('?' * len(self.patterns.DB_WRITE_OPS))
        ), tuple(self.patterns.VALIDATION_FUNCTIONS) + tuple(self.patterns.DB_WRITE_OPS))

        for file, val_line, val_func, db_func, db_line in self.cursor.fetchall():
            self._add_finding(
                rule_name='incomplete-validation',
                message=f'Validation at line {val_line} may not cover all fields used in {db_func}',
                file=file,
                line=val_line,
                severity=Severity.MEDIUM,
                confidence=Confidence.MEDIUM,
                cwe_id='CWE-20',
                snippet=f'{val_func} -> {db_func}'
            )

    def _detect_schema_bypass(self):
        """Detect validation that allows additional properties."""
        # Look for spread operators after validation
        self.cursor.execute("""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE (callee_function LIKE '%.create%'
                   OR callee_function LIKE '%.update%')
              AND (argument_expr LIKE '%...%'
                   OR argument_expr LIKE '%Object.assign%'
                   OR argument_expr LIKE '%spread%')
            ORDER BY file, line
        """)

        for file, line, func, args in self.cursor.fetchall():
            if '...' in str(args):
                self._add_finding(
                    rule_name='schema-bypass',
                    message='Spread operator may allow additional properties to bypass validation',
                    file=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    confidence=Confidence.MEDIUM,
                    cwe_id='CWE-915',  # Improperly Controlled Modification of Dynamically-Determined Object Attributes
                    snippet=f'{func}({args[:50]})'
                )

    def _detect_validation_library_misuse(self):
        """Detect common validation library misconfigurations."""
        # Check for weak validation patterns
        self.cursor.execute("""
            SELECT file, line, callee_function, argument_expr
            FROM function_call_args
            WHERE callee_function IN ({})
              AND (argument_expr LIKE '%required: false%'
                   OR argument_expr LIKE '%optional: true%'
                   OR argument_expr LIKE '%allowUnknown: true%'
                   OR argument_expr LIKE '%stripUnknown: false%')
            ORDER BY file, line
        """.format(','.join('?' * len(self.patterns.VALIDATION_FUNCTIONS))),
        tuple(self.patterns.VALIDATION_FUNCTIONS))

        for file, line, func, args in self.cursor.fetchall():
            config_issue = 'Unknown properties allowed' if 'allowUnknown' in str(args) else 'Weak validation config'

            self._add_finding(
                rule_name='validation-misconfiguration',
                message=f'{config_issue} in {func}',
                file=file,
                line=line,
                severity=Severity.MEDIUM,
                confidence=Confidence.HIGH,
                cwe_id='CWE-20',
                snippet=f'{func}({args[:50]})'
            )

    def _detect_framework_bypasses(self):
        """Detect framework-specific validation bypasses."""
        # Check for endpoints without middleware
        self.cursor.execute("""
            SELECT file, method, pattern, controls
            FROM api_endpoints
            WHERE (method IN ('POST', 'PUT', 'PATCH', 'DELETE'))
              AND (controls IS NULL
                   OR controls = '[]'
                   OR controls = '')
            ORDER BY file, pattern
        """)

        for file, method, route, controls in self.cursor.fetchall():
            # Extract line number from file if possible
            line = 1  # Default line

            self._add_finding(
                rule_name='missing-middleware',
                message=f'{method} endpoint {route} has no validation middleware',
                file=file,
                line=line,
                severity=Severity.HIGH,
                confidence=Confidence.MEDIUM,
                cwe_id='CWE-20',
                snippet=f'{method} {route}'
            )

    def _detect_graphql_injection(self):
        """Detect GraphQL injection vulnerabilities."""
        for graphql_func in self.patterns.GRAPHQL_OPS:
            self.cursor.execute("""
                SELECT file, line, callee_function, argument_expr
                FROM function_call_args
                WHERE callee_function LIKE ?
                  AND (argument_expr LIKE '%req.body.query%'
                       OR argument_expr LIKE '%request.body.query%'
                       OR argument_expr LIKE '%userQuery%')
                ORDER BY file, line
            """, (f'%{graphql_func}%',))

            for file, line, func, args in self.cursor.fetchall():
                self._add_finding(
                    rule_name='graphql-injection',
                    message=f'GraphQL injection risk in {func} with user-provided query',
                    file=file,
                    line=line,
                    severity=Severity.HIGH,
                    confidence=Confidence.MEDIUM,
                    cwe_id='CWE-20',
                    snippet=f'{func}({args[:50]})'
                )

    # ========================================================================
    # PRIORITY 3: Advanced Detection (Variable Confidence)
    # ========================================================================

    def _detect_second_order_injection(self):
        """Detect second-order injection vulnerabilities."""
        # Find data retrieved from DB and used without validation
        self.cursor.execute("""
            SELECT a.file, a.line, a.target_var, f.callee_function, f.line
            FROM assignments a
            JOIN function_call_args f ON a.file = f.file
            WHERE a.source_expr LIKE '%.find%'
              AND f.argument_expr LIKE '%' || a.target_var || '%'
              AND f.callee_function IN ({})
              AND f.line > a.line
              AND f.line - a.line <= 50
            ORDER BY a.file, a.line
        """.format(','.join('?' * len(self.patterns.TEMPLATE_ENGINES))),
        tuple(self.patterns.TEMPLATE_ENGINES))

        for file, retrieve_line, var, use_func, use_line in self.cursor.fetchall():
            self._add_finding(
                rule_name='second-order-injection',
                message=f'Data from database used in {use_func} without revalidation',
                file=file,
                line=use_line,
                severity=Severity.MEDIUM,
                confidence=Confidence.LOW,
                cwe_id='CWE-20',
                snippet=f'{var} used in {use_func}'
            )

    def _detect_business_logic_bypass(self):
        """Detect business logic validation issues."""
        # Find negative number checks
        self.cursor.execute("""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE (target_var LIKE '%amount%'
                   OR target_var LIKE '%quantity%'
                   OR target_var LIKE '%price%'
                   OR target_var LIKE '%balance%')
              AND (source_expr LIKE '%req.%'
                   OR source_expr LIKE '%request.%')
            ORDER BY file, line
        """)

        for file, line, var, expr in self.cursor.fetchall():
            # Check if there's a negative check nearby
            self.cursor.execute("""
                SELECT COUNT(*) FROM assignments
                WHERE file = ?
                  AND ABS(line - ?) <= 10
                  AND (source_expr LIKE '%< 0%'
                       OR source_expr LIKE '%<= 0%'
                       OR source_expr LIKE '%Math.abs%'
                       OR source_expr LIKE '%Math.max%')
            """, (file, line))

            if self.cursor.fetchone()[0] == 0:
                self._add_finding(
                    rule_name='business-logic-bypass',
                    message=f'Numeric value {var} not validated for negative amounts',
                    file=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    confidence=Confidence.LOW,
                    cwe_id='CWE-20',
                    snippet=f'{var} = {expr[:50]}'
                )

    def _detect_path_traversal(self):
        """Detect path traversal vulnerabilities."""
        # Find file operations with user input
        self.cursor.execute("""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE (source_expr LIKE '%req.%filename%'
                   OR source_expr LIKE '%req.%path%'
                   OR source_expr LIKE '%req.%file%')
              AND (target_var LIKE '%path%'
                   OR target_var LIKE '%file%'
                   OR target_var LIKE '%dir%')
            ORDER BY file, line
        """)

        for file, line, var, expr in self.cursor.fetchall():
            # Check for ../ filtering
            if '../' not in expr and '..' not in expr:
                self._add_finding(
                    rule_name='path-traversal',
                    message=f'Path variable {var} from user input without traversal check',
                    file=file,
                    line=line,
                    severity=Severity.HIGH,
                    confidence=Confidence.LOW,
                    cwe_id='CWE-22',  # Path Traversal
                    snippet=f'{var} = {expr[:50]}'
                )

    def _detect_type_juggling(self):
        """Detect type juggling vulnerabilities."""
        # Find loose equality checks
        self.cursor.execute("""
            SELECT file, line, target_var, source_expr
            FROM assignments
            WHERE (source_expr LIKE '%==%' AND source_expr NOT LIKE '%===%')
              AND (source_expr LIKE '%true%'
                   OR source_expr LIKE '%false%'
                   OR source_expr LIKE '%admin%'
                   OR source_expr LIKE '%role%')
            ORDER BY file, line
        """)

        for file, line, var, expr in self.cursor.fetchall():
            self._add_finding(
                rule_name='type-juggling',
                message='Loose equality (==) can cause type juggling vulnerabilities',
                file=file,
                line=line,
                severity=Severity.MEDIUM,
                confidence=Confidence.MEDIUM,
                cwe_id='CWE-697',  # Incorrect Comparison
                snippet=f'{var} = {expr[:50]}'
            )

    def _detect_orm_injection(self):
        """Detect ORM-specific injection vulnerabilities."""
        # Check for raw queries with user input
        for orm_method in self.patterns.ORM_METHODS:
            self.cursor.execute("""
                SELECT file, line, callee_function, argument_expr
                FROM function_call_args
                WHERE callee_function LIKE ?
                  AND (argument_expr LIKE '%req.%'
                       OR argument_expr LIKE '%request.%'
                       OR argument_expr LIKE '%+%'
                       OR argument_expr LIKE '%`%')
                ORDER BY file, line
            """, (f'%{orm_method}%',))

            for file, line, func, args in self.cursor.fetchall():
                # Check for string concatenation
                if args and ('+' in str(args) or '`' in str(args)):
                    self._add_finding(
                        rule_name='orm-injection',
                        message=f'ORM injection risk in {func} with string concatenation',
                        file=file,
                        line=line,
                        severity=Severity.HIGH,
                        confidence=Confidence.MEDIUM,
                        cwe_id='CWE-89',  # SQL Injection
                        snippet=f'{func}({args[:50]})'
                    )

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _check_validation_nearby(self, file: str, line: int) -> bool:
        """Check if validation exists near a line."""
        # Check for validation calls within 20 lines before
        validation_funcs = tuple(self.patterns.VALIDATION_FUNCTIONS)
        placeholders = ','.join('?' * len(validation_funcs))

        self.cursor.execute(f"""
            SELECT COUNT(*) FROM function_call_args
            WHERE file = ?
              AND line BETWEEN ? AND ?
              AND callee_function IN ({placeholders})
        """, (file, line - 20, line) + validation_funcs)

        return self.cursor.fetchone()[0] > 0


# ============================================================================
# MAIN RULE FUNCTION (Orchestrator Entry Point)
# ============================================================================

def find_input_validation_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect input validation vulnerabilities.

    Detects:
    - Prototype pollution
    - NoSQL injection
    - Template injection
    - Type confusion
    - Validation bypasses
    - Framework-specific issues
    - ORM injection patterns

    Args:
        context: Standardized rule context with database path

    Returns:
        List of input validation vulnerabilities found
    """
    analyzer = InputValidationAnalyzer(context)
    return analyzer.analyze()


# ============================================================================
# TAINT REGISTRATION (For Orchestrator)
# ============================================================================

def register_taint_patterns(taint_registry):
    """Register input validation taint patterns.

    Args:
        taint_registry: TaintRegistry instance
    """
    patterns = ValidationPatterns()

    # Register input sources
    for source in patterns.INPUT_SOURCES:
        taint_registry.register_source(source, 'user_input', 'javascript')

    # Register dangerous sinks
    for sink in patterns.DANGEROUS_SINKS:
        taint_registry.register_sink(sink, 'code_execution', 'javascript')

    # Register template engines as sinks
    for template in patterns.TEMPLATE_ENGINES:
        taint_registry.register_sink(template, 'template_injection', 'javascript')

    # Register merge functions as potential pollution sinks
    for merge in patterns.MERGE_FUNCTIONS:
        taint_registry.register_sink(merge, 'prototype_pollution', 'javascript')