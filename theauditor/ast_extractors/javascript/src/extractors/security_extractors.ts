import type {
  ORMQuery as IORMQuery,
  APIEndpoint as IAPIEndpoint,
  MiddlewareChain as IMiddlewareChain,
  ValidationCall as IValidationCall,
  SchemaDefinition as ISchemaDefinition,
  SQLQuery as ISQLQuery,
  CDKConstruct as ICDKConstruct,
  CDKConstructProperty as ICDKConstructProperty,
  FrontendAPICall as IFrontendAPICall,
  FunctionCallArg as IFunctionCallArg,
  Assignment as IAssignment,
  Import as IImport,
  ImportSpecifier as IImportSpecifier,
  JWTPattern as IJWTPattern,
} from "../schema.js";

const ORM_METHODS = new Set([
  "findAll",
  "findOne",
  "findByPk",
  "create",
  "update",
  "destroy",
  "upsert",
  "bulkCreate",
  "count",
  "max",
  "min",
  "sum",
  "findMany",
  "findUnique",
  "findFirst",
  "createMany",
  "updateMany",
  "deleteMany",
  "aggregate",
  "groupBy",
]);

export function extractORMQueries(
  functionCallArgs: IFunctionCallArg[],
): IORMQuery[] {
  const queries: IORMQuery[] = [];

  for (const call of functionCallArgs) {
    const method = call.callee_function
      ? call.callee_function.split(".").pop() || ""
      : "";
    if (!ORM_METHODS.has(method)) continue;

    const hasIncludes =
      call.argument_expr && call.argument_expr.includes("include:");
    const hasLimit = Boolean(
      call.argument_expr &&
      (call.argument_expr.includes("limit:") ||
        call.argument_expr.includes("take:")),
    );

    queries.push({
      line: call.line,
      query_type: call.callee_function || "",
      model_name: call.callee_function?.split(".")[0] || null,
      includes: hasIncludes ? "has_includes" : null,
      has_limit: hasLimit,
      has_transaction: false,
    });
  }

  return queries;
}

const HTTP_METHODS = new Set([
  "get",
  "post",
  "put",
  "delete",
  "patch",
  "head",
  "options",
  "all",
]);

interface ExtractAPIEndpointsResult {
  endpoints: IAPIEndpoint[];
  middlewareChains: IMiddlewareChain[];
}

