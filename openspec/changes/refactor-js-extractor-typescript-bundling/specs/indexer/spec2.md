# Semantic Extraction Engine Rewrite Specification

> **Purpose:** This spec provides EXACT code examples of what is BROKEN, WHY it's broken, and the CORRECT replacement code. No ambiguity. No AI decisions. Copy-paste the correct patterns.

---

## 1. BROKEN: serializeNodeForCFG (DELETE ENTIRELY)

**Task Reference:** 3.1.2

**Location:** `theauditor/ast_extractors/javascript/core_language.js` lines 1-72

### WHY IT'S BROKEN

This function is a **Recursion Bomb**. It walks the ENTIRE AST (every token, comma, bracket) and builds a massive nested JSON object. When `batch_templates.js` calls `JSON.stringify()`, Node.js runs out of heap memory (512MB crash).

### BROKEN CODE (DO NOT COPY)

```javascript
// core_language.js lines 1-72 - THIS IS THE RECURSION BOMB
function serializeNodeForCFG(node, sourceFile, ts, depth = 0) {
  if (!node || depth > 100) return null;  // depth limit doesn't help - still crashes

  const serialized = {
    kind: ts.SyntaxKind[node.kind],
    start: node.getStart(),
    end: node.getEnd(),
    text: node.getText().substring(0, 200),
    children: []  // THIS IS THE PROBLEM - NESTED CHILDREN
  };

  ts.forEachChild(node, child => {
    const childSerialized = serializeNodeForCFG(child, sourceFile, ts, depth + 1);
    if (childSerialized) {
      serialized.children.push(childSerialized);  // BUILDS 5000-LEVEL DEEP TREE
    }
  });

  return serialized;
}
```

### CORRECT ACTION

**DELETE THE ENTIRE FUNCTION.** Do not convert it to TypeScript. Do not refactor it. Delete it.

```typescript
// core_language.ts - CORRECT
// serializeNodeForCFG DOES NOT EXIST
// We use flat extraction tables, not nested JSON trees
```

### VERIFICATION

Before deleting, verify `batch_templates.js` sets `ast: null`:

```javascript
// batch_templates.js line ~440
const result = {
  success: true,
  ast: null,  // MUST BE NULL - serializeNodeForCFG not called
  extracted_data: { ... }
};
```

---

## 2. BROKEN: extractClasses (REWRITE WITH TYPECHECKER)

**Task Reference:** 3.1.4

**Location:** `theauditor/ast_extractors/javascript/core_language.js` lines 381-616

### WHY IT'S BROKEN

Current code uses **text-based parsing** to read `node.heritageClauses`. This loses semantic information:
- Cannot resolve type aliases (`type A = B; class C extends A` - what is A?)
- Cannot see inherited members from parent classes
- Cannot handle re-exports or barrel files

### BROKEN CODE (DO NOT COPY)

```javascript
// core_language.js - BROKEN TEXT-BASED PARSING
function extractClasses(sourceFile, ts, filePath, scopeMap) {
  const classes = [];

  function traverse(node) {
    if (ts.isClassDeclaration(node)) {
      const classEntry = {
        name: node.name ? node.name.text : "Anonymous",
        line: sourceFile.getLineAndCharacterOfPosition(node.getStart()).line + 1,
        type: "class",
        // BROKEN: Text parsing loses semantic info
        extends_type: node.heritageClauses?.[0]?.types?.[0]?.expression?.getText() || null
      };
      classes.push(classEntry);
    }
    ts.forEachChild(node, traverse);
  }

  traverse(sourceFile);
  return { classes };
}
```

### CORRECT CODE (COPY THIS)

