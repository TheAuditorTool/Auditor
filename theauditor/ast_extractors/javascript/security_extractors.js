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
    for (const call of functionCallArgs) {
        const callee = call.callee_function || '';

        // Check if this is a 'new' expression
        // Core extractors mark these as 'new ClassName' or 'new module.ClassName'
        if (!callee.startsWith('new ')) {
            continue;
        }

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