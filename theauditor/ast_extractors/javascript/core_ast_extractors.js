/**
 * Core AST Extractors - Foundation Layer
 *
 * Fundamental JavaScript/TypeScript language feature extraction. These extractors
 * form the stable foundation for all derived pattern detection.
 *
 * STABILITY: HIGH - Rarely changes once language features are implemented.
 * Only modify when adding support for new ECMAScript/TypeScript syntax.
 *
 * DEPENDENCIES: None (foundation layer)
 * USED BY: security_extractors.js, framework_extractors.js
 *
 * Architecture:
 * - Extracted from: js_helper_templates.py (refactored 2025-01-24)
 * - Used by: ES Module and CommonJS batch templates
 * - Assembly: Runtime file loading + concatenation in js_helper_templates.py
 *
 * Functions (14 core extractors):
 * 1. extractImports() - Import/require/dynamic import detection
 * 2. serializeNodeForCFG() - AST serialization (legacy, minimal)
 * 3. extractFunctions() - Function metadata with type annotations
 * 4. extractClasses() - Class declarations and expressions
 * 5. extractCalls() - Call expressions and property accesses
 * 6. buildScopeMap() - Line-to-function mapping for scope context
 * 7. extractAssignments() - Variable assignments with data flow
 * 8. extractFunctionCallArgs() - Function call arguments (foundation for taint)
 * 9. extractReturns() - Return statements with scope
 * 10. extractObjectLiterals() - Object literals for dynamic dispatch
 * 11. extractVariableUsage() - Variable reference tracking (utility)
 * 12. extractImportStyles() - Bundle optimization analysis (utility)
 * 13. extractRefs() - Module resolution mappings for cross-file analysis
 * 14. countNodes() - AST complexity metrics (utility)
 *
 * Current size: 1,628 lines (2025-01-24)
 * Growth policy: If exceeds 2,000 lines, split by language feature category
 * (e.g., imports_exports.js, functions_classes.js, data_flow.js)
 */

/**
 * Extract import statements from TypeScript AST.
 *
 * Detects both ES6 imports and CommonJS require() calls.
 * Critical for dependency tracking and taint analysis.
 *
 * @param {Object} sourceFile - TypeScript source file
 * @param {Object} ts - TypeScript compiler API
 * @returns {Array} - List of import statements
 */
function extractImports(sourceFile, ts) {
    const imports = [];

    function visit(node) {
        // ES6 Import declarations: import { foo } from 'bar'
        if (node.kind === ts.SyntaxKind.ImportDeclaration) {
            const moduleSpecifier = node.moduleSpecifier;
            if (moduleSpecifier && moduleSpecifier.text) {
                const { line } = sourceFile.getLineAndCharacterOfPosition(node.getStart ? node.getStart(sourceFile) : node.pos);

                // Extract import specifiers (what's being imported)
                const specifiers = [];
                if (node.importClause) {
                    // Default import: import Foo from 'bar'
                    if (node.importClause.name) {
                        specifiers.push({
                            name: node.importClause.name.text || node.importClause.name.escapedText,
                            isDefault: true
                        });
                    }

                    // Named imports: import { a, b } from 'bar'
                    if (node.importClause.namedBindings) {
                        const bindings = node.importClause.namedBindings;

                        // Namespace import: import * as foo from 'bar'
                        if (bindings.kind === ts.SyntaxKind.NamespaceImport) {
                            specifiers.push({
                                name: bindings.name.text || bindings.name.escapedText,
                                isNamespace: true
                            });
                        }
                        // Named imports: import { a, b } from 'bar'
                        else if (bindings.kind === ts.SyntaxKind.NamedImports && bindings.elements) {
                            bindings.elements.forEach(element => {
                                specifiers.push({
                                    name: element.name.text || element.name.escapedText,
                                    isNamed: true
                                });
                            });
                        }
                    }
                }

                imports.push({
                    kind: 'import',
                    module: moduleSpecifier.text,
                    line: line + 1,
                    specifiers: specifiers
                });
            }
        }

        // CommonJS require: const x = require('bar')
        else if (node.kind === ts.SyntaxKind.CallExpression) {
            const expr = node.expression;
            if (expr && (expr.text === 'require' || expr.escapedText === 'require')) {
                const args = node.arguments;
                if (args && args.length > 0 && args[0].kind === ts.SyntaxKind.StringLiteral) {
                    const { line } = sourceFile.getLineAndCharacterOfPosition(node.getStart ? node.getStart(sourceFile) : node.pos);
                    imports.push({
                        kind: 'require',
                        module: args[0].text,
                        line: line + 1,
                        specifiers: []
                    });
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
                    line: line + 1,
                    specifiers: []
                });
            }
        }

        ts.forEachChild(node, visit);
    }

    visit(sourceFile);
    return imports;
}

/**
 * Serialize TypeScript AST node to plain JavaScript object (CFG-only mode).
 *
 * This is a MINIMAL serialization that only includes fields needed for CFG construction:
 * - kind: Node type (IfStatement, ForStatement, etc.)
 * - line/endLine: Position information
 * - name: Function/variable names
 * - children: Child nodes for traversal
 * - initializer: For property declarations
 * - condition/expression: For control flow
 *
 * This avoids the 512MB crash by NOT serializing:
 * - Type information
 * - Symbol tables
 * - Full text content
 * - Parent references
 */
function serializeNodeForCFG(node, sourceFile, ts, depth = 0, maxDepth = 100) {
    if (!node || depth > maxDepth) {
        return null;
    }

    const kind = ts.SyntaxKind[node.kind];
    const serialized = { kind };

    // Position information (REQUIRED for CFG)
    try {
        const pos = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));
        serialized.line = pos.line + 1;
        const end = sourceFile.getLineAndCharacterOfPosition(node.getEnd());
        serialized.endLine = end.line + 1;
    } catch (e) {
        // Fallback for synthetic nodes
        serialized.line = 1;
        serialized.endLine = 1;
    }

    // Name extraction (for functions, variables, etc.)
    if (node.name) {
        if (typeof node.name === 'string') {
            serialized.name = { text: node.name };
        } else if (node.name.text || node.name.escapedText) {
            serialized.name = { text: node.name.text || node.name.escapedText };
        }
    }

    // Serialize children (REQUIRED for CFG traversal)
    const children = [];
    ts.forEachChild(node, child => {
        const serializedChild = serializeNodeForCFG(child, sourceFile, ts, depth + 1, maxDepth);
        if (serializedChild) {
            children.push(serializedChild);
        }
    });
    if (children.length > 0) {
        serialized.children = children;
    }

    // Special handling for specific node types needed by CFG
    if (node.initializer) {
        serialized.initializer = serializeNodeForCFG(node.initializer, sourceFile, ts, depth + 1, maxDepth);
    }

    if (node.condition) {
        serialized.condition = serializeNodeForCFG(node.condition, sourceFile, ts, depth + 1, maxDepth);
    }

    if (node.expression) {
        serialized.expression = serializeNodeForCFG(node.expression, sourceFile, ts, depth + 1, maxDepth);
    }

    return serialized;
}

/**
 * Extract function metadata directly from TypeScript AST with type annotations.
 * This replaces Python's extract_typescript_functions_for_symbols().
 *
 * @param {Object} sourceFile - TypeScript source file node
 * @param {Object} checker - TypeScript type checker
 * @param {Object} ts - TypeScript compiler API
 * @returns {Array} - List of function metadata objects
 */
