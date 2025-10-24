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
 * Functions (2 current + future growth):
 * 1. extractReactComponents() - React component detection (class & functional)
 * 2. extractReactHooks() - React Hooks usage patterns
 *
 * FUTURE ADDITIONS (planned):
 * - extractReactProps() - React prop types and validation
 * - extractTypeScriptTypes() - TypeScript type definitions
 * - extractVueComponents() - Vue component detection
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

