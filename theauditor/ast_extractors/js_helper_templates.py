"""JavaScript helper script templates for TypeScript AST extraction.

This module contains Node.js helper scripts that run in subprocess to extract
semantic ASTs using the TypeScript Compiler API. These are complete JavaScript
programs that cannot import Python code and must be self-contained.

Architecture:
- Shared components (naming heuristics, serialization) defined once
- Four template variants: ES Module/CommonJS × Single/Batch
- Templates use string formatting to inject shared components
"""

from typing import Literal

# ============================================================================
# SHARED JAVASCRIPT COMPONENTS
# ============================================================================
# ANONYMOUS_FUNCTION_NAMING_HEURISTICS deleted - only used by serializeNode (also deleted)
# NODE_SERIALIZATION deleted - Phase 5 batch templates set ast: null instead of serializing

IMPORT_EXTRACTION = '''
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
'''

# PHASE 4: SYMBOL_EXTRACTION constant deleted - replaced by inline type extraction in serializeNode()
# extractSymbols() function removed - single-pass AST traversal with type info is now the only mechanism

# ============================================================================
# PHASE 5: EXTRACTION-FIRST ARCHITECTURE
# ============================================================================
# Instead of serializing the full AST (512MB+) and extracting in Python,
# we extract data directly in JavaScript where the TypeScript checker lives.
# This sends only ~5MB of pre-processed data to Python, eliminating crashes.

EXTRACT_FUNCTIONS = '''
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
        // PropertyDeclaration with ArrowFunction
        else if (kind === 'PropertyDeclaration' && node.initializer) {
            const init_kind = ts.SyntaxKind[node.initializer.kind];
            if (init_kind === 'ArrowFunction' || init_kind === 'FunctionExpression') {
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
            functions.forEach(f => console.error(`[DEBUG JS]   - ${f.name} at line ${f.line}`));
        }
    }

    return functions;
}
'''

EXTRACT_CLASSES = '''
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

        ts.forEachChild(node, traverse);
    }

    traverse(sourceFile);
    return classes;
}
'''

EXTRACT_CALLS = '''
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
                } else if (node.expression && node.expression.kind === ts.SyntaxKind.PropertyAccessExpression) {
                    // Nested property access - recursively build
                    const buildName = (n) => {
                        if (!n) return '';
                        const k = ts.SyntaxKind[n.kind];
                        if (k === 'Identifier') {
                            return n.text || n.escapedText || '';
                        } else if (k === 'PropertyAccessExpression') {
                            const left = buildName(n.expression);
                            const right = n.name ? (n.name.text || n.name.escapedText || '') : '';
                            return left && right ? left + '.' + right : left || right;
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
                        // Build dotted name for method calls
                        const buildName = (n) => {
                            if (!n) return '';
                            const k = ts.SyntaxKind[n.kind];
                            if (k === 'Identifier') {
                                return n.text || n.escapedText || '';
                            } else if (k === 'PropertyAccessExpression') {
                                const left = buildName(n.expression);
                                const right = n.name ? (n.name.text || n.name.escapedText || '') : '';
                                return left && right ? left + '.' + right : left || right;
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
'''

BUILD_SCOPE_MAP = '''
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

    function collectFunctions(node, depth = 0) {
        if (depth > 100 || !node) return;

        const kind = ts.SyntaxKind[node.kind];
        const { line: startLine } = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));
        const { line: endLine } = sourceFile.getLineAndCharacterOfPosition(node.end);

        // Track class context
        if (kind === 'ClassDeclaration') {
            const className = node.name ? (node.name.text || node.name.escapedText || 'UnknownClass') : 'UnknownClass';
            classStack.push(className);
            ts.forEachChild(node, child => collectFunctions(child, depth + 1));
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
            // For arrow functions/function expressions, use placeholder - will be named later if needed
            funcName = '<anonymous>';
        }

        if (funcName && funcName !== 'anonymous') {
            functionRanges.push({
                name: funcName,
                start: startLine + 1,  // Convert to 1-indexed
                end: endLine + 1,
                depth: depth
            });
        }

        ts.forEachChild(node, child => collectFunctions(child, depth + 1));
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
'''

