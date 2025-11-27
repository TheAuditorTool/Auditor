/**
 * Module & Framework Extractors - Integration Layer
 *
 * Module system and framework pattern extractors. These extractors
 * capture imports, module resolution, and framework-specific patterns.
 *
 * STABILITY: MEDIUM - Changes when adding new framework support.
 * Modify when adding support for new import patterns or ORM frameworks.
 *
 * DEPENDENCIES: None (standalone patterns)
 * USED BY: framework_extractors.js, sequelize_extractors.js
 *
 * Architecture:
 * - Extracted from: core_ast_extractors.js (refactored 2025-11-03)
 * - Used by: ES Module and CommonJS batch templates
 * - Assembly: Runtime file loading + concatenation in js_helper_templates.py
 *
 * Functions (5 module/framework extractors):
 * 1. extractImports() - Import/require/dynamic import detection
 * 2. extractEnvVarUsage() - Environment variable usage patterns
 * 3. extractORMRelationships() - ORM relationship declarations
 * 4. extractImportStyles() - Bundle optimization analysis (utility)
 * 5. extractRefs() - Module resolution mappings for cross-file analysis
 */

/**
 * Extract import statements from TypeScript AST.
 *
 * Detects both ES6 imports and CommonJS require() calls.
 * Critical for dependency tracking and taint analysis.
 *
 * @param {Object} sourceFile - TypeScript source file
 * @param {Object} ts - TypeScript compiler API
 * @param {string} filePath - Relative file path for database records
 * @returns {Object} - { imports, import_specifiers }
 */
