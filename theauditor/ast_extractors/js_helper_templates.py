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

ANONYMOUS_FUNCTION_NAMING_HEURISTICS = '''
/**
 * Apply naming heuristics to anonymous functions based on context.
 * This is critical for taint analysis to track function flows.
 *
 * @param {Node} node - The function node to name
 * @param {Node} parentNode - The parent AST node
 * @param {Node} grandparentNode - The grandparent AST node
 * @param {Object} sourceFile - TypeScript source file for line info
 * @param {string} sourceCode - Raw source code text
 * @param {Object} ts - TypeScript compiler API
 * @returns {string|null} - Inferred name or null
 */
function applyNamingHeuristics(node, parentNode, grandparentNode, sourceFile, sourceCode, ts) {
    if (!parentNode) return null;

    const parentKind = ts.SyntaxKind[parentNode.kind] || parentNode.kind;

    // ========== JSX PATTERNS (Highest Priority) ==========

    // Direct JSX attribute: onClick={handler}
    if (parentKind === 'JsxAttribute') {
        const attrName = parentNode.name?.escapedText || parentNode.name?.text;
        if (attrName) return attrName + '_handler';
    }

    // JSX expression container: onClick={() => {}}
    if (parentKind === 'JsxExpression') {
        // Traverse up to find the JsxAttribute
        let current = parentNode;
        let depth = 0;
        while (current && depth < 5) {
            if (current.parent && ts.SyntaxKind[current.parent.kind] === 'JsxAttribute') {
                const attrName = current.parent.name?.escapedText || current.parent.name?.text;
                if (attrName) return attrName + '_handler';
            }
            current = current.parent;
            depth++;
        }
        // If in JSX but not an attribute, might be render prop
        if (grandparentNode && ts.SyntaxKind[grandparentNode.kind] === 'JsxElement') {
            return 'jsx_render_function';
        }
    }

    // ========== CLASS/OBJECT PATTERNS ==========

    // Class property: handleSubmit = () => {}
    if (parentKind === 'PropertyDeclaration') {
        const propName = parentNode.name?.escapedText || parentNode.name?.text;
        if (propName) return propName;
    }

    // Object property: { handleRequest: function() {} }
    if (parentKind === 'PropertyAssignment') {
        const propName = parentNode.name?.escapedText || parentNode.name?.text;
        if (propName) return propName;
    }

    // ========== VARIABLE PATTERNS ==========

    // Variable declaration: const validateInput = () => {}
    if (parentKind === 'VariableDeclaration') {
        const varName = parentNode.name?.escapedText || parentNode.name?.text;
        if (varName) return varName;
    }

    // Binary expression assignment: x = () => {}
    if (parentKind === 'BinaryExpression' && parentNode.operatorToken) {
        if (parentNode.operatorToken.kind === ts.SyntaxKind.EqualsToken && parentNode.left) {
            const leftText = sourceCode.substring(parentNode.left.pos, parentNode.left.end).trim();
            if (leftText) return leftText;
        }
    }

    // ========== CALLBACK PATTERNS ==========

    // Method call argument: promise.then(() => {})
    if (parentKind === 'CallExpression' && parentNode.expression) {
        let methodName = null;

        // Handle PropertyAccessExpression (e.g., promise.then)
        if (parentNode.expression.kind === ts.SyntaxKind.PropertyAccessExpression) {
            methodName = parentNode.expression.name?.escapedText || parentNode.expression.name?.text;
        }
        // Handle simple Identifier (e.g., map, filter)
        else if (parentNode.expression.kind === ts.SyntaxKind.Identifier) {
            methodName = parentNode.expression.escapedText || parentNode.expression.text;
        }

        if (methodName) {
            // Find argument position
            const args = parentNode.arguments || [];
            let argIndex = 0;
            for (let i = 0; i < args.length; i++) {
                if (args[i] === node) {
                    argIndex = i;
                    break;
                }
            }

            // Special naming for common patterns
            if (methodName === 'then' || methodName === 'catch' || methodName === 'finally') {
                return methodName + '_callback';
            }
            if (methodName === 'map' || methodName === 'filter' || methodName === 'forEach' || methodName === 'reduce') {
                return methodName + '_callback';
            }
            if (methodName === 'addEventListener' || methodName === 'on') {
                // Try to get event name from first argument
                if (args.length > 0 && args[0].kind === ts.SyntaxKind.StringLiteral) {
                    return args[0].text + '_handler';
                }
                return 'event_handler';
            }
            if (methodName.startsWith('use')) {
                // React hooks
                return methodName.replace('use', '').toLowerCase() + '_callback';
            }

            return methodName + '_arg' + argIndex;
        }
    }

    // ========== SPECIAL PATTERNS ==========

    // Array element: [function() {}]
    if (parentKind === 'ArrayLiteralExpression') {
        const elements = parentNode.elements || [];
        for (let i = 0; i < elements.length; i++) {
            if (elements[i] === node) {
                return 'array_function_' + i;
            }
        }
    }

    // Return statement: return () => {}
    if (parentKind === 'ReturnStatement' && grandparentNode) {
        const grandKind = ts.SyntaxKind[grandparentNode.kind];
        if (grandKind && grandKind.includes('Function')) {
            const containerName = grandparentNode.name?.escapedText || grandparentNode.name?.text || 'unknown';
            return containerName + '_returned_function';
        }
    }

    // IIFE: (function() {})()
    if (parentKind === 'ParenthesizedExpression' && grandparentNode) {
        if (ts.SyntaxKind[grandparentNode.kind] === 'CallExpression') {
            return 'IIFE';
        }
    }

    // Export default: export default () => {}
    if (parentKind === 'ExportAssignment') {
        return 'default_export';
    }

    // ========== DEEP TRAVERSAL FOR COMPLEX PATTERNS ==========

    let current = node;
    let depth = 0;
    const visited = new Set();

    while (current && depth < 5 && !visited.has(current)) {
        visited.add(current);

        if (current.parent) {
            const currentParentKind = ts.SyntaxKind[current.parent.kind] || current.parent.kind;

            // Higher-Order Component patterns
            if (currentParentKind === 'CallExpression') {
                const expr = current.parent.expression;
                if (expr) {
                    const funcName = expr.text || expr.name?.text || expr.escapedText;

                    // React HOCs
                    if (funcName === 'connect') return 'redux_connector';
                    if (funcName === 'memo') return 'memoized_component';
                    if (funcName === 'forwardRef') return 'forwarded_ref_component';
                    if (funcName === 'withRouter') return 'with_router_hoc';

                    // React.lazy
                    const exprText = sourceCode.substring(expr.pos, expr.end).trim();
                    if (exprText.includes('React.lazy')) return 'lazy_component_loader';
                }
            }

            // Module.exports patterns
            if (currentParentKind === 'BinaryExpression' && current.parent.left) {
                const leftText = sourceCode.substring(current.parent.left.pos, current.parent.left.end).trim();
                if (leftText.includes('module.exports')) return 'module_export';
                if (leftText.includes('exports.')) {
                    const exportName = leftText.split('exports.')[1];
                    if (exportName) return exportName.split(/[^a-zA-Z0-9_]/)[0];
                }
            }
        }

        current = current.parent;
        depth++;
    }

    // Last resort - line-based naming
    const { line } = sourceFile.getLineAndCharacterOfPosition(node.pos);
    return 'anonymous_line_' + (line + 1);
}
'''

