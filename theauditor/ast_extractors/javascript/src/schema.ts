/**
 * Zod Schemas for TypeScript AST Extraction
 *
 * This file defines the contract between Node.js extraction and Python ingestion.
 * All schemas mirror the database column structure expected by Python storage handlers.
 *
 * Key semantic fields (from spec2.md):
 * - ClassSchema: extends[], implements[], properties[], methods[]
 * - CallSymbolSchema: name (resolved), original_text (raw), defined_in (file path)
 */

import { z } from "zod";

// =============================================================================
// SECTION 2.1: CORE EXTRACTION SCHEMAS
// =============================================================================

/**
 * 2.1.1 Symbol Schema
 * Represents any named entity in the codebase (function, class, variable, etc.)
 */
export const SymbolSchema = z.object({
  path: z.string(),
  name: z.string(),
  type: z.string(),
  line: z.number(),
  col: z.number(),
  jsx_mode: z.string().nullable(),
  extraction_pass: z.number().nullable(),
});

/**
 * 2.1.2 Function Schema
 * Represents function declarations, expressions, arrow functions, methods
 */
export const FunctionSchema = z.object({
  name: z.string(),
  line: z.number(),
  col: z.number().optional(),
  column: z.number().optional(),
  kind: z.string().optional(),
  type: z.literal("function"),
  type_annotation: z.string().optional(),
  is_any: z.boolean().optional(),
  is_unknown: z.boolean().optional(),
  is_generic: z.boolean().optional(),
  return_type: z.string().optional(),
  extends_type: z.string().optional(),
});

/**
 * 2.1.3 Class Schema - SEMANTIC EXTRACTION
 * Includes NEW semantic fields from spec2.md Section 8:
 * - extends[]: Resolved base types via checker.getDeclaredTypeOfSymbol()
 * - implements[]: Interface contracts
 * - properties[]: All members including inherited
 * - methods[]: All methods including inherited
 */
export const ClassMemberSchema = z.object({
  name: z.string(),
  type: z.string(),
  inherited: z.boolean(),
});

export const ClassMethodSchema = z.object({
  name: z.string(),
  signature: z.string(),
  inherited: z.boolean(),
});

export const ClassSchema = z.object({
  name: z.string(),
  line: z.number(),
  col: z.number().optional(),
  column: z.number().optional(),
  type: z.literal("class"),
  kind: z.string().optional(),
  type_annotation: z.string().optional(),
  // Legacy field (text-based)
  extends_type: z.string().nullable().optional(),
  has_type_params: z.boolean().optional(),
  type_params: z.string().optional(),
  // NEW SEMANTIC FIELDS (from spec2.md)
  extends: z.array(z.string()).optional(),           // Resolved base types
  implements: z.array(z.string()).optional(),        // Interface contracts
  properties: z.array(ClassMemberSchema).optional(), // All members including inherited
  methods: z.array(ClassMethodSchema).optional(),    // All methods including inherited
});

/**
 * 2.1.4 Assignment Schema
 * Represents variable assignments and property assignments
 */
export const AssignmentSchema = z.object({
  file: z.string(),
  line: z.number(),
  target_var: z.string(),
  source_expr: z.string(),
  in_function: z.string(),
  property_path: z.string().nullable().optional(),
  jsx_mode: z.string().nullable().optional(),
  extraction_pass: z.number().nullable().optional(),
});

/**
 * 2.1.5 Function Return Schema
 * Represents return statements within functions
 */
export const FunctionReturnSchema = z.object({
  file: z.string().optional(),
  line: z.number(),
  function_name: z.string(),
  return_expr: z.string(),
  has_jsx: z.boolean(),
  returns_component: z.boolean(),
  cleanup_operations: z.string().nullable().optional(),
  return_index: z.number().optional(),
  jsx_mode: z.string().nullable().optional(),
  extraction_pass: z.number().nullable().optional(),
});

/**
 * 2.1.6 Function Call Arg Schema
 * Represents arguments passed to function calls
 */
