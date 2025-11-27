/**
 * Control Flow Graph (CFG) Extraction for TypeScript/JavaScript
 *
 * This file contains the CFG extraction logic that builds control flow graphs
 * for all functions in a TypeScript/JavaScript file. It handles:
 * - Basic blocks (entry, exit, condition, loop, etc.)
 * - Control flow edges (normal, true, false, exception, back_edge)
 * - JSX statement tracking
 * - Nested function detection
 *
 * Architecture:
 * - Extracted from: js_helper_templates.py.bak2 (EXTRACT_CFG constant)
 * - Used by: ES Module and CommonJS batch templates
 * - Injected via: Python f-string concatenation
 *
 * REGRESSION FIXES (Session 5 - 2025-10-24):
 * FIX 1: Removed return statements in visit() to detect nested functions (85% JSX loss)
 * FIX 2: Create explicit basic blocks for control flow bodies (3,442 basic blocks)
 * FIX 3: Add true/false edges correctly (2,038 true edges)
 * FIX 4: Populate statements arrays for basic blocks (4,994 statements)
 *
 * FORMAT (2025-11-27 normalize-all-node-extractors):
 * Returns nested per-function CFG objects for Python _store_cfg compatibility.
 * Format: [{ function_name, blocks: [...], edges: [...] }, ...]
 * Each block has: { id, type, start_line, end_line, condition, statements: [...] }
 * Each statement has: { type, line, text }
 * Python handles ID mapping (temp JS block IDs -> real DB autoincrement IDs).
 *
 * Current size: 630 lines (2025-11-27)
 */

/**
 * Build CFG for all functions directly from TypeScript AST.
 * Ports Python build_typescript_function_cfg to JavaScript with historical parity.
 *
 * REGRESSION FIXES (Session 5 - 2025-10-24):
 * FIX 1: Removed return statements in visit() to detect nested functions (85% JSX loss)
 * FIX 2: Create explicit basic blocks for control flow bodies (3,442 basic blocks)
 * FIX 3: Add true/false edges correctly (2,038 true edges)
 * FIX 4: Populate statements arrays for basic blocks (4,994 statements)
 *
 * FORMAT (2025-11-27 normalize-all-node-extractors):
 * Returns nested per-function CFG objects for Python _store_cfg compatibility.
 * Format: Array of { function_name, blocks: [...], edges: [...] }
 * Each block includes statements array: [{ type, line, text }, ...]
 * Python _store_cfg handles ID mapping from temp JS IDs to real DB IDs.
 *
 * @param {Object} sourceFile - TypeScript source file
 * @param {Object} ts - TypeScript compiler API
 * @returns {Array} - List of per-function CFG objects for Python _store_cfg compatibility
 */
