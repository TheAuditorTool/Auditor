import * as path from "path";
import type * as ts from "typescript";
import type {
  CallSymbol as ICallSymbol,
  Assignment as IAssignment,
  AssignmentSourceVar as IAssignmentSourceVar,
  FunctionCallArg as IFunctionCallArg,
  FunctionReturn as IFunctionReturn,
  ReturnSourceVar as IReturnSourceVar,
  Function as IFunction,
  Class as IClass,
} from "../schema";

export function extractCalls(
  sourceFile: ts.SourceFile,
  checker: ts.TypeChecker | null,
  ts: typeof import("typescript"),
  filePath: string,
  functions: IFunction[],
  classes: IClass[],
  scopeMap: Map<number, string>,
  projectRoot?: string,
): ICallSymbol[] {
  const calls: ICallSymbol[] = [];
  const seen = new Map<string, boolean>();

  function buildName(node: ts.Node): string {
    if (!node) return "";
    const kind = ts.SyntaxKind[node.kind];
    if (kind === "Identifier") {
      const id = node as ts.Identifier;
      return id.text || id.escapedText?.toString() || "";
    } else if (kind === "ThisKeyword") {
      return "this";
    } else if (kind === "PropertyAccessExpression") {
      const pae = node as ts.PropertyAccessExpression;
      const left = buildName(pae.expression);
      const right = pae.name
        ? pae.name.text || pae.name.escapedText?.toString() || ""
        : "";
      return left && right ? left + "." + right : left || right;
    } else if (kind === "CallExpression") {
      const ce = node as ts.CallExpression;
      const calleeName = buildName(ce.expression);
      return calleeName ? calleeName + "()" : "";
    } else if (kind === "NewExpression") {
      const ne = node as ts.NewExpression;
      if (ne.expression) {
        const className = buildName(ne.expression);
        return className ? "new " + className + "()" : "";
      }
      return "";
    } else if (
      kind === "ParenthesizedExpression" ||
      kind === "AsExpression" ||
      kind === "TypeAssertionExpression"
    ) {
      const expr = (node as any).expression;
      return expr ? buildName(expr) : "";
    } else if (kind === "ElementAccessExpression") {
      const eae = node as ts.ElementAccessExpression;
      const objName = buildName(eae.expression);
      return objName ? objName + "[" : "[";
    }
    return "";
  }

  function traverse(node: ts.Node): void {
    if (!node) return;
    const kind = ts.SyntaxKind[node.kind];
    const { line, character } = sourceFile.getLineAndCharacterOfPosition(
      node.getStart(sourceFile),
    );

    if (kind === "CallExpression") {
      const callExpr = node as ts.CallExpression;
      let resolvedName = "unknown";
      let originalText = "";
      let definedIn: string | null = null;
      let callType = "call";

      originalText = callExpr.expression.getText(sourceFile);

      if (checker) {
        let symbol = checker.getSymbolAtLocation(callExpr.expression);

        if (!symbol && ts.isPropertyAccessExpression(callExpr.expression)) {
          symbol = checker.getSymbolAtLocation(callExpr.expression.name);
        }

        if (symbol) {
          resolvedName = checker.getFullyQualifiedName(symbol);

          const declarations = symbol.getDeclarations();
          if (declarations && declarations.length > 0) {
            const declSourceFile = declarations[0].getSourceFile();
            if (projectRoot) {
              definedIn = path
                .relative(projectRoot, declSourceFile.fileName)
                .replace(/\\/g, "/");
            } else {
              definedIn = declSourceFile.fileName;
            }
          }
        } else {
          const builtName = buildName(callExpr.expression);
          resolvedName = builtName || originalText || "unknown";
        }
      } else {
        const builtName = buildName(callExpr.expression);
        resolvedName = builtName || originalText || "unknown";
      }

      const args = callExpr.arguments.map((arg) =>
        arg.getText(sourceFile).substring(0, 500),
      );

      const callerFunction = scopeMap.get(line + 1) || "<module>";

      const key = `${resolvedName}|${line + 1}|${character}|${callType}`;
      if (!seen.has(key)) {
        seen.set(key, true);
        calls.push({
          line: line + 1,
          column: character,
          name: resolvedName,
          original_text: originalText,
          defined_in: definedIn,
          caller_function: callerFunction,
          arguments: args,
          type: callType,
        });
      }
    } else if (kind === "PropertyAccessExpression") {
      const pae = node as ts.PropertyAccessExpression;
      let fullName = "";

      fullName = buildName(pae);

      if (fullName) {
        let dbType = "property";
        const sinkPatterns = [
          "res.send",
          "res.render",
          "res.json",
          "response.write",
          "innerHTML",
          "outerHTML",
          "exec",
          "eval",
          "system",
          "spawn",
        ];
        for (const sink of sinkPatterns) {
          if (fullName.includes(sink)) {
            dbType = "call";
            break;
          }
        }

        const callerFunction = scopeMap.get(line + 1) || "<module>";
        const key = `${fullName}|${line + 1}|${character}|${dbType}`;
        if (!seen.has(key)) {
          seen.set(key, true);
          calls.push({
            line: line + 1,
            column: character,
            name: fullName,
            original_text: fullName,
            defined_in: null,
            caller_function: callerFunction,
            type: dbType,
          });
        }
      }
    }

    ts.forEachChild(node, traverse);
  }

  traverse(sourceFile);

  if (process.env.THEAUDITOR_DEBUG) {
    console.error(
      `[DEBUG JS] extractCalls: Extracted ${calls.length} calls/properties from ${sourceFile.fileName}`,
    );
    if (calls.length > 0 && calls.length <= 5) {
      calls.forEach((s) =>
        console.error(`[DEBUG JS]   - ${s.name} (${s.type}) at line ${s.line}`),
      );
    }
  }

  return calls;
}