export const FunctionCallArgSchema = z.object({
  file: z.string().optional(),
  line: z.number(),
  caller_function: z.string(),
  callee_function: z.string(),
  argument_index: z.number().nullable(),
  argument_expr: z.string().nullable(),
  param_name: z.string().nullable(),
  callee_file_path: z.string().nullable().optional(),
  jsx_mode: z.string().nullable().optional(),
  extraction_pass: z.number().nullable().optional(),
});

/**
 * Call Symbol Schema - SEMANTIC EXTRACTION
 * From spec2.md Section 8 - represents resolved function calls:
 * - name: Resolved symbol name (e.g., "User.findAll")
 * - original_text: Raw text from AST (e.g., "db.users.findAll")
 * - defined_in: File path where function is defined
 */
export const CallSymbolSchema = z.object({
  line: z.number(),
  column: z.number().optional(),
  name: z.string(),                                  // Resolved: "User.findAll"
  original_text: z.string().optional(),              // Raw: "db.users.findAll"
  defined_in: z.string().nullable().optional(),      // File path where defined
  arguments: z.array(z.string()).optional(),
  caller_function: z.string().optional(),
  type: z.string().optional(),                       // "call" or "property"
  jsx_mode: z.string().nullable().optional(),
  extraction_pass: z.number().nullable().optional(),
});

// =============================================================================
// SECTION 2.2: JUNCTION TABLE SCHEMAS
// =============================================================================

/**
 * 2.2.1 Function Parameter Schema
 */
export const FuncParamSchema = z.object({
  file: z.string().optional(),
  function_line: z.number(),
  function_name: z.string(),
  param_index: z.number(),
  param_name: z.string(),
  param_type: z.string().nullable(),
});

/**
 * 2.2.2 Function Decorator Schema
 */
export const FuncDecoratorSchema = z.object({
  file: z.string().optional(),
  function_line: z.number(),
  function_name: z.string(),
  decorator_index: z.number(),
  decorator_name: z.string(),
  decorator_line: z.number(),
});

/**
 * 2.2.3 Function Decorator Argument Schema
 */
export const FuncDecoratorArgSchema = z.object({
  file: z.string().optional(),
  function_line: z.number(),
  function_name: z.string(),
  decorator_index: z.number(),
  arg_index: z.number(),
  arg_value: z.string(),
});

/**
 * 2.2.4 Function Parameter Decorator Schema
 */
export const FuncParamDecoratorSchema = z.object({
  file: z.string().optional(),
  function_line: z.number(),
  function_name: z.string(),
  param_index: z.number(),
  decorator_name: z.string(),
  decorator_args: z.string().nullable(),
});

/**
 * 2.2.5 Class Decorator Schema
 */
export const ClassDecoratorSchema = z.object({
  file: z.string().optional(),
  class_line: z.number(),
  class_name: z.string(),
  decorator_index: z.number(),
  decorator_name: z.string(),
  decorator_line: z.number(),
});

/**
 * 2.2.6 Class Decorator Argument Schema
 */
export const ClassDecoratorArgSchema = z.object({
  file: z.string().optional(),
  class_line: z.number(),
  class_name: z.string(),
  decorator_index: z.number(),
  arg_index: z.number(),
  arg_value: z.string(),
});

/**
 * 2.2.7 Class Property Schema
 */
export const ClassPropertySchema = z.object({
  file: z.string().optional(),
  line: z.number(),
  class_name: z.string(),
  property_name: z.string(),
  property_type: z.string().nullable(),
  is_optional: z.boolean(),
  is_readonly: z.boolean(),
  access_modifier: z.string().nullable(),
  has_declare: z.boolean(),
  initializer: z.string().nullable(),
});

/**
 * 2.2.8 Import Specifier Schema
 */
export const ImportSpecifierSchema = z.object({
  file: z.string(),
  import_line: z.number(),
  specifier_name: z.string(),
  original_name: z.string(),
  is_default: z.number(),    // 0 or 1
  is_namespace: z.number(),  // 0 or 1
  is_named: z.number(),      // 0 or 1
});

