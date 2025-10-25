# Validation Framework Implementation - Step-by-Step Debug Plan

**Project:** TheAuditor
**Feature:** Validation Framework Sanitizer Detection
**Test Target:** Plant project (C:/Users/santa/Desktop/plant)
**Date:** 2025-10-25

---

## CONCRETE TEST CASE: Login Endpoint with Zod Validation

### Source Code Flow (Plant Project)

```typescript
// 1. SOURCE: auth.routes.ts:23-26
router.post('/login',
  authRateLimit,
  validate(validation.auth.login),  // <-- Validation middleware
  handler(authController.login)
);

// 2. VALIDATION MIDDLEWARE: validate.ts:15-22
export const validateBody = (schema: ZodSchema) => {
  return async (req: Request, res: Response, next: NextFunction) => {
    // LINE 19: CRITICAL SANITIZER CALL
    const validated = await schema.parseAsync(req.body);
    req.body = validated;  // Clean data replaces tainted
    next();
  }
}

// 3. VALIDATION SCHEMA: auth.schemas.ts:19-22
login: z.object({
  email: atoms.email,
  password: atoms.password
})

// 4. CONTROLLER: auth.controller.ts:56-60
async login(req, res, next) {
  const { email, password } = req.body;  // Should be clean
  const { user, tokens } = await authService.login({ email, password });  // SINK
}
```

### Expected Data Flow in TheAuditor

**Layer 1: Framework Detection**
- Input: `plant/backend/package.json`
- Expected: `frameworks` table contains `{name: 'zod', version: '4.1.11', language: 'javascript'}`
- Debug query: `SELECT * FROM frameworks WHERE name='zod'`

**Layer 2: Validation Extraction**
- Input: `plant/backend/src/middleware/validate.ts`
- Expected: `validation_framework_usage` table contains:
  ```
  {
    file_path: 'backend/src/middleware/validate.ts',
    line: 19,
    framework: 'zod',
    method: 'parseAsync',
    variable_name: 'schema',
    is_schema_builder: 0,
    is_validator: 1,
    argument_expr: 'req.body'
  }
  ```
- Debug query: `SELECT * FROM validation_framework_usage WHERE method='parseAsync'`

**Layer 3: Taint Analysis**
- Input: Taint sources (req.body), sinks (authService.login)
- Expected: `has_sanitizer_between()` finds validation at line 19
- Result: NO taint path reported (validation sanitizes)

### Current State (Baseline - Before Implementation)

**Run baseline to establish current behavior:**
```bash
cd C:/Users/santa/Desktop/plant
C:/Users/santa/Desktop/TheAuditor/.venv/Scripts/aud.exe index
C:/Users/santa/Desktop/TheAuditor/.venv/Scripts/aud.exe taint-analyze
```

**Expected baseline result:** FALSE POSITIVE (taint path reported even though validated)

---

## Implementation Steps

### STEP 1: Add Debug Logging Infrastructure

**File:** `theauditor/utils/validation_debug.py` (NEW)

```python
"""Debug logging for validation framework implementation."""
import os
import sys

VALIDATION_DEBUG = os.getenv('THEAUDITOR_VALIDATION_DEBUG', '0') == '1'

def log_validation(layer: str, message: str, data: dict = None):
    """Log validation framework detection/extraction."""
    if not VALIDATION_DEBUG:
        return

    prefix = f"[VALIDATION-{layer}]"
    print(f"{prefix} {message}", file=sys.stderr)
    if data:
        import json
        print(f"{prefix}   Data: {json.dumps(data, indent=2)}", file=sys.stderr)
```

**Usage in each layer:**
- Layer 1: `log_validation("L1-DETECT", "Found zod in package.json", {"version": "4.1.11"})`
- Layer 2: `log_validation("L2-EXTRACT", "Extracted parseAsync call", {"line": 19, "method": "parseAsync"})`
- Layer 3: `log_validation("L3-TAINT", "Checking sanitizer between", {"source_line": 10, "sink_line": 60})`

---

### STEP 2: Layer 1 - Framework Detection

**File:** `theauditor/framework_registry.py`

**Add after line 200 (after angular):**

