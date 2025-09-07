"""Fetch or summarize documentation for dependencies."""

import json
import click
from pathlib import Path


@click.command("docs")
@click.argument("action", type=click.Choice(["fetch", "summarize", "view", "list"]))
@click.argument("package_name", required=False)
@click.option("--deps", default="./.pf/deps.json", help="Input dependencies file")
@click.option("--offline", is_flag=True, help="Force offline mode")
@click.option("--allow-non-gh-readmes", is_flag=True, help="Allow non-GitHub README fetching")
@click.option("--docs-dir", default="./.pf/context/docs", help="Documentation cache directory")
@click.option("--capsules-dir", default="./.pf/context/doc_capsules", help="Output capsules directory")
@click.option("--workset", default="./.pf/workset.json", help="Workset file for filtering")
@click.option("--print-stats", is_flag=True, help="Print statistics")
@click.option("--raw", is_flag=True, help="View raw fetched doc instead of capsule")
def docs(action, package_name, deps, offline, allow_non_gh_readmes, docs_dir, capsules_dir, workset, print_stats, raw):
    """Fetch or summarize documentation for dependencies."""
    from theauditor.deps import parse_dependencies
    from theauditor.docs_fetch import fetch_docs, DEFAULT_ALLOWLIST
    from theauditor.docs_summarize import summarize_docs
    
    try:
        if action == "fetch":
            # Load dependencies
            if Path(deps).exists():
                with open(deps, encoding="utf-8") as f:
                    deps_list = json.load(f)
            else:
                # Parse if not cached
                deps_list = parse_dependencies()
            
            # Set up allowlist
            allowlist = DEFAULT_ALLOWLIST.copy()
            if not allow_non_gh_readmes:
                # Already restricted to GitHub by default
                pass
            
            # Check for policy file
            policy_file = Path(".pf/policy.yml")
            allow_net = True
            if policy_file.exists():
                try:
                    # Simple YAML parsing without external deps
                    with open(policy_file, encoding="utf-8") as f:
                        for line in f:
                            if "allow_net:" in line:
                                allow_net = "true" in line.lower()
                                break
                except Exception:
                    pass  # Default to True
            
            # Fetch docs
            result = fetch_docs(
                deps_list,
                allow_net=allow_net,
                allowlist=allowlist,
                offline=offline,
                output_dir=docs_dir
            )
            
            if not print_stats:
                if result["mode"] == "offline":
                    click.echo("Running in offline mode - no documentation fetched")
                else:
                    click.echo(f"Documentation fetch complete:")
                    click.echo(f"  Fetched: {result['fetched']}")
                    click.echo(f"  Cached: {result['cached']}")
                    click.echo(f"  Skipped: {result['skipped']}")
                    if result["errors"]:
                        click.echo(f"  Errors: {len(result['errors'])}")
        
        elif action == "summarize":
            # Summarize docs
            result = summarize_docs(
                docs_dir=docs_dir,
                output_dir=capsules_dir,
                workset_path=workset if Path(workset).exists() else None
            )
            
            if not print_stats:
                click.echo(f"Documentation capsules created:")
                click.echo(f"  Capsules: {result['capsules_created']}")
                click.echo(f"  Skipped: {result['skipped']}")
                if result["errors"]:
                    click.echo(f"  Errors: {len(result['errors'])}")
                
                index_file = Path(capsules_dir).parent / "doc_index.json"
                click.echo(f"  Index: {index_file}")
        
        elif action == "list":
            # List available docs and capsules
            docs_path = Path(docs_dir)
            capsules_path = Path(capsules_dir)
            
            click.echo("\n[Docs] Available Documentation:\n")
            
            # List fetched docs
            if docs_path.exists():
                click.echo("Fetched Docs (.pf/context/docs/):")
                for ecosystem in ["npm", "py"]:
                    ecosystem_dir = docs_path / ecosystem
                    if ecosystem_dir.exists():
                        packages = sorted([d.name for d in ecosystem_dir.iterdir() if d.is_dir()])
                        if packages:
                            click.echo(f"\n  {ecosystem.upper()}:")
                            for pkg in packages[:20]:  # Show first 20
                                click.echo(f"    * {pkg}")
                            if len(packages) > 20:
                                click.echo(f"    ... and {len(packages) - 20} more")
            
            # List capsules
            if capsules_path.exists():
                click.echo("\nDoc Capsules (.pf/context/doc_capsules/):")
                capsules = sorted([f.stem for f in capsules_path.glob("*.md")])
                if capsules:
                    for capsule in capsules[:20]:  # Show first 20
                        click.echo(f"  * {capsule}")
                    if len(capsules) > 20:
                        click.echo(f"  ... and {len(capsules) - 20} more")
            
            click.echo("\n[TIP] Use 'aud docs view <package_name>' to view a specific doc")
            click.echo("   Add --raw to see the full fetched doc instead of capsule")
        
        elif action == "view":
            if not package_name:
                click.echo("Error: Package name required for view action")
                click.echo("Usage: aud docs view <package_name>")
                click.echo("       aud docs view geopandas")
                click.echo("       aud docs view numpy --raw")
                raise click.ClickException("Package name required")
            
            docs_path = Path(docs_dir)
            capsules_path = Path(capsules_dir)
            found = False
            
            if raw:
                # View raw fetched doc
                for ecosystem in ["npm", "py"]:
                    # Try exact match first
                    for pkg_dir in (docs_path / ecosystem).glob(f"{package_name}@*"):
                        if pkg_dir.is_dir():
                            doc_file = pkg_dir / "doc.md"
                            if doc_file.exists():
                                click.echo(f"\n[RAW DOC] Raw Doc: {pkg_dir.name}\n")
                                click.echo("=" * 80)
                                with open(doc_file, encoding="utf-8") as f:
                                    content = f.read()
                                    # Limit output for readability
                                    lines = content.split("\n")
                                    if len(lines) > 200:
                                        click.echo("\n".join(lines[:200]))
                                        click.echo(f"\n... (truncated, {len(lines) - 200} more lines)")
                                    else:
                                        click.echo(content)
                                found = True
                                break
                    if found:
                        break
            else:
                # View capsule (default)
                # Try exact match first
                for capsule_file in capsules_path.glob(f"*{package_name}*.md"):
                    if capsule_file.exists():
                        click.echo(f"\n[CAPSULE] Capsule: {capsule_file.stem}\n")
                        click.echo("=" * 80)
                        with open(capsule_file, encoding="utf-8") as f:
                            click.echo(f.read())
                        click.echo("\n" + "=" * 80)
                        
                        # Try to find the corresponding full doc
                        package_parts = capsule_file.stem.replace("__", "@").split("@")
                        if len(package_parts) >= 2:
                            ecosystem_prefix = package_parts[0]
                            pkg_name = "@".join(package_parts[:-1]).replace(ecosystem_prefix + "@", "")
                            version = package_parts[-1]
                            ecosystem = "py" if ecosystem_prefix == "py" else "npm"
                            full_doc_path = f"./.pf/context/docs/{ecosystem}/{pkg_name}@{version}/doc.md"
                            click.echo(f"\n[SOURCE] Full Documentation: `{full_doc_path}`")
                        
                        click.echo("[TIP] Use --raw to see the full fetched documentation")
                        found = True
                        break
            
            if not found:
                click.echo(f"No documentation found for '{package_name}'")
                click.echo("\nAvailable packages:")
                # Show some available packages
                for ecosystem in ["npm", "py"]:
                    ecosystem_dir = docs_path / ecosystem
                    if ecosystem_dir.exists():
                        packages = [d.name for d in ecosystem_dir.iterdir() if d.is_dir()][:5]
                        if packages:
                            click.echo(f"  {ecosystem.upper()}: {', '.join(packages)}")
                click.echo("\nUse 'aud docs list' to see all available docs")
    
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        raise click.ClickException(str(e)) from e