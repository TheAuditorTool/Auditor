/**
 * Framework & Type System Extractors
 *
 * Framework-specific pattern extraction (React, Vue, Angular) and TypeScript
 * type system features.
 *
 * Functions:
 * 1. extractReactComponents() - Returns { react_components, react_component_hooks }
 * 2. extractReactHooks() - Returns { react_hooks, react_hook_dependencies }
 * 3. extractVueComponents() - Returns { vue_components, vue_component_props, vue_component_emits, vue_component_setup_returns }
 * 4. extractVueHooks() - Returns array of vue_hooks
 * 5. extractVueProvideInject() - Returns array
 * 6. extractVueDirectives() - Returns array of vue_directives
 * 7. extractApolloResolvers() - Returns { graphql_resolvers, graphql_resolver_params }
 * 8. extractNestJSResolvers() - Returns { graphql_resolvers, graphql_resolver_params }
 * 9. extractTypeGraphQLResolvers() - Returns { graphql_resolvers, graphql_resolver_params }
 */

/**
 * Extract React components with flat hooks junction array.
 *
 * @returns {Object} - { react_components, react_component_hooks }
 */
function extractReactComponents(functions, classes, returns, functionCallArgs, filePath, imports) {
    const react_components = [];
    const react_component_hooks = [];

    const isBackendPath = filePath && (
        filePath.includes('backend/') ||
        filePath.includes('backend\\') ||
        filePath.includes('server/') ||
        filePath.includes('server\\') ||
        filePath.includes('/api/') ||
        filePath.includes('\\api\\') ||
        filePath.includes('controllers/') ||
        filePath.includes('controllers\\') ||
        filePath.includes('services/') ||
        filePath.includes('services\\') ||
        filePath.includes('middleware/') ||
        filePath.includes('middleware\\') ||
        filePath.includes('models/') ||
        filePath.includes('models\\') ||
        filePath.includes('routes/') ||
        filePath.includes('routes\\')
    );

    if (isBackendPath) {
        return { react_components, react_component_hooks };
    }

    const isFrontendPath = filePath && (
        filePath.includes('frontend/') ||
        filePath.includes('frontend\\') ||
        filePath.includes('client/') ||
        filePath.includes('client\\') ||
        filePath.includes('/components/') ||
        filePath.includes('\\components\\') ||
        filePath.includes('/pages/') ||
        filePath.includes('\\pages\\') ||
        filePath.includes('/ui/') ||
        filePath.includes('\\ui\\') ||
        filePath.endsWith('.tsx') ||
        filePath.endsWith('.jsx')
    );

    if (!isFrontendPath) {
        return { react_components, react_component_hooks };
    }

    for (const func of functions) {
        const name = func.name || '';
        if (!name || name[0] !== name[0].toUpperCase()) continue;

        const funcReturns = returns.filter(r => r.function_name === name);
        const hasJsx = funcReturns.some(r => r.has_jsx || r.returns_component);

        const seenHooks = new Set();
        for (const call of functionCallArgs) {
            if (call.caller_function === name && call.callee_function && call.callee_function.startsWith('use')) {
                const hookName = call.callee_function;
                if (!seenHooks.has(hookName)) {
                    seenHooks.add(hookName);
                    // Schema: component_file, component_name, hook_name
                    react_component_hooks.push({
                        component_file: filePath,
                        component_name: name,
                        hook_name: hookName
                    });
                }
            }
        }

        react_components.push({
            name: name,
            type: 'function',
            start_line: func.line,
            end_line: func.end_line || func.line,
            has_jsx: hasJsx,
            props_type: null
        });
    }

    for (const cls of classes) {
        const name = cls.name || '';
        if (!name || name[0] !== name[0].toUpperCase()) continue;

        const extendsReact = cls.extends_type &&
            (cls.extends_type.includes('Component') || cls.extends_type.includes('React'));

        if (extendsReact) {
            react_components.push({
                name: name,
                type: 'class',
                start_line: cls.line,
                end_line: cls.line,
                has_jsx: true,
                props_type: null
            });
        }
    }

    return { react_components, react_component_hooks };
}

