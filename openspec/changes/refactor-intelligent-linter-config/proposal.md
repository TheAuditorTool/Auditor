## Why

TheAuditor's ESLint integration currently uses a static bundled config (`eslint.config.cjs`) that ignores project-specific ESLint configurations. This causes:

1. **False positives**: Projects with `@typescript-eslint/no-unused-vars` configured get flagged by base ESLint's `no-unused-vars` (406 false positives in PlantPro)
2. **Duplicate findings**: Both TheAuditor's rules AND leaked project rules fire
3. **Missing type-checked rules**: The bundled tsconfig.json only covers sandbox files, not target project files
4. **Wasted signal**: Real issues buried under noise from incompatible configs

**Root Cause**: `eslint.py:53` always calls `self.toolbox.get_eslint_config()` which returns the static sandbox config. No project config detection. No intelligent config generation.

## What Changes

1. **NEW**: `ConfigGenerator` class in `theauditor/linters/config_generator.py`
   - Generates tsconfig.json based on project analysis (frameworks, file extensions, dependencies)
   - Generates eslint.config.cjs based on detected frameworks and TypeScript presence
   - Writes generated configs to `.pf/temp/` (isolated, not polluting project)

2. **MODIFIED**: `EslintLinter` in `theauditor/linters/eslint.py`
   - Detect project ESLint config first (respect user's choices)
   - If no project config: use generated config from ConfigGenerator
   - If no TypeScript: skip type-checked rules entirely

3. **MODIFIED**: `Toolbox` in `theauditor/utils/toolbox.py`
   - Add `get_generated_eslint_config()` method returning `.pf/temp/eslint.config.cjs`
   - Add `get_generated_tsconfig()` method returning `.pf/temp/tsconfig.json`

4. **MODIFIED**: `LinterOrchestrator` in `theauditor/linters/linters.py`
   - Before running linters, invoke ConfigGenerator to prepare configs
   - Pass project root and database path to generator

## Impact

- **Affected specs**: NEW capability `linter-config` (this is new functionality, not modifying existing spec)
- **Affected code**:
  - `theauditor/linters/config_generator.py` (NEW - ~200 lines)
  - `theauditor/linters/eslint.py` (MODIFIED - ~30 lines changed)
  - `theauditor/linters/linters.py` (MODIFIED - ~10 lines added)
  - `theauditor/utils/toolbox.py` (MODIFIED - ~15 lines added)
- **No breaking changes**: Existing behavior preserved for projects without configs
- **Risk**: Medium - linter integration is critical path, but changes are additive

## Evidence From Source Code

### Current State (Problem)

**eslint.py:53** - Always uses static config:
```python
config_path = self.toolbox.get_eslint_config()
```

**toolbox.py:136-138** - Returns sandbox config:
```python
def get_eslint_config(self) -> Path:
    return self.sandbox / "eslint.config.cjs"
```

**eslint.config.cjs:45-50** - Has hardcoded paths:
```javascript
files: ["**/frontend/src/**/*.js", "**/frontend/src/**/*.tsx", ...]
```

### Available Intelligence (What We Can Use)

**framework_detector.py** - Already detects:
- React, Express, FastAPI, Flask, Django, Vue, Next.js, etc.
- Parses package.json, pyproject.toml, Cargo.toml
- Returns `detected_frameworks` list with framework, version, language

**Database** - Already indexed:
- `frameworks` table: name, version, language, path, source
- `files` table: path, ext, loc, file_category
- Can query file extension counts: `.ts`, `.tsx`, `.js`, `.jsx`

### Config Generation Logic

```
IF project has tsconfig.json:
    COPY to .pf/temp/tsconfig.json
ELSE IF has TypeScript files:
    GENERATE tsconfig.json based on:
        - Has React in deps -> jsx: "react-jsx", lib: ["DOM"]
        - Has Express/Node -> module: "NodeNext", types: ["node"]
        - Has .tsx files -> include: ["**/*.tsx"]
    WRITE to .pf/temp/tsconfig.json

IF project has eslint.config.*:
    USE project config (omit --config flag)
ELSE:
    GENERATE eslint.config.cjs based on:
        - Has TypeScript -> @typescript-eslint rules
        - Has React -> react-hooks, react-refresh plugins
        - Has Node -> globals.node
        - Has browser code -> globals.browser
    WRITE to .pf/temp/eslint.config.cjs
    USE generated config
```

## Non-Goals

- **NOT** merging project config with TheAuditor config (complexity explosion)
- **NOT** supporting every ESLint plugin (focus on common ones: typescript-eslint, react, unicorn)
- **NOT** modifying project files (all generated configs go to `.pf/temp/`)