interface ExtractAssignmentsResult {
  assignments: IAssignment[];
  assignment_source_vars: IAssignmentSourceVar[];
}

function extractVarsFromNode(
  node: ts.Node,
  sourceFile: ts.SourceFile,
  ts: typeof import("typescript"),
): string[] {
  const vars: string[] = [];
  const seen = new Set<string>();

  function visit(n: ts.Node): void {
    if (!n) return;
    const kind = ts.SyntaxKind[n.kind];

    if (n.kind === ts.SyntaxKind.Identifier) {
      const id = n as ts.Identifier;
      const text = id.text || id.escapedText?.toString();
      if (text && !seen.has(text)) {
        vars.push(text);
        seen.add(text);
      }
    }

    if (n.kind === ts.SyntaxKind.PropertyAccessExpression) {
      const fullText = n.getText(sourceFile);
      if (fullText && !seen.has(fullText)) {
        vars.push(fullText);
        seen.add(fullText);
      }
    }

    if (n.kind === ts.SyntaxKind.ElementAccessExpression) {
      const fullText = n.getText(sourceFile);
      if (fullText && !seen.has(fullText)) {
        vars.push(fullText);
        seen.add(fullText);
      }
    }

    if (n.kind === ts.SyntaxKind.ThisKeyword) {
      const fullText = "this";
      if (!seen.has(fullText)) {
        vars.push(fullText);
        seen.add(fullText);
      }
    }

    if (n.kind === ts.SyntaxKind.NewExpression) {
      const fullText = n.getText(sourceFile);
      if (fullText && !seen.has(fullText)) {
        vars.push(fullText);
        seen.add(fullText);
      }
    }

    if (
      kind === "ParenthesizedExpression" ||
      kind === "AsExpression" ||
      kind === "TypeAssertionExpression" ||
      kind === "NonNullExpression" ||
      kind === "ArrayLiteralExpression"
    ) {
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

export function extractAssignments(
  sourceFile: ts.SourceFile,
  ts: typeof import("typescript"),
  scopeMap: Map<number, string>,
  filePath: string,
): ExtractAssignmentsResult {
  const assignments: IAssignment[] = [];
  const assignment_source_vars: IAssignmentSourceVar[] = [];
  const visited = new Set<string>();

  function traverse(node: ts.Node, depth: number = 0): void {
    if (depth > 100 || !node) return;

    const nodeId = node.pos + "-" + node.kind;
    if (visited.has(nodeId)) return;
    visited.add(nodeId);

    const kind = ts.SyntaxKind[node.kind];

    if (kind === "VariableDeclaration") {
      const varDecl = node as ts.VariableDeclaration;
      const { line, character } = sourceFile.getLineAndCharacterOfPosition(
        node.getStart(sourceFile),
      );
      const inFunction = scopeMap.get(line + 1) || "global";

      const name = varDecl.name;
      const initializer = varDecl.initializer;

      if (name && initializer) {
        if (name.kind === ts.SyntaxKind.Identifier) {
          const id = name as ts.Identifier;
          const targetVar = id.text || id.escapedText?.toString();
          if (targetVar) {
            const sourceVars = extractVarsFromNode(initializer, sourceFile, ts);
            sourceVars.forEach((sourceVar, varIndex) => {
              assignment_source_vars.push({
                file: filePath,
                line: line + 1,
                target_var: targetVar,
                source_var: sourceVar,
                var_index: varIndex,
              });
            });
            assignments.push({
              file: filePath,
              target_var: targetVar,
              source_expr: initializer.getText(sourceFile).substring(0, 500),
              line: line + 1,
              col: character,
              in_function: inFunction,
              source_vars: sourceVars,
            });
          }
        } else if (name.kind === ts.SyntaxKind.ObjectBindingPattern) {
          const pattern = name as ts.ObjectBindingPattern;
          const sourceExprText = initializer
            .getText(sourceFile)
            .substring(0, 500);
          const sourceVars = extractVarsFromNode(initializer, sourceFile, ts);

          pattern.elements.forEach((elem) => {
            const bindingElem = elem as ts.BindingElement;
            if (
              bindingElem.name &&
              bindingElem.name.kind === ts.SyntaxKind.Identifier
            ) {
              const id = bindingElem.name as ts.Identifier;
              const targetVar = id.text || id.escapedText?.toString();
              if (!targetVar) return;

              sourceVars.forEach((sourceVar, varIndex) => {
                assignment_source_vars.push({
                  file: filePath,
                  line: line + 1,
                  target_var: targetVar,
                  source_var: sourceVar,
                  var_index: varIndex,
                });
              });

              assignments.push({
                file: filePath,
                target_var: targetVar,
                source_expr: sourceExprText,
                line: line + 1,
                col: character,
                in_function: inFunction,
                source_vars: sourceVars,
              });
            }
          });
        } else if (name.kind === ts.SyntaxKind.ArrayBindingPattern) {
          const pattern = name as ts.ArrayBindingPattern;
          const sourceExprText = initializer
            .getText(sourceFile)
            .substring(0, 500);
          const sourceVars = extractVarsFromNode(initializer, sourceFile, ts);

          pattern.elements.forEach((elem) => {
            if (
              elem.kind === ts.SyntaxKind.BindingElement &&
              (elem as ts.BindingElement).name &&
              (elem as ts.BindingElement).name.kind === ts.SyntaxKind.Identifier
            ) {
              const id = (elem as ts.BindingElement).name as ts.Identifier;
              const targetVar = id.text || id.escapedText?.toString();
              if (!targetVar) return;

              sourceVars.forEach((sourceVar, varIndex) => {
                assignment_source_vars.push({
                  file: filePath,
                  line: line + 1,
                  target_var: targetVar,
                  source_var: sourceVar,
                  var_index: varIndex,
                });
              });

              assignments.push({
                file: filePath,
                target_var: targetVar,
                source_expr: sourceExprText,
                line: line + 1,
                col: character,
                in_function: inFunction,
                source_vars: sourceVars,
              });
            }
          });
        }
      }
    } else if (kind === "BinaryExpression") {
      const binExpr = node as ts.BinaryExpression;
      if (
        binExpr.operatorToken &&
        binExpr.operatorToken.kind === ts.SyntaxKind.EqualsToken
      ) {
        const { line, character } = sourceFile.getLineAndCharacterOfPosition(
          node.getStart(sourceFile),
        );
        const inFunction = scopeMap.get(line + 1) || "global";

        const left = binExpr.left;
        const right = binExpr.right;

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
              var_index: varIndex,
            });
          });

          assignments.push({
            file: filePath,
            target_var: targetVar,
            source_expr: sourceExpr,
            line: line + 1,
            col: character,
            in_function: inFunction,
            source_vars: sourceVars,
          });
        }
      }
    }

    ts.forEachChild(node, (child) => traverse(child, depth + 1));
  }

  traverse(sourceFile);
  return { assignments, assignment_source_vars };
}

