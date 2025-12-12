## Context

TheAuditor is a polyglot static analysis tool. The linter subsystem runs ESLint on JS/TS files using configs stored in the sandbox (`.auditor_venv/.theauditor_tools/`). Current implementation ignores project-specific ESLint configs, causing false positives when projects have TypeScript-aware rules configured.

**Constraints:**
- Must work on ANY Node.js project (with or without ESLint config)
- Must not pollute target project (no writing to project root)
- Must respect ZERO FALLBACK policy (no try/except alternative logic)
- Generated configs must be deterministic (same inputs = same outputs)

**Stakeholders:**
- Users running `aud full` on their projects
- TheAuditor maintainers

## Goals / Non-Goals

**Goals:**
- Respect project ESLint configs when they exist
- Generate intelligent configs when no project config exists
- Enable type-checked ESLint rules for TypeScript projects
- Reduce false positives from config mismatch

**Non-Goals:**
- Supporting every ESLint plugin (focus on: typescript-eslint, react, unicorn)
- Merging project config with TheAuditor baseline (too complex)
- Caching generated configs across runs (regenerate is cheap)
- Modifying any project files

## Decisions

### Decision 1: Project config detection order

**What:** Check for project ESLint config in this order:
1. `eslint.config.js` (flat config, ESM)
2. `eslint.config.mjs` (flat config, ESM explicit)
3. `eslint.config.cjs` (flat config, CommonJS)
4. `eslint.config.ts` (flat config, TypeScript)
5. `.eslintrc.js` (legacy)
6. `.eslintrc.cjs` (legacy CommonJS)
7. `.eslintrc.json` (legacy JSON)
8. `.eslintrc.yaml` / `.eslintrc.yml` (legacy YAML)

**Why:** ESLint 9+ prefers flat config. Check modern formats first. This is the order ESLint itself uses for auto-discovery.

**Alternatives considered:**
- Let ESLint auto-discover by omitting `--config` flag
- Rejected: ESLint might find configs in parent directories outside project scope

### Decision 2: Generated config location

**What:** Write all generated configs to `.pf/temp/` directory.

**Why:**
- `.pf/` is already TheAuditor's data directory (contains `repo_index.db`, `graphs.db`)
- `temp/` subdirectory already exists for temporary files
- Isolated from project source code
- Easy cleanup (delete `.pf/temp/` contents)

**Alternatives considered:**
- Write to sandbox (`.auditor_venv/.theauditor_tools/temp/`)
- Rejected: Configs need project-relative paths, sandbox is fixed location

### Decision 3: tsconfig.json generation strategy

**What:** Generate minimal tsconfig that enables type-checked ESLint rules.

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "<detected>",       // NodeNext for backend, ESNext for frontend
    "moduleResolution": "<detected>", // NodeNext or Bundler
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "jsx": "<if-react>",          // react-jsx if React detected
    "lib": ["ES2020", "<if-browser>"] // Add DOM if frontend
  },
  "include": ["**/*.ts", "**/*.tsx"], // Based on actual file extensions
  "exclude": ["node_modules", "dist", "build", ".pf"]
}
```

**Why:**
- Minimal config that works for type-checking without full compilation
- `skipLibCheck: true` avoids errors from node_modules type declarations
- `strict: true` matches modern TypeScript defaults
- Include patterns based on actual files found (no assumptions)

**Alternatives considered:**
- Copy project tsconfig if exists, generate only if missing
- ACCEPTED: This is the actual implementation - copy first, generate as fallback

### Decision 4: ESLint config generation strategy

**What:** Generate CommonJS flat config (`eslint.config.cjs`) with detected plugins.

**Generation approach:** String concatenation of config blocks based on detection results.

```python
# In config_generator.py
ESLINT_HEADER = '''const globals = require("globals");
const js = require("@eslint/js");
'''

TYPESCRIPT_IMPORTS = '''const typescript = require("@typescript-eslint/eslint-plugin");
const typescriptParser = require("@typescript-eslint/parser");
'''

REACT_IMPORTS = '''const reactHooks = require("eslint-plugin-react-hooks");
'''

ESLINT_BASE = '''module.exports = [
  js.configs.recommended,
  { ignores: ["node_modules/**", "dist/**", "build/**", ".pf/**"] },
'''

TYPESCRIPT_BLOCK = '''  {
    files: ["**/*.ts", "**/*.tsx"],
    languageOptions: {
      parser: typescriptParser,
      parserOptions: {
        project: "./tsconfig.json",
        tsconfigRootDir: __dirname,
      },
    },
    plugins: { "@typescript-eslint": typescript },
    rules: {
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/explicit-function-return-type": "warn",
    },
  },
'''

REACT_BLOCK = '''  {
    files: ["**/*.jsx", "**/*.tsx"],
    plugins: { "react-hooks": reactHooks },
    rules: {
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
    },
  },
'''

NODE_GLOBALS_BLOCK = '''  {
    files: ["**/*.js", "**/*.ts"],
    languageOptions: { globals: globals.node },
  },
'''

