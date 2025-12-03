import * as ts from "typescript";
import type {
  SequelizeModel,
  SequelizeModelField,
  SequelizeAssociation,
  Class as IClass,
  FunctionCallArg as IFunctionCallArg,
} from "../schema.js";

interface ExtractSequelizeResult {
  sequelize_models: SequelizeModel[];
  sequelize_model_fields: SequelizeModelField[];
  sequelize_associations: SequelizeAssociation[];
}

const SEQUELIZE_DATA_TYPES = new Set([
  "STRING",
  "TEXT",
  "CITEXT",
  "TSVECTOR",
  "INTEGER",
  "BIGINT",
  "FLOAT",
  "REAL",
  "DOUBLE",
  "DECIMAL",
  "BOOLEAN",
  "DATE",
  "DATEONLY",
  "TIME",
  "NOW",
  "UUID",
  "UUIDV1",
  "UUIDV4",
  "HSTORE",
  "JSON",
  "JSONB",
  "ARRAY",
  "RANGE",
  "GEOMETRY",
  "GEOGRAPHY",
  "BLOB",
  "ENUM",
  "VIRTUAL",
  "CIDR",
  "INET",
  "MACADDR",
]);

const ASSOCIATION_METHODS = new Set([
  "hasOne",
  "hasMany",
  "belongsTo",
  "belongsToMany",
]);