export function extractFunctionCallArgs(
  sourceFile: ts.SourceFile,
  checker: ts.TypeChecker | null,
  ts: typeof import("typescript"),
  scopeMap: Map<number, string>,
  functionParams: Map<string, Array<{ name: string }>>,
  projectRoot?: string,
): IFunctionCallArg[] {
  const calls: IFunctionCallArg[] = [];
  const visited = new Set<string>();

  function buildDottedName(node: ts.Node): string {
    if (!node) return "";
    const kind = ts.SyntaxKind[node.kind];
    if (kind === "Identifier") {
      const id = node as ts.Identifier;
      return id.text || id.escapedText?.toString() || "";
    }
    if (kind === "PropertyAccessExpression") {
      const pae = node as ts.PropertyAccessExpression;
      const left = buildDottedName(pae.expression);
      const right = pae.name
        ? pae.name.text || pae.name.escapedText?.toString() || ""
        : "";
      return left && right ? left + "." + right : left || right;
    }
    if (kind === "CallExpression") {
      const ce = node as ts.CallExpression;
      const callee = buildDottedName(ce.expression);
      if (callee) {
        return callee + "()";
      }
      return "";
    }
    return "";
  }

  function traverse(node: ts.Node, depth: number = 0): void {
    if (depth > 100 || !node) return;

    const nodeId = node.pos + "-" + node.kind;
    if (visited.has(nodeId)) return;

    if (node.kind === ts.SyntaxKind.CallExpression) {
      const callExpr = node as ts.CallExpression;
      if (callExpr.expression) {
        const exprKind = ts.SyntaxKind[callExpr.expression.kind];
        if (exprKind === "PropertyAccessExpression") {
          const pae = callExpr.expression as ts.PropertyAccessExpression;
          if (pae.expression) {
            const innerExprKind = ts.SyntaxKind[pae.expression.kind];
            if (innerExprKind === "CallExpression") {
              const innerNodeId =
                pae.expression.pos + "-" + pae.expression.kind;
              if (!visited.has(innerNodeId)) {
                traverse(pae.expression, depth + 1);
              }
            }
          }
        } else if (exprKind === "CallExpression") {
          const innerNodeId =
            callExpr.expression.pos + "-" + callExpr.expression.kind;
          if (!visited.has(innerNodeId)) {
            traverse(callExpr.expression, depth + 1);
          }
        }
      }
    }

    visited.add(nodeId);

    if (node.kind === ts.SyntaxKind.CallExpression) {
      const callExpr = node as ts.CallExpression;
      const { line } = sourceFile.getLineAndCharacterOfPosition(
        node.getStart(sourceFile),
      );
      const callerFunction = scopeMap.get(line + 1) || "global";

      let calleeName = "";
      if (callExpr.expression) {
        const exprKind = ts.SyntaxKind[callExpr.expression.kind];
        if (exprKind === "Identifier") {
          const id = callExpr.expression as ts.Identifier;
          calleeName = id.text || id.escapedText?.toString() || "";
        } else if (exprKind === "PropertyAccessExpression") {
          calleeName = buildDottedName(callExpr.expression);
        } else if (exprKind === "CallExpression") {
          calleeName = buildDottedName(callExpr.expression);
        }
      }

      let calleeFilePath: string | null = null;
      if (checker && callExpr.expression) {
        try {
          const symbol = checker.getSymbolAtLocation(callExpr.expression);
          if (symbol && symbol.declarations && symbol.declarations.length > 0) {
            const decl = symbol.declarations[0];
            const calleeSource = decl.getSourceFile();
            if (calleeSource && projectRoot) {
              calleeFilePath = path
                .relative(projectRoot, calleeSource.fileName)
                .replace(/\\/g, "/");
            }
          }
        } catch {}
      }

      if (calleeName) {
        const args = callExpr.arguments || [];
        const calleeBaseName = calleeName.split(".").pop() || calleeName;
        const params = functionParams.get(calleeBaseName) || [];

        if (args.length === 0) {
          calls.push({
            line: line + 1,
            caller_function: callerFunction,
            callee_function: calleeName,
            argument_index: null,
            argument_expr: null,
            param_name: null,
            callee_file_path: calleeFilePath,
          });
        } else {
          args.forEach((arg, i) => {
            const paramName = i < params.length ? params[i].name : "arg" + i;
            const argExpr = arg.getText(sourceFile).substring(0, 500);

            calls.push({
              line: line + 1,
              caller_function: callerFunction,
              callee_function: calleeName,
              argument_index: i,
              argument_expr: argExpr,
              param_name: paramName,
              callee_file_path: calleeFilePath,
            });
          });
        }
      }
    }

    if (node.kind === ts.SyntaxKind.NewExpression) {
      const newExpr = node as ts.NewExpression;
      const { line } = sourceFile.getLineAndCharacterOfPosition(
        node.getStart(sourceFile),
      );
      const callerFunction = scopeMap.get(line + 1) || "global";

      let className = "";
      if (newExpr.expression) {
        const exprKind = ts.SyntaxKind[newExpr.expression.kind];
        if (exprKind === "Identifier") {
          const id = newExpr.expression as ts.Identifier;
          className = id.text || id.escapedText?.toString() || "";
        } else if (exprKind === "PropertyAccessExpression") {
          className = buildDottedName(newExpr.expression);
        }
      }

      if (className) {
        const calleeName = "new " + className;
        const args = newExpr.arguments || [];
        const params = functionParams.get(className) || [];

        if (args.length === 0) {
          calls.push({
            line: line + 1,
            caller_function: callerFunction,
            callee_function: calleeName,
            argument_index: null,
            argument_expr: null,
            param_name: null,
            callee_file_path: null,
          });
        } else {
          args.forEach((arg, i) => {
            const paramName = i < params.length ? params[i].name : "arg" + i;
            const argExpr = arg.getText(sourceFile).substring(0, 500);

            calls.push({
              line: line + 1,
              caller_function: callerFunction,
              callee_function: calleeName,
              argument_index: i,
              argument_expr: argExpr,
              param_name: paramName,
              callee_file_path: null,
            });
          });
        }
      }
    }

    ts.forEachChild(node, (child) => traverse(child, depth + 1));
  }

  traverse(sourceFile);
  return calls;
}