```typescript
// src/extractors/core_language.ts - CORRECT SEMANTIC EXTRACTION
import * as ts from 'typescript';

interface IClassMember {
  name: string;
  type: string;
  inherited: boolean;
}

interface IClass {
  name: string;
  line: number;
  column: number;
  type: "class";
  extends: string[];      // NEW: Resolved base types
  implements: string[];   // NEW: Interface contracts
  properties: IClassMember[];  // NEW: All members including inherited
  methods: IClassMember[];     // NEW: All methods including inherited
}

export function extractClasses(
  sourceFile: ts.SourceFile,
  checker: ts.TypeChecker,  // REQUIRED: TypeChecker for semantic analysis
  ts: typeof import('typescript'),
  filePath: string,
  scopeMap: Map<number, string>
): { classes: IClass[], class_decorators: any[], class_decorator_args: any[] } {
  const classes: IClass[] = [];

  function traverse(node: ts.Node): void {
    if (ts.isClassDeclaration(node) || ts.isClassExpression(node)) {
      const { line, character } = sourceFile.getLineAndCharacterOfPosition(node.getStart());

      // 1. Get the Symbol (The Identity)
      let symbol = node.name ? checker.getSymbolAtLocation(node.name) : undefined;

      // Fallback for ClassExpression assigned to variable
      if (!symbol && ts.isVariableDeclaration(node.parent)) {
        symbol = checker.getSymbolAtLocation(node.parent.name);
      }

      const classEntry: IClass = {
        name: symbol ? symbol.getName() : "AnonymousClass",
        line: line + 1,
        column: character,
        type: "class",
        extends: [],
        implements: [],
        properties: [],
        methods: []
      };

      if (symbol) {
        // 2. Get the Instance Type (The Shape)
        const instanceType = checker.getDeclaredTypeOfSymbol(symbol);

        // 3. Resolve Inheritance - THIS IS THE KEY DIFFERENCE
        const baseTypes = instanceType.getBaseTypes() || [];
        classEntry.extends = baseTypes.map(t => checker.typeToString(t));

        // 4. Get ALL Properties (including inherited!)
        const properties = instanceType.getProperties();

        for (const prop of properties) {
          const propName = prop.getName();
          if (propName.startsWith("__")) continue; // Skip internal

          const propType = checker.getTypeOfSymbolAtLocation(prop, node);
          const propTypeString = checker.typeToString(propType);

          // Check if method (has call signatures)
          const callSignatures = propType.getCallSignatures();

          if (callSignatures.length > 0) {
            classEntry.methods.push({
              name: propName,
              type: propTypeString,
              inherited: prop.parent !== symbol  // TRUE if from parent class
            });
          } else {
            classEntry.properties.push({
              name: propName,
              type: propTypeString,
              inherited: prop.parent !== symbol
            });
          }
        }
      }

      // 5. Resolve implements (syntax only)
      if (node.heritageClauses) {
        for (const clause of node.heritageClauses) {
          if (clause.token === ts.SyntaxKind.ImplementsKeyword) {
            classEntry.implements = clause.types.map(t => t.expression.getText());
          }
        }
      }

      classes.push(classEntry);
    }
    ts.forEachChild(node, traverse);
  }

  traverse(sourceFile);
  return { classes, class_decorators: [], class_decorator_args: [] };
}
```

### KEY DIFFERENCES

| Aspect | BROKEN (Text) | CORRECT (Semantic) |
|--------|---------------|-------------------|
| Get base class | `node.heritageClauses?.[0]?.getText()` | `instanceType.getBaseTypes()` |
| Resolve aliases | Cannot | `checker.typeToString(t)` resolves |
| Inherited members | Cannot see | `instanceType.getProperties()` includes all |
| Cross-file | Cannot | TypeChecker resolves imports |

---

## 3. BROKEN: extractCalls (REWRITE WITH TYPECHECKER)

**Task Reference:** 3.2.2

**Location:** `theauditor/ast_extractors/javascript/data_flow.js` lines 3-224

### WHY IT'S BROKEN

Current code uses `buildName()` to reconstruct function names from AST text. This creates the **Anonymous Caller Bug**:
- `db.User.findAll()` extracts as literal text "db.User.findAll"
- Cannot resolve that `db.User` is actually the `User` model from `./models`
- Downstream extractors (Sequelize, security) get garbage data