/**
 * 2.2.9 Assignment Source Variable Schema
 */
export const AssignmentSourceVarSchema = z.object({
  file: z.string(),
  line: z.number(),
  target_var: z.string(),
  source_var: z.string(),
  var_index: z.number(),
});

/**
 * 2.2.10 Return Source Variable Schema
 */
export const ReturnSourceVarSchema = z.object({
  file: z.string(),
  line: z.number(),
  function_name: z.string(),
  source_var: z.string(),
  var_index: z.number(),
});

// =============================================================================
// SECTION 2.3: FRAMEWORK SCHEMAS
// =============================================================================

/**
 * 2.3.1 React Component Schema
 */
export const ReactComponentSchema = z.object({
  file: z.string().optional(),
  name: z.string(),
  type: z.enum(["function", "class"]),
  start_line: z.number(),
  end_line: z.number(),
  has_jsx: z.boolean(),
  props_type: z.string().nullable(),
});

/**
 * React Component Hook Schema (junction table)
 */
export const ReactComponentHookSchema = z.object({
  file: z.string().optional(),
  component_name: z.string(),
  hook_name: z.string(),
  hook_line: z.number(),
});

/**
 * 2.3.2 React Hook Schema
 */
export const ReactHookSchema = z.object({
  file: z.string().optional(),
  line: z.number(),
  component_name: z.string(),
  hook_name: z.string(),
  dependency_array: z.string().nullable().optional(),
  callback_body: z.string().nullable().optional(),
  has_cleanup: z.boolean().optional(),
  cleanup_type: z.string().nullable().optional(),
  is_custom: z.boolean().optional(),
  argument_count: z.number().optional(),
});

/**
 * React Hook Dependency Schema (junction table)
 */
export const ReactHookDependencySchema = z.object({
  file: z.string().optional(),
  hook_line: z.number(),
  component_name: z.string(),
  dependency_name: z.string(),
  dependency_index: z.number(),
});

/**
 * 2.3.3 Vue Component Schema
 */
export const VueComponentSchema = z.object({
  file: z.string().optional(),
  name: z.string(),
  type: z.enum(["script-setup", "composition-api", "options-api"]),
  start_line: z.number(),
  end_line: z.number(),
  has_template: z.boolean(),
  has_style: z.boolean(),
  composition_api_used: z.boolean(),
});

/**
 * 2.3.4 Vue Component Prop Schema
 */
export const VueComponentPropSchema = z.object({
  file: z.string().optional(),
  component_name: z.string(),
  prop_name: z.string(),
  prop_type: z.string().nullable(),
  is_required: z.number(),  // 0 or 1
  default_value: z.string().nullable(),
});

/**
 * Vue Component Emit Schema
 */
export const VueComponentEmitSchema = z.object({
  file: z.string().optional(),
  component_name: z.string(),
  emit_name: z.string(),
  payload_type: z.string().nullable(),
});

/**
 * Vue Component Setup Return Schema
 */
export const VueComponentSetupReturnSchema = z.object({
  file: z.string().optional(),
  component_name: z.string(),
  return_name: z.string(),
  return_type: z.string().nullable(),
});

/**
 * Vue Hook Schema
 */
export const VueHookSchema = z.object({
  file: z.string().optional(),
  line: z.number(),
  component_name: z.string(),
  hook_name: z.string(),
  hook_type: z.string().nullable(),
});

/**
 * Vue Directive Schema
 */
export const VueDirectiveSchema = z.object({
  file: z.string().optional(),
  line: z.number(),
  component_name: z.string(),
  directive_name: z.string(),
  directive_arg: z.string().nullable(),
  directive_modifiers: z.string().nullable(),
  directive_value: z.string().nullable(),
});

/**
 * Vue Provide/Inject Schema
 */
export const VueProvideInjectSchema = z.object({
  file: z.string().optional(),
  line: z.number(),
  component_name: z.string(),
  type: z.enum(["provide", "inject"]),
  key: z.string(),
  value_type: z.string().nullable(),
});