interface ExtractReturnsResult {
  returns: IFunctionReturn[];
  return_source_vars: IReturnSourceVar[];
}

function detectJsxInNode(
  node: ts.Node,
  ts: typeof import("typescript"),
): { hasJsx: boolean; isComponent: boolean } {
  const JSX_KINDS = new Set([
    "JsxElement",
    "JsxSelfClosingElement",
    "JsxFragment",
    "JsxOpeningElement",
    "JsxClosingElement",
    "JsxExpression",
  ]);

  const visited = new Set<string>();

  function search(
    n: ts.Node,
    depth: number = 0,
  ): { hasJsx: boolean; isComponent: boolean } {
    if (depth > 30 || !n) return { hasJsx: false, isComponent: false };

    const id = n.pos + "-" + n.kind;
    if (visited.has(id)) return { hasJsx: false, isComponent: false };
    visited.add(id);

    const kind = ts.SyntaxKind[n.kind];

    if (JSX_KINDS.has(kind)) {
      let isComponent = false;
      const jsxNode = n as any;
      if (jsxNode.tagName) {
        const tagName =
          jsxNode.tagName.text || jsxNode.tagName.escapedText || "";
        isComponent =
          tagName.length > 0 && tagName[0] === tagName[0].toUpperCase();
      }
      return { hasJsx: true, isComponent };
    }

    if (kind === "CallExpression") {
      const ce = n as ts.CallExpression;
      if (ce.expression) {
        const exprText = ce.expression.getText ? ce.expression.getText() : "";
        if (
          exprText.includes("React.createElement") ||
          exprText.includes("jsx") ||
          exprText.includes("_jsx")
        ) {
          return { hasJsx: true, isComponent: false };
        }
      }
    }

    let result = { hasJsx: false, isComponent: false };
    ts.forEachChild(n, (child) => {
      const childResult = search(child, depth + 1);
      if (childResult.hasJsx) {
        result = childResult;
      }
    });
    return result;
  }

  return search(node);
}