function extractImports(sourceFile, ts, filePath) {
    const imports = [];
    const import_specifiers = [];

    function visit(node) {
        // ES6 Import declarations: import { foo } from 'bar'
        if (node.kind === ts.SyntaxKind.ImportDeclaration) {
            const moduleSpecifier = node.moduleSpecifier;
            if (moduleSpecifier && moduleSpecifier.text) {
                const { line } = sourceFile.getLineAndCharacterOfPosition(node.getStart ? node.getStart(sourceFile) : node.pos);
                const importLine = line + 1;

                if (node.importClause) {
                    // Default import: import Foo from 'bar'
                    if (node.importClause.name) {
                        const specName = node.importClause.name.text || node.importClause.name.escapedText;
                        import_specifiers.push({
                            file: filePath,
                            import_line: importLine,
                            specifier_name: specName,
                            original_name: specName,
                            is_default: 1,
                            is_namespace: 0,
                            is_named: 0
                        });
                    }

                    // Named imports: import { a, b } from 'bar'
                    if (node.importClause.namedBindings) {
                        const bindings = node.importClause.namedBindings;

                        // Namespace import: import * as foo from 'bar'
                        if (bindings.kind === ts.SyntaxKind.NamespaceImport) {
                            const specName = bindings.name.text || bindings.name.escapedText;
                            import_specifiers.push({
                                file: filePath,
                                import_line: importLine,
                                specifier_name: specName,
                                original_name: '*',
                                is_default: 0,
                                is_namespace: 1,
                                is_named: 0
                            });
                        }
                        // Named imports: import { a, b as c } from 'bar'
                        else if (bindings.kind === ts.SyntaxKind.NamedImports && bindings.elements) {
                            bindings.elements.forEach(element => {
                                const localName = element.name.text || element.name.escapedText;
                                // propertyName is the original name when aliased: import { foo as bar }
                                // element.propertyName = 'foo', element.name = 'bar'
                                let originalName = localName;
                                if (element.propertyName) {
                                    originalName = element.propertyName.text || element.propertyName.escapedText;
                                }
                                import_specifiers.push({
                                    file: filePath,
                                    import_line: importLine,
                                    specifier_name: localName,
                                    original_name: originalName,
                                    is_default: 0,
                                    is_namespace: 0,
                                    is_named: 1
                                });
                            });
                        }
                    }
                }

                imports.push({
                    kind: 'import',
                    module: moduleSpecifier.text,
                    line: importLine
                });
            }
        }

        // CommonJS require: const x = require('bar')
        // CRITICAL FIX 2025-11-27: Also populate import_specifiers for CommonJS
        // Without this, resolve_handler_file_paths() in javascript.py cannot
        // resolve handler_file for express_middleware_chains, breaking the graph.
        else if (node.kind === ts.SyntaxKind.CallExpression) {
            const expr = node.expression;
            if (expr && (expr.text === 'require' || expr.escapedText === 'require')) {
                const args = node.arguments;
                if (args && args.length > 0 && args[0].kind === ts.SyntaxKind.StringLiteral) {
                    const { line } = sourceFile.getLineAndCharacterOfPosition(node.getStart ? node.getStart(sourceFile) : node.pos);
                    const importLine = line + 1;
                    const modulePath = args[0].text;

                    imports.push({
                        kind: 'require',
                        module: modulePath,
                        line: importLine
                    });

                    // CRITICAL FIX: Extract variable name from parent VariableDeclaration
                    // AST structure: VariableDeclaration -> initializer: CallExpression
                    // We need to traverse up to find the variable name being assigned
                    let parent = node.parent;

                    // Handle: const x = require('bar').default or require('bar').someExport
                    // AST: PropertyAccessExpression -> expression: CallExpression
                    if (parent && parent.kind === ts.SyntaxKind.PropertyAccessExpression) {
                        parent = parent.parent;
                    }

                    // Now parent should be VariableDeclaration
                    if (parent && parent.kind === ts.SyntaxKind.VariableDeclaration) {
                        const declName = parent.name;

                        // Case 1: Simple identifier - const x = require('bar')
                        if (declName.kind === ts.SyntaxKind.Identifier) {
                            const specName = declName.text || declName.escapedText;
                            import_specifiers.push({
                                file: filePath,
                                import_line: importLine,
                                specifier_name: specName,
                                original_name: specName,
                                is_default: 1,
                                is_namespace: 0,
                                is_named: 0
                            });
                        }
                        // Case 2: Destructuring - const { a, b } = require('bar')
                        else if (declName.kind === ts.SyntaxKind.ObjectBindingPattern && declName.elements) {
                            declName.elements.forEach(element => {
                                if (element.name && element.name.kind === ts.SyntaxKind.Identifier) {
                                    const localName = element.name.text || element.name.escapedText;
                                    // propertyName is the original name when aliased: { foo: bar }
                                    let originalName = localName;
                                    if (element.propertyName) {
                                        originalName = element.propertyName.text || element.propertyName.escapedText;
                                    }
                                    import_specifiers.push({
                                        file: filePath,
                                        import_line: importLine,
                                        specifier_name: localName,
                                        original_name: originalName,
                                        is_default: 0,
                                        is_namespace: 0,
                                        is_named: 1
                                    });
                                }
                            });
                        }
                        // Case 3: Array destructuring - const [a, b] = require('bar')
                        else if (declName.kind === ts.SyntaxKind.ArrayBindingPattern && declName.elements) {
                            declName.elements.forEach((element, idx) => {
                                if (element.name && element.name.kind === ts.SyntaxKind.Identifier) {
                                    const localName = element.name.text || element.name.escapedText;
                                    import_specifiers.push({
                                        file: filePath,
                                        import_line: importLine,
                                        specifier_name: localName,
                                        original_name: `[${idx}]`,
                                        is_default: 0,
                                        is_namespace: 0,
                                        is_named: 1
                                    });
                                }
                            });
                        }
                    }
                }
            }
        }

        // Dynamic imports: import('module')
        else if (node.kind === ts.SyntaxKind.ImportKeyword && node.parent && node.parent.kind === ts.SyntaxKind.CallExpression) {
            const callExpr = node.parent;
            const args = callExpr.arguments;
            if (args && args.length > 0 && args[0].kind === ts.SyntaxKind.StringLiteral) {
                const { line } = sourceFile.getLineAndCharacterOfPosition(callExpr.getStart ? callExpr.getStart(sourceFile) : callExpr.pos);
                imports.push({
                    kind: 'dynamic_import',
                    module: args[0].text,
                    line: line + 1
                });
            }
        }

        ts.forEachChild(node, visit);
    }

    visit(sourceFile);
    return { imports, import_specifiers };
}