EXTRACT_ASSIGNMENTS = '''
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
            if (n.kind === ts.SyntaxKind.Identifier) {
                const text = n.text || n.escapedText;
                if (text && !seen.has(text)) {
                    vars.push(text);
                    seen.add(text);
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
                            source_vars: extractVarsFromNode(initializer, sourceFile, ts)
                        });
                    }
                }
                // Handle destructuring: const {x, y} = obj
                else if (name.kind === ts.SyntaxKind.ObjectBindingPattern && name.elements) {
                    name.elements.forEach(elem => {
                        if (elem.name && elem.name.kind === ts.SyntaxKind.Identifier) {
                            const elemName = elem.name.text || elem.name.escapedText;
                            if (elemName) {
                                assignments.push({
                                    target_var: elemName,
                                    source_expr: initializer.getText(sourceFile).substring(0, 500),
                                    line: line + 1,
                                    in_function: inFunction,
                                    source_vars: extractVarsFromNode(initializer, sourceFile, ts)
                                });
                            }
                        }
                    });
                }
                // Handle array destructuring: const [x, y] = arr
                else if (name.kind === ts.SyntaxKind.ArrayBindingPattern && name.elements) {
                    name.elements.forEach(elem => {
                        if (elem.kind === ts.SyntaxKind.BindingElement && elem.name && elem.name.kind === ts.SyntaxKind.Identifier) {
                            const elemName = elem.name.text || elem.name.escapedText;
                            if (elemName) {
                                assignments.push({
                                    target_var: elemName,
                                    source_expr: initializer.getText(sourceFile).substring(0, 500),
                                    line: line + 1,
                                    in_function: inFunction,
                                    source_vars: extractVarsFromNode(initializer, sourceFile, ts)
                                });
                            }
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
                    source_vars: extractVarsFromNode(right, sourceFile, ts)
                });
            }
        }

        ts.forEachChild(node, child => traverse(child, depth + 1));
    }

    traverse(sourceFile);
    return assignments;
}
'''

EXTRACT_FUNCTION_CALL_ARGS = '''
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
        return '';
    }

    function traverse(node, depth = 0) {
        if (depth > 100 || !node) return;

        const nodeId = node.pos + '-' + node.kind;
        if (visited.has(nodeId)) return;
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
                            calleeFilePath = path.relative(projectRoot, calleeSource.fileName).replace(/\\\\/g, '/');
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

        ts.forEachChild(node, child => traverse(child, depth + 1));
    }

    traverse(sourceFile);
    return calls;
}
'''

EXTRACT_RETURNS = '''
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
            if (n.kind === ts.SyntaxKind.Identifier) {
                const text = n.text || n.escapedText;
                if (text && !seen.has(text)) {
                    vars.push(text);
                    seen.add(text);
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
'''

EXTRACT_OBJECT_LITERALS = '''
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

    function extractFromObjectNode(objNode, varName, inFunction, sourceFile, ts) {
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
                    nested_level: 0,
                    in_function: inFunction
                });
            } else if (kind === 'ShorthandPropertyAssignment') {
                const propName = prop.name ? (prop.name.text || prop.name.escapedText || '<unknown>') : '<unknown>';

                literals.push({
                    line: line + 1,
                    variable_name: varName,
                    property_name: propName,
                    property_value: propName,  // Shorthand: { x } means { x: x }
                    property_type: 'shorthand',
                    nested_level: 0,
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
                    nested_level: 0,
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
'''

EXTRACT_VARIABLE_USAGE = '''
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
'''

EXTRACT_IMPORT_STYLES = '''
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
'''

EXTRACT_REFS = '''
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
        const moduleName = modulePath.split('/').pop().replace(/\\.(js|ts|jsx|tsx)$/, '');

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
'''

COUNT_NODES = '''
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
'''

EXTRACT_REACT_COMPONENTS = '''
/**
 * Detect React function and class components.
 * Criteria: Uppercase name + returns JSX + uses hooks.
 * Implements Python's javascript.py:462-513 React component detection.
 *
 * @param {Array} functions - From extractFunctions()
 * @param {Array} classes - From extractClasses()
 * @param {Array} returns - From extractReturns()
 * @param {Array} functionCallArgs - From extractFunctionCallArgs()
 * @returns {Array} - React component records
 */
function extractReactComponents(functions, classes, returns, functionCallArgs) {
    const components = [];

    // Detect function components
    for (const func of functions) {
        const name = func.name || '';

        // Must be uppercase (React convention)
        if (!name || name[0] !== name[0].toUpperCase()) continue;

        // Check if returns JSX
        const funcReturns = returns.filter(r => r.function_name === name);
        const hasJsx = funcReturns.some(r => r.has_jsx || r.returns_component);

        // Find hooks used in this component
        const hooksUsed = [];
        for (const call of functionCallArgs) {
            if (call.caller_function === name && call.callee_function && call.callee_function.startsWith('use')) {
                hooksUsed.push(call.callee_function);
            }
        }

        components.push({
            name: name,
            type: 'function',
            start_line: func.line,
            end_line: func.end_line || func.line,
            has_jsx: hasJsx,
            hooks_used: [...new Set(hooksUsed)].slice(0, 10),
            props_type: null  // Could extract from type_annotation
        });
    }

    // Detect class components
    for (const cls of classes) {
        const name = cls.name || '';
        if (!name || name[0] !== name[0].toUpperCase()) continue;

        // Check if extends React.Component
        const extendsReact = cls.extends_type &&
            (cls.extends_type.includes('Component') || cls.extends_type.includes('React'));

        if (extendsReact) {
            components.push({
                name: name,
                type: 'class',
                start_line: cls.line,
                end_line: cls.line,  // Class end line not tracked
                has_jsx: true,
                hooks_used: [],
                props_type: null
            });
        }
    }

    return components;
}
'''

