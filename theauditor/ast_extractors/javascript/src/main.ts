/**
 * Main Entry Point for TypeScript/JavaScript AST Extraction
 *
 * This file replaces batch_templates.js with a proper TypeScript module
 * that imports all extractors and validates output with Zod schemas.
 *
 * Architecture:
 * - Reads batch request from CLI args (requestPath, outputPath)
 * - Creates TypeScript Program with TypeChecker for semantic analysis
 * - Calls all extractors with proper typed signatures
 * - Validates output with Zod before writing
 */

import * as path from 'path';
import * as fs from 'fs';
import * as os from 'os';
import * as crypto from 'crypto';
import { pathToFileURL } from 'url';

// Import extractors
import * as core from './extractors/core_language';
import * as flow from './extractors/data_flow';
import * as mod from './extractors/module_framework';
import * as sec from './extractors/security_extractors';
import * as fw from './extractors/framework_extractors';
import * as seq from './extractors/sequelize_extractors';
import * as bull from './extractors/bullmq_extractors';
import * as ang from './extractors/angular_extractors';
import * as cfg from './extractors/cfg_extractor';

// Import Zod schema for validation
import { ExtractionReceiptSchema } from './schema';
import { z } from 'zod';

// =============================================================================
// VUE SFC SUPPORT (Optional)
// =============================================================================

// In CommonJS, require is globally available. No createRequire needed.

let parseVueSfc: any = null;
let compileVueScript: any = null;
let compileVueTemplate: any = null;
let VueNodeTypes: any = null;

try {
  const vueSfcModule = require('@vue/compiler-sfc');
  if (vueSfcModule) {
    parseVueSfc = vueSfcModule.parse;
    compileVueScript = vueSfcModule.compileScript;
    compileVueTemplate = vueSfcModule.compileTemplate;
  }
} catch (err: any) {
  console.error(`[VUE SUPPORT DISABLED] @vue/compiler-sfc not available: ${err.message}`);
}

try {
  const vueDomModule = require('@vue/compiler-dom');
  if (vueDomModule) {
    VueNodeTypes = vueDomModule.NodeTypes;
  }
} catch (err: any) {
  console.error(`[VUE TEMPLATE SUPPORT DISABLED] @vue/compiler-dom not available: ${err.message}`);
}

// =============================================================================
// TYPES
// =============================================================================

interface BatchRequest {
  files: string[];
  projectRoot: string;
  jsxMode?: 'transformed' | 'preserved';
  configMap?: Record<string, string | null>;
}

interface FileEntry {
  original: string;
  absolute: string;
  cleanup: string | null;
  vueMeta: VueMeta | null;
}

interface VueMeta {
  virtualPath: string;
  scriptContent: string;
  descriptor: any;
  compiledScript: any;
  templateAst: any;
  scopeId: string;
  hasStyle: boolean;
}

interface FileResult {
  success: boolean;
  fileName?: string;
  languageVersion?: string;
  ast: null;
  diagnostics: any[];
  imports?: any[];
  nodeCount?: number;
  hasTypes?: boolean;
  jsxMode?: string;
  extracted_data?: any;
  error?: string;
  symbols?: any[];
}

// =============================================================================
// VUE HELPERS
// =============================================================================

function createVueScopeId(filePath: string): string {
  return crypto.createHash('sha256').update(filePath).digest('hex').slice(0, 8);
}

function ensureVueCompilerAvailable(): void {
  if (!parseVueSfc || !compileVueScript) {
    throw new Error(
      'Vue SFC support requires @vue/compiler-sfc. Install dependency or skip .vue files.'
    );
  }
}

