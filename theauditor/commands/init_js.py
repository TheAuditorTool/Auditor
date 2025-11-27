"""Create or merge minimal package.json for lint/typecheck."""

import click


@click.command("init-js", hidden=True)
@click.option("--path", default="package.json", help="Path to package.json")
@click.option("--add-hooks", is_flag=True, help="Add TheAuditor hooks to npm scripts")
def init_js(path, add_hooks):
    """Create or merge minimal JavaScript/TypeScript project configuration with linting and type-checking setup.

    Scaffolds or updates package.json with ESLint, TypeScript, and Prettier configurations optimized
    for static analysis. Idempotent operation that merges with existing configuration, never overwrites.
    Optionally adds TheAuditor npm script hooks for pre-commit validation workflows.

    AI ASSISTANT CONTEXT:
      Purpose: Bootstrap JavaScript/TypeScript projects with analysis tooling
      Input: Existing package.json (if present) or create new
      Output: package.json with devDependencies and scripts for lint/typecheck
      Prerequisites: None (creates from scratch if needed)
      Integration: Enables 'aud lint' for JavaScript/TypeScript projects
      Performance: ~1-2 seconds (file I/O only, no npm install)

    WHAT IT CREATES:
      DevDependencies (with PIN_ME placeholders):
        - eslint: JavaScript linter
        - @typescript-eslint/parser: TypeScript parser for ESLint
        - @typescript-eslint/eslint-plugin: TypeScript-specific rules
        - prettier: Code formatter
        - typescript: TypeScript compiler (for type checking)

      NPM Scripts:
        - "lint": "eslint . --ext .js,.jsx,.ts,.tsx"
        - "typecheck": "tsc --noEmit"
        - "format": "prettier --write ."

      TheAuditor Hooks (if --add-hooks):
        - "precommit": "aud workset --diff HEAD && aud lint --workset"
        - "prepush": "aud full --workset"

    HOW IT WORKS (Configuration Merging):
      1. File Detection:
         - Checks if package.json exists at --path
         - Reads existing JSON if present

      2. Configuration Merging:
         - Preserves existing dependencies and scripts
         - Adds missing devDependencies (marked PIN_ME)
         - Merges lint/typecheck scripts (non-destructive)
         - Never overwrites user-defined values

      3. Hook Integration (if --add-hooks):
         - Adds TheAuditor scripts to npm scripts
         - Integrates with git workflow (precommit, prepush)
         - Skips if hooks already present

      4. File Write:
         - Writes formatted JSON (2-space indent)
         - Atomic write (temp file + rename)
         - Preserves file permissions

    EXAMPLES:
      # Use Case 1: Create minimal package.json from scratch
      aud init-js

      # Use Case 2: Merge with existing package.json
      aud init-js --path ./frontend/package.json

      # Use Case 3: Add TheAuditor pre-commit hooks
      aud init-js --add-hooks

      # Use Case 4: Initialize monorepo workspace
      aud init-js --path ./packages/api/package.json

    COMMON WORKFLOWS:
      New JavaScript Project Setup:
        aud init-js --add-hooks && npm install

      Add Analysis to Existing Project:
        aud init-js && npm install && aud lint

      Monorepo Initialization:
        for pkg in packages/*; do aud init-js --path $pkg/package.json; done

    OUTPUT FILES:
      package.json (created or updated)  # NPM configuration file
      Existing files preserved, no deletions

    OUTPUT FORMAT (package.json additions):
      {
        "devDependencies": {
          "eslint": "PIN_ME",
          "@typescript-eslint/parser": "PIN_ME",
          "@typescript-eslint/eslint-plugin": "PIN_ME",
          "prettier": "PIN_ME",
          "typescript": "PIN_ME"
        },
        "scripts": {
          "lint": "eslint . --ext .js,.jsx,.ts,.tsx",
          "typecheck": "tsc --noEmit",
          "format": "prettier --write .",
          "precommit": "aud workset --diff HEAD && aud lint --workset",
          "prepush": "aud full --workset"
        }
      }

    PERFORMANCE EXPECTATIONS:
      All cases: ~1-2 seconds (file I/O only, no npm install triggered)

    FLAG INTERACTIONS:
      Mutually Exclusive:
        None (all flags can be combined)

      Recommended Combinations:
        --add-hooks                      # Enable pre-commit validation
        --path <custom> --add-hooks      # Configure specific package.json

      Flag Modifiers:
        --path: Custom package.json location (default: ./package.json)
        --add-hooks: Adds TheAuditor npm scripts for git workflow

    PREREQUISITES:
      Required:
        Write permissions in target directory

      Optional:
        Node.js (for running npm install after init)
        Git repository (for --add-hooks to be useful)

    EXIT CODES:
      0 = Success, package.json created or updated
      1 = File write error (permission denied)
      2 = JSON parse error (corrupted existing package.json)

    RELATED COMMANDS:
      aud init               # Python project initialization
      aud lint               # Runs ESLint on JavaScript/TypeScript
      aud init-config        # Creates mypy configuration

    SEE ALSO:
      aud lint --help        # Understand linting workflow
      aud workset --help     # Learn about targeted analysis

    TROUBLESHOOTING:
      Error: "Permission denied" writing package.json:
        -> Run from directory where you have write permissions
        -> Check file ownership: ls -la package.json
        -> Use sudo only if absolutely necessary (not recommended)

      Warning: "PIN_ME" placeholders in devDependencies:
        -> Edit package.json to set exact versions (e.g., "^8.0.0")
        -> Run 'npm install' to install dependencies
        -> Check npm registry for latest stable versions

      Existing package.json corrupted after init:
        -> package.json should be backed up automatically
        -> Check for .bak file: ls package.json.bak
        -> Validate JSON: cat package.json | jq .

      Hooks not working after --add-hooks:
        -> Verify git repository: git status
        -> Check npm scripts are defined: npm run precommit --if-present
        -> Hooks run via npm lifecycle, not git hooks

      TypeScript errors after initialization:
        -> Create tsconfig.json if missing: npx tsc --init
        -> Configure "include" and "exclude" patterns
        -> Run 'npm run typecheck' to verify setup

    NOTE: This command does NOT run 'npm install' - you must install dependencies
    manually after initialization. PIN_ME placeholders must be replaced with actual
    version numbers before running npm install.
    """
    click.echo("WARNING: 'aud init-js' is deprecated and will be removed in v2.0.")
    click.echo("         Package.json scaffolding is not part of security auditing.")
    click.echo("")

    from theauditor.js_init import add_auditor_hooks, ensure_package_json

    try:
        res = ensure_package_json(path)

        if res["status"] == "created":
            click.echo(f"[OK] Created {path} with PIN_ME placeholders")
            click.echo("  Edit devDependencies to set exact versions")
        elif res["status"] == "merged":
            click.echo(f"[OK] Merged lint/typecheck config into {path}")
            click.echo("  Check devDependencies for PIN_ME placeholders")
        else:
            click.echo(f"No changes needed - {path} already configured")

        if add_hooks:
            click.echo("\nAdding TheAuditor hooks to npm scripts...")
            hook_res = add_auditor_hooks(path)

            if hook_res["status"] == "hooks_added":
                click.echo("[OK] Added TheAuditor hooks to package.json:")
                for change in hook_res["details"]:
                    click.echo(f"  - {change}")
            elif hook_res["status"] == "unchanged":
                click.echo("No changes needed - all hooks already present")
            elif hook_res["status"] == "error":
                click.echo(f"Error adding hooks: {hook_res['message']}", err=True)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.ClickException(str(e)) from e
