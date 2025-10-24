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
        if (!route) continue;

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