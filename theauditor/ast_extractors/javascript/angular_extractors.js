function _inferDeclarationType(decl) {
  const name = typeof decl === "string" ? decl : (decl && decl.name) || "";
  if (name.endsWith("Component")) return "component";
  if (name.endsWith("Directive")) return "directive";
  if (name.endsWith("Pipe")) return "pipe";
  return null;
}

function _inferProviderType(prov) {
  if (typeof prov === "string") return "class";
  if (!prov || typeof prov !== "object") return null;
  if (prov.useValue !== undefined) return "value";
  if (prov.useFactory !== undefined) return "factory";
  if (prov.useClass !== undefined) return "class";
  if (prov.useExisting !== undefined) return "existing";
  return null;
}

function extractAngularComponents(
  functions,
  classes,
  imports,
  functionCallArgs,
  func_decorators,
  class_decorators,
  class_decorator_args,
) {
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
    angular_module_exports: [],
  };

  const hasAngular =
    imports &&
    imports.some(
      (imp) =>
        imp.module === "@angular/core" ||
        imp.module === "@angular/common" ||
        imp.module === "@angular/router",
    );

  if (!hasAngular) {
    return results;
  }

  const classDecoratorMap = new Map();
  for (const dec of class_decorators || []) {
    if (!classDecoratorMap.has(dec.class_name)) {
      classDecoratorMap.set(dec.class_name, []);
    }
    classDecoratorMap.get(dec.class_name).push(dec);
  }

  const classDecoratorArgsMap = new Map();
  for (const arg of class_decorator_args || []) {
    const key = `${arg.class_name}|${arg.decorator_index}`;
    if (!classDecoratorArgsMap.has(key)) {
      classDecoratorArgsMap.set(key, []);
    }
    classDecoratorArgsMap.get(key).push(arg);
  }

  const funcDecoratorMap = new Map();
  for (const dec of func_decorators || []) {
    const key = `${dec.function_name}`;
    if (!funcDecoratorMap.has(key)) {
      funcDecoratorMap.set(key, []);
    }
    funcDecoratorMap.get(key).push(dec);
  }

  for (const cls of classes) {
    const className = cls.name;
    if (!className) continue;

    const classDecorators = classDecoratorMap.get(className) || [];

    const componentDecorator = classDecorators.find(
      (d) => d.decorator_name === "Component",
    );

    if (componentDecorator) {
      const inputs = [];
      const outputs = [];

      if (functions) {
        for (const func of functions) {
          if (func.parent_class === className) {
            const funcDecs = funcDecoratorMap.get(func.name) || [];
            for (const decorator of funcDecs) {
              if (decorator.decorator_name === "Input") {
                inputs.push({ name: func.name, line: func.line });
              } else if (decorator.decorator_name === "Output") {
                outputs.push({ name: func.name, line: func.line });
              }
            }
          }
        }
      }

      const decoratorArgsKey = `${className}|${componentDecorator.decorator_index}`;
      const componentArgs = classDecoratorArgsMap.get(decoratorArgsKey) || [];
      for (const arg of componentArgs) {
        if (arg.arg_value) {
          const styleMatch = arg.arg_value.match(
            /styleUrls?\s*:\s*\[?['"]([^'"]+)['"]/,
          );
          if (styleMatch) {
            results.angular_component_styles.push({
              component_name: className,
              style_path: styleMatch[1],
            });
          }
        }
      }

      results.components.push({
        name: className,
        line: cls.line,
        inputs_count: inputs.length,
        outputs_count: outputs.length,
        has_lifecycle_hooks: _detectAngularLifecycleHooks(cls, functions),
      });

      const dependencies = _extractAngularDI(cls, functionCallArgs);
      for (const dep of dependencies) {
        results.di_injections.push({
          line: cls.line,
          target_class: className,
          service: dep.service,
          injection_type: "constructor",
        });
      }
    }

    const injectableDecorator = classDecorators.find(
      (d) => d.decorator_name === "Injectable",
    );

    if (injectableDecorator) {
      const diDependencies = _extractAngularDI(cls, functionCallArgs);

      results.services.push({
        name: className,
        line: cls.line,
        injectable: true,
        dependencies_count: diDependencies.length,
      });

      for (const dep of diDependencies) {
        results.di_injections.push({
          line: cls.line,
          target_class: className,
          service: dep.service,
          injection_type: "constructor",
        });
      }
    }

    const ngModuleDecorator = classDecorators.find(
      (d) => d.decorator_name === "NgModule",
    );

    if (ngModuleDecorator) {
      const decoratorArgsKey = `${className}|${ngModuleDecorator.decorator_index}`;
      const moduleArgs = classDecoratorArgsMap.get(decoratorArgsKey) || [];

      for (const arg of moduleArgs) {
        if (!arg.arg_value) continue;

        const declMatch = arg.arg_value.match(
          /declarations\s*:\s*\[([^\]]*)\]/,
        );
        if (declMatch) {
          const decls = declMatch[1]
            .split(",")
            .map((s) => s.trim().replace(/['"]/g, ""))
            .filter(Boolean);
          for (const declName of decls) {
            results.angular_module_declarations.push({
              module_name: className,
              declaration_name: declName,
              declaration_type: _inferDeclarationType(declName),
            });
          }
        }

        const importsMatch = arg.arg_value.match(/imports\s*:\s*\[([^\]]*)\]/);
        if (importsMatch) {
          const imps = importsMatch[1]
            .split(",")
            .map((s) => s.trim().replace(/['"]/g, ""))
            .filter(Boolean);
          for (const impName of imps) {
            results.angular_module_imports.push({
              module_name: className,
              imported_module: impName,
            });
          }
        }

        const providersMatch = arg.arg_value.match(
          /providers\s*:\s*\[([^\]]*)\]/,
        );
        if (providersMatch) {
          const provs = providersMatch[1]
            .split(",")
            .map((s) => s.trim().replace(/['"]/g, ""))
            .filter(Boolean);
          for (const provName of provs) {
            results.angular_module_providers.push({
              module_name: className,
              provider_name: provName,
              provider_type: _inferProviderType(provName),
            });
          }
        }

        const exportsMatch = arg.arg_value.match(/exports\s*:\s*\[([^\]]*)\]/);
        if (exportsMatch) {
          const exps = exportsMatch[1]
            .split(",")
            .map((s) => s.trim().replace(/['"]/g, ""))
            .filter(Boolean);
          for (const expName of exps) {
            results.angular_module_exports.push({
              module_name: className,
              exported_name: expName,
            });
          }
        }
      }

      results.modules.push({
        name: className,
        line: cls.line,
      });
    }

    if (className.includes("Guard")) {
      const implementsGuard =
        cls.implements_types &&
        (cls.implements_types.includes("CanActivate") ||
          cls.implements_types.includes("CanDeactivate") ||
          cls.implements_types.includes("CanLoad"));

      if (implementsGuard) {
        results.guards.push({
          name: className,
          line: cls.line,
          guard_type: _detectGuardType(cls),
        });
      }
    }
  }

  return results;
}

function _detectAngularLifecycleHooks(cls, functions) {
  const lifecycleHooks = [
    "ngOnInit",
    "ngOnDestroy",
    "ngOnChanges",
    "ngAfterViewInit",
    "ngDoCheck",
  ];

  for (const func of functions) {
    if (func.parent_class === cls.name && lifecycleHooks.includes(func.name)) {
      return true;
    }
  }

  return false;
}

function _extractAngularDI(cls, functionCallArgs) {
  const dependencies = [];

  for (const call of functionCallArgs) {
    if (call.caller_class === cls.name) {
      const commonServices = [
        "http",
        "HttpClient",
        "Router",
        "ActivatedRoute",
        "FormBuilder",
        "AuthService",
        "UserService",
        "DataService",
        "ApiService",
      ];

      for (const service of commonServices) {
        if (
          call.callee_function &&
          call.callee_function.toLowerCase().includes(service.toLowerCase())
        ) {
          dependencies.push({ service: service });
          break;
        }
      }
    }
  }

  return dependencies;
}

function _detectGuardType(cls) {
  if (!cls.implements_types) return "unknown";

  if (cls.implements_types.includes("CanActivate")) return "CanActivate";
  if (cls.implements_types.includes("CanDeactivate")) return "CanDeactivate";
  if (cls.implements_types.includes("CanLoad")) return "CanLoad";

  return "unknown";
}