/**
 * 2.3.5 Angular Component Schema
 */
export const AngularComponentSchema = z.object({
  file: z.string(),
  line: z.number(),
  component_name: z.string(),
  selector: z.string().nullable(),
  template_path: z.string().nullable(),
  has_lifecycle_hooks: z.boolean(),
});

/**
 * Angular Module Schema
 */
export const AngularModuleSchema = z.object({
  file: z.string(),
  line: z.number(),
  module_name: z.string(),
});

/**
 * Angular Service Schema
 */
export const AngularServiceSchema = z.object({
  file: z.string(),
  line: z.number(),
  service_name: z.string(),
  provided_in: z.string().nullable(),
});

/**
 * Angular Guard Schema
 */
export const AngularGuardSchema = z.object({
  file: z.string(),
  line: z.number(),
  guard_name: z.string(),
  guard_type: z.string().nullable(),
});

/**
 * 2.3.6 Sequelize Model Schema
 */
export const SequelizeModelSchema = z.object({
  file: z.string(),
  line: z.number(),
  model_name: z.string(),
  table_name: z.string().nullable(),
  extends_model: z.string().nullable(),
});

/**
 * Sequelize Model Field Schema
 */
export const SequelizeModelFieldSchema = z.object({
  file: z.string(),
  model_name: z.string(),
  field_name: z.string(),
  data_type: z.string(),
  is_primary_key: z.boolean(),
  is_nullable: z.boolean(),
  is_unique: z.boolean(),
  default_value: z.string().nullable(),
});

/**
 * Sequelize Association Schema
 */
export const SequelizeAssociationSchema = z.object({
  file: z.string(),
  line: z.number(),
  source_model: z.string(),
  target_model: z.string(),
  association_type: z.string(),
  foreign_key: z.string().nullable(),
  alias: z.string().nullable(),
});

/**
 * 2.3.7 BullMQ Queue Schema
 */
export const BullMQQueueSchema = z.object({
  file: z.string(),
  line: z.number(),
  queue_name: z.string(),
  redis_config: z.string().nullable(),
});

/**
 * BullMQ Worker Schema
 */
export const BullMQWorkerSchema = z.object({
  file: z.string(),
  line: z.number(),
  queue_name: z.string(),
  worker_function: z.string().nullable(),
  processor_path: z.string().nullable(),
});

// =============================================================================
// ADDITIONAL SCHEMAS (Security, GraphQL, etc.)
// =============================================================================

/**
 * Import Schema
 */
export const ImportSchema = z.object({
  file: z.string().optional(),
  line: z.number(),
  module_path: z.string().optional(),
  module: z.string().optional(), // Alias for module_path
  kind: z.string().optional(), // 'import', 'require', 'dynamic_import'
  is_relative: z.boolean().optional(),
  is_type_only: z.boolean().optional(),
});

/**
 * Environment Variable Usage Schema
 */
export const EnvVarUsageSchema = z.object({
  file: z.string().optional(),
  line: z.number(),
  var_name: z.string(),
  access_method: z.string().optional(),
  access_type: z.string().optional(), // 'read', 'write', 'check'
  in_function: z.string().nullable(),
  property_access: z.string().optional(), // e.g., 'process.env.NODE_ENV'
});

/**
 * ORM Relationship Schema
 */
export const ORMRelationshipSchema = z.object({
  file: z.string().optional(),
  line: z.number(),
  source_model: z.string(),
  relationship_type: z.string(),
  target_model: z.string(),
  options: z.string().nullable().optional(),
  foreign_key: z.string().nullable().optional(),
  cascade_delete: z.boolean().optional(),
  as_name: z.string().nullable().optional(),
});

/**
 * ORM Query Schema
 */
export const ORMQuerySchema = z.object({
  file: z.string().optional(),
  line: z.number(),
  model_name: z.string().nullable().optional(),
  method: z.string().optional(),
  query_type: z.string().optional(),
  where_clause: z.string().nullable().optional(),
  include_relations: z.string().nullable().optional(),
  includes: z.string().nullable().optional(),
  has_limit: z.boolean().optional(),
  has_transaction: z.boolean().optional(),
});

