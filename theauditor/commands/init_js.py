"""Create or merge minimal package.json for lint/typecheck."""

import click


@click.command("init-js")
@click.option("--path", default="package.json", help="Path to package.json")
@click.option("--add-hooks", is_flag=True, help="Add TheAuditor hooks to npm scripts")
def init_js(path, add_hooks):
    """Create or merge minimal package.json for lint/typecheck."""
    from theauditor.js_init import ensure_package_json, add_auditor_hooks

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
        
        # Add hooks if requested
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