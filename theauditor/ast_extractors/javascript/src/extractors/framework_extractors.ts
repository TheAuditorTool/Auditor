import type {
  Function as IFunction,
  Class as IClass,
  FunctionReturn as IFunctionReturn,
  FunctionCallArg as IFunctionCallArg,
  Import as IImport,
  FuncParam as IFuncParam,
  FuncDecorator as IFuncDecorator,
  FuncDecoratorArg as IFuncDecoratorArg,
  FuncParamDecorator as IFuncParamDecorator,
  ClassDecorator as IClassDecorator,
  ClassDecoratorArg as IClassDecoratorArg,
  ReactComponent as IReactComponent,
  ReactComponentHook as IReactComponentHook,
  ReactHook as IReactHook,
  ReactHookDependency as IReactHookDependency,
  VueComponent as IVueComponent,
  VueComponentProp as IVueComponentProp,
  VueComponentEmit as IVueComponentEmit,
  VueComponentSetupReturn as IVueComponentSetupReturn,
  VueHook as IVueHook,
  VueProvideInject as IVueProvideInject,
  VueDirective as IVueDirective,
  GraphQLResolver as IGraphQLResolver,
  GraphQLResolverParam as IGraphQLResolverParam,
} from "../schema.js";

interface ExtractReactComponentsResult {
  react_components: IReactComponent[];
  react_component_hooks: IReactComponentHook[];
}

export function extractReactComponents(
  functions: IFunction[],
  classes: IClass[],
  returns: IFunctionReturn[],
  functionCallArgs: IFunctionCallArg[],
  filePath: string,
  _imports: IImport[],
): ExtractReactComponentsResult {
  const react_components: IReactComponent[] = [];
  const react_component_hooks: IReactComponentHook[] = [];

  const isFrontendPath =
    filePath &&
    (filePath.includes("frontend/") ||
      filePath.includes("frontend\\") ||
      filePath.includes("client/") ||
      filePath.includes("client\\") ||
      filePath.includes("/components/") ||
      filePath.includes("\\components\\") ||
      filePath.includes("/pages/") ||
      filePath.includes("\\pages\\") ||
      filePath.includes("/ui/") ||
      filePath.includes("\\ui\\") ||
      filePath.endsWith(".tsx") ||
      filePath.endsWith(".jsx"));

  if (!isFrontendPath) {
    return { react_components, react_component_hooks };
  }

  for (const func of functions) {
    const name = func.name || "";
    if (!name || name[0] !== name[0].toUpperCase()) continue;

    const funcReturns = returns.filter((r) => r.function_name === name);
    const hasJsx = funcReturns.some((r) => r.has_jsx || r.returns_component);

    const seenHooks = new Set<string>();
    for (const call of functionCallArgs) {
      if (
        call.caller_function === name &&
        call.callee_function &&
        call.callee_function.startsWith("use")
      ) {
        const hookName = call.callee_function;
        if (!seenHooks.has(hookName)) {
          seenHooks.add(hookName);
          react_component_hooks.push({
            file: filePath,
            component_name: name,
            hook_name: hookName,
            hook_line: call.line,
          });
        }
      }
    }

    react_components.push({
      name: name,
      type: "function",
      start_line: func.line,
      end_line: func.line,
      has_jsx: hasJsx,
      props_type: null,
    });
  }

  for (const cls of classes) {
    const name = cls.name || "";
    if (!name || name[0] !== name[0].toUpperCase()) continue;

    const extendsReact =
      cls.extends_type &&
      (cls.extends_type.includes("Component") ||
        cls.extends_type.includes("React"));

    if (extendsReact) {
      react_components.push({
        name: name,
        type: "class",
        start_line: cls.line,
        end_line: cls.line,
        has_jsx: true,
        props_type: null,
      });
    }
  }

  return { react_components, react_component_hooks };
}

