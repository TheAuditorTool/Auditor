process.on("uncaughtException", (err: Error) => {
  const crashReport = {
    type: "FATAL_CRASH",
    category: "uncaughtException",
    error: err.message,
    stack: err.stack,
    timestamp: new Date().toISOString(),
  };
  console.error(JSON.stringify(crashReport));
  process.exit(1);
});

process.on(
  "unhandledRejection",
  (reason: unknown, promise: Promise<unknown>) => {
    const crashReport = {
      type: "FATAL_CRASH",
      category: "unhandledRejection",
      error: reason instanceof Error ? reason.message : String(reason),
      stack: reason instanceof Error ? reason.stack : undefined,
      timestamp: new Date().toISOString(),
    };
    console.error(JSON.stringify(crashReport));
    process.exit(1);
  },
);

import * as path from "path";
import * as fs from "fs";
import * as os from "os";
import * as crypto from "crypto";
import { pathToFileURL } from "url";

import * as core from "./extractors/core_language.js";
import * as flow from "./extractors/data_flow.js";
import * as mod from "./extractors/module_framework.js";
import * as sec from "./extractors/security_extractors.js";
import * as fw from "./extractors/framework_extractors.js";
import * as seq from "./extractors/sequelize_extractors.js";
import * as bull from "./extractors/bullmq_extractors.js";
import * as ang from "./extractors/angular_extractors.js";
import * as cfg from "./extractors/cfg_extractor.js";

import { ExtractionReceiptSchema } from "./schema.js";
import { z } from "zod";
import { attachManifest } from "./fidelity.js";

let parseVueSfc: any = null;
let compileVueScript: any = null;
let compileVueTemplate: any = null;
let VueNodeTypes: any = null;

try {
  const vueSfcModule = require("@vue/compiler-sfc");
  if (vueSfcModule) {
    parseVueSfc = vueSfcModule.parse;
    compileVueScript = vueSfcModule.compileScript;
    compileVueTemplate = vueSfcModule.compileTemplate;
  }
} catch (err: any) {
  console.error(
    `[VUE SUPPORT DISABLED] @vue/compiler-sfc not available: ${err.message}`,
  );
}

try {
  const vueDomModule = require("@vue/compiler-dom");
  if (vueDomModule) {
    VueNodeTypes = vueDomModule.NodeTypes;
  }
} catch (err: any) {
  console.error(
    `[VUE TEMPLATE SUPPORT DISABLED] @vue/compiler-dom not available: ${err.message}`,
  );
}

function sanitizeVirtualPaths(
  data: any,
  virtualToOriginalMap: Map<string, string>,
): any {
  if (!data) return data;

  if (Array.isArray(data)) {
    return data.map((item) => sanitizeVirtualPaths(item, virtualToOriginalMap));
  }

  if (typeof data === "object") {
    const sanitized: any = {};
    for (const [key, value] of Object.entries(data)) {
      if (
        (key === "file" ||
          key === "defined_in" ||
          key === "callee_file_path" ||
          key === "path" ||
          key === "fileName") &&
        typeof value === "string" &&
        value.includes("/virtual_vue/")
      ) {
        const match = value.match(/\/virtual_vue\/([^.]+)/);
        if (match) {
          const scopeId = match[1];
          const original = virtualToOriginalMap.get(scopeId);
          if (!original) {
            console.error(
              `[SANITIZE ERROR] Virtual path ${value} has no mapping for scopeId ${scopeId}`,
            );
          }
          sanitized[key] = original || value;
        } else {
          console.error(
            `[SANITIZE ERROR] Virtual path ${value} does not match expected pattern`,
          );
          sanitized[key] = value;
        }
      } else {
        sanitized[key] = sanitizeVirtualPaths(value, virtualToOriginalMap);
      }
    }
    return sanitized;
  }

  return data;
}