/**
 * API Endpoint Schema
 */
export const APIEndpointSchema = z.object({
  file: z.string().optional(),
  line: z.number(),
  method: z.string(),
  path: z.string().optional(),
  route: z.string().optional(), // Alias for path
  handler_function: z.string().nullable(),
  requires_auth: z.boolean().optional(),
});

/**
 * Middleware Chain Schema
 */
export const MiddlewareChainSchema = z.object({
  file: z.string().optional(),
  line: z.number().optional(),
  route_line: z.number().optional(),
  route_path: z.string().optional(),
  route_method: z.string().optional(),
  endpoint_path: z.string().optional(),
  middleware_name: z.string().optional(),
  middleware_index: z.number().optional(),
  execution_order: z.number().optional(),
  handler_expr: z.string().optional(),
  handler_type: z.string().optional(),
  handler_function: z.string().nullable().optional(),
});

/**
 * Validation Call Schema
 */
export const ValidationCallSchema = z.object({
  file: z.string().optional(),
  line: z.number(),
  framework: z.string(),
  method: z.string().optional(),
  function_name: z.string().optional(),
  variable_name: z.string().nullable().optional(),
  is_validator: z.boolean().optional(),
  argument_expr: z.string().optional(),
  schema_ref: z.string().nullable().optional(),
});

/**
 * Schema Definition Schema
 */
export const SchemaDefinitionSchema = z.object({
  file: z.string().optional(),
  line: z.number(),
  name: z.string().optional(),
  framework: z.string(),
  definition: z.string().optional(),
  method: z.string().optional(),
  variable_name: z.string().nullable().optional(),
  is_validator: z.boolean().optional(),
  argument_expr: z.string().optional(),
});

/**
 * SQL Query Schema
 */
export const SQLQuerySchema = z.object({
  file: z.string().optional(),
  line: z.number(),
  query_type: z.string().optional(),
  query_text: z.string().optional(),
  raw_query: z.string().nullable().optional(),
  is_parameterized: z.boolean().optional(),
  function_name: z.string().nullable().optional(),
});

/**
 * CDK Construct Schema
 */
export const CDKConstructSchema = z.object({
  file: z.string().optional(),
  line: z.number(),
  construct_name: z.string().nullable().optional(),
  construct_type: z.string().optional(),
  construct_id: z.string().optional(),
  cdk_class: z.string().optional(),
});

/**
 * CDK Construct Property Schema
 */
export const CDKConstructPropertySchema = z.object({
  file: z.string().optional(),
  construct_name: z.string().optional(),
  construct_class: z.string().optional(),
  construct_line: z.number().optional(),
  property_name: z.string(),
  property_value: z.string().optional(),
  value_expr: z.string().optional(),
  property_line: z.number().optional(),
});

/**
 * Frontend API Call Schema
 */
export const FrontendApiCallSchema = z.object({
  file: z.string().optional(),
  line: z.number(),
  method: z.string(),
  url: z.string().optional(),
  url_literal: z.string().optional(),
  body_variable: z.string().nullable().optional(),
  function_name: z.string().optional(),
  client_library: z.string().optional(),
});

/**
 * GraphQL Resolver Schema
 */
export const GraphQLResolverSchema = z.object({
  file: z.string(),
  line: z.number(),
  resolver_name: z.string(),
  resolver_type: z.string(),
  parent_type: z.string().nullable(),
});

/**
 * GraphQL Resolver Param Schema
 */
export const GraphQLResolverParamSchema = z.object({
  file: z.string(),
  resolver_name: z.string(),
  param_name: z.string(),
  param_type: z.string().nullable(),
  param_index: z.number(),
});

/**
 * Object Literal Schema
 */
export const ObjectLiteralSchema = z.object({
  file: z.string(),
  line: z.number(),
  in_function: z.string(),
  property_count: z.number(),
  keys: z.string().nullable(),
});

/**
 * Variable Usage Schema
 */
