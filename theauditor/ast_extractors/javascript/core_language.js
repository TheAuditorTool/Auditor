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
 *
 * NORMALIZATION (2025-11-26):
 * - Functions return flat junction arrays instead of nested structures
 * - func_params, func_decorators, func_decorator_args, func_param_decorators
 * - class_decorators, class_decorator_args
 * - ZERO FALLBACK: Nested arrays REMOVED from parent objects
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
    // Note: Synthetic nodes may not have position info - use defaults
    const pos = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));
    serialized.line = pos.line + 1;
    const end = sourceFile.getLineAndCharacterOfPosition(node.getEnd());
    serialized.endLine = end.line + 1;

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
 * NORMALIZED OUTPUT (2025-11-26):
 * Returns object with:
 * - functions: Array of function metadata (WITHOUT nested parameters/decorators)
 * - func_params: Flat array of {function_name, function_line, param_index, param_name, param_type}
 * - func_decorators: Flat array of {function_name, function_line, decorator_index, decorator_name, decorator_line}
 * - func_decorator_args: Flat array of {function_name, function_line, decorator_index, arg_index, arg_value}
 * - func_param_decorators: Flat array of {function_name, function_line, param_index, decorator_name, decorator_args}
 *
 * @param {Object} sourceFile - TypeScript source file node
 * @param {Object} checker - TypeScript type checker
 * @param {Object} ts - TypeScript compiler API
 * @returns {Object} - { functions, func_params, func_decorators, func_decorator_args, func_param_decorators }
 */