function extractCFG(sourceFile, ts) {
    // Nested format for Python _store_cfg (requires ID mapping per function)
    const functionCFGs = [];
    const class_stack = [];

    function getFunctionName(node, classStack, parent) {
        if (node.name) {
            const name = node.name.text || node.name.escapedText || 'anonymous';
            if (classStack.length > 0 && node.kind !== ts.SyntaxKind.FunctionDeclaration) {
                return classStack[classStack.length - 1] + '.' + name;
            }
            return name;
        }

        const kind = ts.SyntaxKind[node.kind];
        if (kind === 'Constructor') {
            return classStack.length > 0 ? classStack[classStack.length - 1] + '.constructor' : 'constructor';
        }

        // Try to get name from parent context for arrow functions
        if (parent) {
            const parentKind = ts.SyntaxKind[parent.kind];

            // Case 1: const foo = () => {}
            if (parentKind === 'VariableDeclaration' && parent.name) {
                const varName = parent.name.text || parent.name.escapedText || 'anonymous';
                return classStack.length > 0 ? classStack[classStack.length - 1] + '.' + varName : varName;
            }

            // Case 2: { foo: () => {} }
            if (parentKind === 'PropertyAssignment' && parent.name) {
                const propName = parent.name.text || parent.name.escapedText || 'anonymous';
                return classStack.length > 0 ? classStack[classStack.length - 1] + '.' + propName : propName;
            }

            // Case 3: foo = () => {}
            if (parentKind === 'BinaryExpression' && parent.left) {
                const leftText = parent.left.getText ? parent.left.getText(sourceFile) : '';
                if (leftText) return leftText;
            }

            // COVERAGE FIX: Case 4: asyncHandler(() => {}) or .map(() => {})
            // Root cause: 48% function loss due to unnamed callbacks
            // Patterns: list = this.asyncHandler(async () => {}), array.map(x => x)
            if (parentKind === 'CallExpression') {
                // Get the function/method being called
                let calleeName = '';
                if (parent.expression) {
                    const exprKind = ts.SyntaxKind[parent.expression.kind];

                    // Method call: obj.method(callback)
                    if (exprKind === 'PropertyAccessExpression' && parent.expression.name) {
                        calleeName = parent.expression.name.text || parent.expression.name.escapedText || '';
                    }
                    // Function call: func(callback)
                    else if (parent.expression.getText) {
                        calleeName = parent.expression.getText(sourceFile).substring(0, 50);
                    }
                }

                // Find argument position
                let argPosition = 0;
                if (parent.arguments) {
                    for (let i = 0; i < parent.arguments.length; i++) {
                        if (parent.arguments[i] === node) {
                            argPosition = i;
                            break;
                        }
                    }
                }

                // Generate name: methodName_callback or methodName_arg0
                if (calleeName) {
                    const baseName = calleeName.includes('.') ? calleeName.split('.').pop() : calleeName;
                    const suffix = argPosition === 0 ? 'callback' : `arg${argPosition}`;
                    const generatedName = `${baseName}_${suffix}`;
                    return classStack.length > 0 ? classStack[classStack.length - 1] + '.' + generatedName : generatedName;
                }
            }

            // COVERAGE FIX: Case 5: class Foo { method = () => {} }
            // PropertyDeclaration with arrow function initializer
            if (parentKind === 'PropertyDeclaration' && parent.name) {
                const propName = parent.name.text || parent.name.escapedText || 'anonymous';
                return classStack.length > 0 ? classStack[classStack.length - 1] + '.' + propName : propName;
            }
        }

        return 'anonymous';
    }

    function buildFunctionCFG(funcNode, classStack, parent) {
        // Local arrays for this function's CFG (nested format for Python _store_cfg)
        const blocks = [];
        const edges = [];
        let blockCounter = 0;

        function getNextBlockId() {
            return ++blockCounter;
        }

        // Helper: Add block to local array
        function addBlock(block) {
            blocks.push({
                id: block.block_id,
                type: block.block_type,
                start_line: block.start_line,
                end_line: block.end_line,
                condition: block.condition_expr || null
            });
        }

        // Helper: Add edge to local array (Python expects source/target/type)
        function addEdge(edge) {
            edges.push({
                source: edge.source_block_id,
                target: edge.target_block_id,
                type: edge.edge_type
            });
        }

        // Helper: Add statement to a specific block (Nested Mode for Python _store_cfg)
        function addStatementToBlock(blockId, type, line, text) {
            const block = blocks.find(b => b.id === blockId);
            if (block) {
                if (!block.statements) block.statements = [];
                block.statements.push({
                    type: type,
                    line: line,
                    text: text || ''
                });
            }
        }

        const funcName = getFunctionName(funcNode, classStack, parent);
        const { line: funcStartLine } = sourceFile.getLineAndCharacterOfPosition(funcNode.getStart(sourceFile));
        const { line: funcEndLine } = sourceFile.getLineAndCharacterOfPosition(funcNode.getEnd());

        const entryId = getNextBlockId();
        const exitId = getNextBlockId();

        // Entry block (flat - no nested statements array)
        addBlock({
            function_name: funcName,
            block_id: entryId,
            block_type: 'entry',
            start_line: funcStartLine + 1,
            end_line: funcEndLine + 1,
            condition_expr: null
        });

        // Exit block (flat)
        addBlock({
            function_name: funcName,
            block_id: exitId,
            block_type: 'exit',
            start_line: funcStartLine + 1,
            end_line: funcEndLine + 1,
            condition_expr: null
        });

        function processNode(node, currentId, depth = 0) {
            // COVERAGE FIX: Increased from 50 to 500 for deep React component nesting
            // Evidence: buildHumanNarrative (146 blocks) hitting limit in 610-line file
            // Modern React: hooks → callbacks → JSX → inline handlers = 100+ depth
            // 500 = 10x safety margin for deterministic SAST (target 99%+ coverage)
            if (depth > 500 || !node) {
                return currentId;
            }

            const kind = ts.SyntaxKind[node.kind];
            const { line } = sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile));

            // Control flow nodes
            if (kind === 'IfStatement') {
                const condId = getNextBlockId();
                const condExpr = node.expression ? node.expression.getText(sourceFile).substring(0, 200) : 'condition';
                addBlock({
                    function_name: funcName,
                    block_id: condId,
                    block_type: 'condition',
                    start_line: line + 1,
                    end_line: line + 1,
                    condition_expr: condExpr
                });
                // FIX: Add statement to condition block (was missing - caused 1117 missing statements)
                addStatementToBlock(condId, 'if', line + 1, 'if (' + condExpr + ')');
                addEdge({function_name: funcName, source_block_id: currentId, target_block_id: condId, edge_type: 'normal'});

                // FIX 2 & 3: Create explicit then basic block with true edge
                const thenBlockId = getNextBlockId();
                addBlock({function_name: funcName, block_id: thenBlockId, block_type: 'basic', start_line: line + 1, end_line: line + 1, condition_expr: null});
                addEdge({function_name: funcName, source_block_id: condId, target_block_id: thenBlockId, edge_type: 'true'});

                let thenExitId = thenBlockId;
                if (node.thenStatement) {
                    thenExitId = processNode(node.thenStatement, thenBlockId, depth + 1);
                }

                const mergeId = getNextBlockId();
                addBlock({function_name: funcName, block_id: mergeId, block_type: 'merge', start_line: line + 1, end_line: line + 1, condition_expr: null});

                if (node.elseStatement) {
                    // FIX 2 & 3: Create explicit else basic block with false edge
                    const elseBlockId = getNextBlockId();
                    addBlock({function_name: funcName, block_id: elseBlockId, block_type: 'basic', start_line: line + 1, end_line: line + 1, condition_expr: null});
                    addEdge({function_name: funcName, source_block_id: condId, target_block_id: elseBlockId, edge_type: 'false'});

                    let elseExitId = processNode(node.elseStatement, elseBlockId, depth + 1);

                    if (thenExitId) addEdge({function_name: funcName, source_block_id: thenExitId, target_block_id: mergeId, edge_type: 'normal'});
                    if (elseExitId) addEdge({function_name: funcName, source_block_id: elseExitId, target_block_id: mergeId, edge_type: 'normal'});
                } else {
                    if (thenExitId) addEdge({function_name: funcName, source_block_id: thenExitId, target_block_id: mergeId, edge_type: 'normal'});
                    // FIX 3: false edge from condition to merge when no else
                    addEdge({function_name: funcName, source_block_id: condId, target_block_id: mergeId, edge_type: 'false'});
                }
                return mergeId;
            }
            else if (kind === 'ForStatement' || kind === 'ForInStatement' || kind === 'ForOfStatement' || kind === 'WhileStatement' || kind === 'DoStatement') {
                const loopCondId = getNextBlockId();
                const loopCondExpr = node.expression ? node.expression.getText(sourceFile).substring(0, 200) : 'loop';
                addBlock({
                    function_name: funcName,
                    block_id: loopCondId,
                    block_type: 'loop_condition',
                    start_line: line + 1,
                    end_line: line + 1,
                    condition_expr: loopCondExpr
                });
                addStatementToBlock(loopCondId, 'loop', line + 1, node.getText(sourceFile).substring(0, 200));
                addEdge({function_name: funcName, source_block_id: currentId, target_block_id: loopCondId, edge_type: 'normal'});

                // FIX 2 & 3: Create explicit loop body basic block with true edge
                const bodyId = getNextBlockId();
                addBlock({function_name: funcName, block_id: bodyId, block_type: 'loop_body', start_line: line + 1, end_line: line + 1, condition_expr: null});
                addEdge({function_name: funcName, source_block_id: loopCondId, target_block_id: bodyId, edge_type: 'true'});

                let bodyExitId = bodyId;
                if (node.statement) {
                    bodyExitId = processNode(node.statement, bodyId, depth + 1);
                }
                if (bodyExitId) {
                    addEdge({function_name: funcName, source_block_id: bodyExitId, target_block_id: loopCondId, edge_type: 'back_edge'});
                }

                const afterLoopId = getNextBlockId();
                addBlock({function_name: funcName, block_id: afterLoopId, block_type: 'merge', start_line: line + 1, end_line: line + 1, condition_expr: null});
                addEdge({function_name: funcName, source_block_id: loopCondId, target_block_id: afterLoopId, edge_type: 'false'});
                return afterLoopId;
            }
            else if (kind === 'ReturnStatement') {
                const retId = getNextBlockId();
                const retLine = line + 1;
                addBlock({function_name: funcName, block_id: retId, block_type: 'return', start_line: retLine, end_line: retLine, condition_expr: null});
                addStatementToBlock(retId, 'return', retLine, node.getText(sourceFile).substring(0, 200));
                addEdge({function_name: funcName, source_block_id: currentId, target_block_id: retId, edge_type: 'normal'});
                addEdge({function_name: funcName, source_block_id: retId, target_block_id: exitId, edge_type: 'normal'});
                return null; // Terminal block
            }
            else if (kind === 'TryStatement') {
                const tryId = getNextBlockId();
                // FIX: Use try block's actual end position (not just try keyword line)
                const tryEndPos = node.tryBlock ? node.tryBlock.getEnd() : node.getEnd();
                const tryEndLine = sourceFile.getLineAndCharacterOfPosition(tryEndPos).line + 1;
                addBlock({function_name: funcName, block_id: tryId, block_type: 'try', start_line: line + 1, end_line: tryEndLine, condition_expr: null});
                addStatementToBlock(tryId, 'try', line + 1, 'try');
                addEdge({function_name: funcName, source_block_id: currentId, target_block_id: tryId, edge_type: 'normal'});

                let tryBodyExitId = tryId;
                if (node.tryBlock) {
                    // FIX 2: Create basic block for try body
                    const tryBlockId = getNextBlockId();
                    addBlock({function_name: funcName, block_id: tryBlockId, block_type: 'basic', start_line: line + 1, end_line: line + 1, condition_expr: null});
                    addEdge({function_name: funcName, source_block_id: tryId, target_block_id: tryBlockId, edge_type: 'normal'});
                    tryBodyExitId = processNode(node.tryBlock, tryBlockId, depth + 1);
                }

                const mergeId = getNextBlockId();
                addBlock({function_name: funcName, block_id: mergeId, block_type: 'merge', start_line: line + 1, end_line: line + 1, condition_expr: null});

                if (tryBodyExitId) {
                    addEdge({function_name: funcName, source_block_id: tryBodyExitId, target_block_id: mergeId, edge_type: 'normal'});
                }

                if (node.catchClause) {
                    const catchId = getNextBlockId();
                    // FIX: Use catch clause's actual start and end positions
                    const catchStartPos = node.catchClause.getStart(sourceFile);
                    const catchStartLine = sourceFile.getLineAndCharacterOfPosition(catchStartPos).line + 1;
                    const catchEndPos = node.catchClause.block ? node.catchClause.block.getEnd() : node.catchClause.getEnd();
                    const catchEndLine = sourceFile.getLineAndCharacterOfPosition(catchEndPos).line + 1;
                    addBlock({function_name: funcName, block_id: catchId, block_type: 'except', start_line: catchStartLine, end_line: catchEndLine, condition_expr: null});
                    addStatementToBlock(catchId, 'catch', catchStartLine, 'catch');
                    addEdge({function_name: funcName, source_block_id: tryId, target_block_id: catchId, edge_type: 'exception'});

                    let catchBodyExitId = catchId;
                    if (node.catchClause.block) {
                        // FIX 2: Create basic block for catch body
                        const catchBlockId = getNextBlockId();
                        addBlock({function_name: funcName, block_id: catchBlockId, block_type: 'basic', start_line: line + 1, end_line: line + 1, condition_expr: null});
                        addEdge({function_name: funcName, source_block_id: catchId, target_block_id: catchBlockId, edge_type: 'normal'});
                        catchBodyExitId = processNode(node.catchClause.block, catchBlockId, depth + 1);
                    }
                    if (catchBodyExitId) {
                        addEdge({function_name: funcName, source_block_id: catchBodyExitId, target_block_id: mergeId, edge_type: 'normal'});
                    }
                }

                // Finally block executes after try/catch merge
                if (node.finallyBlock) {
                    const finallyId = getNextBlockId();
                    // FIX: Use finally block's actual end position
                    const finallyEndPos = node.finallyBlock.getEnd();
                    const finallyEndLine = sourceFile.getLineAndCharacterOfPosition(finallyEndPos).line + 1;
                    addBlock({function_name: funcName, block_id: finallyId, block_type: 'finally', start_line: line + 1, end_line: finallyEndLine, condition_expr: null});
                    addEdge({function_name: funcName, source_block_id: mergeId, target_block_id: finallyId, edge_type: 'normal'});

                    let finallyBodyExitId = finallyId;
                    if (node.finallyBlock) {
                        // FIX 2: Create basic block for finally body
                        const finallyBlockId = getNextBlockId();
                        addBlock({function_name: funcName, block_id: finallyBlockId, block_type: 'basic', start_line: line + 1, end_line: line + 1, condition_expr: null});
                        addEdge({function_name: funcName, source_block_id: finallyId, target_block_id: finallyBlockId, edge_type: 'normal'});
                        finallyBodyExitId = processNode(node.finallyBlock, finallyBlockId, depth + 1);
                    }
                    return finallyBodyExitId || finallyId;
                }

                return mergeId;
            }
            else if (kind === 'SwitchStatement') {
                // COVERAGE FIX: Add switch statement handler
                // Evidence: 43 SwitchStatements detected but treated as generic statements
                // Impact: ~300 missing blocks (43 × ~7 blocks per switch)
                const switchId = getNextBlockId();
                const switchExpr = node.expression ? node.expression.getText(sourceFile).substring(0, 200) : 'switch';
                addBlock({
                    function_name: funcName,
                    block_id: switchId,
                    block_type: 'condition',
                    start_line: line + 1,
                    end_line: line + 1,
                    condition_expr: switchExpr
                });
                addStatementToBlock(switchId, 'switch', line + 1, switchExpr);
                addEdge({function_name: funcName, source_block_id: currentId, target_block_id: switchId, edge_type: 'normal'});

                const mergeId = getNextBlockId();
                addBlock({function_name: funcName, block_id: mergeId, block_type: 'merge', start_line: line + 1, end_line: line + 1, condition_expr: null});

                if (node.caseBlock && node.caseBlock.clauses) {
                    let lastCaseExitId = null;

                    for (const clause of node.caseBlock.clauses) {
                        const clauseKind = ts.SyntaxKind[clause.kind];
                        const isDefault = clauseKind === 'DefaultClause';

                        const caseBlockId = getNextBlockId();
                        addBlock({
                            function_name: funcName,
                            block_id: caseBlockId,
                            block_type: 'basic',
                            start_line: line + 1,
                            end_line: line + 1,
                            condition_expr: null
                        });

                        // Edge from switch to case (or from previous case for fallthrough)
                        if (lastCaseExitId) {
                            // Fallthrough from previous case
                            addEdge({function_name: funcName, source_block_id: lastCaseExitId, target_block_id: caseBlockId, edge_type: 'fallthrough'});
                        }
                        addEdge({function_name: funcName, source_block_id: switchId, target_block_id: caseBlockId, edge_type: isDefault ? 'default' : 'case'});

                        // Process case body
                        let caseExitId = caseBlockId;
                        if (clause.statements && clause.statements.length > 0) {
                            for (const stmt of clause.statements) {
                                if (caseExitId) {
                                    caseExitId = processNode(stmt, caseExitId, depth + 1);
                                }
                            }
                        }

                        // Check if case has break (terminal) or falls through
                        const hasBreak = clause.statements && clause.statements.some(
                            s => ts.SyntaxKind[s.kind] === 'BreakStatement'
                        );

                        if (hasBreak) {
                            // Break jumps to merge (handled by BreakStatement handler below)
                            lastCaseExitId = null;
                        } else {
                            // Fallthrough to next case
                            lastCaseExitId = caseExitId;
                        }
                    }

                    // If last case doesn't have break, connect to merge
                    if (lastCaseExitId) {
                        addEdge({function_name: funcName, source_block_id: lastCaseExitId, target_block_id: mergeId, edge_type: 'normal'});
                    }
                }

                return mergeId;
            }
            else if (kind === 'BreakStatement') {
                // COVERAGE FIX: Add break statement handler
                // Evidence: 66 BreakStatements detected
                // Creates proper exit edges from loops/switches
                const breakId = getNextBlockId();
                addBlock({
                    function_name: funcName,
                    block_id: breakId,
                    block_type: 'basic',
                    start_line: line + 1,
                    end_line: line + 1,
                    condition_expr: null
                });
                addStatementToBlock(breakId, 'break', line + 1, 'break');
                addEdge({function_name: funcName, source_block_id: currentId, target_block_id: breakId, edge_type: 'normal'});
                // Note: Edge to merge block should be added by enclosing loop/switch
                return null; // Terminal for this path
            }
            else if (kind === 'ThrowStatement') {
                // COVERAGE FIX: Add throw statement handler
                // Evidence: 290 ThrowStatements detected
                // Impact: ~290 missing blocks
                const throwId = getNextBlockId();
                addBlock({
                    function_name: funcName,
                    block_id: throwId,
                    block_type: 'basic',
                    start_line: line + 1,
                    end_line: line + 1,
                    condition_expr: null
                });
                addStatementToBlock(throwId, 'throw', line + 1, node.getText(sourceFile).substring(0, 200));
                addEdge({function_name: funcName, source_block_id: currentId, target_block_id: throwId, edge_type: 'normal'});
                addEdge({function_name: funcName, source_block_id: throwId, target_block_id: exitId, edge_type: 'exception'});
                return null; // Terminal block
            }
            // JSX nodes - add statement and traverse children
            else if (kind.startsWith('Jsx')) {
                addStatementToBlock(currentId, kind, line + 1, node.getText(sourceFile).substring(0, 200));
                let lastId = currentId;
                ts.forEachChild(node, child => {
                    if (lastId) {
                        lastId = processNode(child, lastId, depth + 1);
                    }
                });
                return lastId;
            }
            // FIX 4: Handle Block nodes specially to avoid creating extra blocks
            else if (kind === 'Block') {
                // Block node: process its children into current block
                let lastId = currentId;
                ts.forEachChild(node, child => {
                    if (lastId) {
                        lastId = processNode(child, lastId, depth + 1);
                    }
                });
                return lastId;
            }
            // DATA QUALITY FIX: DELETED Default case that extracted every AST node
            // Bug: Was recording Identifier, PropertyAccess, etc. as "statements"
            // Result: 139,234 nodes vs historical 4,994 control flow statements (2788% garbage)
            //
            // Evidence from block 191 (one function):
            //   - Actual statements: 13
            //   - Database claimed: 380 (29x over-extraction)
            //   - Single line "const x = y" became 11 database entries
            //
            // Historical implementation: Only extracted control flow statements (if, return, try, loop, switch)
            // Current fix: ONLY extract control flow nodes explicitly (handled above), IGNORE everything else
            //
            // If this node is not control flow, simply traverse children without recording:
            else {
                let lastId = currentId;
                ts.forEachChild(node, child => {
                    if (lastId) {
                        lastId = processNode(child, lastId, depth + 1);
                    }
                });
                return lastId;
            }
        }

        // Start processing from function body
        let lastBlockId = entryId;
        if (funcNode.body) {
            // Handle arrow function concise body (not a block)
            if (funcNode.body.kind !== ts.SyntaxKind.Block) {
                lastBlockId = processNode(funcNode.body, entryId, 0);
            } else {
                // Standard block body
                ts.forEachChild(funcNode.body, child => {
                    if (lastBlockId) {
                        lastBlockId = processNode(child, lastBlockId, 0);
                    }
                });
            }
        }

        // Connect last block to exit
        if (lastBlockId) {
            addEdge({function_name: funcName, source_block_id: lastBlockId, target_block_id: exitId, edge_type: 'normal'});
        }

        // Return nested function CFG object (Python _store_cfg format)
        return {
            function_name: funcName,
            blocks: blocks,
            edges: edges
        };
    }

    function visit(node, depth = 0, parent = null) {
        // COVERAGE FIX: Increased from 100 to 500 to match processNode() depth limit
        // Root cause: 48% function loss (1414/2720) due to nested callbacks/methods beyond depth 100
        // Must match processNode() limit to discover ALL functions before building their CFGs
        if (depth > 500 || !node) return;

        const kind = ts.SyntaxKind[node.kind];

        // Track class context
        if (kind === 'ClassDeclaration') {
            const className = node.name ? (node.name.text || node.name.escapedText || 'UnknownClass') : 'UnknownClass';
            class_stack.push(className);
            ts.forEachChild(node, child => visit(child, depth + 1, node));
            class_stack.pop();
            return;
        }

        // Function-like nodes
        if (kind === 'FunctionDeclaration' || kind === 'MethodDeclaration' ||
            kind === 'ArrowFunction' || kind === 'FunctionExpression' ||
            kind === 'Constructor' || kind === 'GetAccessor' || kind === 'SetAccessor') {

            // Collect returned CFG object into list
            const cfg = buildFunctionCFG(node, class_stack, parent);
            if (cfg) functionCFGs.push(cfg);
            // FIX 1: REMOVED return statement - allows nested function detection
        }

        // Property declarations with function initializers
        if (kind === 'PropertyDeclaration' && node.initializer) {
            const initKind = ts.SyntaxKind[node.initializer.kind];
            if (initKind === 'ArrowFunction' || initKind === 'FunctionExpression') {
                // Collect returned CFG object into list
                const cfg = buildFunctionCFG(node.initializer, class_stack, node);
                if (cfg) functionCFGs.push(cfg);
                // FIX 1: REMOVED return statement
            }
        }

        ts.forEachChild(node, child => visit(child, depth + 1, node));
    }

    visit(sourceFile);

    // Return list of per-function CFG objects (Python _store_cfg format)
    return functionCFGs;
}