export const VariableUsageSchema = z.object({
  file: z.string(),
  line: z.number(),
  variable_name: z.string(),
  usage_type: z.string(),
  in_function: z.string(),
});

/**
 * Import Style Schema
 */
export const ImportStyleSchema = z.object({
  file: z.string(),
  line: z.number().optional(),
  package: z.string().optional(),
  import_style: z.string().optional(),
  alias_name: z.string().nullable().optional(),
  full_statement: z.string().optional(),
  style: z.string().optional(), // Legacy compatibility
  count: z.number().optional(), // Legacy compatibility
});

/**
 * Import Style Name Schema
 */
export const ImportStyleNameSchema = z.object({
  file: z.string().optional(),
  import_file: z.string().optional(),
  import_line: z.number().optional(),
  imported_name: z.string().optional(),
  style: z.string().optional(), // Legacy compatibility
  name: z.string().optional(), // Legacy compatibility
});

/**
 * CFG Block Schema
 */
export const CFGBlockSchema = z.object({
  function_id: z.string(),
  block_id: z.string(),
  block_type: z.string(),
  start_line: z.number().nullable(),
  end_line: z.number().nullable(),
});

/**
 * CFG Edge Schema
 */
export const CFGEdgeSchema = z.object({
  function_id: z.string(),
  from_block: z.string(),
  to_block: z.string(),
  edge_type: z.string(),
  condition: z.string().nullable(),
});

/**
 * CFG Block Statement Schema
 */
export const CFGBlockStatementSchema = z.object({
  function_id: z.string(),
  block_id: z.string(),
  statement_type: z.string(),
  line: z.number(),
  text: z.string(),
});

// =============================================================================
// SECTION 2.4: EXTRACTION RECEIPT (TOP-LEVEL OUTPUT)
// =============================================================================

/**
 * 2.4.1 Extracted Data Schema
 * Contains all extraction types - this is what each file produces
 */
