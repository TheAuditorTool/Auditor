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
 * 5. _inferDeclarationType() - Infer type of NgModule declaration
 * 6. _inferProviderType() - Infer type of NgModule provider
 *
 * Current size: 385 lines (2025-11-26)
 * Updated: 2025-11-26 - Normalized to flat junction arrays, removed nested dependencies
 */

/**
 * Infer the type of an NgModule declaration from its name.
 * @param {string|Object} decl - Declaration name or object
 * @returns {string|null} - 'component', 'directive', 'pipe', or null
 */
function _inferDeclarationType(decl) {
    const name = typeof decl === 'string' ? decl : (decl && decl.name) || '';
    if (name.endsWith('Component')) return 'component';
    if (name.endsWith('Directive')) return 'directive';
    if (name.endsWith('Pipe')) return 'pipe';
    return null;
}

/**
 * Infer the type of an NgModule provider from its structure.
 * @param {string|Object} prov - Provider name or config object
 * @returns {string|null} - 'class', 'value', 'factory', 'existing', or null
 */
function _inferProviderType(prov) {
    if (typeof prov === 'string') return 'class';
    if (!prov || typeof prov !== 'object') return null;
    if (prov.useValue !== undefined) return 'value';
    if (prov.useFactory !== undefined) return 'factory';
    if (prov.useClass !== undefined) return 'class';
    if (prov.useExisting !== undefined) return 'existing';
    return null;
}

/**
 * Extract Angular components, services, modules, and dependency injection.
 * Detects: @Component, @Injectable, @NgModule, @Input, @Output decorators
 *
 * @param {Array} functions - From extractFunctions()
 * @param {Array} classes - From extractClasses()
 * @param {Array} imports - From extractImports()
 * @param {Array} functionCallArgs - From extractFunctionCallArgs()
 * @param {Array} func_decorators - From extractFunctions() junction array
 * @param {Array} class_decorators - From extractClasses() junction array
 * @param {Array} class_decorator_args - From extractClasses() junction array
 * @returns {Object} - Angular extraction results { components, services, modules, guards }
 */