function extractFunctions(sourceFile, checker, ts) {
    const functions = [];
    const class_stack = [];

    function traverse(node) {
        if (!node) return;
        const kind = ts.SyntaxKind[node.kind];

        // Track class context for qualified names
        if (kind === 'ClassDeclaration') {
            const className = node.name ? node.name.text : 'UnknownClass';
            class_stack.push(className);
            ts.forEachChild(node, traverse);
            class_stack.pop();
            return;
        }

        let is_function_like = false;
        let func_name = '';
        const { line, character } = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));
        const func_entry = {
            line: line + 1,
            col: character,
            column: character,
            kind: kind
        };

        // FunctionDeclaration
        if (kind === 'FunctionDeclaration') {
            is_function_like = true;
            func_name = node.name ? node.name.text : 'anonymous';
        }
        // MethodDeclaration
        else if (kind === 'MethodDeclaration') {
            is_function_like = true;
            const method_name = node.name ? node.name.text : 'anonymous';
            func_name = class_stack.length > 0 ? class_stack[class_stack.length - 1] + '.' + method_name : method_name;
        }
        // PropertyDeclaration with ArrowFunction or function-like initializer
        else if (kind === 'PropertyDeclaration' && node.initializer) {
            const init_kind = ts.SyntaxKind[node.initializer.kind];
            // Detect arrow functions, function expressions, and call expressions that return functions
            // (baseline parity: property assignments like `list = this.asyncHandler(...)`)
            if (init_kind === 'ArrowFunction' || init_kind === 'FunctionExpression' || init_kind === 'CallExpression') {
                is_function_like = true;
                const prop_name = node.name ? node.name.text : 'anonymous';
                func_name = class_stack.length > 0 ? class_stack[class_stack.length - 1] + '.' + prop_name : prop_name;
            }
        }
        // Constructor
        else if (kind === 'Constructor') {
            is_function_like = true;
            func_name = class_stack.length > 0 ? class_stack[class_stack.length - 1] + '.constructor' : 'constructor';
        }
        // GetAccessor / SetAccessor
        else if (kind === 'GetAccessor' || kind === 'SetAccessor') {
            is_function_like = true;
            const accessor_name = node.name ? node.name.text : 'anonymous';
            const prefix = kind === 'GetAccessor' ? 'get ' : 'set ';
            func_name = class_stack.length > 0 ? class_stack[class_stack.length - 1] + '.' + prefix + accessor_name : prefix + accessor_name;
        }

        if (is_function_like && func_name && func_name !== 'anonymous') {
            func_entry.name = func_name;
            func_entry.type = 'function';

            // CRITICAL: Extract parameter names for inter-procedural taint tracking
            // This enables real parameter names (data, _createdBy) instead of generic (arg0, arg1)
            // Multi-hop taint analysis requires matching actual parameter names to arguments
            func_entry.parameters = [];
            if (node.parameters && Array.isArray(node.parameters)) {
                node.parameters.forEach(param => {
                    let paramName = '';
                    if (param.name) {
                        const nameKind = ts.SyntaxKind[param.name.kind];
                        if (nameKind === 'Identifier') {
                            paramName = param.name.text || param.name.escapedText || '';
                        } else if (nameKind === 'ObjectBindingPattern') {
                            // Destructured parameter: ({ id, name }) -> extract as 'destructured'
                            paramName = 'destructured';
                        } else if (nameKind === 'ArrayBindingPattern') {
                            // Array destructuring: ([first, second]) -> extract as 'destructured'
                            paramName = 'destructured';
                        }
                    }
                    if (paramName) {
                        func_entry.parameters.push(paramName);
                    }
                });
            }

            // CRITICAL: Extract type metadata using TypeScript checker
            try {
                const symbol = checker.getSymbolAtLocation(node.name || node);
                if (symbol) {
                    const type = checker.getTypeOfSymbolAtLocation(symbol, node);
                    if (type) {
                        func_entry.type_annotation = checker.typeToString(type);

                        if (type.flags & ts.TypeFlags.Any) {
                            func_entry.is_any = true;
                        }
                        if (type.flags & ts.TypeFlags.Unknown) {
                            func_entry.is_unknown = true;
                        }
                        if (type.isTypeParameter && type.isTypeParameter()) {
                            func_entry.is_generic = true;
                        }

                        // Extract return type
                        const callSignatures = type.getCallSignatures();
                        if (callSignatures && callSignatures.length > 0) {
                            const returnType = callSignatures[0].getReturnType();
                            func_entry.return_type = checker.typeToString(returnType);
                        }

                        // Extract base class for methods
                        const baseTypes = type.getBaseTypes ? type.getBaseTypes() : null;
                        if (baseTypes && baseTypes.length > 0) {
                            func_entry.extends_type = baseTypes.map(t => checker.typeToString(t)).join(', ');
                        }
                    }
                }
            } catch (typeError) {
                // Type extraction failed - continue without type info
            }

            functions.push(func_entry);
        }

        ts.forEachChild(node, traverse);
    }

    traverse(sourceFile);

    // DEBUG: Log extraction results if env var set
    if (process.env.THEAUDITOR_DEBUG) {
        console.error(`[DEBUG JS] extractFunctions: Extracted ${functions.length} functions from ${sourceFile.fileName}`);
        if (functions.length > 0 && functions.length <= 5) {
            functions.forEach(f => {
                const params = f.parameters ? f.parameters.join(', ') : 'NONE';
                console.error(`[DEBUG JS]   - ${f.name}(${params}) at line ${f.line}`);
            });
        }
    }

    return functions;
}

/**
 * Extract class declarations for symbols table.
 *
 * @param {Object} sourceFile - TypeScript source file
 * @param {Object} checker - TypeScript type checker
 * @param {Object} ts - TypeScript compiler API
 * @returns {Array} - List of class declarations
 */
function extractClasses(sourceFile, checker, ts) {
    const classes = [];

    function traverse(node) {
        if (!node) return;
        const kind = ts.SyntaxKind[node.kind];

        if (kind === 'ClassDeclaration') {
            const { line, character } = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));
            const className = node.name ? (node.name.text || node.name.escapedText || 'UnknownClass') : 'UnknownClass';

            const classEntry = {
                line: line + 1,
                col: character,
                column: character,
                name: className,
                type: 'class',
                kind: kind
            };

            // Extract type metadata using TypeScript checker
            try {
                if (node.name) {
                    const symbol = checker.getSymbolAtLocation(node.name);
                    if (symbol) {
                        const type = checker.getTypeOfSymbolAtLocation(symbol, node);
                        if (type) {
                            classEntry.type_annotation = checker.typeToString(type);
                        }
                    }
                }

                // Extract extends clause
                if (node.heritageClauses) {
                    for (const clause of node.heritageClauses) {
                        if (clause.token === ts.SyntaxKind.ExtendsKeyword && clause.types && clause.types.length > 0) {
                            const extendsType = clause.types[0];
                            classEntry.extends_type = extendsType.expression ? (extendsType.expression.text || extendsType.expression.escapedText) : null;
                        }
                    }
                }

                // Extract type parameters
                if (node.typeParameters && node.typeParameters.length > 0) {
                    classEntry.has_type_params = true;
                    classEntry.type_params = node.typeParameters.map(tp => {
                        const paramName = tp.name ? (tp.name.text || tp.name.escapedText) : 'T';
                        if (tp.constraint) {
                            const constraintText = tp.constraint.getText ? tp.constraint.getText(sourceFile) : '';
                            return `${paramName} extends ${constraintText}`;
                        }
                        return paramName;
                    }).join(', ');
                }
            } catch (e) {
                // Type extraction failed - metadata will be incomplete
            }

            classes.push(classEntry);
        }
        // ClassExpression: const MyClass = class { ... } or const MyClass = class MyClass { ... }
        else if (kind === 'ClassExpression') {
            const { line, character } = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));

            // Try to get name from class itself
            let className = node.name ? (node.name.text || node.name.escapedText) : null;

            // If anonymous, try to get name from parent variable declaration
            if (!className && node.parent) {
                const parentKind = ts.SyntaxKind[node.parent.kind];
                if (parentKind === 'VariableDeclaration' && node.parent.name) {
                    className = node.parent.name.text || node.parent.name.escapedText;
                }
                // Also check for export default class { ... }
                else if (parentKind === 'ExportAssignment') {
                    className = 'DefaultExportClass';
                }
            }

            if (!className) {
                className = 'AnonymousClass';
            }

            const classEntry = {
                line: line + 1,
                col: character,
                column: character,
                name: className,
                type: 'class',
                kind: kind
            };

            // Extract same type metadata as ClassDeclaration
            try {
                if (node.name) {
                    const symbol = checker.getSymbolAtLocation(node.name);
                    if (symbol) {
                        const type = checker.getTypeOfSymbolAtLocation(symbol, node);
                        if (type) {
                            classEntry.type_annotation = checker.typeToString(type);
                        }
                    }
                }

                // Extract extends clause
                if (node.heritageClauses) {
                    for (const clause of node.heritageClauses) {
                        if (clause.token === ts.SyntaxKind.ExtendsKeyword && clause.types && clause.types.length > 0) {
                            const extendsType = clause.types[0];
                            classEntry.extends_type = extendsType.expression ? (extendsType.expression.text || extendsType.expression.escapedText) : null;
                        }
                    }
                }

                // Extract type parameters
                if (node.typeParameters && node.typeParameters.length > 0) {
                    classEntry.has_type_params = true;
                    classEntry.type_params = node.typeParameters.map(tp => {
                        const paramName = tp.name ? (tp.name.text || tp.name.escapedText) : 'T';
                        if (tp.constraint) {
                            const constraintText = tp.constraint.getText ? tp.constraint.getText(sourceFile) : '';
                            return `${paramName} extends ${constraintText}`;
                        }
                        return paramName;
                    }).join(', ');
                }
            } catch (e) {
                // Type extraction failed - metadata will be incomplete
            }

            classes.push(classEntry);
        }
        // REMOVED: InterfaceDeclaration and TypeAliasDeclaration extraction
        //
        // Baseline Python extractor incorrectly classified TypeScript interfaces and type aliases as "class" symbols.
        // This contaminated the symbols.class and react_components tables with non-class types:
        //   - Interfaces: BadgeProps, CapacityIndicatorProps, ImportMetaEnv
        //   - Type aliases: JWTPayload, RequestWithId
        //   - Result: 385 false "React components" (interfaces/types marked as class components)
        //
        // Phase 5 correctly extracts ONLY actual ClassDeclaration and ClassExpression nodes.
        // Benefits:
        //   - Clean class data for downstream consumers
        //   - Accurate React component detection (only classes extending React.Component)
        //   - Better taint analysis (no interface contamination)
        //   - Reduced false positives in pattern rules
        //
        // Trade-off: Lower total count (655 vs 1,039 react_components) but HIGHER DATA QUALITY

        ts.forEachChild(node, traverse);
    }

    traverse(sourceFile);
    return classes;
}