export const ExtractedDataSchema = z.object({
  // Core
  symbols: z.array(SymbolSchema).optional(),
  functions: z.array(FunctionSchema).optional(),
  classes: z.array(ClassSchema).optional(),
  calls: z.array(CallSymbolSchema).optional(),              // Semantic call data
  assignments: z.array(AssignmentSchema).optional(),
  returns: z.array(FunctionReturnSchema).optional(),
  function_call_args: z.array(FunctionCallArgSchema).optional(),
  object_literals: z.array(ObjectLiteralSchema).optional(),
  variable_usage: z.array(VariableUsageSchema).optional(),

  // Junction tables
  func_params: z.array(FuncParamSchema).optional(),
  func_decorators: z.array(FuncDecoratorSchema).optional(),
  func_decorator_args: z.array(FuncDecoratorArgSchema).optional(),
  func_param_decorators: z.array(FuncParamDecoratorSchema).optional(),
  class_decorators: z.array(ClassDecoratorSchema).optional(),
  class_decorator_args: z.array(ClassDecoratorArgSchema).optional(),
  class_properties: z.array(ClassPropertySchema).optional(),
  imports: z.array(ImportSchema).optional(),
  import_specifiers: z.array(ImportSpecifierSchema).optional(),
  assignment_source_vars: z.array(AssignmentSourceVarSchema).optional(),
  return_source_vars: z.array(ReturnSourceVarSchema).optional(),

  // React
  react_components: z.array(ReactComponentSchema).optional(),
  react_component_hooks: z.array(ReactComponentHookSchema).optional(),
  react_hooks: z.array(ReactHookSchema).optional(),
  react_hook_dependencies: z.array(ReactHookDependencySchema).optional(),

  // Vue
  vue_components: z.array(VueComponentSchema).optional(),
  vue_component_props: z.array(VueComponentPropSchema).optional(),
  vue_component_emits: z.array(VueComponentEmitSchema).optional(),
  vue_component_setup_returns: z.array(VueComponentSetupReturnSchema).optional(),
  vue_hooks: z.array(VueHookSchema).optional(),
  vue_directives: z.array(VueDirectiveSchema).optional(),
  vue_provide_inject: z.array(VueProvideInjectSchema).optional(),

  // Angular
  angular_components: z.array(AngularComponentSchema).optional(),
  angular_modules: z.array(AngularModuleSchema).optional(),
  angular_services: z.array(AngularServiceSchema).optional(),
  angular_guards: z.array(AngularGuardSchema).optional(),
  angular_component_styles: z.array(z.any()).optional(),
  angular_module_declarations: z.array(z.any()).optional(),
  angular_module_imports: z.array(z.any()).optional(),
  angular_module_providers: z.array(z.any()).optional(),
  angular_module_exports: z.array(z.any()).optional(),

  // ORM
  sequelize_models: z.array(SequelizeModelSchema).optional(),
  sequelize_associations: z.array(SequelizeAssociationSchema).optional(),
  sequelize_model_fields: z.array(SequelizeModelFieldSchema).optional(),
  orm_relationships: z.array(ORMRelationshipSchema).optional(),
  orm_queries: z.array(ORMQuerySchema).optional(),

  // Jobs
  bullmq_queues: z.array(BullMQQueueSchema).optional(),
  bullmq_workers: z.array(BullMQWorkerSchema).optional(),

  // Security
  api_endpoints: z.array(APIEndpointSchema).optional(),
  middleware_chains: z.array(MiddlewareChainSchema).optional(),
  validation_calls: z.array(ValidationCallSchema).optional(),
  schema_definitions: z.array(SchemaDefinitionSchema).optional(),
  sql_queries: z.array(SQLQuerySchema).optional(),
  cdk_constructs: z.array(CDKConstructSchema).optional(),
  cdk_construct_properties: z.array(CDKConstructPropertySchema).optional(),
  frontend_api_calls: z.array(FrontendApiCallSchema).optional(),

  // GraphQL
  graphql_resolvers: z.array(GraphQLResolverSchema).optional(),
  graphql_resolver_params: z.array(GraphQLResolverParamSchema).optional(),

  // Misc
  env_vars: z.array(EnvVarUsageSchema).optional(),
  import_styles: z.array(ImportStyleSchema).optional(),
  import_style_names: z.array(ImportStyleNameSchema).optional(),
  refs: z.record(z.string()).optional(),
  cfg_blocks: z.array(CFGBlockSchema).optional(),
  cfg_edges: z.array(CFGEdgeSchema).optional(),
  cfg_block_statements: z.array(CFGBlockStatementSchema).optional(),
});

/**
 * 2.4.2 File Result Schema
 * Result for a single file extraction
 */
export const FileResultSchema = z.object({
  success: z.boolean(),
  extracted_data: ExtractedDataSchema.optional(),
  error: z.string().optional(),
});

/**
 * 2.4.3 Extraction Receipt Schema
 * Top-level output: maps file paths to their extraction results
 */
export const ExtractionReceiptSchema = z.record(z.string(), FileResultSchema);

// =============================================================================
// TYPE EXPORTS
// =============================================================================