function prepareVueSfcFile(filePath: string): VueMeta {
  ensureVueCompilerAvailable();

  const source = fs.readFileSync(filePath, 'utf8');
  const { descriptor, errors } = parseVueSfc(source, { filename: filePath });

  if (errors && errors.length > 0) {
    const firstError = errors[0];
    const message =
      typeof firstError === 'string'
        ? firstError
        : firstError.message || firstError.msg || 'Unknown Vue SFC parse error';
    throw new Error(message);
  }

  if (!descriptor.script && !descriptor.scriptSetup) {
    throw new Error('Vue SFC is missing <script> or <script setup> block');
  }

  const scopeId = createVueScopeId(filePath);
  let compiledScript;
  try {
    compiledScript = compileVueScript(descriptor, {
      id: scopeId,
      inlineTemplate: false,
    });
  } catch (err: any) {
    throw new Error(`Failed to compile Vue script: ${err.message}`);
  }

  const langHint =
    (descriptor.scriptSetup && descriptor.scriptSetup.lang) ||
    (descriptor.script && descriptor.script.lang) ||
    'js';

  const isTs = langHint && langHint.toLowerCase().includes('ts');
  const virtualPath = `/virtual_vue/${scopeId}.${isTs ? 'ts' : 'js'}`;

  let templateAst = null;
  if (descriptor.template && descriptor.template.content) {
    if (typeof compileVueTemplate === 'function') {
      try {
        const templateResult = compileVueTemplate({
          source: descriptor.template.content,
          filename: filePath,
          id: scopeId,
        });
        templateAst = templateResult.ast || null;
      } catch (err: any) {
        console.error(
          `[VUE TEMPLATE WARN] Failed to compile template for ${filePath}: ${err.message}`
        );
      }
    }
  }

  return {
    virtualPath,
    scriptContent: compiledScript.content,
    descriptor,
    compiledScript,
    templateAst,
    scopeId,
    hasStyle: descriptor.styles && descriptor.styles.length > 0,
  };
}

// =============================================================================
// TYPESCRIPT COMPILER HOST FOR VUE
// =============================================================================

function createVueAwareCompilerHost(
  ts: typeof import('typescript'),
  compilerOptions: import('typescript').CompilerOptions,
  vueContentMap: Map<string, string>
): import('typescript').CompilerHost {
  const defaultHost = ts.createCompilerHost(compilerOptions);

  return {
    ...defaultHost,

    fileExists: (fileName: string): boolean => {
      if (vueContentMap.has(fileName)) {
        return true;
      }
      return defaultHost.fileExists(fileName);
    },

    readFile: (fileName: string): string | undefined => {
      if (vueContentMap.has(fileName)) {
        return vueContentMap.get(fileName);
      }
      return defaultHost.readFile(fileName);
    },

    getSourceFile: (
      fileName: string,
      languageVersion: import('typescript').ScriptTarget,
      onError?: (message: string) => void,
      shouldCreateNewSourceFile?: boolean
    ): import('typescript').SourceFile | undefined => {
      if (vueContentMap.has(fileName)) {
        const content = vueContentMap.get(fileName)!;
        return ts.createSourceFile(fileName, content, languageVersion, true);
      }
      return defaultHost.getSourceFile(fileName, languageVersion, onError, shouldCreateNewSourceFile);
    },
  };
}

// =============================================================================
// TSCONFIG HELPERS
// =============================================================================

function findNearestTsconfig(
  startPath: string,
  projectRoot: string,
  ts: typeof import('typescript')
): string | null {
  let currentDir = path.resolve(path.dirname(startPath));
  const projectRootResolved = path.resolve(projectRoot);

  while (true) {
    const candidate = path.join(currentDir, 'tsconfig.json');
    if (ts.sys.fileExists(candidate)) {
      return candidate;
    }
    if (currentDir === projectRootResolved || currentDir === path.dirname(currentDir)) {
      break;
    }
    currentDir = path.dirname(currentDir);
  }

  return null;
}

// =============================================================================
// MAIN EXTRACTION LOGIC
// =============================================================================

