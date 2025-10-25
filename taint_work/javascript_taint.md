# JavaScript Extraction System - Complete Analysis

**Last Updated**: 2025-10-26
**Purpose**: Document EXACTLY what data is extracted from JavaScript/TypeScript files and how it flows into the database.

---

## Architecture Overview

### Orchestrator: `js_helper_templates.py`

**Role**: Python-side coordinator that assembles and executes JavaScript extraction scripts.

**Assembly Process** (Lines 133-196):
```python
def get_batch_helper(module_type: Literal["module", "commonjs"]) -> str:
    # Load JavaScript modules from disk (cached after first call)
    if _JS_CACHE['core_ast_extractors'] is None:
        _load_javascript_modules()

    # Assembly order (CRITICAL - defines dependency chain):
    assembled_script = (
        _JS_CACHE['core_ast_extractors'] +      # Foundation layer
        '\n\n' +
        _JS_CACHE['security_extractors'] +      # SAST patterns
        '\n\n' +
        _JS_CACHE['framework_extractors'] +     # React/Vue/Angular
        '\n\n' +
        _JS_CACHE['cfg_extractor'] +            # Control flow graphs
        '\n\n' +
        batch_template                          # Main orchestration
    )

    return assembled_script
```

**Data Flow**:
1. Python creates batch request JSON with file paths
2. Python assembles complete JavaScript script (concatenates 5 modules)
3. Python writes script to temp file (`.mjs` or `.cjs`)
4. Python spawns Node.js subprocess: `node script.mjs request.json output.json`
5. JavaScript extracts ALL data and writes to `output.json`
6. Python reads `output.json` and inserts into SQLite database

---

## Core Extractors (`core_ast_extractors.js`)

**Foundation layer** - 2,173 lines of TypeScript AST traversal.

### 1. **extractImports** (Lines 49-139)

**Purpose**: Track module dependencies and external code references.

**Schema**:
```javascript
{
    kind: 'import' | 'require' | 'dynamic_import',
    module: string,              // 'react', './utils', '@/services/api'
    line: number,
    specifiers: [                // What's being imported
        {
            name: string,        // 'useState', 'default', 'UserService'
            isDefault: boolean,
            isNamed: boolean,
            isNamespace: boolean
        }
    ]
}
```

**Database Table**: `imports` (symbol_manager.py)
- Columns: `file, line, module, specifiers, kind`

**Examples**:
```javascript
// ES6 named import
import { useState, useEffect } from 'react';
// → kind='import', module='react', specifiers=[{name: 'useState', isNamed: true}, {name: 'useEffect', isNamed: true}]

// Default import
import React from 'react';
// → kind='import', module='react', specifiers=[{name: 'React', isDefault: true}]

// Namespace import
import * as fs from 'fs';
// → kind='import', module='fs', specifiers=[{name: 'fs', isNamespace: true}]

// CommonJS require
const path = require('path');
// → kind='require', module='path', specifiers=[]

// Dynamic import
const module = await import('./dynamic');
// → kind='dynamic_import', module='./dynamic', specifiers=[]
```

---

### 2. **extractFunctions** (Lines 224-371)

**Purpose**: Extract function metadata with TypeScript type annotations for inter-procedural analysis.

**Schema**:
```javascript
{
    line: number,
    col: number,
    column: number,              // Duplicate for compatibility
    kind: string,                // 'FunctionDeclaration', 'MethodDeclaration', etc.
    name: string,                // 'getUserById', 'UserController.create'
    type: 'function',
    parameters: string[],        // ['req', 'res', 'next'] - CRITICAL for taint tracking
    type_annotation: string,     // Full TypeScript signature
    is_any: boolean,             // Uses 'any' type
    is_unknown: boolean,         // Uses 'unknown' type
    is_generic: boolean,         // Generic function
    return_type: string,         // Return type string
    extends_type: string         // For methods: base class
}
```

**Database Table**: `symbols` (type='function')
- Columns: `file, line, name, type, parameters, type_annotation, return_type`

**Critical Feature**: **Real parameter names** (Lines 290-313)
- Enables multi-hop taint tracking: `function createUser(data, _createdBy)` → tracks actual param names, not `arg0, arg1`
- Handles destructuring: `({ id, name }) → 'destructured'`
- Used by `extractFunctionCallArgs` to map arguments to parameter names

**Examples**:
```javascript
// Function declaration
function getUserById(id: string): Promise<User> { }
// → name='getUserById', parameters=['id'], return_type='Promise<User>'

// Class method
class UserService {
    async createUser(data: UserInput, _createdBy: string) { }
}
// → name='UserService.createUser', parameters=['data', '_createdBy']

// Arrow function property
class Controller {
    list = async (req: Request, res: Response) => { };
}
// → name='Controller.list', parameters=['req', 'res']

// Constructor
class User {
    constructor(id: number, name: string) { }
}
// → name='User.constructor', parameters=['id', 'name']
```

---

### 3. **extractClasses** (Lines 381-535)

**Purpose**: Extract class declarations (NOT interfaces/types - Phase 5 fix).

**Schema**:
```javascript
{
    line: number,
    col: number,
    column: number,
    name: string,                // 'UserController', 'DefaultExportClass'
    type: 'class',
    kind: 'ClassDeclaration' | 'ClassExpression',
    type_annotation: string,     // TypeScript type info
    extends_type: string,        // Parent class name
    has_type_params: boolean,    // Generic class
    type_params: string          // 'T extends User, U'
}
```

**Database Table**: `symbols` (type='class')

**Phase 5 Fix** (Lines 513-528): **REMOVED interface/type extraction**
- Baseline incorrectly included interfaces/types as "class" symbols
- Phase 5 ONLY extracts `ClassDeclaration` and `ClassExpression`
- Result: 655 real classes (vs 1,039 contaminated with interfaces)

**Examples**:
```javascript
// Class declaration
class UserService extends BaseService { }
// → name='UserService', extends_type='BaseService'

// Generic class
class Repository<T extends Model> { }
// → name='Repository', has_type_params=true, type_params='T extends Model'

// Class expression
const MyClass = class InnerName { };
// → name='InnerName' (or 'MyClass' if anonymous)
```

---

### 4. **extractClassProperties** (Lines 553-643)

**Purpose**: Extract class field declarations (TypeScript/ES2022+).

