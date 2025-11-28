## 0. Verification (Prime Directive)
- [ ] 0.1 Read `theauditor/ast_extractors/javascript/core_language.js` (873 lines) - verify 6 function exports
- [ ] 0.2 Read `theauditor/ast_extractors/javascript/data_flow.js` (~1100 lines) - verify 6 function exports
- [ ] 0.3 Read `theauditor/ast_extractors/javascript/module_framework.js` (595 lines) - verify 5 function exports
- [ ] 0.4 Read `theauditor/ast_extractors/javascript/security_extractors.js` (1109 lines) - verify 7 function exports
- [ ] 0.5 Read `theauditor/ast_extractors/javascript/framework_extractors.js` (974 lines) - verify 9 function exports
- [ ] 0.6 Read `theauditor/ast_extractors/javascript/batch_templates.js` - identify all function calls to replace with imports
- [ ] 0.7 Read `theauditor/ast_extractors/js_helper_templates.py` (lines 15-89) - understand current orchestration
- [ ] 0.8 Run `aud full --index` on test fixtures to establish baseline extraction counts
- [ ] 0.9 Verify no existing TypeScript/build artifacts in `javascript/` directory

## 1. Infrastructure Setup

### 1.1 Package Configuration
- [ ] 1.1.1 Create `theauditor/ast_extractors/javascript/package.json`:
```json
{
  "name": "@theauditor/js-extractors",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "build": "esbuild src/main.ts --bundle --platform=node --target=node18 --format=esm --outfile=dist/extractor.js",
    "typecheck": "tsc --noEmit",
    "clean": "rm -rf dist"
  },
  "dependencies": {
    "zod": "^3.22.4"
  },
  "devDependencies": {
    "typescript": "^5.3.3",
    "esbuild": "^0.19.11",
    "@types/node": "^20.10.0"
  }
}
```
- [ ] 1.1.2 Create `theauditor/ast_extractors/javascript/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "node",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "outDir": "dist",
    "rootDir": "src",
    "declaration": false
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist"]
}
```
- [ ] 1.1.3 Add to root `.gitignore`:
```
theauditor/ast_extractors/javascript/dist/
theauditor/ast_extractors/javascript/node_modules/
```

### 1.2 Directory Structure
- [ ] 1.2.1 Create `theauditor/ast_extractors/javascript/src/` directory
- [ ] 1.2.2 Create `theauditor/ast_extractors/javascript/src/extractors/` directory
- [ ] 1.2.3 Create `theauditor/ast_extractors/javascript/src/types/` directory
- [ ] 1.2.4 Create placeholder `src/main.ts`:
```typescript
// Entry point - TODO: migrate from batch_templates.js
export {};
```
- [ ] 1.2.5 Create placeholder `src/schema.ts`:
```typescript
// Zod schemas - TODO: implement from design.md
export {};
```

### 1.3 Build Pipeline Verification
- [ ] 1.3.1 Run `cd theauditor/ast_extractors/javascript && npm install`
- [ ] 1.3.2 Run `npm run build` - verify `dist/extractor.js` created
- [ ] 1.3.3 Run `npm run typecheck` - verify no errors on placeholder files

## 2. Schema Definition

### 2.1 Core Schemas
Implement schemas from design.md "Complete Zod Schema Definition" section:

- [ ] 2.1.1 Implement `SymbolSchema` (columns: path, name, type, line, col, jsx_mode, extraction_pass)
- [ ] 2.1.2 Implement `FunctionSchema` (columns: name, line, col, type, kind, return_type, extends_type)
- [ ] 2.1.3 Implement `ClassSchema` (columns: name, line, col, type, kind, extends_type, has_type_params)
- [ ] 2.1.4 Implement `AssignmentSchema` (columns: file, line, target_var, source_expr, in_function, property_path)
- [ ] 2.1.5 Implement `FunctionReturnSchema` (columns: file, line, function_name, return_expr, has_jsx, returns_component)
- [ ] 2.1.6 Implement `FunctionCallArgSchema` (columns: file, line, caller_function, callee_function, argument_index, argument_expr, param_name)

