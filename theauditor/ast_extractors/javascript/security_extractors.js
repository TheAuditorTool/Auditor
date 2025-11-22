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
 * Extract REST API endpoint definitions AND middleware chains.
 * Detects: app.get, router.post, etc.
 * Implements Python's javascript.py:455-460, 1158-1263 route extraction.
 *
 * PHASE 5 ENHANCEMENT:
 * - Captures ALL route handler arguments (not just route path at index 0)
 * - Extracts middleware execution chain: router.METHOD(path, mw1, mw2, controller)
 * - Returns BOTH endpoint records (for api_endpoints table) AND middleware chain records
 *   (for express_middleware_chains table)
 *
 * @param {Array} functionCallArgs - From extractFunctionCallArgs()
 * @returns {Object} - { endpoints: Array, middlewareChains: Array }
 */
function extractAPIEndpoints(functionCallArgs) {
    const HTTP_METHODS = new Set(['get', 'post', 'put', 'delete', 'patch', 'head', 'options', 'all']);
    const endpoints = [];
    const middlewareChains = [];

    // STEP 1: Group function calls by line number
    // Same router.METHOD(...) call creates multiple functionCallArgs records (one per argument)
    // We must group them to process each route definition as a single unit
    const callsByLine = {};

    for (const call of functionCallArgs) {
        const callee = call.callee_function || '';
        if (!callee.includes('.')) continue;

        const parts = callee.split('.');
        const method = parts[parts.length - 1];

        if (!HTTP_METHODS.has(method)) continue;

        // Group by line number
        if (!callsByLine[call.line]) {
            callsByLine[call.line] = {
                method: method,
                callee: callee,
                caller_function: call.caller_function,
                calls: []
            };
        }
        callsByLine[call.line].calls.push(call);
    }

    // STEP 2: Process each route definition
    for (const [line, data] of Object.entries(callsByLine)) {
        const { method, callee, caller_function, calls } = data;

        // Sort by argument_index to get deterministic execution order
        calls.sort((a, b) => a.argument_index - b.argument_index);

        // STEP 3: Extract route path (argument 0)
        const routeArg = calls.find(c => c.argument_index === 0);
        if (!routeArg) continue;

        const route = routeArg.argument_expr;
        if (!route || typeof route !== 'string') continue;

        let cleanRoute = route.replace(/['"]/g, '').trim();

        // STEP 4: Extract endpoint record (for api_endpoints table)
        endpoints.push({
            line: parseInt(line),
            method: method.toUpperCase(),
            route: cleanRoute,
            handler_function: caller_function,
            requires_auth: false
        });

        // STEP 5: Extract middleware chain (arguments 1 to N-1)
        // Pattern: router.post('/', middleware1, middleware2, controller)
        //   arg0: '/'           ← route path (processed above)
        //   arg1: middleware1   ← execution_order = 1
        //   arg2: middleware2   ← execution_order = 2
        //   arg3: controller    ← execution_order = 3, handler_type = 'controller'
        for (let i = 1; i < calls.length; i++) {
            const call = calls[i];

            // Determine handler type: last argument is controller, others are middleware
            const isController = i === calls.length - 1;

            middlewareChains.push({
                route_line: parseInt(line),
                route_path: cleanRoute,
                route_method: method.toUpperCase(),
                execution_order: i,  // 1, 2, 3... (after route path at 0)
                handler_expr: call.argument_expr || '',
                handler_type: isController ? 'controller' : 'middleware'
            });
        }
    }

    // STEP 6: Return both datasets
    return { endpoints, middlewareChains };
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
                function_name: callee,  // Full callee for database (e.g., 'userSchema.parseAsync')
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

/**
 * Extract schema definitions (Zod, Joi, Yup schema builders)
 * Detects: z.object(), z.string(), Joi.number(), etc.
 *
 * PURPOSE: Track schema DEFINITIONS for coverage metrics (separate from validation USAGE)
 *
 * ARCHITECTURAL DECISION (2025-11-09):
 * Validation extraction was split into TWO concerns:
 * 1. extractValidationFrameworkUsage() - Tracks where validation is APPLIED (parseAsync, validate)
 *    - is_validator=TRUE
 *    - Used by: Taint analysis for sanitization tracking
 * 2. extractSchemaDefinitions() - Tracks where schemas are DEFINED (z.object, z.string)
 *    - is_validator=FALSE
 *    - Used by: Coverage metrics, schema inventory
 *
 * Both write to the SAME table (validation_framework_usage) differentiated by is_validator flag.
 * Schema already supported this via is_validator column (node_schema.py:544).
 *
 * @param {Array} functionCallArgs - From extractFunctionCallArgs()
 * @param {Array} assignments - Variable assignments (not currently used, reserved for future)
 * @param {Array} imports - Import statements to detect framework
 * @returns {Array} - Schema definition records (is_validator=false)
 */
function extractSchemaDefinitions(functionCallArgs, assignments, imports) {
    const schemaDefs = [];

    // Debug logging helper (reuse pattern from extractValidationFrameworkUsage)
    const debugLog = (msg, data) => {
        if (process.env.THEAUDITOR_VALIDATION_DEBUG === '1') {
            console.error(`[SCHEMA-DEF-EXTRACT] ${msg}`);
            if (data) {
                console.error(`[SCHEMA-DEF-EXTRACT]   ${JSON.stringify(data)}`);
            }
        }
    };

    debugLog('Starting schema definition extraction', {
        functionCallArgs_count: functionCallArgs.length,
        imports_count: imports.length
    });

    // Step 1: Detect which validation frameworks are imported
    const frameworks = detectValidationFrameworks(imports, debugLog);
    debugLog(`Detected ${frameworks.length} validation frameworks in imports`, frameworks);

    if (frameworks.length === 0) {
        debugLog('No validation frameworks found, skipping extraction');
        return schemaDefs;
    }

    // Step 2: Define schema builder methods for each framework
    // These are the DEFINITION methods (z.object, z.string) NOT validator methods (parse, validate)
    const SCHEMA_BUILDERS = {
        // Zod builders
        'zod': [
            'object', 'string', 'number', 'array', 'boolean', 'date', 'enum', 'union', 'tuple',
            'record', 'map', 'set', 'promise', 'function', 'lazy', 'literal', 'void', 'undefined',
            'null', 'any', 'unknown', 'never', 'instanceof', 'discriminatedUnion', 'intersection',
            'optional', 'nullable', 'coerce', 'nativeEnum', 'bigint', 'nan'
        ],
        // Joi builders
        'joi': [
            'object', 'string', 'number', 'array', 'boolean', 'date', 'alternatives', 'any',
            'binary', 'link', 'symbol', 'func'
        ],
        // Yup builders
        'yup': [
            'object', 'string', 'number', 'array', 'boolean', 'date', 'mixed', 'ref', 'lazy'
        ],
        // Default set (union of all frameworks)
        'default': [
            'object', 'string', 'number', 'array', 'boolean', 'date', 'enum', 'union', 'tuple',
            'record', 'map', 'set', 'literal', 'any', 'unknown', 'alternatives', 'binary',
            'link', 'symbol', 'func', 'mixed', 'ref', 'lazy'
        ]
    };

    // Step 3: Build set of builder methods for detected frameworks
    const builderMethods = new Set();
    for (const fw of frameworks) {
        const methods = SCHEMA_BUILDERS[fw.name] || SCHEMA_BUILDERS['default'];
        methods.forEach(m => builderMethods.add(m));
    }

    debugLog(`Watching for ${builderMethods.size} schema builder methods`, Array.from(builderMethods));

    // Step 4: Extract schema builder calls
    for (const call of functionCallArgs) {
        const callee = call.callee_function || '';
        if (!callee) continue;

        // Extract method name (last part after final dot)
        // Examples: z.object → object, Joi.string → string
        const method = callee.split('.').pop();

        // Check if this is a schema builder method
        if (!builderMethods.has(method)) continue;

        // Check if the prefix matches one of our frameworks
        let matchedFramework = null;
        for (const fw of frameworks) {
            for (const name of fw.importedNames) {
                // Check for direct framework calls: z.object, Joi.string, yup.number
                if (callee.startsWith(`${name}.`)) {
                    matchedFramework = fw.name;
                    break;
                }
            }
            if (matchedFramework) break;
        }

        // Only extract if we matched a known framework prefix
        if (matchedFramework) {
            const schemaDef = {
                line: call.line,
                framework: matchedFramework,
                method: method,
                variable_name: null,  // Schema builders don't have variable context in this extraction
                is_validator: false,  // FALSE = schema definition (not validation call)
                argument_expr: (call.argument_expr || '').substring(0, 200)  // Truncate long args
            };

            debugLog(`Extracted schema definition at line ${call.line}`, schemaDef);
            schemaDefs.push(schemaDef);
        }
    }

    debugLog(`Total schema definitions extracted: ${schemaDefs.length}`);
    return schemaDefs;
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
 * [ENHANCED] Added more schema builder patterns for comprehensive coverage
 */
function findSchemaVariables(assignments, frameworks, debugLog) {
    const schemas = {};

    // Zod schema builders
    const ZOD_BUILDERS = [
        'object', 'string', 'number', 'array', 'boolean', 'date', 'enum', 'union', 'tuple',
        'record', 'map', 'set', 'promise', 'function', 'lazy', 'literal', 'void', 'undefined',
        'null', 'any', 'unknown', 'never', 'instanceof', 'discriminatedUnion', 'intersection',
        'optional', 'nullable', 'coerce', 'nativeEnum', 'bigint', 'nan'
    ];

    // Joi schema builders
    const JOI_BUILDERS = [
        'object', 'string', 'number', 'array', 'boolean', 'date', 'alternatives', 'any',
        'binary', 'link', 'symbol', 'func'
    ];

    // Yup schema builders
    const YUP_BUILDERS = [
        'object', 'string', 'number', 'array', 'boolean', 'date', 'mixed', 'ref', 'lazy'
    ];

    for (const assign of assignments) {
        const target = assign.target_var;
        const source = assign.source_expr || '';

        // Look for: const userSchema = z.object(...)
        for (const fw of frameworks) {
            // Select appropriate builders based on framework
            let builders = ZOD_BUILDERS;
            if (fw.name === 'joi') {
                builders = JOI_BUILDERS;
            } else if (fw.name === 'yup') {
                builders = YUP_BUILDERS;
            }

            for (const name of fw.importedNames) {
                // Check if source expression uses schema builder
                for (const builder of builders) {
                    if (source.includes(`${name}.${builder}(`)) {
                        schemas[target] = { framework: fw.name };
                        debugLog(`Found schema variable: ${target}`, {
                            target_var: target,
                            framework: fw.name,
                            builder: builder,
                            source_expr: source.substring(0, 100)
                        });
                        break;
                    }
                }

                // Also catch chained schema definitions:
                // const schema = z.string().email().max(255)
                if (source.includes(`${name}.`)) {
                    schemas[target] = { framework: fw.name };
                    debugLog(`Found chained schema variable: ${target}`, {
                        target_var: target,
                        framework: fw.name,
                        source_expr: source.substring(0, 100)
                    });
                    break;
                }
            }
        }
    }

    return schemas;
}

/**
 * Check if call is validation method
 * [FIXED] Precise pattern matching to avoid false positives (JSON.parse, etc.)
 *
 * BUG FIX (2025-01-09):
 * Previous Pattern 1 was too broad - flagged ANY .parse() call if file imported Zod/Joi.
 * Result: JSON.parse(), parseInt(), custom .parse() methods all flagged as validation.
 * Fix: Check if variable name LOOKS like a schema/validator before accepting.
 */
function isValidationCall(callee, frameworks, schemaVars) {
    // Pattern 1: Direct framework call (z.parse, Joi.validate, yup.object)
    // This is the MOST PRECISE pattern - matches 'z.parse', 'Joi.validate'
    for (const fw of frameworks) {
        for (const name of fw.importedNames) {
            if (callee.startsWith(`${name}.`) && isValidatorMethod(callee)) {
                return true;
            }
        }
    }

    // Pattern 2: Schema variable call (userSchema.parse, validateUser.validate)
    // Check if variable name LOOKS like a schema/validator
    if (callee.includes('.') && frameworks.length > 0 && isValidatorMethod(callee)) {
        const varName = callee.split('.')[0];

        // Sub-pattern 2a: Variable defined in this file's assignments
        if (varName in schemaVars) {
            return true;
        }

        // Sub-pattern 2b: Variable NAME suggests it's a schema/validator
        // Common patterns: userSchema, requestSchema, emailValidator, validateUser
        if (looksLikeSchemaVariable(varName)) {
            return true;
        }
    }

    return false;
}

/**
 * Check if variable name looks like a schema/validator.
 * Used to detect IMPORTED schemas that aren't in schemaVars (defined in other files).
 *
 * Patterns:
 * - Ends with 'Schema': userSchema, requestSchema, dataSchema
 * - Ends with 'Validator': emailValidator, userValidator
 * - Contains 'schema': mySchemaObj, schemaConfig
 * - Contains 'validator': validatorFn, myValidator
 * - Starts with 'validate': validateUser, validateRequest
 * - Common validation var names: schema, validator, validation
 *
 * @param {string} varName - Variable name to check
 * @returns {boolean} - True if name suggests schema/validator
 */
function looksLikeSchemaVariable(varName) {
    const lower = varName.toLowerCase();

    // Ends with 'schema' or 'validator'
    if (lower.endsWith('schema') || lower.endsWith('validator')) {
        return true;
    }

    // Contains 'schema' or 'validator' (but not as whole word 'parse', 'int', etc.)
    if (lower.includes('schema') || lower.includes('validator')) {
        return true;
    }

    // Starts with 'validate'
    if (lower.startsWith('validate')) {
        return true;
    }

    // Common single-word names
    if (['schema', 'validator', 'validation'].includes(lower)) {
        return true;
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

/**
 * Extract AWS CDK construct instantiations from TypeScript/JavaScript.
 *
 * Detects patterns:
 * - new s3.Bucket(this, 'MyBucket', {...})
 * - new SecurityGroup(this, 'MySG', {...})
 * - new rds.DatabaseInstance(this, 'MyDB', {...})
 *
 * PURPOSE: Enable infrastructure-as-code security analysis for AWS CDK
 *
 * TEAMSOP.MD COMPLIANCE:
 * - NO FALLBACKS: If CDK imports not detected, return empty array (deterministic)
 * - NO REGEX: Use AST data from core extractors only
 * - DATABASE-FIRST: Write to database, rules query database (never re-parse source)
 * - HARD FAILURE: Missing data causes crash (no graceful degradation)
 *
 * @param {Array} functionCallArgs - From extractFunctionCallArgs()
 * @param {Array} imports - From extractImports()
 * @returns {Array} - CDK construct records
 */
function extractCDKConstructs(functionCallArgs, imports) {
    const constructs = [];

    // Debug logging helper
    const debugLog = (msg, data) => {
        if (process.env.THEAUDITOR_CDK_DEBUG === '1') {
            console.error(`[CDK-EXTRACT] ${msg}`);
            if (data) {
                console.error(`[CDK-EXTRACT]   ${JSON.stringify(data)}`);
            }
        }
    };

    debugLog('Starting CDK construct extraction', {
        functionCallArgs_count: functionCallArgs.length,
        imports_count: imports.length
    });

    // Step 1: Detect CDK imports
    const cdkImports = imports.filter(i => {
        const module = i.module || '';
        return module && module.includes('aws-cdk-lib');
    });

    debugLog(`Found ${cdkImports.length} CDK imports`, cdkImports);

    if (cdkImports.length === 0) {
        debugLog('No CDK imports found, skipping extraction (DETERMINISTIC)');
        return [];  // No CDK imports = no CDK constructs (deterministic, not a fallback)
    }

    // Step 2: Build map of CDK module aliases
    // Example: import * as s3 from 'aws-cdk-lib/aws-s3' → {s3: 'aws-s3'}
    // Example: import { Bucket } from 'aws-cdk-lib/aws-s3' → {Bucket: 'aws-s3'}
    const cdkAliases = {};
    for (const imp of cdkImports) {
        const module = imp.module || '';

        // Extract service name from module path: 'aws-cdk-lib/aws-s3' → 'aws-s3'
        const serviceName = module.includes('/') ? module.split('/').pop() : null;

        // Process specifiers array from extractImports()
        if (imp.specifiers && imp.specifiers.length > 0) {
            for (const spec of imp.specifiers) {
                const name = spec.name;

                // Handle namespace imports: import * as s3
                if (spec.isNamespace) {
                    cdkAliases[name] = serviceName;
                    debugLog(`Mapped namespace import: ${name} → ${serviceName}`);
                }

                // Handle named imports: import { Bucket }
                else if (spec.isNamed) {
                    cdkAliases[name] = serviceName;
                    debugLog(`Mapped named import: ${name} → ${serviceName}`);
                }

                // Handle default imports: import cdk
                else if (spec.isDefault) {
                    cdkAliases[name] = serviceName;
                    debugLog(`Mapped default import: ${name} → ${serviceName}`);
                }
            }
        }
    }

    debugLog('Built CDK alias map', cdkAliases);

    // Step 3: Detect 'new X(...)' patterns from functionCallArgs
    // CRITICAL: functionCallArgs contains one entry PER ARGUMENT
    // So new s3.Bucket(this, 'Name', {}) creates 3 entries (args 0, 1, 2)
    // We must deduplicate to process each construct only ONCE
    const processedConstructs = new Set();

    for (const call of functionCallArgs) {
        const callee = call.callee_function || '';

        // Check if this is a 'new' expression
        // Core extractors mark these as 'new ClassName' or 'new module.ClassName'
        if (!callee.startsWith('new ')) {
            continue;
        }

        // Deduplicate: Skip if we've already processed this construct
        const constructKey = `${call.line}::${callee}`;
        if (processedConstructs.has(constructKey)) {
            continue;
        }
        processedConstructs.add(constructKey);

        // Extract class name from 'new s3.Bucket' → 's3.Bucket'
        const className = callee.replace(/^new\s+/, '');

        debugLog(`Analyzing new expression: ${className}`, { line: call.line });

        // Check if this matches a CDK alias
        const parts = className.split('.');
        if (parts.length >= 2) {
            const moduleAlias = parts[0];  // e.g., 's3'
            const constructClass = parts.slice(1).join('.');  // e.g., 'Bucket'

            if (moduleAlias in cdkAliases) {
                // This is a CDK construct!
                debugLog(`Matched CDK construct: ${className}`, {
                    module_alias: moduleAlias,
                    construct_class: constructClass,
                    service: cdkAliases[moduleAlias]
                });

                // Extract construct name from arguments (typically second argument after 'this')
                const constructName = extractConstructName(call, functionCallArgs);

                // Extract properties from object literal (typically third argument)
                const properties = extractConstructProperties(call, functionCallArgs);

                constructs.push({
                    line: call.line,
                    cdk_class: className,  // e.g., 's3.Bucket'
                    construct_name: constructName,
                    properties: properties
                });

                debugLog(`Extracted CDK construct at line ${call.line}`, {
                    cdk_class: className,
                    construct_name: constructName,
                    properties_count: properties.length
                });
            }
        } else if (parts.length === 1) {
            // Direct class import: new Bucket(...)
            const constructClass = parts[0];
            if (constructClass in cdkAliases) {
                debugLog(`Matched direct CDK import: ${constructClass}`);

                const constructName = extractConstructName(call, functionCallArgs);
                const properties = extractConstructProperties(call, functionCallArgs);

                constructs.push({
                    line: call.line,
                    cdk_class: constructClass,
                    construct_name: constructName,
                    properties: properties
                });

                debugLog(`Extracted CDK construct at line ${call.line}`, {
                    cdk_class: constructClass,
                    construct_name: constructName,
                    properties_count: properties.length
                });
            }
        }
    }

    debugLog(`Total CDK constructs extracted: ${constructs.length}`);
    return constructs;
}

/**
 * Extract construct name from CDK constructor arguments.
 * CDK pattern: new Bucket(this, 'ConstructName', {...})
 * The second argument is always the construct ID (name).
 *
 * @param {Object} call - Function call record for 'new ClassName'
 * @param {Array} allCalls - All function call args to find matching arguments
 * @returns {string|null} - Construct name or null
 */
function extractConstructName(call, allCalls) {
    // Find all arguments for this call (same line, same caller)
    const args = allCalls.filter(c =>
        c.line === call.line &&
        c.callee_function === call.callee_function
    );

    // CDK constructor pattern: (scope, id, props)
    // id is the second argument (argument_index === 1)
    const idArg = args.find(a => a.argument_index === 1);
    if (!idArg || !idArg.argument_expr) {
        return null;
    }

    // Extract string literal from argument
    const expr = idArg.argument_expr.trim();

    // Remove quotes: 'MyBucket' → MyBucket
    if ((expr.startsWith("'") && expr.endsWith("'")) ||
        (expr.startsWith('"') && expr.endsWith('"'))) {
        return expr.slice(1, -1);
    }

    // If not a string literal, return the expression as-is
    return expr;
}

/**
 * Extract properties from CDK construct configuration object.
 * CDK pattern: new Bucket(this, 'Name', { publicReadAccess: true, versioned: false })
 * The third argument is the props object.
 *
 * @param {Object} call - Function call record for 'new ClassName'
 * @param {Array} allCalls - All function call args to find matching arguments
 * @returns {Array} - Property records
 */
function extractConstructProperties(call, allCalls) {
    const properties = [];

    // Find the props argument (third argument, argument_index === 2)
    const propsArg = allCalls.find(c =>
        c.line === call.line &&
        c.callee_function === call.callee_function &&
        c.argument_index === 2
    );

    if (!propsArg || !propsArg.argument_expr) {
        return properties;
    }

    const expr = propsArg.argument_expr.trim();

    // Parse object literal: { key: value, ... }
    // This is a simplified parser - handles basic key-value pairs
    const objMatch = expr.match(/\{([^}]+)\}/);
    if (!objMatch) {
        return properties;
    }

    const objContent = objMatch[1];

    // Split by commas, but be careful with nested objects/arrays
    // Simplified approach: split and rejoin nested structures
    const pairs = splitObjectPairs(objContent);

    for (const pair of pairs) {
        const colonIdx = pair.indexOf(':');
        if (colonIdx === -1) continue;

        const key = pair.substring(0, colonIdx).trim();
        const value = pair.substring(colonIdx + 1).trim();

        if (!key) continue;

        properties.push({
            name: key,
            value_expr: value,
            line: call.line  // Properties use same line as construct
        });
    }

    return properties;
}

/**
 * Split object literal pairs by commas, handling nested structures.
 * Simplified implementation that handles basic nesting.
 *
 * @param {string} content - Object literal content (without braces)
 * @returns {Array} - Array of key:value strings
 */
function splitObjectPairs(content) {
    const pairs = [];
    let current = '';
    let depth = 0;
    let inString = false;
    let stringChar = null;

    for (let i = 0; i < content.length; i++) {
        const char = content[i];
        const prevChar = i > 0 ? content[i - 1] : '';

        // Track string literals
        if ((char === '"' || char === "'" || char === '`') && prevChar !== '\\') {
            if (!inString) {
                inString = true;
                stringChar = char;
            } else if (char === stringChar) {
                inString = false;
                stringChar = null;
            }
        }

        // Track nesting depth (ignore inside strings)
        if (!inString) {
            if (char === '{' || char === '[' || char === '(') {
                depth++;
            } else if (char === '}' || char === ']' || char === ')') {
                depth--;
            }
        }

        // Split on comma at depth 0 (outside nested structures)
        if (char === ',' && depth === 0 && !inString) {
            pairs.push(current.trim());
            current = '';
        } else {
            current += char;
        }
    }

    // Add final pair
    if (current.trim()) {
        pairs.push(current.trim());
    }

    return pairs;
}

/**
 * Extract Frontend API calls (fetch, axios)
 *
 * Detects patterns:
 * - fetch('/api/users', { method: 'POST', body: data })
 * - axios.post('/api/products', data)
 * - axios.get('/api/items', { params: query })
 *
 * PURPOSE: Populate frontend_api_calls table to bridge
 * frontend-to-backend taint analysis.
 *
 * @param {Array} functionCallArgs - From extractFunctionCallArgs()
 * @param {Array} imports - From extractImports()
 * @returns {Array} - Frontend API call records
 */
function extractFrontendApiCalls(functionCallArgs, imports) {
    const apiCalls = [];

    // --- Debug Logging ---
    const debugLog = (msg, data) => {
        if (process.env.THEAUDITOR_DEBUG === '1') {
            console.error(`[FE-API-EXTRACT] ${msg}`);
            if (data) console.error(`[FE-API-EXTRACT]   ${JSON.stringify(data)}`);
        }
    };

    // --- Framework Detection ---
    const hasAxios = imports.some(i => i.module === 'axios');
    const hasFetch = true; // fetch is global, always assume true

    if (!hasAxios && !hasFetch) {
        return apiCalls;
    }

    debugLog('Starting frontend API call extraction', { hasAxios });

    // --- Argument Parsing Helpers ---
    const parseUrl = (call) => {
        if (call.argument_index === 0 && call.argument_expr) {
            const url = call.argument_expr.trim().replace(/['"`]/g, '');
            // Only return static, relative URLs
            if (url.startsWith('/')) {
                return url.split('?')[0]; // Remove query string
            }
        }
        return null;
    };

    const parseFetchOptions = (call) => {
        const options = { method: 'GET', body_variable: null }; // Default for fetch
        if (call.argument_index === 1 && call.argument_expr) {
            const expr = call.argument_expr;

            // Extract Method
            const methodMatch = expr.match(/method:\s*['"]([^'"]+)['"]/i);
            if (methodMatch) {
                options.method = methodMatch[1].toUpperCase();
            }

            // Extract Body Variable
            // Handles: body: data, body: JSON.stringify(data)
            const bodyMatch = expr.match(/body:\s*([^\s,{}]+)/i);
            if (bodyMatch) {
                let bodyVar = bodyMatch[1];
                if (bodyVar.startsWith('JSON.stringify(')) {
                    bodyVar = bodyVar.substring(15, bodyVar.length - 1);
                }
                options.body_variable = bodyVar;
            }
        }
        return options;
    };

    // --- Group calls by line ---
    const callsByLine = {};
    for (const call of functionCallArgs) {
        const callee = call.callee_function || '';
        if (!callee) continue;

        if (!callsByLine[call.line]) {
            callsByLine[call.line] = {
                callee: callee,
                caller: call.caller_function,
                args: []
            };
        }
        callsByLine[call.line].args[call.argument_index] = call;
    }

    // --- Process grouped calls ---
    for (const line in callsByLine) {
        const callData = callsByLine[line];
        const callee = callData.callee;
        const args = callData.args;

        let url = null;
        let method = null;
        let body_variable = null;

        // Pattern 1: fetch()
        if (callee === 'fetch' && args[0]) {
            url = parseUrl(args[0]);
            if (!url) continue; // Skip non-static or external fetches

            const options = parseFetchOptions(args[1] || {});
            method = options.method;
            body_variable = options.body_variable;

        // Pattern 2: axios.get(url, config)
        } else if ((callee === 'axios.get' || callee === 'axios') && args[0]) {
            url = parseUrl(args[0]);
            if (!url) continue;
            method = 'GET';
            // body_variable is in config.params, not body (skip for now)

        // Pattern 3: axios.post(url, data, config)
        } else if (callee === 'axios.post' && args[0] && args[1]) {
            url = parseUrl(args[0]);
            if (!url) continue;
            method = 'POST';
            body_variable = args[1].argument_expr;

        // Pattern 4: axios.put / axios.patch
        } else if ((callee === 'axios.put' || callee === 'axios.patch') && args[0] && args[1]) {
            url = parseUrl(args[0]);
            if (!url) continue;
            method = callee === 'axios.put' ? 'PUT' : 'PATCH';
            body_variable = args[1].argument_expr;

        // Pattern 5: axios.delete
        } else if (callee === 'axios.delete' && args[0]) {
            url = parseUrl(args[0]);
            if (!url) continue;
            method = 'DELETE';

        // Pattern 6: Axios wrapper patterns (api.get, apiService.post, instance.put, etc.)
        // Common patterns: apiService.get(), api.post(), this.instance.put(), service.delete()
        } else if (callee.match(/\.(get|post|put|patch|delete)$/)) {
            // Check if this looks like an API wrapper (not random .get() calls)
            const prefix = callee.substring(0, callee.lastIndexOf('.'));
            const httpMethod = callee.substring(callee.lastIndexOf('.') + 1).toUpperCase();

            // Common API wrapper prefixes
            const apiWrapperPrefixes = ['api', 'apiService', 'service', 'http', 'httpClient',
                                         'client', 'axios', 'instance', 'this.instance',
                                         'this.api', 'this.http', 'request'];

            // Check if it's likely an API wrapper
            const isLikelyApiWrapper = apiWrapperPrefixes.some(p =>
                prefix === p || prefix.endsWith('.' + p) || prefix.includes('api') || prefix.includes('service')
            );

            if (isLikelyApiWrapper && args[0]) {
                url = parseUrl(args[0]);
                if (!url) continue;

                method = httpMethod;

                // For POST/PUT/PATCH, second argument is usually the body
                if (['POST', 'PUT', 'PATCH'].includes(method) && args[1]) {
                    body_variable = args[1].argument_expr;
                }
            }
        }

        // --- Save the extracted call ---
        if (url && method) {
            apiCalls.push({
                file: args[0].file, // File path from the first argument
                line: parseInt(line),
                method: method,
                url_literal: url,
                body_variable: body_variable,
                function_name: callData.caller
            });
            debugLog(`Extracted FE API Call at line ${line}`, { url, method, body_variable });
        }
    }

    return apiCalls;
}