const REACT_HOOKS = new Set([
  "useState",
  "useEffect",
  "useCallback",
  "useMemo",
  "useRef",
  "useContext",
  "useReducer",
  "useLayoutEffect",
  "useImperativeHandle",
  "useDebugValue",
  "useDeferredValue",
  "useTransition",
  "useId",
]);

const HOOKS_WITH_DEPS = new Set([
  "useEffect",
  "useCallback",
  "useMemo",
  "useLayoutEffect",
  "useImperativeHandle",
]);

function parseDependencyArray(expr: string): string[] {
  if (!expr || typeof expr !== "string") return [];
  const trimmed = expr.trim();

  if (trimmed.startsWith("[") && trimmed.endsWith("]")) {
    const inner = trimmed.slice(1, -1).trim();
    if (!inner) return [];

    const deps: string[] = [];
    let depth = 0;
    let current = "";

    for (const char of inner) {
      if (char === "[" || char === "(" || char === "{") {
        depth++;
        current += char;
      } else if (char === "]" || char === ")" || char === "}") {
        depth--;
        current += char;
      } else if (char === "," && depth === 0) {
        const dep = current.trim();
        if (dep && isValidDependencyName(dep)) {
          deps.push(extractBaseName(dep));
        }
        current = "";
      } else {
        current += char;
      }
    }

    const lastDep = current.trim();
    if (lastDep && isValidDependencyName(lastDep)) {
      deps.push(extractBaseName(lastDep));
    }

    return deps;
  }

  return [];
}

function isValidDependencyName(name: string): boolean {
  if (!name) return false;
  return /^[a-zA-Z_$][a-zA-Z0-9_$]*(\??\.[\w$]+)*$/.test(name);
}

function extractBaseName(expr: string): string {
  if (expr.includes("(")) {
    return expr.split("(")[0].trim();
  }
  return expr;
}

interface ExtractReactHooksResult {
  react_hooks: IReactHook[];
  react_hook_dependencies: IReactHookDependency[];
}

export function extractReactHooks(
  functionCallArgs: IFunctionCallArg[],
  _scopeMap: Map<number, string>,
  filePath: string,
): ExtractReactHooksResult {
  const react_hooks: IReactHook[] = [];
  const react_hook_dependencies: IReactHookDependency[] = [];

  for (const call of functionCallArgs) {
    const hookName = call.callee_function || "";
    if (!hookName || !hookName.startsWith("use")) continue;

    if (hookName.includes(".")) {
      const parts = hookName.split(".");
      const prefix = parts[0];
      if (
        prefix !== "React" &&
        prefix !== "React_1" &&
        !prefix.endsWith("React")
      ) {
        continue;
      }
    }

    const actualHookName = hookName.includes(".")
      ? hookName.split(".").pop() || hookName
      : hookName;

    const isReactHook = REACT_HOOKS.has(actualHookName);
    const isCustomHook =
      !isReactHook &&
      actualHookName.startsWith("use") &&
      actualHookName.length > 3;

    if (isReactHook || isCustomHook) {
      const hookLine = call.line;
      const componentName = call.caller_function || "global";

      react_hooks.push({
        line: hookLine,
        hook_name: actualHookName,
        component_name: componentName,
        is_custom: isCustomHook,
        argument_count:
          call.argument_index != null ? call.argument_index + 1 : 0,
      });

      if (HOOKS_WITH_DEPS.has(actualHookName) && call.argument_expr) {
        const deps = parseDependencyArray(call.argument_expr);
        for (let i = 0; i < deps.length; i++) {
          react_hook_dependencies.push({
            file: filePath,
            hook_line: hookLine,
            component_name: componentName,
            dependency_name: deps[i],
            dependency_index: i,
          });
        }
      }
    }
  }

  return { react_hooks, react_hook_dependencies };
}

const VUE_LIFECYCLE_HOOKS = new Set([
  "onMounted",
  "onBeforeMount",
  "onBeforeUpdate",
  "onUpdated",
  "onBeforeUnmount",
  "onUnmounted",
  "onActivated",
  "onDeactivated",
  "onErrorCaptured",
  "onRenderTracked",
  "onRenderTriggered",
  "onServerPrefetch",
]);

