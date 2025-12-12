## 0. Verification

- [ ] 0.1 Confirm `eslint.py:53` uses `self.toolbox.get_eslint_config()` with no project detection
- [ ] 0.2 Confirm `toolbox.py:136-138` returns static sandbox path
- [ ] 0.3 Confirm `frameworks` table exists in repo_index.db with framework/version/language columns
- [ ] 0.4 Confirm `files` table has `ext` column for file extension queries
- [ ] 0.5 Confirm `.pf/temp/` directory creation pattern exists in codebase (eslint.py:138-140)

## 1. Create ConfigGenerator Class

- [ ] 1.1 Create `theauditor/linters/config_generator.py` with class skeleton and imports:
  ```python
  """Intelligent linter config generation based on project analysis."""
  import json
  import sqlite3
  from dataclasses import dataclass
  from pathlib import Path
  from theauditor.utils.logging import logger
  ```
- [ ] 1.2 Implement `__init__(self, root: Path, db_path: Path)` - store paths, open read-only DB:
  ```python
  def __init__(self, root: Path, db_path: Path):
      self.root = Path(root).resolve()
      self.db_path = Path(db_path)
      if not self.db_path.exists():
          raise RuntimeError(f"Database required for config generation: {db_path}")
      self.conn = sqlite3.connect(str(self.db_path))
      self.conn.row_factory = sqlite3.Row  # Dict-like access
  ```
- [ ] 1.3 Implement `_query_frameworks(self) -> list[dict]` - query frameworks table:
  ```python
  def _query_frameworks(self) -> list[dict]:
      cursor = self.conn.cursor()
      cursor.execute("SELECT name, version, language FROM frameworks")
      return [dict(row) for row in cursor.fetchall()]
  ```
- [ ] 1.4 Implement `_query_file_extensions(self) -> dict[str, int]` - count files by extension:
  ```python
  def _query_file_extensions(self) -> dict[str, int]:
      cursor = self.conn.cursor()
      cursor.execute("SELECT ext, COUNT(*) as count FROM files WHERE file_category='source' GROUP BY ext")
      return {row["ext"]: row["count"] for row in cursor.fetchall()}
  ```
- [ ] 1.5 Implement `_detect_project_eslint_config(self) -> Path | None` - check for existing config
- [ ] 1.6 Implement `_detect_project_tsconfig(self) -> Path | None` - check for existing tsconfig
- [ ] 1.7 Implement `_generate_tsconfig(self, frameworks: list, extensions: dict) -> str` - generate JSON content
- [ ] 1.8 Implement `_generate_eslint_config(self, frameworks: list, extensions: dict, tsconfig_path: Path) -> str` - generate CJS content
- [ ] 1.9 Implement `prepare_configs(self) -> ConfigResult` - main entry point, returns paths

## 2. Define ConfigResult Dataclass

- [ ] 2.1 Add `@dataclass ConfigResult` to config_generator.py with fields:
  - `tsconfig_path: Path` - path to tsconfig (generated or copied)
  - `eslint_config_path: Path | None` - path to generated config (None if using project config)
  - `use_project_eslint: bool` - True if project has its own eslint config

## 3. Implement tsconfig Generation

- [ ] 3.1 Define `TSCONFIG_TEMPLATE` dict with base compilerOptions
- [ ] 3.2 Add React detection: if "react" in frameworks -> `jsx: "react-jsx"`, add "DOM" to lib
- [ ] 3.3 Add Node detection: if "express"/"fastapi" in frameworks -> `module: "NodeNext"`, `types: ["node"]`
- [ ] 3.4 Add include patterns based on file extensions (.ts -> `**/*.ts`, .tsx -> `**/*.tsx`)
- [ ] 3.5 Write to `.pf/temp/tsconfig.json` using json.dumps with indent=2

## 4. Implement ESLint Config Generation

- [ ] 4.1 Define `ESLINT_CONFIG_TEMPLATE` string with placeholders
- [ ] 4.2 Add TypeScript block: if .ts/.tsx files exist -> add @typescript-eslint plugin and rules
- [ ] 4.3 Add React block: if "react" in frameworks -> add react-hooks plugin and rules
- [ ] 4.4 Add Node block: if "express"/"node" detected -> add globals.node
- [ ] 4.5 Add Browser block: if "react"/"vue" detected -> add globals.browser
- [ ] 4.6 Set parserOptions.project to point to generated/copied tsconfig
- [ ] 4.7 Write to `.pf/temp/eslint.config.cjs`

## 5. Modify Toolbox

- [ ] 5.1 Add `get_temp_dir(self) -> Path` method returning `self.root / ".pf" / "temp"`
- [ ] 5.2 Add `get_generated_tsconfig(self) -> Path` returning `self.get_temp_dir() / "tsconfig.json"`
- [ ] 5.3 Add `get_generated_eslint_config(self) -> Path` returning `self.get_temp_dir() / "eslint.config.cjs"`

## 6. Modify LinterOrchestrator

- [ ] 6.1 Import ConfigGenerator at top of linters.py
- [ ] 6.2 In `_run_async()`, before creating linter instances, call:
  ```python
  generator = ConfigGenerator(self.root, self.db.db_path)
  config_result = generator.prepare_configs()
  ```
- [ ] 6.3 Pass `config_result` to EslintLinter constructor (add parameter)

## 7. Modify EslintLinter

- [ ] 7.1 Add `config_result: ConfigResult | None = None` keyword argument to `__init__`:
  ```python
  class EslintLinter(BaseLinter):
      def __init__(self, toolbox: Toolbox, root: Path, *, config_result: ConfigResult | None = None):
          super().__init__(toolbox, root)
          self.config_result = config_result
  ```
- [ ] 7.2 In `run()`, replace config selection logic (NO FALLBACK - fail if misconfigured):
  ```python
  if self.config_result is None:
      # No ConfigGenerator was run - use static sandbox config (backward compat for direct instantiation)
      config_path = self.toolbox.get_eslint_config()
  elif self.config_result.use_project_eslint:
      # Project has its own config - omit --config flag, let ESLint auto-discover
      config_path = None
  else:
      # Use generated config
      config_path = self.config_result.eslint_config_path
  ```
- [ ] 7.3 Modify `_run_batch()` to conditionally omit `--config` flag when config_path is None:
  ```python
  cmd = [str(eslint_bin)]
  if config_path is not None:
      cmd.extend(["--config", str(config_path)])
  cmd.extend(["--format", "json", "--output-file", str(output_file), *files])
  ```

## 8. Update Package Exports

- [ ] 8.1 Add `ConfigGenerator` and `ConfigResult` to `theauditor/linters/__init__.py`

## 9. Testing

- [ ] 9.1 Run `aud full --offline` on TheAuditor itself (has no project ESLint config)
- [ ] 9.2 Run `aud full --offline` on a project WITH eslint.config.mjs (should use project config)
- [ ] 9.3 Run `aud full --offline` on a project with only package.json (should generate config)
- [ ] 9.4 Verify generated configs appear in `.pf/temp/`
- [ ] 9.5 Verify ESLint findings change (fewer false positives for TypeScript projects)

## 10. Cleanup

- [ ] 10.1 Run `ruff check theauditor/linters/` - fix any lint errors
- [ ] 10.2 Run `mypy theauditor/linters/` - fix any type errors
- [ ] 10.3 Remove any commented-out code
- [ ] 10.4 Add docstrings to all new public methods
