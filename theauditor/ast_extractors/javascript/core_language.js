/**
 * Core Language Extractors - Structure Layer
 *
 * Language structure and scope analysis extractors. These extractors
 * capture fundamental TypeScript/JavaScript code organization patterns.
 *
 * STABILITY: HIGH - Rarely changes once language features are implemented.
 * Only modify when adding support for new ECMAScript/TypeScript syntax.
 *
 * DEPENDENCIES: None (foundation layer)
 * USED BY: data_flow.js (scope map), security_extractors.js, framework_extractors.js
 *
 * Architecture:
 * - Extracted from: core_ast_extractors.js (refactored 2025-11-03)
 * - Used by: ES Module and CommonJS batch templates
 * - Assembly: Runtime file loading + concatenation in js_helper_templates.py
 *
 * Functions (6 language structure extractors):
 * 1. serializeNodeForCFG() - AST serialization (legacy, minimal)
 * 2. extractFunctions() - Function metadata with type annotations
 * 3. extractClasses() - Class declarations and expressions
 * 4. extractClassProperties() - Class field declarations
 * 5. buildScopeMap() - Line-to-function mapping for scope context
 * 6. countNodes() - AST complexity metrics (utility)
 */

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
                    let paramDecorators = [];

                    // Extract parameter decorators (e.g., @Inject, @Param)
                    if (param.decorators && param.decorators.length > 0) {
                        paramDecorators = param.decorators.map(decorator => {
                            const decoratorEntry = {};
                            if (decorator.expression) {
                                if (decorator.expression.kind === ts.SyntaxKind.Identifier) {
                                    decoratorEntry.name = decorator.expression.text || decorator.expression.escapedText;
                                } else if (decorator.expression.kind === ts.SyntaxKind.CallExpression) {
                                    const callExpr = decorator.expression;
                                    if (callExpr.expression && callExpr.expression.kind === ts.SyntaxKind.Identifier) {
                                        decoratorEntry.name = callExpr.expression.text || callExpr.expression.escapedText;
                                    }
                                    if (callExpr.arguments && callExpr.arguments.length > 0) {
                                        decoratorEntry.arguments = callExpr.arguments.map(arg => {
                                            if (arg.kind === ts.SyntaxKind.StringLiteral) {
                                                return arg.text;
                                            }
                                            return arg.getText ? arg.getText(sourceFile) : '[complex]';
                                        });
                                    }
                                }
                            }
                            return decoratorEntry;
                        });
                    }

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
                        // ARCHITECTURAL CONTRACT: Python expects { name: "paramName" } dict
                        // See typescript_impl.py:295-314 for the consuming code
                        // Python will extract param.get("name") string and store in func_params
                        func_entry.parameters.push({ name: paramName });
                    }
                });
            }

            // Extract method/function decorators (e.g., @Get, @Post, @Query, @Mutation)
            if (node.decorators && node.decorators.length > 0) {
                func_entry.decorators = node.decorators.map(decorator => {
                    const decoratorEntry = {};
                    if (decorator.expression) {
                        if (decorator.expression.kind === ts.SyntaxKind.Identifier) {
                            decoratorEntry.name = decorator.expression.text || decorator.expression.escapedText;
                        } else if (decorator.expression.kind === ts.SyntaxKind.CallExpression) {
                            const callExpr = decorator.expression;
                            if (callExpr.expression && callExpr.expression.kind === ts.SyntaxKind.Identifier) {
                                decoratorEntry.name = callExpr.expression.text || callExpr.expression.escapedText;
                            }
                            if (callExpr.arguments && callExpr.arguments.length > 0) {
                                decoratorEntry.arguments = callExpr.arguments.map(arg => {
                                    if (arg.kind === ts.SyntaxKind.StringLiteral) {
                                        return arg.text;
                                    } else if (arg.kind === ts.SyntaxKind.ObjectLiteralExpression) {
                                        // Simplified object literal extraction
                                        const obj = {};
                                        arg.properties.forEach(prop => {
                                            if (prop.kind === ts.SyntaxKind.PropertyAssignment && prop.name) {
                                                const key = prop.name.text || prop.name.escapedText;
                                                if (key && prop.initializer && prop.initializer.kind === ts.SyntaxKind.StringLiteral) {
                                                    obj[key] = prop.initializer.text;
                                                }
                                            }
                                        });
                                        return obj;
                                    }
                                    return arg.getText ? arg.getText(sourceFile) : '[complex]';
                                });
                            }
                        }
                    }
                    return decoratorEntry;
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

            // Extract decorators (for Angular, NestJS, TypeGraphQL, etc.)
            if (node.decorators && node.decorators.length > 0) {
                classEntry.decorators = node.decorators.map(decorator => {
                    const decoratorEntry = {};

                    // Get decorator name
                    if (decorator.expression) {
                        if (decorator.expression.kind === ts.SyntaxKind.Identifier) {
                            // Simple decorator: @Component
                            decoratorEntry.name = decorator.expression.text || decorator.expression.escapedText;
                        } else if (decorator.expression.kind === ts.SyntaxKind.CallExpression) {
                            // Decorator with arguments: @Component({...})
                            const callExpr = decorator.expression;
                            if (callExpr.expression && callExpr.expression.kind === ts.SyntaxKind.Identifier) {
                                decoratorEntry.name = callExpr.expression.text || callExpr.expression.escapedText;
                            }

                            // Extract arguments
                            if (callExpr.arguments && callExpr.arguments.length > 0) {
                                decoratorEntry.arguments = callExpr.arguments.map(arg => {
                                    // Try to get literal value
                                    if (arg.kind === ts.SyntaxKind.StringLiteral) {
                                        return arg.text;
                                    } else if (arg.kind === ts.SyntaxKind.NumericLiteral) {
                                        return arg.text;
                                    } else if (arg.kind === ts.SyntaxKind.TrueKeyword) {
                                        return true;
                                    } else if (arg.kind === ts.SyntaxKind.FalseKeyword) {
                                        return false;
                                    } else if (arg.kind === ts.SyntaxKind.ObjectLiteralExpression) {
                                        // For object literals, extract properties if possible
                                        const obj = {};
                                        arg.properties.forEach(prop => {
                                            if (prop.kind === ts.SyntaxKind.PropertyAssignment) {
                                                const key = prop.name ? (prop.name.text || prop.name.escapedText) : null;
                                                if (key && prop.initializer) {
                                                    if (prop.initializer.kind === ts.SyntaxKind.StringLiteral) {
                                                        obj[key] = prop.initializer.text;
                                                    } else if (prop.initializer.kind === ts.SyntaxKind.ArrayLiteralExpression) {
                                                        obj[key] = '[array]'; // Simplified for now
                                                    }
                                                }
                                            }
                                        });
                                        return obj;
                                    } else {
                                        // Return text representation for complex arguments
                                        return arg.getText ? arg.getText(sourceFile) : '[complex]';
                                    }
                                });
                            }
                        }
                    }

                    return decoratorEntry;
                });
            }

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
        let startLine = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line;
        let endLine = sourceFile.getLineAndCharacterOfPosition(node.end).line;

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
        let actualFunctionNode = node;  // Track the actual function node for line calculation

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
            // CRITICAL FIX: Handle wrapped functions like this.asyncHandler(async () => {})
            // Common pattern in controllers: create = this.asyncHandler(async (req, res) => { ... })
            else if (initKind === 'CallExpression' && node.initializer.arguments && node.initializer.arguments.length > 0) {
                const firstArg = node.initializer.arguments[0];
                const firstArgKind = ts.SyntaxKind[firstArg.kind];
                if (firstArgKind === 'ArrowFunction' || firstArgKind === 'FunctionExpression') {
                    const propName = node.name ? (node.name.text || node.name.escapedText || 'anonymous') : 'anonymous';
                    funcName = classStack.length > 0 ? classStack[classStack.length - 1] + '.' + propName : propName;
                    // Use the INNER function's range (the actual arrow function), not the outer PropertyDeclaration
                    actualFunctionNode = firstArg;
                    startLine = sourceFile.getLineAndCharacterOfPosition(firstArg.getStart(sourceFile)).line;
                    endLine = sourceFile.getLineAndCharacterOfPosition(firstArg.end).line;
                }
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