```python
# Validation/Schema libraries (JavaScript/TypeScript)
"zod": {
    "language": "javascript",
    "detection_sources": {
        "package.json": [
            ["dependencies"],
            ["devDependencies"],
        ],
    },
    "import_patterns": ["from 'zod'", "import { z }", "import * as z from 'zod'"],
    "category": "validation",
},
"joi": {
    "language": "javascript",
    "detection_sources": {
        "package.json": [
            ["dependencies"],
            ["devDependencies"],
        ],
    },
    "package_pattern": "joi",
    "import_patterns": ["require('joi')", "from 'joi'", "import Joi"],
    "category": "validation",
},
```

**Debug logging:** Add to `framework_detector.py:_detect_from_manifests()` (around line 150)

```python
from theauditor.utils.validation_debug import log_validation

# After detecting framework
if fw_name in ['zod', 'joi', 'yup', 'ajv', 'class-validator', 'express-validator']:
    log_validation("L1-DETECT", f"Found validation framework: {fw_name}", {
        "framework": fw_name,
        "version": version,
        "source": manifest_file
    })
```

**Verification:**
```bash
cd C:/Users/santa/Desktop/plant
THEAUDITOR_VALIDATION_DEBUG=1 C:/Users/santa/Desktop/TheAuditor/.venv/Scripts/aud.exe index 2>&1 | grep "L1-DETECT"

# Expected output:
# [VALIDATION-L1-DETECT] Found validation framework: zod
#   Data: {"framework": "zod", "version": "4.1.11", "source": "backend/package.json"}
```

**Database check:**
```bash
cd C:/Users/santa/Desktop/plant
C:/Users/santa/Desktop/TheAuditor/.venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('.pf/repo_index.db')
c = conn.cursor()
c.execute(\"SELECT name, version, language FROM frameworks WHERE name IN ('zod', 'joi', 'yup')\")
results = c.fetchall()
if results:
    print('✅ Layer 1 SUCCESS - Frameworks detected:')
    for row in results:
        print(f'  {row[0]} {row[1]} ({row[2]})')
else:
    print('❌ Layer 1 FAILED - No validation frameworks in database')
"
```

---

### STEP 3: Layer 2 - Validation Call Extraction

**File:** `theauditor/ast_extractors/javascript/security_extractors.js`

**Add function after extractAPIEndpoints (line 104):**