export function extractReturns(
  sourceFile: ts.SourceFile,
  ts: typeof import("typescript"),
  scopeMap: Map<number, string>,
  filePath: string,
): ExtractReturnsResult {
  const returns: IFunctionReturn[] = [];
  const return_source_vars: IReturnSourceVar[] = [];
  const functionReturnCounts = new Map<string, number>();
  const visited = new Set<string>();

  function traverse(node: ts.Node, depth: number = 0): void {
    if (depth > 100 || !node) return;

    const nodeId = node.pos + "-" + node.kind;
    if (visited.has(nodeId)) return;
    visited.add(nodeId);

    if (node.kind === ts.SyntaxKind.ReturnStatement) {
      const returnStmt = node as ts.ReturnStatement;
      const { line, character } = sourceFile.getLineAndCharacterOfPosition(
        node.getStart(sourceFile),
      );
      const functionName = scopeMap.get(line + 1) || "global";

      const currentCount = functionReturnCounts.get(functionName) || 0;
      functionReturnCounts.set(functionName, currentCount + 1);

      const expression = returnStmt.expression;
      let returnExpr = "";
      let hasJsx = false;
      let returnsComponent = false;
      let returnVars: string[] = [];

      if (expression) {
        returnExpr = expression.getText(sourceFile).substring(0, 1000);

        const jsxDetection = detectJsxInNode(expression, ts);
        hasJsx = jsxDetection.hasJsx;
        returnsComponent = jsxDetection.isComponent;

        returnVars = extractVarsFromNode(expression, sourceFile, ts);
        returnVars.forEach((sourceVar, varIndex) => {
          return_source_vars.push({
            file: filePath,
            line: line + 1,
            function_name: functionName,
            source_var: sourceVar,
            var_index: varIndex,
          });
        });
      }

      returns.push({
        function_name: functionName,
        line: line + 1,
        col: character,
        return_expr: returnExpr,
        has_jsx: hasJsx,
        returns_component: returnsComponent,
        return_vars: returnVars,
        return_index: currentCount + 1,
      });
    }

    ts.forEachChild(node, (child) => traverse(child, depth + 1));
  }

  traverse(sourceFile);
  return { returns, return_source_vars };
}

