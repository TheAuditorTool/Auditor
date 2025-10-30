/**
 * Angular Framework Extractors
 *
 * Extracts Angular components, services, modules, and dependency injection patterns
 * from TypeScript codebases.
 *
 * STABILITY: MODERATE - Changes when Angular API updates or new patterns emerge.
 *
 * DEPENDENCIES: core_ast_extractors.js (uses functions, classes, imports)
 * USED BY: Indexer for Angular framework pattern detection
 *
 * Architecture:
 * - Extracted from: framework_extractors.js (split 2025-10-31)
 * - Pattern: Detect Angular decorators via naming conventions + imports
 * - Assembly: Concatenated after bullmq_extractors.js, before batch_templates.js
 *
 * KNOWN LIMITATIONS:
 * - Uses naming conventions (@Component = class name includes "Component") rather than AST decorator detection
 * - Will produce false positives for non-Angular classes with Angular-style naming
 * - Proper implementation requires parsing TypeScript decorators from AST nodes
 *
 * Functions:
 * 1. extractAngularComponents() - Detect Angular components, services, modules, guards
 * 2. _detectAngularLifecycleHooks() - Check for lifecycle hook methods
 * 3. _extractAngularDI() - Extract dependency injection (STUB - needs AST)
 * 4. _detectGuardType() - Determine guard interface type
 *
 * Current size: 170 lines (2025-10-31)
 */

/**
 * Extract Angular components, services, modules, and dependency injection.
 * Detects: @Component, @Injectable, @NgModule, @Input, @Output decorators
 *
 * NOTE: This is a heuristic-based implementation that relies on naming conventions.
 * Proper decorator detection requires parsing TypeScript decorator AST nodes.
 *
 * @param {Array} functions - From extractFunctions()
 * @param {Array} classes - From extractClasses()
 * @param {Array} imports - From extract imports
 * @param {Array} functionCallArgs - From extractFunctionCallArgs()
 * @returns {Object} - Angular extraction results { components, services, modules, guards }
 */
function extractAngularComponents(functions, classes, imports, functionCallArgs) {
    const results = {
        components: [],
        services: [],
        modules: [],
        guards: [],
        pipes: [],
        directives: []
    };

    // Check if Angular is imported
    const hasAngular = imports && imports.some(imp =>
        imp.source === '@angular/core' ||
        imp.source === '@angular/common' ||
        imp.source === '@angular/router'
    );

    if (!hasAngular) {
        return results;
    }

    // Analyze classes for Angular decorators
    for (const cls of classes) {
        const className = cls.name;
        if (!className) continue;

        // Detect @Component decorator (HEURISTIC: class name + import check)
        // LIMITATION: Does not verify decorator is actually applied, only that it's imported
        if (className.includes('Component')) {
            const hasComponentImport = imports.some(imp =>
                imp.source === '@angular/core' && imp.specifier === 'Component'
            );

            if (hasComponentImport) {
                // Extract @Input/@Output properties from class
                const inputs = [];
                const outputs = [];

                // Look for Input/Output decorator usage in function calls
                for (const call of functionCallArgs) {
                    if (call.callee_function === 'Input' && call.caller_class === className) {
                        inputs.push({ line: call.line });
                    }
                    if (call.callee_function === 'Output' && call.caller_class === className) {
                        outputs.push({ line: call.line });
                    }
                }

                results.components.push({
                    name: className,
                    line: cls.line,
                    inputs_count: inputs.length,
                    outputs_count: outputs.length,
                    has_lifecycle_hooks: _detectAngularLifecycleHooks(cls, functions)
                });
            }
        }

        // Detect @Injectable decorator (services)
        // LIMITATION: Naming-based heuristic, not decorator AST parsing
        if (className.includes('Service')) {
            const hasInjectableImport = imports.some(imp =>
                imp.source === '@angular/core' && imp.specifier === 'Injectable'
            );

            if (hasInjectableImport) {
                // Extract constructor DI parameters
                const diDependencies = _extractAngularDI(cls, classes);

                results.services.push({
                    name: className,
                    line: cls.line,
                    injectable: true,
                    dependencies: diDependencies
                });
            }
        }

        // Detect @NgModule decorator
        // LIMITATION: Naming-based heuristic, not decorator AST parsing
        if (className.includes('Module')) {
            const hasModuleImport = imports.some(imp =>
                imp.source === '@angular/core' && imp.specifier === 'NgModule'
            );

            if (hasModuleImport) {
                results.modules.push({
                    name: className,
                    line: cls.line
                });
            }
        }

        // Detect route guards (CanActivate, CanDeactivate interfaces)
        if (className.includes('Guard')) {
            const implementsGuard = cls.implements_types && (
                cls.implements_types.includes('CanActivate') ||
                cls.implements_types.includes('CanDeactivate') ||
                cls.implements_types.includes('CanLoad')
            );

            if (implementsGuard) {
                results.guards.push({
                    name: className,
                    line: cls.line,
                    guard_type: _detectGuardType(cls)
                });
            }
        }
    }

    return results;
}

/**
 * Detect Angular lifecycle hooks in a class.
 * Checks for ngOnInit, ngOnDestroy, ngOnChanges, etc. methods.
 *
 * @param {Object} cls - Class object from extractClasses()
 * @param {Array} functions - All functions from extractFunctions()
 * @returns {boolean} - True if any lifecycle hook method exists
 * @private
 */
function _detectAngularLifecycleHooks(cls, functions) {
    const lifecycleHooks = ['ngOnInit', 'ngOnDestroy', 'ngOnChanges', 'ngAfterViewInit', 'ngDoCheck'];

    // Check if any lifecycle hook methods exist
    for (const func of functions) {
        if (func.parent_class === cls.name && lifecycleHooks.includes(func.name)) {
            return true;
        }
    }

    return false;
}

/**
 * Extract Angular dependency injection from constructor.
 *
 * STUB IMPLEMENTATION: Proper DI extraction requires analyzing constructor AST nodes
 * for parameter decorators and type annotations.
 *
 * @param {Object} cls - Class object from extractClasses()
 * @param {Array} classes - All classes (unused in stub)
 * @returns {Array} - Empty array (requires AST traversal for full implementation)
 * @private
 */
function _extractAngularDI(cls, classes) {
    // Angular DI is via constructor parameters with type annotations
    // This would require analyzing constructor AST nodes
    // For now, return empty array (full implementation needs AST traversal)
    return [];
}

/**
 * Detect guard type from class implements clause.
 *
 * @param {Object} cls - Class object from extractClasses()
 * @returns {string} - Guard type: 'CanActivate', 'CanDeactivate', 'CanLoad', or 'unknown'
 * @private
 */
function _detectGuardType(cls) {
    if (!cls.implements_types) return 'unknown';

    if (cls.implements_types.includes('CanActivate')) return 'CanActivate';
    if (cls.implements_types.includes('CanDeactivate')) return 'CanDeactivate';
    if (cls.implements_types.includes('CanLoad')) return 'CanLoad';

    return 'unknown';
}
