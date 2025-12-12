# linter-config Specification

## Purpose
TBD - created by archiving change refactor-intelligent-linter-config. Update Purpose after archive.
## Requirements
### Requirement: Project ESLint Config Detection

The system SHALL detect existing ESLint configurations in the target project before running ESLint analysis.

Detection SHALL check for these files in order (first match wins):
1. `eslint.config.js`
2. `eslint.config.mjs`
3. `eslint.config.cjs`
4. `eslint.config.ts`
5. `eslint.config.mts`
6. `eslint.config.cts`
7. `.eslintrc.js`
8. `.eslintrc.cjs`
9. `.eslintrc.yaml`
10. `.eslintrc.yml`
11. `.eslintrc.json`
12. `.eslintrc`

When a project ESLint config is found, the system SHALL use the project's config instead of generating one.

#### Scenario: Project has eslint.config.mjs
- **WHEN** target project contains `eslint.config.mjs` in root directory
- **THEN** system detects project config and sets `use_project_eslint = True`
- **AND** ESLint runs without explicit `--config` flag (auto-discovery)
- **AND** no generated config is written to `.pf/temp/`

#### Scenario: Project has legacy .eslintrc.json
- **WHEN** target project contains `.eslintrc.json` but no flat config
- **THEN** system detects legacy config and sets `use_project_eslint = True`
- **AND** ESLint uses project's legacy config

#### Scenario: Project has no ESLint config
- **WHEN** target project contains no ESLint config files
- **THEN** system sets `use_project_eslint = False`
- **AND** system generates intelligent config based on project analysis

### Requirement: tsconfig.json Generation

The system SHALL generate a minimal `tsconfig.json` for TypeScript projects that enables type-checked ESLint rules.

Generation SHALL occur when:
1. Target project has no `tsconfig.json` in root
2. Target project contains `.ts` or `.tsx` files

Generated tsconfig SHALL be written to `.pf/temp/tsconfig.json`.

#### Scenario: TypeScript project without tsconfig
- **WHEN** project has `.ts` files but no `tsconfig.json`
- **THEN** system generates tsconfig with `strict: true`, `skipLibCheck: true`
- **AND** include patterns match actual file extensions found
- **AND** generated file is written to `.pf/temp/tsconfig.json`

#### Scenario: React TypeScript project
- **WHEN** project has `.tsx` files AND React framework detected
- **THEN** generated tsconfig includes `jsx: "react-jsx"`
- **AND** lib array includes `"DOM"`

#### Scenario: Node.js TypeScript project
- **WHEN** project has `.ts` files AND Express/Fastify framework detected
- **THEN** generated tsconfig includes `module: "NodeNext"`
- **AND** types array includes `"node"`

#### Scenario: Project already has tsconfig.json
- **WHEN** project contains `tsconfig.json` in root
- **THEN** system copies project tsconfig to `.pf/temp/tsconfig.json`
- **AND** no generation occurs

### Requirement: ESLint Config Generation

The system SHALL generate an intelligent ESLint configuration based on detected frameworks and file types.

Generation SHALL occur when:
1. Target project has no ESLint config (detection returned None)
2. ConfigGenerator is invoked during linter orchestration

Generated config SHALL be CommonJS format (`.cjs`) for Node.js compatibility.

#### Scenario: TypeScript project without ESLint config
- **WHEN** project has `.ts` files but no ESLint config
- **THEN** generated config includes `@typescript-eslint/eslint-plugin`
- **AND** generated config includes `@typescript-eslint/parser`
- **AND** parserOptions.project is set to `"./tsconfig.json"`
- **AND** parserOptions.tsconfigRootDir is set to `__dirname` (config file location)
- **AND** rules include:
  - `@typescript-eslint/no-unused-vars`: `["error", { argsIgnorePattern: "^_" }]`
  - `@typescript-eslint/no-explicit-any`: `"error"`
  - `@typescript-eslint/explicit-function-return-type`: `"warn"`

#### Scenario: React project without ESLint config
- **WHEN** project has React framework detected but no ESLint config
- **THEN** generated config includes `eslint-plugin-react-hooks`
- **AND** generated config includes `globals.browser`
- **AND** rules include:
  - `react-hooks/rules-of-hooks`: `"error"`
  - `react-hooks/exhaustive-deps`: `"warn"`

#### Scenario: Node.js project without ESLint config
- **WHEN** project has Express/Fastify framework detected but no ESLint config
- **THEN** generated config includes `globals.node`

#### Scenario: Plain JavaScript project
- **WHEN** project has only `.js` files (no TypeScript)
- **THEN** generated config does NOT include TypeScript plugins
- **AND** generated config uses base ESLint recommended rules only

### Requirement: Config Isolation

The system SHALL write all generated configuration files to `.pf/temp/` directory.

The system SHALL NOT modify any files in the target project root or source directories.

#### Scenario: Generated files location
- **WHEN** ConfigGenerator generates tsconfig.json and eslint.config.cjs
- **THEN** files are written to `.pf/temp/tsconfig.json` and `.pf/temp/eslint.config.cjs`
- **AND** no files are created in project root
- **AND** no files are created in project source directories

#### Scenario: Temp directory creation
- **WHEN** `.pf/temp/` directory does not exist
- **THEN** system creates the directory before writing configs
- **AND** directory creation does not raise errors

### Requirement: Framework-Aware Configuration

The system SHALL query the `frameworks` table in `repo_index.db` to determine detected frameworks.

The system SHALL query the `files` table to determine file extension distribution.

Configuration generation SHALL be deterministic: same frameworks and files produce identical configs.

#### Scenario: Query frameworks table
- **WHEN** ConfigGenerator initializes with database path
- **THEN** system executes `SELECT name, version, language FROM frameworks`
- **AND** results are returned as list of dicts: `[{"name": "react", "version": "18.2.0", "language": "javascript"}, ...]`
- **AND** results inform config generation decisions

#### Scenario: Query file extensions
- **WHEN** ConfigGenerator prepares configs
- **THEN** system executes `SELECT ext, COUNT(*) as count FROM files WHERE file_category='source' GROUP BY ext`
- **AND** results are returned as dict: `{".ts": 150, ".tsx": 45, ".js": 30}`
- **AND** extension counts inform include patterns

#### Scenario: Database not available
- **WHEN** ConfigGenerator is initialized with non-existent database path
- **THEN** system raises `RuntimeError` with message "Database required for config generation: {path}"
- **AND** linter orchestration fails immediately (ZERO FALLBACK)
- **AND** no generated configs are written

#### Scenario: Deterministic generation
- **WHEN** same project is analyzed twice
- **THEN** generated configs are byte-for-byte identical
- **AND** no randomness or timestamps in generated content

### Requirement: Integration with LinterOrchestrator

The system SHALL invoke ConfigGenerator before running any linters.

ConfigResult SHALL be passed to EslintLinter to control config selection.

#### Scenario: Orchestrator invokes generator
- **WHEN** LinterOrchestrator._run_async() executes
- **THEN** ConfigGenerator.prepare_configs() is called before linter instantiation
- **AND** ConfigResult is available for EslintLinter

#### Scenario: EslintLinter uses ConfigResult
- **WHEN** EslintLinter receives ConfigResult with use_project_eslint=True
- **THEN** ESLint command omits `--config` flag
- **WHEN** EslintLinter receives ConfigResult with use_project_eslint=False
- **THEN** ESLint command uses `--config <generated_path>`