interface IObjectLiteralProperty {
  line: number;
  variable_name: string;
  property_name: string;
  property_value: string;
  property_type: string;
  nested_level: number;
  in_function: string;
}

function extractFromObjectNode(
  objNode: ts.ObjectLiteralExpression,
  varName: string,
  inFunction: string,
  sourceFile: ts.SourceFile,
  ts: typeof import("typescript"),
  nestedLevel: number,
  literals: IObjectLiteralProperty[],
): void {
  const properties = objNode.properties || [];
  properties.forEach((prop) => {
    if (!prop) return;

    const { line } = sourceFile.getLineAndCharacterOfPosition(
      prop.getStart(sourceFile),
    );
    const kind = ts.SyntaxKind[prop.kind];

    if (kind === "PropertyAssignment") {
      const propAssign = prop as ts.PropertyAssignment;
      const propName = propAssign.name
        ? (propAssign.name as ts.Identifier).text ||
          (propAssign.name as ts.Identifier).escapedText?.toString() ||
          "<unknown>"
        : "<unknown>";
      const propValue = propAssign.initializer
        ? propAssign.initializer.getText(sourceFile).substring(0, 250)
        : "";

      literals.push({
        line: line + 1,
        variable_name: varName,
        property_name: propName,
        property_value: propValue,
        property_type: "value",
        nested_level: nestedLevel,
        in_function: inFunction,
      });

      if (
        propAssign.initializer &&
        propAssign.initializer.kind === ts.SyntaxKind.ObjectLiteralExpression
      ) {
        const nestedVarName = "<property:" + propName + ">";
        extractFromObjectNode(
          propAssign.initializer as ts.ObjectLiteralExpression,
          nestedVarName,
          inFunction,
          sourceFile,
          ts,
          nestedLevel + 1,
          literals,
        );
      }
    } else if (kind === "ShorthandPropertyAssignment") {
      const shorthand = prop as ts.ShorthandPropertyAssignment;
      const propName = shorthand.name
        ? shorthand.name.text ||
          shorthand.name.escapedText?.toString() ||
          "<unknown>"
        : "<unknown>";

      literals.push({
        line: line + 1,
        variable_name: varName,
        property_name: propName,
        property_value: propName,
        property_type: "shorthand",
        nested_level: nestedLevel,
        in_function: inFunction,
      });
    } else if (kind === "MethodDeclaration") {
      const method = prop as ts.MethodDeclaration;
      const methodName = method.name
        ? (method.name as ts.Identifier).text ||
          (method.name as ts.Identifier).escapedText?.toString() ||
          "<unknown>"
        : "<unknown>";

      literals.push({
        line: line + 1,
        variable_name: varName,
        property_name: methodName,
        property_value: "<function>",
        property_type: "method",
        nested_level: nestedLevel,
        in_function: inFunction,
      });
    }
  });
}