async function main(): Promise<void> {
  try {
    // Get request and output paths from command line
    const requestPath = process.argv[2];
    const outputPath = process.argv[3];

    if (!requestPath || !outputPath) {
      console.error(JSON.stringify({ error: 'Request and output paths required' }));
      process.exit(1);
    }

    // Read batch request
    const request: BatchRequest = JSON.parse(fs.readFileSync(requestPath, 'utf8'));
    const filePaths = request.files || [];
    const projectRoot = request.projectRoot;
    const jsxMode = request.jsxMode || 'transformed';

    if (filePaths.length === 0) {
      fs.writeFileSync(outputPath, JSON.stringify({}), 'utf8');
      process.exit(0);
    }

    if (!projectRoot) {
      throw new Error('projectRoot not provided in batch request');
    }

    // Load TypeScript - search up the directory tree for .auditor_venv
    let tsPath: string | null = null;
    let searchDir = projectRoot;

    for (let i = 0; i < 10; i++) {
      const potentialPath = path.join(
        searchDir,
        '.auditor_venv',
        '.theauditor_tools',
        'node_modules',
        'typescript',
        'lib',
        'typescript.js'
      );
      if (fs.existsSync(potentialPath)) {
        tsPath = potentialPath;
        break;
      }
      const parent = path.dirname(searchDir);
      if (parent === searchDir) break;
      searchDir = parent;
    }

    if (!tsPath) {
      tsPath = path.join(
        projectRoot,
        '.auditor_venv',
        '.theauditor_tools',
        'node_modules',
        'typescript',
        'lib',
        'typescript.js'
      );
    }

    if (!fs.existsSync(tsPath)) {
      throw new Error(`TypeScript not found at: ${tsPath}`);
    }

    const tsModule = await import(pathToFileURL(tsPath).href);
    const ts: typeof import('typescript') = tsModule.default || tsModule;

    const configMap = request.configMap || {};
    const resolvedProjectRoot = path.resolve(projectRoot);

    const normalizedConfigMap = new Map<string, string | null>();
    for (const [key, value] of Object.entries(configMap)) {
      const resolvedKey = path.resolve(key);
      normalizedConfigMap.set(resolvedKey, value ? path.resolve(value) : null);
    }

    const filesByConfig = new Map<string, FileEntry[]>();
    const DEFAULT_KEY = '__DEFAULT__';
    const preprocessingErrors = new Map<string, string>();

    // Group files by tsconfig
    for (const filePath of filePaths) {
      const absoluteFilePath = path.resolve(filePath);
      const ext = path.extname(absoluteFilePath).toLowerCase();
      const fileEntry: FileEntry = {
        original: filePath,
        absolute: absoluteFilePath,
        cleanup: null,
        vueMeta: null,
      };

      if (ext === '.vue') {
        try {
          const vueMeta = prepareVueSfcFile(absoluteFilePath);
          fileEntry.absolute = vueMeta.virtualPath;
          fileEntry.vueMeta = vueMeta;
        } catch (err: any) {
          preprocessingErrors.set(filePath, `Vue SFC preprocessing failed: ${err.message}`);
          continue;
        }
      }

      const mappedConfig = normalizedConfigMap.get(absoluteFilePath);
      const nearestConfig = mappedConfig || findNearestTsconfig(absoluteFilePath, resolvedProjectRoot, ts);
      const groupKey = nearestConfig ? path.resolve(nearestConfig) : DEFAULT_KEY;

      if (!filesByConfig.has(groupKey)) {
        filesByConfig.set(groupKey, []);
      }
      filesByConfig.get(groupKey)!.push(fileEntry);
    }

    const results: Record<string, FileResult> = {};
    const jsxEmitMode = jsxMode === 'preserved' ? ts.JsxEmit.Preserve : ts.JsxEmit.React;

    console.error(`[BATCH DEBUG] Processing ${filePaths.length} files, jsxMode=${jsxMode}`);

    // Process each config group
    for (const [configKey, groupedFiles] of filesByConfig.entries()) {
      if (!groupedFiles || groupedFiles.length === 0) {
        continue;
      }

      let compilerOptions: import('typescript').CompilerOptions;
      let program: import('typescript').Program;

      // Build vueContentMap for in-memory Vue file handling
      const vueContentMap = new Map<string, string>();
      for (const fileInfo of groupedFiles) {
        if (fileInfo.vueMeta) {
          vueContentMap.set(fileInfo.vueMeta.virtualPath, fileInfo.vueMeta.scriptContent);
        }
      }

      if (configKey !== DEFAULT_KEY) {
        const tsConfig = ts.readConfigFile(configKey, ts.sys.readFile);
        if (tsConfig.error) {
          throw new Error(
            `Failed to read tsconfig: ${ts.flattenDiagnosticMessageText(tsConfig.error.messageText, '\n')}`
          );
        }

        const configDir = path.dirname(configKey);
        const parsedConfig = ts.parseJsonConfigFileContent(
          tsConfig.config,
          ts.sys,
          configDir,
          {},
          configKey
        );

        if (parsedConfig.errors && parsedConfig.errors.length > 0) {
          const errorMessages = parsedConfig.errors
            .map((err) => ts.flattenDiagnosticMessageText(err.messageText, '\n'))
            .join('; ');
          throw new Error(`Failed to parse tsconfig: ${errorMessages}`);
        }

        compilerOptions = { ...parsedConfig.options };
        compilerOptions.jsx = jsxEmitMode;

        const hasJavaScriptFiles = groupedFiles.some((fileInfo) => {
          const ext = path.extname(fileInfo.absolute).toLowerCase();
          return ext === '.js' || ext === '.jsx' || ext === '.cjs' || ext === '.mjs';
        });
        if (hasJavaScriptFiles) {
          compilerOptions.allowJs = true;
          if (compilerOptions.checkJs === undefined) {
            compilerOptions.checkJs = false;
          }
        }

        const host =
          vueContentMap.size > 0
            ? createVueAwareCompilerHost(ts, compilerOptions, vueContentMap)
            : undefined;

        // Note: projectReferences handled via configFileParsingDiagnostics if needed
        program = ts.createProgram(
          groupedFiles.map((f) => f.absolute),
          compilerOptions,
          host
        );
      } else {
        compilerOptions = {
          target: ts.ScriptTarget.Latest,
          module: ts.ModuleKind.ESNext,
          jsx: jsxEmitMode,
          allowJs: true,
          checkJs: false,
          noEmit: true,
          skipLibCheck: true,
          moduleResolution: ts.ModuleResolutionKind.NodeJs,
          baseUrl: resolvedProjectRoot,
          rootDir: resolvedProjectRoot,
        };

        const host =
          vueContentMap.size > 0
            ? createVueAwareCompilerHost(ts, compilerOptions, vueContentMap)
            : undefined;

        program = ts.createProgram(groupedFiles.map((f) => f.absolute), compilerOptions, host);
      }

      console.error(`[BATCH DEBUG] Created program, rootNames=${program.getRootFileNames().length}`);
      const checker = program.getTypeChecker();

      // Process each file
      for (const fileInfo of groupedFiles) {
        try {
          const sourceFile = program.getSourceFile(fileInfo.absolute);
          if (!sourceFile) {
            console.error(`[DEBUG JS BATCH] Could not load sourceFile for ${fileInfo.original}`);
            results[fileInfo.original] = {
              success: false,
              error: `Could not load source file: ${fileInfo.original}`,
              ast: null,
              diagnostics: [],
              symbols: [],
            };
            continue;
          }

          const filePath = fileInfo.original;
          console.error(`[DEBUG JS BATCH] Processing ${filePath}`);

          // Extract diagnostics
          const diagnostics: any[] = [];
          const fileDiagnostics = ts.getPreEmitDiagnostics(program, sourceFile);
          fileDiagnostics.forEach((diagnostic) => {
            const message = ts.flattenDiagnosticMessageText(diagnostic.messageText, '\n');
            const location =
              diagnostic.file && diagnostic.start
                ? diagnostic.file.getLineAndCharacterOfPosition(diagnostic.start)
                : null;

            diagnostics.push({
              message,
              category: ts.DiagnosticCategory[diagnostic.category],
              code: diagnostic.code,
              line: location ? location.line + 1 : null,
              column: location ? location.character : null,
            });
          });

          // =====================================================
          // CALL EXTRACTORS WITH NEW TYPED SIGNATURES
          // =====================================================

          // Step 1: Build scope map
          const scopeMap = core.buildScopeMap(sourceFile, ts);

          // Step 2: Extract imports
          const importData = mod.extractImports(sourceFile, ts, filePath);
          const imports = importData.imports;
          const import_specifiers = importData.import_specifiers;

          // Step 3: Extract functions (4 args - no scopeMap)
          const funcData = core.extractFunctions(sourceFile, checker, ts, filePath);
          const functions = funcData.functions;
          const func_params = funcData.func_params;
          const func_decorators = funcData.func_decorators;
          const func_decorator_args = funcData.func_decorator_args;
          const func_param_decorators = funcData.func_param_decorators;

          // Build parameter map from func_params (structure matches extractor expectation)
          const functionParamsMap = new Map<string, Array<{ name: string }>>();
          func_params.forEach((p) => {
            if (!functionParamsMap.has(p.function_name)) {
              functionParamsMap.set(p.function_name, []);
            }
            functionParamsMap.get(p.function_name)!.push({ name: p.param_name });
          });

          // Step 4: Extract classes (with TypeChecker semantic data)
          const classData = core.extractClasses(sourceFile, checker, ts, filePath, scopeMap);
          const classes = classData.classes;
          const class_decorators = classData.class_decorators;
          const class_decorator_args = classData.class_decorator_args;

          // Step 5: Extract calls (with TypeChecker symbol resolution)
          const calls = flow.extractCalls(
            sourceFile,
            checker,
            ts,
            filePath,
            functions,
            classes,
            scopeMap,
            resolvedProjectRoot
          );

          // Step 6: Extract class properties
          const classProperties = core.extractClassProperties(sourceFile, ts, filePath, classes);

          // Step 7: Extract env var usage
          const envVarUsage = mod.extractEnvVarUsage(sourceFile, ts, scopeMap);

          // Step 8: Extract ORM relationships
          const ormRelationships = mod.extractORMRelationships(sourceFile, ts);

          // Step 9: Extract assignments (scopeMap before filePath)
          const assignmentData = flow.extractAssignments(sourceFile, ts, scopeMap, filePath);
          const assignments = assignmentData.assignments;
          const assignment_source_vars = assignmentData.assignment_source_vars;

          // Step 10: Extract function call args (scopeMap, functionParamsMap, projectRoot)
          const refs = mod.extractRefs(imports, import_specifiers);
          const functionCallArgs = flow.extractFunctionCallArgs(
            sourceFile,
            checker,
            ts,
            scopeMap,
            functionParamsMap,
            resolvedProjectRoot
          );

          // Step 11: Extract returns (scopeMap, filePath - 4 args)
          const returnData = flow.extractReturns(sourceFile, ts, scopeMap, filePath);
          const returns = returnData.returns;
          const return_source_vars = returnData.return_source_vars;

          // Step 12: Extract object literals (3 args - no filePath)
          const objectLiterals = flow.extractObjectLiterals(sourceFile, ts, scopeMap);

          // Step 13: Extract variable usage
          const variableUsage = flow.extractVariableUsage(
            assignments,
            functionCallArgs,
            assignment_source_vars
          );

          // Step 14: Extract import styles
          const importStyleData = mod.extractImportStyles(imports, import_specifiers, filePath);
          const importStyles = importStyleData.import_styles;
          const import_style_names = importStyleData.import_style_names;

          // Step 15: Extract React components
          const reactComponentData = fw.extractReactComponents(
            functions,
            classes,
            returns,
            functionCallArgs,
            filePath,
            imports
          );
          const reactComponents = reactComponentData.react_components;
          const react_component_hooks = reactComponentData.react_component_hooks;

          // Step 16: Extract React hooks
          const reactHookData = fw.extractReactHooks(functionCallArgs, scopeMap, filePath);
          const reactHooks = reactHookData.react_hooks;
          const react_hook_dependencies = reactHookData.react_hook_dependencies;

          // Step 17: Security extractors
          const ormQueries = sec.extractORMQueries(functionCallArgs);
          const apiEndpointData = sec.extractAPIEndpoints(functionCallArgs);
          const apiEndpoints = apiEndpointData.endpoints || [];
          const middlewareChains = apiEndpointData.middlewareChains || [];
          const validationCalls = sec.extractValidationFrameworkUsage(
            functionCallArgs,
            assignments,
            imports
          );
          const schemaDefs = sec.extractSchemaDefinitions(functionCallArgs, assignments, imports);
          const validationUsage = [...validationCalls, ...schemaDefs];
          const sqlQueries = sec.extractSQLQueries(functionCallArgs);
          const cdkData = sec.extractCDKConstructs(functionCallArgs, imports, import_specifiers);
          const frontendApiCalls = sec.extractFrontendApiCalls(functionCallArgs, imports);

          // Step 18: Sequelize extractors
          const sequelizeData = seq.extractSequelizeModels(
            sourceFile,
            classes,
            functionCallArgs,
            filePath
          );

          // Step 19: BullMQ extractors
          const bullmqData = bull.extractBullMQQueueWorkers(sourceFile, filePath);

          // Step 20: Angular extractors
          const angularData = ang.extractAngularDefinitions(
            classes,
            class_decorators,
            class_decorator_args,
            sourceFile,
            filePath
          );

          // Step 21: Vue extractors (if Vue file)
          let vueComponents: any[] = [];
          let vueHooks: any[] = [];
          let vueDirectives: any[] = [];
          let vueProvideInject: any[] = [];
          let vueComponentProps: any[] = [];
          let vueComponentEmits: any[] = [];
          let vueComponentSetupReturns: any[] = [];

          if (fileInfo.vueMeta) {
            const vueComponentData = fw.extractVueComponents(
              fileInfo.vueMeta,
              filePath,
              functionCallArgs,
              returns
            );
            vueComponents = vueComponentData.vue_components || [];
            vueComponentProps = vueComponentData.vue_component_props || [];
            vueComponentEmits = vueComponentData.vue_component_emits || [];
            vueComponentSetupReturns = vueComponentData.vue_component_setup_returns || [];
            const activeComponentName = vueComponentData.primaryName;

            vueHooks = fw.extractVueHooks(functionCallArgs, activeComponentName);
            vueProvideInject = fw.extractVueProvideInject(functionCallArgs, activeComponentName);
            vueDirectives = fw.extractVueDirectives(
              fileInfo.vueMeta.templateAst,
              activeComponentName,
              VueNodeTypes
            );
          }

          // Step 22: GraphQL extractors
          const apolloResolvers = fw.extractApolloResolvers(
            functions,
            func_params,
            {},
            filePath
          );
          const nestjsResolvers = fw.extractNestJSResolvers(
            functions,
            classes,
            func_decorators,
            func_decorator_args,
            class_decorators,
            class_decorator_args,
            func_params,
            func_param_decorators,
            filePath
          );
          const graphql_resolvers = [
            ...(apolloResolvers.graphql_resolvers || []),
            ...(nestjsResolvers.graphql_resolvers || []),
          ];
          const graphql_resolver_params = [
            ...(apolloResolvers.graphql_resolver_params || []),
            ...(nestjsResolvers.graphql_resolver_params || []),
          ];

          // Step 23: Extract CFG (optimized - skips non-executable code)
          console.error(`[DEBUG JS BATCH] Extracting CFG for ${filePath}`);
          const cfgData = cfg.extractCFG(sourceFile, functions, filePath);

          // Step 24: Count nodes
          const nodeCount = core.countNodes(sourceFile, ts);

          // Assemble result
          results[fileInfo.original] = {
            success: true,
            fileName: fileInfo.absolute,
            languageVersion: ts.ScriptTarget[sourceFile.languageVersion],
            ast: null,
            diagnostics: diagnostics,
            imports: imports,
            nodeCount: nodeCount,
            hasTypes: true,
            jsxMode: jsxMode,
            extracted_data: {
              // Core language
              functions: functions,
              func_params: func_params,
              func_decorators: func_decorators,
              func_decorator_args: func_decorator_args,
              func_param_decorators: func_param_decorators,
              classes: classes,
              class_decorators: class_decorators,
              class_decorator_args: class_decorator_args,
              class_properties: classProperties,
              // Module system
              imports: imports,
              import_specifiers: import_specifiers,
              import_styles: importStyles,
              import_style_names: import_style_names,
              resolved_imports: refs,
              // Data flow
              assignments: assignments,
              assignment_source_vars: assignment_source_vars,
              returns: returns,
              return_source_vars: return_source_vars,
              // Other extractors
              env_var_usage: envVarUsage,
              orm_relationships: ormRelationships,
              calls: calls,
              function_call_args: functionCallArgs,
              object_literals: objectLiterals,
              variable_usage: variableUsage,
              // React
              react_components: reactComponents,
              react_component_hooks: react_component_hooks,
              react_hooks: reactHooks,
              react_hook_dependencies: react_hook_dependencies,
              // API & ORM
              orm_queries: ormQueries,
              routes: apiEndpoints,
              express_middleware_chains: middlewareChains,
              validation_framework_usage: validationUsage,
              sql_queries: sqlQueries,
              cdk_constructs: cdkData.cdk_constructs || [],
              cdk_construct_properties: cdkData.cdk_construct_properties || [],
              // Sequelize
              sequelize_models: sequelizeData.sequelize_models || [],
              sequelize_associations: sequelizeData.sequelize_associations || [],
              sequelize_model_fields: sequelizeData.sequelize_model_fields || [],
              // BullMQ
              bullmq_queues: bullmqData.bullmq_queues || [],
              bullmq_workers: bullmqData.bullmq_workers || [],
              // Angular
              angular_components: angularData.angular_components || [],
              angular_services: angularData.angular_services || [],
              angular_modules: angularData.angular_modules || [],
              angular_guards: angularData.angular_guards || [],
              // Vue
              vue_components: vueComponents,
              vue_component_props: vueComponentProps,
              vue_component_emits: vueComponentEmits,
              vue_component_setup_returns: vueComponentSetupReturns,
              vue_hooks: vueHooks,
              vue_directives: vueDirectives,
              vue_provide_inject: vueProvideInject,
              // GraphQL
              graphql_resolvers: graphql_resolvers,
              graphql_resolver_params: graphql_resolver_params,
              // Frontend & CFG
              frontend_api_calls: frontendApiCalls,
              scope_map: Object.fromEntries(scopeMap),
              cfg_blocks: cfgData.cfg_blocks || [],
              cfg_edges: cfgData.cfg_edges || [],
              cfg_block_statements: cfgData.cfg_block_statements || [],
            },
          };

          console.error(`[DEBUG JS BATCH] Complete for ${filePath}`);
        } catch (error: any) {
          results[fileInfo.original] = {
            success: false,
            error: `Error processing file: ${error.message}`,
            ast: null,
            diagnostics: [],
            symbols: [],
          };
        }
      }
    }

    // Add preprocessing errors
    for (const [failedPath, message] of preprocessingErrors.entries()) {
      results[failedPath] = {
        success: false,
        error: message,
        ast: null,
        diagnostics: [],
        symbols: [],
      };
    }

    // =====================================================
    // ZOD VALIDATION BEFORE OUTPUT
    // =====================================================
    try {
      // Note: We validate the structure but allow pass-through for now
      // Full strict validation can be enabled once all extractors are aligned
      const validated = ExtractionReceiptSchema.parse(results);
      fs.writeFileSync(outputPath, JSON.stringify(validated, null, 2), 'utf8');
      console.error('[BATCH DEBUG] Output validated and written successfully');
    } catch (e) {
      if (e instanceof z.ZodError) {
        console.error('[BATCH WARN] Zod validation failed, writing raw results:');
        console.error(JSON.stringify(e.errors.slice(0, 5), null, 2));
        // Write anyway for debugging - validation can be strict later
        fs.writeFileSync(outputPath, JSON.stringify(results, null, 2), 'utf8');
      } else {
        throw e;
      }
    }

    process.exit(0);
  } catch (error: any) {
    console.error(
      JSON.stringify({
        success: false,
        error: error.message,
        stack: error.stack,
      })
    );
    process.exit(1);
  }
}

// Run
main().catch((error) => {
  console.error(
    JSON.stringify({
      success: false,
      error: `Unhandled error: ${error.message}`,
      stack: error.stack,
    })
  );
  process.exit(1);
});
