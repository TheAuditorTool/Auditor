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
 *
 * Current size: 76 lines (2025-10-31)
 */

/**
 * Extract Sequelize ORM models and relationships.
 * Detects: Model.init(), class extends Model, associations (hasMany, belongsTo, etc.)
 *
 * @param {Array} functions - From extractFunctions()
 * @param {Array} classes - From extractClasses()
 * @param {Array} functionCallArgs - From extractFunctionCallArgs()
 * @param {Array} imports - From extract imports
 * @returns {Object} - Object with sequelize_models and sequelize_associations arrays
 */
function extractSequelizeModels(functions, classes, functionCallArgs, imports) {
    const models = [];
    const associations = [];

    // Check if Sequelize is imported
    const hasSequelize = imports && imports.some(imp =>
        imp.source === 'sequelize' || imp.source === '@sequelize/core'
    );

    if (!hasSequelize) {
        return { sequelize_models: models, sequelize_associations: associations };
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
                                // belongsToMany is bidirectional - both sides are the same
                                inverseType = 'belongsToMany';
                            }
                            // Note: belongsTo doesn't get an inverse because it's already the inverse of hasMany/hasOne

                            if (inverseType) {
                                associations.push({
                                    line: call.line,
                                    model_name: targetModel,  // Swap source and target
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
            line: cls.line,
            model_name: modelName,
            table_name: tableName,
            extends_model: true
        });
    }

    return {
        sequelize_models: models,
        sequelize_associations: associations
    };
}