NODE_SERIALIZATION = '''
/**
 * Serialize TypeScript AST node to JSON-serializable format.
 * Includes semantic information like types and symbols.
 *
 * @param {Node} node - TypeScript AST node
 * @param {number} depth - Current recursion depth
 * @param {Node} parentNode - Parent AST node
 * @param {Node} grandparentNode - Grandparent AST node
 * @param {Object} sourceFile - TypeScript source file
 * @param {string} sourceCode - Raw source code text
 * @param {Object} ts - TypeScript compiler API
 * @returns {Object} - Serialized node representation
 */
function serializeNode(node, depth = 0, parentNode = null, grandparentNode = null, sourceFile, sourceCode, ts, checker = null, projectRoot = '') {
    if (depth > 100) {
        return { kind: "TooDeep" };
    }

    const result = {
        kind: node.kind !== undefined ? (ts.SyntaxKind[node.kind] || node.kind) : 'Unknown',
        kindValue: node.kind || 0,
        pos: node.pos || 0,
        end: node.end || 0,
        flags: node.flags || 0
    };

    // Add text content for leaf nodes
    if (node.text !== undefined) {
        result.text = node.text;
    }

    // Extract node name
    if (node.name) {
        if (typeof node.name === 'object') {
            if (node.name.escapedText !== undefined) {
                result.name = node.name.escapedText;
            } else if (node.name.text !== undefined) {
                result.name = node.name.text;
            } else {
                result.name = serializeNode(node.name, depth + 1, node, parentNode, sourceFile, sourceCode, ts, checker, projectRoot);
            }
        } else {
            result.name = node.name;
        }
    }

    // Enhanced function name extraction
    const nodeKind = result.kind;
    if (!result.name || result.name === 'anonymous' || typeof result.name === 'object') {
        // Handle different function types
        if (nodeKind === 'FunctionDeclaration' || nodeKind === 'MethodDeclaration') {
            if (node.name?.escapedText) {
                result.name = node.name.escapedText;
            } else if (node.name?.text) {
                result.name = node.name.text;
            }
        } else if (nodeKind === 'FunctionExpression') {
            if (node.name?.escapedText) {
                result.name = node.name.escapedText;
            } else if (node.name?.text) {
                result.name = node.name.text;
            } else {
                result.name = applyNamingHeuristics(node, parentNode, grandparentNode, sourceFile, sourceCode, ts) || 'anonymous';
            }
        } else if (nodeKind === 'ArrowFunction') {
            // Arrow functions never have direct names - apply heuristics
            result.name = applyNamingHeuristics(node, parentNode, grandparentNode, sourceFile, sourceCode, ts) || 'anonymous';
        } else if (nodeKind === 'Constructor') {
            result.name = 'constructor';
        } else if (nodeKind === 'GetAccessor') {
            const accessorName = node.name?.escapedText || node.name?.text;
            if (accessorName) result.name = 'get ' + accessorName;
        } else if (nodeKind === 'SetAccessor') {
            const accessorName = node.name?.escapedText || node.name?.text;
            if (accessorName) result.name = 'set ' + accessorName;
        }
    }

    // Store variable name for arrow function assignments (helps taint analysis)
    if (nodeKind === 'VariableDeclaration') {
        const varName = node.name?.escapedText || node.name?.text;
        if (varName && node.initializer) {
            const initKind = node.initializer.kind;
            if (initKind === ts.SyntaxKind.ArrowFunction || initKind === ts.SyntaxKind.FunctionExpression) {
                result.variableName = varName;
            }
        }
    }

    // Add type information
    if (node.type) {
        result.type = serializeNode(node.type, depth + 1, node, parentNode, sourceFile, sourceCode, ts, checker, projectRoot);
    }

    // CRITICAL FIX: Extract initializer field for VariableDeclaration and PropertyDeclaration
    // This enables direct access to arrow function initializers without searching children array
    if (node.initializer) {
        result.initializer = serializeNode(node.initializer, depth + 1, node, parentNode, sourceFile, sourceCode, ts, checker, projectRoot);
    }

    // CRITICAL FIX: Extract parameters field for function signatures
    // Without this, parameter extraction falls back to broken heuristics (ZERO FALLBACK POLICY)
    if (node.parameters && Array.isArray(node.parameters)) {
        result.parameters = node.parameters.map(param =>
            serializeNode(param, depth + 1, node, parentNode, sourceFile, sourceCode, ts, checker, projectRoot)
        );
    }

    // CRITICAL FIX: Extract expression field for PropertyAccessExpression
    // This enables taint analysis to build dotted names (req.body, res.send, etc.)
    // Without this, only leaf identifiers are captured (body, send)
    if (nodeKind === 'PropertyAccessExpression' && node.expression) {
        result.expression = serializeNode(node.expression, depth + 1, node, parentNode, sourceFile, sourceCode, ts, checker, projectRoot);
    }

    // CRITICAL: Resolve callee file path for CallExpression nodes
    // This enables unambiguous cross-file taint tracking
    if (nodeKind === 'CallExpression' && node.expression && checker) {
        try {
            const symbol = checker.getSymbolAtLocation(node.expression);
            if (symbol && symbol.declarations && symbol.declarations.length > 0) {
                const declaration = symbol.declarations[0];
                const calleeSourceFile = declaration.getSourceFile();
                if (calleeSourceFile && projectRoot) {
                    // Normalize path to be relative to project root (path module already imported at top level)
                    result.calleeFilePath = path.relative(projectRoot, calleeSourceFile.fileName).replace(/\\\\/g, '/');
                }
            }
        } catch (e) {
            // If resolution fails, field will be absent
        }
    }

    // Process children
    const children = [];

    // Handle nodes with members (interfaces, classes, etc.)
    if (node.members && Array.isArray(node.members)) {
        node.members.forEach(member => {
            if (member) children.push(serializeNode(member, depth + 1, node, parentNode, sourceFile, sourceCode, ts, checker, projectRoot));
        });
    }

    // Handle regular children
    ts.forEachChild(node, child => {
        if (child) children.push(serializeNode(child, depth + 1, node, parentNode, sourceFile, sourceCode, ts, checker, projectRoot));
    });

    if (children.length > 0) {
        result.children = children;
    }

    // Get accurate line and column information
    const actualStart = node.getStart ? node.getStart(sourceFile) : node.pos;
    const { line, character } = sourceFile.getLineAndCharacterOfPosition(actualStart);
    result.line = line + 1;  // Convert to 1-indexed
    result.column = character;

    // Add end line for CFG boundaries
    if (node.end !== undefined) {
        const endPosition = sourceFile.getLineAndCharacterOfPosition(node.end);
        result.endLine = endPosition.line + 1;  // Convert to 1-indexed
    }

    // Extract text for taint analysis (critical for symbol tracking)
    result.text = sourceCode.substring(node.pos, node.end).trim();

    // PHASE 1: Add inline type extraction from TypeScript checker
    // This eliminates the need for separate extractSymbols() pass
    if (checker) {
        try {
            // Get symbol at this location for type information
            const symbol = checker.getSymbolAtLocation(node);
            if (symbol) {
                // Get the TypeScript type for this symbol
                const type = checker.getTypeOfSymbolAtLocation(symbol, node);

                if (type) {
                    // Get type string representation
                    result.type_annotation = checker.typeToString(type);

                    // Check for 'any' type
                    if (type.flags & ts.TypeFlags.Any) {
                        result.is_any = true;
                    }

                    // Check for 'unknown' type
                    if (type.flags & ts.TypeFlags.Unknown) {
                        result.is_unknown = true;
                    }

                    // Check if this is a generic type parameter
                    if (type.isTypeParameter && type.isTypeParameter()) {
                        result.is_generic = true;
                    }

                    // Check for type parameters (generic instantiation)
                    if (type.aliasTypeArguments && type.aliasTypeArguments.length > 0) {
                        result.has_type_params = true;
                        result.type_params = type.aliasTypeArguments
                            .map(t => checker.typeToString(t))
                            .join(', ');
                    }

                    // For function types, extract return type
                    const callSignatures = type.getCallSignatures();
                    if (callSignatures && callSignatures.length > 0) {
                        const returnType = callSignatures[0].getReturnType();
                        result.return_type = checker.typeToString(returnType);
                    }

                    // For class types, extract base class
                    const baseTypes = type.getBaseTypes ? type.getBaseTypes() : null;
                    if (baseTypes && baseTypes.length > 0) {
                        result.extends_type = baseTypes
                            .map(t => checker.typeToString(t))
                            .join(', ');
                    }
                }
            }
        } catch (typeError) {
            // Type extraction failed - continue without type info
            // This is expected for many node types that don't have symbols
        }
    }

    return result;
}
'''

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