EXTRACT_REACT_HOOKS = '''
/**
 * Extract React hooks usage for dependency analysis.
 * Detects: useState, useEffect, useCallback, useMemo, custom hooks.
 * Implements Python's javascript.py:515-587 hooks extraction.
 *
 * @param {Array} functionCallArgs - From extractFunctionCallArgs()
 * @param {Map} scopeMap - Line → function mapping
 * @returns {Array} - Hook usage records
 */
function extractReactHooks(functionCallArgs, scopeMap) {
    const hooks = [];

    const REACT_HOOKS = new Set([
        'useState', 'useEffect', 'useCallback', 'useMemo', 'useRef',
        'useContext', 'useReducer', 'useLayoutEffect', 'useImperativeHandle',
        'useDebugValue', 'useDeferredValue', 'useTransition', 'useId'
    ]);

    for (const call of functionCallArgs) {
        const hookName = call.callee_function;
        if (!hookName || !hookName.startsWith('use')) continue;

        // Check if it's a known React hook or custom hook (starts with 'use')
        const isReactHook = REACT_HOOKS.has(hookName);
        const isCustomHook = !isReactHook && hookName.startsWith('use') && hookName.length > 3;

        if (isReactHook || isCustomHook) {
            hooks.push({
                line: call.line,
                hook_name: hookName,
                component_name: call.caller_function,
                is_custom: isCustomHook,
                argument_expr: call.argument_expr || '',
                argument_index: call.argument_index
            });
        }
    }

    return hooks;
}
'''

EXTRACT_ORM_QUERIES = '''
/**
 * Extract ORM query patterns (Sequelize, Prisma, TypeORM).
 * Detects: findAll, create, update, delete, etc.
 * Implements Python's javascript.py:643-703 ORM extraction.
 *
 * @param {Array} functionCallArgs - From extractFunctionCallArgs()
 * @returns {Array} - ORM query records
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
'''

EXTRACT_API_ENDPOINTS = '''
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
'''

# ============================================================================
# SINGLE FILE PROCESSING TEMPLATES - DELETED (Phase 5 obsolete)
# ============================================================================
# These templates were removed because they:
# 1. Serialize full AST (ast: ast) → 512MB JSON.stringify crash
# 2. Phase 5 batch templates fix this with ast: null
# 3. Single-file mode is incompatible with Phase 5 extraction-first architecture
#
# DELETED:
# - ES_MODULE_SINGLE (~205 lines)
# - COMMONJS_SINGLE (~187 lines)
#
# If single-file processing is needed, use batch mode with 1 file instead.

# ============================================================================
# BATCH PROCESSING TEMPLATES
# ============================================================================

