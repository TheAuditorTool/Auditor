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
 * @returns {Array} - Sequelize model records
 */
function extractSequelizeModels(functions, classes, functionCallArgs, imports) {
    const models = [];

    // Check if Sequelize is imported
    const hasSequelize = imports && imports.some(imp =>
        imp.source === 'sequelize' || imp.source === '@sequelize/core'
    );

    if (!hasSequelize) {
        return models;
    }

    // Detect classes extending Model
    for (const cls of classes) {
        const extendsModel = cls.extends_type && cls.extends_type.includes('Model');
        if (!extendsModel) continue;

        const modelName = cls.name;
        let tableName = null;
        let fields = [];
        let associations = [];

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

                    // Extract target model from first argument
                    if (call.argument_index === 0 && call.argument_expr) {
                        const targetModel = call.argument_expr.trim();
                        associations.push({
                            type: method,
                            target: targetModel,
                            line: call.line
                        });
                    }
                }
            }
        }

        models.push({
            name: modelName,
            line: cls.line,
            table_name: tableName || modelName.toLowerCase(),
            extends_model: true,
            associations: associations
        });
    }

    return models;
}