export function extractAPIEndpoints(
  functionCallArgs: IFunctionCallArg[],
): ExtractAPIEndpointsResult {
  const endpoints: IAPIEndpoint[] = [];
  const middlewareChains: IMiddlewareChain[] = [];

  const callsByLine: Record<
    number,
    {
      method: string;
      callee: string;
      caller_function: string;
      calls: IFunctionCallArg[];
    }
  > = {};

  for (const call of functionCallArgs) {
    const callee = call.callee_function || "";
    if (!callee.includes(".")) continue;

    const parts = callee.split(".");
    const receiver = parts.slice(0, -1).join(".").toLowerCase();
    const method = parts[parts.length - 1];

    const ROUTER_PATTERNS = [
      "router",
      "app",
      "express",
      "server",
      "route",
      "fastify",
      "koa",
      "hapi",
      "nest",
      "hono",
      "elysia",
      "oak",
      "polka",
    ];
    const isRouter = ROUTER_PATTERNS.some((p) => receiver.includes(p));

    if (!isRouter || !HTTP_METHODS.has(method)) continue;

    if (!callsByLine[call.line]) {
      callsByLine[call.line] = {
        method: method,
        callee: callee,
        caller_function: call.caller_function || "global",
        calls: [],
      };
    }
    callsByLine[call.line].calls.push(call);
  }

  for (const [lineStr, data] of Object.entries(callsByLine)) {
    const line = parseInt(lineStr);
    const { method, caller_function, calls } = data;

    calls.sort((a, b) => (a.argument_index || 0) - (b.argument_index || 0));

    const routeArg = calls.find((c) => c.argument_index === 0);
    if (!routeArg) continue;

    const route = routeArg.argument_expr;
    if (!route || typeof route !== "string") continue;

    const cleanRoute = route.replace(/['"]/g, "").trim();

    endpoints.push({
      line: line,
      method: method.toUpperCase(),
      pattern: cleanRoute,
      handler_function: caller_function,
      requires_auth: false,
    });

    for (let i = 1; i < calls.length; i++) {
      const call = calls[i];
      const isController = i === calls.length - 1;
      let handlerFunction: string | null = null;
      const expr = call.argument_expr || "";
      if (expr && !expr.includes("=>") && !expr.includes("function")) {
        // Named handler reference (e.g., "userController.create")
        handlerFunction = expr;
      } else if (expr.includes("=>") || expr.includes("function")) {
        // Inline arrow/function - generate clean name from route metadata
        handlerFunction = `${method.toUpperCase()}:${cleanRoute}@${line}`;
      }

      middlewareChains.push({
        route_line: line,
        route_path: cleanRoute,
        route_method: method.toUpperCase(),
        execution_order: i - 1,
        handler_expr: expr,
        handler_type: isController ? "controller" : "middleware",
        handler_function: handlerFunction,
      });
    }
  }

  return { endpoints, middlewareChains };
}

interface ValidationFramework {
  name: string;
  importedNames: string[];
}

const VALIDATION_FRAMEWORKS: Record<string, string[]> = {
  zod: ["z", "zod", "ZodSchema"],
  joi: ["Joi", "joi"],
  yup: ["yup", "Yup"],
  ajv: ["Ajv", "ajv"],
  "class-validator": ["validate", "validateSync", "validateOrReject"],
  "express-validator": ["validationResult", "matchedData", "checkSchema"],
};

function detectValidationFrameworks(imports: IImport[]): ValidationFramework[] {
  const detected: ValidationFramework[] = [];

  for (const imp of imports) {
    const moduleName = imp.module || "";
    if (!moduleName) continue;

    for (const [framework, names] of Object.entries(VALIDATION_FRAMEWORKS)) {
      if (moduleName.includes(framework)) {
        detected.push({ name: framework, importedNames: names });
        break;
      }
    }
  }

  return detected;
}

const VALIDATOR_METHODS = [
  "parse",
  "parseAsync",
  "safeParse",
  "safeParseAsync",
  "validate",
  "validateAsync",
  "validateSync",
  "isValid",
  "isValidSync",
];

function isValidatorMethod(callee: string): boolean {
  const method = callee.split(".").pop() || "";
  return VALIDATOR_METHODS.includes(method);
}

function looksLikeSchemaVariable(varName: string): boolean {
  const lower = varName.toLowerCase();
  if (lower.endsWith("schema") || lower.endsWith("validator")) return true;
  if (lower.includes("schema") || lower.includes("validator")) return true;
  if (lower.startsWith("validate")) return true;
  if (["schema", "validator", "validation"].includes(lower)) return true;
  return false;
}

export function extractValidationFrameworkUsage(
  functionCallArgs: IFunctionCallArg[],
  assignments: IAssignment[],
  imports: IImport[],
): IValidationCall[] {
  const validationCalls: IValidationCall[] = [];

  const frameworks = detectValidationFrameworks(imports);
  if (frameworks.length === 0) return validationCalls;

  const schemaVars: Record<string, { framework: string }> = {};
  for (const assign of assignments) {
    const source = assign.source_expr || "";
    for (const fw of frameworks) {
      for (const name of fw.importedNames) {
        if (source.includes(`${name}.`)) {
          schemaVars[assign.target_var] = { framework: fw.name };
          break;
        }
      }
    }
  }

  for (const call of functionCallArgs) {
    const callee = call.callee_function || "";
    if (!callee) continue;

    let isValidation = false;
    let frameworkName = "unknown";

    for (const fw of frameworks) {
      for (const name of fw.importedNames) {
        if (callee.startsWith(`${name}.`) && isValidatorMethod(callee)) {
          isValidation = true;
          frameworkName = fw.name;
          break;
        }
      }
      if (isValidation) break;
    }

    if (!isValidation && callee.includes(".") && isValidatorMethod(callee)) {
      const varName = callee.split(".")[0];
      if (varName in schemaVars) {
        isValidation = true;
        frameworkName = schemaVars[varName].framework;
      } else if (looksLikeSchemaVariable(varName)) {
        isValidation = true;
        frameworkName = frameworks[0]?.name || "unknown";
      }
    }

    if (isValidation) {
      validationCalls.push({
        line: call.line,
        framework: frameworkName,
        function_name: callee,
        method: callee.split(".").pop() || "",
        variable_name: callee.includes(".") ? callee.split(".")[0] : null,
        is_validator: isValidatorMethod(callee),
        argument_expr: (call.argument_expr || "").substring(0, 2000),
      });
    }
  }

  return validationCalls;
}

const SCHEMA_BUILDERS: Record<string, string[]> = {
  zod: [
    "object",
    "string",
    "number",
    "array",
    "boolean",
    "date",
    "enum",
    "union",
    "tuple",
    "record",
    "map",
    "set",
    "promise",
    "function",
    "lazy",
    "literal",
    "void",
    "undefined",
    "null",
    "any",
    "unknown",
    "never",
    "instanceof",
    "discriminatedUnion",
    "intersection",
    "optional",
    "nullable",
    "coerce",
    "nativeEnum",
    "bigint",
    "nan",
  ],
  joi: [
    "object",
    "string",
    "number",
    "array",
    "boolean",
    "date",
    "alternatives",
    "any",
    "binary",
    "link",
    "symbol",
    "func",
  ],
  yup: [
    "object",
    "string",
    "number",
    "array",
    "boolean",
    "date",
    "mixed",
    "ref",
    "lazy",
  ],
  default: [
    "object",
    "string",
    "number",
    "array",
    "boolean",
    "date",
    "enum",
    "union",
    "tuple",
    "record",
    "map",
    "set",
    "literal",
    "any",
    "unknown",
    "alternatives",
    "binary",
    "link",
    "symbol",
    "func",
    "mixed",
    "ref",
    "lazy",
  ],
};

export function extractSchemaDefinitions(
  functionCallArgs: IFunctionCallArg[],
  _assignments: IAssignment[],
  imports: IImport[],
): ISchemaDefinition[] {
  const schemaDefs: ISchemaDefinition[] = [];

  const frameworks = detectValidationFrameworks(imports);
  if (frameworks.length === 0) return schemaDefs;

  const builderMethods = new Set<string>();
  for (const fw of frameworks) {
    const methods = SCHEMA_BUILDERS[fw.name] || SCHEMA_BUILDERS["default"];
    methods.forEach((m) => builderMethods.add(m));
  }

  for (const call of functionCallArgs) {
    const callee = call.callee_function || "";
    if (!callee) continue;

    const method = callee.split(".").pop() || "";
    if (!builderMethods.has(method)) continue;

    let matchedFramework: string | null = null;
    for (const fw of frameworks) {
      for (const name of fw.importedNames) {
        if (callee.startsWith(`${name}.`)) {
          matchedFramework = fw.name;
          break;
        }
      }
      if (matchedFramework) break;
    }

    if (matchedFramework) {
      schemaDefs.push({
        line: call.line,
        framework: matchedFramework,
        method: method,
        variable_name: null,
        is_validator: false,
        argument_expr: (call.argument_expr || "").substring(0, 2000),
      });
    }
  }

  return schemaDefs;
}

const SQL_METHODS = new Set([
  "execute",
  "query",
  "raw",
  "exec",
  "run",
  "executeSql",
  "executeQuery",
  "execSQL",
  "select",
  "insert",
  "update",
  "delete",
  "query_raw",
]);

function resolveSQLLiteral(argExpr: string): string | null {
  const trimmed = argExpr.trim();

  if (
    (trimmed.startsWith('"') && trimmed.endsWith('"')) ||
    (trimmed.startsWith("'") && trimmed.endsWith("'"))
  ) {
    return trimmed.slice(1, -1);
  }

  if (trimmed.startsWith("`") && trimmed.endsWith("`")) {
    if (trimmed.includes("${")) {
      return null;
    }
    let unescaped = trimmed.slice(1, -1);
    unescaped = unescaped.replace(/\\`/g, "`").replace(/\\\\/g, "\\");
    return unescaped;
  }

  return null;
}

export function extractSQLQueries(
  functionCallArgs: IFunctionCallArg[],
): ISQLQuery[] {
  const queries: ISQLQuery[] = [];

  for (const call of functionCallArgs) {
    const callee = call.callee_function || "";
    const methodName = callee.includes(".")
      ? callee.split(".").pop() || ""
      : callee;
    if (!SQL_METHODS.has(methodName)) continue;

    const argExpr = call.argument_expr || "";
    if (!argExpr) continue;

    const upperArg = argExpr.toUpperCase();
    const hasSQLKeyword = [
      "SELECT",
      "INSERT",
      "UPDATE",
      "DELETE",
      "CREATE",
      "DROP",
      "ALTER",
    ].some((kw) => upperArg.includes(kw));

    if (call.argument_index !== 0) {
      if (call.argument_index === 1 && hasSQLKeyword) {
      } else {
        continue;
      }
    }

    const queryText = resolveSQLLiteral(argExpr);

    if (queryText && hasSQLKeyword) {
      queries.push({
        line: call.line,
        query_text: queryText.substring(0, 1000),
        function_name: call.caller_function || null,
      });
    } else if (!queryText && argExpr.trim()) {
      const strongSQLMethods = [
        "query",
        "execute",
        "exec",
        "raw",
        "executeSql",
        "executeQuery",
        "query_raw",
      ];
      if (strongSQLMethods.includes(methodName)) {
        queries.push({
          line: call.line,
          query_text: `[DYNAMIC_SQL] ${argExpr.substring(0, 900)}`,
          function_name: call.caller_function || null,
        });
      }
    }
  }

  return queries;
}

interface ExtractCDKResult {
  cdk_constructs: ICDKConstruct[];
  cdk_construct_properties: ICDKConstructProperty[];
}

function extractConstructName(
  call: IFunctionCallArg,
  allCalls: IFunctionCallArg[],
): string | undefined {
  const args = allCalls.filter(
    (c) => c.line === call.line && c.callee_function === call.callee_function,
  );

  const idArg = args.find((a) => a.argument_index === 1);
  if (!idArg || !idArg.argument_expr) return undefined;

  const expr = idArg.argument_expr.trim();
  if (
    (expr.startsWith("'") && expr.endsWith("'")) ||
    (expr.startsWith('"') && expr.endsWith('"'))
  ) {
    return expr.slice(1, -1);
  }

  return expr;
}

function splitObjectPairs(content: string): string[] {
  const pairs: string[] = [];
  let current = "";
  let depth = 0;
  let inString = false;
  let stringChar: string | null = null;

  for (let i = 0; i < content.length; i++) {
    const char = content[i];
    const prevChar = i > 0 ? content[i - 1] : "";

    if ((char === '"' || char === "'" || char === "`") && prevChar !== "\\") {
      if (!inString) {
        inString = true;
        stringChar = char;
      } else if (char === stringChar) {
        inString = false;
        stringChar = null;
      }
    }

    if (!inString) {
      if (char === "{" || char === "[" || char === "(") {
        depth++;
      } else if (char === "}" || char === "]" || char === ")") {
        depth--;
      }
    }

    if (char === "," && depth === 0 && !inString) {
      pairs.push(current.trim());
      current = "";
    } else {
      current += char;
    }
  }

  if (current.trim()) {
    pairs.push(current.trim());
  }

  return pairs;
}

function extractConstructProperties(
  call: IFunctionCallArg,
  allCalls: IFunctionCallArg[],
): Array<{ name: string; value_expr: string; line: number }> {
  const properties: Array<{ name: string; value_expr: string; line: number }> =
    [];

  const propsArg = allCalls.find(
    (c) =>
      c.line === call.line &&
      c.callee_function === call.callee_function &&
      c.argument_index === 2,
  );

  if (!propsArg || !propsArg.argument_expr) return properties;

  const expr = propsArg.argument_expr.trim();
  const objMatch = expr.match(/\{([^}]+)\}/);
  if (!objMatch) return properties;

  const objContent = objMatch[1];
  const pairs = splitObjectPairs(objContent);

  for (const pair of pairs) {
    const colonIdx = pair.indexOf(":");
    if (colonIdx === -1) continue;

    const key = pair.substring(0, colonIdx).trim();
    const value = pair.substring(colonIdx + 1).trim();

    if (!key) continue;

    properties.push({
      name: key,
      value_expr: value,
      line: call.line,
    });
  }

  return properties;
}

export function extractCDKConstructs(
  functionCallArgs: IFunctionCallArg[],
  imports: IImport[],
  import_specifiers: IImportSpecifier[],
): ExtractCDKResult {
  const cdk_constructs: ICDKConstruct[] = [];
  const cdk_construct_properties: ICDKConstructProperty[] = [];

  const cdkImports = imports.filter((i) => {
    const module = i.module || "";
    return module && module.includes("aws-cdk-lib");
  });

  if (cdkImports.length === 0) {
    return { cdk_constructs: [], cdk_construct_properties: [] };
  }

  const specifiersByLine = new Map<number, IImportSpecifier[]>();
  for (const spec of import_specifiers || []) {
    if (!specifiersByLine.has(spec.import_line)) {
      specifiersByLine.set(spec.import_line, []);
    }
    specifiersByLine.get(spec.import_line)!.push(spec);
  }

  const cdkAliases: Record<string, string | null> = {};
  for (const imp of cdkImports) {
    const module = imp.module || "";
    const serviceName = module.includes("/")
      ? module.split("/").pop() || null
      : null;

    const specifiers = specifiersByLine.get(imp.line) || [];
    for (const spec of specifiers) {
      const name = spec.specifier_name;
      if (spec.is_namespace || spec.is_named || spec.is_default) {
        cdkAliases[name] = serviceName;
      }
    }
  }

  const processedConstructs = new Set<string>();

  for (const call of functionCallArgs) {
    const callee = call.callee_function || "";
    if (!callee.startsWith("new ")) continue;

    const constructKey = `${call.line}::${callee}`;
    if (processedConstructs.has(constructKey)) continue;
    processedConstructs.add(constructKey);

    const className = callee.replace(/^new\s+/, "");
    const parts = className.split(".");

    let matched = false;
    if (parts.length >= 2) {
      const moduleAlias = parts[0];
      if (moduleAlias in cdkAliases) {
        matched = true;
        const constructName = extractConstructName(call, functionCallArgs);
        const properties = extractConstructProperties(call, functionCallArgs);

        cdk_constructs.push({
          line: call.line,
          cdk_class: className,
          construct_name: constructName,
        });

        for (const prop of properties) {
          cdk_construct_properties.push({
            construct_line: call.line,
            construct_class: className,
            construct_name: constructName,
            property_name: prop.name,
            value_expr: prop.value_expr,
            property_line: prop.line,
          });
        }
      }
    } else if (parts.length === 1) {
      const constructClass = parts[0];
      if (constructClass in cdkAliases) {
        matched = true;
        const constructName = extractConstructName(call, functionCallArgs);
        const properties = extractConstructProperties(call, functionCallArgs);

        cdk_constructs.push({
          line: call.line,
          cdk_class: constructClass,
          construct_name: constructName,
        });

        for (const prop of properties) {
          cdk_construct_properties.push({
            construct_line: call.line,
            construct_class: constructClass,
            construct_name: constructName,
            property_name: prop.name,
            value_expr: prop.value_expr,
            property_line: prop.line,
          });
        }
      }
    }
  }

  return { cdk_constructs, cdk_construct_properties };
}

export function extractFrontendApiCalls(
  functionCallArgs: IFunctionCallArg[],
  imports: IImport[],
  import_specifiers: IImportSpecifier[] = [],
): IFrontendAPICall[] {
  const apiCalls: IFrontendAPICall[] = [];
  const debug = process.env.THEAUDITOR_DEBUG === "1";

  const aliasToModule = new Map<string, string>();
  const HTTP_LIBRARIES = new Set([
    "axios",
    "node-fetch",
    "got",
    "ky",
    "superagent",
    "request",
  ]);

  const lineToModule = new Map<number, string>();
  for (const imp of imports) {
    if (imp.module) {
      lineToModule.set(imp.line, imp.module);
    }
  }

  for (const spec of import_specifiers) {
    const modulePath = lineToModule.get(spec.import_line);
    if (modulePath) {
      const baseName =
        modulePath
          .split("/")
          .pop()
          ?.replace(/^@.*\//, "") || modulePath;
      if (HTTP_LIBRARIES.has(baseName) || baseName === "axios") {
        aliasToModule.set(spec.specifier_name, baseName);
        if (debug) {
          console.error(
            `[API_DEBUG] Alias mapping: ${spec.specifier_name} -> ${baseName}`,
          );
        }
      }
    }
  }

  function resolveCallee(callee: string): string {
    const parts = callee.split(".");
    if (parts.length >= 1) {
      const prefix = parts[0];
      const resolvedModule = aliasToModule.get(prefix);
      if (resolvedModule) {
        parts[0] = resolvedModule;
        return parts.join(".");
      }
    }
    return callee;
  }

  if (debug) {
    console.error(
      `[API_DEBUG] extractFrontendApiCalls called with ${functionCallArgs.length} function call args`,
    );
    const axiosCalls = functionCallArgs.filter(
      (c) => c.callee_function && c.callee_function.includes("axios"),
    );
    console.error(`[API_DEBUG] Found ${axiosCalls.length} axios-related calls`);
    axiosCalls
      .slice(0, 5)
      .forEach((c) =>
        console.error(
          `[API_DEBUG]   - ${c.callee_function} @ line ${c.line}, arg_idx=${c.argument_index}, expr=${c.argument_expr?.substring(0, 50)}`,
        ),
      );
  }

  function parseUrl(call: IFunctionCallArg): string | null {
    if (call.argument_index === 0 && call.argument_expr) {
      let url = call.argument_expr.trim();
      if (
        (url.startsWith("'") && url.endsWith("'")) ||
        (url.startsWith('"') && url.endsWith('"')) ||
        (url.startsWith("`") && url.endsWith("`"))
      ) {
        url = url.slice(1, -1);
      }
      if (url.length > 0) {
        return url.split("?")[0];
      }
    }
    return null;
  }

  function parseFetchOptions(call: IFunctionCallArg): {
    method: string;
    body_variable: string | null;
  } {
    const options = { method: "GET", body_variable: null as string | null };
    if (call.argument_index === 1 && call.argument_expr) {
      const expr = call.argument_expr;
      const methodMatch = expr.match(/method:\s*['"]([^'"]+)['"]/i);
      if (methodMatch) {
        options.method = methodMatch[1].toUpperCase();
      }
      const bodyMatch = expr.match(/body:\s*([^\s,{}]+)/i);
      if (bodyMatch) {
        let bodyVar = bodyMatch[1];
        if (bodyVar.startsWith("JSON.stringify(")) {
          bodyVar = bodyVar.substring(15, bodyVar.length - 1);
        }
        options.body_variable = bodyVar;
      }
    }
    return options;
  }

  const callsByLine: Record<
    number,
    {
      callee: string;
      caller: string;
      args: IFunctionCallArg[];
    }
  > = {};

  for (const call of functionCallArgs) {
    const callee = call.callee_function || "";
    if (!callee) continue;

    if (!callsByLine[call.line]) {
      callsByLine[call.line] = {
        callee: callee,
        caller: call.caller_function || "global",
        args: [],
      };
    }
    if (call.argument_index !== undefined && call.argument_index !== null) {
      callsByLine[call.line].args[call.argument_index] = call;
    }
  }

  for (const lineStr in callsByLine) {
    const line = parseInt(lineStr);
    const callData = callsByLine[line];
    const callee = resolveCallee(callData.callee);
    const args = callData.args;

    let url: string | null = null;
    let method: string | null = null;
    let body_variable: string | null = null;

    if (callee === "fetch" && args[0]) {
      url = parseUrl(args[0]);
      if (!url) {
        if (debug)
          console.error(
            `[API_DEBUG] Line ${line}: fetch rejected - parseUrl failed for: ${args[0]?.argument_expr}`,
          );
        continue;
      }
      const options = parseFetchOptions(args[1] || ({} as IFunctionCallArg));
      method = options.method;
      body_variable = options.body_variable;
    } else if ((callee === "axios.get" || callee === "axios") && args[0]) {
      url = parseUrl(args[0]);
      if (!url) {
        if (debug)
          console.error(
            `[API_DEBUG] Line ${line}: axios.get rejected - parseUrl failed for: ${args[0]?.argument_expr}`,
          );
        continue;
      }
      method = "GET";
    } else if (callee === "axios.post" && args[0]) {
      url = parseUrl(args[0]);
      if (!url) {
        if (debug)
          console.error(
            `[API_DEBUG] Line ${line}: axios.post rejected - parseUrl failed for: ${args[0]?.argument_expr}`,
          );
        continue;
      }
      method = "POST";
      if (args[1]) {
        body_variable = args[1].argument_expr || null;
      }
    } else if (
      (callee === "axios.put" || callee === "axios.patch") &&
      args[0]
    ) {
      url = parseUrl(args[0]);
      if (!url) {
        if (debug)
          console.error(
            `[API_DEBUG] Line ${line}: axios.put/patch rejected - parseUrl failed for: ${args[0]?.argument_expr}`,
          );
        continue;
      }
      method = callee === "axios.put" ? "PUT" : "PATCH";
      if (args[1]) {
        body_variable = args[1].argument_expr || null;
      }
    } else if (callee === "axios.delete" && args[0]) {
      url = parseUrl(args[0]);
      if (!url) {
        if (debug)
          console.error(
            `[API_DEBUG] Line ${line}: axios.delete rejected - parseUrl failed for: ${args[0]?.argument_expr}`,
          );
        continue;
      }
      method = "DELETE";
    } else if (callee.match(/\.(get|post|put|patch|delete)$/)) {
      const prefix = callee.substring(0, callee.lastIndexOf("."));
      const httpMethod = callee
        .substring(callee.lastIndexOf(".") + 1)
        .toUpperCase();

      const apiWrapperPrefixes = [
        "api",
        "apiService",
        "service",
        "http",
        "httpClient",
        "client",
        "axios",
        "instance",
        "this.instance",
        "this.api",
        "this.http",
        "request",
      ];

      const isLikelyApiWrapper = apiWrapperPrefixes.some(
        (p) =>
          prefix === p ||
          prefix.endsWith("." + p) ||
          prefix.includes("api") ||
          prefix.includes("service"),
      );

      if (isLikelyApiWrapper && args[0]) {
        url = parseUrl(args[0]);
        if (!url) {
          if (debug)
            console.error(
              `[API_DEBUG] Line ${line}: wrapper ${callee} rejected - parseUrl failed for: ${args[0]?.argument_expr}`,
            );
          continue;
        }
        method = httpMethod;
        if (["POST", "PUT", "PATCH"].includes(method) && args[1]) {
          body_variable = args[1].argument_expr || null;
        }
      } else if (debug) {
        console.error(
          `[API_DEBUG] Line ${line}: callee ${callee} prefix "${prefix}" not in wrapper list`,
        );
      }
    }

    if (url && method) {
      if (debug)
        console.error(
          `[API_DEBUG] Line ${line}: CAPTURED ${method} ${url} (client: ${callee})`,
        );
      apiCalls.push({
        line: line,
        method: method,
        url_literal: url,
        body_variable: body_variable,
        function_name: callData.caller,
        client_library: callee.split(".")[0] || "fetch",
      });
    }
  }

  if (debug) {
    console.error(
      `[API_DEBUG] extractFrontendApiCalls returning ${apiCalls.length} calls`,
    );
  }

  return apiCalls;
}

/**
 * JWT library methods that indicate signing (creating tokens)
 */
const JWT_SIGN_METHODS = new Set(["sign", "encode"]);

/**
 * JWT library methods that indicate verification/decoding
 */
const JWT_VERIFY_METHODS = new Set(["verify", "decode"]);

/**
 * Known JWT library module names
 */
const JWT_LIBRARIES = new Set([
  "jsonwebtoken",
  "jose",
  "jwt-simple",
  "njwt",
  "express-jwt",
  "passport-jwt",
  "koa-jwt",
]);

/**
 * Extract JWT patterns from function calls and imports.
 * Detects jwt.sign(), jwt.verify(), jwt.decode() and similar patterns.
 */
export function extractJWTPatterns(
  functionCallArgs: IFunctionCallArg[],
  imports: IImport[],
): IJWTPattern[] {
  const patterns: IJWTPattern[] = [];

  // Build a map of local aliases to JWT libraries
  const jwtAliases = new Set<string>();
  for (const imp of imports) {
    const module = imp.module || "";
    if (!module) continue;

    // Check if this is a JWT library import
    const baseName = module.split("/").pop() || module;
    if (JWT_LIBRARIES.has(baseName)) {
      // The default import or namespace would be used as jwt.sign(), etc.
      // We track common patterns like: import jwt from 'jsonwebtoken'
      jwtAliases.add("jwt");
      jwtAliases.add("jsonwebtoken");
      jwtAliases.add(baseName);
    }
  }

  // Also check for common jwt variable names even without explicit import tracking
  jwtAliases.add("jwt");
  jwtAliases.add("JWT");

  // Group calls by line to handle multi-argument calls
  const callsByLine: Record<
    number,
    {
      callee: string;
      caller: string;
      args: IFunctionCallArg[];
    }
  > = {};

  for (const call of functionCallArgs) {
    const callee = call.callee_function || "";
    if (!callee) continue;

    if (!callsByLine[call.line]) {
      callsByLine[call.line] = {
        callee: callee,
        caller: call.caller_function || "global",
        args: [],
      };
    }
    if (call.argument_index !== undefined && call.argument_index !== null) {
      callsByLine[call.line].args[call.argument_index] = call;
    }
  }

  for (const lineStr in callsByLine) {
    const line = parseInt(lineStr);
    const callData = callsByLine[line];
    const callee = callData.callee;
    const args = callData.args;

    // Check for jwt.sign, jwt.verify, jwt.decode patterns
    const parts = callee.split(".");
    if (parts.length < 2) continue;

    const receiver = parts.slice(0, -1).join(".");
    const method = parts[parts.length - 1];

    // Check if receiver is a known JWT alias
    const isJwtReceiver =
      jwtAliases.has(receiver) ||
      receiver.toLowerCase().includes("jwt") ||
      receiver.toLowerCase().includes("token");

    if (!isJwtReceiver) continue;

    let patternType: string | null = null;
    if (JWT_SIGN_METHODS.has(method)) {
      patternType = "jwt_sign";
    } else if (JWT_VERIFY_METHODS.has(method)) {
      patternType = method === "verify" ? "jwt_verify" : "jwt_decode";
    }

    if (!patternType) continue;

    // Extract secret source type from second argument (for sign/verify)
    let secretType = "unknown";
    let algorithm: string | null = null;

    if (patternType === "jwt_sign" || patternType === "jwt_verify") {
      // Second argument is typically the secret
      const secretArg = args[1];
      if (secretArg && secretArg.argument_expr) {
        const expr = secretArg.argument_expr.trim();

        if (
          (expr.startsWith("'") && expr.endsWith("'")) ||
          (expr.startsWith('"') && expr.endsWith('"')) ||
          (expr.startsWith("`") && expr.endsWith("`"))
        ) {
          secretType = "hardcoded";
        } else if (
          expr.includes("process.env") ||
          expr.includes("ENV") ||
          expr.includes("getenv")
        ) {
          secretType = "environment";
        } else if (
          expr.includes("config") ||
          expr.includes("settings") ||
          expr.includes("secrets")
        ) {
          secretType = "config";
        } else {
          secretType = "variable";
        }
      }

      // Third argument often contains options including algorithm
      const optionsArg = args[2];
      if (optionsArg && optionsArg.argument_expr) {
        const optExpr = optionsArg.argument_expr;
        // Look for algorithm in options object
        const algoMatch = optExpr.match(
          /algorithm:\s*['"]([^'"]+)['"]/i,
        );
        if (algoMatch) {
          algorithm = algoMatch[1];
        }
        // Also check for expiresIn pattern to confirm it's JWT options
        if (!algorithm && optExpr.includes("expiresIn")) {
          algorithm = "HS256"; // Default assumption
        }
      }
    }

    // For decode, typically doesn't need secret (unless complete: true)
    if (patternType === "jwt_decode") {
      secretType = "none";
    }

    const fullMatch = `${receiver}.${method}(...)`;

    patterns.push({
      line: line,
      type: patternType,
      full_match: fullMatch,
      secret_type: secretType,
      algorithm: algorithm,
    });
  }

  return patterns;
}
