import * as ts from "typescript";
import type {
  AngularComponent,
  AngularModule,
  AngularService,
  AngularGuard,
  Class as IClass,
  FuncDecorator as IFuncDecorator,
  ClassDecorator as IClassDecorator,
  ClassDecoratorArg as IClassDecoratorArg,
} from "../schema.js";

interface ExtractAngularResult {
  angular_components: AngularComponent[];
  angular_modules: AngularModule[];
  angular_services: AngularService[];
  angular_guards: AngularGuard[];
}

const ANGULAR_LIFECYCLE_HOOKS = new Set([
  "ngOnInit",
  "ngOnDestroy",
  "ngOnChanges",
  "ngDoCheck",
  "ngAfterContentInit",
  "ngAfterContentChecked",
  "ngAfterViewInit",
  "ngAfterViewChecked",
]);

export function extractAngularDefinitions(
  classes: IClass[],
  class_decorators: IClassDecorator[],
  class_decorator_args: IClassDecoratorArg[],
  sourceFile: ts.SourceFile,
  filePath: string,
): ExtractAngularResult {
  const angular_components: AngularComponent[] = [];
  const angular_modules: AngularModule[] = [];
  const angular_services: AngularService[] = [];
  const angular_guards: AngularGuard[] = [];

  for (const cls of classes) {
    const clsDecorators = class_decorators.filter(
      (d) => d.class_name === cls.name && d.class_line === cls.line,
    );

    for (const decorator of clsDecorators) {
      const decoratorName = decorator.decorator_name;
      const decoratorArgs = class_decorator_args.filter(
        (a) =>
          a.class_name === cls.name &&
          a.class_line === cls.line &&
          a.decorator_index === decorator.decorator_index,
      );

      if (decoratorName === "Component") {
        let selector: string | null = null;
        let templatePath: string | null = null;

        for (const arg of decoratorArgs) {
          const argValue = arg.arg_value;
          if (argValue.includes(":")) {
            const [key, value] = argValue
              .split(":")
              .map((s: string) => s.trim());
            if (key === "selector") {
              selector = value.replace(/['"]/g, "");
            } else if (key === "templateUrl") {
              templatePath = value.replace(/['"]/g, "");
            }
          }
        }

        const hasLifecycleHooks = checkForLifecycleHooks(sourceFile, cls.name);

        angular_components.push({
          file: filePath,
          line: cls.line,
          component_name: cls.name,
          selector: selector,
          template_path: templatePath,
          has_lifecycle_hooks: hasLifecycleHooks,
        });
      } else if (decoratorName === "NgModule") {
        angular_modules.push({
          file: filePath,
          line: cls.line,
          module_name: cls.name,
        });
      } else if (decoratorName === "Injectable") {
        let providedIn: string | null = null;

        for (const arg of decoratorArgs) {
          const argValue = arg.arg_value;
          if (argValue.includes("providedIn")) {
            const match = argValue.match(/providedIn\s*:\s*['"]?(\w+)['"]?/);
            if (match) {
              providedIn = match[1];
            }
          }
        }

        angular_services.push({
          file: filePath,
          line: cls.line,
          service_name: cls.name,
          provided_in: providedIn,
        });
      }
    }

    const guardTypes = extractGuardTypes(sourceFile, cls.name);
    if (guardTypes.length > 0) {
      angular_guards.push({
        file: filePath,
        line: cls.line,
        guard_name: cls.name,
        guard_type: guardTypes.join(","),
      });
    }
  }

  return {
    angular_components,
    angular_modules,
    angular_services,
    angular_guards,
  };
}

function checkForLifecycleHooks(
  sourceFile: ts.SourceFile,
  className: string,
): boolean {
  let hasLifecycleHooks = false;

  function visit(node: ts.Node): void {
    if (
      ts.isClassDeclaration(node) &&
      node.name &&
      node.name.text === className
    ) {
      for (const member of node.members) {
        if (
          ts.isMethodDeclaration(member) &&
          member.name &&
          ts.isIdentifier(member.name)
        ) {
          if (ANGULAR_LIFECYCLE_HOOKS.has(member.name.text)) {
            hasLifecycleHooks = true;
            return;
          }
        }
      }
    }
    ts.forEachChild(node, visit);
  }

  visit(sourceFile);
  return hasLifecycleHooks;
}

function extractGuardTypes(
  sourceFile: ts.SourceFile,
  className: string,
): string[] {
  const guardTypes: string[] = [];
  const GUARD_INTERFACES = new Set([
    "CanActivate",
    "CanActivateChild",
    "CanDeactivate",
    "CanLoad",
    "Resolve",
  ]);

  function visit(node: ts.Node): void {
    if (
      ts.isClassDeclaration(node) &&
      node.name &&
      node.name.text === className
    ) {
      if (node.heritageClauses) {
        for (const clause of node.heritageClauses) {
          if (clause.token === ts.SyntaxKind.ImplementsKeyword) {
            for (const type of clause.types) {
              const typeName = type.expression.getText(sourceFile);
              if (GUARD_INTERFACES.has(typeName)) {
                guardTypes.push(typeName);
              }
            }
          }
        }
      }
    }
    ts.forEachChild(node, visit);
  }

  visit(sourceFile);
  return guardTypes;
}

export { ExtractAngularResult };
