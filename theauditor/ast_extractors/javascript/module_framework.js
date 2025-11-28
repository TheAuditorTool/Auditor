function extractImports(sourceFile, ts, filePath) {
  const imports = [];
  const import_specifiers = [];

  function visit(node) {
    if (node.kind === ts.SyntaxKind.ImportDeclaration) {
      const moduleSpecifier = node.moduleSpecifier;
      if (moduleSpecifier && moduleSpecifier.text) {
        const { line } = sourceFile.getLineAndCharacterOfPosition(
          node.getStart ? node.getStart(sourceFile) : node.pos,
        );
        const importLine = line + 1;

        if (node.importClause) {
          if (node.importClause.name) {
            const specName =
              node.importClause.name.text || node.importClause.name.escapedText;
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

          if (node.importClause.namedBindings) {
            const bindings = node.importClause.namedBindings;

            if (bindings.kind === ts.SyntaxKind.NamespaceImport) {
              const specName = bindings.name.text || bindings.name.escapedText;
              import_specifiers.push({
                file: filePath,
                import_line: importLine,
                specifier_name: specName,
                original_name: "*",
                is_default: 0,
                is_namespace: 1,
                is_named: 0,
              });
            } else if (
              bindings.kind === ts.SyntaxKind.NamedImports &&
              bindings.elements
            ) {
              bindings.elements.forEach((element) => {
                const localName = element.name.text || element.name.escapedText;
                let originalName = localName;
                if (element.propertyName) {
                  originalName =
                    element.propertyName.text ||
                    element.propertyName.escapedText;
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

        imports.push({
          kind: "import",
          module: moduleSpecifier.text,
          line: importLine,
        });
      }
    } else if (node.kind === ts.SyntaxKind.CallExpression) {
      const expr = node.expression;
      if (expr && (expr.text === "require" || expr.escapedText === "require")) {
        const args = node.arguments;
        if (
          args &&
          args.length > 0 &&
          args[0].kind === ts.SyntaxKind.StringLiteral
        ) {
          const { line } = sourceFile.getLineAndCharacterOfPosition(
            node.getStart ? node.getStart(sourceFile) : node.pos,
          );
          const importLine = line + 1;
          const modulePath = args[0].text;

          imports.push({
            kind: "require",
            module: modulePath,
            line: importLine,
          });

          let parent = node.parent;

          if (
            parent &&
            parent.kind === ts.SyntaxKind.PropertyAccessExpression
          ) {
            parent = parent.parent;
          }

          if (parent && parent.kind === ts.SyntaxKind.VariableDeclaration) {
            const declName = parent.name;

            if (declName.kind === ts.SyntaxKind.Identifier) {
              const specName = declName.text || declName.escapedText;
              import_specifiers.push({
                file: filePath,
                import_line: importLine,
                specifier_name: specName,
                original_name: specName,
                is_default: 1,
                is_namespace: 0,
                is_named: 0,
              });
            } else if (
              declName.kind === ts.SyntaxKind.ObjectBindingPattern &&
              declName.elements
            ) {
              declName.elements.forEach((element) => {
                if (
                  element.name &&
                  element.name.kind === ts.SyntaxKind.Identifier
                ) {
                  const localName =
                    element.name.text || element.name.escapedText;
                  let originalName = localName;
                  if (element.propertyName) {
                    originalName =
                      element.propertyName.text ||
                      element.propertyName.escapedText;
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
            } else if (
              declName.kind === ts.SyntaxKind.ArrayBindingPattern &&
              declName.elements
            ) {
              declName.elements.forEach((element, idx) => {
                if (
                  element.name &&
                  element.name.kind === ts.SyntaxKind.Identifier
                ) {
                  const localName =
                    element.name.text || element.name.escapedText;
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
    } else if (
      node.kind === ts.SyntaxKind.ImportKeyword &&
      node.parent &&
      node.parent.kind === ts.SyntaxKind.CallExpression
    ) {
      const callExpr = node.parent;
      const args = callExpr.arguments;
      if (
        args &&
        args.length > 0 &&
        args[0].kind === ts.SyntaxKind.StringLiteral
      ) {
        const { line } = sourceFile.getLineAndCharacterOfPosition(
          callExpr.getStart ? callExpr.getStart(sourceFile) : callExpr.pos,
        );
        imports.push({
          kind: "dynamic_import",
          module: args[0].text,
          line: line + 1,
        });
      }
    }

    ts.forEachChild(node, visit);
  }

  visit(sourceFile);
  return { imports, import_specifiers };
}

function extractEnvVarUsage(sourceFile, ts, scopeMap) {
  const usages = [];

  const visitedNodes = new Set();

  function traverse(node) {
    if (!node) return;

    const pos = node.getStart ? node.getStart(sourceFile) : node.pos;
    const { line, character } = sourceFile.getLineAndCharacterOfPosition(pos);
    const nodeId = `${line}:${character}:${node.kind}`;
    if (visitedNodes.has(nodeId)) {
      return;
    }
    visitedNodes.add(nodeId);

    const kind = ts.SyntaxKind[node.kind];

    if (kind === "PropertyAccessExpression") {
      if (node.expression && node.name) {
        const exprKind = ts.SyntaxKind[node.expression.kind];

        if (
          exprKind === "PropertyAccessExpression" &&
          node.expression.expression &&
          node.expression.name
        ) {
          const objName =
            node.expression.expression.text ||
            node.expression.expression.escapedText;
          const propName =
            node.expression.name.text || node.expression.name.escapedText;

          if (objName === "process" && propName === "env") {
            const varName = node.name.text || node.name.escapedText;
            const { line } = sourceFile.getLineAndCharacterOfPosition(
              node.getStart(sourceFile),
            );
            const inFunction = scopeMap.get(line + 1) || null;

            let accessType = "read";
            if (node.parent) {
              const parentKind = ts.SyntaxKind[node.parent.kind];
              if (
                parentKind === "BinaryExpression" &&
                node.parent.operatorToken &&
                ts.SyntaxKind[node.parent.operatorToken.kind] ===
                  "EqualsToken" &&
                node.parent.left === node
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
              line: line + 1,
              var_name: varName,
              access_type: accessType,
              in_function: inFunction,
              property_access: `process.env.${varName}`,
            });
          }
        }
      }
    }

    if (kind === "ElementAccessExpression") {
      if (node.expression && node.argumentExpression) {
        const exprKind = ts.SyntaxKind[node.expression.kind];

        if (
          exprKind === "PropertyAccessExpression" &&
          node.expression.expression &&
          node.expression.name
        ) {
          const objName =
            node.expression.expression.text ||
            node.expression.expression.escapedText;
          const propName =
            node.expression.name.text || node.expression.name.escapedText;

          if (objName === "process" && propName === "env") {
            let varName = null;
            const argKind = ts.SyntaxKind[node.argumentExpression.kind];
            if (argKind === "StringLiteral") {
              varName = node.argumentExpression.text;
            } else if (argKind === "Identifier") {
              varName = `[${node.argumentExpression.text || node.argumentExpression.escapedText}]`;
            }

            if (varName) {
              const { line } = sourceFile.getLineAndCharacterOfPosition(
                node.getStart(sourceFile),
              );
              const inFunction = scopeMap.get(line + 1) || null;

              let accessType = "read";
              if (node.parent) {
                const parentKind = ts.SyntaxKind[node.parent.kind];
                if (
                  parentKind === "BinaryExpression" &&
                  node.parent.operatorToken &&
                  ts.SyntaxKind[node.parent.operatorToken.kind] ===
                    "EqualsToken" &&
                  node.parent.left === node
                ) {
                  accessType = "write";
                }
              }

              usages.push({
                line: line + 1,
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

    if (kind === "VariableDeclaration") {
      if (node.name && node.initializer) {
        const nameKind = ts.SyntaxKind[node.name.kind];
        const initKind = ts.SyntaxKind[node.initializer.kind];

        if (
          nameKind === "ObjectBindingPattern" &&
          initKind === "PropertyAccessExpression"
        ) {
          const initExpr = node.initializer.expression;
          const initName = node.initializer.name;

          if (initExpr && initName) {
            const objName = initExpr.text || initExpr.escapedText;
            const propName = initName.text || initName.escapedText;

            if (objName === "process" && propName === "env") {
              if (node.name.elements) {
                for (const element of node.name.elements) {
                  if (element.name) {
                    const varName =
                      element.name.text || element.name.escapedText;
                    const { line } = sourceFile.getLineAndCharacterOfPosition(
                      element.getStart(sourceFile),
                    );
                    const inFunction = scopeMap.get(line + 1) || null;

                    usages.push({
                      line: line + 1,
                      var_name: varName,
                      access_type: "read",
                      in_function: inFunction,
                      property_access: `process.env.${varName} (destructured)`,
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

function extractORMRelationships(sourceFile, ts) {
  const relationships = [];

  const seenRelationships = new Set();

  const relationshipMethods = new Set([
    "hasMany",
    "belongsTo",
    "hasOne",
    "hasAndBelongsToMany",
    "belongsToMany",
  ]);

  function traverse(node) {
    if (!node) return;
    const kind = ts.SyntaxKind[node.kind];

    if (kind === "CallExpression") {
      if (node.expression && node.arguments && node.arguments.length > 0) {
        const exprKind = ts.SyntaxKind[node.expression.kind];

        if (exprKind === "PropertyAccessExpression") {
          const methodName =
            node.expression.name.text || node.expression.name.escapedText;

          if (relationshipMethods.has(methodName)) {
            let sourceModel = null;
            if (node.expression.expression) {
              const exprExpr = node.expression.expression;
              const exprExprKind = ts.SyntaxKind[exprExpr.kind];

              if (exprExprKind === "Identifier") {
                sourceModel = exprExpr.text || exprExpr.escapedText;
              } else if (exprExprKind === "PropertyAccessExpression") {
                sourceModel = exprExpr.name.text || exprExpr.name.escapedText;
              }
            }

            let targetModel = null;
            const firstArg = node.arguments[0];
            if (firstArg) {
              const argKind = ts.SyntaxKind[firstArg.kind];
              if (argKind === "Identifier") {
                targetModel = firstArg.text || firstArg.escapedText;
              } else if (argKind === "PropertyAccessExpression") {
                targetModel = firstArg.name.text || firstArg.name.escapedText;
              }
            }

            let foreignKey = null;
            let cascadeDelete = false;
            let asName = null;

            if (node.arguments.length > 1) {
              const optionsArg = node.arguments[1];
              const optionsKind = ts.SyntaxKind[optionsArg.kind];

              if (optionsKind === "ObjectLiteralExpression") {
                if (optionsArg.properties) {
                  for (const prop of optionsArg.properties) {
                    const propKind = ts.SyntaxKind[prop.kind];

                    if (propKind === "PropertyAssignment") {
                      const propName = prop.name.text || prop.name.escapedText;

                      if (propName === "foreignKey") {
                        const initKind = ts.SyntaxKind[prop.initializer.kind];
                        if (initKind === "StringLiteral") {
                          foreignKey = prop.initializer.text;
                        }
                      }

                      if (propName === "onDelete") {
                        const initKind = ts.SyntaxKind[prop.initializer.kind];
                        if (initKind === "StringLiteral") {
                          const value = prop.initializer.text;
                          if (value.toUpperCase() === "CASCADE") {
                            cascadeDelete = true;
                          }
                        }
                      }

                      if (propName === "as") {
                        const initKind = ts.SyntaxKind[prop.initializer.kind];
                        if (initKind === "StringLiteral") {
                          asName = prop.initializer.text;
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

              if (seenRelationships.has(dedupKey)) {
                return;
              }

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

    ts.forEachChild(node, traverse);
  }

  traverse(sourceFile);
  return relationships;
}

function extractImportStyles(imports, import_specifiers, filePath) {
  const import_styles = [];
  const import_style_names = [];

  for (const imp of imports) {
    const target = imp.module || imp.target;
    if (!target) continue;

    const line = imp.line || 0;
    let import_style = null;
    let alias_name = null;

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
      const fullStatement =
        imp.text || `import ${import_style} from '${target}'`;

      import_styles.push({
        file: filePath,
        line: line,
        package: target,
        import_style: import_style,
        alias_name: alias_name,
        full_statement: fullStatement.substring(0, 200),
      });
    }
  }

  return { import_styles, import_style_names };
}

function extractRefs(imports, import_specifiers) {
  const resolved = {};

  const lineToModule = new Map();
  for (const imp of imports) {
    const modulePath = imp.module || imp.target;
    if (!modulePath) continue;
    lineToModule.set(imp.line, modulePath);

    const moduleName = modulePath
      .split("/")
      .pop()
      .replace(/\.(js|ts|jsx|tsx)$/, "");
    if (moduleName) {
      resolved[moduleName] = modulePath;
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