/**
 * Extract class property declarations (TypeScript/JavaScript ES2022+).
 * Captures class fields with type annotations, modifiers, and initializers.
 * Critical for ORM model understanding and sensitive field tracking.
 *
 * Examples:
 *   - declare username: string;              → has_declare=true, property_type="string"
 *   - private password_hash: string;         → access_modifier="private"
 *   - email: string | null;                  → property_type="string | null"
 *   - readonly id: number = 1;               → is_readonly=true, initializer="1"
 *   - account?: Account;                     → is_optional=true, property_type="Account"
 *
 * @param {Object} sourceFile - TypeScript source file node
 * @param {Object} ts - TypeScript compiler API
 * @returns {Array} - List of class property objects
 */
function extractClassProperties(sourceFile, ts) {
    const properties = [];
    let currentClass = null;

    function traverse(node) {
        if (!node) return;
        const kind = ts.SyntaxKind[node.kind];

        // Track current class context
        if (kind === 'ClassDeclaration' || kind === 'ClassExpression') {
            const previousClass = currentClass;
            currentClass = node.name ? (node.name.text || node.name.escapedText || 'UnknownClass') : 'UnknownClass';

            // If ClassExpression assigned to variable, use variable name
            if (currentClass === 'UnknownClass' && node.parent) {
                const parentKind = ts.SyntaxKind[node.parent.kind];
                if (parentKind === 'VariableDeclaration' && node.parent.name) {
                    currentClass = node.parent.name.text || node.parent.name.escapedText;
                }
            }

            ts.forEachChild(node, traverse);

            currentClass = previousClass;
            return;
        }

        // PropertyDeclaration: class members
        if (kind === 'PropertyDeclaration' && currentClass) {
            const { line } = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));
            const propertyName = node.name ? (node.name.text || node.name.escapedText || '') : '';

            if (!propertyName) {
                ts.forEachChild(node, traverse);
                return;
            }

            const property = {
                line: line + 1,
                class_name: currentClass,
                property_name: propertyName,
                property_type: null,
                is_optional: false,
                is_readonly: false,
                access_modifier: null,
                has_declare: false,
                initializer: null
            };

            // Type annotation
            if (node.type) {
                property.property_type = node.type.getText(sourceFile);
            }

            // Optional modifier (?)
            if (node.questionToken) {
                property.is_optional = true;
            }

            // Modifiers: readonly, private, protected, public, declare
            if (node.modifiers) {
                for (const modifier of node.modifiers) {
                    const modifierKind = ts.SyntaxKind[modifier.kind];
                    if (modifierKind === 'ReadonlyKeyword') {
                        property.is_readonly = true;
                    } else if (modifierKind === 'PrivateKeyword') {
                        property.access_modifier = 'private';
                    } else if (modifierKind === 'ProtectedKeyword') {
                        property.access_modifier = 'protected';
                    } else if (modifierKind === 'PublicKeyword') {
                        property.access_modifier = 'public';
                    } else if (modifierKind === 'DeclareKeyword') {
                        property.has_declare = true;
                    }
                }
            }

            // Initializer (default value)
            if (node.initializer) {
                property.initializer = node.initializer.getText(sourceFile).substring(0, 500);
            }

            properties.push(property);
        }

        ts.forEachChild(node, traverse);
    }

    traverse(sourceFile);
    return properties;
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

    function traverse(node) {
        if (!node) return;
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

                            relationships.push({
                                line: line + 1,
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
 * Extract call expressions with arguments and cross-file resolution.
 * This replaces Python's extract_semantic_ast_symbols() for calls.
 *
 * @param {Object} sourceFile - TypeScript source file node
 * @param {Object} checker - TypeScript type checker
 * @param {Object} ts - TypeScript compiler API
 * @param {string} projectRoot - Project root path for relative path resolution
 * @returns {Array} - List of call/property access objects
 */
function extractCalls(sourceFile, checker, ts, projectRoot) {
    const symbols = [];

    function traverse(node) {
        if (!node) return;
        const kind = ts.SyntaxKind[node.kind];
        const { line, character } = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));

        // PropertyAccessExpression: req.body, res.send, etc.
        if (kind === 'PropertyAccessExpression') {
            let full_name = '';
            try {
                // Build dotted name
                if (node.expression && node.expression.kind === ts.SyntaxKind.Identifier) {
                    const left = node.expression.text || node.expression.escapedText || '';
                    const right = node.name ? (node.name.text || node.name.escapedText || '') : '';
                    if (left && right) {
                        full_name = left + '.' + right;
                    }
                } else if (node.expression && node.expression.kind === ts.SyntaxKind.ThisKeyword) {
                    // Handle this.property patterns (critical for baseline parity)
                    const right = node.name ? (node.name.text || node.name.escapedText || '') : '';
                    if (right) {
                        full_name = 'this.' + right;
                    }
                } else {
                    // Nested/complex property access - recursively build
                    const buildName = (n) => {
                        if (!n) return '';
                        const k = ts.SyntaxKind[n.kind];
                        if (k === 'Identifier') {
                            return n.text || n.escapedText || '';
                        } else if (k === 'ThisKeyword') {
                            return 'this';
                        } else if (k === 'PropertyAccessExpression') {
                            const left = buildName(n.expression);
                            const right = n.name ? (n.name.text || n.name.escapedText || '') : '';
                            return left && right ? left + '.' + right : left || right;
                        } else if (k === 'CallExpression') {
                            // Handle getData().map pattern - extract callee name + ()
                            const calleeName = buildName(n.expression);
                            return calleeName ? calleeName + '()' : '';
                        } else if (k === 'NewExpression') {
                            // Handle new Date().toISOString pattern
                            if (n.expression) {
                                const className = buildName(n.expression);
                                return className ? 'new ' + className + '()' : '';
                            }
                            return '';
                        } else if (k === 'ParenthesizedExpression' || k === 'AsExpression' || k === 'TypeAssertionExpression') {
                            // Handle (expr).prop or (expr as Type).prop
                            return n.expression ? buildName(n.expression) : '';
                        } else if (k === 'ElementAccessExpression') {
                            // Handle array[0].prop
                            const objName = buildName(n.expression);
                            return objName ? objName + '[' : '[';
                        }
                        return '';
                    };
                    full_name = buildName(node);
                }
            } catch (e) {
                // Name construction failed
            }

            if (full_name) {
                // Determine type: property or call
                let db_type = 'property';
                const sinkPatterns = ['res.send', 'res.render', 'res.json', 'response.write', 'innerHTML', 'outerHTML', 'exec', 'eval', 'system', 'spawn'];
                for (const sink of sinkPatterns) {
                    if (full_name.includes(sink)) {
                        db_type = 'call';
                        break;
                    }
                }

                symbols.push({
                    name: full_name,
                    line: line + 1,
                    column: character,
                    type: db_type
                });
            }
        }
        // CallExpression
        else if (kind === 'CallExpression') {
            let callee_name = '';
            try {
                if (node.expression) {
                    const expr_kind = ts.SyntaxKind[node.expression.kind];
                    if (expr_kind === 'Identifier') {
                        callee_name = node.expression.text || node.expression.escapedText || '';
                    } else if (expr_kind === 'PropertyAccessExpression') {
                        // Build dotted name for method calls (same logic as PropertyAccessExpression)
                        const buildName = (n) => {
                            if (!n) return '';
                            const k = ts.SyntaxKind[n.kind];
                            if (k === 'Identifier') {
                                return n.text || n.escapedText || '';
                            } else if (k === 'ThisKeyword') {
                                return 'this';
                            } else if (k === 'PropertyAccessExpression') {
                                const left = buildName(n.expression);
                                const right = n.name ? (n.name.text || n.name.escapedText || '') : '';
                                return left && right ? left + '.' + right : left || right;
                            } else if (k === 'CallExpression') {
                                const calleeName = buildName(n.expression);
                                return calleeName ? calleeName + '()' : '';
                            } else if (k === 'NewExpression') {
                                if (n.expression) {
                                    const className = buildName(n.expression);
                                    return className ? 'new ' + className + '()' : '';
                                }
                                return '';
                            } else if (k === 'ParenthesizedExpression' || k === 'AsExpression' || k === 'TypeAssertionExpression') {
                                return n.expression ? buildName(n.expression) : '';
                            } else if (k === 'ElementAccessExpression') {
                                const objName = buildName(n.expression);
                                return objName ? objName + '[' : '[';
                            }
                            return '';
                        };
                        callee_name = buildName(node.expression);
                    }
                }
            } catch (e) {
                // Name extraction failed
            }

            if (callee_name) {
                symbols.push({
                    name: callee_name,
                    line: line + 1,
                    column: character,
                    type: 'call'
                });
            }
            // Recurse into CallExpression children (deduplication handles any overlaps)
        }
        // Identifier: Catch property accesses that may be in Identifier form (baseline parity)
        else if (kind === 'Identifier') {
            const text = node.text || node.escapedText || '';
            // Check if it looks like a property access pattern (has dot notation)
            if (text && text.includes('.')) {
                // Determine type based on pattern (same logic as PropertyAccessExpression)
                let db_type = 'property';
                const sinkPatterns = ['res.send', 'res.render', 'res.json', 'response.write', 'innerHTML', 'outerHTML', 'exec', 'eval', 'system', 'spawn'];
                for (const sink of sinkPatterns) {
                    if (text.includes(sink)) {
                        db_type = 'call';
                        break;
                    }
                }

                symbols.push({
                    name: text,
                    line: line + 1,
                    column: character,
                    type: db_type
                });
            }
        }

        ts.forEachChild(node, traverse);
    }

    traverse(sourceFile);

    // DEDUPLICATION: Same symbol may appear via multiple AST paths
    // (e.g., req.body as PropertyAccessExpression + nested Identifier)
    // Deduplicate by (name, line, column, type) tuple to match baseline behavior
    const seen = new Map();
    const deduped = [];
    for (const sym of symbols) {
        const key = `${sym.name}|${sym.line}|${sym.column}|${sym.type}`;
        if (!seen.has(key)) {
            seen.set(key, true);
            deduped.push(sym);
        }
    }

    // DEBUG: Log extraction results if env var set
    if (process.env.THEAUDITOR_DEBUG) {
        console.error(`[DEBUG JS] extractCalls: Extracted ${symbols.length} calls/properties (${deduped.length} after dedup) from ${sourceFile.fileName}`);
        if (deduped.length > 0 && deduped.length <= 5) {
            deduped.forEach(s => console.error(`[DEBUG JS]   - ${s.name} (${s.type}) at line ${s.line}`));
        }
    }

    return deduped;
}

/**
 * Build a map of line numbers to function names for scope context.
 * This is critical for associating assignments, returns, etc. with their containing functions.
 * Implements the same logic as Python's build_scope_map() in typescript_impl.py:353-537.
 *
 * @param {Object} sourceFile - TypeScript source file
 * @param {Object} ts - TypeScript compiler API
 * @returns {Map<number, string>} - Map of line number (1-indexed) to function name
 */
function buildScopeMap(sourceFile, ts) {
    const functionRanges = [];
    const classStack = [];

    function collectFunctions(node, depth = 0, parent = null) {
        if (depth > 100 || !node) return;

        const kind = ts.SyntaxKind[node.kind];
        const { line: startLine } = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));
        const { line: endLine } = sourceFile.getLineAndCharacterOfPosition(node.end);

        // Track class context
        if (kind === 'ClassDeclaration') {
            const className = node.name ? (node.name.text || node.name.escapedText || 'UnknownClass') : 'UnknownClass';
            classStack.push(className);
            ts.forEachChild(node, child => collectFunctions(child, depth + 1, node));
            classStack.pop();
            return;
        }

        // Collect function-like nodes
        let funcName = null;

        if (kind === 'FunctionDeclaration') {
            funcName = node.name ? (node.name.text || node.name.escapedText || 'anonymous') : 'anonymous';
        } else if (kind === 'MethodDeclaration') {
            const methodName = node.name ? (node.name.text || node.name.escapedText || 'anonymous') : 'anonymous';
            funcName = classStack.length > 0 ? classStack[classStack.length - 1] + '.' + methodName : methodName;
        } else if (kind === 'PropertyDeclaration' && node.initializer) {
            const initKind = ts.SyntaxKind[node.initializer.kind];
            if (initKind === 'ArrowFunction' || initKind === 'FunctionExpression') {
                const propName = node.name ? (node.name.text || node.name.escapedText || 'anonymous') : 'anonymous';
                funcName = classStack.length > 0 ? classStack[classStack.length - 1] + '.' + propName : propName;
            }
        } else if (kind === 'Constructor') {
            funcName = classStack.length > 0 ? classStack[classStack.length - 1] + '.constructor' : 'constructor';
        } else if (kind === 'GetAccessor' || kind === 'SetAccessor') {
            const accessorName = node.name ? (node.name.text || node.name.escapedText || 'anonymous') : 'anonymous';
            const prefix = kind === 'GetAccessor' ? 'get ' : 'set ';
            funcName = classStack.length > 0 ? classStack[classStack.length - 1] + '.' + prefix + accessorName : prefix + accessorName;
        } else if (kind === 'ArrowFunction' || kind === 'FunctionExpression') {
            // FIXED: Extract name from parent context instead of hardcoding '<anonymous>'
            // This handles modern TypeScript patterns:
            // - const exportPlants = async () => {} (VariableDeclaration)
            // - { exportPlants: async () => {} } (PropertyAssignment)
            // - class methods are already handled by PropertyDeclaration above
            funcName = getNameFromParent(node, parent, ts, classStack);
        }

        // Only add named functions to ranges (filter out 'anonymous' and '<anonymous>')
        // Anonymous functions will inherit the name from their parent scope
        if (funcName && funcName !== 'anonymous' && funcName !== '<anonymous>') {
            functionRanges.push({
                name: funcName,
                start: startLine + 1,  // Convert to 1-indexed
                end: endLine + 1,
                depth: depth
            });
        }

        ts.forEachChild(node, child => collectFunctions(child, depth + 1, node));
    }

    function getNameFromParent(node, parent, ts, classStack) {
        if (!parent) return '<anonymous>';

        const parentKind = ts.SyntaxKind[parent.kind];

        // VariableDeclaration: const exportPlants = async () => {}
        if (parentKind === 'VariableDeclaration' && parent.name) {
            const varName = parent.name.text || parent.name.escapedText || 'anonymous';
            return classStack.length > 0 ? classStack[classStack.length - 1] + '.' + varName : varName;
        }

        // PropertyAssignment: { exportPlants: async () => {} }
        if (parentKind === 'PropertyAssignment' && parent.name) {
            const propName = parent.name.text || parent.name.escapedText || 'anonymous';
            return classStack.length > 0 ? classStack[classStack.length - 1] + '.' + propName : propName;
        }

        // ShorthandPropertyAssignment: { exportPlants } where exportPlants is a function
        if (parentKind === 'ShorthandPropertyAssignment' && parent.name) {
            const propName = parent.name.text || parent.name.escapedText || 'anonymous';
            return classStack.length > 0 ? classStack[classStack.length - 1] + '.' + propName : propName;
        }

        // BinaryExpression: ExportService.exportPlants = async () => {}
        if (parentKind === 'BinaryExpression' && parent.left) {
            const leftText = parent.left.getText ? parent.left.getText() : '';
            if (leftText) {
                return leftText;
            }
        }

        return '<anonymous>';
    }

    collectFunctions(sourceFile);

    // Build line→function map (deeper functions override)
    const scopeMap = new Map();

    // Sort by start line, then reverse to process deeper functions last
    functionRanges.sort((a, b) => {
        if (a.start !== b.start) return a.start - b.start;
        return b.depth - a.depth;  // Deeper functions last
    });

    for (const func of functionRanges) {
        for (let line = func.start; line <= func.end; line++) {
            scopeMap.set(line, func.name);
        }
    }

    return scopeMap;
}