export type Symbol = z.infer<typeof SymbolSchema>;
export type Function = z.infer<typeof FunctionSchema>;
export type Class = z.infer<typeof ClassSchema>;
export type ClassMember = z.infer<typeof ClassMemberSchema>;
export type ClassMethod = z.infer<typeof ClassMethodSchema>;
export type Assignment = z.infer<typeof AssignmentSchema>;
export type FunctionReturn = z.infer<typeof FunctionReturnSchema>;
export type FunctionCallArg = z.infer<typeof FunctionCallArgSchema>;
export type CallSymbol = z.infer<typeof CallSymbolSchema>;
export type FuncParam = z.infer<typeof FuncParamSchema>;
export type FuncDecorator = z.infer<typeof FuncDecoratorSchema>;
export type FuncDecoratorArg = z.infer<typeof FuncDecoratorArgSchema>;
export type FuncParamDecorator = z.infer<typeof FuncParamDecoratorSchema>;
export type ClassDecorator = z.infer<typeof ClassDecoratorSchema>;
export type ClassDecoratorArg = z.infer<typeof ClassDecoratorArgSchema>;
export type ClassProperty = z.infer<typeof ClassPropertySchema>;
export type ImportSpecifier = z.infer<typeof ImportSpecifierSchema>;
export type AssignmentSourceVar = z.infer<typeof AssignmentSourceVarSchema>;
export type ReturnSourceVar = z.infer<typeof ReturnSourceVarSchema>;
export type ReactComponent = z.infer<typeof ReactComponentSchema>;
export type ReactHook = z.infer<typeof ReactHookSchema>;
export type VueComponent = z.infer<typeof VueComponentSchema>;
export type VueComponentProp = z.infer<typeof VueComponentPropSchema>;
export type VueComponentEmit = z.infer<typeof VueComponentEmitSchema>;
export type VueComponentSetupReturn = z.infer<typeof VueComponentSetupReturnSchema>;
export type AngularComponent = z.infer<typeof AngularComponentSchema>;
export type SequelizeModel = z.infer<typeof SequelizeModelSchema>;
export type SequelizeModelField = z.infer<typeof SequelizeModelFieldSchema>;
export type BullMQQueue = z.infer<typeof BullMQQueueSchema>;
export type BullMQWorker = z.infer<typeof BullMQWorkerSchema>;
export type ExtractedData = z.infer<typeof ExtractedDataSchema>;
export type FileResult = z.infer<typeof FileResultSchema>;
export type ExtractionReceipt = z.infer<typeof ExtractionReceiptSchema>;

// Additional type exports for module_framework.ts
export type Import = z.infer<typeof ImportSchema>;
export type ImportStyle = z.infer<typeof ImportStyleSchema>;
export type ImportStyleName = z.infer<typeof ImportStyleNameSchema>;
export type EnvVarUsage = z.infer<typeof EnvVarUsageSchema>;
export type ORMRelationship = z.infer<typeof ORMRelationshipSchema>;
export type ORMQuery = z.infer<typeof ORMQuerySchema>;

// Additional type exports for security_extractors.ts
export type APIEndpoint = z.infer<typeof APIEndpointSchema>;
export type MiddlewareChain = z.infer<typeof MiddlewareChainSchema>;
export type ValidationCall = z.infer<typeof ValidationCallSchema>;
export type SchemaDefinition = z.infer<typeof SchemaDefinitionSchema>;
export type SQLQuery = z.infer<typeof SQLQuerySchema>;
export type CDKConstruct = z.infer<typeof CDKConstructSchema>;
export type CDKConstructProperty = z.infer<typeof CDKConstructPropertySchema>;
export type FrontendAPICall = z.infer<typeof FrontendApiCallSchema>;

// Additional type exports for framework_extractors.ts
export type ReactComponentHook = z.infer<typeof ReactComponentHookSchema>;
export type ReactHookDependency = z.infer<typeof ReactHookDependencySchema>;
export type VueHook = z.infer<typeof VueHookSchema>;
export type VueProvideInject = z.infer<typeof VueProvideInjectSchema>;
export type VueDirective = z.infer<typeof VueDirectiveSchema>;
export type GraphQLResolver = z.infer<typeof GraphQLResolverSchema>;
export type GraphQLResolverParam = z.infer<typeof GraphQLResolverParamSchema>;

// Additional type exports for sequelize_extractors.ts
export type SequelizeAssociation = z.infer<typeof SequelizeAssociationSchema>;

// Additional type exports for angular_extractors.ts
export type AngularModule = z.infer<typeof AngularModuleSchema>;
export type AngularService = z.infer<typeof AngularServiceSchema>;
export type AngularGuard = z.infer<typeof AngularGuardSchema>;

// Additional type exports for cfg_extractor.ts
export type CFGBlock = z.infer<typeof CFGBlockSchema>;
export type CFGEdge = z.infer<typeof CFGEdgeSchema>;
export type CFGBlockStatement = z.infer<typeof CFGBlockStatementSchema>;