**Schema**:
```javascript
{
    line: number,
    class_name: string,          // 'User'
    property_name: string,       // 'username', 'password_hash'
    property_type: string,       // 'string', 'string | null'
    is_optional: boolean,        // Has '?' modifier
    is_readonly: boolean,        // Has 'readonly' modifier
    access_modifier: string,     // 'private' | 'protected' | 'public' | null
    has_declare: boolean,        // Has 'declare' keyword
    initializer: string          // Default value (truncated to 500 chars)
}
```

**Database Table**: `class_properties`

**Critical for**:
- ORM model understanding (Sequelize/TypeORM)
- Sensitive field detection (password_hash, api_key)
- Type safety analysis

**Examples**:
```javascript
class User {
    declare id: number;
    // → property_name='id', property_type='number', has_declare=true

    private password_hash: string;
    // → access_modifier='private', property_type='string'

    email: string | null;
    // → property_type='string | null'

    readonly createdAt: Date = new Date();
    // → is_readonly=true, initializer='new Date()'

    account?: Account;
    // → is_optional=true, property_type='Account'
}
```

---

### 5. **extractEnvVarUsage** (Lines 662-814)

**Purpose**: Track environment variable access patterns.

**Schema**:
```javascript
{
    line: number,
    var_name: string,            // 'DATABASE_URL', 'API_KEY'
    access_type: string,         // 'read' | 'write' | 'check'
    in_function: string,         // Function scope (from scopeMap)
    property_access: string      // Full expression: 'process.env.DATABASE_URL'
}
```

**Database Table**: `env_var_usage`

**Patterns Detected**:
- Dot access: `process.env.NODE_ENV`
- Bracket access: `process.env['DATABASE_URL']`
- Destructuring: `const { PORT } = process.env`
- Dynamic access: `process.env[variable]`

**Examples**:
```javascript
// Read
const dbUrl = process.env.DATABASE_URL;
// → var_name='DATABASE_URL', access_type='read'

// Write
process.env.SECRET = 'hardcoded';
// → var_name='SECRET', access_type='write'

// Check
if (process.env.API_KEY) { }
// → var_name='API_KEY', access_type='check'

// Destructuring
const { PORT, HOST } = process.env;
// → Two records: var_name='PORT', var_name='HOST'
```

---

### 6. **extractORMRelationships** (Lines 831-958)

**Purpose**: Detect ORM relationship declarations (Sequelize/Prisma/TypeORM).

**Schema**:
```javascript
{
    line: number,
    source_model: string,        // 'User'
    target_model: string,        // 'Operation'
    relationship_type: string,   // 'hasMany', 'belongsTo', 'hasOne', etc.
    foreign_key: string,         // 'user_id'
    cascade_delete: boolean,     // onDelete: 'CASCADE'
    as_name: string              // Alias: 'articles'
}
```

**Database Table**: `orm_relationships`

**Relationship Types**:
- `hasMany`, `belongsTo`, `hasOne`, `hasAndBelongsToMany`, `belongsToMany`

**Critical for**:
- N+1 query detection
- IDOR vulnerability analysis
- Graph-based security analysis

**Examples**:
```javascript
// Has-many relationship
User.hasMany(Operation);
// → source_model='User', target_model='Operation', relationship_type='hasMany'

// Belongs-to with foreign key
User.belongsTo(Account, { foreignKey: 'account_id' });
// → foreign_key='account_id'

// Has-one with cascade delete
User.hasOne(Profile, { onDelete: 'CASCADE' });
// → cascade_delete=true

// With alias
User.hasMany(Post, { as: 'articles' });
// → as_name='articles'
```

---

### 7. **extractCalls** (Lines 970-1160)

**Purpose**: Extract call expressions and property accesses for taint analysis.

**Schema**:
```javascript
{
    name: string,                // 'getUserById', 'req.body', 'res.send'
    line: number,
    column: number,
    type: 'call' | 'property'    // Inferred from sink patterns
}
```

**Database Table**: `symbols` (type='call' or 'property')

**Name Building Logic** (Lines 997-1030):
- Simple: `obj.prop` → `'obj.prop'`
- Chained: `obj.prop1.prop2` → `'obj.prop1.prop2'`
- Nested calls: `getData().map` → `'getData().map'`
- `this` keyword: `this.handler` → `'this.handler'`

**Sink Detection** (Lines 1038-1044):
- If name contains sink pattern (`res.send`, `innerHTML`, `exec`, etc.) → type='call'
- Otherwise → type='property'

**Deduplication** (Lines 1141-1149): Remove duplicate (name, line, column, type) tuples

**Examples**:
```javascript
// Property access
const data = req.body;
// → name='req.body', type='property'

// Method call
res.send(data);
// → name='res.send', type='call' (sink pattern)

// Chained calls
const result = getData().map(x => x).filter(Boolean);
// → name='getData().map', name='getData().map().filter'

// this access
this.userService.create(data);
// → name='this.userService.create'
```

---

### 8. **buildScopeMap** (Lines 1171-1301)

**Purpose**: Map line numbers to function names for scope context.

**Output**: `Map<number, string>` (1-indexed line → function name)

**Critical for**:
- `extractAssignments`: Track assignment scope
- `extractFunctionCallArgs`: Track caller context
- `extractReturns`: Track return scope
- `extractObjectLiterals`: Track object literal context

**Logic**:
1. Collect all function-like nodes with line ranges
2. Build class context stack (qualified names: `Class.method`)
3. Sort by start line, then depth (deeper functions override)
4. Map every line in function range to function name

**Name Extraction** (Lines 1249-1281):
- VariableDeclaration: `const exportPlants = async () => {}` → `'exportPlants'`
- PropertyAssignment: `{ exportPlants: async () => {} }` → `'exportPlants'`
- BinaryExpression: `ExportService.exportPlants = () => {}` → `'ExportService.exportPlants'`

**Examples**:
```javascript
function outer() {           // Lines 1-5 → 'outer'
    function inner() {       // Lines 2-4 → 'inner' (overrides)
        return 1;
    }
    return inner();
}
```

**Result Map**:
```
1 → 'outer'
2 → 'inner'
3 → 'inner'
4 → 'inner'
5 → 'outer'
```

---

### 9. **extractAssignments** (Lines 1312-1523)

**Purpose**: Extract variable assignments with data flow information for taint tracking.

**Schema**:
```javascript
{
    target_var: string,          // 'userId', 'data'
    source_expr: string,         // 'req.params.id' (truncated to 500 chars)
    line: number,
    in_function: string,         // Function scope (from scopeMap)
    source_vars: string[],       // All variables referenced in source_expr
    property_path: string        // For destructuring: 'req.params.id'
}
```

**Database Table**: `assignments`

