import type * as ts from "typescript";
import type {
  Import as IImport,
  ImportSpecifier as IImportSpecifier,
  ImportStyle as IImportStyle,
  ImportStyleName as IImportStyleName,
  EnvVarUsage as IEnvVarUsage,
  ORMRelationship as IORMRelationship,
} from "../schema.js";

interface ExtractImportsResult {
  imports: IImport[];
  import_specifiers: IImportSpecifier[];
}

export function extractImports(
  sourceFile: ts.SourceFile,
  ts: typeof import("typescript"),
  filePath: string,
): ExtractImportsResult {
  const imports: IImport[] = [];
  const import_specifiers: IImportSpecifier[] = [];

  function visit(node: ts.Node): void {
    if (node.kind === ts.SyntaxKind.ImportDeclaration) {
      const importDecl = node as ts.ImportDeclaration;
      const moduleSpecifier = importDecl.moduleSpecifier as ts.StringLiteral;
      if (moduleSpecifier && moduleSpecifier.text) {
        const { line } = sourceFile.getLineAndCharacterOfPosition(
          node.getStart(sourceFile),
        );
        const importLine = line + 1;

        if (importDecl.importClause) {
          if (importDecl.importClause.name) {
            const specName =
              importDecl.importClause.name.text ||
              importDecl.importClause.name.escapedText?.toString() ||
              "";
            import_specifiers.push({
              file: filePath,
              import_line: importLine,
              specifier_name: specName,
              original_name: specName,
              is_default: 1,
              is_namespace: 0,
              is_named: 0,
            });
          }

          if (importDecl.importClause.namedBindings) {
            const bindings = importDecl.importClause.namedBindings;

            if (bindings.kind === ts.SyntaxKind.NamespaceImport) {
              const nsImport = bindings as ts.NamespaceImport;
              const specName =
                nsImport.name.text ||
                nsImport.name.escapedText?.toString() ||
                "";
              import_specifiers.push({
                file: filePath,
                import_line: importLine,
                specifier_name: specName,
                original_name: "*",
                is_default: 0,
                is_namespace: 1,
                is_named: 0,
              });
            } else if (bindings.kind === ts.SyntaxKind.NamedImports) {
              const namedImports = bindings as ts.NamedImports;
              if (namedImports.elements) {
                namedImports.elements.forEach((element) => {
                  const localName =
                    (element.name as ts.Identifier).text ||
                    (element.name as ts.Identifier).escapedText?.toString() ||
                    "";
                  let originalName = localName;
                  if (element.propertyName) {
                    originalName =
                      (element.propertyName as ts.Identifier).text ||
                      (
                        element.propertyName as ts.Identifier
                      ).escapedText?.toString() ||
                      "";
                  }
                  import_specifiers.push({
                    file: filePath,
                    import_line: importLine,
                    specifier_name: localName,
                    original_name: originalName,
                    is_default: 0,
                    is_namespace: 0,
                    is_named: 1,
                  });
                });
              }
            }
          }
        }

        imports.push({
          kind: "import",
          module: moduleSpecifier.text,
          line: importLine,
        });
      }
    } else if (node.kind === ts.SyntaxKind.CallExpression) {
      const callExpr = node as ts.CallExpression;
      const expr = callExpr.expression;
      if (
        expr &&
        ((expr as ts.Identifier).text === "require" ||
          (expr as ts.Identifier).escapedText?.toString() === "require")
      ) {
        const args = callExpr.arguments;
        if (
          args &&
          args.length > 0 &&
          args[0].kind === ts.SyntaxKind.StringLiteral
        ) {
          const { line } = sourceFile.getLineAndCharacterOfPosition(
            node.getStart(sourceFile),
          );
          const importLine = line + 1;
          const modulePath = (args[0] as ts.StringLiteral).text;

          imports.push({
            kind: "require",
            module: modulePath,
            line: importLine,
          });

          let parent: ts.Node | undefined = node.parent;

          if (
            parent &&
            parent.kind === ts.SyntaxKind.PropertyAccessExpression
          ) {
            parent = parent.parent;
          }

          if (parent && parent.kind === ts.SyntaxKind.VariableDeclaration) {
            const varDecl = parent as ts.VariableDeclaration;
            const declName = varDecl.name;

            if (declName.kind === ts.SyntaxKind.Identifier) {
              const specName =
                (declName as ts.Identifier).text ||
                (declName as ts.Identifier).escapedText?.toString() ||
                "";
              import_specifiers.push({
                file: filePath,
                import_line: importLine,
                specifier_name: specName,
                original_name: specName,
                is_default: 1,
                is_namespace: 0,
                is_named: 0,
              });
            } else if (declName.kind === ts.SyntaxKind.ObjectBindingPattern) {
              const pattern = declName as ts.ObjectBindingPattern;
              if (pattern.elements) {
                pattern.elements.forEach((element) => {
                  if (
                    element.name &&
                    element.name.kind === ts.SyntaxKind.Identifier
                  ) {
                    const localName =
                      (element.name as ts.Identifier).text ||
                      (element.name as ts.Identifier).escapedText?.toString() ||
                      "";
                    let originalName = localName;
                    if (element.propertyName) {
                      originalName =
                        (element.propertyName as ts.Identifier).text ||
                        (
                          element.propertyName as ts.Identifier
                        ).escapedText?.toString() ||
                        "";
                    }
                    import_specifiers.push({
                      file: filePath,
                      import_line: importLine,
                      specifier_name: localName,
                      original_name: originalName,
                      is_default: 0,
                      is_namespace: 0,
                      is_named: 1,
                    });
                  }
                });
              }
            } else if (declName.kind === ts.SyntaxKind.ArrayBindingPattern) {
              const pattern = declName as ts.ArrayBindingPattern;
              if (pattern.elements) {
                pattern.elements.forEach((element, idx) => {
                  if (
                    element.kind === ts.SyntaxKind.BindingElement &&
                    (element as ts.BindingElement).name &&
                    (element as ts.BindingElement).name.kind ===
                      ts.SyntaxKind.Identifier
                  ) {
                    const localName =
                      ((element as ts.BindingElement).name as ts.Identifier)
                        .text ||
                      (
                        (element as ts.BindingElement).name as ts.Identifier
                      ).escapedText?.toString() ||
                      "";
                    import_specifiers.push({
                      file: filePath,
                      import_line: importLine,
                      specifier_name: localName,
                      original_name: `[${idx}]`,
                      is_default: 0,
                      is_namespace: 0,
                      is_named: 1,
                    });
                  }
                });
              }
            }
          }
        }
      }
    } else if (
      node.kind === ts.SyntaxKind.ImportKeyword &&
      node.parent &&
      node.parent.kind === ts.SyntaxKind.CallExpression
    ) {
      const callExpr = node.parent as ts.CallExpression;
      const args = callExpr.arguments;
      if (
        args &&
        args.length > 0 &&
        args[0].kind === ts.SyntaxKind.StringLiteral
      ) {
        const { line } = sourceFile.getLineAndCharacterOfPosition(
          callExpr.getStart(sourceFile),
        );
        imports.push({
          kind: "dynamic_import",
          module: (args[0] as ts.StringLiteral).text,
          line: line + 1,
        });
      }
    }

    ts.forEachChild(node, visit);
  }

  visit(sourceFile);
  return { imports, import_specifiers };
}