function extractAngularComponents(functions, classes, imports, functionCallArgs, func_decorators, class_decorators, class_decorator_args) {
    const results = {
        components: [],
        services: [],
        modules: [],
        guards: [],
        pipes: [],
        directives: [],
        di_injections: [],
        angular_component_styles: [],
        angular_module_declarations: [],
        angular_module_imports: [],
        angular_module_providers: [],
        angular_module_exports: []
    };

    // Check if Angular is imported
    const hasAngular = imports && imports.some(imp =>
        imp.module === '@angular/core' ||
        imp.module === '@angular/common' ||
        imp.module === '@angular/router'
    );

    if (!hasAngular) {
        return results;
    }

    // Build lookup maps from flat decorator arrays
    const classDecoratorMap = new Map();
    for (const dec of (class_decorators || [])) {
        if (!classDecoratorMap.has(dec.class_name)) {
            classDecoratorMap.set(dec.class_name, []);
        }
        classDecoratorMap.get(dec.class_name).push(dec);
    }

    const classDecoratorArgsMap = new Map();
    for (const arg of (class_decorator_args || [])) {
        const key = `${arg.class_name}|${arg.decorator_index}`;
        if (!classDecoratorArgsMap.has(key)) {
            classDecoratorArgsMap.set(key, []);
        }
        classDecoratorArgsMap.get(key).push(arg);
    }

    const funcDecoratorMap = new Map();
    for (const dec of (func_decorators || [])) {
        const key = `${dec.function_name}`;
        if (!funcDecoratorMap.has(key)) {
            funcDecoratorMap.set(key, []);
        }
        funcDecoratorMap.get(key).push(dec);
    }

    // Analyze classes for Angular decorators
    for (const cls of classes) {
        const className = cls.name;
        if (!className) continue;

        // Get decorators for this class from lookup map
        const classDecorators = classDecoratorMap.get(className) || [];

        // Detect @Component decorator using flat decorator array
        const componentDecorator = classDecorators.find(d => d.decorator_name === 'Component');

        if (componentDecorator) {
            // Extract @Input/@Output from function decorators
            const inputs = [];
            const outputs = [];

            // Look for @Input/@Output decorators on class methods
            if (functions) {
                for (const func of functions) {
                    if (func.parent_class === className) {
                        const funcDecs = funcDecoratorMap.get(func.name) || [];
                        for (const decorator of funcDecs) {
                            if (decorator.decorator_name === 'Input') {
                                inputs.push({ name: func.name, line: func.line });
                            } else if (decorator.decorator_name === 'Output') {
                                outputs.push({ name: func.name, line: func.line });
                            }
                        }
                    }
                }
            }

            // Extract styleUrls from decorator args (arg_value contains stringified config)
            const decoratorArgsKey = `${className}|${componentDecorator.decorator_index}`;
            const componentArgs = classDecoratorArgsMap.get(decoratorArgsKey) || [];
            for (const arg of componentArgs) {
                if (arg.arg_value) {
                    // Parse styleUrls from stringified decorator argument
                    const styleMatch = arg.arg_value.match(/styleUrls?\s*:\s*\[?['"]([^'"]+)['"]/);
                    if (styleMatch) {
                        results.angular_component_styles.push({
                            component_name: className,
                            style_path: styleMatch[1]
                        });
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
        const injectableDecorator = classDecorators.find(d => d.decorator_name === 'Injectable');

        if (injectableDecorator) {
            const diDependencies = _extractAngularDI(cls, functionCallArgs);

            // ZERO FALLBACK: No nested dependencies array - use di_injections junction table
            results.services.push({
                name: className,
                line: cls.line,
                injectable: true,
                dependencies_count: diDependencies.length
            });

            // Flatten dependencies to di_injections junction array
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
        const ngModuleDecorator = classDecorators.find(d => d.decorator_name === 'NgModule');

        if (ngModuleDecorator) {
            // Parse module config from decorator args
            const decoratorArgsKey = `${className}|${ngModuleDecorator.decorator_index}`;
            const moduleArgs = classDecoratorArgsMap.get(decoratorArgsKey) || [];

            for (const arg of moduleArgs) {
                if (!arg.arg_value) continue;

                // Parse declarations from stringified config
                const declMatch = arg.arg_value.match(/declarations\s*:\s*\[([^\]]*)\]/);
                if (declMatch) {
                    const decls = declMatch[1].split(',').map(s => s.trim().replace(/['"]/g, '')).filter(Boolean);
                    for (const declName of decls) {
                        results.angular_module_declarations.push({
                            module_name: className,
                            declaration_name: declName,
                            declaration_type: _inferDeclarationType(declName)
                        });
                    }
                }

                // Parse imports from stringified config
                const importsMatch = arg.arg_value.match(/imports\s*:\s*\[([^\]]*)\]/);
                if (importsMatch) {
                    const imps = importsMatch[1].split(',').map(s => s.trim().replace(/['"]/g, '')).filter(Boolean);
                    for (const impName of imps) {
                        results.angular_module_imports.push({
                            module_name: className,
                            imported_module: impName
                        });
                    }
                }

                // Parse providers from stringified config
                const providersMatch = arg.arg_value.match(/providers\s*:\s*\[([^\]]*)\]/);
                if (providersMatch) {
                    const provs = providersMatch[1].split(',').map(s => s.trim().replace(/['"]/g, '')).filter(Boolean);
                    for (const provName of provs) {
                        results.angular_module_providers.push({
                            module_name: className,
                            provider_name: provName,
                            provider_type: _inferProviderType(provName)
                        });
                    }
                }

                // Parse exports from stringified config
                const exportsMatch = arg.arg_value.match(/exports\s*:\s*\[([^\]]*)\]/);
                if (exportsMatch) {
                    const exps = exportsMatch[1].split(',').map(s => s.trim().replace(/['"]/g, '')).filter(Boolean);
                    for (const expName of exps) {
                        results.angular_module_exports.push({
                            module_name: className,
                            exported_name: expName
                        });
                    }
                }
            }

            results.modules.push({
                name: className,
                line: cls.line
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
