/**
 * Framework & Type System Extractors
 *
 * Framework-specific pattern extraction (React, Vue, Angular) and TypeScript
 * type system features. These extractors understand framework idioms and type definitions.
 *
 * STABILITY: MODERATE - Changes when frameworks update or new patterns emerge.
 * Less churn than security patterns, more than core language features.
 *
 * DEPENDENCIES: core_ast_extractors.js (uses functions, classes, symbols, returns)
 * USED BY: Indexer for framework pattern detection
 *
 * Architecture:
 * - Extracted from: js_helper_templates.py (refactored 2025-01-24)
 * - Pattern: Process data from core extractors to identify framework patterns
 * - Assembly: Concatenated after core_ast_extractors.js and security_extractors.js
 *
 * Functions (current):
 * 1. extractReactComponents() - React component detection (class & functional)
 * 2. extractReactHooks() - React Hooks usage patterns
 * 3. extractVueComponents() - Vue component metadata from SFC descriptors
 * 4. extractVueHooks() - Vue lifecycle/reactivity hook usage
 * 5. extractVueProvideInject() - Vue DI relationships
 * 6. extractVueDirectives() - Vue template directives
 *
 * FUTURE ADDITIONS (planned):
 * - extractReactProps() - React prop types and validation
 * - extractTypeScriptTypes() - TypeScript type definitions
 * - extractAngularComponents() - Angular component detection
 * - extractContextProviders() - React Context providers/consumers
 * - extractSuspenseBoundaries() - React Suspense boundaries
 * - extractErrorBoundaries() - React Error boundaries
 *
 * Current size: 140 lines (2025-01-24)
 * Growth policy: If React extractors exceed 500 lines, split into react_extractors.js
 * If multiple frameworks supported, split by framework (vue_extractors.js, angular_extractors.js)
 */

function extractReactComponents(functions, classes, returns, functionCallArgs, filePath, imports) {
    const components = [];

    // FIX: Only analyze frontend files for React components
    // Backend controllers may have uppercase method names but are NOT React components
    // This fixes 1,183 false positives (83.4% false positive rate)
    //
    // NOTE: Relies on framework detection (framework_detector.py) which maps directories
    // to frameworks in the `frameworks` table. Path-based filtering aligns with that mapping.

    // Explicit backend path exclusions (aligns with framework_detector.py backend detection)
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
        return components;
    }

    // Frontend path indicators (aligns with framework_detector.py frontend detection)
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

    // Only process if confirmed frontend file
    if (!isFrontendPath) {
        return components;
    }

    // Detect function components
    for (const func of functions) {
        const name = func.name || '';

        // Must be uppercase (React convention)
        if (!name || name[0] !== name[0].toUpperCase()) continue;

        // Check if returns JSX
        const funcReturns = returns.filter(r => r.function_name === name);
        const hasJsx = funcReturns.some(r => r.has_jsx || r.returns_component);

        // Find hooks used in this component
        const hooksUsed = [];
        for (const call of functionCallArgs) {
            if (call.caller_function === name && call.callee_function && call.callee_function.startsWith('use')) {
                hooksUsed.push(call.callee_function);
            }
        }

        components.push({
            name: name,
            type: 'function',
            start_line: func.line,
            end_line: func.end_line || func.line,
            has_jsx: hasJsx,
            hooks_used: [...new Set(hooksUsed)].slice(0, 10),
            props_type: null  // Could extract from type_annotation
        });
    }

    // Detect class components
    // Only include classes that extend React.Component (correct behavior)
    // Baseline incorrectly included ALL uppercase names (interfaces, types, regular classes)
    // Phase 5 fixes this contamination
    for (const cls of classes) {
        const name = cls.name || '';
        if (!name || name[0] !== name[0].toUpperCase()) continue;

        // CORRECT: Only classes extending React.Component are React components
        const extendsReact = cls.extends_type &&
            (cls.extends_type.includes('Component') || cls.extends_type.includes('React'));

        if (extendsReact) {
            components.push({
                name: name,
                type: 'class',
                start_line: cls.line,
                end_line: cls.line,  // Class end line not tracked
                has_jsx: true,
                hooks_used: [],
                props_type: null
            });
        }
    }

    return components;
}