export function extractObjectLiterals(
  sourceFile: ts.SourceFile,
  ts: typeof import("typescript"),
  scopeMap: Map<number, string>,
): IObjectLiteralProperty[] {
  const literals: IObjectLiteralProperty[] = [];
  const visited = new Set<string>();

  function traverse(node: ts.Node, depth: number = 0): void {
    if (depth > 100 || !node) return;

    const nodeId = node.pos + "-" + node.kind;
    if (visited.has(nodeId)) return;
    visited.add(nodeId);

    const kind = ts.SyntaxKind[node.kind];
    const { line } = sourceFile.getLineAndCharacterOfPosition(
      node.getStart(sourceFile),
    );
    const inFunction = scopeMap.get(line + 1) || "global";

    if (kind === "VariableDeclaration") {
      const varDecl = node as ts.VariableDeclaration;
      if (
        varDecl.initializer &&
        varDecl.initializer.kind === ts.SyntaxKind.ObjectLiteralExpression
      ) {
        const varName = varDecl.name
          ? (varDecl.name as ts.Identifier).text ||
            (varDecl.name as ts.Identifier).escapedText?.toString() ||
            "<unknown>"
          : "<unknown>";
        extractFromObjectNode(
          varDecl.initializer as ts.ObjectLiteralExpression,
          varName,
          inFunction,
          sourceFile,
          ts,
          0,
          literals,
        );
      }
    } else if (kind === "BinaryExpression") {
      const binExpr = node as ts.BinaryExpression;
      if (
        binExpr.operatorToken &&
        binExpr.operatorToken.kind === ts.SyntaxKind.EqualsToken
      ) {
        if (
          binExpr.right &&
          binExpr.right.kind === ts.SyntaxKind.ObjectLiteralExpression
        ) {
          const varName = binExpr.left
            ? binExpr.left.getText(sourceFile)
            : "<unknown>";
          extractFromObjectNode(
            binExpr.right as ts.ObjectLiteralExpression,
            varName,
            inFunction,
            sourceFile,
            ts,
            0,
            literals,
          );
        }
      }
    } else if (kind === "ReturnStatement") {
      const returnStmt = node as ts.ReturnStatement;
      if (
        returnStmt.expression &&
        returnStmt.expression.kind === ts.SyntaxKind.ObjectLiteralExpression
      ) {
        const varName = "<return:" + inFunction + ">";
        extractFromObjectNode(
          returnStmt.expression as ts.ObjectLiteralExpression,
          varName,
          inFunction,
          sourceFile,
          ts,
          0,
          literals,
        );
      }
    } else if (kind === "CallExpression") {
      const callExpr = node as ts.CallExpression;
      const args = callExpr.arguments || [];
      const calleeName = callExpr.expression
        ? callExpr.expression.getText(sourceFile)
        : "unknown";

      args.forEach((arg, i) => {
        if (arg.kind === ts.SyntaxKind.ObjectLiteralExpression) {
          const varName = "<arg" + i + ":" + calleeName + ">";
          extractFromObjectNode(
            arg as ts.ObjectLiteralExpression,
            varName,
            inFunction,
            sourceFile,
            ts,
            0,
            literals,
          );
        }
      });
    } else if (kind === "ArrayLiteralExpression") {
      const arrayExpr = node as ts.ArrayLiteralExpression;
      const elements = arrayExpr.elements || [];
      elements.forEach((elem, i) => {
        if (elem.kind === ts.SyntaxKind.ObjectLiteralExpression) {
          const varName = "<array_elem" + i + ">";
          extractFromObjectNode(
            elem as ts.ObjectLiteralExpression,
            varName,
            inFunction,
            sourceFile,
            ts,
            0,
            literals,
          );
        }
      });
    }

    ts.forEachChild(node, (child) => traverse(child, depth + 1));
  }

  traverse(sourceFile);
  return literals;
}