function extractFunctions(sourceFile, checker, ts) {
    const functions = [];
    const func_params = [];
    const func_decorators = [];
    const func_decorator_args = [];
    const func_param_decorators = [];
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
        const func_line = line + 1;
        const func_entry = {
            line: func_line,
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

            // Extract parameters to FLAT func_params array
            if (node.parameters && Array.isArray(node.parameters)) {
                node.parameters.forEach((param, paramIndex) => {
                    let paramName = '';
                    let paramType = null;

                    // Extract parameter type annotation
                    if (param.type) {
                        paramType = param.type.getText(sourceFile);
                    }

                    // Extract parameter decorators to FLAT func_param_decorators array
                    if (param.decorators && param.decorators.length > 0) {
                        param.decorators.forEach(decorator => {
                            let decoratorName = '';
                            let decoratorArgs = null;

                            if (decorator.expression) {
                                if (decorator.expression.kind === ts.SyntaxKind.Identifier) {
                                    decoratorName = decorator.expression.text || decorator.expression.escapedText || '';
                                } else if (decorator.expression.kind === ts.SyntaxKind.CallExpression) {
                                    const callExpr = decorator.expression;
                                    if (callExpr.expression && callExpr.expression.kind === ts.SyntaxKind.Identifier) {
                                        decoratorName = callExpr.expression.text || callExpr.expression.escapedText || '';
                                    }
                                    if (callExpr.arguments && callExpr.arguments.length > 0) {
                                        decoratorArgs = callExpr.arguments.map(arg => {
                                            if (arg.kind === ts.SyntaxKind.StringLiteral) {
                                                return arg.text;
                                            }
                                            return arg.getText ? arg.getText(sourceFile) : '[complex]';
                                        }).join(', ');
                                    }
                                }
                            }

                            if (decoratorName) {
                                func_param_decorators.push({
                                    function_name: func_name,
                                    function_line: func_line,
                                    param_index: paramIndex,
                                    decorator_name: decoratorName,
                                    decorator_args: decoratorArgs
                                });
                            }
                        });
                    }

                    // Extract parameter name (handle destructuring)
                    if (param.name) {
                        const nameKind = ts.SyntaxKind[param.name.kind];
                        if (nameKind === 'Identifier') {
                            paramName = param.name.text || param.name.escapedText || '';
                        } else if (nameKind === 'ObjectBindingPattern') {
                            // Destructured parameter: ({ id, name }) -> extract individual bindings
                            param.name.elements.forEach((element, bindingIndex) => {
                                if (element.name && element.name.text) {
                                    func_params.push({
                                        function_name: func_name,
                                        function_line: func_line,
                                        param_index: paramIndex,
                                        param_name: element.name.text,
                                        param_type: paramType
                                    });
                                }
                            });
                            return; // Skip the main push since we handled destructuring
                        } else if (nameKind === 'ArrayBindingPattern') {
                            // Array destructuring: ([first, second]) -> extract individual bindings
                            param.name.elements.forEach((element, bindingIndex) => {
                                if (element.name && element.name.text) {
                                    func_params.push({
                                        function_name: func_name,
                                        function_line: func_line,
                                        param_index: paramIndex,
                                        param_name: element.name.text,
                                        param_type: paramType
                                    });
                                }
                            });
                            return; // Skip the main push since we handled destructuring
                        }
                    }

                    if (paramName) {
                        func_params.push({
                            function_name: func_name,
                            function_line: func_line,
                            param_index: paramIndex,
                            param_name: paramName,
                            param_type: paramType
                        });
                    }
                });
            }

            // Extract method/function decorators to FLAT func_decorators and func_decorator_args arrays
            if (node.decorators && node.decorators.length > 0) {
                node.decorators.forEach((decorator, decoratorIndex) => {
                    let decoratorName = '';
                    let decoratorLine = func_line;

                    // Get decorator line
                    const decPos = sourceFile.getLineAndCharacterOfPosition(decorator.getStart(sourceFile));
                    decoratorLine = decPos.line + 1;

                    if (decorator.expression) {
                        if (decorator.expression.kind === ts.SyntaxKind.Identifier) {
                            decoratorName = decorator.expression.text || decorator.expression.escapedText || '';
                        } else if (decorator.expression.kind === ts.SyntaxKind.CallExpression) {
                            const callExpr = decorator.expression;
                            if (callExpr.expression && callExpr.expression.kind === ts.SyntaxKind.Identifier) {
                                decoratorName = callExpr.expression.text || callExpr.expression.escapedText || '';
                            }

                            // Extract decorator arguments to flat array
                            if (callExpr.arguments && callExpr.arguments.length > 0) {
                                callExpr.arguments.forEach((arg, argIndex) => {
                                    let argValue = '';
                                    if (arg.kind === ts.SyntaxKind.StringLiteral) {
                                        argValue = arg.text;
                                    } else if (arg.kind === ts.SyntaxKind.ObjectLiteralExpression) {
                                        argValue = arg.getText(sourceFile);
                                    } else {
                                        argValue = arg.getText ? arg.getText(sourceFile) : '[complex]';
                                    }

                                    func_decorator_args.push({
                                        function_name: func_name,
                                        function_line: func_line,
                                        decorator_index: decoratorIndex,
                                        arg_index: argIndex,
                                        arg_value: argValue
                                    });
                                });
                            }
                        }
                    }

                    if (decoratorName) {
                        func_decorators.push({
                            function_name: func_name,
                            function_line: func_line,
                            decorator_index: decoratorIndex,
                            decorator_name: decoratorName,
                            decorator_line: decoratorLine
                        });
                    }
                });
            }

            // Extract type metadata using TypeScript checker
            if (checker) {
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
            }

            // NOTE: parameters and decorators are NO LONGER stored on func_entry
            // They are extracted to flat junction arrays above (ZERO FALLBACK)

            functions.push(func_entry);
        }

        ts.forEachChild(node, traverse);
    }

    traverse(sourceFile);

    // DEBUG: Log extraction results if env var set
    if (process.env.THEAUDITOR_DEBUG) {
        console.error(`[DEBUG JS] extractFunctions: Extracted ${functions.length} functions, ${func_params.length} params, ${func_decorators.length} decorators`);
    }

    return {
        functions: functions,
        func_params: func_params,
        func_decorators: func_decorators,
        func_decorator_args: func_decorator_args,
        func_param_decorators: func_param_decorators
    };
}

/**
 * Extract class declarations for symbols table.
 *
 * NORMALIZED OUTPUT (2025-11-26):
 * Returns object with:
 * - classes: Array of class metadata (WITHOUT nested decorators)
 * - class_decorators: Flat array of {class_name, class_line, decorator_index, decorator_name, decorator_line}
 * - class_decorator_args: Flat array of {class_name, class_line, decorator_index, arg_index, arg_value}
 *
 * @param {Object} sourceFile - TypeScript source file
 * @param {Object} checker - TypeScript type checker
 * @param {Object} ts - TypeScript compiler API
 * @returns {Object} - { classes, class_decorators, class_decorator_args }
 */