interface BatchRequest {
  files: string[];
  projectRoot: string;
  jsxMode?: "transformed" | "preserved";
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

function createVueScopeId(filePath: string): string {
  return crypto.createHash("sha256").update(filePath).digest("hex").slice(0, 8);
}

function ensureVueCompilerAvailable(): void {
  if (!parseVueSfc || !compileVueScript) {
    throw new Error(
      "Vue SFC support requires @vue/compiler-sfc. Install dependency or skip .vue files.",
    );
  }
}

function prepareVueSfcFile(filePath: string): VueMeta {
  ensureVueCompilerAvailable();

  const source = fs.readFileSync(filePath, "utf8");
  const { descriptor, errors } = parseVueSfc(source, { filename: filePath });

  if (errors && errors.length > 0) {
    const firstError = errors[0];
    const message =
      typeof firstError === "string"
        ? firstError
        : firstError.message || firstError.msg || "Unknown Vue SFC parse error";
    throw new Error(message);
  }

  if (!descriptor.script && !descriptor.scriptSetup) {
    throw new Error("Vue SFC is missing <script> or <script setup> block");
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
    "js";

  const isTs = langHint && langHint.toLowerCase().includes("ts");
  const virtualPath = `/virtual_vue/${scopeId}.${isTs ? "ts" : "js"}`;

  let templateAst = null;
  if (descriptor.template && descriptor.template.content) {
    if (typeof compileVueTemplate === "function") {
      try {
        const templateResult = compileVueTemplate({
          source: descriptor.template.content,
          filename: filePath,
          id: scopeId,
        });
        templateAst = templateResult.ast || null;
      } catch (err: any) {
        console.error(
          `[VUE TEMPLATE WARN] Failed to compile template for ${filePath}: ${err.message}`,
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

function createVueAwareCompilerHost(
  ts: typeof import("typescript"),
  compilerOptions: import("typescript").CompilerOptions,
  vueContentMap: Map<string, string>,
): import("typescript").CompilerHost {
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
      languageVersion: import("typescript").ScriptTarget,
      onError?: (message: string) => void,
      shouldCreateNewSourceFile?: boolean,
    ): import("typescript").SourceFile | undefined => {
      if (vueContentMap.has(fileName)) {
        const content = vueContentMap.get(fileName)!;
        return ts.createSourceFile(fileName, content, languageVersion, true);
      }
      return defaultHost.getSourceFile(
        fileName,
        languageVersion,
        onError,
        shouldCreateNewSourceFile,
      );
    },
  };
}

function findNearestTsconfig(
  startPath: string,
  projectRoot: string,
  ts: typeof import("typescript"),
): string | null {
  let currentDir = path.resolve(path.dirname(startPath));
  const projectRootResolved = path.resolve(projectRoot);

  while (true) {
    const candidate = path.join(currentDir, "tsconfig.json");
    if (fs.existsSync(candidate)) {
      return candidate;
    }
    if (
      currentDir === projectRootResolved ||
      currentDir === path.dirname(currentDir)
    ) {
      break;
    }
    currentDir = path.dirname(currentDir);
  }

  return null;
}

async function main(): Promise<void> {
  try {
    const requestPath = process.argv[2];
    const outputPath = process.argv[3];

    if (!requestPath || !outputPath) {
      console.error(
        JSON.stringify({ error: "Request and output paths required" }),
      );
      process.exit(1);
    }

    const request: BatchRequest = JSON.parse(
      fs.readFileSync(requestPath, "utf8"),
    );
    const filePaths = request.files || [];
    const projectRoot = request.projectRoot;
    const jsxMode = request.jsxMode || "transformed";

    if (filePaths.length === 0) {
      fs.writeFileSync(outputPath, JSON.stringify({}), "utf8");
      process.exit(0);
    }

    if (!projectRoot) {
      throw new Error("projectRoot not provided in batch request");
    }

    let tsPath: string | null = null;
    let searchDir = projectRoot;

    for (let i = 0; i < 10; i++) {
      const potentialPath = path.join(
        searchDir,
        ".auditor_venv",
        ".theauditor_tools",
        "node_modules",
        "typescript",
        "lib",
        "typescript.js",
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
        ".auditor_venv",
        ".theauditor_tools",
        "node_modules",
        "typescript",
        "lib",
        "typescript.js",
      );
    }

    if (!fs.existsSync(tsPath)) {
      throw new Error(`TypeScript not found at: ${tsPath}`);
    }

    const tsModule = await import(pathToFileURL(tsPath).href);
    const ts: typeof import("typescript") = tsModule.default || tsModule;

    const configMap = request.configMap || {};
    const resolvedProjectRoot = path.resolve(projectRoot);

    const normalizedConfigMap = new Map<string, string | null>();
    for (const [key, value] of Object.entries(configMap)) {
      const resolvedKey = path.resolve(key);
      normalizedConfigMap.set(resolvedKey, value ? path.resolve(value) : null);
    }

    const filesByConfig = new Map<string, FileEntry[]>();
    const DEFAULT_KEY = "__DEFAULT__";
    const preprocessingErrors = new Map<string, string>();
    const virtualToOriginalMap = new Map<string, string>();

    for (const filePath of filePaths) {
      const absoluteFilePath = path.resolve(filePath);
      const ext = path.extname(absoluteFilePath).toLowerCase();
      const fileEntry: FileEntry = {
        original: filePath,
        absolute: absoluteFilePath,
        cleanup: null,
        vueMeta: null,
      };

      if (ext === ".vue") {
        try {
          const vueMeta = prepareVueSfcFile(absoluteFilePath);
          fileEntry.absolute = vueMeta.virtualPath;
          fileEntry.vueMeta = vueMeta;
          virtualToOriginalMap.set(vueMeta.scopeId, filePath);
        } catch (err: any) {
          preprocessingErrors.set(
            filePath,
            `Vue SFC preprocessing failed: ${err.message}`,
          );
          continue;
        }
      }

      const mappedConfig = normalizedConfigMap.get(absoluteFilePath);
      const nearestConfig =
        mappedConfig ||
        findNearestTsconfig(absoluteFilePath, resolvedProjectRoot, ts);
      const groupKey = nearestConfig
        ? path.resolve(nearestConfig)
        : DEFAULT_KEY;

      if (!filesByConfig.has(groupKey)) {
        filesByConfig.set(groupKey, []);
      }
      filesByConfig.get(groupKey)!.push(fileEntry);
    }

    const results: Record<string, FileResult> = {};
    const jsxEmitMode =
      jsxMode === "preserved" ? ts.JsxEmit.Preserve : ts.JsxEmit.React;

    console.error(
      `[BATCH DEBUG] Processing ${filePaths.length} files, jsxMode=${jsxMode}`,
    );

    for (const [configKey, groupedFiles] of filesByConfig.entries()) {
      if (!groupedFiles || groupedFiles.length === 0) {
        continue;
      }

      let compilerOptions!: import("typescript").CompilerOptions;
      let program: import("typescript").Program;

      const vueContentMap = new Map<string, string>();
      for (const fileInfo of groupedFiles) {
        if (fileInfo.vueMeta) {
          vueContentMap.set(
            fileInfo.vueMeta.virtualPath,
            fileInfo.vueMeta.scriptContent,
          );
        }
      }

      let loadedConfigSuccessfully = false;

      if (configKey !== DEFAULT_KEY) {
        try {
          const configFileContent = fs.readFileSync(configKey, "utf8");

          const { config, error } = ts.parseConfigFileTextToJson(
            configKey,
            configFileContent,
          );
          if (error) {
            throw new Error(
              typeof error.messageText === "string"
                ? error.messageText
                : JSON.stringify(error.messageText),
            );
          }

          const parseConfigHost = {
            useCaseSensitiveFileNames:
              ts.sys?.useCaseSensitiveFileNames ?? true,
            readDirectory: ts.sys?.readDirectory ?? (() => []),
            fileExists: fs.existsSync,
            readFile: (f: string) => fs.readFileSync(f, "utf8"),
          };

          const parsedConfig = ts.parseJsonConfigFileContent(
            config,
            parseConfigHost,
            path.dirname(configKey),
            {},
            configKey,
          );

          if (parsedConfig.errors && parsedConfig.errors.length > 0) {
            const errorMessages = parsedConfig.errors
              .map((err) =>
                ts.flattenDiagnosticMessageText(err.messageText, "\n"),
              )
              .join("; ");
            throw new Error(errorMessages);
          }

          compilerOptions = { ...parsedConfig.options };
          compilerOptions.jsx = jsxEmitMode;

          const hasJavaScriptFiles = groupedFiles.some((fileInfo) => {
            const ext = path.extname(fileInfo.absolute).toLowerCase();
            return (
              ext === ".js" ||
              ext === ".jsx" ||
              ext === ".cjs" ||
              ext === ".mjs"
            );
          });
          if (hasJavaScriptFiles) {
            compilerOptions.allowJs = true;
            if (compilerOptions.checkJs === undefined) {
              compilerOptions.checkJs = false;
            }
          }

          loadedConfigSuccessfully = true;
        } catch (err: any) {
          console.error(
            `[BATCH WARN] Failed to load tsconfig ${configKey}, falling back to defaults: ${err.message}`,
          );
        }
      }

      if (configKey === DEFAULT_KEY || !loadedConfigSuccessfully) {
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
      }

      const host =
        vueContentMap.size > 0
          ? createVueAwareCompilerHost(ts, compilerOptions, vueContentMap)
          : undefined;

      program = ts.createProgram(
        groupedFiles.map((f) => f.absolute),
        compilerOptions,
        host,
      );

      console.error(
        `[BATCH DEBUG] Created program, rootNames=${program.getRootFileNames().length}`,
      );
      const checker = program.getTypeChecker();

      for (const fileInfo of groupedFiles) {
        try {
          const sourceFile = program.getSourceFile(fileInfo.absolute);
          if (!sourceFile) {
            console.error(
              `[DEBUG JS BATCH] Could not load sourceFile for ${fileInfo.original}`,
            );
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

          const diagnostics: any[] = [];
          const fileDiagnostics = ts.getPreEmitDiagnostics(program, sourceFile);
          fileDiagnostics.forEach((diagnostic) => {
            const message = ts.flattenDiagnosticMessageText(
              diagnostic.messageText,
              "\n",
            );
            const location =
              diagnostic.file && diagnostic.start
                ? diagnostic.file.getLineAndCharacterOfPosition(
                    diagnostic.start,
                  )
                : null;

            diagnostics.push({
              message,
              category: ts.DiagnosticCategory[diagnostic.category],
              code: diagnostic.code,
              line: location ? location.line + 1 : null,
              column: location ? location.character : null,
            });
          });

          const scopeMap = core.buildScopeMap(sourceFile, ts);

          const importData = mod.extractImports(sourceFile, ts, filePath);
          const imports = importData.imports;
          const import_specifiers = importData.import_specifiers;

          const funcData = core.extractFunctions(
            sourceFile,
            checker,
            ts,
            filePath,
          );
          const functions = funcData.functions;
          const func_params = funcData.func_params;
          const func_decorators = funcData.func_decorators;
          const func_decorator_args = funcData.func_decorator_args;
          const func_param_decorators = funcData.func_param_decorators;

          const functionParamsMap = new Map<string, Array<{ name: string }>>();
          func_params.forEach(
            (p: { function_name: string; param_name: string }) => {
              if (!functionParamsMap.has(p.function_name)) {
                functionParamsMap.set(p.function_name, []);
              }
              functionParamsMap
                .get(p.function_name)!
                .push({ name: p.param_name });
            },
          );

          const classData = core.extractClasses(
            sourceFile,
            checker,
            ts,
            filePath,
            scopeMap,
          );
          const classes = classData.classes;
          const class_decorators = classData.class_decorators;
          const class_decorator_args = classData.class_decorator_args;

          const interfaceData = core.extractInterfaces(
            sourceFile,
            checker,
            ts,
            filePath,
          );
          const interfaces = interfaceData.interfaces;

          const calls = flow.extractCalls(
            sourceFile,
            checker,
            ts,
            filePath,
            functions,
            classes,
            scopeMap,
            resolvedProjectRoot,
          );

          const classProperties = core.extractClassProperties(
            sourceFile,
            ts,
            filePath,
            classes,
          );

          const envVarUsage = mod.extractEnvVarUsage(sourceFile, ts, scopeMap);

          const ormRelationships = mod.extractORMRelationships(sourceFile, ts);

          const assignmentData = flow.extractAssignments(
            sourceFile,
            ts,
            scopeMap,
            filePath,
          );
          const assignments = assignmentData.assignments;
          const assignment_source_vars = assignmentData.assignment_source_vars;

          const refs = mod.extractRefs(imports, import_specifiers);
          const functionCallArgs = flow.extractFunctionCallArgs(
            sourceFile,
            checker,
            ts,
            scopeMap,
            functionParamsMap,
            resolvedProjectRoot,
          );

          const returnData = flow.extractReturns(
            sourceFile,
            ts,
            scopeMap,
            filePath,
          );
          const returns = returnData.returns;
          const return_source_vars = returnData.return_source_vars;

          const objectLiterals = flow.extractObjectLiterals(
            sourceFile,
            ts,
            scopeMap,
            filePath,
          );

          const variableUsage = flow.extractVariableUsage(
            assignments,
            functionCallArgs,
            assignment_source_vars,
            filePath,
          );

          const importStyleData = mod.extractImportStyles(
            imports,
            import_specifiers,
            filePath,
            program,
            sourceFile,
            ts as any,
            resolvedProjectRoot,
          );
          const importStyles = importStyleData.import_styles;
          const import_style_names = importStyleData.import_style_names;

          const reactComponentData = fw.extractReactComponents(
            functions,
            classes,
            returns,
            functionCallArgs,
            filePath,
            imports,
          );
          const reactComponents = reactComponentData.react_components;
          const react_component_hooks =
            reactComponentData.react_component_hooks;

          const reactHookData = fw.extractReactHooks(
            functionCallArgs,
            scopeMap,
            filePath,
          );
          const reactHooks = reactHookData.react_hooks;
          const react_hook_dependencies = reactHookData.react_hook_dependencies;

          const ormQueries = sec.extractORMQueries(functionCallArgs);
          const apiEndpointData = sec.extractAPIEndpoints(functionCallArgs);
          const apiEndpoints = apiEndpointData.endpoints || [];
          const middlewareChains = apiEndpointData.middlewareChains || [];
          const validationCalls = sec.extractValidationFrameworkUsage(
            functionCallArgs,
            assignments,
            imports,
          );
          const schemaDefs = sec.extractSchemaDefinitions(
            functionCallArgs,
            assignments,
            imports,
          );
          const validationUsage = [...validationCalls, ...schemaDefs];
          const sqlQueries = sec.extractSQLQueries(functionCallArgs);
          const cdkData = sec.extractCDKConstructs(
            functionCallArgs,
            imports,
            import_specifiers,
          );
          const frontendApiCalls = sec.extractFrontendApiCalls(
            functionCallArgs,
            imports,
            import_specifiers,
          );
          const jwtPatterns = sec.extractJWTPatterns(functionCallArgs, imports);

          const sequelizeData = seq.extractSequelizeModels(
            sourceFile,
            classes,
            functionCallArgs,
            filePath,
          );

          const bullmqData = bull.extractBullMQQueueWorkers(
            sourceFile,
            filePath,
          );

          const angularData = ang.extractAngularDefinitions(
            classes,
            class_decorators,
            class_decorator_args,
            sourceFile,
            filePath,
          );

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
              returns,
            );
            vueComponents = vueComponentData.vue_components || [];
            vueComponentProps = vueComponentData.vue_component_props || [];
            vueComponentEmits = vueComponentData.vue_component_emits || [];
            vueComponentSetupReturns =
              vueComponentData.vue_component_setup_returns || [];
            const activeComponentName = vueComponentData.primaryName;

            vueHooks = fw.extractVueHooks(
              functionCallArgs,
              activeComponentName,
            );
            vueProvideInject = fw.extractVueProvideInject(
              functionCallArgs,
              activeComponentName,
            );
            vueDirectives = fw.extractVueDirectives(
              fileInfo.vueMeta.templateAst,
              activeComponentName,
              VueNodeTypes,
            );
          }

          const apolloResolvers = fw.extractApolloResolvers(
            functions,
            func_params,
            {},
            filePath,
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
            filePath,
          );
          const graphql_resolvers = [
            ...(apolloResolvers.graphql_resolvers || []),
            ...(nestjsResolvers.graphql_resolvers || []),
          ];
          const graphql_resolver_params = [
            ...(apolloResolvers.graphql_resolver_params || []),
            ...(nestjsResolvers.graphql_resolver_params || []),
          ];

          console.error(`[DEBUG JS BATCH] Extracting CFG for ${filePath}`);
          const cfgData = cfg.extractCFG(sourceFile, functions, filePath);

          const nodeCount = core.countNodes(sourceFile, ts);

          results[fileInfo.original] = {
            success: true,
            fileName: fileInfo.original,
            languageVersion: ts.ScriptTarget[sourceFile.languageVersion],
            ast: null,
            diagnostics: diagnostics,
            imports: imports,
            nodeCount: nodeCount,
            hasTypes: true,
            jsxMode: jsxMode,
            extracted_data: {
              functions: functions,
              func_params: func_params,
              func_decorators: func_decorators,
              func_decorator_args: func_decorator_args,
              func_param_decorators: func_param_decorators,
              classes: classes,
              interfaces: interfaces,
              class_decorators: class_decorators,
              class_decorator_args: class_decorator_args,
              class_properties: classProperties,
              imports: imports,
              import_specifiers: import_specifiers,
              import_styles: importStyles,
              import_style_names: import_style_names,
              refs: refs,
              assignments: assignments,
              assignment_source_vars: assignment_source_vars,
              returns: returns,
              return_source_vars: return_source_vars,
              env_var_usage: envVarUsage,
              orm_relationships: ormRelationships,
              calls: calls,
              function_call_args: functionCallArgs,
              object_literals: objectLiterals,
              variable_usage: variableUsage,
              react_components: reactComponents,
              react_component_hooks: react_component_hooks,
              react_hooks: reactHooks,
              react_hook_dependencies: react_hook_dependencies,
              orm_queries: ormQueries,
              api_endpoints: apiEndpoints,
              middleware_chains: middlewareChains,
              validation_calls: validationUsage,
              sql_queries: sqlQueries,
              cdk_constructs: cdkData.cdk_constructs || [],
              cdk_construct_properties: cdkData.cdk_construct_properties || [],
              sequelize_models: sequelizeData.sequelize_models || [],
              sequelize_associations:
                sequelizeData.sequelize_associations || [],
              sequelize_model_fields:
                sequelizeData.sequelize_model_fields || [],
              bullmq_queues: bullmqData.bullmq_queues || [],
              bullmq_workers: bullmqData.bullmq_workers || [],
              angular_components: angularData.angular_components || [],
              angular_services: angularData.angular_services || [],
              angular_modules: angularData.angular_modules || [],
              angular_guards: angularData.angular_guards || [],
              vue_components: vueComponents,
              vue_component_props: vueComponentProps,
              vue_component_emits: vueComponentEmits,
              vue_component_setup_returns: vueComponentSetupReturns,
              vue_hooks: vueHooks,
              vue_directives: vueDirectives,
              vue_provide_inject: vueProvideInject,
              graphql_resolvers: graphql_resolvers,
              graphql_resolver_params: graphql_resolver_params,
              frontend_api_calls: frontendApiCalls,
              jwt_patterns: jwtPatterns,
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

    for (const [failedPath, message] of preprocessingErrors.entries()) {
      results[failedPath] = {
        success: false,
        error: message,
        ast: null,
        diagnostics: [],
        symbols: [],
      };
    }

    const sanitizedResults = sanitizeVirtualPaths(
      results,
      virtualToOriginalMap,
    );

    const withManifest = attachManifest(sanitizedResults);

    try {
      const validated = ExtractionReceiptSchema.parse(withManifest);
      fs.writeFileSync(outputPath, JSON.stringify(validated, null, 2), "utf8");
      console.error("[BATCH DEBUG] Output validated and written successfully");
    } catch (e) {
      if (e instanceof z.ZodError) {
        console.error(
          "[BATCH ERROR] Zod validation failed - refusing to write invalid data:",
        );
        console.error(JSON.stringify(e.errors.slice(0, 10), null, 2));
        process.exit(1);
      }
      throw e;
    }

    process.exit(0);
  } catch (error: any) {
    console.error(
      JSON.stringify({
        success: false,
        error: error.message,
        stack: error.stack,
      }),
    );
    process.exit(1);
  }
}

main().catch((error) => {
  console.error(
    JSON.stringify({
      success: false,
      error: `Unhandled error: ${error.message}`,
      stack: error.stack,
    }),
  );
  process.exit(1);
});