**Critical Feature**: **Property Path Tracking** (Lines 1429-1492)
- Preserves destructuring semantics for taint analysis
- Object destructuring: `const { id } = req.params` → property_path='req.params.id'
- Array destructuring: `const [first] = array` → property_path='array[0]'

**Patterns Detected**:
1. **VariableDeclaration** (Lines 1406-1493)
   - Simple: `const x = y`
   - Object destructuring: `const { id, batchId } = req.params`
   - Array destructuring: `const [first, second] = array`

2. **BinaryExpression** (Lines 1496-1516)
   - Assignment: `x = y`

**Source Variable Extraction** (Lines 1316-1394):
- Identifiers: `userId` → `['userId']`
- Property access: `req.body` → `['req.body']`
- Element access: `array[0]` → `['array[0]']`
- Complex expressions: `(genetics.yield * genetics.quantity)` → `['genetics.yield', 'genetics.quantity']`

**Examples**:
```javascript
// Simple assignment
const userId = req.params.id;
// → target_var='userId', source_expr='req.params.id', source_vars=['req.params.id'], property_path=null

// Object destructuring (CRITICAL for taint)
const { id, batchId } = req.params;
// → Two records:
//   1. target_var='id', property_path='req.params.id'
//   2. target_var='batchId', property_path='req.params.batchId'

// Array destructuring
const [first, second] = array;
// → Two records:
//   1. target_var='first', property_path='array[0]'
//   2. target_var='second', property_path='array[1]'

// Binary assignment
data.field = taintedInput;
// → target_var='data.field', source_expr='taintedInput', property_path=null
```

---

### 10. **extractFunctionCallArgs** (Lines 1537-1675)

**Purpose**: Extract function call arguments for inter-procedural taint tracking.

**Schema**:
```javascript
{
    line: number,
    caller_function: string,     // Function making the call (from scopeMap)
    callee_function: string,     // Function being called
    argument_index: number,      // 0, 1, 2, ... (null for 0-arg calls)
    argument_expr: string,       // Argument expression (truncated to 500 chars)
    param_name: string,          // Parameter name from function signature
    callee_file_path: string     // Cross-file resolution (relative to project root)
}
```

**Database Table**: `function_call_args`

**Critical Features**:
1. **Chained Call Handling** (Lines 1555-1591)
   - Processes intermediate calls BEFORE marking visited
   - Example: `res.status(404).json({})` captures BOTH calls

2. **0-Argument Call Handling** (Lines 1640-1649)
   - Creates baseline record with NULL argument fields
   - Fixes 30.7% missing coverage (createApp(), useState(), etc.)

3. **Cross-File Resolution** (Lines 1616-1629)
   - Uses TypeScript checker to resolve callee file path
   - Enables cross-file taint tracking

**Examples**:
```javascript
// Simple call
createUser(userData, req.user.id);
// → Two records:
//   1. argument_index=0, argument_expr='userData', param_name='data' (from function signature)
//   2. argument_index=1, argument_expr='req.user.id', param_name='_createdBy'

// Chained calls
res.status(404).json({ error: 'Not found' });
// → Two calls captured:
//   1. callee_function='res.status', argument_expr='404'
//   2. callee_function='res.status().json', argument_expr='{ error: \'Not found\' }'

// Zero-argument call
const app = createApp();
// → argument_index=null, argument_expr=null, param_name=null
```

---

### 11. **extractReturns** (Lines 1686-1869)

**Purpose**: Extract return statements with JSX detection for React component analysis.

**Schema**:
```javascript
{
    function_name: string,       // Function scope (from scopeMap)
    line: number,
    return_expr: string,         // Return expression (truncated to 1000 chars)
    return_vars: string[],       // All variables referenced in return_expr
    has_jsx: boolean,            // Contains JSX elements
    returns_component: boolean,  // Returns uppercase JSX component
    return_index: number         // Nth return in function (1-indexed)
}
```

**Database Table**: `returns`

**JSX Detection** (Lines 1771-1818):
- Direct JSX: `JsxElement`, `JsxSelfClosingElement`, `JsxFragment`
- Transformed JSX: `React.createElement` calls
- Component detection: Uppercase tag names (`<UserCard />`)

**Examples**:
```javascript
// Simple return
function getUserId() {
    return user.id;
}
// → return_expr='user.id', return_vars=['user.id'], has_jsx=false

// JSX return
function UserCard() {
    return <div>{user.name}</div>;
}
// → has_jsx=true, returns_component=false (lowercase tag)

// Component return
function Dashboard() {
    return <UserCard user={currentUser} />;
}
// → has_jsx=true, returns_component=true (uppercase component)

// Multiple returns
function validate(x) {
    if (x < 0) return false;  // return_index=1
    return true;               // return_index=2
}
```

---

### 12. **extractObjectLiterals** (Lines 1880-1999)

**Purpose**: Extract object literal properties for dynamic dispatch resolution.

**Schema**:
```javascript
{
    line: number,
    variable_name: string,       // Variable name or synthetic ('<return:funcName>')
    property_name: string,       // Property key
    property_value: string,      // Property value (truncated to 250 chars)
    property_type: string,       // 'value' | 'shorthand' | 'method'
    nested_level: number,        // Nesting depth
    in_function: string          // Function scope (from scopeMap)
}
```

**Database Table**: `object_literals`

**Patterns Extracted**:
1. **Variable Declaration**: `const x = { ... }`
2. **Assignment**: `x = { ... }`
3. **Return Statement**: `return { ... }`
4. **Function Argument**: `fn({ ... })`
5. **Array Element**: `[{ ... }, { ... }]`

**Recursive Nesting** (Lines 1911-1914):
- Extracts ALL nesting levels (fixes 26.2% missing records)

**Examples**:
```javascript
// Variable declaration
const config = { port: 3000, host: 'localhost' };
// → Two records:
//   1. property_name='port', property_value='3000', property_type='value'
//   2. property_name='host', property_value='localhost', property_type='value'

// Shorthand property
const port = 8080;
const config = { port };
// → property_name='port', property_value='port', property_type='shorthand'

// Method
const service = {
    async create(data) { }
};
// → property_name='create', property_value='<function>', property_type='method'

// Nested object
const schema = {
    fields: { id: 'number', name: 'string' }
};
// → Records for 'fields' (nested_level=0) and 'id'/'name' (nested_level=1)

// Return object (synthetic name)
function getConfig() {
    return { port: 3000 };
}
// → variable_name='<return:getConfig>'
```

---

### 13. **extractVariableUsage** (Lines 2010-2055)