/**
 * Extract variable assignments with scope context for taint analysis.
 * Implements Python's extract_typescript_assignments() from typescript_impl.py:1014-1184.
 *
 * @param {Object} sourceFile - TypeScript source file
 * @param {Object} ts - TypeScript compiler API
 * @param {Map} scopeMap - Pre-built line→function mapping
 * @returns {Array} - Assignment records
 */
function extractAssignments(sourceFile, ts, scopeMap) {
    const assignments = [];
    const visited = new Set();

    function extractVarsFromNode(node, sourceFile, ts) {
        const vars = [];
        const seen = new Set();

        function visit(n) {
            if (!n) return;

            const kind = ts.SyntaxKind[n.kind];

            // Extract individual identifiers
            if (n.kind === ts.SyntaxKind.Identifier) {
                const text = n.text || n.escapedText;
                if (text && !seen.has(text)) {
                    vars.push(text);
                    seen.add(text);
                }
            }

            // CRITICAL FIX: Extract compound property access chains
            // Matches baseline: "TenantContext.runWithTenant", "plant.area?"
            if (n.kind === ts.SyntaxKind.PropertyAccessExpression) {
                const fullText = n.getText(sourceFile);
                if (fullText && !seen.has(fullText)) {
                    vars.push(fullText);
                    seen.add(fullText);
                }
            }

            // ULTRA-GREEDY MODE: Extract EVERYTHING baseline extracted
            // Element access: array[0], obj['key'], formData[key]
            if (n.kind === ts.SyntaxKind.ElementAccessExpression) {
                const fullText = n.getText(sourceFile);
                if (fullText && !seen.has(fullText)) {
                    vars.push(fullText);
                    seen.add(fullText);
                }
            }

            // this keyword
            if (n.kind === ts.SyntaxKind.ThisKeyword) {
                const fullText = 'this';
                if (!seen.has(fullText)) {
                    vars.push(fullText);
                    seen.add(fullText);
                }
            }

            // new expressions: new Date(), new Error()
            if (n.kind === ts.SyntaxKind.NewExpression) {
                const fullText = n.getText(sourceFile);
                if (fullText && !seen.has(fullText)) {
                    vars.push(fullText);
                    seen.add(fullText);
                }
            }

            // Parenthesized expressions: (genetics.yield_estimate * genetics.purchase_quantity)
            // Type assertions: (req.body as Type)
            // Non-null assertions: obj!.prop
            // Array literals: ['a', 'b'] as const
            // ALL of these need their full text extracted
            if (kind === 'ParenthesizedExpression' ||
                kind === 'AsExpression' ||
                kind === 'TypeAssertionExpression' ||
                kind === 'NonNullExpression' ||
                kind === 'ArrayLiteralExpression') {
                const fullText = n.getText(sourceFile);
                if (fullText && !seen.has(fullText)) {
                    vars.push(fullText);
                    seen.add(fullText);
                }
            }

            ts.forEachChild(n, visit);
        }

        visit(node);
        return vars;
    }

    function traverse(node, depth = 0) {
        if (depth > 100 || !node) return;

        const nodeId = node.pos + '-' + node.kind;
        if (visited.has(nodeId)) return;
        visited.add(nodeId);

        const kind = ts.SyntaxKind[node.kind];

        // Pattern 1: VariableDeclaration (const x = y)
        if (kind === 'VariableDeclaration') {
            const { line } = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));
            const inFunction = scopeMap.get(line + 1) || 'global';

            const name = node.name;
            const initializer = node.initializer;

            if (name && initializer) {
                // Handle simple identifier
                if (name.kind === ts.SyntaxKind.Identifier) {
                    const targetVar = name.text || name.escapedText;
                    if (targetVar) {
                        assignments.push({
                            target_var: targetVar,
                            source_expr: initializer.getText(sourceFile).substring(0, 500),
                            line: line + 1,
                            in_function: inFunction,
                            source_vars: extractVarsFromNode(initializer, sourceFile, ts),
                            property_path: null  // NULL for non-destructured assignments
                        });
                    }
                }
                // Handle object destructuring: const {x, y} = obj
                // CRITICAL FOR TAINT: Preserve property paths for destructured variables
                // Example: const { id, batchId } = req.params
                //   - target_var: id, property_path: req.params.id
                //   - target_var: batchId, property_path: req.params.batchId
                else if (name.kind === ts.SyntaxKind.ObjectBindingPattern && name.elements) {
                    const sourceExprText = initializer.getText(sourceFile).substring(0, 500);

                    name.elements.forEach(elem => {
                        if (elem.name && elem.name.kind === ts.SyntaxKind.Identifier) {
                            const targetVar = elem.name.text || elem.name.escapedText;
                            if (!targetVar) return;

                            // Determine the property name being destructured
                            // Case 1: { id } - property name is 'id'
                            // Case 2: { id: userId } - property name is 'id', target is 'userId'
                            let propertyName = targetVar;  // Default: same as target
                            if (elem.propertyName && elem.propertyName.kind === ts.SyntaxKind.Identifier) {
                                // Renamed destructuring: { id: userId }
                                propertyName = elem.propertyName.text || elem.propertyName.escapedText;
                            }

                            // Build property path: sourceExpr.propertyName
                            // Example: req.params + .id = req.params.id
                            const propertyPath = sourceExprText + '.' + propertyName;

                            assignments.push({
                                target_var: targetVar,
                                source_expr: sourceExprText,
                                line: line + 1,
                                in_function: inFunction,
                                source_vars: extractVarsFromNode(initializer, sourceFile, ts),
                                property_path: propertyPath  // NEW: Full path for taint tracking
                            });
                        }
                    });
                }
                // Handle array destructuring: const [x, y] = arr
                // CRITICAL FOR TAINT: Preserve array index paths
                // Example: const [first, second] = array
                //   - target_var: first, property_path: array[0]
                //   - target_var: second, property_path: array[1]
                else if (name.kind === ts.SyntaxKind.ArrayBindingPattern && name.elements) {
                    const sourceExprText = initializer.getText(sourceFile).substring(0, 500);

                    name.elements.forEach((elem, index) => {
                        if (elem.kind === ts.SyntaxKind.BindingElement && elem.name && elem.name.kind === ts.SyntaxKind.Identifier) {
                            const targetVar = elem.name.text || elem.name.escapedText;
                            if (!targetVar) return;

                            // Build property path with array index: sourceExpr[index]
                            // Example: array + [0] = array[0]
                            const propertyPath = sourceExprText + '[' + index + ']';

                            assignments.push({
                                target_var: targetVar,
                                source_expr: sourceExprText,
                                line: line + 1,
                                in_function: inFunction,
                                source_vars: extractVarsFromNode(initializer, sourceFile, ts),
                                property_path: propertyPath  // NEW: Array index path for taint tracking
                            });
                        }
                    });
                }
            }
        }
        // Pattern 2: BinaryExpression with = operator (x = y)
        else if (kind === 'BinaryExpression' && node.operatorToken && node.operatorToken.kind === ts.SyntaxKind.EqualsToken) {
            const { line } = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));
            const inFunction = scopeMap.get(line + 1) || 'global';

            const left = node.left;
            const right = node.right;

            if (left && right) {
                const targetVar = left.getText(sourceFile);
                const sourceExpr = right.getText(sourceFile).substring(0, 500);

                assignments.push({
                    target_var: targetVar,
                    source_expr: sourceExpr,
                    line: line + 1,
                    in_function: inFunction,
                    source_vars: extractVarsFromNode(right, sourceFile, ts),
                    property_path: null  // NULL for non-destructured assignments
                });
            }
        }

        ts.forEachChild(node, child => traverse(child, depth + 1));
    }

    traverse(sourceFile);
    return assignments;
}

