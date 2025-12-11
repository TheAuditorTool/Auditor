import type * as ts from "typescript";
import { logger } from "../utils/logger.js";
import type {
  Function as IFunction,
  Class as IClass,
  Interface as IInterface,
  ClassMember as IClassMember,
  ClassMethod as IClassMethod,
  FuncParam as IFuncParam,
  FuncDecorator as IFuncDecorator,
  FuncDecoratorArg as IFuncDecoratorArg,
  FuncParamDecorator as IFuncParamDecorator,
  ClassDecorator as IClassDecorator,
  ClassDecoratorArg as IClassDecoratorArg,
  ClassProperty as IClassProperty,
} from "../schema.js";

interface ExtractFunctionsResult {
  functions: IFunction[];
  func_params: IFuncParam[];
  func_decorators: IFuncDecorator[];
  func_decorator_args: IFuncDecoratorArg[];
  func_param_decorators: IFuncParamDecorator[];
}

export function extractFunctions(
  sourceFile: ts.SourceFile,
  checker: ts.TypeChecker | null,
  ts: typeof import("typescript"),
  filePath: string,
): ExtractFunctionsResult {
  const functions: IFunction[] = [];
  const func_params: IFuncParam[] = [];
  const func_decorators: IFuncDecorator[] = [];
  const func_decorator_args: IFuncDecoratorArg[] = [];
  const func_param_decorators: IFuncParamDecorator[] = [];
  const class_stack: string[] = [];

  function traverse(node: ts.Node): void {
    if (!node) return;
    const kind = ts.SyntaxKind[node.kind];

    if (kind === "ClassDeclaration") {
      const classNode = node as ts.ClassDeclaration;
      const className = classNode.name ? classNode.name.text : "UnknownClass";
      class_stack.push(className);
      ts.forEachChild(node, traverse);
      class_stack.pop();
      return;
    }

    let is_function_like = false;
    let func_name = "";
    const { line, character } = sourceFile.getLineAndCharacterOfPosition(
      node.getStart(sourceFile),
    );
    const func_line = line + 1;
    const func_entry: IFunction = {
      line: func_line,
      col: character,
      kind: kind,
      name: "",
      type: "function",
    };

    if (kind === "FunctionDeclaration") {
      const funcNode = node as ts.FunctionDeclaration;
      is_function_like = true;
      func_name = funcNode.name ? funcNode.name.text : "anonymous";
    } else if (kind === "MethodDeclaration") {
      const methodNode = node as ts.MethodDeclaration;
      is_function_like = true;
      const method_name = methodNode.name
        ? (methodNode.name as ts.Identifier).text || "anonymous"
        : "anonymous";
      func_name =
        class_stack.length > 0
          ? class_stack[class_stack.length - 1] + "." + method_name
          : method_name;
    } else if (kind === "PropertyDeclaration") {
      const propNode = node as ts.PropertyDeclaration;
      if (propNode.initializer) {
        const init_kind = ts.SyntaxKind[propNode.initializer.kind];
        if (
          init_kind === "ArrowFunction" ||
          init_kind === "FunctionExpression" ||
          init_kind === "CallExpression"
        ) {
          is_function_like = true;
          const prop_name = propNode.name
            ? (propNode.name as ts.Identifier).text || "anonymous"
            : "anonymous";
          func_name =
            class_stack.length > 0
              ? class_stack[class_stack.length - 1] + "." + prop_name
              : prop_name;
        }
      }
    } else if (kind === "Constructor") {
      is_function_like = true;
      func_name =
        class_stack.length > 0
          ? class_stack[class_stack.length - 1] + ".constructor"
          : "constructor";
    } else if (kind === "GetAccessor" || kind === "SetAccessor") {
      const accessorNode = node as ts.AccessorDeclaration;
      is_function_like = true;
      const accessor_name = accessorNode.name
        ? (accessorNode.name as ts.Identifier).text || "anonymous"
        : "anonymous";
      const prefix = kind === "GetAccessor" ? "get " : "set ";
      func_name =
        class_stack.length > 0
          ? class_stack[class_stack.length - 1] + "." + prefix + accessor_name
          : prefix + accessor_name;
    }

    if (is_function_like && func_name && func_name !== "anonymous") {
      func_entry.name = func_name;

      const funcLikeNode = node as ts.FunctionLikeDeclaration;
      if (funcLikeNode.parameters && Array.isArray(funcLikeNode.parameters)) {
        funcLikeNode.parameters.forEach((param, paramIndex) => {
          let paramName = "";
          let paramType: string | null = null;

          if (param.type) {
            paramType = param.type.getText(sourceFile);
          }

          const decorators = ts.canHaveDecorators(param)
            ? ts.getDecorators(param)
            : undefined;
          if (decorators && decorators.length > 0) {
            decorators.forEach((decorator) => {
              let decoratorName = "";
              let decoratorArgs: string | null = null;

              if (decorator.expression) {
                if (decorator.expression.kind === ts.SyntaxKind.Identifier) {
                  const id = decorator.expression as ts.Identifier;
                  decoratorName = id.text || id.escapedText?.toString() || "";
                } else if (
                  decorator.expression.kind === ts.SyntaxKind.CallExpression
                ) {
                  const callExpr = decorator.expression as ts.CallExpression;
                  if (
                    callExpr.expression &&
                    callExpr.expression.kind === ts.SyntaxKind.Identifier
                  ) {
                    const id = callExpr.expression as ts.Identifier;
                    decoratorName = id.text || id.escapedText?.toString() || "";
                  }
                  if (callExpr.arguments && callExpr.arguments.length > 0) {
                    decoratorArgs = callExpr.arguments
                      .map((arg) => {
                        if (arg.kind === ts.SyntaxKind.StringLiteral) {
                          return (arg as ts.StringLiteral).text;
                        }
                        return arg.getText
                          ? arg.getText(sourceFile)
                          : "[complex]";
                      })
                      .join(", ");
                  }
                }
              }

              if (decoratorName) {
                func_param_decorators.push({
                  function_name: func_name,
                  function_line: func_line,
                  param_index: paramIndex,
                  decorator_name: decoratorName,
                  decorator_args: decoratorArgs,
                });
              }
            });
          }

          if (param.name) {
            const nameKind = ts.SyntaxKind[param.name.kind];
            if (nameKind === "Identifier") {
              const id = param.name as ts.Identifier;
              paramName = id.text || id.escapedText?.toString() || "";
            } else if (nameKind === "ObjectBindingPattern") {
              const pattern = param.name as ts.ObjectBindingPattern;
              pattern.elements.forEach((element) => {
                if (element.name && (element.name as ts.Identifier).text) {
                  func_params.push({
                    function_name: func_name,
                    function_line: func_line,
                    param_index: paramIndex,
                    param_name: (element.name as ts.Identifier).text,
                    param_type: paramType,
                  });
                }
              });
              return;
            } else if (nameKind === "ArrayBindingPattern") {
              const pattern = param.name as ts.ArrayBindingPattern;
              pattern.elements.forEach((element) => {
                if (
                  element.kind === ts.SyntaxKind.BindingElement &&
                  (element as ts.BindingElement).name
                ) {
                  const bindingName = (element as ts.BindingElement).name;
                  if ((bindingName as ts.Identifier).text) {
                    func_params.push({
                      function_name: func_name,
                      function_line: func_line,
                      param_index: paramIndex,
                      param_name: (bindingName as ts.Identifier).text,
                      param_type: paramType,
                    });
                  }
                }
              });
              return;
            }
          }

          if (paramName) {
            func_params.push({
              function_name: func_name,
              function_line: func_line,
              param_index: paramIndex,
              param_name: paramName,
              param_type: paramType,
            });
          }
        });
      }

      const decorators = ts.canHaveDecorators(node)
        ? ts.getDecorators(node)
        : undefined;
      if (decorators && decorators.length > 0) {
        decorators.forEach((decorator, decoratorIndex) => {
          let decoratorName = "";
          let decoratorLine = func_line;

          const decPos = sourceFile.getLineAndCharacterOfPosition(
            decorator.getStart(sourceFile),
          );
          decoratorLine = decPos.line + 1;

          if (decorator.expression) {
            if (decorator.expression.kind === ts.SyntaxKind.Identifier) {
              const id = decorator.expression as ts.Identifier;
              decoratorName = id.text || id.escapedText?.toString() || "";
            } else if (
              decorator.expression.kind === ts.SyntaxKind.CallExpression
            ) {
              const callExpr = decorator.expression as ts.CallExpression;
              if (
                callExpr.expression &&
                callExpr.expression.kind === ts.SyntaxKind.Identifier
              ) {
                const id = callExpr.expression as ts.Identifier;
                decoratorName = id.text || id.escapedText?.toString() || "";
              }

              if (callExpr.arguments && callExpr.arguments.length > 0) {
                callExpr.arguments.forEach((arg, argIndex) => {
                  let argValue = "";
                  if (arg.kind === ts.SyntaxKind.StringLiteral) {
                    argValue = (arg as ts.StringLiteral).text;
                  } else if (
                    arg.kind === ts.SyntaxKind.ObjectLiteralExpression
                  ) {
                    argValue = arg.getText(sourceFile);
                  } else {
                    argValue = arg.getText
                      ? arg.getText(sourceFile)
                      : "[complex]";
                  }

                  func_decorator_args.push({
                    function_name: func_name,
                    function_line: func_line,
                    decorator_index: decoratorIndex,
                    arg_index: argIndex,
                    arg_value: argValue,
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
              decorator_line: decoratorLine,
            });
          }
        });
      }

      if (checker) {
        const nameNode = (node as ts.FunctionDeclaration).name || node;
        const symbol = checker.getSymbolAtLocation(nameNode);
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
            if (
              typeof (type as any).isTypeParameter === "function" &&
              (type as any).isTypeParameter()
            ) {
              func_entry.is_generic = true;
            }

            const callSignatures = type.getCallSignatures();
            if (callSignatures && callSignatures.length > 0) {
              const returnType = callSignatures[0].getReturnType();
              func_entry.return_type = checker.typeToString(returnType);
            }

            const baseTypes = (type as any).getBaseTypes
              ? (type as any).getBaseTypes()
              : null;
            if (baseTypes && baseTypes.length > 0) {
              func_entry.extends_type = baseTypes
                .map((t: ts.Type) => checker.typeToString(t))
                .join(", ");
            }
          }
        }
      }

      functions.push(func_entry);
    }

    ts.forEachChild(node, traverse);
  }

  traverse(sourceFile);

  logger.debug(
    `extractFunctions: Extracted ${functions.length} functions, ${func_params.length} params, ${func_decorators.length} decorators`,
  );

  return {
    functions,
    func_params,
    func_decorators,
    func_decorator_args,
    func_param_decorators,
  };
}

interface ExtractClassesResult {
  classes: IClass[];
  class_decorators: IClassDecorator[];
  class_decorator_args: IClassDecoratorArg[];
}

export function extractClasses(
  sourceFile: ts.SourceFile,
  checker: ts.TypeChecker | null,
  ts: typeof import("typescript"),
  filePath: string,
  scopeMap: Map<number, string>,
): ExtractClassesResult {
  const classes: IClass[] = [];
  const class_decorators: IClassDecorator[] = [];
  const class_decorator_args: IClassDecoratorArg[] = [];

  function traverse(node: ts.Node): void {
    if (!node) return;
    const kind = ts.SyntaxKind[node.kind];

    if (kind === "ClassDeclaration" || kind === "ClassExpression") {
      const classNode = node as ts.ClassDeclaration | ts.ClassExpression;
      const { line, character } = sourceFile.getLineAndCharacterOfPosition(
        node.getStart(sourceFile),
      );
      const class_line = line + 1;

      let className = classNode.name
        ? classNode.name.text ||
          classNode.name.escapedText?.toString() ||
          "UnknownClass"
        : "UnknownClass";

      if (className === "UnknownClass" && classNode.parent) {
        const parentKind = ts.SyntaxKind[classNode.parent.kind];
        if (parentKind === "VariableDeclaration") {
          const varDecl = classNode.parent as ts.VariableDeclaration;
          if (varDecl.name) {
            className =
              (varDecl.name as ts.Identifier).text ||
              (varDecl.name as ts.Identifier).escapedText?.toString() ||
              "UnknownClass";
          }
        } else if (parentKind === "ExportAssignment") {
          className = "DefaultExportClass";
        }
      }

      if (className === "UnknownClass") {
        className = "AnonymousClass";
      }

      const classEntry: IClass = {
        line: class_line,
        col: character,
        name: className,
        type: "class",
        kind: kind,
        extends: [],
        implements: [],
        properties: [],
        methods: [],
      };

      if (checker && classNode.name) {
        let symbol = checker.getSymbolAtLocation(classNode.name);

        if (!symbol && ts.isVariableDeclaration(classNode.parent)) {
          symbol = checker.getSymbolAtLocation(
            (classNode.parent as ts.VariableDeclaration).name,
          );
        }

        if (symbol) {
          const type = checker.getTypeOfSymbolAtLocation(symbol, node);
          if (type) {
            classEntry.type_annotation = checker.typeToString(type);
          }

          const instanceType = checker.getDeclaredTypeOfSymbol(symbol);

          const baseTypes = instanceType.getBaseTypes
            ? instanceType.getBaseTypes()
            : [];
          if (baseTypes && baseTypes.length > 0) {
            classEntry.extends = baseTypes.map((t) => checker.typeToString(t));
            classEntry.extends_type = classEntry.extends[0] || null;
          }

          const properties = instanceType.getProperties
            ? instanceType.getProperties()
            : [];

          for (const prop of properties) {
            const propName = prop.getName();
            if (propName.startsWith("__")) continue;

            const propType = checker.getTypeOfSymbolAtLocation(prop, node);
            const propTypeString = checker.typeToString(propType);

            const callSignatures = propType.getCallSignatures();

            let isInherited = true;
            const declarations = prop.getDeclarations();
            if (declarations && declarations.length > 0) {
              for (const decl of declarations) {
                let parent = decl.parent;
                while (parent) {
                  if (parent === classNode) {
                    isInherited = false;
                    break;
                  }
                  parent = parent.parent;
                }
                if (!isInherited) break;
              }
            }

            if (callSignatures && callSignatures.length > 0) {
              classEntry.methods!.push({
                name: propName,
                signature: propTypeString,
                inherited: isInherited,
              });
            } else {
              classEntry.properties!.push({
                name: propName,
                type: propTypeString,
                inherited: isInherited,
              });
            }
          }
        }
      } else {
        if (classNode.heritageClauses) {
          for (const clause of classNode.heritageClauses) {
            if (
              clause.token === ts.SyntaxKind.ExtendsKeyword &&
              clause.types &&
              clause.types.length > 0
            ) {
              const extendsType = clause.types[0];
              const extendsText = extendsType.expression
                ? (extendsType.expression as ts.Identifier).text ||
                  (
                    extendsType.expression as ts.Identifier
                  ).escapedText?.toString()
                : null;
              classEntry.extends_type = extendsText || null;
              if (extendsText) {
                classEntry.extends = [extendsText];
              }
            }
          }
        }
      }

      if (classNode.heritageClauses) {
        for (const clause of classNode.heritageClauses) {
          if (clause.token === ts.SyntaxKind.ImplementsKeyword) {
            classEntry.implements = clause.types.map((t) =>
              t.expression.getText(sourceFile),
            );
          }
        }
      }

      if (classNode.typeParameters && classNode.typeParameters.length > 0) {
        classEntry.has_type_params = true;
        classEntry.type_params = classNode.typeParameters
          .map((tp) => {
            const paramName = tp.name
              ? tp.name.text || tp.name.escapedText?.toString()
              : "T";
            if (tp.constraint) {
              const constraintText = tp.constraint.getText
                ? tp.constraint.getText(sourceFile)
                : "";
              return `${paramName} extends ${constraintText}`;
            }
            return paramName || "T";
          })
          .join(", ");
      }

      const decorators = ts.canHaveDecorators(node)
        ? ts.getDecorators(node)
        : undefined;
      if (decorators && decorators.length > 0) {
        decorators.forEach((decorator, decoratorIndex) => {
          let decoratorName = "";
          let decoratorLine = class_line;

          const decPos = sourceFile.getLineAndCharacterOfPosition(
            decorator.getStart(sourceFile),
          );
          decoratorLine = decPos.line + 1;

          if (decorator.expression) {
            if (decorator.expression.kind === ts.SyntaxKind.Identifier) {
              const id = decorator.expression as ts.Identifier;
              decoratorName = id.text || id.escapedText?.toString() || "";
            } else if (
              decorator.expression.kind === ts.SyntaxKind.CallExpression
            ) {
              const callExpr = decorator.expression as ts.CallExpression;
              if (
                callExpr.expression &&
                callExpr.expression.kind === ts.SyntaxKind.Identifier
              ) {
                const id = callExpr.expression as ts.Identifier;
                decoratorName = id.text || id.escapedText?.toString() || "";
              }

              if (callExpr.arguments && callExpr.arguments.length > 0) {
                callExpr.arguments.forEach((arg, argIndex) => {
                  let argValue = "";
                  if (arg.kind === ts.SyntaxKind.StringLiteral) {
                    argValue = (arg as ts.StringLiteral).text;
                  } else if (arg.kind === ts.SyntaxKind.NumericLiteral) {
                    argValue = (arg as ts.NumericLiteral).text;
                  } else if (arg.kind === ts.SyntaxKind.TrueKeyword) {
                    argValue = "true";
                  } else if (arg.kind === ts.SyntaxKind.FalseKeyword) {
                    argValue = "false";
                  } else if (
                    arg.kind === ts.SyntaxKind.ObjectLiteralExpression
                  ) {
                    argValue = arg.getText(sourceFile);
                  } else {
                    argValue = arg.getText
                      ? arg.getText(sourceFile)
                      : "[complex]";
                  }

                  class_decorator_args.push({
                    class_name: className,
                    class_line: class_line,
                    decorator_index: decoratorIndex,
                    arg_index: argIndex,
                    arg_value: argValue,
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
              decorator_line: decoratorLine,
            });
          }
        });
      }

      classes.push(classEntry);
    }

    ts.forEachChild(node, traverse);
  }

  traverse(sourceFile);

  return {
    classes,
    class_decorators,
    class_decorator_args,
  };
}

interface ExtractInterfacesResult {
  interfaces: IInterface[];
}

export function extractInterfaces(
  sourceFile: ts.SourceFile,
  checker: ts.TypeChecker | null,
  ts: typeof import("typescript"),
  filePath: string,
): ExtractInterfacesResult {
  const interfaces: IInterface[] = [];

  function traverse(node: ts.Node): void {
    if (!node) return;
    const kind = ts.SyntaxKind[node.kind];

    if (kind === "InterfaceDeclaration") {
      const ifaceNode = node as ts.InterfaceDeclaration;
      const { line, character } = sourceFile.getLineAndCharacterOfPosition(
        node.getStart(sourceFile),
      );

      const ifaceName = ifaceNode.name ? ifaceNode.name.text : "UnknownInterface";

      const ifaceEntry: IInterface = {
        line: line + 1,
        col: character,
        name: ifaceName,
        type: "interface",
        kind: "InterfaceDeclaration",
        extends: [],
        properties: [],
        methods: [],
      };

      // Extract extends clause
      if (ifaceNode.heritageClauses) {
        for (const clause of ifaceNode.heritageClauses) {
          if (clause.token === ts.SyntaxKind.ExtendsKeyword) {
            ifaceEntry.extends = clause.types.map((t) =>
              t.expression.getText(sourceFile),
            );
          }
        }
      }

      // Extract type parameters
      if (ifaceNode.typeParameters && ifaceNode.typeParameters.length > 0) {
        ifaceEntry.has_type_params = true;
        ifaceEntry.type_params = ifaceNode.typeParameters
          .map((tp) => tp.name.text)
          .join(", ");
      }

      // Extract members (properties and methods)
      for (const member of ifaceNode.members) {
        const memberKind = ts.SyntaxKind[member.kind];
        if (memberKind === "PropertySignature") {
          const prop = member as ts.PropertySignature;
          const propName = prop.name
            ? (prop.name as ts.Identifier).text ||
              (prop.name as ts.Identifier).escapedText?.toString() ||
              ""
            : "";
          const propType = prop.type ? prop.type.getText(sourceFile) : "any";
          if (propName) {
            ifaceEntry.properties!.push({
              name: propName,
              type: propType,
              inherited: false,
            });
          }
        } else if (memberKind === "MethodSignature") {
          const method = member as ts.MethodSignature;
          const methodName = method.name
            ? (method.name as ts.Identifier).text ||
              (method.name as ts.Identifier).escapedText?.toString() ||
              ""
            : "";
          if (methodName) {
            const signature = method.getText(sourceFile);
            ifaceEntry.methods!.push({
              name: methodName,
              signature: signature,
              inherited: false,
            });
          }
        }
      }

      interfaces.push(ifaceEntry);
    }

    // Also handle TypeAliasDeclaration for type aliases (stored as interfaces)
    if (kind === "TypeAliasDeclaration") {
      const typeNode = node as ts.TypeAliasDeclaration;
      const { line, character } = sourceFile.getLineAndCharacterOfPosition(
        node.getStart(sourceFile),
      );

      const typeEntry: IInterface = {
        line: line + 1,
        col: character,
        name: typeNode.name.text,
        type: "interface",
        kind: "TypeAliasDeclaration",
        extends: [],
        properties: [],
        methods: [],
      };

      // Extract type parameters for type aliases
      if (typeNode.typeParameters && typeNode.typeParameters.length > 0) {
        typeEntry.has_type_params = true;
        typeEntry.type_params = typeNode.typeParameters
          .map((tp) => tp.name.text)
          .join(", ");
      }

      interfaces.push(typeEntry);
    }

    ts.forEachChild(node, traverse);
  }

  traverse(sourceFile);
  return { interfaces };
}

export function extractClassProperties(
  sourceFile: ts.SourceFile,
  ts: typeof import("typescript"),
  filePath: string,
  classes: IClass[],
): IClassProperty[] {
  const properties: IClassProperty[] = [];
  let currentClass: string | null = null;

  function traverse(node: ts.Node): void {
    if (!node) return;
    const kind = ts.SyntaxKind[node.kind];

    if (kind === "ClassDeclaration" || kind === "ClassExpression") {
      const classNode = node as ts.ClassDeclaration | ts.ClassExpression;
      const previousClass = currentClass;
      currentClass = classNode.name
        ? classNode.name.text ||
          classNode.name.escapedText?.toString() ||
          "UnknownClass"
        : "UnknownClass";

      if (currentClass === "UnknownClass" && classNode.parent) {
        const parentKind = ts.SyntaxKind[classNode.parent.kind];
        if (parentKind === "VariableDeclaration") {
          const varDecl = classNode.parent as ts.VariableDeclaration;
          if (varDecl.name) {
            currentClass =
              (varDecl.name as ts.Identifier).text ||
              (varDecl.name as ts.Identifier).escapedText?.toString() ||
              "UnknownClass";
          }
        }
      }

      ts.forEachChild(node, traverse);
      currentClass = previousClass;
      return;
    }

    if (kind === "PropertyDeclaration" && currentClass) {
      const propNode = node as ts.PropertyDeclaration;
      const { line } = sourceFile.getLineAndCharacterOfPosition(
        node.getStart(sourceFile),
      );
      const propertyName = propNode.name
        ? (propNode.name as ts.Identifier).text ||
          (propNode.name as ts.Identifier).escapedText?.toString() ||
          ""
        : "";

      if (!propertyName) {
        ts.forEachChild(node, traverse);
        return;
      }

      const property: IClassProperty = {
        line: line + 1,
        class_name: currentClass,
        property_name: propertyName,
        property_type: null,
        is_optional: false,
        is_readonly: false,
        access_modifier: null,
        has_declare: false,
        initializer: null,
      };

      if (propNode.type) {
        property.property_type = propNode.type.getText(sourceFile);
      }

      if (propNode.questionToken) {
        property.is_optional = true;
      }

      const modifiers = ts.canHaveModifiers(node)
        ? ts.getModifiers(node)
        : undefined;
      if (modifiers) {
        for (const modifier of modifiers) {
          const modifierKind = ts.SyntaxKind[modifier.kind];
          if (modifierKind === "ReadonlyKeyword") {
            property.is_readonly = true;
          } else if (modifierKind === "PrivateKeyword") {
            property.access_modifier = "private";
          } else if (modifierKind === "ProtectedKeyword") {
            property.access_modifier = "protected";
          } else if (modifierKind === "PublicKeyword") {
            property.access_modifier = "public";
          } else if (modifierKind === "DeclareKeyword") {
            property.has_declare = true;
          }
        }
      }

      if (propNode.initializer) {
        property.initializer = propNode.initializer
          .getText(sourceFile)
          .substring(0, 5000);
      }

      properties.push(property);
    }

    ts.forEachChild(node, traverse);
  }

  traverse(sourceFile);
  return properties;
}

interface FunctionRange {
  name: string;
  start: number;
  end: number;
  depth: number;
}

export function buildScopeMap(
  sourceFile: ts.SourceFile,
  ts: typeof import("typescript"),
): Map<number, string> {
  const functionRanges: FunctionRange[] = [];
  const classStack: string[] = [];

  function getNameFromParent(
    node: ts.Node,
    parent: ts.Node | null,
    ts: typeof import("typescript"),
    classStack: string[],
  ): string {
    if (!parent) return "<anonymous>";

    const parentKind = ts.SyntaxKind[parent.kind];

    if (parentKind === "VariableDeclaration") {
      const varDecl = parent as ts.VariableDeclaration;
      if (varDecl.name) {
        const varName =
          (varDecl.name as ts.Identifier).text ||
          (varDecl.name as ts.Identifier).escapedText?.toString() ||
          "anonymous";
        return classStack.length > 0
          ? classStack[classStack.length - 1] + "." + varName
          : varName;
      }
    }

    if (parentKind === "PropertyAssignment") {
      const propAssign = parent as ts.PropertyAssignment;
      if (propAssign.name) {
        const propName =
          (propAssign.name as ts.Identifier).text ||
          (propAssign.name as ts.Identifier).escapedText?.toString() ||
          "anonymous";
        return classStack.length > 0
          ? classStack[classStack.length - 1] + "." + propName
          : propName;
      }
    }

    if (parentKind === "ShorthandPropertyAssignment") {
      const shorthand = parent as ts.ShorthandPropertyAssignment;
      if (shorthand.name) {
        const propName =
          shorthand.name.text ||
          shorthand.name.escapedText?.toString() ||
          "anonymous";
        return classStack.length > 0
          ? classStack[classStack.length - 1] + "." + propName
          : propName;
      }
    }

    if (parentKind === "BinaryExpression") {
      const binExpr = parent as ts.BinaryExpression;
      if (binExpr.left) {
        const leftText = binExpr.left.getText ? binExpr.left.getText() : "";
        if (leftText) {
          return leftText;
        }
      }
    }

    // Handle arrow functions passed as arguments: handler(async (req, res) => {})
    if (parentKind === "CallExpression") {
      const callExpr = parent as ts.CallExpression;
      const calleeName = callExpr.expression.getText
        ? callExpr.expression.getText(sourceFile)
        : "";

      // Find which argument index this arrow function is
      const argIndex =
        callExpr.arguments?.findIndex((arg) => arg === node) ?? -1;

      if (calleeName && argIndex >= 0) {
        // Extract short callee name (e.g., "handler" from "router.post")
        const shortCallee = calleeName.includes(".")
          ? calleeName.split(".").pop() || calleeName
          : calleeName;
        return `${shortCallee}_callback${argIndex}`;
      }

      // Fallback: use line number for unnamed callbacks
      const { line } = sourceFile.getLineAndCharacterOfPosition(
        node.getStart(sourceFile),
      );
      return `callback@${line + 1}`;
    }

    return "<anonymous>";
  }

  function collectFunctions(
    node: ts.Node,
    depth: number = 0,
    parent: ts.Node | null = null,
  ): void {
    if (depth > 100 || !node) return;

    const kind = ts.SyntaxKind[node.kind];
    let startLine = sourceFile.getLineAndCharacterOfPosition(
      node.getStart(sourceFile),
    ).line;
    let endLine = sourceFile.getLineAndCharacterOfPosition(node.end).line;

    if (kind === "ClassDeclaration") {
      const classNode = node as ts.ClassDeclaration;
      const className = classNode.name
        ? classNode.name.text ||
          classNode.name.escapedText?.toString() ||
          "UnknownClass"
        : "UnknownClass";
      classStack.push(className);
      ts.forEachChild(node, (child) =>
        collectFunctions(child, depth + 1, node),
      );
      classStack.pop();
      return;
    }

    let funcName: string | null = null;
    let actualFunctionNode: ts.Node = node;

    if (kind === "FunctionDeclaration") {
      const funcNode = node as ts.FunctionDeclaration;
      funcName = funcNode.name
        ? funcNode.name.text ||
          funcNode.name.escapedText?.toString() ||
          "anonymous"
        : "anonymous";
    } else if (kind === "MethodDeclaration") {
      const methodNode = node as ts.MethodDeclaration;
      const methodName = methodNode.name
        ? (methodNode.name as ts.Identifier).text ||
          (methodNode.name as ts.Identifier).escapedText?.toString() ||
          "anonymous"
        : "anonymous";
      funcName =
        classStack.length > 0
          ? classStack[classStack.length - 1] + "." + methodName
          : methodName;
    } else if (kind === "PropertyDeclaration") {
      const propNode = node as ts.PropertyDeclaration;
      if (propNode.initializer) {
        const initKind = ts.SyntaxKind[propNode.initializer.kind];
        if (initKind === "ArrowFunction" || initKind === "FunctionExpression") {
          const propName = propNode.name
            ? (propNode.name as ts.Identifier).text ||
              (propNode.name as ts.Identifier).escapedText?.toString() ||
              "anonymous"
            : "anonymous";
          funcName =
            classStack.length > 0
              ? classStack[classStack.length - 1] + "." + propName
              : propName;
        } else if (initKind === "CallExpression") {
          const callExpr = propNode.initializer as ts.CallExpression;
          if (callExpr.arguments && callExpr.arguments.length > 0) {
            const firstArg = callExpr.arguments[0];
            const firstArgKind = ts.SyntaxKind[firstArg.kind];
            if (
              firstArgKind === "ArrowFunction" ||
              firstArgKind === "FunctionExpression"
            ) {
              const propName = propNode.name
                ? (propNode.name as ts.Identifier).text ||
                  (propNode.name as ts.Identifier).escapedText?.toString() ||
                  "anonymous"
                : "anonymous";
              funcName =
                classStack.length > 0
                  ? classStack[classStack.length - 1] + "." + propName
                  : propName;
              actualFunctionNode = firstArg;
              startLine = sourceFile.getLineAndCharacterOfPosition(
                firstArg.getStart(sourceFile),
              ).line;
              endLine = sourceFile.getLineAndCharacterOfPosition(
                firstArg.end,
              ).line;
            }
          }
        }
      }
    } else if (kind === "Constructor") {
      funcName =
        classStack.length > 0
          ? classStack[classStack.length - 1] + ".constructor"
          : "constructor";
    } else if (kind === "GetAccessor" || kind === "SetAccessor") {
      const accessorNode = node as ts.AccessorDeclaration;
      const accessorName = accessorNode.name
        ? (accessorNode.name as ts.Identifier).text ||
          (accessorNode.name as ts.Identifier).escapedText?.toString() ||
          "anonymous"
        : "anonymous";
      const prefix = kind === "GetAccessor" ? "get " : "set ";
      funcName =
        classStack.length > 0
          ? classStack[classStack.length - 1] + "." + prefix + accessorName
          : prefix + accessorName;
    } else if (kind === "ArrowFunction" || kind === "FunctionExpression") {
      funcName = getNameFromParent(node, parent, ts, classStack);
    }

    if (funcName && funcName !== "anonymous" && funcName !== "<anonymous>") {
      functionRanges.push({
        name: funcName,
        start: startLine + 1,
        end: endLine + 1,
        depth: depth,
      });
    }

    ts.forEachChild(node, (child) => collectFunctions(child, depth + 1, node));
  }

  collectFunctions(sourceFile);

  const scopeMap = new Map<number, string>();

  functionRanges.sort((a, b) => {
    if (a.start !== b.start) return a.start - b.start;
    return b.depth - a.depth;
  });

  for (const func of functionRanges) {
    for (let line = func.start; line <= func.end; line++) {
      scopeMap.set(line, func.name);
    }
  }

  return scopeMap;
}

export function countNodes(
  node: ts.Node,
  ts: typeof import("typescript"),
): number {
  if (!node) return 0;

  let count = 1;

  ts.forEachChild(node, (child) => {
    count += countNodes(child, ts);
  });

  return count;
}