/**
 * Extract React hooks with flat dependency junction array.
 *
 * @returns {Object} - { react_hooks, react_hook_dependencies }
 */
function extractReactHooks(functionCallArgs, scopeMap, filePath) {
    const react_hooks = [];
    const react_hook_dependencies = [];

    const REACT_HOOKS = new Set([
        'useState', 'useEffect', 'useCallback', 'useMemo', 'useRef',
        'useContext', 'useReducer', 'useLayoutEffect', 'useImperativeHandle',
        'useDebugValue', 'useDeferredValue', 'useTransition', 'useId'
    ]);

    const HOOKS_WITH_DEPS = new Set([
        'useEffect', 'useCallback', 'useMemo', 'useLayoutEffect', 'useImperativeHandle'
    ]);

    for (const call of functionCallArgs) {
        const hookName = call.callee_function;
        if (!hookName || !hookName.startsWith('use')) continue;
        if (hookName.includes('.')) continue;

        const isReactHook = REACT_HOOKS.has(hookName);
        const isCustomHook = !isReactHook && hookName.startsWith('use') && hookName.length > 3;

        if (isReactHook || isCustomHook) {
            const hookLine = call.line;
            const componentName = call.caller_function;

            react_hooks.push({
                line: hookLine,
                hook_name: hookName,
                component_name: componentName,
                is_custom: isCustomHook,
                argument_count: call.argument_index !== undefined ? call.argument_index + 1 : 0
            });

            if (HOOKS_WITH_DEPS.has(hookName) && call.argument_expr) {
                const deps = parseDependencyArray(call.argument_expr);
                for (const dep of deps) {
                    // Schema: hook_file, hook_line, hook_component, dependency_name
                    react_hook_dependencies.push({
                        hook_file: filePath,
                        hook_line: hookLine,
                        hook_component: componentName,
                        dependency_name: dep
                    });
                }
            }
        }
    }

    return { react_hooks, react_hook_dependencies };
}

