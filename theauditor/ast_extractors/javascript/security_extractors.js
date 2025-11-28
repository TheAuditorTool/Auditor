function extractORMQueries(functionCallArgs) {
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

  const queries = [];

  for (const call of functionCallArgs) {
    const method = call.callee_function
      ? call.callee_function.split(".").pop()
      : "";
    if (!ORM_METHODS.has(method)) continue;

    const hasIncludes =
      call.argument_expr && call.argument_expr.includes("include:");
    const hasLimit =
      call.argument_expr &&
      (call.argument_expr.includes("limit:") ||
        call.argument_expr.includes("take:"));

    queries.push({
      line: call.line,
      query_type: call.callee_function,
      includes: hasIncludes ? "has_includes" : null,
      has_limit: hasLimit,
      has_transaction: false,
    });
  }

  return queries;
}

function extractAPIEndpoints(functionCallArgs) {
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
  const endpoints = [];
  const middlewareChains = [];

  const callsByLine = {};

  for (const call of functionCallArgs) {
    const callee = call.callee_function || "";
    if (!callee.includes(".")) continue;

    const parts = callee.split(".");
    const receiver = parts.slice(0, -1).join(".").toLowerCase();
    const method = parts[parts.length - 1];

    const ROUTER_PATTERNS = ["router", "app", "express", "server", "route"];
    const isRouter = ROUTER_PATTERNS.some((p) => receiver.includes(p));

    if (!isRouter || !HTTP_METHODS.has(method)) continue;

    if (!callsByLine[call.line]) {
      callsByLine[call.line] = {
        method: method,
        callee: callee,
        caller_function: call.caller_function,
        calls: [],
      };
    }
    callsByLine[call.line].calls.push(call);
  }

  for (const [line, data] of Object.entries(callsByLine)) {
    const { method, callee, caller_function, calls } = data;

    calls.sort((a, b) => a.argument_index - b.argument_index);

    const routeArg = calls.find((c) => c.argument_index === 0);
    if (!routeArg) continue;

    const route = routeArg.argument_expr;
    if (!route || typeof route !== "string") continue;

    let cleanRoute = route.replace(/['"]/g, "").trim();

    endpoints.push({
      line: parseInt(line),
      method: method.toUpperCase(),
      route: cleanRoute,
      handler_function: caller_function,
      requires_auth: false,
    });

    for (let i = 1; i < calls.length; i++) {
      const call = calls[i];

      const isController = i === calls.length - 1;

      let handlerFunction = null;
      const expr = call.argument_expr || "";
      if (expr && !expr.includes("=>") && !expr.includes("function")) {
        handlerFunction = expr;
      }

      middlewareChains.push({
        route_line: parseInt(line),
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

function extractValidationFrameworkUsage(
  functionCallArgs,
  assignments,
  imports,
) {
  const validationCalls = [];

  const debugLog = (msg, data) => {
    if (process.env.THEAUDITOR_VALIDATION_DEBUG === "1") {
      console.error(`[VALIDATION-L2-EXTRACT] ${msg}`);
      if (data) {
        console.error(`[VALIDATION-L2-EXTRACT]   ${JSON.stringify(data)}`);
      }
    }
  };

  debugLog("Starting validation framework extraction", {
    functionCallArgs_count: functionCallArgs.length,
    assignments_count: assignments.length,
    imports_count: imports.length,
  });

  const frameworks = detectValidationFrameworks(imports, debugLog);
  debugLog(
    `Detected ${frameworks.length} validation frameworks in imports`,
    frameworks,
  );

  if (frameworks.length === 0) {
    debugLog("No validation frameworks found, skipping extraction");
    return validationCalls;
  }

  const schemaVars = findSchemaVariables(assignments, frameworks, debugLog);
  debugLog(
    `Found ${Object.keys(schemaVars).length} schema variables`,
    schemaVars,
  );

  for (const call of functionCallArgs) {
    const callee = call.callee_function || "";
    if (!callee) continue;

    const isValidation = isValidationCall(callee, frameworks, schemaVars);
    if (isValidation) {
      const validation = {
        line: call.line,
        framework: getFrameworkName(callee, frameworks, schemaVars),
        function_name: callee,
        method: getMethodName(callee),
        variable_name: getVariableName(callee),
        is_validator: isValidatorMethod(callee),
        argument_expr: (call.argument_expr || "").substring(0, 200),
      };

      debugLog(`Extracted validation call at line ${call.line}`, validation);
      validationCalls.push(validation);
    }
  }

  debugLog(`Total validation calls extracted: ${validationCalls.length}`);
  return validationCalls;
}

function extractSchemaDefinitions(functionCallArgs, assignments, imports) {
  const schemaDefs = [];

  const debugLog = (msg, data) => {
    if (process.env.THEAUDITOR_VALIDATION_DEBUG === "1") {
      console.error(`[SCHEMA-DEF-EXTRACT] ${msg}`);
      if (data) {
        console.error(`[SCHEMA-DEF-EXTRACT]   ${JSON.stringify(data)}`);
      }
    }
  };

  debugLog("Starting schema definition extraction", {
    functionCallArgs_count: functionCallArgs.length,
    imports_count: imports.length,
  });

  const frameworks = detectValidationFrameworks(imports, debugLog);
  debugLog(
    `Detected ${frameworks.length} validation frameworks in imports`,
    frameworks,
  );

  if (frameworks.length === 0) {
    debugLog("No validation frameworks found, skipping extraction");
    return schemaDefs;
  }

  const SCHEMA_BUILDERS = {
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

  const builderMethods = new Set();
  for (const fw of frameworks) {
    const methods = SCHEMA_BUILDERS[fw.name] || SCHEMA_BUILDERS["default"];
    methods.forEach((m) => builderMethods.add(m));
  }

  debugLog(
    `Watching for ${builderMethods.size} schema builder methods`,
    Array.from(builderMethods),
  );

  for (const call of functionCallArgs) {
    const callee = call.callee_function || "";
    if (!callee) continue;

    const method = callee.split(".").pop();

    if (!builderMethods.has(method)) continue;

    let matchedFramework = null;
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
      const schemaDef = {
        line: call.line,
        framework: matchedFramework,
        method: method,
        variable_name: null,
        is_validator: false,
        argument_expr: (call.argument_expr || "").substring(0, 200),
      };

      debugLog(`Extracted schema definition at line ${call.line}`, schemaDef);
      schemaDefs.push(schemaDef);
    }
  }

  debugLog(`Total schema definitions extracted: ${schemaDefs.length}`);
  return schemaDefs;
}

function detectValidationFrameworks(imports, debugLog) {
  const VALIDATION_FRAMEWORKS = {
    zod: ["z", "zod", "ZodSchema"],
    joi: ["Joi", "joi"],
    yup: ["yup", "Yup"],
    ajv: ["Ajv", "ajv"],
    "class-validator": ["validate", "validateSync", "validateOrReject"],
    "express-validator": ["validationResult", "matchedData", "checkSchema"],
  };

  const detected = [];

  for (const imp of imports) {
    const moduleName = imp.module || "";
    if (!moduleName) continue;

    for (const [framework, names] of Object.entries(VALIDATION_FRAMEWORKS)) {
      if (moduleName.includes(framework)) {
        const fw = { name: framework, importedNames: names };
        detected.push(fw);
        debugLog(`Detected framework import: ${framework}`, {
          module: moduleName,
          imported_names: names,
          import_obj: imp,
        });
        break;
      }
    }
  }

  return detected;
}

function findSchemaVariables(assignments, frameworks, debugLog) {
  const schemas = {};

  const ZOD_BUILDERS = [
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
  ];

  const JOI_BUILDERS = [
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
  ];

  const YUP_BUILDERS = [
    "object",
    "string",
    "number",
    "array",
    "boolean",
    "date",
    "mixed",
    "ref",
    "lazy",
  ];

  for (const assign of assignments) {
    const target = assign.target_var;
    const source = assign.source_expr || "";

    for (const fw of frameworks) {
      let builders = ZOD_BUILDERS;
      if (fw.name === "joi") {
        builders = JOI_BUILDERS;
      } else if (fw.name === "yup") {
        builders = YUP_BUILDERS;
      }

      for (const name of fw.importedNames) {
        for (const builder of builders) {
          if (source.includes(`${name}.${builder}(`)) {
            schemas[target] = { framework: fw.name };
            debugLog(`Found schema variable: ${target}`, {
              target_var: target,
              framework: fw.name,
              builder: builder,
              source_expr: source.substring(0, 100),
            });
            break;
          }
        }

        if (source.includes(`${name}.`)) {
          schemas[target] = { framework: fw.name };
          debugLog(`Found chained schema variable: ${target}`, {
            target_var: target,
            framework: fw.name,
            source_expr: source.substring(0, 100),
          });
          break;
        }
      }
    }
  }

  return schemas;
}

function isValidationCall(callee, frameworks, schemaVars) {
  for (const fw of frameworks) {
    for (const name of fw.importedNames) {
      if (callee.startsWith(`${name}.`) && isValidatorMethod(callee)) {
        return true;
      }
    }
  }

  if (
    callee.includes(".") &&
    frameworks.length > 0 &&
    isValidatorMethod(callee)
  ) {
    const varName = callee.split(".")[0];

    if (varName in schemaVars) {
      return true;
    }

    if (looksLikeSchemaVariable(varName)) {
      return true;
    }
  }

  return false;
}

function looksLikeSchemaVariable(varName) {
  const lower = varName.toLowerCase();

  if (lower.endsWith("schema") || lower.endsWith("validator")) {
    return true;
  }

  if (lower.includes("schema") || lower.includes("validator")) {
    return true;
  }

  if (lower.startsWith("validate")) {
    return true;
  }

  if (["schema", "validator", "validation"].includes(lower)) {
    return true;
  }

  return false;
}

function isValidatorMethod(callee) {
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
  const method = callee.split(".").pop();
  return VALIDATOR_METHODS.includes(method);
}

function getFrameworkName(callee, frameworks, schemaVars) {
  if (callee.includes(".")) {
    const varName = callee.split(".")[0];
    if (varName in schemaVars) {
      return schemaVars[varName].framework;
    }
  }

  for (const fw of frameworks) {
    for (const name of fw.importedNames) {
      if (callee.startsWith(`${name}.`)) {
        return fw.name;
      }
    }
  }

  if (frameworks.length === 1) {
    return frameworks[0].name;
  }

  return "unknown";
}

function getMethodName(callee) {
  return callee.split(".").pop();
}

function getVariableName(callee) {
  if (!callee.includes(".")) return null;
  const parts = callee.split(".");
  return parts.length > 1 ? parts[0] : null;
}

function extractSQLQueries(functionCallArgs) {
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

  const queries = [];

  for (const call of functionCallArgs) {
    const callee = call.callee_function || "";

    const methodName = callee.includes(".") ? callee.split(".").pop() : callee;
    if (!SQL_METHODS.has(methodName)) continue;

    if (call.argument_index !== 0) continue;

    const argExpr = call.argument_expr || "";
    if (!argExpr) continue;

    const upperArg = argExpr.toUpperCase();
    if (
      !["SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER"].some(
        (kw) => upperArg.includes(kw),
      )
    ) {
      continue;
    }

    const queryText = resolveSQLLiteral(argExpr);
    if (!queryText) continue;

    queries.push({
      line: call.line,
      query_text: queryText.substring(0, 1000),
    });
  }

  return queries;
}

function resolveSQLLiteral(argExpr) {
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

function extractCDKConstructs(functionCallArgs, imports, import_specifiers) {
  const cdk_constructs = [];
  const cdk_construct_properties = [];

  const debugLog = (msg, data) => {
    if (process.env.THEAUDITOR_CDK_DEBUG === "1") {
      console.error(`[CDK-EXTRACT] ${msg}`);
      if (data) {
        console.error(`[CDK-EXTRACT]   ${JSON.stringify(data)}`);
      }
    }
  };

  debugLog("Starting CDK construct extraction", {
    functionCallArgs_count: functionCallArgs.length,
    imports_count: imports.length,
  });

  const cdkImports = imports.filter((i) => {
    const module = i.module || "";
    return module && module.includes("aws-cdk-lib");
  });

  debugLog(`Found ${cdkImports.length} CDK imports`, cdkImports);

  if (cdkImports.length === 0) {
    debugLog("No CDK imports found, skipping extraction (DETERMINISTIC)");
    return { cdk_constructs: [], cdk_construct_properties: [] };
  }

  const specifiersByLine = new Map();
  for (const spec of import_specifiers || []) {
    if (!specifiersByLine.has(spec.import_line)) {
      specifiersByLine.set(spec.import_line, []);
    }
    specifiersByLine.get(spec.import_line).push(spec);
  }

  const cdkAliases = {};
  for (const imp of cdkImports) {
    const module = imp.module || "";

    const serviceName = module.includes("/") ? module.split("/").pop() : null;

    const specifiers = specifiersByLine.get(imp.line) || [];
    for (const spec of specifiers) {
      const name = spec.specifier_name;

      if (spec.is_namespace) {
        cdkAliases[name] = serviceName;
        debugLog(`Mapped namespace import: ${name} → ${serviceName}`);
      } else if (spec.is_named) {
        cdkAliases[name] = serviceName;
        debugLog(`Mapped named import: ${name} → ${serviceName}`);
      } else if (spec.is_default) {
        cdkAliases[name] = serviceName;
        debugLog(`Mapped default import: ${name} → ${serviceName}`);
      }
    }
  }

  debugLog("Built CDK alias map", cdkAliases);

  const processedConstructs = new Set();

  for (const call of functionCallArgs) {
    const callee = call.callee_function || "";

    if (!callee.startsWith("new ")) {
      continue;
    }

    const constructKey = `${call.line}::${callee}`;
    if (processedConstructs.has(constructKey)) {
      continue;
    }
    processedConstructs.add(constructKey);

    const className = callee.replace(/^new\s+/, "");

    debugLog(`Analyzing new expression: ${className}`, { line: call.line });

    const parts = className.split(".");
    if (parts.length >= 2) {
      const moduleAlias = parts[0];
      const constructClass = parts.slice(1).join(".");

      if (moduleAlias in cdkAliases) {
        debugLog(`Matched CDK construct: ${className}`, {
          module_alias: moduleAlias,
          construct_class: constructClass,
          service: cdkAliases[moduleAlias],
        });

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
            property_name: prop.name,
            value_expr: prop.value_expr,
            property_line: prop.line,
          });
        }

        debugLog(`Extracted CDK construct at line ${call.line}`, {
          cdk_class: className,
          construct_name: constructName,
          properties_count: properties.length,
        });
      }
    } else if (parts.length === 1) {
      const constructClass = parts[0];
      if (constructClass in cdkAliases) {
        debugLog(`Matched direct CDK import: ${constructClass}`);

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
            property_name: prop.name,
            value_expr: prop.value_expr,
            property_line: prop.line,
          });
        }

        debugLog(`Extracted CDK construct at line ${call.line}`, {
          cdk_class: constructClass,
          construct_name: constructName,
          properties_count: properties.length,
        });
      }
    }
  }

  debugLog(`Total CDK constructs extracted: ${cdk_constructs.length}`);
  return { cdk_constructs, cdk_construct_properties };
}

function extractConstructName(call, allCalls) {
  const args = allCalls.filter(
    (c) => c.line === call.line && c.callee_function === call.callee_function,
  );

  const idArg = args.find((a) => a.argument_index === 1);
  if (!idArg || !idArg.argument_expr) {
    return null;
  }

  const expr = idArg.argument_expr.trim();

  if (
    (expr.startsWith("'") && expr.endsWith("'")) ||
    (expr.startsWith('"') && expr.endsWith('"'))
  ) {
    return expr.slice(1, -1);
  }

  return expr;
}

function extractConstructProperties(call, allCalls) {
  const properties = [];

  const propsArg = allCalls.find(
    (c) =>
      c.line === call.line &&
      c.callee_function === call.callee_function &&
      c.argument_index === 2,
  );

  if (!propsArg || !propsArg.argument_expr) {
    return properties;
  }

  const expr = propsArg.argument_expr.trim();

  const objMatch = expr.match(/\{([^}]+)\}/);
  if (!objMatch) {
    return properties;
  }

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

function splitObjectPairs(content) {
  const pairs = [];
  let current = "";
  let depth = 0;
  let inString = false;
  let stringChar = null;

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

function extractFrontendApiCalls(functionCallArgs, imports) {
  const apiCalls = [];

  const debugLog = (msg, data) => {
    if (process.env.THEAUDITOR_DEBUG === "1") {
      console.error(`[FE-API-EXTRACT] ${msg}`);
      if (data) console.error(`[FE-API-EXTRACT]   ${JSON.stringify(data)}`);
    }
  };

  const hasAxios = imports.some((i) => i.module === "axios");
  const hasFetch = true;

  if (!hasAxios && !hasFetch) {
    return apiCalls;
  }

  debugLog("Starting frontend API call extraction", { hasAxios });

  const parseUrl = (call) => {
    if (call.argument_index === 0 && call.argument_expr) {
      const url = call.argument_expr.trim().replace(/['"`]/g, "");
      if (url.startsWith("/")) {
        return url.split("?")[0];
      }
    }
    return null;
  };

  const parseFetchOptions = (call) => {
    const options = { method: "GET", body_variable: null };
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
  };

  const callsByLine = {};
  for (const call of functionCallArgs) {
    const callee = call.callee_function || "";
    if (!callee) continue;

    if (!callsByLine[call.line]) {
      callsByLine[call.line] = {
        callee: callee,
        caller: call.caller_function,
        args: [],
      };
    }
    callsByLine[call.line].args[call.argument_index] = call;
  }

  for (const line in callsByLine) {
    const callData = callsByLine[line];
    const callee = callData.callee;
    const args = callData.args;

    let url = null;
    let method = null;
    let body_variable = null;

    if (callee === "fetch" && args[0]) {
      url = parseUrl(args[0]);
      if (!url) continue;

      const options = parseFetchOptions(args[1] || {});
      method = options.method;
      body_variable = options.body_variable;
    } else if ((callee === "axios.get" || callee === "axios") && args[0]) {
      url = parseUrl(args[0]);
      if (!url) continue;
      method = "GET";
    } else if (callee === "axios.post" && args[0] && args[1]) {
      url = parseUrl(args[0]);
      if (!url) continue;
      method = "POST";
      body_variable = args[1].argument_expr;
    } else if (
      (callee === "axios.put" || callee === "axios.patch") &&
      args[0] &&
      args[1]
    ) {
      url = parseUrl(args[0]);
      if (!url) continue;
      method = callee === "axios.put" ? "PUT" : "PATCH";
      body_variable = args[1].argument_expr;
    } else if (callee === "axios.delete" && args[0]) {
      url = parseUrl(args[0]);
      if (!url) continue;
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
        if (!url) continue;

        method = httpMethod;

        if (["POST", "PUT", "PATCH"].includes(method) && args[1]) {
          body_variable = args[1].argument_expr;
        }
      }
    }

    if (url && method) {
      apiCalls.push({
        file: args[0].file,
        line: parseInt(line),
        method: method,
        url_literal: url,
        body_variable: body_variable,
        function_name: callData.caller,
      });
      debugLog(`Extracted FE API Call at line ${line}`, {
        url,
        method,
        body_variable,
      });
    }
  }

  return apiCalls;
}