### 2.2 Junction Table Schemas
- [ ] 2.2.1 Implement `FuncParamSchema` (columns: file, function_line, function_name, param_index, param_name, param_type)
- [ ] 2.2.2 Implement `FuncDecoratorSchema` (columns: file, function_line, function_name, decorator_index, decorator_name, decorator_line)
- [ ] 2.2.3 Implement `FuncDecoratorArgSchema` (columns: file, function_line, function_name, decorator_index, arg_index, arg_value)
- [ ] 2.2.4 Implement `FuncParamDecoratorSchema` (columns: file, function_line, function_name, param_index, decorator_name, decorator_args)
- [ ] 2.2.5 Implement `ClassDecoratorSchema` (columns: file, class_line, class_name, decorator_index, decorator_name, decorator_line)
- [ ] 2.2.6 Implement `ClassDecoratorArgSchema` (columns: file, class_line, class_name, decorator_index, arg_index, arg_value)
- [ ] 2.2.7 Implement `ClassPropertySchema` (columns: file, line, class_name, property_name, property_type, is_optional, is_readonly, access_modifier, has_declare, initializer)
- [ ] 2.2.8 Implement `ImportSpecifierSchema` (columns: file, import_line, specifier_name, original_name, is_default, is_namespace, is_named)
- [ ] 2.2.9 Implement `AssignmentSourceVarSchema` (columns: file, line, target_var, source_var, var_index)
- [ ] 2.2.10 Implement `ReturnSourceVarSchema` (columns: file, line, function_name, source_var, var_index)

### 2.3 Framework Schemas
- [ ] 2.3.1 Implement `ReactComponentSchema` (columns: file, name, type, start_line, end_line, has_jsx, props_type)
- [ ] 2.3.2 Implement `ReactHookSchema` (columns: file, line, component_name, hook_name, dependency_array, callback_body, has_cleanup, cleanup_type)
- [ ] 2.3.3 Implement `VueComponentSchema` (columns: file, name, type, start_line, end_line, has_template, has_style, composition_api_used)
- [ ] 2.3.4 Implement `VueComponentPropSchema`, `VueComponentEmitSchema`, `VueComponentSetupReturnSchema`
- [ ] 2.3.5 Implement `AngularComponentSchema` (columns: file, line, component_name, selector, template_path, has_lifecycle_hooks)
- [ ] 2.3.6 Implement `SequelizeModelSchema`, `SequelizeModelFieldSchema`
- [ ] 2.3.7 Implement `BullMQQueueSchema`, `BullMQWorkerSchema`

### 2.4 Extraction Receipt Schema
- [ ] 2.4.1 Implement `ExtractedDataSchema` containing all extraction types (see design.md for complete list)
- [ ] 2.4.2 Implement `FileResultSchema` with success/error/extracted_data
- [ ] 2.4.3 Implement `ExtractionReceiptSchema` as `z.record(z.string(), FileResultSchema)`
- [ ] 2.4.4 Export all schemas from `src/schema.ts`

### 2.5 Schema Contract Tests
- [ ] 2.5.1 Create `tests/test_zod_schema_contract.py` comparing schema keys to database columns
- [ ] 2.5.2 Verify all 50 Node.js tables have corresponding schema definitions
- [ ] 2.5.3 Run contract test, fix any mismatches

## 3. Extractor Conversion

### 3.1 Core Language Extractor
Source: `theauditor/ast_extractors/javascript/core_language.js` (873 lines)

- [ ] 3.1.1 Create `src/extractors/core_language.ts`
- [ ] 3.1.2 Convert `serializeNodeForCFG` (line 1-72):
  - Params: `(node: ts.Node, sourceFile: ts.SourceFile, ts: typeof import('typescript'))`
  - Return: `SerializedNode | null`
- [ ] 3.1.3 Convert `extractFunctions` (line 74-379):
  - Params: `(sourceFile: ts.SourceFile, ts: typeof import('typescript'), filePath: string, scopeMap: Map<number, string>)`
  - Return: `{ functions: IFunction[], func_params: IFuncParam[], func_decorators: IFuncDecorator[], func_decorator_args: IFuncDecoratorArg[], func_param_decorators: IFuncParamDecorator[] }`
