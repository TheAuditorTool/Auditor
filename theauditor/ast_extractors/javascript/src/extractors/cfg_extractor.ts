import * as ts from "typescript";
import type {
  CFGBlock,
  CFGEdge,
  CFGBlockStatement,
  Function as IFunction,
} from "../schema.js";

interface ExtractCFGResult {
  cfg_blocks: CFGBlock[];
  cfg_edges: CFGEdge[];
  cfg_block_statements: CFGBlockStatement[];
}

interface CFGBuildContext {
  blocks: CFGBlock[];
  edges: CFGEdge[];
  statements: CFGBlockStatement[];
  functionId: string;
  blockCounter: number;
  currentBlockId: string | null;
  finallyStack: string[];
}

const SKIP_NODE_KINDS = new Set([
  ts.SyntaxKind.InterfaceDeclaration,
  ts.SyntaxKind.TypeAliasDeclaration,
  ts.SyntaxKind.ImportDeclaration,
  ts.SyntaxKind.ExportDeclaration,
  ts.SyntaxKind.ModuleDeclaration,
  ts.SyntaxKind.NamespaceExportDeclaration,
]);

export function extractCFG(
  sourceFile: ts.SourceFile,
  functions: IFunction[],
  filePath: string,
): ExtractCFGResult {
  const cfg_blocks: CFGBlock[] = [];
  const cfg_edges: CFGEdge[] = [];
  const cfg_block_statements: CFGBlockStatement[] = [];

  for (const func of functions) {
    const functionNode = findFunctionNode(sourceFile, func.name, func.line);
    if (!functionNode) continue;

    const functionId = `${filePath}:${func.name}:${func.line}`;
    const ctx: CFGBuildContext = {
      blocks: [],
      edges: [],
      statements: [],
      functionId,
      blockCounter: 0,
      currentBlockId: null,
      finallyStack: [],
    };

    const entryBlockId = createBlock(ctx, "entry", func.line, func.line);
    ctx.currentBlockId = entryBlockId;

    const body = getFunctionBody(functionNode);
    if (body) {
      if (ts.isBlock(body)) {
        processBlock(body, sourceFile, ctx);
      } else {
        processStatement(body, sourceFile, ctx);
      }
    }

    const exitBlockId = createBlock(ctx, "exit", null, null);
    if (ctx.currentBlockId) {
      addEdge(ctx, ctx.currentBlockId, exitBlockId, "fallthrough", null);
    }

    cfg_blocks.push(...ctx.blocks);
    cfg_edges.push(...ctx.edges);
    cfg_block_statements.push(...ctx.statements);
  }

  return { cfg_blocks, cfg_edges, cfg_block_statements };
}

function findFunctionNode(
  sourceFile: ts.SourceFile,
  name: string,
  line: number,
): ts.FunctionLikeDeclaration | null {
  let result: ts.FunctionLikeDeclaration | null = null;

  function visit(node: ts.Node): void {
    if (result) return;

    const nodeLine =
      sourceFile.getLineAndCharacterOfPosition(node.getStart()).line + 1;

    if (
      ts.isFunctionDeclaration(node) ||
      ts.isFunctionExpression(node) ||
      ts.isArrowFunction(node) ||
      ts.isMethodDeclaration(node)
    ) {
      if (nodeLine === line) {
        let nodeName = "";
        if (ts.isFunctionDeclaration(node) && node.name) {
          nodeName = node.name.text;
        } else if (ts.isMethodDeclaration(node) && ts.isIdentifier(node.name)) {
          nodeName = node.name.text;
        }

        if (nodeName === name || nodeLine === line) {
          result = node;
          return;
        }
      }
    }

    ts.forEachChild(node, visit);
  }

  visit(sourceFile);
  return result;
}

function getFunctionBody(
  node: ts.FunctionLikeDeclaration,
): ts.Block | ts.Expression | undefined {
  return node.body;
}

function createBlock(
  ctx: CFGBuildContext,
  blockType: string,
  startLine: number | null,
  endLine: number | null,
): string {
  const blockId = `block_${ctx.blockCounter++}`;
  ctx.blocks.push({
    function_id: ctx.functionId,
    block_id: blockId,
    block_type: blockType,
    start_line: startLine,
    end_line: endLine,
  });
  return blockId;
}