export function extractEnvVarUsage(
  sourceFile: ts.SourceFile,
  ts: typeof import("typescript"),
  scopeMap: Map<number, string>,
): IEnvVarUsage[] {
  const usages: IEnvVarUsage[] = [];
  const visitedNodes = new Set<string>();

  function traverse(node: ts.Node): void {
    if (!node) return;

    const pos = node.getStart(sourceFile);
    const { line, character } = sourceFile.getLineAndCharacterOfPosition(pos);
    const nodeId = `${line}:${character}:${node.kind}`;
    if (visitedNodes.has(nodeId)) {
      return;
    }
    visitedNodes.add(nodeId);

    const kind = ts.SyntaxKind[node.kind];

    if (kind === "PropertyAccessExpression") {
      const pae = node as ts.PropertyAccessExpression;
      if (pae.expression && pae.name) {
        const exprKind = ts.SyntaxKind[pae.expression.kind];

        if (exprKind === "PropertyAccessExpression") {
          const innerPae = pae.expression as ts.PropertyAccessExpression;
          if (innerPae.expression && innerPae.name) {
            const objName =
              (innerPae.expression as ts.Identifier).text ||
              (innerPae.expression as ts.Identifier).escapedText?.toString() ||
              "";
            const propName =
              innerPae.name.text || innerPae.name.escapedText?.toString() || "";

            if (objName === "process" && propName === "env") {
              const varName =
                pae.name.text || pae.name.escapedText?.toString() || "";
              const { line: envLine } =
                sourceFile.getLineAndCharacterOfPosition(
                  node.getStart(sourceFile),
                );
              const inFunction = scopeMap.get(envLine + 1) || null;

              let accessType = "read";
              if (node.parent) {
                const parentKind = ts.SyntaxKind[node.parent.kind];
                if (
                  parentKind === "BinaryExpression" &&
                  (node.parent as ts.BinaryExpression).operatorToken &&
                  ts.SyntaxKind[
                    (node.parent as ts.BinaryExpression).operatorToken.kind
                  ] === "EqualsToken" &&
                  (node.parent as ts.BinaryExpression).left === node
                ) {
                  accessType = "write";
                } else if (
                  parentKind === "IfStatement" ||
                  parentKind === "ConditionalExpression" ||
                  parentKind === "PrefixUnaryExpression"
                ) {
                  accessType = "check";
                }
              }

              usages.push({
                line: envLine + 1,
                var_name: varName,
                access_type: accessType,
                in_function: inFunction,
                property_access: `process.env.${varName}`,
              });
            }
          }
        }
      }
    }

    if (kind === "ElementAccessExpression") {
      const eae = node as ts.ElementAccessExpression;
      if (eae.expression && eae.argumentExpression) {
        const exprKind = ts.SyntaxKind[eae.expression.kind];

        if (exprKind === "PropertyAccessExpression") {
          const pae = eae.expression as ts.PropertyAccessExpression;
          if (pae.expression && pae.name) {
            const objName =
              (pae.expression as ts.Identifier).text ||
              (pae.expression as ts.Identifier).escapedText?.toString() ||
              "";
            const propName =
              pae.name.text || pae.name.escapedText?.toString() || "";

            if (objName === "process" && propName === "env") {
              let varName: string | null = null;
              const argKind = ts.SyntaxKind[eae.argumentExpression.kind];
              if (argKind === "StringLiteral") {
                varName = (eae.argumentExpression as ts.StringLiteral).text;
              } else if (argKind === "Identifier") {
                varName = `[${(eae.argumentExpression as ts.Identifier).text || (eae.argumentExpression as ts.Identifier).escapedText?.toString()}]`;
              }

              if (varName) {
                const { line: envLine } =
                  sourceFile.getLineAndCharacterOfPosition(
                    node.getStart(sourceFile),
                  );
                const inFunction = scopeMap.get(envLine + 1) || null;

                let accessType = "read";
                if (node.parent) {
                  const parentKind = ts.SyntaxKind[node.parent.kind];
                  if (
                    parentKind === "BinaryExpression" &&
                    (node.parent as ts.BinaryExpression).operatorToken &&
                    ts.SyntaxKind[
                      (node.parent as ts.BinaryExpression).operatorToken.kind
                    ] === "EqualsToken" &&
                    (node.parent as ts.BinaryExpression).left === node
                  ) {
                    accessType = "write";
                  }
                }

                usages.push({
                  line: envLine + 1,
                  var_name: varName,
                  access_type: accessType,
                  in_function: inFunction,
                  property_access: `process.env['${varName}']`,
                });
              }
            }
          }
        }
      }
    }

    if (kind === "VariableDeclaration") {
      const varDecl = node as ts.VariableDeclaration;
      if (varDecl.name && varDecl.initializer) {
        const nameKind = ts.SyntaxKind[varDecl.name.kind];
        const initKind = ts.SyntaxKind[varDecl.initializer.kind];

        if (
          nameKind === "ObjectBindingPattern" &&
          initKind === "PropertyAccessExpression"
        ) {
          const pae = varDecl.initializer as ts.PropertyAccessExpression;
          if (pae.expression && pae.name) {
            const objName =
              (pae.expression as ts.Identifier).text ||
              (pae.expression as ts.Identifier).escapedText?.toString() ||
              "";
            const propName =
              pae.name.text || pae.name.escapedText?.toString() || "";

            if (objName === "process" && propName === "env") {
              const pattern = varDecl.name as ts.ObjectBindingPattern;
              if (pattern.elements) {
                for (const element of pattern.elements) {
                  if (element.name) {
                    const envVarName =
                      (element.name as ts.Identifier).text ||
                      (element.name as ts.Identifier).escapedText?.toString() ||
                      "";
                    const { line: envLine } =
                      sourceFile.getLineAndCharacterOfPosition(
                        element.getStart(sourceFile),
                      );
                    const inFunction = scopeMap.get(envLine + 1) || null;

                    usages.push({
                      line: envLine + 1,
                      var_name: envVarName,
                      access_type: "read",
                      in_function: inFunction,
                      property_access: `process.env.${envVarName} (destructured)`,
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

export function extractORMRelationships(
  sourceFile: ts.SourceFile,
  ts: typeof import("typescript"),
): IORMRelationship[] {
  const relationships: IORMRelationship[] = [];
  const seenRelationships = new Set<string>();

  const relationshipMethods = new Set([
    "hasMany",
    "belongsTo",
    "hasOne",
    "hasAndBelongsToMany",
    "belongsToMany",
  ]);

  function traverse(node: ts.Node): void {
    if (!node) return;
    const kind = ts.SyntaxKind[node.kind];

    if (kind === "CallExpression") {
      const callExpr = node as ts.CallExpression;
      if (
        callExpr.expression &&
        callExpr.arguments &&
        callExpr.arguments.length > 0
      ) {
        const exprKind = ts.SyntaxKind[callExpr.expression.kind];

        if (exprKind === "PropertyAccessExpression") {
          const pae = callExpr.expression as ts.PropertyAccessExpression;
          const methodName =
            pae.name.text || pae.name.escapedText?.toString() || "";

          if (relationshipMethods.has(methodName)) {
            let sourceModel: string | null = null;
            if (pae.expression) {
              const exprExprKind = ts.SyntaxKind[pae.expression.kind];

              if (exprExprKind === "Identifier") {
                sourceModel =
                  (pae.expression as ts.Identifier).text ||
                  (pae.expression as ts.Identifier).escapedText?.toString() ||
                  null;
              } else if (exprExprKind === "PropertyAccessExpression") {
                const innerPae = pae.expression as ts.PropertyAccessExpression;
                sourceModel =
                  innerPae.name.text ||
                  innerPae.name.escapedText?.toString() ||
                  null;
              }
            }

            let targetModel: string | null = null;
            const firstArg = callExpr.arguments[0];
            if (firstArg) {
              const argKind = ts.SyntaxKind[firstArg.kind];
              if (argKind === "Identifier") {
                targetModel =
                  (firstArg as ts.Identifier).text ||
                  (firstArg as ts.Identifier).escapedText?.toString() ||
                  null;
              } else if (argKind === "PropertyAccessExpression") {
                const argPae = firstArg as ts.PropertyAccessExpression;
                targetModel =
                  argPae.name.text ||
                  argPae.name.escapedText?.toString() ||
                  null;
              }
            }

            let foreignKey: string | null = null;
            let cascadeDelete = false;
            let asName: string | null = null;

            if (callExpr.arguments.length > 1) {
              const optionsArg = callExpr.arguments[1];
              const optionsKind = ts.SyntaxKind[optionsArg.kind];

              if (optionsKind === "ObjectLiteralExpression") {
                const objLit = optionsArg as ts.ObjectLiteralExpression;
                if (objLit.properties) {
                  for (const prop of objLit.properties) {
                    const propKind = ts.SyntaxKind[prop.kind];

                    if (propKind === "PropertyAssignment") {
                      const propAssign = prop as ts.PropertyAssignment;
                      const propName =
                        (propAssign.name as ts.Identifier).text ||
                        (
                          propAssign.name as ts.Identifier
                        ).escapedText?.toString() ||
                        "";

                      if (propName === "foreignKey") {
                        const initKind =
                          ts.SyntaxKind[propAssign.initializer.kind];
                        if (initKind === "StringLiteral") {
                          foreignKey = (
                            propAssign.initializer as ts.StringLiteral
                          ).text;
                        }
                      }

                      if (propName === "onDelete") {
                        const initKind =
                          ts.SyntaxKind[propAssign.initializer.kind];
                        if (initKind === "StringLiteral") {
                          const value = (
                            propAssign.initializer as ts.StringLiteral
                          ).text;
                          if (value.toUpperCase() === "CASCADE") {
                            cascadeDelete = true;
                          }
                        }
                      }

                      if (propName === "as") {
                        const initKind =
                          ts.SyntaxKind[propAssign.initializer.kind];
                        if (initKind === "StringLiteral") {
                          asName = (propAssign.initializer as ts.StringLiteral)
                            .text;
                        }
                      }
                    }
                  }
                }
              }
            }

            if (sourceModel && targetModel) {
              const { line } = sourceFile.getLineAndCharacterOfPosition(
                node.getStart(sourceFile),
              );
              const lineNum = line + 1;

              const dedupKey = `${sourceModel}-${targetModel}-${methodName}-${lineNum}`;

              if (!seenRelationships.has(dedupKey)) {
                seenRelationships.add(dedupKey);

                relationships.push({
                  line: lineNum,
                  source_model: sourceModel,
                  target_model: targetModel,
                  relationship_type: methodName,
                  foreign_key: foreignKey,
                  cascade_delete: cascadeDelete,
                  as_name: asName,
                });
              }
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

export function extractImportStyles(
  imports: IImport[],
  import_specifiers: IImportSpecifier[],
  filePath: string,
  program: ts.Program | null,
  sourceFile: ts.SourceFile | null,
  tsLib: typeof ts,
  projectRoot: string,
): { import_styles: IImportStyle[]; import_style_names: IImportStyleName[] } {
  const import_styles: IImportStyle[] = [];
  const import_style_names: IImportStyleName[] = [];

  const resolveModulePath = (modulePath: string): string | null => {
    if (!program || !sourceFile) return null;

    const resolvedModule = (program as any).getResolvedModule?.(
      sourceFile,
      modulePath,
      undefined,
    );

    if (resolvedModule?.resolvedFileName) {
      let resolved = resolvedModule.resolvedFileName;
      resolved = resolved.replace(/\\/g, "/");
      if (projectRoot) {
        const normalizedRoot = projectRoot.replace(/\\/g, "/");
        if (resolved.startsWith(normalizedRoot)) {
          resolved = resolved.slice(normalizedRoot.length);
          if (resolved.startsWith("/")) {
            resolved = resolved.slice(1);
          }
        }
      }
      return resolved;
    }

    return null;
  };

  for (const imp of imports) {
    const target = imp.module;
    if (!target) continue;

    const line = imp.line || 0;
    let import_style: string | null = null;
    let alias_name: string | null = null;

    const lineSpecifiers = import_specifiers.filter(
      (s) => s.import_line === line,
    );
    const namespaceSpec = lineSpecifiers.find((s) => s.is_namespace === 1);
    const defaultSpec = lineSpecifiers.find((s) => s.is_default === 1);
    const namedSpecs = lineSpecifiers.filter((s) => s.is_named === 1);

    if (namespaceSpec) {
      import_style = "namespace";
      alias_name = namespaceSpec.specifier_name;
    } else if (namedSpecs.length > 0) {
      import_style = "named";
      namedSpecs.forEach((spec) => {
        import_style_names.push({
          import_file: filePath,
          import_line: line,
          imported_name: spec.specifier_name,
        });
      });
    } else if (defaultSpec) {
      import_style = "default";
      alias_name = defaultSpec.specifier_name;
    } else {
      import_style = "side-effect";
    }

    if (import_style) {
      const fullStatement = `import ${import_style} from '${target}'`;

      import_styles.push({
        file: filePath,
        line: line,
        package: target,
        import_style: import_style,
        alias_name: alias_name,
        full_statement: fullStatement.substring(0, 200),
        resolved_path: resolveModulePath(target),
      });
    }
  }

  return { import_styles, import_style_names };
}

export function extractRefs(
  imports: IImport[],
  import_specifiers: IImportSpecifier[],
): Record<string, string> {
  const resolved: Record<string, string> = {};

  const lineToModule = new Map<number, string>();
  for (const imp of imports) {
    const modulePath = imp.module;
    if (!modulePath) continue;
    lineToModule.set(imp.line, modulePath);

    const parts = modulePath.split("/");
    const fileName = parts.pop()?.replace(/\.(js|ts|jsx|tsx)$/, "") || "";
    if (fileName) {
      if (fileName === "index" && parts.length > 0) {
        const parent = parts[parts.length - 1];
        resolved[`${parent}/${fileName}`] = modulePath;
      }
      resolved[fileName] = modulePath;
    }
  }

  for (const spec of import_specifiers) {
    const modulePath = lineToModule.get(spec.import_line);
    if (modulePath && spec.specifier_name) {
      resolved[spec.specifier_name] = modulePath;
    }
  }

  return resolved;
}
