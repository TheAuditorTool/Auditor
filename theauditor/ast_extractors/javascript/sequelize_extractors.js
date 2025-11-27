/**
 * Sequelize ORM Extractors
 *
 * Extracts Sequelize model definitions, associations, and relationships
 * from JavaScript/TypeScript codebases.
 *
 * STABILITY: MODERATE - Changes when Sequelize API updates or new patterns emerge.
 *
 * DEPENDENCIES: core_ast_extractors.js (uses functions, classes, returns)
 * USED BY: Indexer for ORM model detection and relationship mapping
 *
 * Architecture:
 * - Extracted from: framework_extractors.js (split 2025-10-31)
 * - Pattern: Detect class extends Model, Model.init(), associations
 * - Assembly: Concatenated after framework_extractors.js, before batch_templates.js
 *
 * Functions:
 * 1. extractSequelizeModels() - Detect Sequelize model classes and associations
 * 2. parseModelFields() - Extract field definitions from Model.init() first argument
 */

/**
 * Parse field definitions from Model.init() first argument.
 * Extracts: field_name, data_type, is_primary_key, is_nullable, is_unique, default_value
 *
 * @param {string} modelName - Name of the model class
 * @param {string} fieldsExpr - The fields object expression from argument_expr
 * @param {string} filePath - Relative file path for database records
 * @returns {Array} - Array of field records
 */
function parseModelFields(modelName, fieldsExpr, filePath) {
    const fields = [];
    const seenFields = new Set();

    if (!fieldsExpr || typeof fieldsExpr !== 'string') {
        return fields;
    }

    // Pattern 1: fieldName: { type: DataTypes.TYPE, ...options }
    // Matches: id: { type: DataTypes.INTEGER, primaryKey: true }
    const objectFieldPattern = /(\w+)\s*:\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}/g;

    let match;
    while ((match = objectFieldPattern.exec(fieldsExpr)) !== null) {
        const fieldName = match[1];
        const fieldBody = match[2];

        // Skip if this looks like a nested property, not a field definition
        if (fieldName === 'type' || fieldName === 'references' || fieldName === 'key') continue;
        if (seenFields.has(fieldName)) continue;

        // Must have a type: DataTypes.X to be a valid field
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

        const defaultMatch = fieldBody.match(/defaultValue\s*:\s*(['"][^'"]*['"]|[\d.]+|true|false|null)/i);
        if (defaultMatch) {
            defaultValue = defaultMatch[1].replace(/^['"]|['"]$/g, '');
        }

        fields.push({
            file: filePath,
            model_name: modelName,
            field_name: fieldName,
            data_type: dataType,
            is_primary_key: isPrimaryKey,
            is_nullable: isNullable,
            is_unique: isUnique,
            default_value: defaultValue
        });
    }

    // Pattern 2: fieldName: DataTypes.TYPE (shorthand without options)
    // Matches: name: DataTypes.STRING
    const simpleFieldPattern = /(\w+)\s*:\s*DataTypes\.(\w+)(?:\([^)]*\))?(?:\s*,|\s*$|\s*\})/g;

    while ((match = simpleFieldPattern.exec(fieldsExpr)) !== null) {
        const fieldName = match[1];

        // Skip nested type: matches and already seen fields
        if (fieldName === 'type') continue;
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
            default_value: null
        });
    }

    return fields;
}

/**
 * Extract Sequelize ORM models and relationships.
 * Detects: Model.init(), class extends Model, associations (hasMany, belongsTo, etc.)
 *
 * @param {Array} functions - From extractFunctions()
 * @param {Array} classes - From extractClasses()
 * @param {Array} functionCallArgs - From extractFunctionCallArgs()
 * @param {Array} imports - From extractImports()
 * @param {string} filePath - Relative file path for database records
 * @returns {Object} - { sequelize_models, sequelize_associations, sequelize_model_fields }
 */