- [ ] 3.1.4 Convert `extractClasses` (line 381-616):
  - Params: `(sourceFile: ts.SourceFile, ts: typeof import('typescript'), filePath: string, scopeMap: Map<number, string>)`
  - Return: `{ classes: IClass[], class_decorators: IClassDecorator[], class_decorator_args: IClassDecoratorArg[] }`
- [ ] 3.1.5 Convert `extractClassProperties` (line 618-709):
  - Params: `(sourceFile: ts.SourceFile, ts: typeof import('typescript'), filePath: string, classes: IClass[])`
  - Return: `IClassProperty[]`
- [ ] 3.1.6 Convert `buildScopeMap` (line 711-871):
  - Params: `(sourceFile: ts.SourceFile, ts: typeof import('typescript'))`
  - Return: `Map<number, string>`
- [ ] 3.1.7 Convert `countNodes` (line 873):
  - Params: `(sourceFile: ts.SourceFile, ts: typeof import('typescript'))`
  - Return: `number`
- [ ] 3.1.8 Add `export` keyword to all 6 functions
- [ ] 3.1.9 Run `npm run build` and `npm run typecheck` - fix any errors

### 3.2 Data Flow Extractor
Source: `theauditor/ast_extractors/javascript/data_flow.js` (~1100 lines)

- [ ] 3.2.1 Create `src/extractors/data_flow.ts`
- [ ] 3.2.2 Convert `extractCalls` (line 3-224):
  - Params: `(sourceFile: ts.SourceFile, ts: typeof import('typescript'), filePath: string, functions: IFunction[], classes: IClass[], scopeMap: Map<number, string>)`
  - Return: `ICallSymbol[]`
- [ ] 3.2.3 Convert `extractAssignments` (line 226-452):
  - Params: `(sourceFile: ts.SourceFile, ts: typeof import('typescript'), filePath: string, scopeMap: Map<number, string>)`
  - Return: `{ assignments: IAssignment[], assignment_source_vars: IAssignmentSourceVar[] }`
- [ ] 3.2.4 Convert `extractFunctionCallArgs` (line 454-647):
  - Params: `(sourceFile: ts.SourceFile, ts: typeof import('typescript'), filePath: string, scopeMap: Map<number, string>, refs: Record<string, string>)`
  - Return: `IFunctionCallArg[]`
- [ ] 3.2.5 Convert `extractReturns` (line 649-836):
  - Params: `(sourceFile: ts.SourceFile, ts: typeof import('typescript'), filePath: string, scopeMap: Map<number, string>, functions: IFunction[])`
  - Return: `{ returns: IFunctionReturn[], return_source_vars: IReturnSourceVar[] }`
- [ ] 3.2.6 Convert `extractObjectLiterals` (line 838-1006):
  - Params: `(sourceFile: ts.SourceFile, ts: typeof import('typescript'), filePath: string, scopeMap: Map<number, string>)`
  - Return: `IObjectLiteral[]`
- [ ] 3.2.7 Convert `extractVariableUsage` (line 1008+):
  - Params: `(sourceFile: ts.SourceFile, ts: typeof import('typescript'), filePath: string, scopeMap: Map<number, string>)`
  - Return: `IVariableUsage[]`
- [ ] 3.2.8 Add `export` keyword to all 6 functions
- [ ] 3.2.9 Run `npm run build` and `npm run typecheck` - fix any errors

### 3.3 Module Framework Extractor
Source: `theauditor/ast_extractors/javascript/module_framework.js` (595 lines)

- [ ] 3.3.1 Create `src/extractors/module_framework.ts`
- [ ] 3.3.2 Convert `extractImports` (line 1-201):
  - Params: `(sourceFile: ts.SourceFile, ts: typeof import('typescript'), filePath: string)`
  - Return: `{ imports: IImport[], import_specifiers: IImportSpecifier[] }`
- [ ] 3.3.3 Convert `extractEnvVarUsage` (line 203-380):
  - Params: `(sourceFile: ts.SourceFile, ts: typeof import('typescript'), scopeMap: Map<number, string>)`
  - Return: `IEnvVarUsage[]`
- [ ] 3.3.4 Convert `extractORMRelationships` (line 382-510):
  - Params: `(sourceFile: ts.SourceFile, ts: typeof import('typescript'))`
  - Return: `IORMRelationship[]`