**Purpose**: Compute variable read/write/call usage from assignments and function calls.

**Schema**:
```javascript
{
    line: number,
    variable_name: string,
    usage_type: 'read' | 'write' | 'call',
    in_component: string,        // Function scope
    in_hook: string,             // Empty (for React hooks)
    scope_level: number          // 0=global, 1=local
}
```

**Database Table**: `variable_usage`

**Computed Data** (derived from `assignments` and `function_call_args`):
- Write: From `assignments.target_var`
- Read: From `assignments.source_vars`
- Call: From `function_call_args.callee_function`

---

### 14. **extractImportStyles** (Lines 2065-2116)

**Purpose**: Analyze import statements for bundle optimization.

**Schema**:
```javascript
{
    line: number,
    package: string,             // 'lodash', 'react'
    import_style: string,        // 'namespace' | 'named' | 'default' | 'side-effect'
    imported_names: string[],    // ['map', 'filter'] (for named imports)
    alias_name: string,          // 'lodash' (for namespace/default)
    full_statement: string       // Full import statement (truncated to 200 chars)
}
```

**Database Table**: `import_styles`

**Classification**:
- **namespace**: `import * as lodash from 'lodash'` (prevents tree-shaking)
- **named**: `import { map } from 'lodash'` (allows tree-shaking)
- **default**: `import React from 'react'`
- **side-effect**: `import 'polyfill'` (no bindings)

---

### 15. **extractRefs** (Lines 2126-2150)

**Purpose**: Map local names to module paths for cross-file analysis.

**Output**: `{ localName: modulePath }`

**Examples**:
```javascript
import { useState } from 'react';
import * as fs from 'fs';

// Result:
{
    'useState': 'react',
    'fs': 'fs'
}
```

---

### 16. **countNodes** (Lines 2161-2172)

**Purpose**: Count total AST nodes for complexity metrics.

**Output**: `number` (total node count)

---

## CFG Extractor (`cfg_extractor.js`)

**Purpose**: Build Control Flow Graphs for all functions.

### **extractCFG** (Lines 40-554)

**Schema**:
```javascript
{
    function_name: string,
    blocks: [
        {
            id: number,              // Unique block ID
            type: string,            // 'entry' | 'exit' | 'condition' | 'loop_condition' | 'basic' | 'merge' | 'try' | 'except' | 'finally' | 'return' | 'loop_body'
            start_line: number,
            end_line: number,
            statements: [            // Control flow statements ONLY
                {
                    type: string,    // 'if', 'loop', 'return', 'try', 'catch', 'switch', etc.
                    line: number,
                    text: string     // Truncated to 200 chars
                }
            ],
            condition: string        // For 'condition' blocks (truncated to 200 chars)
        }
    ],
    edges: [
        {
            source: number,          // Source block ID
            target: number,          // Target block ID
            type: string             // 'normal' | 'true' | 'false' | 'exception' | 'back_edge' | 'fallthrough' | 'case' | 'default'
        }
    ]
}
```

**Database Tables**:
- `cfg_basic_blocks`: Individual basic blocks
- `cfg_edges`: Control flow edges

**Block Types**:
- **entry**: Function entry point
- **exit**: Function exit point
- **condition**: If/while/switch condition
- **loop_condition**: Loop header
- **loop_body**: Loop body
- **basic**: Normal sequential code
- **merge**: Control flow merge point
- **try**: Try block entry
- **except**: Catch block entry
- **finally**: Finally block entry
- **return**: Return statement

**Edge Types**:
- **normal**: Sequential flow
- **true**: Condition true branch
- **false**: Condition false branch
- **exception**: Exception flow
- **back_edge**: Loop back edge
- **fallthrough**: Switch case fallthrough
- **case**: Switch case entry
- **default**: Switch default entry

**Critical Fixes** (Session 5 - 2025-10-24):
1. **FIX 1**: Removed early returns in visit() to detect nested functions
2. **FIX 2**: Create explicit basic blocks for control flow bodies (3,442 blocks)
3. **FIX 3**: Add true/false edges correctly (2,038 true edges)
4. **FIX 4**: Populate statements arrays ONLY for control flow (not every AST node)

**Data Quality Fix** (Lines 451-473):
- **DELETED default case** that extracted every AST node as "statement"
- Bug: Was recording Identifier, PropertyAccess, etc. as statements
- Result: 139,234 nodes vs historical 4,994 (2788% over-extraction)
- Fix: ONLY extract control flow nodes (if, return, try, loop, switch)

**Examples**:
```javascript
function validate(x) {
    if (x < 0) {
        return false;
    }
    return true;
}
```

**CFG**:
```
Blocks:
  1: entry
  2: condition (if x < 0)
  3: basic (then branch)
  4: return (return false)
  5: merge
  6: return (return true)
  7: exit

Edges:
  1 → 2 (normal)
  2 → 3 (true)
  2 → 5 (false)
  3 → 4 (normal)
  4 → 7 (normal)
  5 → 6 (normal)
  6 → 7 (normal)
```

---

## Framework Extractors (`framework_extractors.js`)

### 1. **extractReactComponents** (Lines 36-147)

**Purpose**: Detect React components (function and class-based).

**Schema**:
```javascript
{
    name: string,                // 'UserCard', 'Dashboard'
    type: 'function' | 'class',
    start_line: number,
    end_line: number,
    has_jsx: boolean,            // Returns JSX
    hooks_used: string[],        // ['useState', 'useEffect'] (max 10)
    props_type: string           // TypeScript props type (null if not extracted)
}
```

**Database Table**: `react_components`

**Detection Logic**:
1. **Path Filtering** (Lines 47-88):
   - SKIP backend paths: `backend/`, `server/`, `api/`, `controllers/`, `services/`, `middleware/`, `models/`, `routes/`
   - ONLY process frontend paths: `frontend/`, `client/`, `components/`, `pages/`, `ui/`, `.tsx`, `.jsx`
   - Fixes 83.4% false positive rate (1,183 false positives from backend methods)

2. **Function Components** (Lines 92-119):
   - Must start with uppercase (React convention)
   - Must return JSX (checked via `extractReturns`)
   - Extract hooks used from `function_call_args`

3. **Class Components** (Lines 125-144):
   - Must extend `React.Component` or `Component`
   - Phase 5 fix: Does NOT include interfaces/types

---

### 2. **extractReactHooks** (Lines 158-194)

**Purpose**: Detect React hooks usage.