COUNT_NODES = '''
/**
 * Count total nodes in AST for metrics.
 *
 * @param {Object} node - Serialized AST node
 * @returns {number} - Total node count
 */
function countNodes(node) {
    if (!node) return 0;
    let count = 1;
    if (node.children && Array.isArray(node.children)) {
        node.children.forEach(child => {
            count += countNodes(child);
        });
    }
    return count;
}
'''

# ============================================================================
# SINGLE FILE PROCESSING TEMPLATES
# ============================================================================

ES_MODULE_SINGLE = f'''// ES Module helper script for single-file TypeScript AST extraction
import path from 'path';
import fs from 'fs';
import {{ fileURLToPath, pathToFileURL }} from 'url';

// ES modules don't have __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

{ANONYMOUS_FUNCTION_NAMING_HEURISTICS}

{NODE_SERIALIZATION}

{IMPORT_EXTRACTION}

{COUNT_NODES}

async function main() {{
    try {{
        // Get file path, output path, project root, and jsx mode from command line
        const filePath = process.argv[2];
        const outputPath = process.argv[3];
        const projectRoot = process.argv[4] || path.resolve(__dirname, '..');  // Use provided projectRoot or fallback
        const jsxMode = process.argv[5] || 'transformed';  // Default to transformed for backward compatibility

        if (!filePath || !outputPath || !projectRoot) {{
            console.error(JSON.stringify({{ error: "File path, output path, and project root required" }}));
            process.exit(1);
        }}

        // Validate jsx_mode
        if (jsxMode !== 'preserved' && jsxMode !== 'transformed') {{
            console.error(JSON.stringify({{ error: `Invalid jsx_mode: ${{jsxMode}}. Must be 'preserved' or 'transformed'` }}));
            process.exit(1);
        }}

        // Load TypeScript dynamically
        const tsPath = path.join(projectRoot, '.auditor_venv', '.theauditor_tools', 'node_modules', 'typescript', 'lib', 'typescript.js');

        if (!fs.existsSync(tsPath)) {{
            throw new Error(`TypeScript not found at: ${{tsPath}}. Run 'aud setup-claude' to install.`);
        }}

        // Dynamic import for ES module
        const tsModule = await import(pathToFileURL(tsPath));
        const ts = tsModule.default || tsModule;

        // Read source file
        const sourceCode = fs.readFileSync(filePath, 'utf8');

        // Create TypeScript source file
        const sourceFile = ts.createSourceFile(
            filePath,
            sourceCode,
            ts.ScriptTarget.Latest,
            true,  // setParentNodes - important for traversal
            ts.ScriptKind.TSX  // Support JSX
        );

        // Create program for type checking
        // CRITICAL: JSX mode determines how JSX is handled
        // 'preserved' -> ts.JsxEmit.Preserve (keeps JSX syntax)
        // 'transformed' -> ts.JsxEmit.React (converts to React.createElement)
        const jsxEmitMode = jsxMode === 'preserved' ? ts.JsxEmit.Preserve : ts.JsxEmit.React;

        const program = ts.createProgram([filePath], {{
            target: ts.ScriptTarget.Latest,
            module: ts.ModuleKind.ESNext,
            jsx: jsxEmitMode,
            allowJs: true,
            checkJs: false,
            noEmit: true,
            skipLibCheck: true
        }});

        // Get diagnostics
        const diagnostics = [];
        const allDiagnostics = ts.getPreEmitDiagnostics(program);
        allDiagnostics.forEach(diagnostic => {{
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

        // Extract imports
        const imports = extractImports(sourceFile, ts);

        // PHASE 4: Get type checker for inline type extraction in serializeNode
        const checker = program.getTypeChecker();

        // Serialize AST with checker for inline type extraction and call resolution
        const ast = serializeNode(sourceFile, 0, null, null, sourceFile, sourceCode, ts, checker, projectRoot);

        // Build result
        const result = {{
            success: true,
            fileName: filePath,
            languageVersion: ts.ScriptTarget[sourceFile.languageVersion],
            ast: ast,
            diagnostics: diagnostics,
            imports: imports,  // CRITICAL: Import tracking for dependency analysis
            nodeCount: countNodes(ast),
            hasTypes: true,  // PHASE 4: Always true now - type info extracted inline in AST nodes
            jsxMode: jsxMode  // Include JSX mode in result
        }};

        // Write output
        fs.writeFileSync(outputPath, JSON.stringify(result, null, 2), 'utf8');
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

COMMONJS_SINGLE = f'''// CommonJS helper script for single-file TypeScript AST extraction
const path = require('path');
const fs = require('fs');