export function extractSequelizeModels(
  sourceFile: ts.SourceFile,
  classes: IClass[],
  functionCallArgs: IFunctionCallArg[],
  filePath: string,
): ExtractSequelizeResult {
  const sequelize_models: SequelizeModel[] = [];
  const sequelize_model_fields: SequelizeModelField[] = [];
  const sequelize_associations: SequelizeAssociation[] = [];

  const processedModels = new Set<string>();

  function visit(node: ts.Node): void {
    if (ts.isCallExpression(node)) {
      const expr = node.expression;
      if (ts.isPropertyAccessExpression(expr) && expr.name.text === "init") {
        const modelName = expr.expression.getText(sourceFile);
        if (!processedModels.has(modelName)) {
          processedModels.add(modelName);

          const modelEntry: SequelizeModel = {
            file: filePath,
            line:
              sourceFile.getLineAndCharacterOfPosition(node.getStart()).line +
              1,
            model_name: modelName,
            table_name: null,
            extends_model: null,
          };

          if (
            node.arguments.length > 0 &&
            ts.isObjectLiteralExpression(node.arguments[0])
          ) {
            const fieldsObj = node.arguments[0];
            for (const prop of fieldsObj.properties) {
              if (ts.isPropertyAssignment(prop) && ts.isIdentifier(prop.name)) {
                const fieldName = prop.name.text;
                const fieldDef = parseSequelizeField(
                  prop.initializer,
                  sourceFile,
                  modelName,
                  fieldName,
                  filePath,
                );
                if (fieldDef) {
                  sequelize_model_fields.push(fieldDef);
                }
              }
            }
          }

          if (
            node.arguments.length > 1 &&
            ts.isObjectLiteralExpression(node.arguments[1])
          ) {
            const optionsObj = node.arguments[1];
            for (const prop of optionsObj.properties) {
              if (ts.isPropertyAssignment(prop) && ts.isIdentifier(prop.name)) {
                if (
                  prop.name.text === "tableName" &&
                  ts.isStringLiteral(prop.initializer)
                ) {
                  modelEntry.table_name = prop.initializer.text;
                }
              }
            }
          }

          sequelize_models.push(modelEntry);
        }
      }

      if (ts.isPropertyAccessExpression(expr)) {
        const methodName = expr.name.text;
        if (ASSOCIATION_METHODS.has(methodName)) {
          const sourceModel = expr.expression.getText(sourceFile);
          if (node.arguments.length > 0) {
            const targetArg = node.arguments[0];
            const targetModel = targetArg.getText(sourceFile);

            let foreignKey: string | null = null;
            let alias: string | null = null;

            if (
              node.arguments.length > 1 &&
              ts.isObjectLiteralExpression(node.arguments[1])
            ) {
              const optionsObj = node.arguments[1];
              for (const prop of optionsObj.properties) {
                if (
                  ts.isPropertyAssignment(prop) &&
                  ts.isIdentifier(prop.name)
                ) {
                  if (prop.name.text === "foreignKey") {
                    if (ts.isStringLiteral(prop.initializer)) {
                      foreignKey = prop.initializer.text;
                    } else if (ts.isObjectLiteralExpression(prop.initializer)) {
                      for (const fkProp of prop.initializer.properties) {
                        if (
                          ts.isPropertyAssignment(fkProp) &&
                          ts.isIdentifier(fkProp.name) &&
                          fkProp.name.text === "name" &&
                          ts.isStringLiteral(fkProp.initializer)
                        ) {
                          foreignKey = fkProp.initializer.text;
                        }
                      }
                    }
                  }
                  if (
                    prop.name.text === "as" &&
                    ts.isStringLiteral(prop.initializer)
                  ) {
                    alias = prop.initializer.text;
                  }
                }
              }
            }

            sequelize_associations.push({
              file: filePath,
              line:
                sourceFile.getLineAndCharacterOfPosition(node.getStart()).line +
                1,
              source_model: sourceModel,
              target_model: targetModel,
              association_type: methodName,
              foreign_key: foreignKey,
              alias: alias,
            });
          }
        }
      }
    }

    if (ts.isClassDeclaration(node) && node.name) {
      const className = node.name.text;
      if (!processedModels.has(className)) {
        if (node.heritageClauses) {
          for (const clause of node.heritageClauses) {
            if (clause.token === ts.SyntaxKind.ExtendsKeyword) {
              for (const type of clause.types) {
                const baseType = type.expression.getText(sourceFile);
                if (baseType === "Model" || baseType.includes("Model")) {
                  processedModels.add(className);

                  sequelize_models.push({
                    file: filePath,
                    line:
                      sourceFile.getLineAndCharacterOfPosition(node.getStart())
                        .line + 1,
                    model_name: className,
                    table_name: null,
                    extends_model: baseType,
                  });

                  for (const member of node.members) {
                    if (
                      ts.isPropertyDeclaration(member) &&
                      member.name &&
                      ts.isIdentifier(member.name)
                    ) {
                      const fieldName = member.name.text;
                      if (fieldName.startsWith("_")) continue;

                      let dataType = "unknown";
                      let isPrimaryKey = fieldName === "id";
                      let isNullable = false;

                      if (member.type) {
                        dataType = member.type.getText(sourceFile);
                        if (dataType.includes("null")) {
                          isNullable = true;
                        }
                      }

                      const decorators = ts.getDecorators?.(member) || [];
                      for (const dec of decorators) {
                        if (ts.isCallExpression(dec.expression)) {
                          const decName =
                            dec.expression.expression.getText(sourceFile);
                          if (decName === "PrimaryKey") isPrimaryKey = true;
                          if (decName === "AllowNull") isNullable = true;
                          if (
                            decName === "Column" &&
                            dec.expression.arguments.length > 0
                          ) {
                            const arg = dec.expression.arguments[0];
                            if (ts.isPropertyAccessExpression(arg)) {
                              dataType = arg.name.text;
                            }
                          }
                        }
                      }

                      sequelize_model_fields.push({
                        file: filePath,
                        model_name: className,
                        field_name: fieldName,
                        data_type: dataType,
                        is_primary_key: isPrimaryKey,
                        is_nullable: isNullable,
                        is_unique: false,
                        default_value: null,
                      });
                    }
                  }
                }
              }
            }
          }
        }
      }
    }

    if (ts.isCallExpression(node)) {
      const expr = node.expression;
      if (ts.isPropertyAccessExpression(expr) && expr.name.text === "define") {
        if (node.arguments.length >= 2) {
          const modelNameArg = node.arguments[0];
          const fieldsArg = node.arguments[1];

          let modelName = "AnonymousModel";
          if (ts.isStringLiteral(modelNameArg)) {
            modelName = modelNameArg.text;
          }

          if (!processedModels.has(modelName)) {
            processedModels.add(modelName);

            const modelEntry: SequelizeModel = {
              file: filePath,
              line:
                sourceFile.getLineAndCharacterOfPosition(node.getStart()).line +
                1,
              model_name: modelName,
              table_name: null,
              extends_model: null,
            };

            if (ts.isObjectLiteralExpression(fieldsArg)) {
              for (const prop of fieldsArg.properties) {
                if (
                  ts.isPropertyAssignment(prop) &&
                  ts.isIdentifier(prop.name)
                ) {
                  const fieldName = prop.name.text;
                  const fieldDef = parseSequelizeField(
                    prop.initializer,
                    sourceFile,
                    modelName,
                    fieldName,
                    filePath,
                  );
                  if (fieldDef) {
                    sequelize_model_fields.push(fieldDef);
                  }
                }
              }
            }

            if (
              node.arguments.length > 2 &&
              ts.isObjectLiteralExpression(node.arguments[2])
            ) {
              const optionsObj = node.arguments[2];
              for (const prop of optionsObj.properties) {
                if (
                  ts.isPropertyAssignment(prop) &&
                  ts.isIdentifier(prop.name)
                ) {
                  if (
                    prop.name.text === "tableName" &&
                    ts.isStringLiteral(prop.initializer)
                  ) {
                    modelEntry.table_name = prop.initializer.text;
                  }
                }
              }
            }

            sequelize_models.push(modelEntry);
          }
        }
      }
    }

    ts.forEachChild(node, visit);
  }

  visit(sourceFile);

  return { sequelize_models, sequelize_model_fields, sequelize_associations };
}

