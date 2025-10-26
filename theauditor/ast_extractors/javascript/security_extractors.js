/**
 * Security Pattern Extractors
 *
 * SAST (Static Application Security Testing) pattern detection extractors.
 * These analyze code for security vulnerabilities and risky patterns.
 *
 * STABILITY: LOW - High churn rate, frequent pattern additions/refinements.
 * This is the most actively developed extraction domain.
 *
 * DEPENDENCIES: core_ast_extractors.js (uses functionCallArgs, symbols, assignments)
 * USED BY: Indexer for security pattern detection
 *
 * Architecture:
 * - Extracted from: js_helper_templates.py (refactored 2025-01-24)
 * - Pattern: Process data from core extractors to detect security issues
 * - Assembly: Concatenated after core_ast_extractors.js
 *
 * Functions (2 current + future growth):
 * 1. extractORMQueries() - Prisma/TypeORM/Sequelize query detection
 * 2. extractAPIEndpoints() - Express/Fastify/Koa endpoint detection
 *
 * FUTURE ADDITIONS (planned):
 * - extractJWTPatterns() - JWT usage and validation patterns
 * - extractSQLQueries() - Raw SQL query detection
 * - extractEnvironmentVariables() - Environment variable usage
 * - extractCryptoPatterns() - Cryptographic API usage
 * - extractAuthPatterns() - Authentication/authorization patterns
 * - extractXSSVectors() - Cross-site scripting vectors
 * - extractInjectionPoints() - Injection vulnerability detection
 *
 * Current size: 100 lines (2025-01-24)
 * Growth policy: If exceeds 1,200 lines, split by vulnerability type
 * (e.g., injection_patterns.js, auth_patterns.js, data_flow_patterns.js)
 */

function extractORMQueries(functionCallArgs) {
    const ORM_METHODS = new Set([
        'findAll', 'findOne', 'findByPk', 'create', 'update', 'destroy',
        'upsert', 'bulkCreate', 'count', 'max', 'min', 'sum',
        'findMany', 'findUnique', 'findFirst', 'createMany', 'updateMany',
        'deleteMany', 'aggregate', 'groupBy'
    ]);

    const queries = [];

    for (const call of functionCallArgs) {
        const method = call.callee_function ? call.callee_function.split('.').pop() : '';
        if (!ORM_METHODS.has(method)) continue;

        // Analyze first argument for options
        const hasIncludes = call.argument_expr && call.argument_expr.includes('include:');
        const hasLimit = call.argument_expr && (call.argument_expr.includes('limit:') || call.argument_expr.includes('take:'));

        queries.push({
            line: call.line,
            query_type: call.callee_function,
            includes: hasIncludes ? 'has_includes' : null,
            has_limit: hasLimit,
            has_transaction: false  // Could detect from caller_function
        });
    }

    return queries;
}

/**
 * Extract REST API endpoint definitions.
 * Detects: app.get, router.post, etc.
 * Implements Python's javascript.py:455-460, 1158-1263 route extraction.
 *
 * @param {Array} functionCallArgs - From extractFunctionCallArgs()
 * @returns {Array} - API endpoint records
 */
