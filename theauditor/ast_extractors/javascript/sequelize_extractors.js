function parseModelFields(modelName, fieldsExpr, filePath) {
  const fields = [];
  const seenFields = new Set();

  if (!fieldsExpr || typeof fieldsExpr !== "string") {
    return fields;
  }

  const objectFieldPattern = /(\w+)\s*:\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}/g;

  let match;
  while ((match = objectFieldPattern.exec(fieldsExpr)) !== null) {
    const fieldName = match[1];
    const fieldBody = match[2];

    if (
      fieldName === "type" ||
      fieldName === "references" ||
      fieldName === "key"
    )
      continue;
    if (seenFields.has(fieldName)) continue;

    const typeMatch = fieldBody.match(/type\s*:\s*DataTypes\.(\w+)/);
    if (!typeMatch) continue;

    seenFields.add(fieldName);

    const dataType = typeMatch[1];
    let isPrimaryKey = 0;
    let isNullable = 1;
    let isUnique = 0;
    let defaultValue = null;

    if (/primaryKey\s*:\s*true/i.test(fieldBody)) isPrimaryKey = 1;
    if (/allowNull\s*:\s*false/i.test(fieldBody)) isNullable = 0;
    if (/unique\s*:\s*true/i.test(fieldBody)) isUnique = 1;

    const defaultMatch = fieldBody.match(
      /defaultValue\s*:\s*(['"][^'"]*['"]|[\d.]+|true|false|null)/i,
    );
    if (defaultMatch) {
      defaultValue = defaultMatch[1].replace(/^['"]|['"]$/g, "");
    }

    fields.push({
      file: filePath,
      model_name: modelName,
      field_name: fieldName,
      data_type: dataType,
      is_primary_key: isPrimaryKey,
      is_nullable: isNullable,
      is_unique: isUnique,
      default_value: defaultValue,
    });
  }

  const simpleFieldPattern =
    /(\w+)\s*:\s*DataTypes\.(\w+)(?:\([^)]*\))?(?:\s*,|\s*$|\s*\})/g;

  while ((match = simpleFieldPattern.exec(fieldsExpr)) !== null) {
    const fieldName = match[1];

    if (fieldName === "type") continue;
    if (seenFields.has(fieldName)) continue;
    seenFields.add(fieldName);

    fields.push({
      file: filePath,
      model_name: modelName,
      field_name: fieldName,
      data_type: match[2],
      is_primary_key: 0,
      is_nullable: 1,
      is_unique: 0,
      default_value: null,
    });
  }

  return fields;
}

function extractSequelizeModels(
  functions,
  classes,
  functionCallArgs,
  imports,
  filePath,
) {
  const models = [];
  const associations = [];
  const model_fields = [];

  const hasSequelize =
    imports &&
    imports.some(
      (imp) => imp.module === "sequelize" || imp.module === "@sequelize/core",
    );

  if (!hasSequelize) {
    return {
      sequelize_models: models,
      sequelize_associations: associations,
      sequelize_model_fields: model_fields,
    };
  }

  for (const cls of classes) {
    const extendsModel = cls.extends_type && cls.extends_type.includes("Model");
    if (!extendsModel) continue;

    const modelName = cls.name;
    let tableName = null;

    for (const call of functionCallArgs) {
      if (
        call.callee_function &&
        call.callee_function.includes(".init") &&
        call.callee_function.includes(modelName)
      ) {
        if (call.argument_index === 0 && call.argument_expr) {
          const extractedFields = parseModelFields(
            modelName,
            call.argument_expr,
            filePath,
          );
          model_fields.push(...extractedFields);
        }

        if (call.argument_index === 1 && call.argument_expr) {
          const tableMatch = call.argument_expr.match(
            /tableName:\s*['"]([^'"]+)['"]/,
          );
          if (tableMatch) {
            tableName = tableMatch[1];
          }
        }
      }

      const associationMethods = [
        "hasMany",
        "belongsTo",
        "hasOne",
        "belongsToMany",
      ];
      for (const method of associationMethods) {
        if (
          call.callee_function &&
          call.callee_function.includes(`.${method}`) &&
          call.callee_function.includes(modelName)
        ) {
          let targetModel = null;
          let foreignKey = null;
          let throughTable = null;

          if (call.argument_index === 0 && call.argument_expr) {
            targetModel = call.argument_expr
              .replace(/require\(['"]\.(\/[^'"]+)['"]\)/g, "$1")
              .replace(/['"]/g, "")
              .trim();
          }

          if (call.argument_index === 1 && call.argument_expr) {
            const fkMatch = call.argument_expr.match(
              /foreignKey:\s*['"]([^'"]+)['"]/,
            );
            if (fkMatch) {
              foreignKey = fkMatch[1];
            }
            const throughMatch = call.argument_expr.match(
              /through:\s*['"]([^'"]+)['"]/,
            );
            if (throughMatch) {
              throughTable = throughMatch[1];
            }
          }

          if (targetModel) {
            associations.push({
              file: filePath,
              line: call.line,
              model_name: modelName,
              association_type: method,
              target_model: targetModel,
              foreign_key: foreignKey,
              through_table: throughTable,
            });

            if (targetModel !== modelName) {
              let inverseType = null;

              if (method === "hasMany") {
                inverseType = "belongsTo";
              } else if (method === "hasOne") {
                inverseType = "belongsTo";
              } else if (method === "belongsToMany") {
                inverseType = "belongsToMany";
              }

              if (inverseType) {
                associations.push({
                  file: filePath,
                  line: call.line,
                  model_name: targetModel,
                  association_type: inverseType,
                  target_model: modelName,
                  foreign_key: foreignKey,
                  through_table: throughTable,
                });
              }
            }
          }
        }
      }
    }

    models.push({
      file: filePath,
      line: cls.line,
      model_name: modelName,
      table_name: tableName,
      extends_model: true,
    });
  }

  return {
    sequelize_models: models,
    sequelize_associations: associations,
    sequelize_model_fields: model_fields,
  };
}