/**
 * Extract function call arguments with caller context for inter-procedural taint tracking.
 * Implements Python's extract_typescript_calls_with_args() from typescript_impl.py:1382-1501.
 *
 * @param {Object} sourceFile - TypeScript source file
 * @param {Object} checker - TypeScript type checker
 * @param {Object} ts - TypeScript compiler API
 * @param {Map} scopeMap - Pre-built line→function mapping
 * @param {Map} functionParams - Function name → parameter names mapping
 * @param {string} projectRoot - Project root for relative paths
 * @returns {Array} - Call argument records
 */
function extractFunctionCallArgs(sourceFile, checker, ts, scopeMap, functionParams, projectRoot) {
    const calls = [];
    const visited = new Set();

    function buildDottedName(node, ts) {
        if (!node) return '';
        const kind = ts.SyntaxKind[node.kind];
        if (kind === 'Identifier') {
            return node.text || node.escapedText || '';
        }
        if (kind === 'PropertyAccessExpression') {
            const left = buildDottedName(node.expression, ts);
            const right = node.name ? (node.name.text || node.name.escapedText || '') : '';
            return left && right ? left + '.' + right : left || right;
        }
        // CRITICAL FIX: Handle CallExpression for method chaining
        // Example: res.status().json → builds "res.status().json"
        // This enables complete taint flow tracking for chained calls
        if (kind === 'CallExpression') {
            const callee = buildDottedName(node.expression, ts);
            if (callee) {
                return callee + '()';  // Append () to show it's a call result
            }
            return '';
        }
        return '';
    }

    function traverse(node, depth = 0) {
        if (depth > 100 || !node) return;

        const nodeId = node.pos + '-' + node.kind;
        if (visited.has(nodeId)) return;

        // CRITICAL FIX: For chained CallExpressions, process intermediate calls BEFORE marking this node as visited
        // This ensures: res.status(404).json({}) captures BOTH res.status(404) AND res.status().json({})
        // Without this, ts.forEachChild visits inner CallExpression first, marks it visited, then outer call can't re-process it
        if (node.kind === ts.SyntaxKind.CallExpression && node.expression) {
            const exprKind = ts.SyntaxKind[node.expression.kind];
            if (exprKind === 'PropertyAccessExpression' && node.expression.expression) {
                const innerExprKind = ts.SyntaxKind[node.expression.expression.kind];
                if (innerExprKind === 'CallExpression') {
                    const innerNodeId = node.expression.expression.pos + '-' + node.expression.expression.kind;
                    // Process intermediate call FIRST, before we add THIS node to visited
                    if (!visited.has(innerNodeId)) {
                        traverse(node.expression.expression, depth + 1);
                    }
                }
            } else if (exprKind === 'CallExpression') {
                const innerNodeId = node.expression.pos + '-' + node.expression.kind;
                if (!visited.has(innerNodeId)) {
                    traverse(node.expression, depth + 1);
                }
            }
        }

        // NOW mark this node as visited AFTER processing intermediate calls
        visited.add(nodeId);

        if (node.kind === ts.SyntaxKind.CallExpression) {
            const { line } = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));
            const callerFunction = scopeMap.get(line + 1) || 'global';

            // Extract callee name
            let calleeName = '';
            if (node.expression) {
                const exprKind = ts.SyntaxKind[node.expression.kind];
                if (exprKind === 'Identifier') {
                    calleeName = node.expression.text || node.expression.escapedText || '';
                } else if (exprKind === 'PropertyAccessExpression') {
                    calleeName = buildDottedName(node.expression, ts);
                } else if (exprKind === 'CallExpression') {
                    // Handle chained calls: (res.status()).json becomes "res.status().json"
                    calleeName = buildDottedName(node.expression, ts);
                }
            }

            // Resolve callee file path using checker
            let calleeFilePath = null;
            try {
                if (checker && node.expression) {
                    const symbol = checker.getSymbolAtLocation(node.expression);
                    if (symbol && symbol.declarations && symbol.declarations.length > 0) {
                        const decl = symbol.declarations[0];
                        const calleeSource = decl.getSourceFile();
                        if (calleeSource && projectRoot) {
                            calleeFilePath = path.relative(projectRoot, calleeSource.fileName).replace(/\\/g, '/');
                        }
                    }
                }
            } catch (e) {
                // Resolution failed - field will be null
            }

            // Extract arguments (ONLY if calleeName is non-empty - CHECK constraint)
            if (calleeName) {
                const args = node.arguments || [];
                const calleeBaseName = calleeName.split('.').pop();
                const params = functionParams.get(calleeBaseName) || [];

                // FIX: Handle 0-arg calls (createApp(), useState(), etc.)
                // For 0-arg calls, create baseline record with NULL argument fields
                // This fixes 30.7% missing coverage in function_call_args table
                if (args.length === 0) {
                    calls.push({
                        line: line + 1,
                        caller_function: callerFunction,
                        callee_function: calleeName,
                        argument_index: null,        // NULL = no arguments (schema allows NULL as of 2025-10-25)
                        argument_expr: null,
                        param_name: null,
                        callee_file_path: calleeFilePath
                    });
                } else {
                    // Original logic for calls WITH arguments (1+ args)
                    args.forEach((arg, i) => {
                        const paramName = i < params.length ? params[i] : 'arg' + i;
                        const argExpr = arg.getText(sourceFile).substring(0, 500);

                        calls.push({
                            line: line + 1,
                            caller_function: callerFunction,
                            callee_function: calleeName,
                            argument_index: i,
                            argument_expr: argExpr,
                            param_name: paramName,
                            callee_file_path: calleeFilePath
                        });
                    });
                }
            }
        }

        ts.forEachChild(node, child => traverse(child, depth + 1));
    }

    traverse(sourceFile);
    return calls;
}