function extractAPIEndpoints(functionCallArgs) {
    const HTTP_METHODS = new Set(['get', 'post', 'put', 'delete', 'patch', 'head', 'options', 'all']);
    const endpoints = [];

    for (const call of functionCallArgs) {
        const callee = call.callee_function || '';
        if (!callee.includes('.')) continue;

        const parts = callee.split('.');
        const method = parts[parts.length - 1];

        if (!HTTP_METHODS.has(method)) continue;

        // First argument is typically the route path
        const route = call.argument_index === 0 ? call.argument_expr : null;

        // FIX: Add type check. If route path isn't a string, skip it
        // This prevents TypeError when route is a variable reference or non-string
        if (!route || typeof route !== 'string') continue;

        // Clean up route string
        let cleanRoute = route.replace(/['"]/g, '').trim();

        endpoints.push({
            line: call.line,
            method: method.toUpperCase(),
            route: cleanRoute,
            handler_function: call.caller_function,
            requires_auth: false  // Could detect from middleware analysis
        });
    }

    return endpoints;
}

/**
 * Extract validation framework usage (Zod, Joi, Yup, etc.)
 * Detects: schema.parseAsync(), schema.validate(), etc.
 *
 * PURPOSE: Enable taint analysis to recognize validation as sanitization
 *
 * @param {Array} functionCallArgs - From extractFunctionCallArgs()
 * @param {Array} assignments - Variable assignments for schema tracking
 * @param {Array} imports - Import statements to detect framework
 * @returns {Array} - Validation framework usage records
 */
function extractValidationFrameworkUsage(functionCallArgs, assignments, imports) {
    const validationCalls = [];

    // Debug logging helper
    const debugLog = (msg, data) => {
        if (process.env.THEAUDITOR_VALIDATION_DEBUG === '1') {
            console.error(`[VALIDATION-L2-EXTRACT] ${msg}`);
            if (data) {
                console.error(`[VALIDATION-L2-EXTRACT]   ${JSON.stringify(data)}`);
            }
        }
    };

    debugLog('Starting validation framework extraction', {
        functionCallArgs_count: functionCallArgs.length,
        assignments_count: assignments.length,
        imports_count: imports.length
    });

    // Step 1: Detect which validation frameworks are imported
    const frameworks = detectValidationFrameworks(imports, debugLog);
    debugLog(`Detected ${frameworks.length} validation frameworks in imports`, frameworks);

    if (frameworks.length === 0) {
        debugLog('No validation frameworks found, skipping extraction');
        return validationCalls;
    }

    // Step 2: Find schema variables (const userSchema = z.object(...))
    const schemaVars = findSchemaVariables(assignments, frameworks, debugLog);
    debugLog(`Found ${Object.keys(schemaVars).length} schema variables`, schemaVars);

    // Step 3: Find validation method calls
    for (const call of functionCallArgs) {
        const callee = call.callee_function || '';
        if (!callee) continue;

        // Check if this is a validation call
        const isValidation = isValidationCall(callee, frameworks, schemaVars);
        if (isValidation) {
            const validation = {
                line: call.line,
                framework: getFrameworkName(callee, frameworks, schemaVars),
                method: getMethodName(callee),
                variable_name: getVariableName(callee),
                is_validator: isValidatorMethod(callee),
                argument_expr: (call.argument_expr || '').substring(0, 200)  // Truncate long args
            };

            debugLog(`Extracted validation call at line ${call.line}`, validation);
            validationCalls.push(validation);
        }
    }

    debugLog(`Total validation calls extracted: ${validationCalls.length}`);
    return validationCalls;
}

// === HELPER FUNCTIONS ===

/**
 * Detect validation frameworks from imports
 */
function detectValidationFrameworks(imports, debugLog) {
    const VALIDATION_FRAMEWORKS = {
        'zod': ['z', 'zod', 'ZodSchema'],
        'joi': ['Joi', 'joi'],
        'yup': ['yup', 'Yup'],
        'ajv': ['Ajv', 'ajv'],
        'class-validator': ['validate', 'validateSync', 'validateOrReject'],
        'express-validator': ['validationResult', 'matchedData', 'checkSchema']
    };

    const detected = [];

    for (const imp of imports) {
        // Support both module_ref (old format) and module/value (new format)
        const moduleName = imp.module_ref || imp.module || imp.value || '';
        if (!moduleName) continue;

        for (const [framework, names] of Object.entries(VALIDATION_FRAMEWORKS)) {
            if (moduleName.includes(framework)) {
                const fw = { name: framework, importedNames: names };
                detected.push(fw);
                debugLog(`Detected framework import: ${framework}`, {
                    module: moduleName,
                    imported_names: names,
                    import_obj: imp
                });
                break;
            }
        }
    }

    return detected;
}

/**
 * Find schema variable declarations
 */
function findSchemaVariables(assignments, frameworks, debugLog) {
    const schemas = {};
    const SCHEMA_BUILDERS = ['object', 'string', 'number', 'array', 'boolean', 'date', 'enum', 'union', 'tuple'];

    for (const assign of assignments) {
        const target = assign.target_var;
        const source = assign.source_expr || '';

        // Look for: const userSchema = z.object(...)
        for (const fw of frameworks) {
            for (const name of fw.importedNames) {
                // Check if source expression uses schema builder
                for (const builder of SCHEMA_BUILDERS) {
                    if (source.includes(`${name}.${builder}`)) {
                        schemas[target] = { framework: fw.name };
                        debugLog(`Found schema variable: ${target}`, {
                            target_var: target,
                            framework: fw.name,
                            source_expr: source.substring(0, 100)
                        });
                        break;
                    }
                }
            }
        }
    }

    return schemas;
}

/**
 * Check if call is validation method
 * [MODIFIED] Relaxed logic to support imported schemas
 */
function isValidationCall(callee, frameworks, schemaVars) {
    // Pattern 1: Check if this file imports a validation framework
    // AND the call is to a known validation method.
    // This catches imported schemas (e.g., userSchema.parseAsync)
    if (frameworks.length > 0 && isValidatorMethod(callee)) {
        return true;
    }

    // Pattern 2: Direct framework call (z.parse, Joi.validate)
    // This is often caught by Pattern 1, but we keep it for robustness.
    for (const fw of frameworks) {
        for (const name of fw.importedNames) {
            if (callee.startsWith(`${name}.`) && isValidatorMethod(callee)) {
                return true;
            }
        }
    }

    // Pattern 3: Schema variable call defined in *this* file
    // (This is the original logic, kept as a fallback)
    if (callee.includes('.')) {
        const varName = callee.split('.')[0];
        if (varName in schemaVars && isValidatorMethod(callee)) {
            return true;
        }
    }

    return false;
}

/**
 * Check if method is validator (not schema builder)
 */
function isValidatorMethod(callee) {
    const VALIDATOR_METHODS = [
        'parse', 'parseAsync', 'safeParse', 'safeParseAsync',
        'validate', 'validateAsync', 'validateSync',
        'isValid', 'isValidSync'
    ];
    const method = callee.split('.').pop();
    return VALIDATOR_METHODS.includes(method);
}

/**
 * Get framework name from call
 * [MODIFIED] Deterministic framework detection - NO FALLBACKS
 */
function getFrameworkName(callee, frameworks, schemaVars) {
    // Check schema variables first (most specific)
    if (callee.includes('.')) {
        const varName = callee.split('.')[0];
        if (varName in schemaVars) {
            return schemaVars[varName].framework;
        }
    }

    // Check direct calls
    for (const fw of frameworks) {
        for (const name of fw.importedNames) {
            if (callee.startsWith(`${name}.`)) {
                return fw.name;
            }
        }
    }

    // If there's EXACTLY ONE framework imported, it must be that one
    // This is deterministic, not a fallback
    if (frameworks.length === 1) {
        return frameworks[0].name;
    }

    // If 0 or multiple frameworks, cannot determine - return unknown
    return 'unknown';
}

/**
 * Get method name from call
 */
function getMethodName(callee) {
    return callee.split('.').pop();
}

/**
 * Get variable name (or null for direct calls)
 */
function getVariableName(callee) {
    if (!callee.includes('.')) return null;
    const parts = callee.split('.');
    return parts.length > 1 ? parts[0] : null;
}

/**
 * Extract raw SQL queries from database execution calls.
 * Detects: db.execute, connection.query, pool.raw, etc.
 *
 * PURPOSE: Enable SQL injection detection for raw query strings
 *
 * @param {Array} functionCallArgs - From extractFunctionCallArgs()
 * @returns {Array} - SQL query records
 */
function extractSQLQueries(functionCallArgs) {
    const SQL_METHODS = new Set([
        'execute', 'query', 'raw', 'exec', 'run',
        'executeSql', 'executeQuery', 'execSQL', 'select',
        'insert', 'update', 'delete', 'query_raw'
    ]);

    const queries = [];

    for (const call of functionCallArgs) {
        const callee = call.callee_function || '';

        // Check if method name matches SQL execution pattern
        // Handle both db.query and query (direct import)
        const methodName = callee.includes('.') ? callee.split('.').pop() : callee;
        if (!SQL_METHODS.has(methodName)) continue;

        // Only check first argument (SQL query string)
        if (call.argument_index !== 0) continue;

        const argExpr = call.argument_expr || '';
        if (!argExpr) continue;

        // Check if it looks like SQL (contains SQL keywords)
        const upperArg = argExpr.toUpperCase();
        if (!['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER'].some(kw => upperArg.includes(kw))) {
            continue;
        }

        // Resolve query text from argument expression
        const queryText = resolveSQLLiteral(argExpr);
        if (!queryText) continue;

        // Build query record (Python will parse with sqlparse)
        queries.push({
            line: call.line,
            query_text: queryText.substring(0, 1000)  // Truncate long queries
            // NOTE: command and tables will be parsed by Python using sqlparse
            // We just extract the raw text here
        });
    }

    return queries;
}

/**
 * Resolve SQL literal from argument expression string.
 * Handles:
 * - Plain strings: 'SELECT * FROM users'
 * - Template literals WITHOUT interpolation: `SELECT * FROM users`
 * - Template literals WITH interpolation: SKIP (can't analyze)
 *
 * @param {string} argExpr - Argument expression string
 * @returns {string|null} - Resolved SQL text or null if dynamic
 */
function resolveSQLLiteral(argExpr) {
    const trimmed = argExpr.trim();

    // Plain string (single or double quotes)
    if ((trimmed.startsWith('"') && trimmed.endsWith('"')) ||
        (trimmed.startsWith("'") && trimmed.endsWith("'"))) {
        return trimmed.slice(1, -1);
    }

    // Template literal
    if (trimmed.startsWith('`') && trimmed.endsWith('`')) {
        // Check for interpolation
        if (trimmed.includes('${')) {
            // Dynamic interpolation - can't analyze
            return null;
        }

        // Static template literal - unescape and return
        let unescaped = trimmed.slice(1, -1);  // Remove backticks
        unescaped = unescaped.replace(/\\`/g, '`').replace(/\\\\/g, '\\');
        return unescaped;
    }

    // Complex expression (variable, concatenation, etc.) - can't analyze
    return null;
}