{ANONYMOUS_FUNCTION_NAMING_HEURISTICS}

{NODE_SERIALIZATION}

{IMPORT_EXTRACTION}

{COUNT_NODES}

// Get file path, output path, project root, and jsx mode from command line
const filePath = process.argv[2];
const outputPath = process.argv[3];
const projectRoot = process.argv[4] || path.resolve(__dirname, '..');  // Use provided projectRoot or fallback
const jsxMode = process.argv[5] || 'transformed';  // Default to transformed for backward compatibility

if (!filePath || !outputPath || !projectRoot) {{
    console.error(JSON.stringify({{ error: "File path, output path, and project root required" }}));
    process.exit(1);
}}

// Validate jsx_mode
if (jsxMode !== 'preserved' && jsxMode !== 'transformed') {{
    console.error(JSON.stringify({{ error: `Invalid jsx_mode: ${{jsxMode}}. Must be 'preserved' or 'transformed'` }}));
    process.exit(1);
}}

try {{
    // Load TypeScript
    const tsPath = path.join(projectRoot, '.auditor_venv', '.theauditor_tools', 'node_modules', 'typescript', 'lib', 'typescript.js');

    if (!fs.existsSync(tsPath)) {{
        throw new Error(`TypeScript not found at: ${{tsPath}}. Run 'aud setup-claude' to install.`);
    }}

    const ts = require(tsPath);

    // Read source file
    const sourceCode = fs.readFileSync(filePath, 'utf8');

    // Create TypeScript source file
    const sourceFile = ts.createSourceFile(
        filePath,
        sourceCode,
        ts.ScriptTarget.Latest,
        true,  // setParentNodes - important for traversal
        ts.ScriptKind.TSX  // Support JSX
    );

    // Create program for type checking
    // CRITICAL: JSX mode determines how JSX is handled
    // 'preserved' -> ts.JsxEmit.Preserve (keeps JSX syntax)
    // 'transformed' -> ts.JsxEmit.React (converts to React.createElement)
    const jsxEmitMode = jsxMode === 'preserved' ? ts.JsxEmit.Preserve : ts.JsxEmit.React;

    const program = ts.createProgram([filePath], {{
        target: ts.ScriptTarget.Latest,
        module: ts.ModuleKind.ESNext,
        jsx: jsxEmitMode,
        allowJs: true,
        checkJs: false,
        noEmit: true,
        skipLibCheck: true
    }});

    // Get diagnostics
    const diagnostics = [];
    const allDiagnostics = ts.getPreEmitDiagnostics(program);
    allDiagnostics.forEach(diagnostic => {{
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

    // Extract imports
    const imports = extractImports(sourceFile, ts);

    // PHASE 4: Get type checker for inline type extraction in serializeNode
    const checker = program.getTypeChecker();

    // Serialize AST with checker for inline type extraction and call resolution
    const ast = serializeNode(sourceFile, 0, null, null, sourceFile, sourceCode, ts, checker, projectRoot);

    // Build result
    const result = {{
        success: true,
        fileName: filePath,
        languageVersion: ts.ScriptTarget[sourceFile.languageVersion],
        ast: ast,
        diagnostics: diagnostics,
        imports: imports,  // CRITICAL: Import tracking for dependency analysis
        nodeCount: countNodes(ast),
        hasTypes: true,  // PHASE 4: Always true now - type info extracted inline in AST nodes
        jsxMode: jsxMode  // Include JSX mode in result
    }};

    // Write output
    fs.writeFileSync(outputPath, JSON.stringify(result, null, 2), 'utf8');
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
# BATCH PROCESSING TEMPLATES
# ============================================================================

ES_MODULE_BATCH = f'''// ES Module helper script for batch TypeScript AST extraction
import path from 'path';
import fs from 'fs';
import {{ fileURLToPath, pathToFileURL }} from 'url';

// ES modules don't have __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

{ANONYMOUS_FUNCTION_NAMING_HEURISTICS}

{NODE_SERIALIZATION}

{IMPORT_EXTRACTION}

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

        // Find tsconfig.json if available
        const tsConfigPath = ts.findConfigFile(projectRoot, ts.sys.fileExists, "tsconfig.json");

        let program;
        if (tsConfigPath) {{
            // Use project's tsconfig
            const tsConfig = ts.readConfigFile(tsConfigPath, ts.sys.readFile);
            const parsedConfig = ts.parseJsonConfigFileContent(
                tsConfig.config,
                ts.sys,
                path.dirname(tsConfigPath),
                {{}},
                tsConfigPath
            );

            // Create program with all files at once for shared type checking
            program = ts.createProgram(filePaths, parsedConfig.options);
        }} else {{
            // Use default options
            console.error("[WARN] No tsconfig.json found, using default options");
            program = ts.createProgram(filePaths, {{
                target: ts.ScriptTarget.Latest,
                module: ts.ModuleKind.ESNext,
                jsx: jsxMode === 'preserved' ? ts.JsxEmit.Preserve : ts.JsxEmit.React,
                allowJs: true,
                checkJs: false,
                noEmit: true,
                skipLibCheck: true,
                moduleResolution: ts.ModuleResolutionKind.NodeJs,
                baseUrl: projectRoot,
                rootDir: projectRoot
            }});
        }}

        const checker = program.getTypeChecker();
        const results = {{}};

        // Process each file using the shared program
        for (const filePath of filePaths) {{
            try {{
                const sourceFile = program.getSourceFile(filePath);
                if (!sourceFile) {{
                    results[filePath] = {{
                        success: false,
                        error: `Could not load source file: ${{filePath}}`
                    }};
                    continue;
                }}

                const sourceCode = sourceFile.text;

                // Get file-specific diagnostics
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

                // Extract imports
                const imports = extractImports(sourceFile, ts);

                // PHASE 4: Get type checker for inline type extraction in serializeNode
                // Serialize AST with checker for inline type extraction and call resolution
                const ast = serializeNode(sourceFile, 0, null, null, sourceFile, sourceCode, ts, checker, projectRoot);

                // Build result for this file
                results[filePath] = {{
                    success: true,
                    fileName: filePath,
                    languageVersion: ts.ScriptTarget[sourceFile.languageVersion],
                    ast: ast,
                    diagnostics: diagnostics,
                    imports: imports,  // CRITICAL: Import tracking for dependency analysis
                    nodeCount: countNodes(ast),
                    hasTypes: true,  // PHASE 4: Always true now - type info extracted inline in AST nodes
                    jsxMode: jsxMode  // Include JSX mode in result
                }};

            }} catch (error) {{
                results[filePath] = {{
                    success: false,
                    error: `Error processing file: ${{error.message}}`,
                    ast: null,
                    diagnostics: []
                }};
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

{ANONYMOUS_FUNCTION_NAMING_HEURISTICS}

{NODE_SERIALIZATION}

{IMPORT_EXTRACTION}

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
    const tsConfigPath = ts.findConfigFile(projectRoot, ts.sys.fileExists, "tsconfig.json");

    let program;
    if (tsConfigPath) {{
        // Use project's tsconfig
        const tsConfig = ts.readConfigFile(tsConfigPath, ts.sys.readFile);
        const parsedConfig = ts.parseJsonConfigFileContent(
            tsConfig.config,
            ts.sys,
            path.dirname(tsConfigPath),
            {{}},
            tsConfigPath
        );

        // Create program with all files at once for shared type checking
        program = ts.createProgram(filePaths, parsedConfig.options);
    }} else {{
        // Use default options
        program = ts.createProgram(filePaths, {{
            target: ts.ScriptTarget.Latest,
            module: ts.ModuleKind.ESNext,
            jsx: jsxMode === 'preserved' ? ts.JsxEmit.Preserve : ts.JsxEmit.React,
            allowJs: true,
            checkJs: false,
            noEmit: true,
            skipLibCheck: true,
            moduleResolution: ts.ModuleResolutionKind.NodeJs,
            baseUrl: projectRoot,
            rootDir: projectRoot
        }});
    }}

    const checker = program.getTypeChecker();
    const results = {{}};

    // Process each file using the shared program
    for (const filePath of filePaths) {{
        try {{
            const sourceFile = program.getSourceFile(filePath);
            if (!sourceFile) {{
                results[filePath] = {{
                    success: false,
                    error: `Could not load source file: ${{filePath}}`
                }};
                continue;
            }}

            const sourceCode = sourceFile.text;

            // Get file-specific diagnostics
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

            // Extract imports
            const imports = extractImports(sourceFile, ts);

            // PHASE 4: Get type checker for inline type extraction in serializeNode
            // Serialize AST with checker for inline type extraction and call resolution
            const ast = serializeNode(sourceFile, 0, null, null, sourceFile, sourceCode, ts, checker, projectRoot);

            // Build result for this file
            results[filePath] = {{
                success: true,
                fileName: filePath,
                languageVersion: ts.ScriptTarget[sourceFile.languageVersion],
                ast: ast,
                diagnostics: diagnostics,
                imports: imports,  // CRITICAL: Import tracking for dependency analysis
                nodeCount: countNodes(ast),
                hasTypes: true,  // PHASE 4: Always true now - type info extracted inline in AST nodes
                jsxMode: jsxMode  // Include JSX mode in result
            }};

        }} catch (error) {{
            results[filePath] = {{
                success: false,
                error: `Error processing file: ${{error.message}}`,
                ast: null,
                diagnostics: []
            }};
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

    Args:
        module_type: Either "module" for ES modules or "commonjs" for CommonJS

    Returns:
        Complete JavaScript helper script as a string
    """
    if module_type == "module":
        return ES_MODULE_SINGLE
    return COMMONJS_SINGLE


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