const VUE_REACTIVITY_APIS = new Set([
  "watch",
  "watchEffect",
  "watchPostEffect",
  "watchSyncEffect",
  "ref",
  "reactive",
  "computed",
]);

function truncateVueString(
  value: string | null | undefined,
  maxLength = 1000,
): string | null {
  if (!value || typeof value !== "string") return null;
  return value.length > maxLength ? value.slice(0, maxLength) + "..." : value;
}

function getVueBaseName(name: string): string {
  if (!name || typeof name !== "string") return "";
  const parts = name.split(".");
  return parts[parts.length - 1] || "";
}

function inferVueComponentName(filePath: string): string {
  if (!filePath) return "AnonymousVueComponent";
  const segments = filePath.split(/[/\\]/);
  const candidate = segments.pop() || "Component";
  const base = candidate.replace(/\.vue$/i, "") || "Component";
  return base.charAt(0).toUpperCase() + base.slice(1);
}

function groupFunctionCallArgs(
  functionCallArgs: IFunctionCallArg[],
): Map<string, IFunctionCallArg[]> {
  const grouped = new Map<string, IFunctionCallArg[]>();
  if (!Array.isArray(functionCallArgs)) return grouped;
  for (const call of functionCallArgs) {
    const callee = call.callee_function || "";
    if (!callee) continue;
    const key = `${call.line || 0}:${callee}`;
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key)!.push(call);
  }
  return grouped;
}

function findFirstVueMacroCall(
  functionCallArgs: IFunctionCallArg[],
  macroName: string,
): string | null {
  if (!Array.isArray(functionCallArgs)) return null;
  for (const call of functionCallArgs) {
    const baseName = getVueBaseName(call.callee_function || "");
    if (
      baseName === macroName &&
      (call.argument_index === 0 || call.argument_index === null)
    ) {
      if (call.argument_expr && call.argument_expr.trim()) {
        return truncateVueString(call.argument_expr.trim());
      }
    }
  }
  return null;
}

function parseVuePropsDefinition(
  propsString: string | null,
  componentName: string,
): IVueComponentProp[] {
  if (!propsString || typeof propsString !== "string") return [];
  const props: IVueComponentProp[] = [];
  const trimmed = propsString.trim();

  if (trimmed.startsWith("[")) {
    const arrayMatch = trimmed.match(/\[\s*([^\]]*)\s*\]/);
    if (arrayMatch && arrayMatch[1]) {
      const items = arrayMatch[1]
        .split(",")
        .map((s) => s.trim().replace(/['"]/g, ""));
      for (const item of items) {
        if (item) {
          props.push({
            component_name: componentName,
            prop_name: item,
            prop_type: null,
            is_required: 0,
            default_value: null,
          });
        }
      }
    }
    return props;
  }

  if (trimmed.startsWith("{")) {
    const propPattern = /(\w+)\s*:\s*({[^{}]*(?:{[^{}]*}[^{}]*)*}|[^,}]+)/g;
    let match;
    while ((match = propPattern.exec(trimmed)) !== null) {
      const propName = match[1];
      const propValue = match[2].trim();
      let propType: string | null = null;
      let isRequired = 0;
      let defaultValue: string | null = null;

      if (propValue.startsWith("{")) {
        const typeMatch = propValue.match(/type\s*:\s*(\w+)/);
        if (typeMatch) propType = typeMatch[1];
        const reqMatch = propValue.match(/required\s*:\s*(true|false)/);
        if (reqMatch && reqMatch[1] === "true") isRequired = 1;
        const defMatch = propValue.match(/default\s*:\s*([^,}]+)/);
        if (defMatch) defaultValue = defMatch[1].trim();
      } else {
        propType = propValue;
      }

      props.push({
        component_name: componentName,
        prop_name: propName,
        prop_type: propType,
        is_required: isRequired,
        default_value: defaultValue,
      });
    }
  }
  return props;
}

