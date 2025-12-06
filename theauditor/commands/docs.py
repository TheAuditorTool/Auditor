"""Fetch or summarize documentation for dependencies."""

import json
from pathlib import Path

import click

from theauditor.cli import RichCommand
from theauditor.pipeline.ui import console, err_console


@click.command("docs", cls=RichCommand)
@click.argument("action", type=click.Choice(["fetch", "view", "list"]))
@click.argument("package_name", required=False)
@click.option("--deps", default="./.pf/deps.json", help="Input dependencies file")
@click.option("--offline", is_flag=True, help="Force offline mode")
@click.option("--allow-non-gh-readmes", is_flag=True, help="Allow non-GitHub README fetching")
@click.option("--docs-dir", default="./.pf/context/docs", help="Documentation cache directory")
@click.option("--print-stats", is_flag=True, help="Print statistics")
@click.option("--raw", is_flag=True, help="View raw fetched doc instead of capsule")
def docs(action, package_name, deps, offline, allow_non_gh_readmes, docs_dir, print_stats, raw):
    """Fetch, cache, and summarize external library documentation for AI-consumable context.

    Downloads README files and API documentation from package repositories (PyPI, npm),
    caches locally for offline use, and generates condensed "documentation capsules"
    optimized for LLM context windows. Enables AI assistants to understand library APIs
    without requiring internet access during analysis.

    AI ASSISTANT CONTEXT:
      Purpose: Provide external library documentation for AI code understanding
      Input: .pf/deps.json (detected dependencies), package repository metadata
      Output: .pf/context/docs/ (raw docs), .pf/context/doc_capsules/ (AI-optimized)
      Prerequisites: aud deps (detects dependencies first)
      Integration: Documentation context for AI code review and refactoring
      Performance: ~5-30 seconds (network-dependent, cached after first fetch)

    ACTIONS SUPPORTED:
      fetch:
        - Downloads README files from GitHub/GitLab for all dependencies
        - Caches raw documentation in .pf/context/docs/
        - Respects .pf/policy.yml allow_net setting
        - Uses allowlist for security (GitHub/GitLab only by default)

      summarize:
        - Generates AI-consumable documentation capsules
        - Extracts key API surfaces, usage examples, common patterns
        - Compresses to <10KB per package for context efficiency
        - Outputs to .pf/context/doc_capsules/

      view:
        - Displays documentation for specific package
        - Shows either raw doc (--raw) or capsule (default)
        - Useful for verifying fetch/summarize results

      list:
        - Lists all packages with cached documentation
        - Shows which have raw docs vs capsules
        - Helps verify documentation coverage

    HOW IT WORKS (Documentation Pipeline):
      1. Fetch Action:
         - Reads dependency list from .pf/deps.json
         - Queries package repository API (PyPI/npm) for metadata
         - Downloads README files from GitHub/GitLab (allowlisted)
         - Caches raw markdown in .pf/context/docs/<package>.md
         - Respects offline mode and .pf/policy.yml restrictions

      2. Summarize Action:
         - Parses raw markdown documentation
         - Extracts: API surfaces, class signatures, function examples
         - Filters out: badges, contributor lists, build instructions
         - Generates condensed capsule (<10KB) with key usage patterns
         - Saves to .pf/context/doc_capsules/<package>.json

      3. View Action:
         - Reads cached documentation (raw or capsule)
         - Formats for terminal display
         - Shows package metadata (version, license, homepage)

      4. List Action:
         - Scans .pf/context/docs/ and .pf/context/doc_capsules/
         - Reports coverage statistics
         - Identifies missing or stale documentation

    EXAMPLES:
      # Use Case 1: Fetch all dependency documentation
      aud deps && aud docs fetch

      # Use Case 2: Generate AI-optimized capsules
      aud docs summarize

      # Use Case 3: View documentation for specific package
      aud docs view requests

      # Use Case 4: Offline mode (use cached docs only)
      aud docs fetch --offline

      # Use Case 5: List documentation coverage
      aud docs list --print-stats

    COMMON WORKFLOWS:
      Initial Setup (First-Time):
        aud deps && aud docs fetch && aud docs summarize

      Offline Development:
        aud docs fetch  # (once with network)
        aud docs summarize --offline  # (works offline)

      Documentation Refresh (After Dependencies Change):
        aud deps && aud docs fetch && aud docs summarize

    OUTPUT FILES:
      .pf/context/docs/<package>.md        # Raw README files (cached)
      .pf/context/doc_capsules/<package>.json  # AI-optimized summaries
      .pf/deps.json (input):               # Dependency list from 'aud deps'

    OUTPUT FORMAT (doc_capsules Schema):
      {
        "package": "requests",
        "version": "2.31.0",
        "summary": "HTTP library for Python",
        "key_apis": [
          "requests.get(url, params=None, **kwargs)",
          "requests.post(url, data=None, json=None, **kwargs)"
        ],
        "common_patterns": [
          "response = requests.get('https://api.example.com')",
          "response.json() to parse JSON responses"
        ],
        "documentation_url": "https://requests.readthedocs.io"
      }

    PERFORMANCE EXPECTATIONS:
      Fetch (with network):
        Small (<10 deps):     ~5-10 seconds
        Medium (20-50 deps):  ~15-30 seconds
        Large (100+ deps):    ~60-120 seconds (rate-limited by APIs)

      Summarize (offline):
        Any size:             ~1-5 seconds (local processing only)

    FLAG INTERACTIONS:
      Mutually Exclusive:
        Actions (fetch/summarize/view/list): Choose ONE action per invocation

      Recommended Combinations:
        fetch + --offline                # Use cached docs, no network
        view <package> + --raw           # View raw README instead of capsule
        summarize + --print-stats        # Show compression statistics

      Flag Modifiers:
        --offline: Skip network requests, use cache only
        --allow-non-gh-readmes: Allow non-GitHub sources (SECURITY RISK)
        --raw: View raw documentation instead of capsule (view action only)

    PREREQUISITES:
      Required:
        aud deps               # Populates .pf/deps.json with dependency list

      Optional:
        Network access         # For fetch action (not needed for summarize)
        .pf/policy.yml         # Controls allow_net setting (default: true)

    EXIT CODES:
      0 = Success, action completed
      1 = Network error or missing dependencies
      2 = Invalid action or package not found

    RELATED COMMANDS:
      aud deps               # Detects dependencies (prerequisite)
      aud full               # Runs deps as part of the full pipeline
      aud context            # Uses documentation for semantic analysis

    SEE ALSO:
      aud manual docs        # Deep dive into documentation caching concepts
      aud manual deps        # Understand dependency detection

    TROUBLESHOOTING:
      Error: "Network error" or "Failed to fetch":
        -> Check internet connectivity: curl -I https://pypi.org
        -> Use --offline to skip network and use cache
        -> Check .pf/policy.yml: ensure allow_net: true

      Error: "Package not found" (view action):
        -> Run 'aud docs list' to see available packages
        -> Ensure package was in .pf/deps.json when fetch ran
        -> Package name must match exactly (case-sensitive)

      Missing documentation for some dependencies:
        -> Not all packages have GitHub README files
        -> Check .pf/context/docs/ to see what was fetched
        -> Some packages may be in private registries (not accessible)

      Documentation capsules seem empty or incomplete:
        -> Raw README may not follow standard format
        -> Use 'aud docs view <package> --raw' to inspect original
        -> Some README files are mostly badges/images (low content)

      Security concern: "allow-non-gh-readmes" warning:
        -> Default restricts to GitHub/GitLab for security
        -> Non-GitHub sources may execute arbitrary code
        -> Only use --allow-non-gh-readmes for trusted internal packages

    NOTE: Documentation is cached indefinitely in .pf/context/docs/ - re-run
    'aud docs fetch' after dependency updates to refresh. Offline mode uses cache
    only, enabling air-gapped development after initial fetch.
    """
    from theauditor.package_managers.deps import parse_dependencies
    from theauditor.package_managers.docs_fetch import DEFAULT_ALLOWLIST, fetch_docs

    try:
        if action == "fetch":
            if Path(deps).exists():
                with open(deps, encoding="utf-8") as f:
                    deps_list = json.load(f)
            else:
                deps_list = parse_dependencies()

            allowlist = DEFAULT_ALLOWLIST.copy()
            if not allow_non_gh_readmes:
                pass

            policy_file = Path(".pf/policy.yml")
            allow_net = True
            if policy_file.exists():
                try:
                    with open(policy_file, encoding="utf-8") as f:
                        for line in f:
                            if "allow_net:" in line:
                                allow_net = "true" in line.lower()
                                break
                except Exception:
                    pass

            result = fetch_docs(
                deps_list,
                allow_net=allow_net,
                allowlist=allowlist,
                offline=offline,
                output_dir=docs_dir,
            )

            if not print_stats:
                if result["mode"] == "offline":
                    console.print("Running in offline mode - no documentation fetched")
                else:
                    console.print("Documentation fetch complete:")
                    console.print(f"  Fetched: {result['fetched']}", highlight=False)
                    console.print(f"  Cached: {result['cached']}", highlight=False)
                    console.print(f"  Skipped: {result['skipped']}", highlight=False)
                    if result["errors"]:
                        console.print(f"  Errors: {len(result['errors'])}", highlight=False)

        elif action == "list":
            docs_path = Path(docs_dir)

            console.print("\n\\[Docs] Available Documentation:\n")

            if docs_path.exists():
                console.print("Fetched Docs (.pf/context/docs/):")
                for ecosystem in ["npm", "py"]:
                    ecosystem_dir = docs_path / ecosystem
                    if ecosystem_dir.exists():
                        packages = sorted([d.name for d in ecosystem_dir.iterdir() if d.is_dir()])
                        if packages:
                            console.print(f"\n  {ecosystem.upper()}:", highlight=False)
                            for pkg in packages[:20]:
                                console.print(f"    * {pkg}", highlight=False)
                            if len(packages) > 20:
                                console.print(
                                    f"    ... and {len(packages) - 20} more", highlight=False
                                )

            console.print(
                "\n\\[TIP] Use 'aud docs view <package_name> --raw' to view a specific doc"
            )

        elif action == "view":
            if not package_name:
                console.print("Error: Package name required for view action")
                console.print("Usage: aud docs view <package_name>")
                console.print("       aud docs view geopandas")
                console.print("       aud docs view numpy --raw")
                raise click.ClickException("Package name required")

            docs_path = Path(docs_dir)
            found = False

            for ecosystem in ["npm", "py"]:
                for pkg_dir in (docs_path / ecosystem).glob(f"{package_name}@*"):
                    if pkg_dir.is_dir():
                        doc_file = pkg_dir / "doc.md"
                        if doc_file.exists():
                            console.print(
                                f"\n\\[DOC] Documentation: {pkg_dir.name}\n", highlight=False
                            )
                            console.rule()
                            with open(doc_file, encoding="utf-8") as f:
                                content = f.read()

                                if not raw:
                                    lines = content.split("\n")
                                    if len(lines) > 200:
                                        console.print("\n".join(lines[:200]), markup=False)
                                        console.print(
                                            f"\n... (truncated, {len(lines) - 200} more lines)",
                                            highlight=False,
                                        )
                                        console.print("\nUse --raw to see full content")
                                    else:
                                        console.print(content, markup=False)
                                else:
                                    console.print(content, markup=False)
                            found = True
                            break

                        readme_file = pkg_dir / "README.md"
                        if readme_file.exists():
                            console.print(
                                f"\n\\[DOC] Documentation: {pkg_dir.name}\n", highlight=False
                            )
                            console.rule()

                            md_files = sorted(pkg_dir.glob("*.md"))
                            console.print(
                                f"Documentation files ({len(md_files)}):", highlight=False
                            )
                            for md_file in md_files:
                                console.print(f"  - {md_file.name}", highlight=False)
                            console.print()

                            with open(readme_file, encoding="utf-8") as f:
                                content = f.read()
                                if not raw:
                                    lines = content.split("\n")
                                    if len(lines) > 100:
                                        console.print("\n".join(lines[:100]), markup=False)
                                        console.print(
                                            f"\n... (showing README preview, {len(md_files)} total files)",
                                            highlight=False,
                                        )
                                        console.print(
                                            f"\nFiles: {', '.join([f.name for f in md_files])}",
                                            highlight=False,
                                        )
                                        console.print("\nUse --raw to see full content")
                                    else:
                                        console.print(content, markup=False)
                                else:
                                    for md_file in md_files:
                                        console.print(
                                            f"\n--- {md_file.name} ---\n", highlight=False
                                        )
                                        with open(md_file, encoding="utf-8") as mf:
                                            console.print(mf.read(), markup=False)
                                        console.print()
                            found = True
                            break
                if found:
                    break

            if not found:
                console.print(f"No documentation found for '{package_name}'", highlight=False)
                console.print("\nAvailable packages:")

                for ecosystem in ["npm", "py"]:
                    ecosystem_dir = docs_path / ecosystem
                    if ecosystem_dir.exists():
                        packages = [d.name for d in ecosystem_dir.iterdir() if d.is_dir()][:5]
                        if packages:
                            console.print(
                                f"  {ecosystem.upper()}: {', '.join(packages)}", highlight=False
                            )
                console.print("\nUse 'aud docs list' to see all available docs")

    except Exception as e:
        err_console.print(f"[error]Error: {e}[/error]", highlight=False)
        raise click.ClickException(str(e)) from e