ES_MODULE_BATCH = f'''// ES Module helper script for batch TypeScript AST extraction
import path from 'path';
import fs from 'fs';
import {{ fileURLToPath, pathToFileURL }} from 'url';

// ES modules don't have __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

function findNearestTsconfig(startPath, projectRoot, ts, path) {{
    let currentDir = path.resolve(path.dirname(startPath));
    const projectRootResolved = path.resolve(projectRoot);

    while (true) {{
        const candidate = path.join(currentDir, 'tsconfig.json');
        if (ts.sys.fileExists(candidate)) {{
            return candidate;
        }}
        if (currentDir === projectRootResolved || currentDir === path.dirname(currentDir)) {{
            break;
        }}
        currentDir = path.dirname(currentDir);
    }}

    return null;
}}

{IMPORT_EXTRACTION}

{EXTRACT_FUNCTIONS}

{EXTRACT_CLASSES}

{EXTRACT_CALLS}

{BUILD_SCOPE_MAP}

{EXTRACT_ASSIGNMENTS}

{EXTRACT_FUNCTION_CALL_ARGS}

{EXTRACT_RETURNS}

{EXTRACT_OBJECT_LITERALS}

{EXTRACT_VARIABLE_USAGE}

{EXTRACT_IMPORT_STYLES}

{EXTRACT_REFS}

{EXTRACT_REACT_COMPONENTS}

{EXTRACT_REACT_HOOKS}

{EXTRACT_ORM_QUERIES}

{EXTRACT_API_ENDPOINTS}

{COUNT_NODES}

async function main() {{
    try {{
        // Get request and output paths from command line
        const requestPath = process.argv[2];
        const outputPath = process.argv[3];

        if (!requestPath || !outputPath) {{
            console.error(JSON.stringify({{ error: "Request and output paths required" }}));
            process.exit(1);
        }}

        // Read batch request
        const request = JSON.parse(fs.readFileSync(requestPath, 'utf8'));
        const filePaths = request.files || [];
        const projectRoot = request.projectRoot;
        const jsxMode = request.jsxMode || 'transformed';  // Default to transformed for backward compatibility

        if (filePaths.length === 0) {{
            fs.writeFileSync(outputPath, JSON.stringify({{}}, 'utf8'));
            process.exit(0);
        }}

        if (!projectRoot) {{
            throw new Error("projectRoot not provided in batch request");
        }}

        // Load TypeScript
        const tsPath = path.join(projectRoot, '.auditor_venv', '.theauditor_tools', 'node_modules', 'typescript', 'lib', 'typescript.js');

        if (!fs.existsSync(tsPath)) {{
            throw new Error(`TypeScript not found at: ${{tsPath}}`);
        }}

        const tsModule = await import(pathToFileURL(tsPath));
        const ts = tsModule.default || tsModule;

        const configMap = request.configMap || {{}};
        const resolvedProjectRoot = path.resolve(projectRoot);

        const normalizedConfigMap = new Map();
        for (const [key, value] of Object.entries(configMap)) {{
            const resolvedKey = path.resolve(key);
            normalizedConfigMap.set(resolvedKey, value ? path.resolve(value) : null);
        }}

        const filesByConfig = new Map();
        const DEFAULT_KEY = '__DEFAULT__';

        for (const filePath of filePaths) {{
            const absoluteFilePath = path.resolve(filePath);
            const mappedConfig = normalizedConfigMap.get(absoluteFilePath);
            const nearestConfig = mappedConfig || findNearestTsconfig(absoluteFilePath, resolvedProjectRoot, ts, path);
            const groupKey = nearestConfig ? path.resolve(nearestConfig) : DEFAULT_KEY;

            if (!filesByConfig.has(groupKey)) {{
                filesByConfig.set(groupKey, []);
            }}
            filesByConfig.get(groupKey).push({{ original: filePath, absolute: absoluteFilePath }});
        }}

        const results = {{}};
        const jsxEmitMode = jsxMode === 'preserved' ? ts.JsxEmit.Preserve : ts.JsxEmit.React;

        for (const [configKey, groupedFiles] of filesByConfig.entries()) {{
            let compilerOptions;
            let program;

            if (configKey !== DEFAULT_KEY) {{
                const tsConfig = ts.readConfigFile(configKey, ts.sys.readFile);
                if (tsConfig.error) {{
                    throw new Error(`Failed to read tsconfig: ${{ts.flattenDiagnosticMessageText(tsConfig.error.messageText, '\\n')}}`);
                }}

                const configDir = path.dirname(configKey);
                const parsedConfig = ts.parseJsonConfigFileContent(
                    tsConfig.config,
                    ts.sys,
                    configDir,
                    {{}},
                    configKey
                );

                if (parsedConfig.errors && parsedConfig.errors.length > 0) {{
                    const errorMessages = parsedConfig.errors
                        .map(err => ts.flattenDiagnosticMessageText(err.messageText, '\\n'))
                        .join('; ');
                    throw new Error(`Failed to parse tsconfig: ${{errorMessages}}`);
                }}

        compilerOptions = Object.assign({{}}, parsedConfig.options);
        compilerOptions.jsx = jsxEmitMode;
        const hasJavaScriptFiles = groupedFiles.some(fileInfo => {{
            const ext = path.extname(fileInfo.absolute).toLowerCase();
            return ext === '.js' || ext === '.jsx' || ext === '.cjs' || ext === '.mjs';
        }});
        if (hasJavaScriptFiles) {{
            compilerOptions.allowJs = true;
            if (compilerOptions.checkJs === undefined) {{
                compilerOptions.checkJs = false;
            }}
        }}
        const projectReferences = parsedConfig.projectReferences || [];
        program = ts.createProgram(
            groupedFiles.map(f => f.absolute),
            compilerOptions,
            undefined,
                    undefined,
                    undefined,
                    projectReferences
                );
            }} else {{
                compilerOptions = {{
                    target: ts.ScriptTarget.Latest,
                    module: ts.ModuleKind.ESNext,
                    jsx: jsxEmitMode,
                    allowJs: true,
                    checkJs: false,
                    noEmit: true,
                    skipLibCheck: true,
                    moduleResolution: ts.ModuleResolutionKind.NodeJs,
                    baseUrl: resolvedProjectRoot,
                    rootDir: resolvedProjectRoot
                }};
                program = ts.createProgram(
                    groupedFiles.map(f => f.absolute),
                    compilerOptions
                );
            }}

            const checker = program.getTypeChecker();

            for (const fileInfo of groupedFiles) {{
                try {{
                    const sourceFile = program.getSourceFile(fileInfo.absolute);
                    if (!sourceFile) {{
                        results[fileInfo.original] = {{
                            success: false,
                            error: `Could not load source file: ${{fileInfo.original}}`,
                            ast: null,
                            diagnostics: [],
                            symbols: []
                        }};
                        continue;
                    }}

                    const sourceCode = sourceFile.text;

                    const diagnostics = [];
                    const fileDiagnostics = ts.getPreEmitDiagnostics(program, sourceFile);
                    fileDiagnostics.forEach(diagnostic => {{
                        const message = ts.flattenDiagnosticMessageText(diagnostic.messageText, '\\n');
                        const location = diagnostic.file && diagnostic.start
                            ? diagnostic.file.getLineAndCharacterOfPosition(diagnostic.start)
                            : null;

                        diagnostics.push({{
                            message,
                            category: ts.DiagnosticCategory[diagnostic.category],
                            code: diagnostic.code,
                            line: location ? location.line + 1 : null,
                            column: location ? location.character : null
                        }});
                    }});

                    const imports = extractImports(sourceFile, ts);

                    // PHASE 5: EXTRACTION-FIRST ARCHITECTURE (COMPLETE)
                    // Extract all data types directly in JavaScript using TypeScript checker
                    // This sends structured data instead of 512MB+ serialized AST

                    // Step 1: Build scope map (line → function name mapping)
                    const scopeMap = buildScopeMap(sourceFile, ts);

                    // Step 2: Extract functions and build parameter map
                    const functions = extractFunctions(sourceFile, checker, ts);
                    const functionParams = new Map();
                    functions.forEach(f => {{
                        if (f.name && f.parameters) {{
                            functionParams.set(f.name, f.parameters);
                        }}
                    }});

                    // Step 3: Extract all other data types
                    const calls = extractCalls(sourceFile, checker, ts, resolvedProjectRoot);
                    const classes = extractClasses(sourceFile, checker, ts);
                    const assignments = extractAssignments(sourceFile, ts, scopeMap);
                    const functionCallArgs = extractFunctionCallArgs(sourceFile, checker, ts, scopeMap, functionParams, resolvedProjectRoot);
                    const returns = extractReturns(sourceFile, ts, scopeMap);
                    const objectLiterals = extractObjectLiterals(sourceFile, ts, scopeMap);
                    const variableUsage = extractVariableUsage(assignments, functionCallArgs);
                    const importStyles = extractImportStyles(imports);
                    const refs = extractRefs(imports);
                    const reactComponents = extractReactComponents(functions, classes, returns, functionCallArgs);
                    const reactHooks = extractReactHooks(functionCallArgs, scopeMap);
                    const ormQueries = extractORMQueries(functionCallArgs);
                    const apiEndpoints = extractAPIEndpoints(functionCallArgs);

                    // Count nodes for complexity metrics (we have AST, just not serializing it)
                    const nodeCount = countNodes(sourceFile, ts);

                    results[fileInfo.original] = {{
                        success: true,
                        fileName: fileInfo.absolute,
                        languageVersion: ts.ScriptTarget[sourceFile.languageVersion],
                        ast: null,  // Set to null to prevent JSON.stringify crash
                        diagnostics: diagnostics,
                        imports: imports,
                        nodeCount: nodeCount,  // Real node count from AST traversal
                        hasTypes: true,
                        jsxMode: jsxMode,
                        extracted_data: {{
                            // PHASE 5: All data types extracted in JavaScript
                            functions: functions,
                            classes: classes,
                            calls: calls,
                            imports: imports,
                            assignments: assignments,
                            function_call_args: functionCallArgs,
                            returns: returns,
                            object_literals: objectLiterals,
                            variable_usage: variableUsage,
                            import_styles: importStyles,
                            resolved_imports: refs,
                            react_components: reactComponents,
                            react_hooks: reactHooks,
                            orm_queries: ormQueries,
                            api_endpoints: apiEndpoints,
                            scope_map: Object.fromEntries(scopeMap)  // Convert Map to object for JSON
                        }}
                    }};

                }} catch (error) {{
                    results[fileInfo.original] = {{
                        success: false,
                        error: `Error processing file: ${{error.message}}`,
                        ast: null,
                        diagnostics: [],
                        symbols: []
                    }};
                }}
            }}
        }}

        // Write all results
        fs.writeFileSync(outputPath, JSON.stringify(results, null, 2), 'utf8');
        process.exit(0);

    }} catch (error) {{
        console.error(JSON.stringify({{
            success: false,
            error: error.message,
            stack: error.stack
        }}));
        process.exit(1);
    }}
}}

// Run the async main function
main().catch(error => {{
    console.error(JSON.stringify({{
        success: false,
        error: `Unhandled error: ${{error.message}}`,
        stack: error.stack
    }}));
    process.exit(1);
}});
'''