**Schema**:
```javascript
{
    line: number,
    hook_name: string,           // 'useState', 'useEffect', 'useCustomHook'
    component_name: string,      // Component using the hook
    is_custom: boolean,          // Not a built-in React hook
    argument_expr: string,       // Hook arguments
    argument_index: number       // Argument position
}
```

**Database Table**: `react_hooks`

**Built-in Hooks**:
- useState, useEffect, useCallback, useMemo, useRef, useContext, useReducer, useLayoutEffect, useImperativeHandle, useDebugValue, useDeferredValue, useTransition, useId

**Filter** (Lines 175): Excludes dotted method calls (e.g., `userService.createUser`)

---

## Security Extractors (`security_extractors.js`)

### 1. **extractORMQueries** (Lines 36-64)

**Purpose**: Detect ORM method calls (Sequelize/Prisma/TypeORM).

**Schema**:
```javascript
{
    line: number,
    query_type: string,          // Full method: 'User.findAll'
    includes: string,            // 'has_includes' if includes: detected
    has_limit: boolean,          // Has limit/take clause
    has_transaction: boolean     // Always false (not implemented)
}
```

**Database Table**: `orm_queries`

**ORM Methods**:
- Sequelize: findAll, findOne, findByPk, create, update, destroy, upsert, bulkCreate, count, max, min, sum
- Prisma: findMany, findUnique, findFirst, createMany, updateMany, deleteMany, aggregate, groupBy

---

### 2. **extractAPIEndpoints** (Lines 74-107)

**Purpose**: Detect REST API endpoint definitions.

**Schema**:
```javascript
{
    line: number,
    method: string,              // 'GET', 'POST', 'PUT', 'DELETE', etc.
    route: string,               // '/users/:id', '/api/posts'
    handler_function: string,    // Function handling the request
    requires_auth: boolean       // Always false (not implemented)
}
```

**Database Table**: `routes` (renamed from `api_endpoints` to match Python indexer)

**HTTP Methods**: get, post, put, delete, patch, head, options, all

**Filter** (Lines 91-92): Type check for route path (must be string)

---

### 3. **extractValidationFrameworkUsage** (Lines 120-176)

**Purpose**: Detect validation framework usage (Zod, Joi, Yup, etc.).

**Schema**:
```javascript
{
    line: number,
    framework: string,           // 'zod', 'joi', 'yup', etc.
    method: string,              // 'parse', 'validate', 'safeParse'
    variable_name: string,       // Schema variable name
    is_validator: boolean,       // Is validation method (not schema builder)
    argument_expr: string        // Validation arguments (truncated to 200 chars)
}
```

**Database Table**: `validation_framework_usage`

**Supported Frameworks**:
- zod (z, ZodSchema)
- joi (Joi)
- yup (Yup)
- ajv (Ajv)
- class-validator (validate, validateSync, validateOrReject)
- express-validator (validationResult, matchedData, checkSchema)

**Validator Methods**: parse, parseAsync, safeParse, safeParseAsync, validate, validateAsync, validateSync, isValid, isValidSync

**Critical for**: Taint analysis to recognize validation as sanitization

---

### 4. **extractSQLQueries** (Lines 354-397)

**Purpose**: Extract raw SQL queries from database execution calls.

**Schema**:
```javascript
{
    line: number,
    query_text: string           // SQL query string (truncated to 1000 chars)
    // NOTE: command and tables parsed by Python using sqlparse
}
```

**Database Table**: `sql_queries`

**SQL Methods**: execute, query, raw, exec, run, executeSql, executeQuery, execSQL, select, insert, update, delete, query_raw

