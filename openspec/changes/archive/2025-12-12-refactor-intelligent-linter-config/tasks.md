## 0. Verification

- [x] 0.1 Confirm `eslint.py:53` uses `self.toolbox.get_eslint_config()` with no project detection
- [x] 0.2 Confirm `toolbox.py:136-138` returns static sandbox path
- [x] 0.3 Confirm `frameworks` table exists in repo_index.db with name/version/language columns
- [x] 0.4 Confirm `files` table has `ext` column for file extension queries
- [x] 0.5 Confirm `.pf/temp/` directory creation pattern exists in codebase (eslint.py:138-140)

## 1. Create ConfigGenerator Class

- [x] 1.1 Create `theauditor/linters/config_generator.py` with class skeleton and imports
- [x] 1.2 Implement `__init__(self, root: Path, db_path: Path)` - store paths, open DB
- [x] 1.3 Implement `_query_frameworks(self) -> list[dict]` - query frameworks table
- [x] 1.4 Implement `_query_file_extensions(self) -> dict[str, int]` - count files by extension
- [x] 1.5 Implement `_detect_project_eslint_config(self) -> Path | None` - check for existing config
- [x] 1.6 Implement `_detect_project_tsconfig(self) -> Path | None` - check for existing tsconfig
- [x] 1.7 Implement `_generate_tsconfig(self, frameworks: list, extensions: dict) -> str` - generate JSON content
- [x] 1.8 Implement `_generate_eslint_config(self, frameworks: list, extensions: dict, tsconfig_path: Path) -> str` - generate CJS content
- [x] 1.9 Implement `prepare_configs(self) -> ConfigResult` - main entry point, returns paths

## 2. Define ConfigResult Dataclass

- [x] 2.1 Add `@dataclass ConfigResult` to config_generator.py with fields:
  - `tsconfig_path: Path` - path to tsconfig (generated or copied)
  - `eslint_config_path: Path | None` - path to generated config (None if using project config)
  - `use_project_eslint: bool` - True if project has its own eslint config

## 3. Implement tsconfig Generation

- [x] 3.1 Define base compilerOptions in `_generate_tsconfig`
- [x] 3.2 Add React detection: if "react" in frameworks -> `jsx: "react-jsx"`, add "DOM" to lib
- [x] 3.3 Add Node detection: if "express"/"fastify" in frameworks -> `module: "NodeNext"`, `types: ["node"]`
- [x] 3.4 Add include patterns based on file extensions (.ts -> `**/*.ts`, .tsx -> `**/*.tsx`)
- [x] 3.5 Write to `.pf/temp/tsconfig.json` using json.dumps with indent=2

## 4. Implement ESLint Config Generation

- [x] 4.1 Use string concatenation approach per design.md
- [x] 4.2 Add TypeScript block: if .ts/.tsx files exist -> add @typescript-eslint plugin and rules
- [x] 4.3 Add React block: if "react" in frameworks -> add react-hooks plugin and rules
- [x] 4.4 Add Node block: if "express"/"node" detected -> add globals.node
- [x] 4.5 Add Browser block: if "react" detected (without node) -> add globals.browser
- [x] 4.6 Set parserOptions.project to point to generated/copied tsconfig
- [x] 4.7 Write to `.pf/temp/eslint.config.cjs`

## 5. Modify Toolbox

- [x] 5.1 Add `get_temp_dir(self) -> Path` method returning `self.root / ".pf" / "temp"`
- [x] 5.2 Add `get_generated_tsconfig(self) -> Path` returning `self.get_temp_dir() / "tsconfig.json"`
- [x] 5.3 Add `get_generated_eslint_config(self) -> Path` returning `self.get_temp_dir() / "eslint.config.cjs"`

## 6. Modify LinterOrchestrator

- [x] 6.1 Import ConfigGenerator at top of linters.py
- [x] 6.2 In `_run_async()`, before creating linter instances, call ConfigGenerator.prepare_configs()
- [x] 6.3 Pass `config_result` to EslintLinter constructor (add parameter)

## 7. Modify EslintLinter

- [x] 7.1 Add `config_result: ConfigResult | None = None` keyword argument to `__init__`
- [x] 7.2 In `run()`, replace config selection logic (NO FALLBACK - fail if misconfigured)
- [x] 7.3 Modify `_run_batch()` and `_create_batches()` to handle config_path=None

## 8. Update Package Exports

- [x] 8.1 Add `ConfigGenerator` and `ConfigResult` to `theauditor/linters/__init__.py`

## 9. Testing

- [x] 9.1 Run `aud full --offline` on TheAuditor itself (has no project ESLint config)
- [ ] 9.2 Run `aud full --offline` on a project WITH eslint.config.mjs (should use project config) - deferred
- [ ] 9.3 Run `aud full --offline` on a project with only package.json (should generate config) - deferred
- [x] 9.4 Verify generated configs appear in `.pf/temp/`
- [x] 9.5 Verify ESLint config generation is intelligent (React+Node detected correctly)

## 10. Cleanup

- [x] 10.1 Run `ruff check theauditor/linters/` - all checks passed
- [x] 10.2 Run `mypy` - only pre-existing errors remain
- [x] 10.3 No commented-out code introduced
- [x] 10.4 All public methods have docstrings