### BROKEN CODE (DO NOT COPY)

```javascript
// data_flow.js - BROKEN TEXT RECONSTRUCTION
function extractCalls(sourceFile, ts, filePath, functions, classes, scopeMap) {
  const calls = [];

  function traverse(node) {
    if (ts.isCallExpression(node)) {
      const { line } = sourceFile.getLineAndCharacterOfPosition(node.getStart());

      // BROKEN: buildName just concatenates text
      const calleeName = buildName(node.expression, ts);  // Returns "db.User.findAll"

      calls.push({
        line: line + 1,
        name: calleeName,  // GARBAGE - just text, no semantic meaning
        caller_function: getScopeFromMap(scopeMap, line)
      });
    }
    ts.forEachChild(node, traverse);
  }

  traverse(sourceFile);
  return calls;
}

// BROKEN: This just reads text, doesn't resolve symbols
function buildName(node, ts) {
  if (ts.isIdentifier(node)) {
    return node.text;
  }
  if (ts.isPropertyAccessExpression(node)) {
    return buildName(node.expression, ts) + "." + node.name.text;
  }
  return "unknown";
}
```

### CORRECT CODE (COPY THIS)

```typescript
// src/extractors/data_flow.ts - CORRECT SEMANTIC RESOLUTION
import * as ts from 'typescript';

interface ICallSymbol {
  line: number;
  column: number;
  name: string;           // Resolved: "User.findAll" or "sequelize.Model.findAll"
  original_text: string;  // Raw: "db.User.findAll" (for debugging)
  defined_in: string | null;  // File path where function is defined
  caller_function: string;
  arguments: string[];
}

export function extractCalls(
  sourceFile: ts.SourceFile,
  checker: ts.TypeChecker,  // REQUIRED: TypeChecker for symbol resolution
  ts: typeof import('typescript'),
  filePath: string,
  functions: any[],
  classes: any[],
  scopeMap: Map<number, string>
): ICallSymbol[] {
  const calls: ICallSymbol[] = [];

  function traverse(node: ts.Node): void {
    if (ts.isCallExpression(node)) {
      const { line, character } = sourceFile.getLineAndCharacterOfPosition(node.getStart());

      // 1. Get the Symbol (The Semantic Identity)
      let symbol = checker.getSymbolAtLocation(node.expression);

      // Handle property access: foo.bar.baz()
      if (!symbol && ts.isPropertyAccessExpression(node.expression)) {
        symbol = checker.getSymbolAtLocation(node.expression.name);
      }

      let resolvedName = "unknown";
      let definedIn: string | null = null;

      if (symbol) {
        // 2. Get Fully Qualified Name - THIS IS THE KEY
        resolvedName = checker.getFullyQualifiedName(symbol);

        // 3. Find where the function is defined
        const declarations = symbol.getDeclarations();
        if (declarations && declarations.length > 0) {
          const declSourceFile = declarations[0].getSourceFile();
          definedIn = declSourceFile.fileName;
        }
      } else {
        // Fallback to text only if semantic analysis fails completely
        resolvedName = node.expression.getText();
      }

      // 4. Extract arguments as text (safe for now)
      const args = node.arguments.map(arg => arg.getText());

      calls.push({
        line: line + 1,
        column: character,
        name: resolvedName,           // "User.findAll" (resolved!)
        original_text: node.expression.getText(),  // "db.users.findAll" (raw)
        defined_in: definedIn,        // "/models/User.ts"
        caller_function: scopeMap.get(line) || "<module>",
        arguments: args
      });
    }
    ts.forEachChild(node, traverse);
  }

  traverse(sourceFile);
  return calls;
}
```

### KEY DIFFERENCES

| Aspect | BROKEN (Text) | CORRECT (Semantic) |
|--------|---------------|-------------------|
| Get callee name | `buildName()` concatenates text | `checker.getFullyQualifiedName(symbol)` |
| Resolve imports | Cannot - sees "db" not "User" | Resolves through imports |
| Find definition | Cannot | `symbol.getDeclarations()[0].getSourceFile()` |
| Aliased calls | Wrong name | Correct resolved name |

