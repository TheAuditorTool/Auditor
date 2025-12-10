"""Control Flow Graph analysis commands."""

import json
from pathlib import Path

import click

from theauditor.cli import RichCommand, RichGroup
from theauditor.pipeline.ui import console, err_console
from theauditor.utils.logging import logger


@click.group(cls=RichGroup)
@click.help_option("-h", "--help")
def cfg():
    """Control Flow Graph complexity analysis.

    Analyzes function complexity via CFG - calculates cyclomatic complexity (McCabe),
    identifies unreachable code, measures nesting depth.

    AI ASSISTANT CONTEXT:
      Purpose: Analyze control flow graph complexity and detect unreachable code
      Input: .pf/repo_index.db (after aud full)
      Output: Console or JSON (--json), DOT/SVG diagrams (viz subcommand)
      Prerequisites: aud full (populates CFG data in database)
      Integration: Use after aud full to identify complex functions needing refactoring

    SUBCOMMANDS:
      analyze: Calculate complexity and detect dead code
      viz:     Generate DOT diagrams (requires Graphviz)

    COMPLEXITY THRESHOLDS:
      1-10: Simple | 11-20: Moderate | 21-50: Complex | 50+: Refactor immediately

    EXAMPLES:
      aud cfg analyze --complexity-threshold 15
      aud cfg analyze --find-dead-code --workset
      aud cfg viz --file auth.py --function login

    SEE ALSO:
      aud manual cfg   Learn about control flow graph analysis
    """
    pass