function parseVueEmitsDefinition(
  emitsString: string | null,
  componentName: string,
): IVueComponentEmit[] {
  if (!emitsString || typeof emitsString !== "string") return [];
  const emits: IVueComponentEmit[] = [];
  const trimmed = emitsString.trim();

  if (trimmed.startsWith("[")) {
    const arrayMatch = trimmed.match(/\[\s*([^\]]*)\s*\]/);
    if (arrayMatch && arrayMatch[1]) {
      const items = arrayMatch[1]
        .split(",")
        .map((s) => s.trim().replace(/['"]/g, ""));
      for (const item of items) {
        if (item) {
          emits.push({
            component_name: componentName,
            emit_name: item,
            payload_type: null,
          });
        }
      }
    }
    return emits;
  }

  if (trimmed.startsWith("{")) {
    const emitPattern = /(\w+)\s*:/g;
    let match;
    while ((match = emitPattern.exec(trimmed)) !== null) {
      const emitName = match[1];
      const afterColon = trimmed.slice(match.index + match[0].length);
      let payloadType: string | null = null;
      const funcMatch = afterColon.match(/^\s*\(\s*(\w+)\s*:\s*(\w+)/);
      if (funcMatch) payloadType = funcMatch[2];
      emits.push({
        component_name: componentName,
        emit_name: emitName,
        payload_type: payloadType,
      });
    }
  }
  return emits;
}

function parseSetupReturn(
  returnExpr: string | null,
  componentName: string,
): IVueComponentSetupReturn[] {
  if (!returnExpr || typeof returnExpr !== "string") return [];
  const returns: IVueComponentSetupReturn[] = [];
  const trimmed = returnExpr.trim();

  if (trimmed.startsWith("{")) {
    const inner = trimmed.slice(1, -1).trim();
    if (!inner) return returns;
    const parts = inner.split(",");
    for (const part of parts) {
      const cleaned = part.trim();
      if (!cleaned) continue;
      const colonIndex = cleaned.indexOf(":");
      let returnName: string;
      if (colonIndex > 0) {
        returnName = cleaned.slice(0, colonIndex).trim();
      } else {
        returnName = cleaned.split(/[^a-zA-Z0-9_$]/)[0];
      }
      if (returnName && /^[a-zA-Z_$][a-zA-Z0-9_$]*$/.test(returnName)) {
        returns.push({
          component_name: componentName,
          return_name: returnName,
          return_type: null,
        });
      }
    }
  }
  return returns;
}

interface VueMeta {
  descriptor?: {
    scriptSetup?: { loc?: { start: { line: number }; end: { line: number } } };
    script?: { loc?: { start: { line: number }; end: { line: number } } };
    template?: boolean;
  };
  hasStyle?: boolean;
}

interface ExtractVueComponentsResult {
  vue_components: IVueComponent[];
  vue_component_props: IVueComponentProp[];
  vue_component_emits: IVueComponentEmit[];
  vue_component_setup_returns: IVueComponentSetupReturn[];
  primaryName: string;
}

export function extractVueComponents(
  vueMeta: VueMeta | null,
  filePath: string,
  functionCallArgs: IFunctionCallArg[],
  returns: IFunctionReturn[],
): ExtractVueComponentsResult {
  if (!vueMeta || !vueMeta.descriptor) {
    const fallbackName = inferVueComponentName(filePath);
    return {
      vue_components: [],
      vue_component_props: [],
      vue_component_emits: [],
      vue_component_setup_returns: [],
      primaryName: fallbackName,
    };
  }

  const componentName = inferVueComponentName(filePath);
  const scriptBlock =
    vueMeta.descriptor.scriptSetup || vueMeta.descriptor.script;
  const startLine = scriptBlock?.loc?.start.line ?? 1;
  const endLine = scriptBlock?.loc?.end.line ?? startLine;

  const propsDefinition = findFirstVueMacroCall(
    functionCallArgs,
    "defineProps",
  );
  const emitsDefinition = findFirstVueMacroCall(
    functionCallArgs,
    "defineEmits",
  );

  const usesCompositionApi =
    Boolean(vueMeta.descriptor.scriptSetup) ||
    (Array.isArray(functionCallArgs) &&
      functionCallArgs.some(
        (call) =>
          getVueBaseName(call.callee_function || "") === "defineComponent",
      ));

  let componentType = "options-api";
  if (vueMeta.descriptor.scriptSetup) {
    componentType = "script-setup";
  } else if (usesCompositionApi) {
    componentType = "composition-api";
  }

  let setupReturnExpr: string | null = null;
  if (Array.isArray(returns)) {
    const setupReturn = returns.find((ret) => {
      const fnName = (ret.function_name || "").toLowerCase();
      return fnName.includes("setup");
    });
    if (setupReturn && setupReturn.return_expr) {
      setupReturnExpr = truncateVueString(setupReturn.return_expr);
    }
  }

  const parsedProps = parseVuePropsDefinition(propsDefinition, componentName);
  const parsedEmits = parseVueEmitsDefinition(emitsDefinition, componentName);
  const parsedReturns = parseSetupReturn(setupReturnExpr, componentName);

  return {
    vue_components: [
      {
        name: componentName,
        type: componentType as
          | "script-setup"
          | "composition-api"
          | "options-api",
        start_line: startLine,
        end_line: endLine,
        has_template: Boolean(vueMeta.descriptor.template),
        has_style: Boolean(vueMeta.hasStyle),
        composition_api_used: usesCompositionApi,
      },
    ],
    vue_component_props: parsedProps,
    vue_component_emits: parsedEmits,
    vue_component_setup_returns: parsedReturns,
    primaryName: componentName,
  };
}

export function extractVueHooks(
  functionCallArgs: IFunctionCallArg[],
  componentName: string | null,
): IVueHook[] {
  const hooks: IVueHook[] = [];
  if (!componentName) return hooks;

  const grouped = groupFunctionCallArgs(functionCallArgs);

  grouped.forEach((args) => {
    if (!Array.isArray(args) || args.length === 0) return;

    const callee = args[0].callee_function || "";
    const baseName = getVueBaseName(callee);
    if (!baseName) return;

    const line = args[0].line || 0;

    if (
      VUE_LIFECYCLE_HOOKS.has(baseName) ||
      VUE_REACTIVITY_APIS.has(baseName)
    ) {
      const hookType = VUE_LIFECYCLE_HOOKS.has(baseName)
        ? "lifecycle"
        : "reactivity";

      hooks.push({
        line,
        component_name: componentName,
        hook_name: baseName,
        hook_type: hookType,
      });
    }
  });

  return hooks;
}

export function extractVueProvideInject(
  functionCallArgs: IFunctionCallArg[],
  componentName: string | null,
): IVueProvideInject[] {
  if (!componentName) return [];
  const grouped = groupFunctionCallArgs(functionCallArgs);
  const records: IVueProvideInject[] = [];

  grouped.forEach((args) => {
    if (!Array.isArray(args) || args.length === 0) return;
    const callee = args[0].callee_function || "";
    const baseName = getVueBaseName(callee);
    if (baseName !== "provide" && baseName !== "inject") return;

    const keyArg = args.find((arg) => arg.argument_index === 0);
    const valueArg = args.find((arg) => arg.argument_index === 1);
    const keyName =
      keyArg && keyArg.argument_expr
        ? truncateVueString(keyArg.argument_expr)
        : null;
    const valueExpr =
      valueArg && valueArg.argument_expr
        ? truncateVueString(valueArg.argument_expr)
        : null;

    records.push({
      line: args[0].line || 0,
      component_name: componentName,
      type: baseName as "provide" | "inject",
      key: keyName || "",
      value_type: valueExpr,
    });
  });

  return records;
}

interface TemplateNode {
  type: number;
  props?: Array<{
    type: number;
    name: string;
    modifiers?: Array<{ content?: string } | string>;
    exp?: { content?: string };
    loc?: { start: { line: number } };
  }>;
  children?: TemplateNode[];
  branches?: Array<{ children?: TemplateNode[] }>;
  loc?: { start: { line: number } };
}

interface NodeTypes {
  ELEMENT?: number;
  DIRECTIVE?: number;
  ROOT?: number;
  IF?: number;
  IF_BRANCH?: number;
  FOR?: number;
}

export function extractVueDirectives(
  templateAst: TemplateNode | null,
  componentName: string,
  nodeTypes: NodeTypes | null,
): IVueDirective[] {
  const directives: IVueDirective[] = [];
  if (!templateAst || !nodeTypes) return directives;

  const ELEMENT = nodeTypes.ELEMENT ?? 1;
  const DIRECTIVE = nodeTypes.DIRECTIVE ?? 7;
  const ROOT = nodeTypes.ROOT ?? 0;
  const IF = nodeTypes.IF ?? 9;
  const IF_BRANCH = nodeTypes.IF_BRANCH ?? 10;
  const FOR = nodeTypes.FOR ?? 11;

  function visit(node: TemplateNode): void {
    if (!node || typeof node !== "object") return;

    if (node.type === ELEMENT) {
      if (Array.isArray(node.props)) {
        for (const prop of node.props) {
          if (prop && prop.type === DIRECTIVE) {
            const modifiersText = Array.isArray(prop.modifiers)
              ? prop.modifiers
                  .map((mod) =>
                    typeof mod === "object" ? mod.content || "" : mod,
                  )
                  .join(",")
              : null;

            directives.push({
              line: prop.loc?.start.line ?? node.loc?.start.line ?? 0,
              component_name: componentName,
              directive_name: `v-${prop.name}`,
              directive_arg: null,
              directive_modifiers: modifiersText,
              directive_value:
                prop.exp && prop.exp.content
                  ? truncateVueString(prop.exp.content)
                  : null,
            });
          }
        }
      }
      if (Array.isArray(node.children)) {
        node.children.forEach(visit);
      }
    } else if (node.type === ROOT && Array.isArray(node.children)) {
      node.children.forEach(visit);
    } else if (node.type === IF && Array.isArray(node.branches)) {
      node.branches.forEach((branch) => {
        if (Array.isArray(branch.children)) {
          branch.children.forEach(visit);
        }
      });
    } else if (node.type === IF_BRANCH && Array.isArray(node.children)) {
      node.children.forEach(visit);
    } else if (node.type === FOR && Array.isArray(node.children)) {
      node.children.forEach(visit);
    } else if (Array.isArray(node.children)) {
      node.children.forEach(visit);
    }
  }

  visit(templateAst);
  return directives;
}

interface SymbolTableEntry {
  type?: string;
  value?: Record<string, Record<string, unknown>>;
  line?: number;
}

interface ExtractGraphQLResolversResult {
  graphql_resolvers: IGraphQLResolver[];
  graphql_resolver_params: IGraphQLResolverParam[];
}

export function extractApolloResolvers(
  functions: IFunction[],
  func_params: IFuncParam[],
  symbolTable: Record<string, SymbolTableEntry> | null,
  filePath: string,
): ExtractGraphQLResolversResult {
  const graphql_resolvers: IGraphQLResolver[] = [];
  const graphql_resolver_params: IGraphQLResolverParam[] = [];

  for (const [symbolName, symbolData] of Object.entries(symbolTable || {})) {
    if (
      symbolName.toLowerCase().includes("resolver") &&
      symbolData.type === "variable"
    ) {
      const objData = symbolData.value;
      if (objData && typeof objData === "object") {
        for (const typeName in objData) {
          const fields = objData[typeName];
          if (typeof fields === "object") {
            for (const fieldName in fields) {
              const fieldFunc = fields[fieldName];
              if (typeof fieldFunc === "function" || fieldFunc === "function") {
                const resolverName = `${typeName}.${fieldName}`;
                graphql_resolvers.push({
                  file: filePath,
                  line: symbolData.line || 0,
                  resolver_name: resolverName,
                  resolver_type: "apollo-object",
                  parent_type: typeName,
                });
              }
            }
          }
        }
      }
    }
  }

  for (const func of functions) {
    if (func.name && func.name.toLowerCase().includes("resolver")) {
      const resolverName = func.name;

      const funcParams = func_params.filter(
        (p) =>
          p.function_name === func.name &&
          !["parent", "args", "context", "info", "_"].includes(p.param_name),
      );

      for (const param of funcParams) {
        graphql_resolver_params.push({
          file: filePath,
          resolver_name: resolverName,
          param_name: param.param_name,
          param_type: param.param_type,
          param_index: param.param_index,
        });
      }

      graphql_resolvers.push({
        file: filePath,
        line: func.line,
        resolver_name: resolverName,
        resolver_type: "apollo-function",
        parent_type: null,
      });
    }
  }

  return { graphql_resolvers, graphql_resolver_params };
}

export function extractNestJSResolvers(
  functions: IFunction[],
  classes: IClass[],
  func_decorators: IFuncDecorator[],
  func_decorator_args: IFuncDecoratorArg[],
  class_decorators: IClassDecorator[],
  class_decorator_args: IClassDecoratorArg[],
  func_params: IFuncParam[],
  func_param_decorators: IFuncParamDecorator[],
  filePath: string,
): ExtractGraphQLResolversResult {
  const graphql_resolvers: IGraphQLResolver[] = [];
  const graphql_resolver_params: IGraphQLResolverParam[] = [];

  for (const cls of classes) {
    const clsDecorators = class_decorators.filter(
      (d) => d.class_name === cls.name && d.class_line === cls.line,
    );

    const resolverDecorator = clsDecorators.find(
      (d) => d.decorator_name === "Resolver",
    );
    if (!resolverDecorator) continue;

    let typeName = "Unknown";
    const resolverArgs = class_decorator_args.filter(
      (a) =>
        a.class_name === cls.name &&
        a.class_line === cls.line &&
        a.decorator_index === resolverDecorator.decorator_index,
    );
    if (resolverArgs.length > 0) {
      typeName = resolverArgs[0].arg_value.replace(/['"]/g, "");
    }

    const classMethods = functions.filter(
      (f) => f.name && f.name.startsWith(cls.name + "."),
    );

    for (const method of classMethods) {
      const methodDecorators = func_decorators.filter(
        (d) =>
          d.function_name === method.name && d.function_line === method.line,
      );

      for (const decorator of methodDecorators) {
        const decoratorName = decorator.decorator_name;

        if (
          ["Query", "Mutation", "Subscription", "ResolveField"].includes(
            decoratorName,
          )
        ) {
          let resolverTypeName = typeName;
          if (decoratorName === "Query") resolverTypeName = "Query";
          else if (decoratorName === "Mutation") resolverTypeName = "Mutation";
          else if (decoratorName === "Subscription")
            resolverTypeName = "Subscription";

          const resolverName = method.name;

          const methodParams = func_params.filter(
            (p) =>
              p.function_name === method.name &&
              p.function_line === method.line,
          );
          const paramDecorators = func_param_decorators.filter(
            (pd) =>
              pd.function_name === method.name &&
              pd.function_line === method.line,
          );
          const decoratedParamIndices = new Set(
            paramDecorators.map((pd) => pd.param_index),
          );

          for (const param of methodParams) {
            if (!decoratedParamIndices.has(param.param_index)) {
              graphql_resolver_params.push({
                file: filePath,
                resolver_name: resolverName,
                param_name: param.param_name,
                param_type: param.param_type,
                param_index: param.param_index,
              });
            }
          }

          graphql_resolvers.push({
            file: filePath,
            line: method.line,
            resolver_name: resolverName,
            resolver_type: "nestjs-decorator",
            parent_type: resolverTypeName,
          });
        }
      }
    }
  }

  return { graphql_resolvers, graphql_resolver_params };
}