---

## 4. BROKEN: CFG visit function (OPTIMIZE)

**Task Reference:** 3.9.2

**Location:** `theauditor/ast_extractors/javascript/cfg_extractor.js` lines 458-497

### WHY IT'S BROKEN

Current `visit()` function traverses EVERY node including:
- `InterfaceDeclaration` - not executable code
- `TypeAliasDeclaration` - not executable code
- `ImportDeclaration` - not executable code
- Deeply nested JSX - creates thousands of useless CFG blocks

This wastes ~40% memory on TypeScript projects and causes stack overflow on React files.

### BROKEN CODE (DO NOT COPY)

```javascript
// cfg_extractor.js - BROKEN: VISITS EVERYTHING
function visit(node, depth = 0, parent = null) {
  if (depth > 500 || !node) return;

  const kind = ts.SyntaxKind[node.kind];

  // BROKEN: No filtering - visits Interfaces, Types, Imports
  if (kind === "FunctionDeclaration" || kind === "ArrowFunction" /* etc */) {
    const cfg = buildFunctionCFG(node, class_stack, parent);
    if (cfg) functionCFGs.push(cfg);
  }

  // BROKEN: Recurses into EVERYTHING
  ts.forEachChild(node, (child) => visit(child, depth + 1, node));
}

// Inside processNode - BROKEN JSX handling
} else if (kind.startsWith("Jsx")) {
  // BROKEN: Creates CFG block for EVERY JSX element
  addStatementToBlock(currentId, kind, line + 1, node.getText().substring(0, 100));
  ts.forEachChild(node, (child) => {
    lastId = processNode(child, lastId, depth + 1);  // RECURSION EXPLOSION
  });
}
```

### CORRECT CODE (COPY THIS)

```typescript
// src/extractors/cfg_extractor.ts - CORRECT: SMART TRAVERSAL

function visit(node: ts.Node, depth: number = 0, parent: ts.Node | null = null): void {
  if (depth > 500 || !node) return;

  const kind = ts.SyntaxKind[node.kind];

  // OPTIMIZATION 1: SKIP NON-EXECUTABLE CODE
  // CFG only cares about executable code, not type definitions
  if (
    kind === "InterfaceDeclaration" ||
    kind === "TypeAliasDeclaration" ||
    kind === "ImportDeclaration" ||
    kind === "ModuleDeclaration"
  ) {
    return;  // DO NOT TRAVERSE - these have no control flow
  }

  // CAPTURE FUNCTIONS
  if (
    kind === "FunctionDeclaration" ||
    kind === "MethodDeclaration" ||
    kind === "ArrowFunction" ||
    kind === "FunctionExpression" ||
    kind === "Constructor" ||
    kind === "GetAccessor" ||
    kind === "SetAccessor"
  ) {
    const cfg = buildFunctionCFG(node, class_stack, parent);
    if (cfg) functionCFGs.push(cfg);
    return;  // buildFunctionCFG already walked the body
  }

  // TRACK CLASS CONTEXT
  if (kind === "ClassDeclaration" || kind === "ClassExpression") {
    const className = node.name?.text || node.name?.escapedText || "UnknownClass";
    class_stack.push(className);
    ts.forEachChild(node, (child) => visit(child, depth + 1, node));
    class_stack.pop();
    return;
  }

  // HANDLE PROPERTY INITIALIZERS (arrow functions in class properties)
  if (kind === "PropertyDeclaration" && node.initializer) {
    const initKind = ts.SyntaxKind[node.initializer.kind];
    if (initKind === "ArrowFunction" || initKind === "FunctionExpression") {
      const cfg = buildFunctionCFG(node.initializer, class_stack, node);
      if (cfg) functionCFGs.push(cfg);
      return;
    }
  }

  // Continue searching for functions in other nodes
  ts.forEachChild(node, (child) => visit(child, depth + 1, node));
}

// OPTIMIZATION 2: FLATTEN JSX
// Inside processNode:
} else if (kind.startsWith("Jsx")) {
  // Only add CFG statement for ROOT of JSX tree
  const parentKind = node.parent ? ts.SyntaxKind[node.parent.kind] : "";
  if (!parentKind.startsWith("Jsx")) {
    // This is the outermost JSX element
    addStatementToBlock(currentId, "jsx_root", line + 1, "<JSX>");
  }
  // DO NOT add statements for child JSX elements

  // Continue traversing to find embedded functions (onClick handlers)
  let lastId = currentId;
  ts.forEachChild(node, (child) => {
    const childKind = ts.SyntaxKind[child.kind];
    // Only care about embedded code, not JSX structure
    if (childKind === "ArrowFunction" || childKind === "FunctionExpression" || childKind === "JsxExpression") {
      lastId = processNode(child, lastId, depth + 1);
    }
  });
  return lastId;
}
```

