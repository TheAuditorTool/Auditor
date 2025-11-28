function extractCFG(sourceFile, ts) {
  const functionCFGs = [];
  const class_stack = [];

  function getFunctionName(node, classStack, parent) {
    if (node.name) {
      const name = node.name.text || node.name.escapedText || "anonymous";
      if (
        classStack.length > 0 &&
        node.kind !== ts.SyntaxKind.FunctionDeclaration
      ) {
        return classStack[classStack.length - 1] + "." + name;
      }
      return name;
    }

    const kind = ts.SyntaxKind[node.kind];
    if (kind === "Constructor") {
      return classStack.length > 0
        ? classStack[classStack.length - 1] + ".constructor"
        : "constructor";
    }

    if (parent) {
      const parentKind = ts.SyntaxKind[parent.kind];

      if (parentKind === "VariableDeclaration" && parent.name) {
        const varName =
          parent.name.text || parent.name.escapedText || "anonymous";
        return classStack.length > 0
          ? classStack[classStack.length - 1] + "." + varName
          : varName;
      }

      if (parentKind === "PropertyAssignment" && parent.name) {
        const propName =
          parent.name.text || parent.name.escapedText || "anonymous";
        return classStack.length > 0
          ? classStack[classStack.length - 1] + "." + propName
          : propName;
      }

      if (parentKind === "BinaryExpression" && parent.left) {
        const leftText = parent.left.getText
          ? parent.left.getText(sourceFile)
          : "";
        if (leftText) return leftText;
      }

      if (parentKind === "CallExpression") {
        let calleeName = "";
        if (parent.expression) {
          const exprKind = ts.SyntaxKind[parent.expression.kind];

          if (
            exprKind === "PropertyAccessExpression" &&
            parent.expression.name
          ) {
            calleeName =
              parent.expression.name.text ||
              parent.expression.name.escapedText ||
              "";
          } else if (parent.expression.getText) {
            calleeName = parent.expression.getText(sourceFile).substring(0, 50);
          }
        }

        let argPosition = 0;
        if (parent.arguments) {
          for (let i = 0; i < parent.arguments.length; i++) {
            if (parent.arguments[i] === node) {
              argPosition = i;
              break;
            }
          }
        }

        if (calleeName) {
          const baseName = calleeName.includes(".")
            ? calleeName.split(".").pop()
            : calleeName;
          const suffix = argPosition === 0 ? "callback" : `arg${argPosition}`;
          const generatedName = `${baseName}_${suffix}`;
          return classStack.length > 0
            ? classStack[classStack.length - 1] + "." + generatedName
            : generatedName;
        }
      }

      if (parentKind === "PropertyDeclaration" && parent.name) {
        const propName =
          parent.name.text || parent.name.escapedText || "anonymous";
        return classStack.length > 0
          ? classStack[classStack.length - 1] + "." + propName
          : propName;
      }
    }

    return "anonymous";
  }

  function buildFunctionCFG(funcNode, classStack, parent) {
    const blocks = [];
    const edges = [];
    let blockCounter = 0;

    function getNextBlockId() {
      return ++blockCounter;
    }

    function addBlock(block) {
      blocks.push({
        id: block.block_id,
        type: block.block_type,
        start_line: block.start_line,
        end_line: block.end_line,
        condition: block.condition_expr || null,
      });
    }

    function addEdge(edge) {
      edges.push({
        source: edge.source_block_id,
        target: edge.target_block_id,
        type: edge.edge_type,
      });
    }

    function addStatementToBlock(blockId, type, line, text) {
      const block = blocks.find((b) => b.id === blockId);
      if (block) {
        if (!block.statements) block.statements = [];
        block.statements.push({
          type: type,
          line: line,
          text: text || "",
        });
      }
    }

    const funcName = getFunctionName(funcNode, classStack, parent);
    const { line: funcStartLine } = sourceFile.getLineAndCharacterOfPosition(
      funcNode.getStart(sourceFile),
    );
    const { line: funcEndLine } = sourceFile.getLineAndCharacterOfPosition(
      funcNode.getEnd(),
    );

    const entryId = getNextBlockId();
    const exitId = getNextBlockId();

    addBlock({
      function_name: funcName,
      block_id: entryId,
      block_type: "entry",
      start_line: funcStartLine + 1,
      end_line: funcEndLine + 1,
      condition_expr: null,
    });

    addBlock({
      function_name: funcName,
      block_id: exitId,
      block_type: "exit",
      start_line: funcStartLine + 1,
      end_line: funcEndLine + 1,
      condition_expr: null,
    });

    function processNode(node, currentId, depth = 0) {
      if (depth > 500 || !node) {
        return currentId;
      }

      const kind = ts.SyntaxKind[node.kind];
      const { line } = sourceFile.getLineAndCharacterOfPosition(
        node.getStart(sourceFile),
      );

      if (kind === "IfStatement") {
        const condId = getNextBlockId();
        const condExpr = node.expression
          ? node.expression.getText(sourceFile).substring(0, 200)
          : "condition";
        addBlock({
          function_name: funcName,
          block_id: condId,
          block_type: "condition",
          start_line: line + 1,
          end_line: line + 1,
          condition_expr: condExpr,
        });
        addStatementToBlock(condId, "if", line + 1, "if (" + condExpr + ")");
        addEdge({
          function_name: funcName,
          source_block_id: currentId,
          target_block_id: condId,
          edge_type: "normal",
        });

        const thenBlockId = getNextBlockId();
        addBlock({
          function_name: funcName,
          block_id: thenBlockId,
          block_type: "basic",
          start_line: line + 1,
          end_line: line + 1,
          condition_expr: null,
        });
        addEdge({
          function_name: funcName,
          source_block_id: condId,
          target_block_id: thenBlockId,
          edge_type: "true",
        });

        let thenExitId = thenBlockId;
        if (node.thenStatement) {
          thenExitId = processNode(node.thenStatement, thenBlockId, depth + 1);
        }

        const mergeId = getNextBlockId();
        addBlock({
          function_name: funcName,
          block_id: mergeId,
          block_type: "merge",
          start_line: line + 1,
          end_line: line + 1,
          condition_expr: null,
        });

        if (node.elseStatement) {
          const elseBlockId = getNextBlockId();
          addBlock({
            function_name: funcName,
            block_id: elseBlockId,
            block_type: "basic",
            start_line: line + 1,
            end_line: line + 1,
            condition_expr: null,
          });
          addEdge({
            function_name: funcName,
            source_block_id: condId,
            target_block_id: elseBlockId,
            edge_type: "false",
          });

          let elseExitId = processNode(
            node.elseStatement,
            elseBlockId,
            depth + 1,
          );

          if (thenExitId)
            addEdge({
              function_name: funcName,
              source_block_id: thenExitId,
              target_block_id: mergeId,
              edge_type: "normal",
            });
          if (elseExitId)
            addEdge({
              function_name: funcName,
              source_block_id: elseExitId,
              target_block_id: mergeId,
              edge_type: "normal",
            });
        } else {
          if (thenExitId)
            addEdge({
              function_name: funcName,
              source_block_id: thenExitId,
              target_block_id: mergeId,
              edge_type: "normal",
            });
          addEdge({
            function_name: funcName,
            source_block_id: condId,
            target_block_id: mergeId,
            edge_type: "false",
          });
        }
        return mergeId;
      } else if (
        kind === "ForStatement" ||
        kind === "ForInStatement" ||
        kind === "ForOfStatement" ||
        kind === "WhileStatement" ||
        kind === "DoStatement"
      ) {
        const loopCondId = getNextBlockId();
        const loopCondExpr = node.expression
          ? node.expression.getText(sourceFile).substring(0, 200)
          : "loop";
        addBlock({
          function_name: funcName,
          block_id: loopCondId,
          block_type: "loop_condition",
          start_line: line + 1,
          end_line: line + 1,
          condition_expr: loopCondExpr,
        });
        addStatementToBlock(
          loopCondId,
          "loop",
          line + 1,
          node.getText(sourceFile).substring(0, 200),
        );
        addEdge({
          function_name: funcName,
          source_block_id: currentId,
          target_block_id: loopCondId,
          edge_type: "normal",
        });

        const bodyId = getNextBlockId();
        addBlock({
          function_name: funcName,
          block_id: bodyId,
          block_type: "loop_body",
          start_line: line + 1,
          end_line: line + 1,
          condition_expr: null,
        });
        addEdge({
          function_name: funcName,
          source_block_id: loopCondId,
          target_block_id: bodyId,
          edge_type: "true",
        });

        let bodyExitId = bodyId;
        if (node.statement) {
          bodyExitId = processNode(node.statement, bodyId, depth + 1);
        }
        if (bodyExitId) {
          addEdge({
            function_name: funcName,
            source_block_id: bodyExitId,
            target_block_id: loopCondId,
            edge_type: "back_edge",
          });
        }

        const afterLoopId = getNextBlockId();
        addBlock({
          function_name: funcName,
          block_id: afterLoopId,
          block_type: "merge",
          start_line: line + 1,
          end_line: line + 1,
          condition_expr: null,
        });
        addEdge({
          function_name: funcName,
          source_block_id: loopCondId,
          target_block_id: afterLoopId,
          edge_type: "false",
        });
        return afterLoopId;
      } else if (kind === "ReturnStatement") {
        const retId = getNextBlockId();
        const retLine = line + 1;
        addBlock({
          function_name: funcName,
          block_id: retId,
          block_type: "return",
          start_line: retLine,
          end_line: retLine,
          condition_expr: null,
        });
        addStatementToBlock(
          retId,
          "return",
          retLine,
          node.getText(sourceFile).substring(0, 200),
        );
        addEdge({
          function_name: funcName,
          source_block_id: currentId,
          target_block_id: retId,
          edge_type: "normal",
        });
        addEdge({
          function_name: funcName,
          source_block_id: retId,
          target_block_id: exitId,
          edge_type: "normal",
        });
        return null;
      } else if (kind === "TryStatement") {
        const tryId = getNextBlockId();
        const tryEndPos = node.tryBlock
          ? node.tryBlock.getEnd()
          : node.getEnd();
        const tryEndLine =
          sourceFile.getLineAndCharacterOfPosition(tryEndPos).line + 1;
        addBlock({
          function_name: funcName,
          block_id: tryId,
          block_type: "try",
          start_line: line + 1,
          end_line: tryEndLine,
          condition_expr: null,
        });
        addStatementToBlock(tryId, "try", line + 1, "try");
        addEdge({
          function_name: funcName,
          source_block_id: currentId,
          target_block_id: tryId,
          edge_type: "normal",
        });

        let tryBodyExitId = tryId;
        if (node.tryBlock) {
          const tryBlockId = getNextBlockId();
          addBlock({
            function_name: funcName,
            block_id: tryBlockId,
            block_type: "basic",
            start_line: line + 1,
            end_line: line + 1,
            condition_expr: null,
          });
          addEdge({
            function_name: funcName,
            source_block_id: tryId,
            target_block_id: tryBlockId,
            edge_type: "normal",
          });
          tryBodyExitId = processNode(node.tryBlock, tryBlockId, depth + 1);
        }

        const mergeId = getNextBlockId();
        addBlock({
          function_name: funcName,
          block_id: mergeId,
          block_type: "merge",
          start_line: line + 1,
          end_line: line + 1,
          condition_expr: null,
        });

        if (tryBodyExitId) {
          addEdge({
            function_name: funcName,
            source_block_id: tryBodyExitId,
            target_block_id: mergeId,
            edge_type: "normal",
          });
        }

        if (node.catchClause) {
          const catchId = getNextBlockId();
          const catchStartPos = node.catchClause.getStart(sourceFile);
          const catchStartLine =
            sourceFile.getLineAndCharacterOfPosition(catchStartPos).line + 1;
          const catchEndPos = node.catchClause.block
            ? node.catchClause.block.getEnd()
            : node.catchClause.getEnd();
          const catchEndLine =
            sourceFile.getLineAndCharacterOfPosition(catchEndPos).line + 1;
          addBlock({
            function_name: funcName,
            block_id: catchId,
            block_type: "except",
            start_line: catchStartLine,
            end_line: catchEndLine,
            condition_expr: null,
          });
          addStatementToBlock(catchId, "catch", catchStartLine, "catch");
          addEdge({
            function_name: funcName,
            source_block_id: tryId,
            target_block_id: catchId,
            edge_type: "exception",
          });

          let catchBodyExitId = catchId;
          if (node.catchClause.block) {
            const catchBlockId = getNextBlockId();
            addBlock({
              function_name: funcName,
              block_id: catchBlockId,
              block_type: "basic",
              start_line: line + 1,
              end_line: line + 1,
              condition_expr: null,
            });
            addEdge({
              function_name: funcName,
              source_block_id: catchId,
              target_block_id: catchBlockId,
              edge_type: "normal",
            });
            catchBodyExitId = processNode(
              node.catchClause.block,
              catchBlockId,
              depth + 1,
            );
          }
          if (catchBodyExitId) {
            addEdge({
              function_name: funcName,
              source_block_id: catchBodyExitId,
              target_block_id: mergeId,
              edge_type: "normal",
            });
          }
        }

        if (node.finallyBlock) {
          const finallyId = getNextBlockId();
          const finallyEndPos = node.finallyBlock.getEnd();
          const finallyEndLine =
            sourceFile.getLineAndCharacterOfPosition(finallyEndPos).line + 1;
          addBlock({
            function_name: funcName,
            block_id: finallyId,
            block_type: "finally",
            start_line: line + 1,
            end_line: finallyEndLine,
            condition_expr: null,
          });
          addEdge({
            function_name: funcName,
            source_block_id: mergeId,
            target_block_id: finallyId,
            edge_type: "normal",
          });

          let finallyBodyExitId = finallyId;
          if (node.finallyBlock) {
            const finallyBlockId = getNextBlockId();
            addBlock({
              function_name: funcName,
              block_id: finallyBlockId,
              block_type: "basic",
              start_line: line + 1,
              end_line: line + 1,
              condition_expr: null,
            });
            addEdge({
              function_name: funcName,
              source_block_id: finallyId,
              target_block_id: finallyBlockId,
              edge_type: "normal",
            });
            finallyBodyExitId = processNode(
              node.finallyBlock,
              finallyBlockId,
              depth + 1,
            );
          }
          return finallyBodyExitId || finallyId;
        }

        return mergeId;
      } else if (kind === "SwitchStatement") {
        const switchId = getNextBlockId();
        const switchExpr = node.expression
          ? node.expression.getText(sourceFile).substring(0, 200)
          : "switch";
        addBlock({
          function_name: funcName,
          block_id: switchId,
          block_type: "condition",
          start_line: line + 1,
          end_line: line + 1,
          condition_expr: switchExpr,
        });
        addStatementToBlock(switchId, "switch", line + 1, switchExpr);
        addEdge({
          function_name: funcName,
          source_block_id: currentId,
          target_block_id: switchId,
          edge_type: "normal",
        });

        const mergeId = getNextBlockId();
        addBlock({
          function_name: funcName,
          block_id: mergeId,
          block_type: "merge",
          start_line: line + 1,
          end_line: line + 1,
          condition_expr: null,
        });

        if (node.caseBlock && node.caseBlock.clauses) {
          let lastCaseExitId = null;

          for (const clause of node.caseBlock.clauses) {
            const clauseKind = ts.SyntaxKind[clause.kind];
            const isDefault = clauseKind === "DefaultClause";

            const caseBlockId = getNextBlockId();
            addBlock({
              function_name: funcName,
              block_id: caseBlockId,
              block_type: "basic",
              start_line: line + 1,
              end_line: line + 1,
              condition_expr: null,
            });

            if (lastCaseExitId) {
              addEdge({
                function_name: funcName,
                source_block_id: lastCaseExitId,
                target_block_id: caseBlockId,
                edge_type: "fallthrough",
              });
            }
            addEdge({
              function_name: funcName,
              source_block_id: switchId,
              target_block_id: caseBlockId,
              edge_type: isDefault ? "default" : "case",
            });

            let caseExitId = caseBlockId;
            if (clause.statements && clause.statements.length > 0) {
              for (const stmt of clause.statements) {
                if (caseExitId) {
                  caseExitId = processNode(stmt, caseExitId, depth + 1);
                }
              }
            }

            const hasBreak =
              clause.statements &&
              clause.statements.some(
                (s) => ts.SyntaxKind[s.kind] === "BreakStatement",
              );

            if (hasBreak) {
              lastCaseExitId = null;
            } else {
              lastCaseExitId = caseExitId;
            }
          }

          if (lastCaseExitId) {
            addEdge({
              function_name: funcName,
              source_block_id: lastCaseExitId,
              target_block_id: mergeId,
              edge_type: "normal",
            });
          }
        }

        return mergeId;
      } else if (kind === "BreakStatement") {
        const breakId = getNextBlockId();
        addBlock({
          function_name: funcName,
          block_id: breakId,
          block_type: "basic",
          start_line: line + 1,
          end_line: line + 1,
          condition_expr: null,
        });
        addStatementToBlock(breakId, "break", line + 1, "break");
        addEdge({
          function_name: funcName,
          source_block_id: currentId,
          target_block_id: breakId,
          edge_type: "normal",
        });
        return null;
      } else if (kind === "ThrowStatement") {
        const throwId = getNextBlockId();
        addBlock({
          function_name: funcName,
          block_id: throwId,
          block_type: "basic",
          start_line: line + 1,
          end_line: line + 1,
          condition_expr: null,
        });
        addStatementToBlock(
          throwId,
          "throw",
          line + 1,
          node.getText(sourceFile).substring(0, 200),
        );
        addEdge({
          function_name: funcName,
          source_block_id: currentId,
          target_block_id: throwId,
          edge_type: "normal",
        });
        addEdge({
          function_name: funcName,
          source_block_id: throwId,
          target_block_id: exitId,
          edge_type: "exception",
        });
        return null;
      } else if (kind.startsWith("Jsx")) {
        addStatementToBlock(
          currentId,
          kind,
          line + 1,
          node.getText(sourceFile).substring(0, 200),
        );
        let lastId = currentId;
        ts.forEachChild(node, (child) => {
          if (lastId) {
            lastId = processNode(child, lastId, depth + 1);
          }
        });
        return lastId;
      } else if (kind === "Block") {
        let lastId = currentId;
        ts.forEachChild(node, (child) => {
          if (lastId) {
            lastId = processNode(child, lastId, depth + 1);
          }
        });
        return lastId;
      } else {
        let lastId = currentId;
        ts.forEachChild(node, (child) => {
          if (lastId) {
            lastId = processNode(child, lastId, depth + 1);
          }
        });
        return lastId;
      }
    }

    let lastBlockId = entryId;
    if (funcNode.body) {
      if (funcNode.body.kind !== ts.SyntaxKind.Block) {
        lastBlockId = processNode(funcNode.body, entryId, 0);
      } else {
        ts.forEachChild(funcNode.body, (child) => {
          if (lastBlockId) {
            lastBlockId = processNode(child, lastBlockId, 0);
          }
        });
      }
    }

    if (lastBlockId) {
      addEdge({
        function_name: funcName,
        source_block_id: lastBlockId,
        target_block_id: exitId,
        edge_type: "normal",
      });
    }

    return {
      function_name: funcName,
      blocks: blocks,
      edges: edges,
    };
  }

  function visit(node, depth = 0, parent = null) {
    if (depth > 500 || !node) return;

    const kind = ts.SyntaxKind[node.kind];

    if (kind === "ClassDeclaration") {
      const className = node.name
        ? node.name.text || node.name.escapedText || "UnknownClass"
        : "UnknownClass";
      class_stack.push(className);
      ts.forEachChild(node, (child) => visit(child, depth + 1, node));
      class_stack.pop();
      return;
    }

    if (
      kind === "FunctionDeclaration" ||
      kind === "MethodDeclaration" ||
      kind === "ArrowFunction" ||
      kind === "FunctionExpression" ||
      kind === "Constructor" ||
      kind === "GetAccessor" ||
      kind === "SetAccessor"
    ) {
      const cfg = buildFunctionCFG(node, class_stack, parent);
      if (cfg) functionCFGs.push(cfg);
    }

    if (kind === "PropertyDeclaration" && node.initializer) {
      const initKind = ts.SyntaxKind[node.initializer.kind];
      if (initKind === "ArrowFunction" || initKind === "FunctionExpression") {
        const cfg = buildFunctionCFG(node.initializer, class_stack, node);
        if (cfg) functionCFGs.push(cfg);
      }
    }

    ts.forEachChild(node, (child) => visit(child, depth + 1, node));
  }

  visit(sourceFile);

  return functionCFGs;
}