```javascript
/**
 * Extract validation framework usage (Zod, Joi, Yup, etc.)
 * Detects schema.parseAsync(), schema.validate(), etc.
 */
function extractValidationFrameworkUsage(functionCallArgs, assignments, imports) {
    const validationCalls = [];

    // Debug logging helper
    const debugLog = (msg, data) => {
        if (process.env.THEAUDITOR_VALIDATION_DEBUG === '1') {
            console.error(`[VALIDATION-L2-EXTRACT] ${msg}`);
            if (data) {
                console.error(`[VALIDATION-L2-EXTRACT]   ${JSON.stringify(data)}`);
            }
        }
    };

    // Detect which validation frameworks are imported
    const frameworks = detectValidationFrameworks(imports);
    debugLog(`Found ${frameworks.length} validation frameworks in imports`, frameworks);

    if (frameworks.length === 0) {
        return validationCalls;
    }

    // Find schema variables (const userSchema = z.object(...))
    const schemaVars = findSchemaVariables(assignments, frameworks);
    debugLog(`Found ${Object.keys(schemaVars).length} schema variables`, schemaVars);

    // Find validation method calls
    for (const call of functionCallArgs) {
        const callee = call.callee_function || '';

        // Check if this is a validation call
        if (isValidationCall(callee, frameworks, schemaVars)) {
            const validation = {
                line: call.line,
                framework: getFrameworkName(callee, frameworks, schemaVars),
                method: getMethodName(callee),
                variable_name: getVariableName(callee),
                is_validator: isValidatorMethod(callee),
                argument_expr: call.argument_expr || ''
            };

            debugLog(`Extracted validation call at line ${call.line}`, validation);
            validationCalls.push(validation);
        }
    }

    debugLog(`Total validation calls extracted: ${validationCalls.length}`);
    return validationCalls;
}

// Helper: Detect validation frameworks from imports
function detectValidationFrameworks(imports) {
    const VALIDATION_FRAMEWORKS = {
        'zod': ['z', 'zod', 'ZodSchema'],
        'joi': ['Joi', 'joi'],
        'yup': ['yup', 'Yup'],
    };

    const detected = [];
    for (const imp of imports) {
        if (!imp.module_ref) continue;

        for (const [framework, names] of Object.entries(VALIDATION_FRAMEWORKS)) {
            if (imp.module_ref.includes(framework)) {
                detected.push({ name: framework, importedNames: names });
                break;
            }
        }
    }
    return detected;
}

// Helper: Find schema variable declarations
function findSchemaVariables(assignments, frameworks) {
    const schemas = {};

    for (const assign of assignments) {
        const target = assign.target_var;
        const source = assign.source_expr || '';

        // Look for: const userSchema = z.object(...)
        for (const fw of frameworks) {
            for (const name of fw.importedNames) {
                if (source.includes(`${name}.object`) || source.includes(`${name}.string`)) {
                    schemas[target] = { framework: fw.name };
                    break;
                }
            }
        }
    }

    return schemas;
}

// Helper: Check if call is validation method
function isValidationCall(callee, frameworks, schemaVars) {
    // Pattern 1: Direct framework call (z.parse)
    for (const fw of frameworks) {
        for (const name of fw.importedNames) {
            if (callee.startsWith(`${name}.`)) {
                return isValidatorMethod(callee);
            }
        }
    }

    // Pattern 2: Schema variable call (userSchema.parse)
    if (callee.includes('.')) {
        const varName = callee.split('.')[0];
        if (varName in schemaVars) {
            return isValidatorMethod(callee);
        }
    }

    return false;
}

// Helper: Check if method is validator (not schema builder)
function isValidatorMethod(callee) {
    const VALIDATOR_METHODS = ['parse', 'parseAsync', 'safeParse', 'validate', 'validateAsync', 'validateSync', 'isValid'];
    const method = callee.split('.').pop();
    return VALIDATOR_METHODS.includes(method);
}

// Helper: Get framework name
function getFrameworkName(callee, frameworks, schemaVars) {
    // Check direct calls first
    for (const fw of frameworks) {
        for (const name of fw.importedNames) {
            if (callee.startsWith(`${name}.`)) {
                return fw.name;
            }
        }
    }

    // Check schema variables
    const varName = callee.split('.')[0];
    if (varName in schemaVars) {
        return schemaVars[varName].framework;
    }

    return 'unknown';
}

// Helper: Get method name
function getMethodName(callee) {
    return callee.split('.').pop();
}

// Helper: Get variable name (or null for direct calls)
function getVariableName(callee) {
    if (!callee.includes('.')) return null;
    const parts = callee.split('.');
    return parts.length > 1 ? parts[0] : null;
}
```

**Verification:**
```bash
cd C:/Users/santa/Desktop/plant
THEAUDITOR_VALIDATION_DEBUG=1 C:/Users/santa/Desktop/TheAuditor/.venv/Scripts/aud.exe index 2>&1 | grep "L2-EXTRACT"

# Expected output:
# [VALIDATION-L2-EXTRACT] Found 1 validation frameworks in imports
# [VALIDATION-L2-EXTRACT] Extracted validation call at line 19
#   {"line":19,"framework":"zod","method":"parseAsync","variable_name":"schema","is_validator":true}
```

---

## Debug Workflow

1. **Run with debug enabled:**
   ```bash
   cd C:/Users/santa/Desktop/plant
   THEAUDITOR_VALIDATION_DEBUG=1 C:/Users/santa/Desktop/TheAuditor/.venv/Scripts/aud.exe index 2>&1 | tee validation_debug.log
   ```

2. **Check each layer:**
   - `grep "L1-DETECT" validation_debug.log` - Framework detection
   - `grep "L2-EXTRACT" validation_debug.log` - Extraction
   - `grep "L3-TAINT" validation_debug.log` - Taint analysis

3. **Verify database:**
   - Check `frameworks` table
   - Check `validation_framework_usage` table
   - Check `symbols` table (baseline)

4. **Cross-reference with source:**
   - Open `plant/backend/src/middleware/validate.ts:19`
   - Verify line 19 has `schema.parseAsync(req.body)`
   - Confirm extraction matches reality

---

## Iteration Checklist

- [ ] Layer 1: Frameworks detected in database
- [ ] Layer 2: Validation calls extracted
- [ ] Layer 3: Taint analysis uses extracted data
- [ ] Cross-reference: Source code matches extraction
- [ ] Test: Run taint analysis, expect NO false positive
- [ ] Document: Update findings and iterate

**Next:** Start with Layer 1 implementation and debug logging.