- [ ] 3.3.5 Convert `extractImportStyles` (line 512-566):
  - Params: `(imports: IImport[], import_specifiers: IImportSpecifier[], filePath: string)`
  - Return: `{ import_styles: IImportStyle[], import_style_names: IImportStyleName[] }`
- [ ] 3.3.6 Convert `extractRefs` (line 568-595):
  - Params: `(imports: IImport[], import_specifiers: IImportSpecifier[])`
  - Return: `Record<string, string>`
- [ ] 3.3.7 Add `export` keyword to all 5 functions
- [ ] 3.3.8 Run `npm run build` and `npm run typecheck` - fix any errors

### 3.4 Security Extractor
Source: `theauditor/ast_extractors/javascript/security_extractors.js` (1109 lines)

- [ ] 3.4.1 Create `src/extractors/security_extractors.ts`
- [ ] 3.4.2 Convert `extractORMQueries` (line 1-50):
  - Params: `(functionCallArgs: IFunctionCallArg[])`
  - Return: `IORMQuery[]`
- [ ] 3.4.3 Convert `extractAPIEndpoints` (line 52-137):
  - Params: `(functionCallArgs: IFunctionCallArg[])`
  - Return: `{ endpoints: IAPIEndpoint[], middlewareChains: IMiddlewareChain[] }`
- [ ] 3.4.4 Convert `extractValidationFrameworkUsage` (line 139-201):
  - Params: `(functionCallArgs: IFunctionCallArg[], assignments: IAssignment[], imports: IImport[])`
  - Return: `IValidationCall[]`
- [ ] 3.4.5 Convert `extractSchemaDefinitions` (line 203-364):
  - Params: `(functionCallArgs: IFunctionCallArg[], assignments: IAssignment[], imports: IImport[])`
  - Return: `ISchemaDefinition[]`
- [ ] 3.4.6 Convert helper functions: `detectValidationFrameworks`, `findSchemaVariables`, `isValidationCall`, `looksLikeSchemaVariable`, `isValidatorMethod`, `getFrameworkName`, `getMethodName`, `getVariableName` (lines 366-602)
- [ ] 3.4.7 Convert `extractSQLQueries` (line 604-676):
  - Params: `(functionCallArgs: IFunctionCallArg[])`
  - Return: `ISQLQuery[]`
- [ ] 3.4.8 Convert `extractCDKConstructs` (line 678-833):
  - Params: `(functionCallArgs: IFunctionCallArg[], imports: IImport[], import_specifiers: IImportSpecifier[])`
  - Return: `{ cdk_constructs: ICDKConstruct[], cdk_construct_properties: ICDKConstructProperty[] }`
- [ ] 3.4.9 Convert helper functions: `extractConstructName`, `extractConstructProperties`, `splitObjectPairs` (lines 835-943)
- [ ] 3.4.10 Convert `extractFrontendApiCalls` (line 945-1109):
  - Params: `(functionCallArgs: IFunctionCallArg[], imports: IImport[])`
  - Return: `IFrontendApiCall[]`
- [ ] 3.4.11 Add `export` keyword to 7 main functions (not helper functions)
- [ ] 3.4.12 Run `npm run build` and `npm run typecheck` - fix any errors

### 3.5 Framework Extractor
Source: `theauditor/ast_extractors/javascript/framework_extractors.js` (974 lines)

- [ ] 3.5.1 Create `src/extractors/framework_extractors.ts`
- [ ] 3.5.2 Convert `extractReactComponents` (line 1-112):
  - Params: `(functions: IFunction[], classes: IClass[], returns: IFunctionReturn[], functionCallArgs: IFunctionCallArg[], filePath: string, imports: IImport[])`
  - Return: `{ react_components: IReactComponent[], react_component_hooks: IReactComponentHook[] }`
- [ ] 3.5.3 Convert `extractReactHooks` (line 114-179):
  - Params: `(functionCallArgs: IFunctionCallArg[], scopeMap: Map<number, string>, filePath: string)`
  - Return: `{ react_hooks: IReactHook[], react_hook_dependencies: IReactHookDependency[] }`
