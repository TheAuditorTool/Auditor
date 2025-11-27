/**
 * Data Flow Extractors - Analysis Layer
 *
 * Data flow and taint tracking extractors. These extractors capture
 * how data moves through the program for security analysis.
 *
 * STABILITY: MEDIUM - Changes when adding new taint tracking patterns.
 * Modify when adding support for new data flow patterns or frameworks.
 *
 * DEPENDENCIES: core_language.js (buildScopeMap for scope context)
 * USED BY: security_extractors.js, taint analysis pipeline
 *
 * Architecture:
 * - Extracted from: core_ast_extractors.js (refactored 2025-11-03)
 * - Used by: ES Module and CommonJS batch templates
 * - Assembly: Runtime file loading + concatenation in js_helper_templates.py
 *
 * Functions (6 data flow extractors):
 * 1. extractCalls() - Call expressions and property accesses
 * 2. extractAssignments() - Variable assignments with data flow
 * 3. extractFunctionCallArgs() - Function call arguments (foundation for taint)
 * 4. extractReturns() - Return statements with scope
 * 5. extractObjectLiterals() - Object literals for dynamic dispatch
 * 6. extractVariableUsage() - Variable reference tracking (utility)
 */

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
 * Extract variable assignments with scope context for taint analysis.
 * Implements Python's extract_typescript_assignments() from typescript_impl.py:1014-1184.
 *
 * @param {Object} sourceFile - TypeScript source file
 * @param {Object} ts - TypeScript compiler API
 * @param {Map} scopeMap - Pre-built line→function mapping
 * @param {string} filePath - Relative file path for database records
 * @returns {Object} - { assignments, assignment_source_vars }
 */