/**
 * Extract return statements with JSX detection for React component analysis.
 * Implements Python's extract_typescript_returns() from typescript_impl.py:1504-1641.
 *
 * @param {Object} sourceFile - TypeScript source file
 * @param {Object} ts - TypeScript compiler API
 * @param {Map} scopeMap - Pre-built line→function mapping
 * @returns {Array} - Return statement records
 */
function extractReturns(sourceFile, ts, scopeMap) {
    const returns = [];
    const functionReturnCounts = new Map();
    const visited = new Set();

    function extractVarsFromNode(node, sourceFile, ts) {
        const vars = [];
        const seen = new Set();

        function visit(n) {
            if (!n) return;

            const kind = ts.SyntaxKind[n.kind];

            // Extract individual identifiers
            if (n.kind === ts.SyntaxKind.Identifier) {
                const text = n.text || n.escapedText;
                if (text && !seen.has(text)) {
                    vars.push(text);
                    seen.add(text);
                }
            }

            // CRITICAL FIX: Extract compound property access chains
            // Matches baseline: "TenantContext.runWithTenant", "plant.area?"
            if (n.kind === ts.SyntaxKind.PropertyAccessExpression) {
                const fullText = n.getText(sourceFile);
                if (fullText && !seen.has(fullText)) {
                    vars.push(fullText);
                    seen.add(fullText);
                }
            }

            // ULTRA-GREEDY MODE: Extract EVERYTHING baseline extracted
            // Element access: array[0], obj['key'], formData[key]
            if (n.kind === ts.SyntaxKind.ElementAccessExpression) {
                const fullText = n.getText(sourceFile);
                if (fullText && !seen.has(fullText)) {
                    vars.push(fullText);
                    seen.add(fullText);
                }
            }

            // this keyword
            if (n.kind === ts.SyntaxKind.ThisKeyword) {
                const fullText = 'this';
                if (!seen.has(fullText)) {
                    vars.push(fullText);
                    seen.add(fullText);
                }
            }

            // new expressions: new Date(), new Error()
            if (n.kind === ts.SyntaxKind.NewExpression) {
                const fullText = n.getText(sourceFile);
                if (fullText && !seen.has(fullText)) {
                    vars.push(fullText);
                    seen.add(fullText);
                }
            }

            // Parenthesized expressions: (genetics.yield_estimate * genetics.purchase_quantity)
            // Type assertions: (req.body as Type)
            // Non-null assertions: obj!.prop
            // Array literals: ['a', 'b'] as const
            // ALL of these need their full text extracted
            if (kind === 'ParenthesizedExpression' ||
                kind === 'AsExpression' ||
                kind === 'TypeAssertionExpression' ||
                kind === 'NonNullExpression' ||
                kind === 'ArrayLiteralExpression') {
                const fullText = n.getText(sourceFile);
                if (fullText && !seen.has(fullText)) {
                    vars.push(fullText);
                    seen.add(fullText);
                }
            }

            ts.forEachChild(n, visit);
        }

        visit(node);
        return vars;
    }

    function detectJsxInNode(node, ts) {
        const JSX_KINDS = new Set([
            'JsxElement', 'JsxSelfClosingElement', 'JsxFragment',
            'JsxOpeningElement', 'JsxClosingElement', 'JsxExpression'
        ]);

        const visited = new Set();

        function search(n, depth = 0) {
            if (depth > 30 || !n) return { hasJsx: false, isComponent: false };

            const id = n.pos + '-' + n.kind;
            if (visited.has(id)) return { hasJsx: false, isComponent: false };
            visited.add(id);

            const kind = ts.SyntaxKind[n.kind];

            // Direct JSX
            if (JSX_KINDS.has(kind)) {
                let isComponent = false;
                if (n.tagName) {
                    const tagName = n.tagName.text || n.tagName.escapedText || '';
                    isComponent = tagName.length > 0 && tagName[0] === tagName[0].toUpperCase();
                }
                return { hasJsx: true, isComponent };
            }

            // React.createElement (transformed JSX)
            if (kind === 'CallExpression' && n.expression) {
                const exprText = n.expression.getText ? n.expression.getText() : '';
                if (exprText.includes('React.createElement') || exprText.includes('jsx') || exprText.includes('_jsx')) {
                    return { hasJsx: true, isComponent: false };
                }
            }

            // Recurse
            let result = { hasJsx: false, isComponent: false };
            ts.forEachChild(n, child => {
                const childResult = search(child, depth + 1);
                if (childResult.hasJsx) {
                    result = childResult;
                }
            });
            return result;
        }

        return search(node);
    }

    function traverse(node, depth = 0) {
        if (depth > 100 || !node) return;

        const nodeId = node.pos + '-' + node.kind;
        if (visited.has(nodeId)) return;
        visited.add(nodeId);

        if (node.kind === ts.SyntaxKind.ReturnStatement) {
            const { line } = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));
            const functionName = scopeMap.get(line + 1) || 'global';

            // Track return index per function
            const currentCount = functionReturnCounts.get(functionName) || 0;
            functionReturnCounts.set(functionName, currentCount + 1);

            const expression = node.expression;
            let returnExpr = '';
            let hasJsx = false;
            let returnsComponent = false;
            let returnVars = [];

            if (expression) {
                returnExpr = expression.getText(sourceFile).substring(0, 1000);

                // Detect JSX
                const jsxDetection = detectJsxInNode(expression, ts);
                hasJsx = jsxDetection.hasJsx;
                returnsComponent = jsxDetection.isComponent;

                // Extract variables
                returnVars = extractVarsFromNode(expression, sourceFile, ts);
            }

            returns.push({
                function_name: functionName,
                line: line + 1,
                return_expr: returnExpr,
                return_vars: returnVars,
                has_jsx: hasJsx,
                returns_component: returnsComponent,
                return_index: currentCount + 1
            });
        }

        ts.forEachChild(node, child => traverse(child, depth + 1));
    }

    traverse(sourceFile);
    return returns;
}