### KEY DIFFERENCES

| Aspect | BROKEN | CORRECT |
|--------|--------|---------|
| Interface/Types | Traversed (waste) | Skipped immediately |
| JSX elements | Block per element | Single `jsx_root` statement |
| Memory usage | 100% | ~60% (40% reduction) |
| Stack overflow | On deep JSX | Prevented |

---

## 5. BROKEN: Python Zombie Methods (DELETE)

**Task Reference:** 5.3.1, 5.3.2, 5.3.3, 5.3.4, 5.3.5

**Location:** `theauditor/indexer/extractors/javascript.py`

### WHY IT'S BROKEN

Python layer has **600+ lines of "fallback" extraction** that duplicates JS logic. This creates "Double Vision" - two extraction engines fighting each other. If data is wrong, you don't know which engine produced it.

### BROKEN CODE (DO NOT COPY)

```python
# javascript.py - ZOMBIE METHODS (DELETE ALL OF THESE)

class JavaScriptExtractor(BaseExtractor):

    def extract(self, file_info, content, tree):
        result = { ... }

        if isinstance(tree, dict) and "extracted_data" in tree:
            data = tree["extracted_data"]
            result["routes"] = data.get("routes", [])

        # BROKEN: Fallback that fights with JS
        if not result.get("routes"):
            result["routes"] = self._extract_routes_from_ast(tree)  # ZOMBIE

        if not result.get("sql_queries"):
            result["sql_queries"] = self._extract_sql_from_function_calls(tree)  # ZOMBIE

        return result

    # ZOMBIE METHOD - DELETE
    def _extract_sql_from_function_calls(self, tree):
        """~100 lines of duplicate SQL extraction logic"""
        # This duplicates extractSQLQueries in security_extractors.js
        pass

    # ZOMBIE METHOD - DELETE
    def _extract_jwt_from_function_calls(self, tree):
        """~80 lines of duplicate JWT extraction logic"""
        pass

    # ZOMBIE METHOD - DELETE
    def _extract_routes_from_ast(self, tree):
        """~200 lines of duplicate route extraction logic"""
        # This duplicates extractAPIEndpoints in security_extractors.js
        pass
```

### CORRECT CODE (COPY THIS)

```python
# javascript.py - CORRECT: TRUST JS, NO FALLBACKS

class JavaScriptExtractor(BaseExtractor):

    def extract(self, file_info: dict, content: str, tree: Any) -> dict:
        result = self._init_result()

        # ONLY read from JS output - NO FALLBACKS
        if isinstance(tree, dict) and "extracted_data" in tree:
            data = tree["extracted_data"]

            # Map directly. No logic. No fallbacks.
            result["routes"] = data.get("routes", [])
            result["sql_queries"] = data.get("sql_queries", [])
            result["jwt_patterns"] = data.get("jwt_patterns", [])
            result["function_calls"] = data.get("function_call_args", [])
            result["classes"] = data.get("classes", [])
            result["functions"] = data.get("functions", [])
            # ... map all other fields ...

        # NO FALLBACK. If data is missing, the bug is in JS.
        # DO NOT write: if not result.get("routes"): ...

        return result

    # _extract_sql_from_function_calls - DELETED
    # _extract_jwt_from_function_calls - DELETED
    # _extract_routes_from_ast - DELETED
```