- [ ] 3.5.4 Convert helper functions: `parseDependencyArray`, `isValidDependencyName`, `extractBaseName` (lines 181-232)
- [ ] 3.5.5 Convert Vue helpers: `truncateVueString`, `getVueBaseName`, `inferVueComponentName`, `groupFunctionCallArgs`, `findFirstVueMacroCall`, `parseVuePropsDefinition`, `parseVueEmitsDefinition`, `parseSetupReturn` (lines 234-441)
- [ ] 3.5.6 Convert `extractVueComponents` (line 443-519):
  - Params: `(vueMeta: VueMeta | null, filePath: string, functionCallArgs: IFunctionCallArg[], returns: IFunctionReturn[])`
  - Return: `{ vue_components: IVueComponent[], vue_component_props: IVueComponentProp[], vue_component_emits: IVueComponentEmit[], vue_component_setup_returns: IVueComponentSetupReturn[], primaryName: string }`
- [ ] 3.5.7 Convert `extractVueHooks` (line 521-575):
  - Params: `(functionCallArgs: IFunctionCallArg[], componentName: string)`
  - Return: `IVueHook[]`
- [ ] 3.5.8 Convert `extractVueProvideInject` (line 577-612):
  - Params: `(functionCallArgs: IFunctionCallArg[], componentName: string)`
  - Return: `IVueProvideInject[]`
- [ ] 3.5.9 Convert `extractVueDirectives` (line 614-679):
  - Params: `(templateAst: any, componentName: string, nodeTypes: any)`
  - Return: `IVueDirective[]`
- [ ] 3.5.10 Convert `extractApolloResolvers` (line 681-746):
  - Params: `(functions: IFunction[], func_params: IFuncParam[], symbolTable: Record<string, any>)`
  - Return: `{ graphql_resolvers: IGraphQLResolver[], graphql_resolver_params: IGraphQLResolverParam[] }`
- [ ] 3.5.11 Convert `extractNestJSResolvers` (line 748-856):
  - Params: `(functions: IFunction[], classes: IClass[], func_decorators: IFuncDecorator[], func_decorator_args: IFuncDecoratorArg[], class_decorators: IClassDecorator[], class_decorator_args: IClassDecoratorArg[], func_params: IFuncParam[], func_param_decorators: IFuncParamDecorator[])`
  - Return: `{ graphql_resolvers: IGraphQLResolver[], graphql_resolver_params: IGraphQLResolverParam[] }`
- [ ] 3.5.12 Convert `extractTypeGraphQLResolvers` (line 858-973):
  - Params: same as NestJS
  - Return: same as NestJS
- [ ] 3.5.13 Add `export` keyword to 9 main functions
- [ ] 3.5.14 Run `npm run build` and `npm run typecheck` - fix any errors

### 3.6 Sequelize Extractor
Source: `theauditor/ast_extractors/javascript/sequelize_extractors.js`

- [ ] 3.6.1 Create `src/extractors/sequelize_extractors.ts`
- [ ] 3.6.2 Convert `extractSequelizeModels`:
  - Return: `{ sequelize_models: ISequelizeModel[], sequelize_associations: ISequelizeAssociation[], sequelize_model_fields: ISequelizeModelField[] }`
- [ ] 3.6.3 Add `export` keyword
- [ ] 3.6.4 Run `npm run build` and `npm run typecheck` - fix any errors

### 3.7 BullMQ Extractor
Source: `theauditor/ast_extractors/javascript/bullmq_extractors.js`

- [ ] 3.7.1 Create `src/extractors/bullmq_extractors.ts`
- [ ] 3.7.2 Convert `extractBullMQJobs`:
  - Return: `{ bullmq_queues: IBullMQQueue[], bullmq_workers: IBullMQWorker[] }`
- [ ] 3.7.3 Add `export` keyword
- [ ] 3.7.4 Run `npm run build` and `npm run typecheck` - fix any errors

### 3.8 Angular Extractor
Source: `theauditor/ast_extractors/javascript/angular_extractors.js`

- [ ] 3.8.1 Create `src/extractors/angular_extractors.ts`
- [ ] 3.8.2 Convert `extractAngularComponents`:
  - Return: Full Angular data object (components, modules, services, guards, etc.)
- [ ] 3.8.3 Add `export` keyword
- [ ] 3.8.4 Run `npm run build` and `npm run typecheck` - fix any errors