/**
 * Extract object literal properties for dynamic dispatch resolution in taint analysis.
 * Implements Python's extract_typescript_object_literals() from typescript_impl.py:1662-1836.
 *
 * @param {Object} sourceFile - TypeScript source file
 * @param {Object} ts - TypeScript compiler API
 * @param {Map} scopeMap - Pre-built line→function mapping
 * @returns {Array} - Object literal property records
 */
function extractObjectLiterals(sourceFile, ts, scopeMap) {
    const literals = [];
    const visited = new Set();

    function extractFromObjectNode(objNode, varName, inFunction, sourceFile, ts, nestedLevel = 0) {
        if (!objNode || objNode.kind !== ts.SyntaxKind.ObjectLiteralExpression) return;

        const properties = objNode.properties || [];
        properties.forEach(prop => {
            if (!prop) return;

            const { line } = sourceFile.getLineAndCharacterOfPosition(prop.getStart(sourceFile));
            const kind = ts.SyntaxKind[prop.kind];

            if (kind === 'PropertyAssignment') {
                const propName = prop.name ? (prop.name.text || prop.name.escapedText || '<unknown>') : '<unknown>';
                const propValue = prop.initializer ? prop.initializer.getText(sourceFile).substring(0, 250) : '';

                literals.push({
                    line: line + 1,
                    variable_name: varName,
                    property_name: propName,
                    property_value: propValue,
                    property_type: 'value',
                    nested_level: nestedLevel,
                    in_function: inFunction
                });

                // CRITICAL FIX: RECURSIVELY traverse nested object literals
                // This matches baseline behavior which extracted ALL nesting levels
                // Without this, we lose 3,389 records (26.2%) from deeply nested objects (migrations, schemas, config)
                if (prop.initializer && prop.initializer.kind === ts.SyntaxKind.ObjectLiteralExpression) {
                    const nestedVarName = '<property:' + propName + '>';
                    extractFromObjectNode(prop.initializer, nestedVarName, inFunction, sourceFile, ts, nestedLevel + 1);
                }
            } else if (kind === 'ShorthandPropertyAssignment') {
                const propName = prop.name ? (prop.name.text || prop.name.escapedText || '<unknown>') : '<unknown>';

                literals.push({
                    line: line + 1,
                    variable_name: varName,
                    property_name: propName,
                    property_value: propName,  // Shorthand: { x } means { x: x }
                    property_type: 'shorthand',
                    nested_level: nestedLevel,
                    in_function: inFunction
                });
            } else if (kind === 'MethodDeclaration') {
                const methodName = prop.name ? (prop.name.text || prop.name.escapedText || '<unknown>') : '<unknown>';

                literals.push({
                    line: line + 1,
                    variable_name: varName,
                    property_name: methodName,
                    property_value: '<function>',
                    property_type: 'method',
                    nested_level: nestedLevel,
                    in_function: inFunction
                });
            }
        });
    }

    function traverse(node, depth = 0) {
        if (depth > 100 || !node) return;

        const nodeId = node.pos + '-' + node.kind;
        if (visited.has(nodeId)) return;
        visited.add(nodeId);

        const kind = ts.SyntaxKind[node.kind];
        const { line } = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));
        const inFunction = scopeMap.get(line + 1) || 'global';

        // Pattern 1: Variable Declaration (const x = { ... })
        if (kind === 'VariableDeclaration' && node.initializer && node.initializer.kind === ts.SyntaxKind.ObjectLiteralExpression) {
            const varName = node.name ? (node.name.text || node.name.escapedText || '<unknown>') : '<unknown>';
            extractFromObjectNode(node.initializer, varName, inFunction, sourceFile, ts);
        }
        // Pattern 2: Assignment (x = { ... })
        else if (kind === 'BinaryExpression' && node.operatorToken && node.operatorToken.kind === ts.SyntaxKind.EqualsToken) {
            if (node.right && node.right.kind === ts.SyntaxKind.ObjectLiteralExpression) {
                const varName = node.left ? node.left.getText(sourceFile) : '<unknown>';
                extractFromObjectNode(node.right, varName, inFunction, sourceFile, ts);
            }
        }
        // Pattern 3: Return statement (return { ... })
        else if (kind === 'ReturnStatement' && node.expression && node.expression.kind === ts.SyntaxKind.ObjectLiteralExpression) {
            const varName = '<return:' + inFunction + '>';
            extractFromObjectNode(node.expression, varName, inFunction, sourceFile, ts);
        }
        // Pattern 4: Function argument (fn({ ... }))
        else if (kind === 'CallExpression') {
            const args = node.arguments || [];
            const calleeName = node.expression ? node.expression.getText(sourceFile) : 'unknown';

            args.forEach((arg, i) => {
                if (arg.kind === ts.SyntaxKind.ObjectLiteralExpression) {
                    const varName = '<arg' + i + ':' + calleeName + '>';
                    extractFromObjectNode(arg, varName, inFunction, sourceFile, ts);
                }
            });
        }
        // Pattern 5: Array element ([{ ... }, { ... }])
        else if (kind === 'ArrayLiteralExpression') {
            const elements = node.elements || [];
            elements.forEach((elem, i) => {
                if (elem.kind === ts.SyntaxKind.ObjectLiteralExpression) {
                    const varName = '<array_elem' + i + '>';
                    extractFromObjectNode(elem, varName, inFunction, sourceFile, ts);
                }
            });
        }

        ts.forEachChild(node, child => traverse(child, depth + 1));
    }

    traverse(sourceFile);
    return literals;
}