@cfg.command("analyze", cls=RichCommand)
@click.option("--db", default=".pf/repo_index.db", help="Path to repository database")
@click.option("--file", help="Analyze specific file only")
@click.option("--function", help="Analyze specific function only")
@click.option(
    "--complexity-threshold", default=10, type=int, help="Complexity threshold for reporting"
)
@click.option("--find-dead-code", is_flag=True, help="Find unreachable code blocks")
@click.option("--workset", is_flag=True, help="Analyze workset files only")
def analyze(db, file, function, complexity_threshold, find_dead_code, workset):
    """Analyze control flow complexity and find issues.

    Examples:
        # Analyze all functions for high complexity
        aud cfg analyze --complexity-threshold 15

        # Find dead code in specific file
        aud cfg analyze --file src/auth.py --find-dead-code

        # Analyze specific function
        aud cfg analyze --function process_payment
    """
    from theauditor.graph.cfg_builder import CFGBuilder

    try:
        db_path = Path(db)
        if not db_path.exists():
            raise click.ClickException(f"Database not found: {db}. Run 'aud full' first.")

        builder = CFGBuilder(str(db_path))

        target_files = None
        if workset:
            workset_path = Path(".pf/workset.json")
            if workset_path.exists():
                with open(workset_path) as f:
                    workset_data = json.load(f)
                    target_files = {p["path"] for p in workset_data.get("paths", [])}
                    console.print(f"Analyzing {len(target_files)} workset files", highlight=False)

        if function:
            functions = builder.get_all_functions()
            matching = [f for f in functions if f["function_name"] == function]
            if not matching:
                raise click.ClickException(f"Function '{function}' not found")
            functions = matching
        elif file:
            functions = builder.get_all_functions(file_path=file)
            if not functions:
                raise click.ClickException(f"No functions found in {file}")
        else:
            functions = builder.get_all_functions()

            if target_files:
                functions = [f for f in functions if f["file"] in target_files]

        console.print(f"Analyzing {len(functions)} functions...", highlight=False)

        results = {
            "total_functions": len(functions),
            "complex_functions": [],
            "dead_code": [],
            "statistics": {
                "avg_complexity": 0,
                "max_complexity": 0,
                "functions_above_threshold": 0,
            },
        }

        complex_functions = builder.analyze_complexity(
            file_path=file, threshold=complexity_threshold
        )

        results["complex_functions"] = complex_functions
        results["statistics"]["functions_above_threshold"] = len(complex_functions)

        if complex_functions:
            complexities = [f["complexity"] for f in complex_functions]
            results["statistics"]["max_complexity"] = max(complexities)
            results["statistics"]["avg_complexity"] = sum(complexities) / len(complexities)

        if complex_functions:
            console.print(
                f"\n\\[COMPLEXITY] Found {len(complex_functions)} functions above threshold {complexity_threshold}:",
                highlight=False,
            )
            for func in complex_functions[:10]:
                console.print(f"  • {func['function']} ({func['file']})", highlight=False)
                console.print(
                    f"    Complexity: {func['complexity']}, Blocks: {func['block_count']}, Has loops: {func['has_loops']}",
                    highlight=False,
                )
        else:
            console.print(
                f"[success]No functions exceed complexity threshold {complexity_threshold}[/success]"
            )

        if find_dead_code:
            console.print("\n\\[DEAD CODE] Searching for unreachable blocks...")
            dead_blocks = builder.find_dead_code(file_path=file)
            results["dead_code"] = dead_blocks

            if dead_blocks:
                console.print(f"Found {len(dead_blocks)} unreachable blocks:", highlight=False)

                by_function = {}
                for block in dead_blocks:
                    key = f"{block['function']} ({block['file']})"
                    if key not in by_function:
                        by_function[key] = []
                    by_function[key].append(block)

                for func_key, blocks in list(by_function.items())[:5]:
                    console.print(
                        f"  • {func_key}: {len(blocks)} unreachable blocks", highlight=False
                    )
                    for block in blocks[:2]:
                        console.print(
                            f"    - {block['block_type']} block at lines {block['start_line']}-{block['end_line']}",
                            highlight=False,
                        )
            else:
                console.print("[success]No unreachable code detected[/success]")

        from theauditor.indexer.database import DatabaseManager
        from theauditor.utils.findings import format_complexity_finding

        meta_findings = []

        for func in complex_functions:
            meta_findings.append(format_complexity_finding(func))

        repo_db_path = Path(".pf") / "repo_index.db"
        if repo_db_path.exists() and meta_findings:
            db_manager = DatabaseManager(str(repo_db_path.resolve()))
            db_manager.write_findings_batch(meta_findings, "cfg-analysis")
            db_manager.close()
            console.print(f"  Wrote {len(meta_findings)} CFG findings to database", highlight=False)

        console.print("\n\\[SUMMARY]")
        console.print(f"  Total functions analyzed: {len(functions)}", highlight=False)
        console.print(
            f"  Functions above complexity {complexity_threshold}: {len(complex_functions)}",
            highlight=False,
        )
        if complex_functions:
            console.print(
                f"  Maximum complexity: {results['statistics']['max_complexity']}", highlight=False
            )
            console.print(
                f"  Average complexity of complex functions: {results['statistics']['avg_complexity']:.1f}",
                highlight=False,
            )
        if find_dead_code:
            console.print(
                f"  Unreachable blocks found: {len(results['dead_code'])}", highlight=False
            )

        builder.close()

    except Exception as e:
        logger.error(f"CFG analysis failed: {e}")
        err_console.print(f"[error]Error: {e}[/error]", highlight=False)
        raise click.ClickException(str(e)) from e