### VERIFICATION AFTER DELETION

1. Run `aud full --index` on test fixtures
2. If ANY data is missing, FIX THE JAVASCRIPT EXTRACTOR
3. Do NOT add Python workarounds

---

## 6. CORRECT: javascript_resolvers.py (KEEP UNCHANGED)

**Task Reference:** 5.3.7

**Location:** `theauditor/indexer/extractors/javascript_resolvers.py`

### WHY IT'S CORRECT (DO NOT MODIFY)

This file is the **cross-file linker layer**. It runs AFTER extraction and uses SQL to connect dots that are impossible to see in a single file.

**Architecture:**
1. JavaScript (Eyes): "I see syntax in this one file"
2. SQLite (Memory): Stores raw facts from all files
3. Python Resolvers (Brain): "I connect dots using SQL JOINs"

### CORRECT PATTERN (REFERENCE ONLY)

```python
# javascript_resolvers.py - THIS IS CORRECT ARCHITECTURE

def resolve_cross_file_parameters(db_path: str, debug: bool = False):
    """
    CORRECT: Uses SQL to connect function calls to definitions.

    JavaScript extracted: arg0, arg1 (no param names - single file can't see definition)
    This resolver: JOINs function_call_args with symbols to get real param names
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # SQL-based resolution - NOT AST traversal
    cursor.execute("""
        SELECT fca.id, s.name, fp.param_name
        FROM function_call_args fca
        JOIN symbols s ON fca.callee_function = s.name
        JOIN func_params fp ON s.id = fp.function_id
        WHERE fca.param_name IS NULL
    """)

    # Update with resolved names
    for row in cursor.fetchall():
        cursor.execute(
            "UPDATE function_call_args SET param_name = ? WHERE id = ?",
            (row[2], row[0])
        )

    conn.commit()
    conn.close()
```

### RULE

**If `javascript_resolvers.py` fails, FIX THE JAVASCRIPT EXTRACTION THAT FEEDS IT.**

Do NOT add Python extraction logic to this file. It consumes data from SQLite, it does not parse code.

---

## 7. BROKEN: buildScopeMap (CONSIDER REPLACING)

**Task Reference:** 3.1.6

**Location:** `theauditor/ast_extractors/javascript/core_language.js` lines 711-871

### WHY IT'S FRAGILE

Current `buildScopeMap` maps `Line Number -> Function Name`. This is brittle:
- Arrow functions on same line: `const a = () => null; const b = () => null;`
- Decorators offset line numbers
- SourceMaps further complicate

### BROKEN PATTERN

```javascript
// core_language.js - FRAGILE LINE-BASED SCOPE
function buildScopeMap(sourceFile, ts) {
  const scopeMap = new Map();

  function traverse(node) {
    if (ts.isFunctionDeclaration(node)) {
      const line = sourceFile.getLineAndCharacterOfPosition(node.getStart()).line;
      scopeMap.set(line, node.name?.text || "anonymous");
    }
    ts.forEachChild(node, traverse);
  }

  traverse(sourceFile);
  return scopeMap;
}
```

### CORRECT PATTERN (USE TYPECHECKER)

```typescript
// src/extractors/core_language.ts - SEMANTIC SCOPE CHAIN
export function getScopeChain(
  node: ts.Node,
  checker: ts.TypeChecker
): string {
  const chain: string[] = [];
  let current: ts.Node | undefined = node;

  while (current) {
    if (ts.isFunctionLike(current) || ts.isClassDeclaration(current)) {
      const sym = current.name ? checker.getSymbolAtLocation(current.name) : null;
      if (sym) chain.push(sym.getName());
    }
    current = current.parent;
  }

  return chain.reverse().join(".");  // "UserController.login.validate"
}
```