### 3.9 CFG Extractor
Source: `theauditor/ast_extractors/javascript/cfg_extractor.js`

- [ ] 3.9.1 Create `src/extractors/cfg_extractor.ts`
- [ ] 3.9.2 Convert `extractCFG`:
  - Return: `{ cfg_blocks: ICFGBlock[], cfg_edges: ICFGEdge[], cfg_block_statements: ICFGBlockStatement[] }`
- [ ] 3.9.3 Add `export` keyword
- [ ] 3.9.4 Run `npm run build` and `npm run typecheck` - fix any errors

## 4. Entry Point Migration

### 4.1 Main Entry Point
Source: `theauditor/ast_extractors/javascript/batch_templates.js` (ES Module section)

- [ ] 4.1.1 Create `src/main.ts` with async main() function
- [ ] 4.1.2 Add imports for all extractor modules:
```typescript
import { extractFunctions, extractClasses, extractClassProperties, buildScopeMap, countNodes } from './extractors/core_language';
import { extractCalls, extractAssignments, extractFunctionCallArgs, extractReturns, extractObjectLiterals, extractVariableUsage } from './extractors/data_flow';
import { extractImports, extractEnvVarUsage, extractORMRelationships, extractImportStyles, extractRefs } from './extractors/module_framework';
// ... all other imports
```
- [ ] 4.1.3 Add import for Zod schemas:
```typescript
import { ExtractionReceiptSchema } from './schema';
```
- [ ] 4.1.4 Port Vue SFC handling from batch_templates.js (lines ~50-150)
- [ ] 4.1.5 Port TypeScript program creation logic (lines ~150-200)
- [ ] 4.1.6 Port file processing loop (lines ~200-400)

### 4.2 Import Replacement
Replace ALL global function calls with imports:

- [ ] 4.2.1 Replace `buildScopeMap(sourceFile, ts)` with import call
- [ ] 4.2.2 Replace `extractImports(sourceFile, ts, filePath)` with import call
- [ ] 4.2.3 Replace `extractFunctions(sourceFile, ts, filePath, scopeMap)` with import call
- [ ] 4.2.4 Replace `extractClasses(sourceFile, ts, filePath, scopeMap)` with import call
- [ ] 4.2.5 Replace `extractClassProperties(sourceFile, ts, filePath, classes)` with import call
- [ ] 4.2.6 Replace `extractCalls(sourceFile, ts, filePath, functions, classes, scopeMap)` with import call
- [ ] 4.2.7 Replace `extractAssignments(sourceFile, ts, filePath, scopeMap)` with import call
- [ ] 4.2.8 Replace `extractRefs(imports, import_specifiers)` with import call
- [ ] 4.2.9 Replace `extractFunctionCallArgs(sourceFile, ts, filePath, scopeMap, refs)` with import call
- [ ] 4.2.10 Replace `extractReturns(sourceFile, ts, filePath, scopeMap, functions)` with import call
- [ ] 4.2.11 Replace ALL remaining global function calls (see batch_templates.js for complete list)

### 4.3 Schema Validation
- [ ] 4.3.1 Before JSON.stringify(), add Zod validation:
```typescript
const validated = ExtractionReceiptSchema.parse(results);
console.log(JSON.stringify(validated, null, 2));
```
- [ ] 4.3.2 On validation failure, throw descriptive error:
```typescript
try {
  const validated = ExtractionReceiptSchema.parse(results);
  console.log(JSON.stringify(validated, null, 2));
} catch (e) {
  if (e instanceof z.ZodError) {
    console.error(JSON.stringify({ validation_error: e.errors }));
    process.exit(1);
  }
  throw e;
}
```
- [ ] 4.3.3 On success, output validated JSON

### 4.4 Build and Test Entry Point
- [ ] 4.4.1 Run `npm run build` - verify `dist/extractor.js` created
- [ ] 4.4.2 Run `node dist/extractor.js '["test.ts"]'` - verify it executes
- [ ] 4.4.3 Compare output format to old batch_templates.js output

## 5. Python Orchestrator Update

### 5.1 Simplify js_helper_templates.py
File: `theauditor/ast_extractors/js_helper_templates.py`