/**
 * Extract environment variable usage patterns (process.env.X).
 * Detects reads, writes, and existence checks of environment variables.
 * Critical for secret detection and configuration analysis.
 *
 * Examples:
 *   - process.env.NODE_ENV                    → read: "NODE_ENV"
 *   - process.env['DATABASE_URL']             → read: "DATABASE_URL"
 *   - process.env.SECRET = 'hardcoded'        → write: "SECRET"
 *   - if (process.env.API_KEY)                → check: "API_KEY"
 *   - const { PORT } = process.env            → read: "PORT"
 *
 * @param {Object} sourceFile - TypeScript source file node
 * @param {Object} ts - TypeScript compiler API
 * @param {Map} scopeMap - Line → function mapping
 * @returns {Array} - List of env var usage records
 */
function extractEnvVarUsage(sourceFile, ts, scopeMap) {
    const usages = [];

    // CRITICAL FIX: Idempotent traversal to prevent duplicate entries
    // Track visited nodes by (line, column, kind) to avoid processing same node multiple times
    // Bug: AST traversal visits same node multiple times causing UNIQUE constraint violations
    const visitedNodes = new Set();

    function traverse(node) {
        if (!node) return;

        // CRITICAL FIX: Idempotency check - prevent processing same node twice
        const pos = node.getStart ? node.getStart(sourceFile) : node.pos;
        const { line, character } = sourceFile.getLineAndCharacterOfPosition(pos);
        const nodeId = `${line}:${character}:${node.kind}`;
        if (visitedNodes.has(nodeId)) {
            return;  // Already processed this node
        }
        visitedNodes.add(nodeId);

        const kind = ts.SyntaxKind[node.kind];

        // Detect: process.env.VAR_NAME (PropertyAccessExpression)
        if (kind === 'PropertyAccessExpression') {
            // Check if this is process.env.X pattern
            if (node.expression && node.name) {
                const exprKind = ts.SyntaxKind[node.expression.kind];

                // process.env.VAR_NAME
                if (exprKind === 'PropertyAccessExpression' &&
                    node.expression.expression &&
                    node.expression.name) {
                    const objName = node.expression.expression.text || node.expression.expression.escapedText;
                    const propName = node.expression.name.text || node.expression.name.escapedText;

                    if (objName === 'process' && propName === 'env') {
                        const varName = node.name.text || node.name.escapedText;
                        const { line } = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));
                        const inFunction = scopeMap.get(line + 1) || null;

                        // Determine access type based on parent node
                        let accessType = 'read';  // Default
                        if (node.parent) {
                            const parentKind = ts.SyntaxKind[node.parent.kind];
                            // Write: process.env.FOO = 'value'
                            if (parentKind === 'BinaryExpression' &&
                                node.parent.operatorToken &&
                                ts.SyntaxKind[node.parent.operatorToken.kind] === 'EqualsToken' &&
                                node.parent.left === node) {
                                accessType = 'write';
                            }
                            // Check: if (process.env.FOO) or !process.env.FOO
                            else if (parentKind === 'IfStatement' ||
                                     parentKind === 'ConditionalExpression' ||
                                     parentKind === 'PrefixUnaryExpression') {
                                accessType = 'check';
                            }
                        }

                        usages.push({
                            line: line + 1,
                            var_name: varName,
                            access_type: accessType,
                            in_function: inFunction,
                            property_access: `process.env.${varName}`
                        });
                    }
                }
            }
        }

        // Detect: process.env['VAR_NAME'] (ElementAccessExpression)
        if (kind === 'ElementAccessExpression') {
            if (node.expression && node.argumentExpression) {
                const exprKind = ts.SyntaxKind[node.expression.kind];

                // process.env['VAR_NAME']
                if (exprKind === 'PropertyAccessExpression' &&
                    node.expression.expression &&
                    node.expression.name) {
                    const objName = node.expression.expression.text || node.expression.expression.escapedText;
                    const propName = node.expression.name.text || node.expression.name.escapedText;

                    if (objName === 'process' && propName === 'env') {
                        // Get variable name from bracket access
                        let varName = null;
                        const argKind = ts.SyntaxKind[node.argumentExpression.kind];
                        if (argKind === 'StringLiteral') {
                            varName = node.argumentExpression.text;
                        } else if (argKind === 'Identifier') {
                            // process.env[variable] - dynamic access
                            varName = `[${node.argumentExpression.text || node.argumentExpression.escapedText}]`;
                        }

                        if (varName) {
                            const { line } = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));
                            const inFunction = scopeMap.get(line + 1) || null;

                            let accessType = 'read';
                            if (node.parent) {
                                const parentKind = ts.SyntaxKind[node.parent.kind];
                                if (parentKind === 'BinaryExpression' &&
                                    node.parent.operatorToken &&
                                    ts.SyntaxKind[node.parent.operatorToken.kind] === 'EqualsToken' &&
                                    node.parent.left === node) {
                                    accessType = 'write';
                                }
                            }

                            usages.push({
                                line: line + 1,
                                var_name: varName,
                                access_type: accessType,
                                in_function: inFunction,
                                property_access: `process.env['${varName}']`
                            });
                        }
                    }
                }
            }
        }

        // Detect: const { VAR1, VAR2 } = process.env (ObjectBindingPattern)
        if (kind === 'VariableDeclaration') {
            if (node.name && node.initializer) {
                const nameKind = ts.SyntaxKind[node.name.kind];
                const initKind = ts.SyntaxKind[node.initializer.kind];

                // Destructuring: const { ... } = process.env
                if (nameKind === 'ObjectBindingPattern' && initKind === 'PropertyAccessExpression') {
                    const initExpr = node.initializer.expression;
                    const initName = node.initializer.name;

                    if (initExpr && initName) {
                        const objName = initExpr.text || initExpr.escapedText;
                        const propName = initName.text || initName.escapedText;

                        if (objName === 'process' && propName === 'env') {
                            // Extract each destructured variable
                            if (node.name.elements) {
                                for (const element of node.name.elements) {
                                    if (element.name) {
                                        const varName = element.name.text || element.name.escapedText;
                                        const { line } = sourceFile.getLineAndCharacterOfPosition(element.getStart(sourceFile));
                                        const inFunction = scopeMap.get(line + 1) || null;

                                        usages.push({
                                            line: line + 1,
                                            var_name: varName,
                                            access_type: 'read',
                                            in_function: inFunction,
                                            property_access: `process.env.${varName} (destructured)`
                                        });
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        ts.forEachChild(node, traverse);
    }

    traverse(sourceFile);
    return usages;
}

/**
 * Extract ORM relationship declarations (Sequelize/Prisma/TypeORM).
 * Detects hasMany, belongsTo, hasOne, and other relationship methods.
 * Critical for graph analysis, N+1 query detection, and IDOR vulnerabilities.
 *
 * Examples:
 *   - User.hasMany(Operation)                           → hasMany: User → Operation
 *   - User.belongsTo(Account, { foreignKey: 'acct' })  → belongsTo: User → Account (FK: acct)
 *   - User.hasOne(Profile, { onDelete: 'CASCADE' })    → hasOne: User → Profile (cascade: true)
 *   - User.hasMany(Post, { as: 'articles' })           → hasMany: User → Post (as: articles)
 *
 * @param {Object} sourceFile - TypeScript source file node
 * @param {Object} ts - TypeScript compiler API
 * @returns {Array} - List of ORM relationship records
 */
function extractORMRelationships(sourceFile, ts) {
    const relationships = [];

    // Deduplication set to match Python implementation
    // Key format: sourceModel-targetModel-relationshipType-line
    const seenRelationships = new Set();

    // Sequelize relationship methods
    const relationshipMethods = new Set([
        'hasMany', 'belongsTo', 'hasOne', 'hasAndBelongsToMany',
        'belongsToMany'  // Sequelize many-to-many
    ]);

    function traverse(node) {
        if (!node) return;
        const kind = ts.SyntaxKind[node.kind];

        // Detect: Model.hasMany(Target, { options })
        if (kind === 'CallExpression') {
            if (node.expression && node.arguments && node.arguments.length > 0) {
                const exprKind = ts.SyntaxKind[node.expression.kind];

                // Check if this is a PropertyAccessExpression (Model.method)
                if (exprKind === 'PropertyAccessExpression') {
                    const methodName = node.expression.name.text || node.expression.name.escapedText;

                    // Check if this is a relationship method
                    if (relationshipMethods.has(methodName)) {
                        // Extract source model (the object before the method)
                        let sourceModel = null;
                        if (node.expression.expression) {
                            const exprExpr = node.expression.expression;
                            const exprExprKind = ts.SyntaxKind[exprExpr.kind];

                            // Handle: model.hasMany() (simple identifier)
                            if (exprExprKind === 'Identifier') {
                                sourceModel = exprExpr.text || exprExpr.escapedText;
                            }
                            // Handle: models.Account.hasMany() (property access)
                            else if (exprExprKind === 'PropertyAccessExpression') {
                                sourceModel = exprExpr.name.text || exprExpr.name.escapedText;
                            }
                        }

                        // Extract target model (first argument)
                        let targetModel = null;
                        const firstArg = node.arguments[0];
                        if (firstArg) {
                            const argKind = ts.SyntaxKind[firstArg.kind];
                            if (argKind === 'Identifier') {
                                targetModel = firstArg.text || firstArg.escapedText;
                            }
                            // Handle: hasMany(models.User)
                            else if (argKind === 'PropertyAccessExpression') {
                                targetModel = firstArg.name.text || firstArg.name.escapedText;
                            }
                        }

                        // Parse options object (second argument)
                        let foreignKey = null;
                        let cascadeDelete = false;
                        let asName = null;

                        if (node.arguments.length > 1) {
                            const optionsArg = node.arguments[1];
                            const optionsKind = ts.SyntaxKind[optionsArg.kind];

                            if (optionsKind === 'ObjectLiteralExpression') {
                                if (optionsArg.properties) {
                                    for (const prop of optionsArg.properties) {
                                        const propKind = ts.SyntaxKind[prop.kind];

                                        if (propKind === 'PropertyAssignment') {
                                            const propName = prop.name.text || prop.name.escapedText;

                                            // Extract foreignKey
                                            if (propName === 'foreignKey') {
                                                const initKind = ts.SyntaxKind[prop.initializer.kind];
                                                if (initKind === 'StringLiteral') {
                                                    foreignKey = prop.initializer.text;
                                                }
                                            }

                                            // Extract onDelete: 'CASCADE'
                                            if (propName === 'onDelete') {
                                                const initKind = ts.SyntaxKind[prop.initializer.kind];
                                                if (initKind === 'StringLiteral') {
                                                    const value = prop.initializer.text;
                                                    if (value.toUpperCase() === 'CASCADE') {
                                                        cascadeDelete = true;
                                                    }
                                                }
                                            }

                                            // Extract as: 'alias'
                                            if (propName === 'as') {
                                                const initKind = ts.SyntaxKind[prop.initializer.kind];
                                                if (initKind === 'StringLiteral') {
                                                    asName = prop.initializer.text;
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // Only record if we have both source and target
                        if (sourceModel && targetModel) {
                            const { line } = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));
                            const lineNum = line + 1;

                            // Create deduplication key matching Python implementation
                            const dedupKey = `${sourceModel}-${targetModel}-${methodName}-${lineNum}`;

                            // Skip if we've already seen this relationship
                            if (seenRelationships.has(dedupKey)) {
                                return;
                            }

                            // Add to deduplication set
                            seenRelationships.add(dedupKey);

                            relationships.push({
                                line: lineNum,
                                source_model: sourceModel,
                                target_model: targetModel,
                                relationship_type: methodName,
                                foreign_key: foreignKey,
                                cascade_delete: cascadeDelete,
                                as_name: asName
                            });
                        }
                    }
                }
            }
        }

        ts.forEachChild(node, traverse);
    }

    traverse(sourceFile);
    return relationships;
}

/**
 * Analyze import statements for bundle optimization analysis.
 * Classifies: namespace (prevents tree-shaking) vs named (allows tree-shaking).
 * Implements Python's _analyze_import_styles() from javascript.py:790-853.
 *
 * @param {Array} imports - From extractImports()
 * @param {Array} import_specifiers - Flat specifiers from extractImports()
 * @param {string} filePath - Relative file path for database records
 * @returns {Object} - { import_styles, import_style_names }
 */
function extractImportStyles(imports, import_specifiers, filePath) {
    const import_styles = [];
    const import_style_names = [];

    for (const imp of imports) {
        const target = imp.module || imp.target;
        if (!target) continue;

        const line = imp.line || 0;
        let import_style = null;
        let alias_name = null;

        // Find specifiers for this import line from flat array
        const lineSpecifiers = import_specifiers.filter(s => s.import_line === line);
        const namespaceSpec = lineSpecifiers.find(s => s.is_namespace === 1);
        const defaultSpec = lineSpecifiers.find(s => s.is_default === 1);
        const namedSpecs = lineSpecifiers.filter(s => s.is_named === 1);

        // Classify import style
        if (namespaceSpec) {
            import_style = 'namespace';
            alias_name = namespaceSpec.specifier_name;
        } else if (namedSpecs.length > 0) {
            import_style = 'named';
            // Flatten named imports to junction table
            namedSpecs.forEach(spec => {
                import_style_names.push({
                    import_file: filePath,
                    import_line: line,
                    imported_name: spec.specifier_name
                });
            });
        } else if (defaultSpec) {
            import_style = 'default';
            alias_name = defaultSpec.specifier_name;
        } else {
            import_style = 'side-effect';
        }

        if (import_style) {
            const fullStatement = imp.text || `import ${import_style} from '${target}'`;

            import_styles.push({
                file: filePath,
                line: line,
                package: target,
                import_style: import_style,
                alias_name: alias_name,
                full_statement: fullStatement.substring(0, 200)
            });
        }
    }

    return { import_styles, import_style_names };
}

/**
 * Extract module resolution mappings for cross-file analysis.
 * Maps: local name → module path (for taint tracking across files).
 * Implements Python's module resolution logic from javascript.py:767-786.
 *
 * @param {Array} imports - From extractImports()
 * @param {Array} import_specifiers - Flat specifiers from extractImports()
 * @returns {Object} - Map of { localName: modulePath }
 */
function extractRefs(imports, import_specifiers) {
    const resolved = {};

    // Build line -> module mapping from imports
    const lineToModule = new Map();
    for (const imp of imports) {
        const modulePath = imp.module || imp.target;
        if (!modulePath) continue;
        lineToModule.set(imp.line, modulePath);

        // Extract module name from path: 'lodash/map' → 'map'
        const moduleName = modulePath.split('/').pop().replace(/\.(js|ts|jsx|tsx)$/, '');
        if (moduleName) {
            resolved[moduleName] = modulePath;
        }
    }

    // Map imported names to module using flat specifiers
    for (const spec of import_specifiers) {
        const modulePath = lineToModule.get(spec.import_line);
        if (modulePath && spec.specifier_name) {
            resolved[spec.specifier_name] = modulePath;
        }
    }

    return resolved;
}