function addEdge(
  ctx: CFGBuildContext,
  fromBlock: string,
  toBlock: string,
  edgeType: string,
  condition: string | null,
): void {
  ctx.edges.push({
    function_id: ctx.functionId,
    from_block: fromBlock,
    to_block: toBlock,
    edge_type: edgeType,
    condition: condition,
  });
}

function addStatement(
  ctx: CFGBuildContext,
  statementType: string,
  line: number,
  text: string,
): void {
  if (ctx.currentBlockId) {
    ctx.statements.push({
      function_id: ctx.functionId,
      block_id: ctx.currentBlockId,
      statement_type: statementType,
      line: line,
      text: truncateText(text, 1000),
    });
  }
}

function truncateText(text: string, maxLength: number): string {
  if (!text || text.length <= maxLength) return text;
  return text.slice(0, maxLength) + "...";
}

function getNodeText(node: ts.Node, sourceFile: ts.SourceFile): string {
  if (isJsxNode(node)) {
    return flattenJsx(node, sourceFile);
  }
  return truncateText(node.getText(sourceFile), 1000);
}

function isJsxNode(node: ts.Node): boolean {
  return (
    ts.isJsxElement(node) ||
    ts.isJsxSelfClosingElement(node) ||
    ts.isJsxFragment(node) ||
    ts.isJsxExpression(node)
  );
}

const DANGEROUS_JSX_PROPS = new Set([
  "dangerouslySetInnerHTML",
  "href",
  "src",
  "action",
  "formAction",
  "onClick",
  "onSubmit",
  "onLoad",
  "onError",
]);

function extractDangerousProps(
  attrs: ts.JsxAttributes,
  sourceFile: ts.SourceFile,
): string {
  const dangerous: string[] = [];
  for (const prop of attrs.properties) {
    if (ts.isJsxAttribute(prop) && prop.name) {
      const propName = prop.name.getText(sourceFile);
      if (DANGEROUS_JSX_PROPS.has(propName)) {
        const value = prop.initializer
          ? prop.initializer.getText(sourceFile).substring(0, 100)
          : "true";
        dangerous.push(`${propName}=${value}`);
      }
    }
  }
  return dangerous.length > 0 ? ` ${dangerous.join(" ")}` : "";
}

function flattenJsx(node: ts.Node, sourceFile: ts.SourceFile): string {
  if (ts.isJsxElement(node)) {
    const tagName = node.openingElement.tagName.getText(sourceFile);
    const dangerousProps = extractDangerousProps(
      node.openingElement.attributes,
      sourceFile,
    );
    const childCount = node.children.length;
    return `<${tagName}${dangerousProps}>[${childCount} children]</${tagName}>`;
  }
  if (ts.isJsxSelfClosingElement(node)) {
    const tagName = node.tagName.getText(sourceFile);
    const dangerousProps = extractDangerousProps(node.attributes, sourceFile);
    return `<${tagName}${dangerousProps} />`;
  }
  if (ts.isJsxFragment(node)) {
    return `<>[${node.children.length} children]</>`;
  }
  if (ts.isJsxExpression(node)) {
    return "{...}";
  }
  return "<JSX>";
}

function processBlock(
  block: ts.Block,
  sourceFile: ts.SourceFile,
  ctx: CFGBuildContext,
): void {
  for (const statement of block.statements) {
    if (SKIP_NODE_KINDS.has(statement.kind)) {
      continue;
    }
    processStatement(statement, sourceFile, ctx);
  }
}