function extractSequelizeModels(functions, classes, functionCallArgs, imports, filePath) {
    const models = [];
    const associations = [];
    const model_fields = [];

    // Check if Sequelize is imported
    const hasSequelize = imports && imports.some(imp =>
        imp.module === 'sequelize' || imp.module === '@sequelize/core'
    );

    if (!hasSequelize) {
        return {
            sequelize_models: models,
            sequelize_associations: associations,
            sequelize_model_fields: model_fields
        };
    }

    // Detect classes extending Model
    for (const cls of classes) {
        const extendsModel = cls.extends_type && cls.extends_type.includes('Model');
        if (!extendsModel) continue;

        const modelName = cls.name;
        let tableName = null;

        // Find Model.init() call to extract table/field info
        for (const call of functionCallArgs) {
            // Match: UserModel.init({ ... }, { tableName: 'users', sequelize })
            if (call.callee_function && call.callee_function.includes('.init') &&
                call.callee_function.includes(modelName)) {

                // Extract field definitions from first argument
                if (call.argument_index === 0 && call.argument_expr) {
                    const extractedFields = parseModelFields(modelName, call.argument_expr, filePath);
                    model_fields.push(...extractedFields);
                }

                // Extract table name from second argument
                if (call.argument_index === 1 && call.argument_expr) {
                    const tableMatch = call.argument_expr.match(/tableName:\s*['"]([^'"]+)['"]/);
                    if (tableMatch) {
                        tableName = tableMatch[1];
                    }
                }
            }

            // Detect associations: hasMany, belongsTo, hasOne, belongsToMany
            const associationMethods = ['hasMany', 'belongsTo', 'hasOne', 'belongsToMany'];
            for (const method of associationMethods) {
                if (call.callee_function && call.callee_function.includes(`.${method}`) &&
                    call.callee_function.includes(modelName)) {

                    // Extract target model and options from arguments
                    let targetModel = null;
                    let foreignKey = null;
                    let throughTable = null;

                    if (call.argument_index === 0 && call.argument_expr) {
                        // First argument is the target model
                        targetModel = call.argument_expr.replace(/require\(['"]\.(\/[^'"]+)['"]\)/g, '$1')
                                                       .replace(/['"]/g, '')
                                                       .trim();
                    }

                    // Extract options from second argument
                    if (call.argument_index === 1 && call.argument_expr) {
                        const fkMatch = call.argument_expr.match(/foreignKey:\s*['"]([^'"]+)['"]/);
                        if (fkMatch) {
                            foreignKey = fkMatch[1];
                        }
                        const throughMatch = call.argument_expr.match(/through:\s*['"]([^'"]+)['"]/);
                        if (throughMatch) {
                            throughTable = throughMatch[1];
                        }
                    }

                    if (targetModel) {
                        // Add forward relationship
                        associations.push({
                            file: filePath,
                            line: call.line,
                            model_name: modelName,
                            association_type: method,
                            target_model: targetModel,
                            foreign_key: foreignKey,
                            through_table: throughTable
                        });

                        // Add inverse relationship matching Python SQLAlchemy/Django pattern
                        // Skip self-referential relationships to avoid duplicates
                        if (targetModel !== modelName) {
                            let inverseType = null;

                            // Map relationship types to their inverses
                            if (method === 'hasMany') {
                                inverseType = 'belongsTo';
                            } else if (method === 'hasOne') {
                                inverseType = 'belongsTo';
                            } else if (method === 'belongsToMany') {
                                inverseType = 'belongsToMany';
                            }

                            if (inverseType) {
                                associations.push({
                                    file: filePath,
                                    line: call.line,
                                    model_name: targetModel,
                                    association_type: inverseType,
                                    target_model: modelName,
                                    foreign_key: foreignKey,
                                    through_table: throughTable
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
            extends_model: true
        });
    }

    return {
        sequelize_models: models,
        sequelize_associations: associations,
        sequelize_model_fields: model_fields
    };
}