COMMONJS_BATCH = f'''// CommonJS helper script for batch TypeScript AST extraction
const path = require('path');
const fs = require('fs');

function findNearestTsconfig(startPath, projectRoot, ts, path) {{
    let currentDir = path.resolve(path.dirname(startPath));
    const projectRootResolved = path.resolve(projectRoot);

    while (true) {{
        const candidate = path.join(currentDir, 'tsconfig.json');
        if (ts.sys.fileExists(candidate)) {{
            return candidate;
        }}
        if (currentDir === projectRootResolved || currentDir === path.dirname(currentDir)) {{
            break;
        }}
        currentDir = path.dirname(currentDir);
    }}

    return null;
}}

{IMPORT_EXTRACTION}

{EXTRACT_FUNCTIONS}

{EXTRACT_CLASSES}

{EXTRACT_CALLS}

{BUILD_SCOPE_MAP}

{EXTRACT_ASSIGNMENTS}

{EXTRACT_FUNCTION_CALL_ARGS}

{EXTRACT_RETURNS}

{EXTRACT_OBJECT_LITERALS}

{EXTRACT_VARIABLE_USAGE}

{EXTRACT_IMPORT_STYLES}

{EXTRACT_REFS}

{EXTRACT_REACT_COMPONENTS}

{EXTRACT_REACT_HOOKS}

{EXTRACT_ORM_QUERIES}

{EXTRACT_API_ENDPOINTS}

{COUNT_NODES}

// Get request and output paths from command line
const requestPath = process.argv[2];
const outputPath = process.argv[3];

if (!requestPath || !outputPath) {{
    console.error(JSON.stringify({{ error: "Request and output paths required" }}));
    process.exit(1);
}}

try {{
    // Read batch request
    const request = JSON.parse(fs.readFileSync(requestPath, 'utf8'));
    const filePaths = request.files || [];
    const projectRoot = request.projectRoot;
    const jsxMode = request.jsxMode || 'transformed';  // Default to transformed for backward compatibility

    if (filePaths.length === 0) {{
        fs.writeFileSync(outputPath, JSON.stringify({{}}, 'utf8'));
        process.exit(0);
    }}

    if (!projectRoot) {{
        throw new Error("projectRoot not provided in batch request");
    }}

    // Load TypeScript
    const tsPath = path.join(projectRoot, '.auditor_venv', '.theauditor_tools', 'node_modules', 'typescript', 'lib', 'typescript.js');

    if (!fs.existsSync(tsPath)) {{
        throw new Error(`TypeScript not found at: ${{tsPath}}`);
    }}

    const ts = require(tsPath);

    // Find tsconfig.json if available
    const configMap = request.configMap || {{}};
    const resolvedProjectRoot = path.resolve(projectRoot);

    const normalizedConfigMap = new Map();
    Object.entries(configMap).forEach(([key, value]) => {{
        const resolvedKey = path.resolve(key);
        normalizedConfigMap.set(resolvedKey, value ? path.resolve(value) : null);
    }});

    const filesByConfig = new Map();
    const DEFAULT_KEY = '__DEFAULT__';

    for (const filePath of filePaths) {{
        const absoluteFilePath = path.resolve(filePath);
        const mappedConfig = normalizedConfigMap.get(absoluteFilePath);
        const nearestConfig = mappedConfig || findNearestTsconfig(absoluteFilePath, resolvedProjectRoot, ts, path);
        const groupKey = nearestConfig ? path.resolve(nearestConfig) : DEFAULT_KEY;

        if (!filesByConfig.has(groupKey)) {{
            filesByConfig.set(groupKey, []);
        }}
        filesByConfig.get(groupKey).push({{ original: filePath, absolute: absoluteFilePath }});
    }}

    const results = {{}};
    const jsxEmitMode = jsxMode === 'preserved' ? ts.JsxEmit.Preserve : ts.JsxEmit.React;

    for (const [configKey, groupedFiles] of filesByConfig.entries()) {{
        let compilerOptions;
        let program;

        if (configKey !== DEFAULT_KEY) {{
            const tsConfig = ts.readConfigFile(configKey, ts.sys.readFile);
            if (tsConfig.error) {{
                throw new Error(`Failed to read tsconfig: ${{ts.flattenDiagnosticMessageText(tsConfig.error.messageText, '\n')}}`);
            }}

            const configDir = path.dirname(configKey);
            const parsedConfig = ts.parseJsonConfigFileContent(
                tsConfig.config,
                ts.sys,
                configDir,
                {{}},
                configKey
            );

            if (parsedConfig.errors && parsedConfig.errors.length > 0) {{
                const errorMessages = parsedConfig.errors
                    .map(err => ts.flattenDiagnosticMessageText(err.messageText, '\n'))
                    .join('; ');
                throw new Error(`Failed to parse tsconfig: ${{errorMessages}}`);
            }}

                compilerOptions = Object.assign({{}}, parsedConfig.options);
                compilerOptions.jsx = jsxEmitMode;
                const hasJavaScriptFiles = groupedFiles.some(fileInfo => {{
                    const ext = path.extname(fileInfo.absolute).toLowerCase();
                    return ext === '.js' || ext === '.jsx' || ext === '.cjs' || ext === '.mjs';
                }});
                if (hasJavaScriptFiles) {{
                    compilerOptions.allowJs = true;
                    if (compilerOptions.checkJs === undefined) {{
                        compilerOptions.checkJs = false;
                    }}
                }}
                const projectReferences = parsedConfig.projectReferences || [];
                program = ts.createProgram(
                    groupedFiles.map(f => f.absolute),
                    compilerOptions,
                    undefined,
                undefined,
                undefined,
                projectReferences
            );
        }} else {{
            compilerOptions = {{
                target: ts.ScriptTarget.Latest,
                module: ts.ModuleKind.ESNext,
                jsx: jsxEmitMode,
                allowJs: true,
                checkJs: false,
                noEmit: true,
                skipLibCheck: true,
                moduleResolution: ts.ModuleResolutionKind.NodeJs,
                baseUrl: resolvedProjectRoot,
                rootDir: resolvedProjectRoot
            }};
            program = ts.createProgram(
                groupedFiles.map(f => f.absolute),
                compilerOptions
            );
        }}

        const checker = program.getTypeChecker();

        for (const fileInfo of groupedFiles) {{
            try {{
                const sourceFile = program.getSourceFile(fileInfo.absolute);
                if (!sourceFile) {{
                    results[fileInfo.original] = {{
                        success: false,
                        error: `Could not load source file: ${{fileInfo.original}}`,
                        ast: null,
                        diagnostics: [],
                        symbols: []
                    }};
                    continue;
                }}

                const sourceCode = sourceFile.text;

                const diagnostics = [];
                const fileDiagnostics = ts.getPreEmitDiagnostics(program, sourceFile);
                fileDiagnostics.forEach(diagnostic => {{
                    const message = ts.flattenDiagnosticMessageText(diagnostic.messageText, '\n');
                    const location = diagnostic.file && diagnostic.start
                        ? diagnostic.file.getLineAndCharacterOfPosition(diagnostic.start)
                        : null;

                    diagnostics.push({{
                        message,
                        category: ts.DiagnosticCategory[diagnostic.category],
                        code: diagnostic.code,
                        line: location ? location.line + 1 : null,
                        column: location ? location.character : null
                    }});
                }});

                const imports = extractImports(sourceFile, ts);

                // PHASE 5: EXTRACTION-FIRST ARCHITECTURE (COMPLETE)
                // Extract all data types directly in JavaScript using TypeScript checker
                // This sends structured data instead of 512MB+ serialized AST

                // Step 1: Build scope map (line → function name mapping)
                const scopeMap = buildScopeMap(sourceFile, ts);

                // Step 2: Extract functions and build parameter map
                const functions = extractFunctions(sourceFile, checker, ts);
                const functionParams = new Map();
                functions.forEach(f => {{
                    if (f.name && f.parameters) {{
                        functionParams.set(f.name, f.parameters);
                    }}
                }});

                // Step 3: Extract all other data types
                const calls = extractCalls(sourceFile, checker, ts, resolvedProjectRoot);
                const classes = extractClasses(sourceFile, checker, ts);
                const assignments = extractAssignments(sourceFile, ts, scopeMap);
                const functionCallArgs = extractFunctionCallArgs(sourceFile, checker, ts, scopeMap, functionParams, resolvedProjectRoot);
                const returns = extractReturns(sourceFile, ts, scopeMap);
                const objectLiterals = extractObjectLiterals(sourceFile, ts, scopeMap);
                const variableUsage = extractVariableUsage(assignments, functionCallArgs);
                const importStyles = extractImportStyles(imports);
                const refs = extractRefs(imports);
                const reactComponents = extractReactComponents(functions, classes, returns, functionCallArgs);
                const reactHooks = extractReactHooks(functionCallArgs, scopeMap);
                const ormQueries = extractORMQueries(functionCallArgs);
                const apiEndpoints = extractAPIEndpoints(functionCallArgs);

                // Count nodes for complexity metrics (we have AST, just not serializing it)
                const nodeCount = countNodes(sourceFile, ts);

                results[fileInfo.original] = {{
                    success: true,
                    fileName: fileInfo.absolute,
                    languageVersion: ts.ScriptTarget[sourceFile.languageVersion],
                    ast: null,  // Set to null to prevent JSON.stringify crash
                    diagnostics: diagnostics,
                    imports: imports,
                    nodeCount: nodeCount,  // Real node count from AST traversal
                    hasTypes: true,
                    jsxMode: jsxMode,
                    extracted_data: {{
                        // PHASE 5: All data types extracted in JavaScript
                        functions: functions,
                        classes: classes,
                        calls: calls,
                        imports: imports,
                        assignments: assignments,
                        function_call_args: functionCallArgs,
                        returns: returns,
                        object_literals: objectLiterals,
                        variable_usage: variableUsage,
                        import_styles: importStyles,
                        resolved_imports: refs,
                        react_components: reactComponents,
                        react_hooks: reactHooks,
                        orm_queries: ormQueries,
                        api_endpoints: apiEndpoints,
                        scope_map: Object.fromEntries(scopeMap)  // Convert Map to object for JSON
                    }}
                }};

            }} catch (error) {{
                results[fileInfo.original] = {{
                    success: false,
                    error: `Error processing file: ${{error.message}}`,
                    ast: null,
                    diagnostics: [],
                    symbols: []
                }};
            }}
        }}
    }}
    // Write all results
    fs.writeFileSync(outputPath, JSON.stringify(results, null, 2), 'utf8');
    process.exit(0);

}} catch (error) {{
    console.error(JSON.stringify({{
        success: false,
        error: error.message,
        stack: error.stack
    }}));
    process.exit(1);
}}
'''

# ============================================================================
# PUBLIC API
# ============================================================================

def get_single_file_helper(module_type: Literal["module", "commonjs"]) -> str:
    """Get the appropriate single-file helper script.

    DEPRECATED: Single-file mode is obsolete in Phase 5. Use get_batch_helper() with 1 file instead.

    Args:
        module_type: Either "module" for ES modules or "commonjs" for CommonJS

    Returns:
        Complete JavaScript helper script as a string

    Raises:
        RuntimeError: Always raises - single-file mode removed in Phase 5
    """
    raise RuntimeError(
        "Single-file mode removed in Phase 5. "
        "Single-file templates serialize full AST (512MB crash). "
        "Use get_batch_helper() with 1 file instead (sets ast: null)."
    )


def get_batch_helper(module_type: Literal["module", "commonjs"]) -> str:
    """Get the appropriate batch processing helper script.

    Args:
        module_type: Either "module" for ES modules or "commonjs" for CommonJS

    Returns:
        Complete JavaScript batch helper script as a string
    """
    if module_type == "module":
        return ES_MODULE_BATCH
    return COMMONJS_BATCH


__all__ = [
    'get_single_file_helper',
    'get_batch_helper',
]