@cfg.command("viz", cls=RichCommand)
@click.option("--db", default=".pf/repo_index.db", help="Path to repository database")
@click.option("--file", required=True, help="File containing the function")
@click.option("--function", required=True, help="Function name to visualize")
@click.option("--output", help="Output file path (default: function_name.dot)")
@click.option(
    "--format", type=click.Choice(["dot", "svg", "png"]), default="dot", help="Output format"
)
@click.option("--show-statements", is_flag=True, help="Include statements in blocks")
@click.option("--highlight-paths", is_flag=True, help="Highlight execution paths")
def viz(db, file, function, output, format, show_statements, highlight_paths):
    """Visualize control flow graph for a function.

    Examples:
        # Generate DOT file for a function
        aud cfg viz --file src/auth.py --function validate_token

        # Generate SVG with statements shown
        aud cfg viz --file src/payment.py --function process_payment --format svg --show-statements

        # Highlight execution paths
        aud cfg viz --file src/api.py --function handle_request --highlight-paths
    """
    from theauditor.graph.cfg_builder import CFGBuilder

    try:
        db_path = Path(db)
        if not db_path.exists():
            raise click.ClickException(f"Database not found: {db}. Run 'aud full' first.")

        builder = CFGBuilder(str(db_path))

        console.print(f"Loading CFG for {function} in {file}...", highlight=False)
        cfg = builder.get_function_cfg(file, function)

        if not cfg["blocks"]:
            raise click.ClickException(
                f"No CFG data found for {function} in {file}. Run 'aud full' first."
            )

        console.print(
            f"Found {len(cfg['blocks'])} blocks and {len(cfg['edges'])} edges", highlight=False
        )

        if show_statements:
            dot_content = builder.export_dot(file, function)

            for block in cfg["blocks"]:
                if block["statements"]:
                    old_label = f"{block['type']}\\n{block['start_line']}-{block['end_line']}"
                    stmt_lines = [f"{s['type']}@{s['line']}" for s in block["statements"][:3]]
                    stmt_str = "\\n".join(stmt_lines)
                    new_label = f"{old_label}\\n{stmt_str}"
                    dot_content = dot_content.replace(old_label, new_label)
        else:
            dot_content = builder.export_dot(file, function)

        if highlight_paths:
            paths = builder.get_execution_paths(file, function, max_paths=5)
            if paths:
                console.print(
                    f"Found {len(paths)} execution paths (showing first 5)", highlight=False
                )

                for i, path in enumerate(paths[:5]):
                    console.print(f"  Path {i + 1}: {' → '.join(map(str, path))}", highlight=False)

        if not output:
            output = f"{function}_cfg.{format}"
        elif not output.endswith(f".{format}"):
            output = f"{output}.{format}"

        output_path = Path(output)

        if format == "dot":
            with open(output_path, "w") as f:
                f.write(dot_content)
            console.print(f"[success]DOT file saved to {output_path}[/success]")
            console.print(
                f"  View with: dot -Tsvg {output_path} -o {output_path.stem}.svg", highlight=False
            )
        else:
            import subprocess

            dot_path = output_path.with_suffix(".dot")
            with open(dot_path, "w") as f:
                f.write(dot_content)

            try:
                result = subprocess.run(
                    ["dot", f"-T{format}", str(dot_path), "-o", str(output_path)],
                    capture_output=True,
                    text=True,
                )

                if result.returncode == 0:
                    console.print(f"[success]{format.upper()} saved to {output_path}[/success]")

                    dot_path.unlink()
                else:
                    console.print(f"[error]Graphviz failed: {result.stderr}[/error]")
                    console.print(f"  DOT file saved to {dot_path}", highlight=False)
            except FileNotFoundError:
                console.print(
                    "[error]Graphviz not installed. Install it to generate images:[/error]"
                )
                console.print("  Ubuntu/Debian: apt install graphviz")
                console.print("  macOS: brew install graphviz")
                console.print("  Windows: choco install graphviz")
                console.print(f"\n  DOT file saved to {dot_path}", highlight=False)
                console.print(
                    f"  Manual generation: dot -T{format} {dot_path} -o {output_path}",
                    highlight=False,
                )

        metrics = cfg["metrics"]
        console.print("\n\\[METRICS]")
        console.print(
            f"  Cyclomatic Complexity: {metrics['cyclomatic_complexity']}", highlight=False
        )
        console.print(f"  Decision Points: {metrics['decision_points']}", highlight=False)
        console.print(f"  Maximum Nesting: {metrics['max_nesting_depth']}", highlight=False)
        console.print(f"  Has Loops: {metrics['has_loops']}", highlight=False)

        builder.close()

    except Exception as e:
        logger.error(f"CFG visualization failed: {e}")
        err_console.print(f"[error]Error: {e}[/error]", highlight=False)
        raise click.ClickException(str(e)) from e