interface IVariableUsage {
  line: number;
  variable_name: string;
  usage_type: string;
  in_component: string;
  in_hook: string;
  scope_level: number;
}

export function extractVariableUsage(
  assignments: IAssignment[],
  functionCallArgs: IFunctionCallArg[],
  assignment_source_vars: IAssignmentSourceVar[],
): IVariableUsage[] {
  const usage: IVariableUsage[] = [];

  const assignmentContext = new Map<string, string>();
  assignments.forEach((assign) => {
    const key = assign.line + "|" + assign.target_var;
    assignmentContext.set(key, assign.in_function);
  });

  assignments.forEach((assign) => {
    usage.push({
      line: assign.line,
      variable_name: assign.target_var,
      usage_type: "write",
      in_component: assign.in_function,
      in_hook: "",
      scope_level: assign.in_function === "global" ? 0 : 1,
    });
  });

  assignment_source_vars.forEach((srcVar) => {
    const contextKey = srcVar.line + "|" + srcVar.target_var;
    const inFunction = assignmentContext.get(contextKey) || "global";
    usage.push({
      line: srcVar.line,
      variable_name: srcVar.source_var,
      usage_type: "read",
      in_component: inFunction,
      in_hook: "",
      scope_level: inFunction === "global" ? 0 : 1,
    });
  });

  const seenCalls = new Set<string>();
  functionCallArgs.forEach((call) => {
    const key = call.line + "-" + call.callee_function;
    if (!seenCalls.has(key)) {
      seenCalls.add(key);
      usage.push({
        line: call.line,
        variable_name: call.callee_function,
        usage_type: "call",
        in_component: call.caller_function,
        in_hook: "",
        scope_level: call.caller_function === "global" ? 0 : 1,
      });
    }
  });

  return usage;
}