function parseDependencyArray(expr) {
    if (!expr || typeof expr !== 'string') return [];
    const trimmed = expr.trim();

    if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
        const inner = trimmed.slice(1, -1).trim();
        if (!inner) return [];

        const deps = [];
        let depth = 0;
        let current = '';

        for (const char of inner) {
            if (char === '[' || char === '(' || char === '{') {
                depth++;
                current += char;
            } else if (char === ']' || char === ')' || char === '}') {
                depth--;
                current += char;
            } else if (char === ',' && depth === 0) {
                const dep = current.trim();
                if (dep && isValidDependencyName(dep)) {
                    deps.push(extractBaseName(dep));
                }
                current = '';
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

function isValidDependencyName(name) {
    if (!name) return false;
    return /^[a-zA-Z_$][a-zA-Z0-9_$]*(\??\.[\w$]+)*$/.test(name);
}

function extractBaseName(expr) {
    if (expr.includes('(')) {
        return expr.split('(')[0].trim();
    }
    return expr;
}

// Vue constants
const VUE_LIFECYCLE_HOOKS = new Set([
    'onMounted', 'onBeforeMount', 'onBeforeUpdate', 'onUpdated',
    'onBeforeUnmount', 'onUnmounted', 'onActivated', 'onDeactivated',
    'onErrorCaptured', 'onRenderTracked', 'onRenderTriggered', 'onServerPrefetch'
]);

const VUE_REACTIVITY_APIS = new Set([
    'watch', 'watchEffect', 'watchPostEffect', 'watchSyncEffect',
    'ref', 'reactive', 'computed'
]);

function truncateVueString(value, maxLength = 1000) {
    if (!value || typeof value !== 'string') return value || null;
    return value.length > maxLength ? value.slice(0, maxLength) + '...' : value;
}

function getVueBaseName(name) {
    if (!name || typeof name !== 'string') return '';
    const parts = name.split('.');
    return parts[parts.length - 1] || '';
}

function inferVueComponentName(vueMeta, filePath) {
    if (vueMeta && vueMeta.descriptor && vueMeta.descriptor.filename) {
        filePath = vueMeta.descriptor.filename;
    }
    if (!filePath) return 'AnonymousVueComponent';
    const segments = filePath.split(/[/\\]/);
    const candidate = segments.pop() || 'Component';
    const base = candidate.replace(/\.vue$/i, '') || 'Component';
    return base.charAt(0).toUpperCase() + base.slice(1);
}

function groupFunctionCallArgs(functionCallArgs) {
    const grouped = new Map();
    if (!Array.isArray(functionCallArgs)) return grouped;
    for (const call of functionCallArgs) {
        const callee = call.callee_function || '';
        if (!callee) continue;
        const key = `${call.line || 0}:${callee}`;
        if (!grouped.has(key)) grouped.set(key, []);
        grouped.get(key).push(call);
    }
    return grouped;
}

function findFirstVueMacroCall(functionCallArgs, macroName) {
    if (!Array.isArray(functionCallArgs)) return null;
    for (const call of functionCallArgs) {
        const baseName = getVueBaseName(call.callee_function || '');
        if (baseName === macroName && (call.argument_index === 0 || call.argument_index === null)) {
            if (call.argument_expr && call.argument_expr.trim()) {
                return truncateVueString(call.argument_expr.trim());
            }
        }
    }
    return null;
}

function parseVuePropsDefinition(propsString, componentName) {
    if (!propsString || typeof propsString !== 'string') return [];
    const props = [];
    const trimmed = propsString.trim();

    if (trimmed.startsWith('[')) {
        const arrayMatch = trimmed.match(/\[\s*([^\]]*)\s*\]/);
        if (arrayMatch && arrayMatch[1]) {
            const items = arrayMatch[1].split(',').map(s => s.trim().replace(/['"]/g, ''));
            for (const item of items) {
                if (item) {
                    props.push({
                        component_name: componentName,
                        prop_name: item,
                        prop_type: null,
                        is_required: 0,
                        default_value: null
                    });
                }
            }
        }
        return props;
    }

    if (trimmed.startsWith('{')) {
        const propPattern = /(\w+)\s*:\s*({[^{}]*(?:{[^{}]*}[^{}]*)*}|[^,}]+)/g;
        let match;
        while ((match = propPattern.exec(trimmed)) !== null) {
            const propName = match[1];
            const propValue = match[2].trim();
            let propType = null;
            let isRequired = 0;
            let defaultValue = null;

            if (propValue.startsWith('{')) {
                const typeMatch = propValue.match(/type\s*:\s*(\w+)/);
                if (typeMatch) propType = typeMatch[1];
                const reqMatch = propValue.match(/required\s*:\s*(true|false)/);
                if (reqMatch && reqMatch[1] === 'true') isRequired = 1;
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
                default_value: defaultValue
            });
        }
    }
    return props;
}

function parseVueEmitsDefinition(emitsString, componentName) {
    if (!emitsString || typeof emitsString !== 'string') return [];
    const emits = [];
    const trimmed = emitsString.trim();

    if (trimmed.startsWith('[')) {
        const arrayMatch = trimmed.match(/\[\s*([^\]]*)\s*\]/);
        if (arrayMatch && arrayMatch[1]) {
            const items = arrayMatch[1].split(',').map(s => s.trim().replace(/['"]/g, ''));
            for (const item of items) {
                if (item) {
                    emits.push({
                        component_name: componentName,
                        emit_name: item,
                        payload_type: null
                    });
                }
            }
        }
        return emits;
    }

    if (trimmed.startsWith('{')) {
        const emitPattern = /(\w+)\s*:/g;
        let match;
        while ((match = emitPattern.exec(trimmed)) !== null) {
            const emitName = match[1];
            const afterColon = trimmed.slice(match.index + match[0].length);
            let payloadType = null;
            const funcMatch = afterColon.match(/^\s*\(\s*(\w+)\s*:\s*(\w+)/);
            if (funcMatch) payloadType = funcMatch[2];
            emits.push({
                component_name: componentName,
                emit_name: emitName,
                payload_type: payloadType
            });
        }
    }
    return emits;
}

function parseSetupReturn(returnExpr, componentName) {
    if (!returnExpr || typeof returnExpr !== 'string') return [];
    const returns = [];
    const trimmed = returnExpr.trim();

    if (trimmed.startsWith('{')) {
        const inner = trimmed.slice(1, -1).trim();
        if (!inner) return returns;
        const parts = inner.split(',');
        for (const part of parts) {
            const cleaned = part.trim();
            if (!cleaned) continue;
            const colonIndex = cleaned.indexOf(':');
            let returnName;
            if (colonIndex > 0) {
                returnName = cleaned.slice(0, colonIndex).trim();
            } else {
                returnName = cleaned.split(/[^a-zA-Z0-9_$]/)[0];
            }
            if (returnName && /^[a-zA-Z_$][a-zA-Z0-9_$]*$/.test(returnName)) {
                returns.push({
                    component_name: componentName,
                    return_name: returnName,
                    return_type: null
                });
            }
        }
    }
    return returns;
}

function extractVueComponents(vueMeta, filePath, functionCallArgs, returns) {
    if (!vueMeta || !vueMeta.descriptor) {
        const fallbackName = inferVueComponentName(null, filePath);
        return {
            vue_components: [],
            vue_component_props: [],
            vue_component_emits: [],
            vue_component_setup_returns: [],
            primaryName: fallbackName
        };
    }

    const componentName = inferVueComponentName(vueMeta, filePath);
    const scriptBlock = vueMeta.descriptor.scriptSetup || vueMeta.descriptor.script;
    const startLine = scriptBlock && scriptBlock.loc ? scriptBlock.loc.start.line : 1;
    const endLine = scriptBlock && scriptBlock.loc ? scriptBlock.loc.end.line : startLine;

    const propsDefinition = findFirstVueMacroCall(functionCallArgs, 'defineProps');
    const emitsDefinition = findFirstVueMacroCall(functionCallArgs, 'defineEmits');

    const usesCompositionApi = Boolean(vueMeta.descriptor.scriptSetup) ||
        (Array.isArray(functionCallArgs) && functionCallArgs.some(call => getVueBaseName(call.callee_function || '') === 'defineComponent'));

    let componentType = 'options-api';
    if (vueMeta.descriptor.scriptSetup) {
        componentType = 'script-setup';
    } else if (usesCompositionApi) {
        componentType = 'composition-api';
    }

    let setupReturnExpr = null;
    if (Array.isArray(returns)) {
        const setupReturn = returns.find(ret => {
            const fnName = (ret.function_name || '').toLowerCase();
            return fnName.includes('setup');
        });
        if (setupReturn && setupReturn.return_expr) {
            setupReturnExpr = truncateVueString(setupReturn.return_expr);
        }
    }

    const parsedProps = parseVuePropsDefinition(propsDefinition, componentName);
    const parsedEmits = parseVueEmitsDefinition(emitsDefinition, componentName);
    const parsedReturns = parseSetupReturn(setupReturnExpr, componentName);

    return {
        vue_components: [{
            name: componentName,
            type: componentType,
            start_line: startLine,
            end_line: endLine,
            has_template: Boolean(vueMeta.descriptor.template),
            has_style: Boolean(vueMeta.hasStyle),
            composition_api_used: usesCompositionApi
        }],
        vue_component_props: parsedProps,
        vue_component_emits: parsedEmits,
        vue_component_setup_returns: parsedReturns,
        primaryName: componentName
    };
}

/**
 * Extract Vue hooks. Schema has `dependencies` as TEXT column.
 */
function extractVueHooks(functionCallArgs, componentName) {
    const hooks = [];

    if (!componentName) {
        return hooks;
    }

    const grouped = groupFunctionCallArgs(functionCallArgs);

    grouped.forEach(args => {
        if (!Array.isArray(args) || args.length === 0) return;

        const callee = args[0].callee_function || '';
        const baseName = getVueBaseName(callee);
        if (!baseName) return;

        const line = args[0].line || 0;

        if (VUE_LIFECYCLE_HOOKS.has(baseName) || VUE_REACTIVITY_APIS.has(baseName)) {
            const hookType = VUE_LIFECYCLE_HOOKS.has(baseName) ? 'lifecycle' : 'reactivity';
            const dependencyArg = args.find(arg => arg.argument_index === 0);
            const handlerArg = hookType === 'reactivity'
                ? args.find(arg => arg.argument_index === 1)
                : args.find(arg => arg.argument_index === 0);

            // Schema: file, line, component_name, hook_name, hook_type, dependencies (TEXT), return_value, is_async
            hooks.push({
                line,
                component_name: componentName,
                hook_name: baseName,
                hook_type: hookType,
                dependencies: dependencyArg && dependencyArg.argument_expr
                    ? truncateVueString(dependencyArg.argument_expr)
                    : null,
                return_value: handlerArg && handlerArg.argument_expr
                    ? truncateVueString(handlerArg.argument_expr)
                    : null,
                is_async: Boolean(handlerArg && handlerArg.argument_expr && handlerArg.argument_expr.trim().startsWith('async'))
            });
        }
    });

    return hooks;
}

function extractVueProvideInject(functionCallArgs, componentName) {
    if (!componentName) return [];
    const grouped = groupFunctionCallArgs(functionCallArgs);
    const records = [];

    grouped.forEach(args => {
        if (!Array.isArray(args) || args.length === 0) return;
        const callee = args[0].callee_function || '';
        const baseName = getVueBaseName(callee);
        if (baseName !== 'provide' && baseName !== 'inject') return;

        const keyArg = args.find(arg => arg.argument_index === 0);
        const valueArg = args.find(arg => arg.argument_index === 1);
        const keyName = keyArg && keyArg.argument_expr ? truncateVueString(keyArg.argument_expr) : null;
        const valueExpr = valueArg && valueArg.argument_expr ? truncateVueString(valueArg.argument_expr) : null;

        records.push({
            line: args[0].line || 0,
            component_name: componentName,
            operation_type: baseName,
            key_name: keyName || '',
            value_expr: valueExpr,
            is_reactive: Boolean(valueExpr && /ref\s*\(|reactive\s*\(/.test(valueExpr))
        });
    });

    return records;
}

/**
 * Extract Vue directives. Schema has `modifiers` as TEXT column.
 */
function extractVueDirectives(templateAst, componentName, nodeTypes) {
    const directives = [];

    if (!templateAst || !nodeTypes) {
        return directives;
    }

    const ELEMENT = nodeTypes.ELEMENT ?? 1;
    const DIRECTIVE = nodeTypes.DIRECTIVE ?? 7;
    const ROOT = nodeTypes.ROOT ?? 0;
    const IF = nodeTypes.IF ?? 9;
    const IF_BRANCH = nodeTypes.IF_BRANCH ?? 10;
    const FOR = nodeTypes.FOR ?? 11;

    function visit(node) {
        if (!node || typeof node !== 'object') return;

        if (node.type === ELEMENT) {
            if (Array.isArray(node.props)) {
                for (const prop of node.props) {
                    if (prop && prop.type === DIRECTIVE) {
                        // Schema: file, line, directive_name, expression, in_component, has_key, modifiers (TEXT)
                        const modifiersText = Array.isArray(prop.modifiers)
                            ? prop.modifiers.map(mod => mod.content || mod).join(',')
                            : null;

                        directives.push({
                            line: prop.loc ? prop.loc.start.line : (node.loc ? node.loc.start.line : 0),
                            directive_name: `v-${prop.name}`,
                            expression: prop.exp && prop.exp.content ? truncateVueString(prop.exp.content) : null,
                            in_component: componentName,
                            has_key: prop.name === 'for',
                            modifiers: modifiersText
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
            node.branches.forEach(branch => {
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

/**
 * GraphQL Resolver Extractors
 *
 * Accept flat junction arrays as parameters instead of relying on nested properties.
 */

function extractApolloResolvers(functions, func_params, symbolTable) {
    const graphql_resolvers = [];
    const graphql_resolver_params = [];

    for (const [symbolName, symbolData] of Object.entries(symbolTable || {})) {
        if (symbolName.toLowerCase().includes('resolver') && symbolData.type === 'variable') {
            const objData = symbolData.value;
            if (objData && typeof objData === 'object') {
                for (const typeName in objData) {
                    const fields = objData[typeName];
                    if (typeof fields === 'object') {
                        for (const fieldName in fields) {
                            const fieldFunc = fields[fieldName];
                            if (typeof fieldFunc === 'function' || fieldFunc === 'function') {
                                const resolverName = `${typeName}.${fieldName}`;
                                graphql_resolvers.push({
                                    line: symbolData.line || 0,
                                    resolver_name: resolverName,
                                    field_name: fieldName,
                                    type_name: typeName,
                                    binding_style: 'apollo-object'
                                });
                            }
                        }
                    }
                }
            }
        }
    }

    for (const func of functions) {
        if (func.name && func.name.toLowerCase().includes('resolver')) {
            const fieldName = func.name.replace(/Resolver$/i, '').replace(/^resolve/i, '');
            const resolverName = func.name;

            const funcParams = func_params.filter(p =>
                p.function_name === func.name &&
                !['parent', 'args', 'context', 'info', '_'].includes(p.param_name)
            );

            for (const param of funcParams) {
                graphql_resolver_params.push({
                    resolver_name: resolverName,
                    param_index: param.param_index,
                    param_name: param.param_name
                });
            }

            graphql_resolvers.push({
                line: func.line,
                resolver_name: resolverName,
                field_name: fieldName,
                type_name: 'Unknown',
                binding_style: 'apollo-function'
            });
        }
    }

    return { graphql_resolvers, graphql_resolver_params };
}

function extractNestJSResolvers(functions, classes, func_decorators, func_decorator_args, class_decorators, class_decorator_args, func_params, func_param_decorators) {
    const graphql_resolvers = [];
    const graphql_resolver_params = [];

    for (const cls of classes) {
        const clsDecorators = class_decorators.filter(d =>
            d.class_name === cls.name && d.class_line === cls.line
        );

        const resolverDecorator = clsDecorators.find(d => d.decorator_name === 'Resolver');
        if (!resolverDecorator) continue;

        let typeName = 'Unknown';
        const resolverArgs = class_decorator_args.filter(a =>
            a.class_name === cls.name &&
            a.class_line === cls.line &&
            a.decorator_index === resolverDecorator.decorator_index
        );
        if (resolverArgs.length > 0) {
            typeName = resolverArgs[0].arg_value.replace(/['"]/g, '');
        }

        const classMethods = functions.filter(f =>
            f.name && f.name.startsWith(cls.name + '.')
        );

        for (const method of classMethods) {
            const methodDecorators = func_decorators.filter(d =>
                d.function_name === method.name && d.function_line === method.line
            );

            for (const decorator of methodDecorators) {
                const decoratorName = decorator.decorator_name;

                if (['Query', 'Mutation', 'Subscription', 'ResolveField'].includes(decoratorName)) {
                    let fieldName = method.name.split('.').pop();
                    const decArgs = func_decorator_args.filter(a =>
                        a.function_name === method.name &&
                        a.function_line === method.line &&
                        a.decorator_index === decorator.decorator_index
                    );
                    if (decArgs.length > 0) {
                        fieldName = decArgs[0].arg_value.replace(/['"]/g, '');
                    }

                    let resolverTypeName = typeName;
                    if (decoratorName === 'Query') resolverTypeName = 'Query';
                    else if (decoratorName === 'Mutation') resolverTypeName = 'Mutation';
                    else if (decoratorName === 'Subscription') resolverTypeName = 'Subscription';

                    const resolverName = method.name;

                    const methodParams = func_params.filter(p =>
                        p.function_name === method.name && p.function_line === method.line
                    );
                    const paramDecorators = func_param_decorators.filter(pd =>
                        pd.function_name === method.name && pd.function_line === method.line
                    );
                    const decoratedParamIndices = new Set(paramDecorators.map(pd => pd.param_index));

                    for (const param of methodParams) {
                        if (!decoratedParamIndices.has(param.param_index)) {
                            graphql_resolver_params.push({
                                resolver_name: resolverName,
                                param_index: param.param_index,
                                param_name: param.param_name
                            });
                        }
                    }

                    graphql_resolvers.push({
                        line: method.line,
                        resolver_name: resolverName,
                        field_name: fieldName,
                        type_name: resolverTypeName,
                        binding_style: 'nestjs-decorator'
                    });
                }
            }
        }
    }

    return { graphql_resolvers, graphql_resolver_params };
}

function extractTypeGraphQLResolvers(functions, classes, func_decorators, func_decorator_args, class_decorators, class_decorator_args, func_params, func_param_decorators) {
    const graphql_resolvers = [];
    const graphql_resolver_params = [];

    for (const cls of classes) {
        const clsDecorators = class_decorators.filter(d =>
            d.class_name === cls.name && d.class_line === cls.line
        );

        const resolverDecorator = clsDecorators.find(d => d.decorator_name === 'Resolver');
        if (!resolverDecorator) continue;

        let typeName = 'Unknown';
        const resolverArgs = class_decorator_args.filter(a =>
            a.class_name === cls.name &&
            a.class_line === cls.line &&
            a.decorator_index === resolverDecorator.decorator_index
        );
        if (resolverArgs.length > 0) {
            const arg = resolverArgs[0].arg_value;
            if (arg.includes('=>')) {
                typeName = arg.split('=>')[1].trim();
            }
        }

        const classMethods = functions.filter(f =>
            f.name && f.name.startsWith(cls.name + '.')
        );

        for (const method of classMethods) {
            const methodDecorators = func_decorators.filter(d =>
                d.function_name === method.name && d.function_line === method.line
            );

            for (const decorator of methodDecorators) {
                const decoratorName = decorator.decorator_name;

                if (['Query', 'Mutation', 'Subscription', 'FieldResolver'].includes(decoratorName)) {
                    let fieldName = method.name.split('.').pop();
                    const decArgs = func_decorator_args.filter(a =>
                        a.function_name === method.name &&
                        a.function_line === method.line &&
                        a.decorator_index === decorator.decorator_index
                    );
                    if (decArgs.length > 0) {
                        const arg = decArgs[0].arg_value;
                        if (typeof arg === 'string' && !arg.includes('=>')) {
                            fieldName = arg.replace(/['"]/g, '');
                        }
                    }

                    let resolverTypeName = typeName;
                    if (decoratorName === 'Query') resolverTypeName = 'Query';
                    else if (decoratorName === 'Mutation') resolverTypeName = 'Mutation';
                    else if (decoratorName === 'Subscription') resolverTypeName = 'Subscription';

                    const resolverName = method.name;

                    const methodParamDecorators = func_param_decorators.filter(pd =>
                        pd.function_name === method.name &&
                        pd.function_line === method.line &&
                        pd.decorator_name === 'Arg'
                    );
                    const argParamIndices = new Set(methodParamDecorators.map(pd => pd.param_index));

                    const methodParams = func_params.filter(p =>
                        p.function_name === method.name &&
                        p.function_line === method.line &&
                        argParamIndices.has(p.param_index)
                    );

                    for (const param of methodParams) {
                        graphql_resolver_params.push({
                            resolver_name: resolverName,
                            param_index: param.param_index,
                            param_name: param.param_name
                        });
                    }

                    graphql_resolvers.push({
                        line: method.line,
                        resolver_name: resolverName,
                        field_name: fieldName,
                        type_name: resolverTypeName,
                        binding_style: 'typegraphql-decorator'
                    });
                }
            }
        }
    }

    return { graphql_resolvers, graphql_resolver_params };
}