BROWSER_GLOBALS_BLOCK = '''  {
    files: ["**/*.jsx", "**/*.tsx"],
    languageOptions: { globals: globals.browser },
  },
'''

def _generate_eslint_config(self, frameworks: list, extensions: dict, tsconfig_path: Path) -> str:
    has_ts = ".ts" in extensions or ".tsx" in extensions
    has_react = any(f["name"] == "react" for f in frameworks)
    has_node = any(f["name"] in ("express", "fastapi", "node") for f in frameworks)

    parts = [ESLINT_HEADER]
    if has_ts:
        parts.append(TYPESCRIPT_IMPORTS)
    if has_react:
        parts.append(REACT_IMPORTS)

    parts.append(ESLINT_BASE)
    if has_ts:
        parts.append(TYPESCRIPT_BLOCK)
    if has_react:
        parts.append(REACT_BLOCK)
    if has_node:
        parts.append(NODE_GLOBALS_BLOCK)
    elif has_react:  # Browser only if React without Node
        parts.append(BROWSER_GLOBALS_BLOCK)

    parts.append("];")
    return "".join(parts)
```

**Exact rules included:**

| Plugin | Rule | Severity | Why |
|--------|------|----------|-----|
| @typescript-eslint | no-unused-vars | error | Catches dead code, respects `_` prefix |
| @typescript-eslint | no-explicit-any | error | Enforces type safety |
| @typescript-eslint | explicit-function-return-type | warn | Improves readability |
| react-hooks | rules-of-hooks | error | Prevents hooks misuse |
| react-hooks | exhaustive-deps | warn | Catches stale closures |

**Why these specific rules:**
- Minimal set that catches real bugs without noise
- All have low false-positive rates
- Match common project configurations
- Already used in TheAuditor's bundled configs

**Why:**
- CommonJS format works with all Node.js versions
- Flat config is ESLint 9+ standard
- Only include plugins for detected frameworks (smaller config)
- All required packages already installed in sandbox node_modules
- `tsconfigRootDir: __dirname` resolves paths relative to generated config location

**Alternatives considered:**
- Generate ESM config (.mjs)
- Rejected: Node.js ESM support varies, CJS is universal

### Decision 5: No fallback on detection failure

**What:** If framework detection fails or database is unavailable, generate minimal baseline config. Do NOT fall back to sandbox config.

**Why:** ZERO FALLBACK policy. One code path. Generated config is the path, even if minimal.

**Implementation:**
```python
# CORRECT - Single path
config = self.generate_config()  # Returns minimal if detection fails
return config

# WRONG - Fallback
try:
    config = self.generate_config()
except Exception:
    config = self.toolbox.get_eslint_config()  # FORBIDDEN
```

## Data Flow

```
LinterOrchestrator._run_async()
    |
    v
ConfigGenerator.prepare_configs(root, db_path)
    |
    +-- Query database for frameworks, file extensions
    |
    +-- Check for existing project configs
    |       |
    |       +-- tsconfig.json exists? -> copy to .pf/temp/
    |       +-- eslint.config.* exists? -> return path (use project config)
    |
    +-- Generate missing configs
    |       |
    |       +-- _generate_tsconfig() -> .pf/temp/tsconfig.json
    |       +-- _generate_eslint_config() -> .pf/temp/eslint.config.cjs
    |
    +-- Return ConfigResult(tsconfig_path, eslint_config_path, use_project_eslint)
    |
    v
EslintLinter.run(files)
    |
    +-- If use_project_eslint: omit --config flag
    +-- Else: use generated eslint_config_path
```

## File Structure

```
theauditor/linters/
    __init__.py          # Add ConfigGenerator export
    config_generator.py  # NEW - ~200 lines
    eslint.py            # MODIFIED - config selection logic
    linters.py           # MODIFIED - call ConfigGenerator before linting
    base.py              # UNCHANGED
    ruff.py              # UNCHANGED
    ...

theauditor/utils/
    toolbox.py           # MODIFIED - add generated config getters
```

## Risks / Trade-offs

### Risk 1: Generated tsconfig incompatible with project
**Mitigation:** Use minimal, permissive settings. `skipLibCheck: true` avoids most compatibility issues. If type errors occur, they're from ESLint type-checking, not blocking analysis.

### Risk 2: Missing ESLint plugins in sandbox
**Mitigation:** Only generate config blocks for plugins already installed in sandbox. Current sandbox has: `@typescript-eslint/*`, `eslint-plugin-react`, `eslint-plugin-react-hooks`, `eslint-plugin-unicorn`.

### Risk 3: Performance overhead from config generation
**Mitigation:** Generation is fast (<100ms). Database queries are single-shot. No external process spawning during generation.

## Migration Plan

1. Add `ConfigGenerator` class (new file, no changes to existing behavior)
2. Add toolbox methods (additive, backward compatible)
3. Modify `LinterOrchestrator` to call generator (behavior change, but controlled)
4. Modify `EslintLinter` to use generated/project config (behavior change)

**Rollback:** Delete `config_generator.py`, revert other file changes. Git provides full history.

## Open Questions

None. Design is complete and ready for implementation.