**Query Resolution** (Lines 409-434):
- Plain strings: `'SELECT * FROM users'`
- Template literals WITHOUT interpolation: `` `SELECT * FROM users` ``
- Template literals WITH interpolation: SKIP (dynamic, can't analyze)
- Variables/expressions: SKIP (can't resolve)

**Critical for**: SQL injection detection

---

## Batch Template (`batch_templates.js`)

**Structure**: Two variants (ES Module and CommonJS)

### Main Orchestration Flow

**ES Module** (Lines 59-361):
```javascript
async function main() {
    // 1. Read batch request JSON
    const request = JSON.parse(fs.readFileSync(requestPath, 'utf8'));
    const filePaths = request.files;
    const projectRoot = request.projectRoot;
    const jsxMode = request.jsxMode || 'transformed';

    // 2. Load TypeScript compiler
    const ts = await import(tsPath);

    // 3. Group files by tsconfig.json
    const filesByConfig = new Map();
    for (const filePath of filePaths) {
        const nearestConfig = findNearestTsconfig(filePath, projectRoot, ts, path);
        filesByConfig.get(nearestConfig).push(filePath);
    }

    // 4. Process each config group
    for (const [configKey, groupedFiles] of filesByConfig.entries()) {
        // Create TypeScript program
        const program = ts.createProgram(groupedFiles, compilerOptions);
        const checker = program.getTypeChecker();

        // 5. Extract data from each file (SINGLE-PASS ARCHITECTURE)
        for (const fileInfo of groupedFiles) {
            const sourceFile = program.getSourceFile(fileInfo.absolute);

            // Step 1: Build scope map
            const scopeMap = buildScopeMap(sourceFile, ts);

            // Step 2: Extract functions and build parameter map
            const functions = extractFunctions(sourceFile, checker, ts);
            const functionParams = new Map();
            functions.forEach(f => functionParams.set(f.name, f.parameters));

            // Step 3: Extract all other data types
            const calls = extractCalls(sourceFile, checker, ts, projectRoot);
            const classes = extractClasses(sourceFile, checker, ts);
            const classProperties = extractClassProperties(sourceFile, ts);
            const envVarUsage = extractEnvVarUsage(sourceFile, ts, scopeMap);
            const ormRelationships = extractORMRelationships(sourceFile, ts);
            const assignments = extractAssignments(sourceFile, ts, scopeMap);
            const functionCallArgs = extractFunctionCallArgs(sourceFile, checker, ts, scopeMap, functionParams, projectRoot);
            const returns = extractReturns(sourceFile, ts, scopeMap);
            const objectLiterals = extractObjectLiterals(sourceFile, ts, scopeMap);
            const variableUsage = extractVariableUsage(assignments, functionCallArgs);
            const importStyles = extractImportStyles(imports);
            const refs = extractRefs(imports);
            const reactComponents = extractReactComponents(functions, classes, returns, functionCallArgs, fileInfo.original);
            const reactHooks = extractReactHooks(functionCallArgs, scopeMap);
            const ormQueries = extractORMQueries(functionCallArgs);
            const apiEndpoints = extractAPIEndpoints(functionCallArgs);
            const validationUsage = extractValidationFrameworkUsage(functionCallArgs, assignments, imports);
            const sqlQueries = extractSQLQueries(functionCallArgs);

            // Step 4: Extract CFG (skip for jsx='preserved' to prevent double extraction)
            let cfg = [];
            if (jsxMode !== 'preserved') {
                cfg = extractCFG(sourceFile, ts);
            }

            // Step 5: Package results
            results[fileInfo.original] = {
                success: true,
                ast: null,  // NEVER serialize AST (prevents 512MB crash)
                extracted_data: {
                    functions, classes, class_properties, env_var_usage,
                    orm_relationships, calls, imports, assignments,
                    function_call_args, returns, object_literals,
                    variable_usage, import_styles, resolved_imports: refs,
                    react_components, react_hooks, orm_queries,
                    routes: apiEndpoints, validation_framework_usage: validationUsage,
                    sql_queries: sqlQueries, scope_map: Object.fromEntries(scopeMap),
                    cfg
                }
            };
        }
    }

    // 6. Write results to output JSON
    fs.writeFileSync(outputPath, JSON.stringify(results, null, 2));
}
```

---

## Complete Data Pipeline Summary

### Phase 1: Python Orchestration (`js_helper_templates.py`)

1. **Assemble JavaScript**:
   ```python
   script = (
       core_ast_extractors.js +
       security_extractors.js +
       framework_extractors.js +
       cfg_extractor.js +
       batch_template.js
   )
   ```

2. **Create Batch Request**:
   ```json
   {
       "files": ["src/index.ts", "src/user.service.ts"],
       "projectRoot": "/path/to/project",
       "jsxMode": "transformed",
       "configMap": {
           "src/index.ts": "/path/to/tsconfig.json"
       }
   }
   ```

3. **Execute Node.js**:
   ```bash
   node script.mjs request.json output.json
   ```

### Phase 2: JavaScript Extraction (Node.js subprocess)

1. Load TypeScript compiler
2. Group files by tsconfig.json
3. Create TypeScript program with type checker
4. For each file:
   - Build scope map (line → function)
   - Extract functions with parameters
   - Extract ALL data types (14 extractors)
   - Extract CFG (if not jsx='preserved')
5. Write results to output.json

### Phase 3: Python Database Insertion

1. Read output.json
2. Insert into SQLite tables:
   - `symbols` (functions, classes, calls, properties)
   - `imports`
   - `assignments`
   - `function_call_args`
   - `returns`
   - `object_literals`
   - `variable_usage`
   - `import_styles`
   - `class_properties`
   - `env_var_usage`
   - `orm_relationships`
   - `react_components`
   - `react_hooks`
   - `orm_queries`
   - `routes`
   - `validation_framework_usage`
   - `sql_queries`
   - `cfg_basic_blocks`
   - `cfg_edges`

---

## Database Schema Coverage

### Tables Populated by JavaScript Extraction

| Table | Extractor | Schema Contract | Critical Fields |
|-------|-----------|-----------------|-----------------|
| **symbols** (type='function') | `extractFunctions` | ✅ | name, parameters, type_annotation, return_type |
| **symbols** (type='class') | `extractClasses` | ✅ | name, extends_type, type_params |
| **symbols** (type='call') | `extractCalls` | ✅ | name, line, column |
| **symbols** (type='property') | `extractCalls` | ✅ | name, line, column |
| **imports** | `extractImports` | ✅ | module, specifiers, kind |
| **assignments** | `extractAssignments` | ✅ | target_var, source_expr, source_vars, property_path |
| **function_call_args** | `extractFunctionCallArgs` | ✅ | caller_function, callee_function, argument_expr, param_name, callee_file_path |
| **returns** | `extractReturns` | ✅ | function_name, return_expr, return_vars, has_jsx, returns_component |
| **object_literals** | `extractObjectLiterals` | ✅ | variable_name, property_name, property_value, nested_level |
| **variable_usage** | `extractVariableUsage` | ✅ | variable_name, usage_type, in_component |
| **import_styles** | `extractImportStyles` | ✅ | package, import_style, imported_names |
| **class_properties** | `extractClassProperties` | ✅ | class_name, property_name, property_type, access_modifier |
| **env_var_usage** | `extractEnvVarUsage` | ✅ | var_name, access_type, property_access |
| **orm_relationships** | `extractORMRelationships` | ✅ | source_model, target_model, relationship_type, foreign_key |
| **react_components** | `extractReactComponents` | ✅ | name, type, has_jsx, hooks_used |
| **react_hooks** | `extractReactHooks` | ✅ | hook_name, component_name, is_custom |
| **orm_queries** | `extractORMQueries` | ✅ | query_type, includes, has_limit |
| **routes** | `extractAPIEndpoints` | ✅ | method, route, handler_function |
| **validation_framework_usage** | `extractValidationFrameworkUsage` | ✅ | framework, method, variable_name |
| **sql_queries** | `extractSQLQueries` | ✅ | query_text |
| **cfg_basic_blocks** | `extractCFG` | ✅ | function_name, block_id, block_type, statements |
| **cfg_edges** | `extractCFG` | ✅ | source, target, edge_type |

---

## Current Capabilities Summary

### What We CAN Extract

#### 1. **Complete Function Metadata**
- ✅ Function names (qualified: `Class.method`)
- ✅ Real parameter names (NOT `arg0, arg1`)
- ✅ TypeScript type annotations
- ✅ Return types
- ✅ Generic constraints
- ✅ Method inheritance chains

#### 2. **Call Graph Data**
- ✅ Function calls with arguments
- ✅ Argument → parameter mapping
- ✅ Cross-file callee resolution
- ✅ Chained method calls (`res.status().json()`)
- ✅ 0-argument calls (fixes 30.7% missing coverage)

#### 3. **Data Flow Information**
- ✅ Variable assignments
- ✅ Destructuring assignments (with property paths)
- ✅ Source variable extraction
- ✅ Property access chains
- ✅ Return statement tracking

#### 4. **Control Flow Graphs**
- ✅ All functions (including nested callbacks)
- ✅ 11 block types (entry, exit, condition, loop, try/catch, etc.)
- ✅ 8 edge types (normal, true, false, exception, back_edge, etc.)
- ✅ Switch statement handling
- ✅ JSX integration (no double extraction bug)

#### 5. **React-Specific**
- ✅ Function components (with JSX detection)
- ✅ Class components (extends React.Component)
- ✅ Hooks usage (built-in + custom)
- ✅ Path-based filtering (fixes 83.4% false positives)

#### 6. **Security Patterns**
- ✅ ORM queries (Sequelize/Prisma)
- ✅ ORM relationships (hasMany, belongsTo, etc.)
- ✅ API endpoints (Express/Fastify)
- ✅ Validation framework usage (Zod/Joi/Yup)
- ✅ Raw SQL queries (with interpolation detection)
- ✅ Environment variable access

#### 7. **Class Information**
- ✅ Class declarations (NOT interfaces/types)
- ✅ Class properties with TypeScript metadata
- ✅ Access modifiers (private/protected/public)
- ✅ Readonly/optional/declare modifiers
- ✅ Property initializers

#### 8. **Import Analysis**
- ✅ ES6 imports (named, default, namespace)
- ✅ CommonJS require
- ✅ Dynamic imports
- ✅ Import style classification (tree-shaking analysis)
- ✅ Module resolution mappings

#### 9. **Object Literals**
- ✅ Recursive nesting (all levels)
- ✅ Shorthand properties
- ✅ Methods
- ✅ Return objects (synthetic names)
- ✅ Function arguments

---

### What We CANNOT Extract

#### 1. **Semantic Understanding**
- ❌ Business logic validation
- ❌ Intent inference ("what this code is trying to do")
- ❌ Natural language code descriptions

#### 2. **Runtime Behavior**
- ❌ Dynamic property access resolution (computed keys)
- ❌ Prototype chain traversal
- ❌ Closure variable capture (scope chain)
- ❌ Async execution order

#### 3. **Type-Level Computation**
- ❌ Generic type inference (T extends U → concrete type)
- ❌ Conditional types (T extends U ? X : Y)
- ❌ Mapped types ({ [K in keyof T]: ... })

#### 4. **Cross-Module Analysis (Limited)**
- ❌ Full module dependency graph
- ❌ Transitive taint flow across many files
- ❌ Circular dependency detection

#### 5. **Advanced Patterns**
- ❌ Higher-order function tracking (callbacks of callbacks)
- ❌ Memoization/caching detection
- ❌ Event listener registration
- ❌ Observer pattern subscriptions

---

## Taint Analysis Implications

### What Current Extraction ENABLES

#### 1. **Intra-Procedural Taint Tracking**
- ✅ Source → assignment → sink within single function
- ✅ Property path preservation (destructuring)
- ✅ Variable renaming tracking

**Example**:
```javascript
function createUser(req, res) {
    const { name, email } = req.body;  // property_path: 'req.body.name', 'req.body.email'
    const user = { name, email };      // source_vars: ['name', 'email']
    db.create(user);                   // argument_expr: 'user'
}
```
**Taint Flow**: `req.body` → `name` → `user` → `db.create` ✅

#### 2. **Inter-Procedural Taint Tracking (Simple)**
- ✅ Argument → parameter mapping
- ✅ Cross-file callee resolution
- ✅ Return value tracking

**Example**:
```javascript
function sanitize(input) {
    return input.trim().toLowerCase();
}

function createUser(req, res) {
    const name = sanitize(req.body.name);  // callee='sanitize', argument_expr='req.body.name'
    db.create({ name });
}
```
**Taint Flow**: `req.body.name` → `sanitize(input)` → `return` → `name` → `db.create` ✅

#### 3. **Sanitizer Recognition**
- ✅ Validation framework detection (Zod, Joi, Yup)
- ✅ Method-level tracking (`schema.parse`, `Joi.validate`)

**Example**:
```javascript
const userSchema = z.object({ name: z.string(), email: z.string().email() });

function createUser(req, res) {
    const validated = userSchema.parse(req.body);  // framework='zod', method='parse'
    db.create(validated);  // SANITIZED (taint cleared)
}
```

#### 4. **Source/Sink Detection**
- ✅ Express route handlers (sources)
- ✅ Database calls (sinks: `db.execute`, `User.create`)
- ✅ Response methods (sinks: `res.send`, `res.json`)

---

### What Current Extraction LIMITS

#### 1. **Deep Call Chains**
- ❌ Cannot track taint through 5+ function calls
- ❌ Loses context in higher-order functions

**Example**:
```javascript
function fetchUser(id) { return db.findOne({ id }); }
function getUser(id) { return fetchUser(id); }
function getUserDetails(id) { return getUser(id); }
function handler(req, res) {
    const user = getUserDetails(req.params.id);  // Lost after 3+ hops
}
```

#### 2. **Dynamic Dispatch**
- ❌ Cannot resolve function calls via variables
- ❌ Cannot resolve method calls via `this[methodName]`

**Example**:
```javascript
const handlers = {
    create: (data) => db.create(data),
    update: (data) => db.update(data)
};

function dispatch(action, data) {
    return handlers[action](data);  // Dynamic dispatch - cannot resolve
}
```

#### 3. **Asynchronous Flows**
- ❌ Cannot track taint across `await` boundaries
- ❌ Cannot track promise chains

**Example**:
```javascript
async function handler(req, res) {
    const user = await fetchUser(req.params.id);  // Taint lost across await
    res.json(user);
}
```

#### 4. **Array Operations**
- ❌ Cannot track taint through `.map()`, `.filter()`, `.reduce()`

**Example**:
```javascript
function handler(req, res) {
    const ids = req.body.ids;  // Tainted
    const users = ids.map(id => db.findOne({ id }));  // Taint lost in map callback
}
```

---

## Key Architectural Decisions

### 1. **Single-Pass Extraction** (Phase 5)
- **Before**: Two-pass system (symbols first, CFG second)
- **After**: Single pass extracts everything
- **Benefit**: Fixes jsx='preserved' CFG bug (0 CFGs extracted)

### 2. **No AST Serialization**
- **ast: null** ALWAYS (Line 289, 609 in batch_templates.js)
- **Reason**: Prevents 512MB crash from full AST serialization
- **Trade-off**: Python cannot access AST, must trust JavaScript extraction

### 3. **TypeScript Checker Integration**
- Uses `program.getTypeChecker()` for type metadata
- Enables parameter extraction, return type resolution, cross-file resolution
- Trade-off: Slower (type analysis expensive), but accurate

### 4. **Scope Map Foundation**
- Pre-built `line → function` map used by 4 extractors
- Single source of truth for function context
- Critical for taint analysis (assignments, calls, returns)

### 5. **Property Path Preservation**
- Destructuring assignments preserve full path
- `const { id } = req.params` → `property_path='req.params.id'`
- Enables precise taint tracking (not just variable names)

### 6. **Deduplication Strategy**
- `extractCalls`: Dedupe by (name, line, column, type)
- Reason: Same symbol may appear via multiple AST paths
- Trade-off: Slightly slower, but accurate

### 7. **CFG Statement Filtering**
- ONLY extract control flow statements (if, return, try, loop, switch)
- DO NOT extract every AST node (Identifier, PropertyAccess, etc.)
- Fixes 2788% over-extraction (139,234 nodes → 4,994 statements)

---

## Performance Characteristics

### Bottlenecks

1. **TypeScript Program Creation** (Lines 167-192)
   - Most expensive operation
   - Parses all files + type checking
   - Mitigated: Group files by tsconfig.json

2. **Type Checker Queries** (Lines 316-349 in core_extractors.js)
   - `checker.getSymbolAtLocation()` is slow
   - Called once per function/class
   - Wrapped in try/catch (may fail on complex types)

3. **Recursive AST Traversal**
   - Depth limit: 500 (increased from 100 for deep React components)
   - Visitor pattern: ts.forEachChild()

### Optimizations

1. **Module Caching** (Lines 34-41 in js_helper_templates.py)
   - JavaScript files loaded once on first call
   - Cached in `_JS_CACHE` dictionary

2. **Scope Map Reuse**
   - Built once, used by 4 extractors
   - Avoids redundant traversals

3. **Batch Processing**
   - Single TypeScript program for multiple files
   - Amortizes program creation cost

---

## Future Enhancement Opportunities

### 1. **Cross-File Taint Tracking**
- Current: `callee_file_path` extracted but not used
- Enhancement: Build inter-file call graph in Python
- Enables: Multi-file taint propagation

### 2. **Type-Based Taint Analysis**
- Current: Type annotations extracted but not analyzed
- Enhancement: Use TypeScript types to infer taint (e.g., `Unsafe<T>` type)
- Enables: Type-directed security analysis

### 3. **Async Flow Tracking**
- Current: No async handling
- Enhancement: Track Promise chains, async/await
- Enables: Asynchronous taint tracking

### 4. **Array Operation Tracking**
- Current: Array methods treated as opaque
- Enhancement: Model map/filter/reduce as taint-preserving
- Enables: Collection-based taint tracking

### 5. **Dynamic Dispatch Resolution**
- Current: Object literal extraction exists but not used
- Enhancement: Resolve `obj[key]()` using object_literals table
- Enables: More precise call graph

---

## Error Handling & Edge Cases

### 1. **TypeScript Errors**
- Collected via `ts.getPreEmitDiagnostics()` (Lines 216-230)
- Stored in `diagnostics` array (not inserted to database)
- Does NOT block extraction (best-effort)

### 2. **Missing TypeScript**
- Hard failure if typescript.js not found (Line 89-91)
- Expected location: `.auditor_venv/.theauditor_tools/node_modules/typescript/lib/typescript.js`

### 3. **Invalid tsconfig.json**
- Hard failure with error message (Lines 134-151, 469-474)
- Falls back to DEFAULT_KEY group (no tsconfig)

### 4. **Synthetic Nodes**
- try/catch around position extraction (Lines 167-176 in core_extractors.js)
- Fallback: line=1, endLine=1

### 5. **Type Extraction Failure**
- Silent failure (Lines 347-349 in core_extractors.js)
- Metadata incomplete, but function still extracted

---

## Debugging & Observability

### Environment Variables

1. **THEAUDITOR_DEBUG**
   - Enables debug logging in `extractFunctions` and `extractCalls`
   - Example output: `[DEBUG JS] extractFunctions: Extracted 42 functions from file.ts`

2. **THEAUDITOR_VALIDATION_DEBUG**
   - Enables debug logging in validation framework extraction
   - Example output: `[VALIDATION-L2-EXTRACT] Detected 1 validation frameworks`

### Debug Output

**Batch Mode** (Lines 124-128, 194):
```
[BATCH DEBUG] Processing 15 files, jsxMode=transformed, jsxEmitMode=React
[BATCH DEBUG] Config group: DEFAULT, files=15
[BATCH DEBUG] Created program, rootNames=15
```

**Extraction** (Lines 211, 239, 257, 279-280):
```
[DEBUG JS BATCH] Loaded sourceFile for file.ts, jsxMode=transformed
[DEBUG JS BATCH] Single-pass extraction for file.ts, jsxMode=transformed
[DEBUG JS BATCH] Extracted 12 class properties from file.ts
[DEBUG JS BATCH] Extracting CFG for file.ts (jsxMode=transformed)
[DEBUG JS BATCH] Extracted 42 CFGs from file.ts
[DEBUG JS BATCH] Single-pass complete for file.ts, cfg_count=42
```

---

## Schema Contract Guarantees

All extracted data conforms to Python indexer expectations:

1. **Symbols Table**
   - `name`: Never null (filtered in extractors)
   - `parameters`: Array of strings (never null)
   - `type`: Enum ('function', 'class', 'call', 'property')

2. **Function Call Args**
   - `caller_function`: From scopeMap (never null)
   - `callee_function`: From AST (never null - CHECK constraint)
   - `argument_index`: NULL for 0-arg calls (as of 2025-10-25)
   - `param_name`: Matched from function signature or 'argN'

3. **Assignments**
   - `property_path`: NULL for non-destructured, string for destructured
   - `source_vars`: Array (may be empty)

4. **CFG**
   - `blocks`: Array (minimum 2: entry + exit)
   - `edges`: Array (minimum 1: entry → exit)
   - `statements`: Array (control flow only, NOT all nodes)

---

## Conclusion

The JavaScript extraction system extracts **21 distinct data types** across **4 specialized modules**, populating **22 database tables** with ground-truth facts about JavaScript/TypeScript code. It provides complete function metadata, call graphs, data flow, control flow, React patterns, and security-relevant patterns - all extracted in a single pass using the TypeScript Compiler API.

**Key Strengths**:
- ✅ Real parameter names (not generic arg0, arg1)
- ✅ Property path preservation (destructuring semantics)
- ✅ Cross-file resolution (TypeScript checker)
- ✅ Complete CFG extraction (11 block types, 8 edge types)
- ✅ Phase 5 data quality fixes (no interface contamination, no statement over-extraction)

**Key Limitations**:
- ❌ Deep call chain tracking (5+ hops)
- ❌ Dynamic dispatch resolution
- ❌ Async flow tracking
- ❌ Array operation modeling

The extraction is **deterministic**, **complete** (for static analysis), and **optimized** for taint tracking and security analysis.