function processStatement(
  node: ts.Node,
  sourceFile: ts.SourceFile,
  ctx: CFGBuildContext,
): void {
  if (SKIP_NODE_KINDS.has(node.kind)) {
    return;
  }

  const line =
    sourceFile.getLineAndCharacterOfPosition(node.getStart()).line + 1;

  if (ts.isIfStatement(node)) {
    processIfStatement(node, sourceFile, ctx);
  } else if (
    ts.isForStatement(node) ||
    ts.isForInStatement(node) ||
    ts.isForOfStatement(node)
  ) {
    processForStatement(node, sourceFile, ctx);
  } else if (ts.isWhileStatement(node)) {
    processWhileStatement(node, sourceFile, ctx);
  } else if (ts.isDoStatement(node)) {
    processDoWhileStatement(node, sourceFile, ctx);
  } else if (ts.isSwitchStatement(node)) {
    processSwitchStatement(node, sourceFile, ctx);
  } else if (ts.isTryStatement(node)) {
    processTryStatement(node, sourceFile, ctx);
  } else if (ts.isReturnStatement(node)) {
    addStatement(ctx, "return", line, getNodeText(node, sourceFile));
    if (ctx.finallyStack.length > 0 && ctx.currentBlockId) {
      const finallyBlockId = ctx.finallyStack[ctx.finallyStack.length - 1];
      addEdge(
        ctx,
        ctx.currentBlockId,
        finallyBlockId,
        "return_through_finally",
        null,
      );
    }
    ctx.currentBlockId = null;
  } else if (ts.isThrowStatement(node)) {
    addStatement(ctx, "throw", line, getNodeText(node, sourceFile));
    if (ctx.finallyStack.length > 0 && ctx.currentBlockId) {
      const finallyBlockId = ctx.finallyStack[ctx.finallyStack.length - 1];
      addEdge(
        ctx,
        ctx.currentBlockId,
        finallyBlockId,
        "throw_through_finally",
        null,
      );
    }
    ctx.currentBlockId = null;
  } else if (ts.isBreakStatement(node)) {
    addStatement(ctx, "break", line, getNodeText(node, sourceFile));
    ctx.currentBlockId = null;
  } else if (ts.isContinueStatement(node)) {
    addStatement(ctx, "continue", line, getNodeText(node, sourceFile));
    ctx.currentBlockId = null;
  } else if (ts.isBlock(node)) {
    processBlock(node, sourceFile, ctx);
  } else if (ts.isExpressionStatement(node)) {
    addStatement(
      ctx,
      "expression",
      line,
      getNodeText(node.expression, sourceFile),
    );
  } else if (ts.isVariableStatement(node)) {
    addStatement(ctx, "variable", line, getNodeText(node, sourceFile));
  } else {
    addStatement(ctx, "statement", line, getNodeText(node, sourceFile));
  }
}

function processIfStatement(
  node: ts.IfStatement,
  sourceFile: ts.SourceFile,
  ctx: CFGBuildContext,
): void {
  const line =
    sourceFile.getLineAndCharacterOfPosition(node.getStart()).line + 1;
  const conditionText = getNodeText(node.expression, sourceFile);

  addStatement(ctx, "condition", line, `if (${conditionText})`);

  const conditionBlockId = ctx.currentBlockId;

  const thenBlockId = createBlock(ctx, "then", line, null);
  if (conditionBlockId) {
    addEdge(ctx, conditionBlockId, thenBlockId, "true", conditionText);
  }
  ctx.currentBlockId = thenBlockId;
  processStatement(node.thenStatement, sourceFile, ctx);
  const afterThenBlockId = ctx.currentBlockId;

  let afterElseBlockId: string | null = null;
  if (node.elseStatement) {
    const elseBlockId = createBlock(ctx, "else", line, null);
    if (conditionBlockId) {
      addEdge(
        ctx,
        conditionBlockId,
        elseBlockId,
        "false",
        `!(${conditionText})`,
      );
    }
    ctx.currentBlockId = elseBlockId;
    processStatement(node.elseStatement, sourceFile, ctx);
    afterElseBlockId = ctx.currentBlockId;
  }

  const mergeBlockId = createBlock(ctx, "merge", null, null);
  if (afterThenBlockId) {
    addEdge(ctx, afterThenBlockId, mergeBlockId, "fallthrough", null);
  }
  if (node.elseStatement) {
    if (afterElseBlockId) {
      addEdge(ctx, afterElseBlockId, mergeBlockId, "fallthrough", null);
    }
  } else if (conditionBlockId) {
    addEdge(
      ctx,
      conditionBlockId,
      mergeBlockId,
      "false",
      `!(${conditionText})`,
    );
  }
  ctx.currentBlockId = mergeBlockId;
}