- [ ] 5.1.1 Remove `_JS_CACHE` dictionary (line 8-12)
- [ ] 5.1.2 Remove `_load_javascript_modules()` function (line 15-46)
- [ ] 5.1.3 Update `get_batch_helper()` (line 48-89) to read `dist/extractor.js`:
```python
def get_batch_helper(module_type: str = "esm") -> str:
    """Read pre-compiled extractor bundle."""
    bundle_path = Path(__file__).parent / "javascript" / "dist" / "extractor.js"
    if not bundle_path.exists():
        raise FileNotFoundError(
            f"Extractor bundle not found at {bundle_path}. "
            "Run 'npm run build' in theauditor/ast_extractors/javascript"
        )
    return bundle_path.read_text(encoding="utf-8")
```
- [ ] 5.1.4 Remove `module_type` parameter (always ESM now)
- [ ] 5.1.5 Update docstring to reflect new architecture

### 5.2 Integration Test
- [ ] 5.2.1 Run `aud full --index` on test fixtures
- [ ] 5.2.2 Query database: verify all Node tables populated correctly
- [ ] 5.2.3 Compare extraction counts to baseline from step 0.8
- [ ] 5.2.4 If counts differ, investigate and fix

## 6. CI/CD Updates

### 6.1 Build Integration
- [ ] 6.1.1 Add npm install step to CI before tests:
```yaml
- name: Install JS extractor dependencies
  run: cd theauditor/ast_extractors/javascript && npm install
```
- [ ] 6.1.2 Add npm run build step after install:
```yaml
- name: Build JS extractor
  run: cd theauditor/ast_extractors/javascript && npm run build
```
- [ ] 6.1.3 Verify build artifacts exist before test run

### 6.2 Setup Script Updates
- [ ] 6.2.1 Update `aud setup-ai` to run npm install in javascript directory
- [ ] 6.2.2 Update `aud setup-ai` to run npm run build
- [ ] 6.2.3 Add check for Node.js availability (node --version)

## 7. Cleanup

### 7.1 Remove Legacy Files
After ALL tests pass:

- [ ] 7.1.1 Delete `theauditor/ast_extractors/javascript/core_language.js`
- [ ] 7.1.2 Delete `theauditor/ast_extractors/javascript/data_flow.js`
- [ ] 7.1.3 Delete `theauditor/ast_extractors/javascript/module_framework.js`
- [ ] 7.1.4 Delete `theauditor/ast_extractors/javascript/security_extractors.js`
- [ ] 7.1.5 Delete `theauditor/ast_extractors/javascript/framework_extractors.js`
- [ ] 7.1.6 Delete `theauditor/ast_extractors/javascript/sequelize_extractors.js`
- [ ] 7.1.7 Delete `theauditor/ast_extractors/javascript/bullmq_extractors.js`
- [ ] 7.1.8 Delete `theauditor/ast_extractors/javascript/angular_extractors.js`
- [ ] 7.1.9 Delete `theauditor/ast_extractors/javascript/cfg_extractor.js`
- [ ] 7.1.10 Delete `theauditor/ast_extractors/javascript/batch_templates.js`

### 7.2 Update ESLint
- [ ] 7.2.1 Remove eslint-disable comments that were for legacy files
- [ ] 7.2.2 Add TypeScript ESLint rules for src/ directory
- [ ] 7.2.3 Run ESLint - verify no false unused variable warnings

### 7.3 Documentation
- [ ] 7.3.1 Update `js_helper_templates.py` docstring
- [ ] 7.3.2 Add `theauditor/ast_extractors/javascript/README.md` explaining build process
- [ ] 7.3.3 Update CLAUDE.md if needed (add note about npm build step)

## 8. Post-Implementation Audit
- [ ] 8.1 Re-read all modified files to confirm correctness
- [ ] 8.2 Run full test suite: `pytest tests/`
- [ ] 8.3 Run smoke tests: `python scripts/cli_smoke_test.py`
- [ ] 8.4 Run `aud full --offline` on test fixtures
- [ ] 8.5 Verify extraction output matches expected format (compare JSON structure)
- [ ] 8.6 Document any discrepancies found
- [ ] 8.7 Create completion report per teamsop.md template C-4.20
