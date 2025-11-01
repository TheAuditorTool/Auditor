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
        directives: [],
        di_injections: []
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

        // Detect @Component decorator using actual decorator data
        const componentDecorator = cls.decorators && cls.decorators.find(d => d.name === 'Component');

        if (componentDecorator) {
                // Extract @Input/@Output properties from class
                const inputs = [];
                const outputs = [];

                // Look for @Input/@Output decorators on class properties/methods
                if (functions) {
                    for (const func of functions) {
                        if (func.parent_class === className && func.decorators) {
                            for (const decorator of func.decorators) {
                                if (decorator.name === 'Input') {
                                    inputs.push({
                                        name: func.name,
                                        line: func.line
                                    });
                                } else if (decorator.name === 'Output') {
                                    outputs.push({
                                        name: func.name,
                                        line: func.line
                                    });
                                }
                            }
                        }
                    }
                }

                // Also check class properties if available
                if (cls.properties) {
                    for (const prop of cls.properties) {
                        if (prop.decorators) {
                            for (const decorator of prop.decorators) {
                                if (decorator.name === 'Input') {
                                    inputs.push({
                                        name: prop.name,
                                        line: prop.line
                                    });
                                } else if (decorator.name === 'Output') {
                                    outputs.push({
                                        name: prop.name,
                                        line: prop.line
                                    });
                                }
                            }
                        }
                    }
                }

                results.components.push({
                    name: className,
                    line: cls.line,
                    inputs_count: inputs.length,
                    outputs_count: outputs.length,
                    has_lifecycle_hooks: _detectAngularLifecycleHooks(cls, functions)
                });

                // Extract DI for components
                const dependencies = _extractAngularDI(cls, functionCallArgs);
                for (const dep of dependencies) {
                    results.di_injections.push({
                        line: cls.line,
                        target_class: className,
                        service: dep.service,
                        injection_type: 'constructor'
                    });
                }
        }

        // Detect @Injectable decorator (services)
        const injectableDecorator = cls.decorators && cls.decorators.find(d => d.name === 'Injectable');

        if (injectableDecorator) {
                // Extract constructor DI parameters
                const diDependencies = _extractAngularDI(cls, functionCallArgs);

                results.services.push({
                    name: className,
                    line: cls.line,
                    injectable: true,
                    dependencies: diDependencies
                });

                // Add DI injections for services
                for (const dep of diDependencies) {
                    results.di_injections.push({
                        line: cls.line,
                        target_class: className,
                        service: dep.service,
                        injection_type: 'constructor'
                    });
                }
        }

        // Detect @NgModule decorator
        const ngModuleDecorator = cls.decorators && cls.decorators.find(d => d.name === 'NgModule');

        if (ngModuleDecorator) {
            const moduleConfig = {};

            // Extract module configuration from decorator arguments
            if (ngModuleDecorator.arguments && ngModuleDecorator.arguments[0]) {
                const config = ngModuleDecorator.arguments[0];
                if (typeof config === 'object') {
                    moduleConfig.declarations = config.declarations || [];
                    moduleConfig.imports = config.imports || [];
                    moduleConfig.providers = config.providers || [];
                    moduleConfig.exports = config.exports || [];
                    moduleConfig.bootstrap = config.bootstrap || [];
                }
            }

            results.modules.push({
                name: className,
                line: cls.line,
                ...moduleConfig
            });
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
 * Heuristic implementation: Looks for common service patterns in constructor calls.
 * Full implementation would require analyzing constructor AST nodes for type annotations.
 *
 * @param {Object} cls - Class object from extractClasses()
 * @param {Array} functionCallArgs - All function calls
 * @returns {Array} - Detected service dependencies
 * @private
 */
function _extractAngularDI(cls, functionCallArgs) {
    const dependencies = [];

    // Look for constructor calls that might indicate DI
    // Common patterns: this.http = http, this.router = router, etc.
    for (const call of functionCallArgs) {
        // Check for property assignments in the class that look like DI
        if (call.caller_class === cls.name) {
            // Look for common Angular service names
            const commonServices = ['http', 'HttpClient', 'Router', 'ActivatedRoute',
                                   'FormBuilder', 'AuthService', 'UserService',
                                   'DataService', 'ApiService'];

            for (const service of commonServices) {
                if (call.callee_function && call.callee_function.toLowerCase().includes(service.toLowerCase())) {
                    dependencies.push({ service: service });
                    break;
                }
            }
        }
    }

    return dependencies;
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