function processForStatement(
  node: ts.ForStatement | ts.ForInStatement | ts.ForOfStatement,
  sourceFile: ts.SourceFile,
  ctx: CFGBuildContext,
): void {
  const line =
    sourceFile.getLineAndCharacterOfPosition(node.getStart()).line + 1;

  const headerBlockId = createBlock(ctx, "loop_header", line, null);
  if (ctx.currentBlockId) {
    addEdge(ctx, ctx.currentBlockId, headerBlockId, "fallthrough", null);
  }

  let conditionText = "loop";
  if (ts.isForStatement(node) && node.condition) {
    conditionText = getNodeText(node.condition, sourceFile);
  } else if (ts.isForInStatement(node) || ts.isForOfStatement(node)) {
    conditionText = getNodeText(node.expression, sourceFile);
  }

  addStatement(ctx, "loop_condition", line, `for (${conditionText})`);

  const bodyBlockId = createBlock(ctx, "loop_body", line, null);
  addEdge(ctx, headerBlockId, bodyBlockId, "true", conditionText);

  ctx.currentBlockId = bodyBlockId;
  processStatement(node.statement, sourceFile, ctx);
  const afterBodyBlockId = ctx.currentBlockId;

  if (afterBodyBlockId) {
    addEdge(ctx, afterBodyBlockId, headerBlockId, "back_edge", null);
  }

  const exitBlockId = createBlock(ctx, "loop_exit", null, null);
  addEdge(ctx, headerBlockId, exitBlockId, "false", `!(${conditionText})`);
  ctx.currentBlockId = exitBlockId;
}

function processWhileStatement(
  node: ts.WhileStatement,
  sourceFile: ts.SourceFile,
  ctx: CFGBuildContext,
): void {
  const line =
    sourceFile.getLineAndCharacterOfPosition(node.getStart()).line + 1;
  const conditionText = getNodeText(node.expression, sourceFile);

  const headerBlockId = createBlock(ctx, "loop_header", line, null);
  if (ctx.currentBlockId) {
    addEdge(ctx, ctx.currentBlockId, headerBlockId, "fallthrough", null);
  }

  addStatement(ctx, "loop_condition", line, `while (${conditionText})`);

  const bodyBlockId = createBlock(ctx, "loop_body", line, null);
  addEdge(ctx, headerBlockId, bodyBlockId, "true", conditionText);

  ctx.currentBlockId = bodyBlockId;
  processStatement(node.statement, sourceFile, ctx);
  const afterBodyBlockId = ctx.currentBlockId;

  if (afterBodyBlockId) {
    addEdge(ctx, afterBodyBlockId, headerBlockId, "back_edge", null);
  }

  const exitBlockId = createBlock(ctx, "loop_exit", null, null);
  addEdge(ctx, headerBlockId, exitBlockId, "false", `!(${conditionText})`);
  ctx.currentBlockId = exitBlockId;
}

function processDoWhileStatement(
  node: ts.DoStatement,
  sourceFile: ts.SourceFile,
  ctx: CFGBuildContext,
): void {
  const line =
    sourceFile.getLineAndCharacterOfPosition(node.getStart()).line + 1;
  const conditionText = getNodeText(node.expression, sourceFile);

  const bodyBlockId = createBlock(ctx, "loop_body", line, null);
  if (ctx.currentBlockId) {
    addEdge(ctx, ctx.currentBlockId, bodyBlockId, "fallthrough", null);
  }

  ctx.currentBlockId = bodyBlockId;
  processStatement(node.statement, sourceFile, ctx);
  const afterBodyBlockId = ctx.currentBlockId;

  const conditionBlockId = createBlock(ctx, "loop_condition", line, null);
  if (afterBodyBlockId) {
    addEdge(ctx, afterBodyBlockId, conditionBlockId, "fallthrough", null);
  }

  addStatement(ctx, "loop_condition", line, `while (${conditionText})`);

  addEdge(ctx, conditionBlockId, bodyBlockId, "true", conditionText);

  const exitBlockId = createBlock(ctx, "loop_exit", null, null);
  addEdge(ctx, conditionBlockId, exitBlockId, "false", `!(${conditionText})`);
  ctx.currentBlockId = exitBlockId;
}