function parseSequelizeField(
  initializer: ts.Expression,
  sourceFile: ts.SourceFile,
  modelName: string,
  fieldName: string,
  filePath: string,
): SequelizeModelField | null {
  let dataType = "unknown";
  let isPrimaryKey = fieldName === "id";
  let isNullable = true;
  let isUnique = false;
  let defaultValue: string | null = null;

  if (ts.isPropertyAccessExpression(initializer)) {
    dataType = initializer.name.text;
  } else if (
    ts.isCallExpression(initializer) &&
    ts.isPropertyAccessExpression(initializer.expression)
  ) {
    dataType = initializer.expression.name.text;
    if (initializer.arguments.length > 0) {
      const arg = initializer.arguments[0].getText(sourceFile);
      dataType = `${dataType}(${arg})`;
    }
  } else if (ts.isObjectLiteralExpression(initializer)) {
    for (const prop of initializer.properties) {
      if (!ts.isPropertyAssignment(prop) || !ts.isIdentifier(prop.name))
        continue;

      const propName = prop.name.text;
      const propValue = prop.initializer;

      if (propName === "type") {
        if (ts.isPropertyAccessExpression(propValue)) {
          dataType = propValue.name.text;
        } else if (
          ts.isCallExpression(propValue) &&
          ts.isPropertyAccessExpression(propValue.expression)
        ) {
          dataType = propValue.expression.name.text;
        }
      } else if (propName === "primaryKey") {
        isPrimaryKey = propValue.kind === ts.SyntaxKind.TrueKeyword;
      } else if (propName === "allowNull") {
        isNullable = propValue.kind === ts.SyntaxKind.TrueKeyword;
      } else if (propName === "unique") {
        isUnique = propValue.kind === ts.SyntaxKind.TrueKeyword;
      } else if (propName === "defaultValue") {
        defaultValue = propValue.getText(sourceFile);
      }
    }
  }

  if (dataType !== "unknown" || ts.isObjectLiteralExpression(initializer)) {
    return {
      file: filePath,
      model_name: modelName,
      field_name: fieldName,
      data_type: dataType,
      is_primary_key: isPrimaryKey,
      is_nullable: isNullable,
      is_unique: isUnique,
      default_value: defaultValue,
    };
  }

  return null;
}

export { ExtractSequelizeResult };
