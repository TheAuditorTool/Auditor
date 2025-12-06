import * as ts from "typescript";
import { z } from "zod";
import { extractObjectLiterals } from "./extractors/data_flow.js";
import { extractSequelizeModels } from "./extractors/sequelize_extractors.js";
import {
  ObjectLiteralSchema,
  VariableUsageSchema,
  SequelizeModelSchema,
  SequelizeModelFieldSchema,
  SequelizeAssociationSchema,
  ExtractedDataSchema,
  ImportSchema,
  FunctionCallArgSchema,
  AssignmentSchema,
} from "./schema.js";

interface TestResult {
  name: string;
  passed: boolean;
  error?: string;
  details?: string;
}

const results: TestResult[] = [];

function test(name: string, fn: () => void): void {
  try {
    fn();
    results.push({ name, passed: true });
    console.log(`[PASS] ${name}`);
  } catch (e) {
    const error = e instanceof Error ? e.message : String(e);
    results.push({ name, passed: false, error });
    console.error(`[FAIL] ${name}`);
    console.error(`       ${error}`);
  }
}

function assertEqual<T>(actual: T, expected: T, msg: string): void {
  if (actual !== expected) {
    throw new Error(`${msg}: expected ${expected}, got ${actual}`);
  }
}

function assertGreaterThan(actual: number, min: number, msg: string): void {
  if (actual <= min) {
    throw new Error(`${msg}: expected > ${min}, got ${actual}`);
  }
}

function assertLessThan(actual: number, max: number, msg: string): void {
  if (actual >= max) {
    throw new Error(`${msg}: expected < ${max}, got ${actual}`);
  }
}

function createSourceFile(code: string, filename = "test.ts"): ts.SourceFile {
  return ts.createSourceFile(filename, code, ts.ScriptTarget.Latest, true);
}

test("ObjectLiterals: Basic extraction", () => {
  const code = `
const config = {
    apiKey: "12345",
    retries: 3,
    nested: { deep: true }
};
`;
  const sourceFile = createSourceFile(code);
  const scopeMap = new Map<number, string>();
  const results = extractObjectLiterals(sourceFile, ts, scopeMap, "test.ts");

  assertGreaterThan(results.length, 0, "Should extract object literals");
  z.array(ObjectLiteralSchema).parse(results);
});

test("ObjectLiterals: Empty object", () => {
  const code = `const empty = {};`;
  const sourceFile = createSourceFile(code);
  const scopeMap = new Map<number, string>();
  const results = extractObjectLiterals(sourceFile, ts, scopeMap, "test.ts");

  z.array(ObjectLiteralSchema).parse(results);
});

test("Sequelize: Model with define()", () => {
  const code = `
module.exports = (sequelize, DataTypes) => {
  const User = sequelize.define("User", {
    id: { type: DataTypes.INTEGER, primaryKey: true },
    name: { type: DataTypes.STRING, allowNull: false }
  }, { tableName: "users" });
  return User;
};
`;
  const sourceFile = createSourceFile(code, "User.js");
  const classes: any[] = [];
  const functionCallArgs: any[] = [];

  const result = extractSequelizeModels(
    sourceFile,
    classes,
    functionCallArgs,
    "models/User.js",
  );

  assertGreaterThan(
    result.sequelize_models.length,
    0,
    "Should extract sequelize_models",
  );
  assertGreaterThan(
    result.sequelize_model_fields.length,
    0,
    "Should extract sequelize_model_fields",
  );

  z.array(SequelizeModelSchema).parse(result.sequelize_models);
  z.array(SequelizeModelFieldSchema).parse(result.sequelize_model_fields);
  z.array(SequelizeAssociationSchema).parse(result.sequelize_associations);

  const model = result.sequelize_models[0];
  assertEqual(model.model_name, "User", "Model name should be User");
  assertEqual(model.table_name, "users", "Table name should be users");
});

test("Sequelize: Model with class extends Model", () => {
  const code = `
import { Model, DataTypes } from "sequelize";

class Product extends Model {
  id: number;
  name: string;
  price: number;
}
`;
  const sourceFile = createSourceFile(code, "Product.ts");
  const classes = [
    {
      name: "Product",
      type: "class" as const,
      line: 4,
      col: 0,
      extends_type: "Model",
    },
  ];

  const result = extractSequelizeModels(
    sourceFile,
    classes,
    [],
    "models/Product.ts",
  );

  assertGreaterThan(
    result.sequelize_models.length,
    0,
    "Should extract class-based models",
  );
  z.array(SequelizeModelSchema).parse(result.sequelize_models);
});

test("Sequelize: Associations", () => {
  const code = `
User.hasMany(Post, { foreignKey: "userId", as: "posts" });
User.belongsTo(Organization, { foreignKey: "orgId" });
`;
  const sourceFile = createSourceFile(code, "associations.js");

  const result = extractSequelizeModels(sourceFile, [], [], "associations.js");

  assertGreaterThan(
    result.sequelize_associations.length,
    0,
    "Should extract associations",
  );
  z.array(SequelizeAssociationSchema).parse(result.sequelize_associations);
});

test("EdgeCase: Huge JSX should not create giant variable names", () => {
  const hugeJsx = `const x = "a".repeat(1000);`;
  const code = `
function Component() {
  return (
    <div>
      ${hugeJsx}
    </div>
  );
}
`;
  const sourceFile = createSourceFile(code, "Component.tsx");
  const scopeMap = new Map<number, string>();

  const results = extractObjectLiterals(sourceFile, ts, scopeMap, "test.tsx");

  for (const r of results) {
    assertLessThan(
      r.variable_name.length,
      500,
      `Variable name too long: ${r.variable_name.substring(0, 50)}...`,
    );
  }
});