---

## 8. OUTPUT FORMAT CHANGES

### Class Output (Before vs After)

**BEFORE (Text-based):**
```json
{
  "name": "UserController",
  "line": 10,
  "type": "class",
  "extends_type": "BaseController"
}
```

**AFTER (Semantic):**
```json
{
  "name": "UserController",
  "line": 10,
  "column": 0,
  "type": "class",
  "extends": ["BaseController"],
  "implements": ["IController"],
  "properties": [
    { "name": "db", "type": "Database", "inherited": true },
    { "name": "logger", "type": "Logger", "inherited": true },
    { "name": "userRepo", "type": "UserRepository", "inherited": false }
  ],
  "methods": [
    { "name": "getUser", "type": "(id: string) => Promise<User>", "inherited": false },
    { "name": "init", "type": "() => void", "inherited": true }
  ]
}
```

### Call Output (Before vs After)

**BEFORE (Text-based):**
```json
{
  "line": 25,
  "name": "db.users.findAll",
  "caller_function": "getUsers"
}
```

**AFTER (Semantic):**
```json
{
  "line": 25,
  "column": 4,
  "name": "User.findAll",
  "original_text": "db.users.findAll",
  "defined_in": "/models/User.ts",
  "caller_function": "getUsers",
  "arguments": ["{ where: { active: true } }"]
}
```

---

## 9. MANDATORY CHECKLIST

Before marking ANY task complete:

- [ ] `serializeNodeForCFG` is DELETED (not converted, DELETED)
- [ ] `extractClasses` uses `checker.getDeclaredTypeOfSymbol()`
- [ ] `extractClasses` returns `extends[]`, `implements[]`, `properties[]`, `methods[]`
- [ ] `extractCalls` uses `checker.getSymbolAtLocation()` and `checker.getFullyQualifiedName()`
- [ ] `extractCalls` returns `name`, `original_text`, `defined_in`
- [ ] CFG `visit()` skips InterfaceDeclaration, TypeAliasDeclaration, ImportDeclaration, ModuleDeclaration
- [ ] CFG JSX handling only creates ONE `jsx_root` statement per JSX tree
- [ ] `javascript.py` has NO `_extract_sql...`, `_extract_jwt...`, `_extract_routes...` methods
- [ ] `javascript.py` `extract()` has NO fallback blocks
- [ ] `javascript_resolvers.py` is UNCHANGED

---

## 10. DOWNSTREAM IMPACT WARNING

When `extractCalls` returns semantic names (e.g., `sequelize.Model.init` instead of `User.init`), downstream extractors may need updates:

### Check These Files After Migration

1. `sequelize_extractors.js` - String matching on `callee_function`
2. `security_extractors.js` - Pattern matching for SQL/JWT
3. `framework_extractors.js` - React/Vue component detection

### How to Fix

```javascript
// BEFORE: Matches exact text
if (call.callee_function.includes(".init") && call.callee_function.includes(modelName))

// AFTER: May need to match resolved name
if (call.callee_function.endsWith(".init") || call.callee_function.includes("Model.init"))

// OR: Use original_text for pattern matching, name for resolution
if (call.original_text.includes(".init")) {
  // Pattern matched - use call.name for the resolved identity
}
```

---

## Summary

| Component | Action | Risk |
|-----------|--------|------|
| `serializeNodeForCFG` | DELETE | None - legacy code |
| `extractClasses` | REWRITE with TypeChecker | HIGH - core logic |
| `extractCalls` | REWRITE with TypeChecker | HIGH - core logic |
| CFG `visit()` | OPTIMIZE - skip types | MEDIUM - performance |
| CFG JSX | FLATTEN - single statement | MEDIUM - performance |
| Python zombies | DELETE all | MEDIUM - exposes JS gaps |
| `javascript_resolvers.py` | KEEP unchanged | None |

**This is not a refactor. This is an engine rewrite.**