function extractClasses(sourceFile, checker, ts) {
    const classes = [];
    const class_decorators = [];
    const class_decorator_args = [];

    function traverse(node) {
        if (!node) return;
        const kind = ts.SyntaxKind[node.kind];

        if (kind === 'ClassDeclaration') {
            const { line, character } = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));
            const class_line = line + 1;
            const className = node.name ? (node.name.text || node.name.escapedText || 'UnknownClass') : 'UnknownClass';

            const classEntry = {
                line: class_line,
                col: character,
                column: character,
                name: className,
                type: 'class',
                kind: kind
            };

            // Extract decorators to FLAT class_decorators and class_decorator_args arrays
            if (node.decorators && node.decorators.length > 0) {
                node.decorators.forEach((decorator, decoratorIndex) => {
                    let decoratorName = '';
                    let decoratorLine = class_line;

                    // Get decorator line
                    const decPos = sourceFile.getLineAndCharacterOfPosition(decorator.getStart(sourceFile));
                    decoratorLine = decPos.line + 1;

                    if (decorator.expression) {
                        if (decorator.expression.kind === ts.SyntaxKind.Identifier) {
                            decoratorName = decorator.expression.text || decorator.expression.escapedText || '';
                        } else if (decorator.expression.kind === ts.SyntaxKind.CallExpression) {
                            const callExpr = decorator.expression;
                            if (callExpr.expression && callExpr.expression.kind === ts.SyntaxKind.Identifier) {
                                decoratorName = callExpr.expression.text || callExpr.expression.escapedText || '';
                            }

                            // Extract decorator arguments to flat array
                            if (callExpr.arguments && callExpr.arguments.length > 0) {
                                callExpr.arguments.forEach((arg, argIndex) => {
                                    let argValue = '';
                                    if (arg.kind === ts.SyntaxKind.StringLiteral) {
                                        argValue = arg.text;
                                    } else if (arg.kind === ts.SyntaxKind.NumericLiteral) {
                                        argValue = arg.text;
                                    } else if (arg.kind === ts.SyntaxKind.TrueKeyword) {
                                        argValue = 'true';
                                    } else if (arg.kind === ts.SyntaxKind.FalseKeyword) {
                                        argValue = 'false';
                                    } else if (arg.kind === ts.SyntaxKind.ObjectLiteralExpression) {
                                        argValue = arg.getText(sourceFile);
                                    } else {
                                        argValue = arg.getText ? arg.getText(sourceFile) : '[complex]';
                                    }

                                    class_decorator_args.push({
                                        class_name: className,
                                        class_line: class_line,
                                        decorator_index: decoratorIndex,
                                        arg_index: argIndex,
                                        arg_value: argValue
                                    });
                                });
                            }
                        }
                    }

                    if (decoratorName) {
                        class_decorators.push({
                            class_name: className,
                            class_line: class_line,
                            decorator_index: decoratorIndex,
                            decorator_name: decoratorName,
                            decorator_line: decoratorLine
                        });
                    }
                });
            }

            // Extract type metadata using TypeScript checker
            if (checker && node.name) {
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

            // NOTE: decorators are NO LONGER stored on classEntry
            // They are extracted to flat junction arrays above (ZERO FALLBACK)

            classes.push(classEntry);
        }
        // ClassExpression: const MyClass = class { ... } or const MyClass = class MyClass { ... }
        else if (kind === 'ClassExpression') {
            const { line, character } = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));
            const class_line = line + 1;

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
                line: class_line,
                col: character,
                column: character,
                name: className,
                type: 'class',
                kind: kind
            };

            // Extract same type metadata as ClassDeclaration
            if (checker && node.name) {
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

    return {
        classes: classes,
        class_decorators: class_decorators,
        class_decorator_args: class_decorator_args
    };
}

/**
 * Extract class property declarations (TypeScript/JavaScript ES2022+).
 * Captures class fields with type annotations, modifiers, and initializers.
 * Critical for ORM model understanding and sensitive field tracking.
 *
 * Examples:
 *   - declare username: string;              -> has_declare=true, property_type="string"
 *   - private password_hash: string;         -> access_modifier="private"
 *   - email: string | null;                  -> property_type="string | null"
 *   - readonly id: number = 1;               -> is_readonly=true, initializer="1"
 *   - account?: Account;                     -> is_optional=true, property_type="Account"
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

    // Build line->function map (deeper functions override)
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