function processSwitchStatement(
  node: ts.SwitchStatement,
  sourceFile: ts.SourceFile,
  ctx: CFGBuildContext,
): void {
  const line =
    sourceFile.getLineAndCharacterOfPosition(node.getStart()).line + 1;
  const switchExpr = getNodeText(node.expression, sourceFile);

  addStatement(ctx, "switch", line, `switch (${switchExpr})`);
  const switchBlockId = ctx.currentBlockId;

  const exitBlockId = createBlock(ctx, "switch_exit", null, null);

  let previousCaseBlockId: string | null = null;

  for (const clause of node.caseBlock.clauses) {
    const clauseLine =
      sourceFile.getLineAndCharacterOfPosition(clause.getStart()).line + 1;
    let caseBlockId: string;
    let caseCondition: string | null = null;

    if (ts.isCaseClause(clause)) {
      const caseExpr = getNodeText(clause.expression, sourceFile);
      caseBlockId = createBlock(ctx, "case", clauseLine, null);
      caseCondition = `${switchExpr} === ${caseExpr}`;
    } else {
      caseBlockId = createBlock(ctx, "default", clauseLine, null);
    }

    if (switchBlockId) {
      addEdge(ctx, switchBlockId, caseBlockId, "case", caseCondition);
    }
    if (previousCaseBlockId) {
      addEdge(ctx, previousCaseBlockId, caseBlockId, "fallthrough", null);
    }

    ctx.currentBlockId = caseBlockId;

    for (const statement of clause.statements) {
      processStatement(statement, sourceFile, ctx);
    }

    const lastStatement = clause.statements[clause.statements.length - 1];
    if (lastStatement && ts.isBreakStatement(lastStatement)) {
      if (ctx.currentBlockId) {
        addEdge(ctx, ctx.currentBlockId, exitBlockId, "break", null);
      }
      previousCaseBlockId = null;
    } else {
      previousCaseBlockId = ctx.currentBlockId;
    }
  }

  if (previousCaseBlockId) {
    addEdge(ctx, previousCaseBlockId, exitBlockId, "fallthrough", null);
  }

  ctx.currentBlockId = exitBlockId;
}

function processTryStatement(
  node: ts.TryStatement,
  sourceFile: ts.SourceFile,
  ctx: CFGBuildContext,
): void {
  const line =
    sourceFile.getLineAndCharacterOfPosition(node.getStart()).line + 1;

  addStatement(ctx, "try", line, "try");

  let finallyBlockId: string | null = null;
  if (node.finallyBlock) {
    const finallyLine =
      sourceFile.getLineAndCharacterOfPosition(node.finallyBlock.getStart())
        .line + 1;
    finallyBlockId = createBlock(ctx, "finally", finallyLine, null);
    ctx.finallyStack.push(finallyBlockId);
  }

  const tryBlockId = createBlock(ctx, "try", line, null);
  if (ctx.currentBlockId) {
    addEdge(ctx, ctx.currentBlockId, tryBlockId, "fallthrough", null);
  }

  ctx.currentBlockId = tryBlockId;
  processBlock(node.tryBlock, sourceFile, ctx);
  const afterTryBlockId = ctx.currentBlockId;

  const exitBlockId = createBlock(ctx, "try_exit", null, null);

  if (afterTryBlockId) {
    addEdge(ctx, afterTryBlockId, exitBlockId, "fallthrough", null);
  }

  if (node.catchClause) {
    const catchLine =
      sourceFile.getLineAndCharacterOfPosition(node.catchClause.getStart())
        .line + 1;
    const catchBlockId = createBlock(ctx, "catch", catchLine, null);

    addEdge(ctx, tryBlockId, catchBlockId, "exception", null);

    ctx.currentBlockId = catchBlockId;
    processBlock(node.catchClause.block, sourceFile, ctx);

    if (ctx.currentBlockId) {
      addEdge(ctx, ctx.currentBlockId, exitBlockId, "fallthrough", null);
    }
  }

  if (finallyBlockId) {
    ctx.finallyStack.pop();

    addEdge(ctx, exitBlockId, finallyBlockId, "finally", null);

    ctx.currentBlockId = finallyBlockId;
    processBlock(node.finallyBlock!, sourceFile, ctx);

    const afterFinallyExitId = createBlock(ctx, "finally_exit", null, null);
    if (ctx.currentBlockId) {
      addEdge(ctx, ctx.currentBlockId, afterFinallyExitId, "fallthrough", null);
    }
    ctx.currentBlockId = afterFinallyExitId;
  } else {
    ctx.currentBlockId = exitBlockId;
  }
}

export { ExtractCFGResult };