/**
 * Extract React hooks usage for dependency analysis.
 * Detects: useState, useEffect, useCallback, useMemo, custom hooks.
 * Implements Python's javascript.py:515-587 hooks extraction.
 *
 * @param {Array} functionCallArgs - From extractFunctionCallArgs()
 * @param {Map} scopeMap - Line → function mapping
 * @returns {Array} - Hook usage records
 */
function extractReactHooks(functionCallArgs, scopeMap) {
    const hooks = [];

    const REACT_HOOKS = new Set([
        'useState', 'useEffect', 'useCallback', 'useMemo', 'useRef',
        'useContext', 'useReducer', 'useLayoutEffect', 'useImperativeHandle',
        'useDebugValue', 'useDeferredValue', 'useTransition', 'useId'
    ]);

    for (const call of functionCallArgs) {
        const hookName = call.callee_function;
        if (!hookName || !hookName.startsWith('use')) continue;

        // FIX: Filter out dotted method calls (userService.createUser, users.map)
        // Real hooks are standalone identifiers: useState, useEffect, useCustomHook
        // NOT: service.useMethod, obj.property.useFunc
        // This fixes 42 false positive React hook records
        if (hookName.includes('.')) continue;

        // Check if it's a known React hook or custom hook (starts with 'use')
        const isReactHook = REACT_HOOKS.has(hookName);
        const isCustomHook = !isReactHook && hookName.startsWith('use') && hookName.length > 3;

        if (isReactHook || isCustomHook) {
            hooks.push({
                line: call.line,
                hook_name: hookName,
                component_name: call.caller_function,
                is_custom: isCustomHook,
                argument_expr: call.argument_expr || '',
                argument_index: call.argument_index
            });
        }
    }

    return hooks;
}

const VUE_LIFECYCLE_HOOKS = new Set([
    'onMounted',
    'onBeforeMount',
    'onBeforeUpdate',
    'onUpdated',
    'onBeforeUnmount',
    'onUnmounted',
    'onActivated',
    'onDeactivated',
    'onErrorCaptured',
    'onRenderTracked',
    'onRenderTriggered',
    'onServerPrefetch'
]);

const VUE_REACTIVITY_APIS = new Set([
    'watch',
    'watchEffect',
    'watchPostEffect',
    'watchSyncEffect',
    'ref',
    'reactive',
    'computed'
]);

function truncateVueString(value, maxLength = 1000) {
    if (!value || typeof value !== 'string') {
        return value || null;
    }
    return value.length > maxLength ? value.slice(0, maxLength) + '…' : value;
}

function getVueBaseName(name) {
    if (!name || typeof name !== 'string') {
        return '';
    }
    const parts = name.split('.');
    return parts[parts.length - 1] || '';
}

function inferVueComponentName(vueMeta, filePath) {
    if (vueMeta && vueMeta.descriptor && vueMeta.descriptor.filename) {
        filePath = vueMeta.descriptor.filename;
    }
    if (!filePath) {
        return 'AnonymousVueComponent';
    }
    const segments = filePath.split(/[/\\]/);
    const candidate = segments.pop() || 'Component';
    const base = candidate.replace(/\.vue$/i, '') || 'Component';
    return base.charAt(0).toUpperCase() + base.slice(1);
}

function groupFunctionCallArgs(functionCallArgs) {
    const grouped = new Map();
    if (!Array.isArray(functionCallArgs)) {
        return grouped;
    }
    for (const call of functionCallArgs) {
        const callee = call.callee_function || '';
        if (!callee) continue;
        const key = `${call.line || 0}:${callee}`;
        if (!grouped.has(key)) {
            grouped.set(key, []);
        }
        grouped.get(key).push(call);
    }
    return grouped;
}