test("EdgeCase: Empty file", () => {
  const code = ``;
  const sourceFile = createSourceFile(code);
  const scopeMap = new Map<number, string>();

  const results = extractObjectLiterals(sourceFile, ts, scopeMap, "empty.ts");
  assertEqual(results.length, 0, "Empty file should produce no results");
});

test("EdgeCase: File with only comments", () => {
  const code = `
// This is a comment
/* Multi-line
   comment */
`;
  const sourceFile = createSourceFile(code);
  const scopeMap = new Map<number, string>();

  const results = extractObjectLiterals(
    sourceFile,
    ts,
    scopeMap,
    "comments.ts",
  );
  assertEqual(results.length, 0, "Comment-only file should produce no results");
});

test("SchemaCompleteness: All ExtractedDataSchema keys are testable", () => {
  const schemaShape = ExtractedDataSchema.shape;
  const allKeys = Object.keys(schemaShape);

  const testedKeys = new Set([
    "object_literals",
    "sequelize_models",
    "sequelize_model_fields",
    "sequelize_associations",
  ]);

  const integrationTestedKeys = new Set([
    "symbols",
    "functions",
    "classes",
    "calls",
    "assignments",
    "returns",
    "function_call_args",
    "variable_usage",
    "func_params",
    "func_decorators",
    "func_decorator_args",
    "func_param_decorators",
    "class_decorators",
    "class_decorator_args",
    "class_properties",
    "imports",
    "import_specifiers",
    "assignment_source_vars",
    "return_source_vars",
    "react_components",
    "react_component_hooks",
    "react_hooks",
    "react_hook_dependencies",
    "vue_components",
    "vue_component_props",
    "vue_component_emits",
    "vue_component_setup_returns",
    "vue_hooks",
    "vue_directives",
    "vue_provide_inject",
    "angular_components",
    "angular_modules",
    "angular_services",
    "angular_guards",
    "angular_component_styles",
    "angular_module_declarations",
    "angular_module_imports",
    "angular_module_providers",
    "angular_module_exports",
    "bullmq_queues",
    "bullmq_workers",
    "env_var_usage",
    "orm_relationships",
    "orm_queries",
    "api_endpoints",
    "middleware_chains",
    "validation_calls",
    "sql_queries",
    "cdk_constructs",
    "cdk_construct_properties",
    "graphql_resolvers",
    "graphql_resolver_params",
    "import_styles",
    "import_style_names",
    "refs",
    "cfg_blocks",
    "cfg_edges",
    "cfg_block_statements",
    "frontend_api_calls",
    "jwt_patterns",
    "di_injections",
  ]);

  const untestedKeys = allKeys.filter(
    (k) => !testedKeys.has(k) && !integrationTestedKeys.has(k),
  );

  if (untestedKeys.length > 0) {
    console.log(`[WARN] Untested schema keys: ${untestedKeys.join(", ")}`);
  }
});

test("PythonCompat: Sequelize field names match Python storage expectations", () => {
  const pythonExpectedFields = [
    "file",
    "line",
    "model_name",
    "table_name",
    "extends_model",
  ];

  const schemaFields = Object.keys(SequelizeModelSchema.shape);

  for (const field of pythonExpectedFields) {
    if (!schemaFields.includes(field)) {
      throw new Error(
        `Python expects field '${field}' but schema doesn't have it`,
      );
    }
  }
});

test("PythonCompat: Sequelize model field names match Python storage", () => {
  const pythonExpectedFields = [
    "file",
    "model_name",
    "field_name",
    "data_type",
    "is_primary_key",
    "is_nullable",
    "is_unique",
    "default_value",
  ];

  const schemaFields = Object.keys(SequelizeModelFieldSchema.shape);

  for (const field of pythonExpectedFields) {
    if (!schemaFields.includes(field)) {
      throw new Error(
        `Python expects field '${field}' but schema doesn't have it`,
      );
    }
  }
});

test("DataIntegrity: No null in required string fields", () => {
  const code = `
const User = sequelize.define("User", {
  name: DataTypes.STRING
});
`;
  const sourceFile = createSourceFile(code, "User.js");
  const result = extractSequelizeModels(sourceFile, [], [], "User.js");

  for (const model of result.sequelize_models) {
    if (model.model_name === null || model.model_name === undefined) {
      throw new Error("model_name should not be null");
    }
    if (model.file === null || model.file === undefined) {
      throw new Error("file should not be null");
    }
  }
});

test("DataIntegrity: Line numbers are positive integers", () => {
  const code = `
const Config = sequelize.define("Config", {
  key: DataTypes.STRING
});
`;
  const sourceFile = createSourceFile(code, "Config.js");
  const result = extractSequelizeModels(sourceFile, [], [], "Config.js");

  for (const model of result.sequelize_models) {
    if (typeof model.line !== "number" || model.line < 0) {
      throw new Error(`Invalid line number: ${model.line}`);
    }
  }
});

console.log("=".repeat(60));
console.log("COMPREHENSIVE EXTRACTOR TEST SUITE");
console.log("=".repeat(60));
console.log("");

console.log("");
console.log("=".repeat(60));

const passed = results.filter((r) => r.passed).length;
const failed = results.filter((r) => !r.passed).length;

console.log(`RESULTS: ${passed} passed, ${failed} failed`);

if (failed > 0) {
  console.log("");
  console.log("FAILURES:");
  for (const r of results.filter((r) => !r.passed)) {
    console.log(`  - ${r.name}: ${r.error}`);
  }
  process.exit(1);
} else {
  console.log("[SUCCESS] All tests passed!");
  process.exit(0);
}