/**
 * Compute variable usage from assignments and calls.
 * Implements Python's javascript.py:643-674 computed data.
 *
 * @param {Array} assignments - From extractAssignments
 * @param {Array} functionCallArgs - From extractFunctionCallArgs
 * @returns {Array} - Variable usage records
 */

function extractVariableUsage(assignments, functionCallArgs) {
    const usage = [];

    // Track writes from assignments
    assignments.forEach(assign => {
        usage.push({
            line: assign.line,
            variable_name: assign.target_var,
            usage_type: 'write',
            in_component: assign.in_function,
            in_hook: '',
            scope_level: assign.in_function === 'global' ? 0 : 1
        });

        // Track reads from source variables
        (assign.source_vars || []).forEach(varName => {
            usage.push({
                line: assign.line,
                variable_name: varName,
                usage_type: 'read',
                in_component: assign.in_function,
                in_hook: '',
                scope_level: assign.in_function === 'global' ? 0 : 1
            });
        });
    });

    // Track calls
    const seenCalls = new Set();
    functionCallArgs.forEach(call => {
        const key = call.line + '-' + call.callee_function;
        if (!seenCalls.has(key)) {
            seenCalls.add(key);
            usage.push({
                line: call.line,
                variable_name: call.callee_function,
                usage_type: 'call',
                in_component: call.caller_function,
                in_hook: '',
                scope_level: call.caller_function === 'global' ? 0 : 1
            });
        }
    });

    return usage;
}

/**
 * Analyze import statements for bundle optimization analysis.
 * Classifies: namespace (prevents tree-shaking) vs named (allows tree-shaking).
 * Implements Python's _analyze_import_styles() from javascript.py:790-853.
 *
 * @param {Array} imports - From extractImports()
 * @returns {Array} - Import style records
 */
function extractImportStyles(imports) {
    const styles = [];

    for (const imp of imports) {
        const target = imp.module || imp.target;
        if (!target) continue;

        const line = imp.line || 0;
        let import_style = null;
        let imported_names = null;
        let alias_name = null;

        // Extract names from specifiers
        const specifiers = imp.specifiers || [];
        const namespaceName = specifiers.find(s => s.isNamespace)?.name || null;
        const defaultName = specifiers.find(s => s.isDefault)?.name || null;
        const namedImports = specifiers.filter(s => s.isNamed).map(s => s.name);

        // Classify import style
        if (namespaceName) {
            // import * as lodash from 'lodash'
            import_style = 'namespace';
            alias_name = namespaceName;
        } else if (namedImports.length > 0) {
            // import { map, filter } from 'lodash'
            import_style = 'named';
            imported_names = namedImports;
        } else if (defaultName) {
            // import lodash from 'lodash'
            import_style = 'default';
            alias_name = defaultName;
        } else {
            // import 'polyfill'
            import_style = 'side-effect';
        }

        if (import_style) {
            const fullStatement = imp.text || `import ${import_style} from '${target}'`;

            styles.push({
                line: line,
                package: target,
                import_style: import_style,
                imported_names: imported_names,
                alias_name: alias_name,
                full_statement: fullStatement.substring(0, 200)
            });
        }
    }

    return styles;
}

/**
 * Extract module resolution mappings for cross-file analysis.
 * Maps: local name → module path (for taint tracking across files).
 * Implements Python's module resolution logic from javascript.py:767-786.
 *
 * @param {Array} imports - From extractImports()
 * @returns {Object} - Map of { localName: modulePath }
 */
function extractRefs(imports) {
    const resolved = {};

    for (const imp of imports) {
        const modulePath = imp.module || imp.target;
        if (!modulePath) continue;

        // Extract module name from path: 'lodash/map' → 'map'
        const moduleName = modulePath.split('/').pop().replace(/\.(js|ts|jsx|tsx)$/, '');

        if (moduleName) {
            resolved[moduleName] = modulePath;
        }

        // Also map imported names to module
        const specifiers = imp.specifiers || [];
        for (const spec of specifiers) {
            if (spec.name) {
                resolved[spec.name] = modulePath;
            }
        }
    }

    return resolved;
}


/**
 * Count total nodes in AST for complexity metrics.
 * Critical for downstream consumers that track codebase size.
 *
 * @param {Object} node - AST node to count from
 * @param {Object} ts - TypeScript compiler API
 * @returns {number} - Total node count
 */
function countNodes(node, ts) {
    if (!node) return 0;

    let count = 1;  // Count this node

    // Recursively count all children
    ts.forEachChild(node, child => {
        count += countNodes(child, ts);
    });

    return count;
}