function findFirstVueMacroCall(functionCallArgs, macroName) {
    if (!Array.isArray(functionCallArgs)) {
        return null;
    }
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

/**
 * Parse Vue defineProps() argument into flat prop records.
 * Handles: { foo: String }, { foo: { type: String, required: true } }, ['foo', 'bar']
 *
 * @param {string|null} propsString - Raw defineProps() argument expression
 * @param {string} componentName - Parent component name for junction FK
 * @returns {Array} - Flat array of { component_name, prop_name, prop_type, is_required, default_value }
 */
function parseVuePropsDefinition(propsString, componentName) {
    if (!propsString || typeof propsString !== 'string') {
        return [];
    }

    const props = [];
    const trimmed = propsString.trim();

    // Handle array syntax: ['foo', 'bar']
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

    // Handle object syntax: { foo: String } or { foo: { type: String, required: true } }
    if (trimmed.startsWith('{')) {
        // Extract top-level key-value pairs using regex
        // Pattern: propName: Type or propName: { ... }
        const propPattern = /(\w+)\s*:\s*({[^{}]*(?:{[^{}]*}[^{}]*)*}|[^,}]+)/g;
        let match;

        while ((match = propPattern.exec(trimmed)) !== null) {
            const propName = match[1];
            const propValue = match[2].trim();

            let propType = null;
            let isRequired = 0;
            let defaultValue = null;

            // Check if value is an object config: { type: String, required: true }
            if (propValue.startsWith('{')) {
                // Extract type
                const typeMatch = propValue.match(/type\s*:\s*(\w+)/);
                if (typeMatch) {
                    propType = typeMatch[1];
                }
                // Extract required
                const reqMatch = propValue.match(/required\s*:\s*(true|false)/);
                if (reqMatch && reqMatch[1] === 'true') {
                    isRequired = 1;
                }
                // Extract default
                const defMatch = propValue.match(/default\s*:\s*([^,}]+)/);
                if (defMatch) {
                    defaultValue = defMatch[1].trim();
                }
            } else {
                // Shorthand syntax: foo: String
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

/**
 * Parse Vue defineEmits() argument into flat emit records.
 * Handles: ['update', 'delete'] or { update: null, submit: (payload: string) => void }
 *
 * @param {string|null} emitsString - Raw defineEmits() argument expression
 * @param {string} componentName - Parent component name for junction FK
 * @returns {Array} - Flat array of { component_name, emit_name, payload_type }
 */
function parseVueEmitsDefinition(emitsString, componentName) {
    if (!emitsString || typeof emitsString !== 'string') {
        return [];
    }

    const emits = [];
    const trimmed = emitsString.trim();

    // Handle array syntax: ['update', 'delete']
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

    // Handle object syntax: { update: null, submit: (payload: string) => void }
    if (trimmed.startsWith('{')) {
        // Extract emit names (keys) - simpler pattern for emit objects
        const emitPattern = /(\w+)\s*:/g;
        let match;

        while ((match = emitPattern.exec(trimmed)) !== null) {
            const emitName = match[1];
            // Try to extract payload type from function signature
            const afterColon = trimmed.slice(match.index + match[0].length);
            let payloadType = null;

            // Check for function signature: (payload: Type) => void
            const funcMatch = afterColon.match(/^\s*\(\s*(\w+)\s*:\s*(\w+)/);
            if (funcMatch) {
                payloadType = funcMatch[2];
            }

            emits.push({
                component_name: componentName,
                emit_name: emitName,
                payload_type: payloadType
            });
        }
    }

    return emits;
}

/**
 * Parse Vue setup() return expression into flat return records.
 * Handles: { count, increment, user } or { count: countRef, ... }
 *
 * @param {string|null} returnExpr - Raw setup return expression
 * @param {string} componentName - Parent component name for junction FK
 * @returns {Array} - Flat array of { component_name, return_name, return_type }
 */
function parseSetupReturn(returnExpr, componentName) {
    if (!returnExpr || typeof returnExpr !== 'string') {
        return [];
    }

    const returns = [];
    const trimmed = returnExpr.trim();

    // Handle object syntax: { count, increment } or { count: countRef }
    if (trimmed.startsWith('{')) {
        // Remove outer braces and split by comma
        const inner = trimmed.slice(1, -1).trim();
        if (!inner) return returns;

        // Split carefully (handle nested objects)
        const parts = inner.split(',');
        for (const part of parts) {
            const cleaned = part.trim();
            if (!cleaned) continue;

            // Check for key: value or shorthand
            const colonIndex = cleaned.indexOf(':');
            let returnName;

            if (colonIndex > 0) {
                // key: value syntax
                returnName = cleaned.slice(0, colonIndex).trim();
            } else {
                // Shorthand: just identifier
                returnName = cleaned.split(/[^a-zA-Z0-9_$]/)[0];
            }

            if (returnName && /^[a-zA-Z_$][a-zA-Z0-9_$]*$/.test(returnName)) {
                returns.push({
                    component_name: componentName,
                    return_name: returnName,
                    return_type: null  // Type inference not available from raw expression
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

    // Get raw macro expressions
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

    // Parse raw expressions into flat junction arrays
    const parsedProps = parseVuePropsDefinition(propsDefinition, componentName);
    const parsedEmits = parseVueEmitsDefinition(emitsDefinition, componentName);
    const parsedReturns = parseSetupReturn(setupReturnExpr, componentName);

    return {
        vue_components: [
            {
                name: componentName,
                type: componentType,
                start_line: startLine,
                end_line: endLine,
                has_template: Boolean(vueMeta.descriptor.template),
                has_style: Boolean(vueMeta.hasStyle),
                composition_api_used: usesCompositionApi
                // REMOVED: props_definition, emits_definition, setup_return (now in junction arrays)
            }
        ],
        vue_component_props: parsedProps,
        vue_component_emits: parsedEmits,
        vue_component_setup_returns: parsedReturns,
        primaryName: componentName
    };
}

function extractVueHooks(functionCallArgs, componentName) {
    if (!componentName) {
        return [];
    }
    const grouped = groupFunctionCallArgs(functionCallArgs);
    const hooks = [];

    grouped.forEach(args => {
        if (!Array.isArray(args) || args.length === 0) {
            return;
        }
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

            hooks.push({
                line,
                component_name: componentName,
                hook_name: baseName,
                hook_type: hookType,
                dependencies: dependencyArg && dependencyArg.argument_expr
                    ? [truncateVueString(dependencyArg.argument_expr)]
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
    if (!componentName) {
        return [];
    }
    const grouped = groupFunctionCallArgs(functionCallArgs);
    const records = [];

    grouped.forEach(args => {
        if (!Array.isArray(args) || args.length === 0) {
            return;
        }
        const callee = args[0].callee_function || '';
        const baseName = getVueBaseName(callee);
        if (baseName !== 'provide' && baseName !== 'inject') {
            return;
        }
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
        if (!node || typeof node !== 'object') {
            return;
        }

        if (node.type === ELEMENT) {
            if (Array.isArray(node.props)) {
                for (const prop of node.props) {
                    if (prop && prop.type === DIRECTIVE) {
                        directives.push({
                            line: prop.loc ? prop.loc.start.line : (node.loc ? node.loc.start.line : null),
                            directive_name: `v-${prop.name}`,
                            expression: prop.exp && prop.exp.content ? truncateVueString(prop.exp.content) : null,
                            in_component: componentName,
                            has_key: prop.name === 'for' ? true : false,
                            modifiers: Array.isArray(prop.modifiers) ? prop.modifiers.map(mod => mod.content || mod) : [],
                            argument: prop.arg && prop.arg.content ? prop.arg.content : null,
                            element_type: node.tag || null,
                            is_dynamic: prop.name === 'bind' || prop.name === 'on' || Boolean(prop.exp && prop.exp.content && prop.exp.content.trim().length > 0)
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
 * Extract GraphQL resolver patterns from JavaScript/TypeScript:
 * - Apollo Server (resolvers object pattern)
 * - NestJS (@Resolver, @Query, @Mutation decorators)
 * - TypeGraphQL (@Resolver, @Query decorators)
 *
 * Returns resolver metadata WITHOUT field_id (correlation happens in graphql build command).
 */

function extractApolloResolvers(functions, classes, symbolTable) {
    const resolvers = [];

    // Apollo pattern 1: Object literal resolvers
    // const resolvers = {
    //   Query: {
    //     user: (parent, args, context) => { ... }
    //   }
    // }
    for (const [symbolName, symbolData] of Object.entries(symbolTable)) {
        if (symbolName.toLowerCase().includes('resolver') && symbolData.type === 'variable') {
            const objData = symbolData.value;
            if (objData && typeof objData === 'object') {
                // Iterate over type names (Query, Mutation, etc.)
                for (const typeName in objData) {
                    const fields = objData[typeName];
                    if (typeof fields === 'object') {
                        for (const fieldName in fields) {
                            const fieldFunc = fields[fieldName];
                            if (typeof fieldFunc === 'function' || fieldFunc === 'function') {
                                resolvers.push({
                                    line: symbolData.line || 0,
                                    resolver_name: `${typeName}.${fieldName}`,
                                    field_name: fieldName,
                                    type_name: typeName,
                                    binding_style: 'apollo-object',
                                    params: []  // Parameters extracted from function signature
                                });
                            }
                        }
                    }
                }
            }
        }
    }

    // Apollo pattern 2: Exported resolver functions
    // export const userResolver = (parent, args, context) => { ... }
    for (const func of functions) {
        if (func.name && func.name.toLowerCase().includes('resolver')) {
            // Try to infer field name from function name
            const fieldName = func.name.replace(/Resolver$/i, '').replace(/^resolve/i, '');

            // Extract parameters (skip parent, args, context/info)
            // ARCHITECTURAL CONTRACT: Return { name: "param" } dicts matching core_ast_extractors.js
            const params = (func.params || [])
                .filter(p => !['parent', 'args', 'context', 'info', '_'].includes(p.name))
                .map(p => ({ name: p.name }));

            resolvers.push({
                line: func.line,
                resolver_name: func.name,
                field_name: fieldName,
                type_name: 'Unknown',  // Type inferred during graphql build
                binding_style: 'apollo-function',
                params: params
            });
        }
    }

    return resolvers;
}

function extractNestJSResolvers(functions, classes) {
    const resolvers = [];

    // NestJS pattern: @Resolver() class with @Query()/@Mutation() methods
    for (const cls of classes) {
        if (!cls.decorators) continue;

        // Check for @Resolver() decorator
        const hasResolverDecorator = cls.decorators.some(d =>
            d.name === 'Resolver' || d.expression && d.expression.includes('Resolver')
        );

        if (!hasResolverDecorator) continue;

        // Extract type name from @Resolver('TypeName') argument
        let typeName = 'Unknown';
        const resolverDecorator = cls.decorators.find(d => d.name === 'Resolver');
        if (resolverDecorator && resolverDecorator.arguments && resolverDecorator.arguments.length > 0) {
            typeName = resolverDecorator.arguments[0].replace(/['"]/g, '');
        }

        // Extract methods with @Query() or @Mutation() decorators
        for (const method of cls.methods || []) {
            if (!method.decorators) continue;

            for (const decorator of method.decorators) {
                const decoratorName = decorator.name || (decorator.expression || '').split('(')[0];

                if (['Query', 'Mutation', 'Subscription', 'ResolveField'].includes(decoratorName)) {
                    // Extract field name from decorator argument or use method name
                    let fieldName = method.name;
                    if (decorator.arguments && decorator.arguments.length > 0) {
                        fieldName = decorator.arguments[0].replace(/['"]/g, '');
                    }

                    // Determine type name based on decorator
                    let resolverTypeName = typeName;
                    if (decoratorName === 'Query') resolverTypeName = 'Query';
                    else if (decoratorName === 'Mutation') resolverTypeName = 'Mutation';
                    else if (decoratorName === 'Subscription') resolverTypeName = 'Subscription';

                    // Extract parameters (skip decorated params like @Args(), @Context())
                    // ARCHITECTURAL CONTRACT: Return { name: "param" } dicts matching core_ast_extractors.js
                    const params = (method.params || [])
                        .filter(p => !p.decorators || p.decorators.length === 0)
                        .map(p => ({ name: p.name }));

                    resolvers.push({
                        line: method.line,
                        resolver_name: `${cls.name}.${method.name}`,
                        field_name: fieldName,
                        type_name: resolverTypeName,
                        binding_style: 'nestjs-decorator',
                        params: params
                    });
                }
            }
        }
    }

    return resolvers;
}

function extractTypeGraphQLResolvers(functions, classes) {
    const resolvers = [];

    // TypeGraphQL pattern: @Resolver() class with @Query()/@Mutation() methods
    for (const cls of classes) {
        if (!cls.decorators) continue;

        // Check for @Resolver() decorator
        const hasResolverDecorator = cls.decorators.some(d =>
            d.name === 'Resolver' || d.expression && d.expression.includes('Resolver')
        );

        if (!hasResolverDecorator) continue;

        // Extract type name from @Resolver(of => TypeName) argument
        let typeName = 'Unknown';
        const resolverDecorator = cls.decorators.find(d => d.name === 'Resolver');
        if (resolverDecorator && resolverDecorator.arguments && resolverDecorator.arguments.length > 0) {
            const arg = resolverDecorator.arguments[0];
            // Parse arrow function: of => TypeName
            if (arg.includes('=>')) {
                typeName = arg.split('=>')[1].trim();
            }
        }

        // Extract methods with @Query(), @Mutation(), @FieldResolver() decorators
        for (const method of cls.methods || []) {
            if (!method.decorators) continue;

            for (const decorator of method.decorators) {
                const decoratorName = decorator.name || (decorator.expression || '').split('(')[0];

                if (['Query', 'Mutation', 'Subscription', 'FieldResolver'].includes(decoratorName)) {
                    // Extract field name from decorator argument or use method name
                    let fieldName = method.name;
                    if (decorator.arguments && decorator.arguments.length > 0) {
                        // TypeGraphQL uses returns => Type syntax
                        const arg = decorator.arguments[0];
                        if (typeof arg === 'string' && !arg.includes('=>')) {
                            fieldName = arg.replace(/['"]/g, '');
                        }
                    }

                    // Determine type name based on decorator
                    let resolverTypeName = typeName;
                    if (decoratorName === 'Query') resolverTypeName = 'Query';
                    else if (decoratorName === 'Mutation') resolverTypeName = 'Mutation';
                    else if (decoratorName === 'Subscription') resolverTypeName = 'Subscription';

                    // Extract parameters decorated with @Arg()
                    // ARCHITECTURAL CONTRACT: Return { name: "param" } dicts matching core_ast_extractors.js
                    const params = (method.params || [])
                        .filter(p => p.decorators && p.decorators.some(d => d.name === 'Arg'))
                        .map(p => ({ name: p.name }));

                    resolvers.push({
                        line: method.line,
                        resolver_name: `${cls.name}.${method.name}`,
                        field_name: fieldName,
                        type_name: resolverTypeName,
                        binding_style: 'typegraphql-decorator',
                        params: params
                    });
                }
            }
        }
    }

    return resolvers;
}