function extractAssignments(sourceFile, ts, scopeMap, filePath) {
    const assignments = [];
    const assignment_source_vars = [];
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
                        const sourceVars = extractVarsFromNode(initializer, sourceFile, ts);
                        sourceVars.forEach((sourceVar, varIndex) => {
                            assignment_source_vars.push({
                                file: filePath,
                                line: line + 1,
                                target_var: targetVar,
                                source_var: sourceVar,
                                var_index: varIndex
                            });
                        });
                        assignments.push({
                            target_var: targetVar,
                            source_expr: initializer.getText(sourceFile).substring(0, 500),
                            line: line + 1,
                            in_function: inFunction
                        });
                    }
                }
                // Handle object destructuring: const {x, y} = obj
                else if (name.kind === ts.SyntaxKind.ObjectBindingPattern && name.elements) {
                    const sourceExprText = initializer.getText(sourceFile).substring(0, 500);
                    const sourceVars = extractVarsFromNode(initializer, sourceFile, ts);

                    name.elements.forEach(elem => {
                        if (elem.name && elem.name.kind === ts.SyntaxKind.Identifier) {
                            const targetVar = elem.name.text || elem.name.escapedText;
                            if (!targetVar) return;

                            sourceVars.forEach((sourceVar, varIndex) => {
                                assignment_source_vars.push({
                                    file: filePath,
                                    line: line + 1,
                                    target_var: targetVar,
                                    source_var: sourceVar,
                                    var_index: varIndex
                                });
                            });

                            assignments.push({
                                target_var: targetVar,
                                source_expr: sourceExprText,
                                line: line + 1,
                                in_function: inFunction
                            });
                        }
                    });
                }
                // Handle array destructuring: const [x, y] = arr
                else if (name.kind === ts.SyntaxKind.ArrayBindingPattern && name.elements) {
                    const sourceExprText = initializer.getText(sourceFile).substring(0, 500);
                    const sourceVars = extractVarsFromNode(initializer, sourceFile, ts);

                    name.elements.forEach((elem, index) => {
                        if (elem.kind === ts.SyntaxKind.BindingElement && elem.name && elem.name.kind === ts.SyntaxKind.Identifier) {
                            const targetVar = elem.name.text || elem.name.escapedText;
                            if (!targetVar) return;

                            sourceVars.forEach((sourceVar, varIndex) => {
                                assignment_source_vars.push({
                                    file: filePath,
                                    line: line + 1,
                                    target_var: targetVar,
                                    source_var: sourceVar,
                                    var_index: varIndex
                                });
                            });

                            assignments.push({
                                target_var: targetVar,
                                source_expr: sourceExprText,
                                line: line + 1,
                                in_function: inFunction
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
                const sourceVars = extractVarsFromNode(right, sourceFile, ts);

                sourceVars.forEach((sourceVar, varIndex) => {
                    assignment_source_vars.push({
                        file: filePath,
                        line: line + 1,
                        target_var: targetVar,
                        source_var: sourceVar,
                        var_index: varIndex
                    });
                });

                assignments.push({
                    target_var: targetVar,
                    source_expr: sourceExpr,
                    line: line + 1,
                    in_function: inFunction
                });
            }
        }

        ts.forEachChild(node, child => traverse(child, depth + 1));
    }

    traverse(sourceFile);
    return { assignments, assignment_source_vars };
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
                        // CRITICAL FIX: params array contains {name: "param"} dicts (architectural contract)
                        // Must extract .name field to get the string value
                        const paramName = i < params.length ? params[i].name : 'arg' + i;
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

        // CRITICAL FIX: Handle NewExpression for CDK construct extraction
        // Pattern: new s3.Bucket(this, 'MyBucket', {...})
        // Creates function_call_args with callee_function = "new s3.Bucket"
        if (node.kind === ts.SyntaxKind.NewExpression) {
            const { line } = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));
            const callerFunction = scopeMap.get(line + 1) || 'global';

            // Extract class name
            let className = '';
            if (node.expression) {
                const exprKind = ts.SyntaxKind[node.expression.kind];
                if (exprKind === 'Identifier') {
                    className = node.expression.text || node.expression.escapedText || '';
                } else if (exprKind === 'PropertyAccessExpression') {
                    className = buildDottedName(node.expression, ts);
                }
            }

            // Prefix with "new " to distinguish from regular calls
            if (className) {
                const calleeName = 'new ' + className;

                // Extract arguments (same logic as CallExpression)
                const args = node.arguments || [];
                const params = functionParams.get(className) || [];

                // Handle 0-arg constructors (e.g., new Date())
                if (args.length === 0) {
                    calls.push({
                        line: line + 1,
                        caller_function: callerFunction,
                        callee_function: calleeName,
                        argument_index: null,
                        argument_expr: null,
                        param_name: null,
                        callee_file_path: null  // Constructor resolution not critical for CDK
                    });
                } else {
                    // Constructors with arguments (e.g., new s3.Bucket(this, 'MyBucket', {...}))
                    args.forEach((arg, i) => {
                        // CRITICAL FIX: params array contains {name: "param"} dicts (architectural contract)
                        // Must extract .name field to get the string value
                        const paramName = i < params.length ? params[i].name : 'arg' + i;
                        const argExpr = arg.getText(sourceFile).substring(0, 500);

                        calls.push({
                            line: line + 1,
                            caller_function: callerFunction,
                            callee_function: calleeName,
                            argument_index: i,
                            argument_expr: argExpr,
                            param_name: paramName,
                            callee_file_path: null  // Constructor resolution not critical
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
 * @param {string} filePath - Relative file path for database records
 * @returns {Object} - { returns, return_source_vars }
 */
function extractReturns(sourceFile, ts, scopeMap, filePath) {
    const returns = [];
    const return_source_vars = [];
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

                // Extract variables and flatten to junction array
                returnVars = extractVarsFromNode(expression, sourceFile, ts);
                returnVars.forEach((sourceVar, varIndex) => {
                    return_source_vars.push({
                        file: filePath,
                        line: line + 1,
                        function_name: functionName,
                        source_var: sourceVar,
                        var_index: varIndex
                    });
                });
            }

            returns.push({
                function_name: functionName,
                line: line + 1,
                return_expr: returnExpr,
                has_jsx: hasJsx,
                returns_component: returnsComponent,
                return_index: currentCount + 1
            });
        }

        ts.forEachChild(node, child => traverse(child, depth + 1));
    }

    traverse(sourceFile);
    return { returns, return_source_vars };
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
 * @param {Array} assignment_source_vars - Flat array from extractAssignments
 * @returns {Array} - Variable usage records
 */
function extractVariableUsage(assignments, functionCallArgs, assignment_source_vars) {
    const usage = [];

    // Build lookup for assignment context (line+target_var -> in_function)
    const assignmentContext = new Map();
    assignments.forEach(assign => {
        const key = assign.line + '|' + assign.target_var;
        assignmentContext.set(key, assign.in_function);
    });

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
    });

    // Track reads from source variables (using flat junction array)
    assignment_source_vars.forEach(srcVar => {
        const contextKey = srcVar.line + '|' + srcVar.target_var;
        const inFunction = assignmentContext.get(contextKey) || 'global';
        usage.push({
            line: srcVar.line,
            variable_name: srcVar.source_var,
            usage_type: 'read',
            in_component: inFunction,
            in_hook: '',
            scope_level: inFunction === 'global' ? 0 : 1
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
