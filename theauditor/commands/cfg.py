"""Control Flow Graph analysis commands."""

import json
from pathlib import Path

import click

from theauditor.pipeline.ui import console
from theauditor.utils.logging import logger


@click.group()
@click.help_option("-h", "--help")
def cfg():
    """Control Flow Graph complexity analysis for maintainability and testability assessment.

    Group command for analyzing function complexity via Control Flow Graphs (CFG) - directed
    graphs mapping all possible execution paths through functions. Calculates cyclomatic
    complexity (McCabe metric), identifies unreachable code blocks, measures nesting depth,
    and visualizes control flow for refactoring candidates.

    AI ASSISTANT CONTEXT:
      Purpose: Measure function complexity for maintainability risk assessment
      Input: .pf/repo_index.db (function definitions)
      Output: Complexity metrics, dead code locations, visualizations
      Prerequisites: aud index (populates functions/classes)
      Integration: Code quality gates, refactoring prioritization, test planning
      Performance: ~5-15 seconds (AST parsing + graph construction)

    SUBCOMMANDS:
      analyze: Calculate cyclomatic complexity and detect issues
      viz:     Generate visual CFG diagrams (requires Graphviz)

    KEY METRICS:
      Cyclomatic Complexity:
        - Number of linearly independent paths through code
        - McCabe metric: edges - nodes + 2 * connected_components
        - Higher = more complex = harder to test

      Dead Code Blocks:
        - Unreachable code after return/break/continue
        - Conditions that can never be true

      Nesting Depth:
        - Maximum indentation level (nested if/for/while)
        - Deep nesting indicates high cognitive load

      Loop Complexity:
        - Nested loops and nested conditions
        - Contributes to overall complexity

    MCCABE COMPLEXITY THRESHOLDS:
      1-10:   Simple, low risk, easily testable
      11-20:  Moderate, medium risk, needs attention
      21-50:  Complex, high risk, refactor candidate
      50+:    Untestable, very high risk, immediate refactor

    EXAMPLES:
      aud cfg analyze
      aud cfg analyze --complexity-threshold 15
      aud cfg analyze --find-dead-code
      aud cfg viz --function process_payment

    PERFORMANCE: ~5-15 seconds

    RELATED COMMANDS:
      aud deadcode  # Module-level isolation
      aud graph     # File-level dependencies

    NOTE: CFG analysis is function-level (not module). For module-level dead
    code detection, use 'aud deadcode'.

    EXAMPLES:
      aud cfg analyze --workset                  # Analyze changed files only
      aud cfg viz --file auth.py --function login # Visualize login function

    Output:
      .pf/raw/cfg_analysis.json  # Complexity metrics and issues
      .pf/repo_index.db          # CFG data stored in database
        - cfg_blocks table        # Basic blocks
        - cfg_edges table         # Control flow edges

    Use Cases:
      - Code review: Find overly complex functions
      - Testing: Identify hard-to-test code
      - Refactoring: Prioritize by complexity
      - Security: Complex functions hide bugs
    """
    pass


@cfg.command("analyze")
@click.option("--db", default=".pf/repo_index.db", help="Path to repository database")
@click.option("--file", help="Analyze specific file only")
@click.option("--function", help="Analyze specific function only")
@click.option(
    "--complexity-threshold", default=10, type=int, help="Complexity threshold for reporting"
)
@click.option("--output", default="./.pf/raw/cfg_analysis.json", help="Output JSON file path")
@click.option("--find-dead-code", is_flag=True, help="Find unreachable code blocks")
@click.option("--workset", is_flag=True, help="Analyze workset files only")
def analyze(db, file, function, complexity_threshold, output, find_dead_code, workset):
    """Analyze control flow complexity and find issues.

    Examples:
        # Analyze all functions for high complexity
        aud cfg analyze --complexity-threshold 15

        # Find dead code in specific file
        aud cfg analyze --file src/auth.py --find-dead-code

        # Analyze specific function
        aud cfg analyze --function process_payment --output payment_cfg.json
    """
    from theauditor.graph.cfg_builder import CFGBuilder

    try:
        db_path = Path(db)
        if not db_path.exists():
            console.print(f"Database not found: {db}. Run 'aud full' first.", highlight=False)
            return

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
                console.print(f"Function '{function}' not found", highlight=False)
                return
            functions = matching
        elif file:
            functions = builder.get_all_functions(file_path=file)
            if not functions:
                console.print(f"No functions found in {file}", highlight=False)
                return
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
        from theauditor.utils.meta_findings import format_complexity_finding

        meta_findings = []

        for func in complex_functions:
            meta_findings.append(format_complexity_finding(func))

        repo_db_path = Path(".pf") / "repo_index.db"
        if repo_db_path.exists() and meta_findings:
            try:
                db_manager = DatabaseManager(str(repo_db_path.resolve()))
                db_manager.write_findings_batch(meta_findings, "cfg-analysis")
                db_manager.close()
                console.print(
                    f"  Wrote {len(meta_findings)} CFG findings to database", highlight=False
                )
            except Exception as e:
                console.print(
                    f"[error]  Warning: Could not write findings to database: {e}[/error]",
                    stderr=True,
                    highlight=False,
                )

        output_path = Path(".pf") / "raw" / "cfg.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
        console.print(f"\n\\[OK] CFG analysis saved to {output_path}")

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
        console.print(f"[error]Error: {e}[/error]", stderr=True, highlight=False)
        raise click.ClickException(str(e)) from e


@cfg.command("viz")
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
            console.print(f"Database not found: {db}. Run 'aud full' first.", highlight=False)
            return

        builder = CFGBuilder(str(db_path))

        console.print(f"Loading CFG for {function} in {file}...", highlight=False)
        cfg = builder.get_function_cfg(file, function)

        if not cfg["blocks"]:
            console.print(f"No CFG data found for {function} in {file}", highlight=False)
            console.print("Make sure the function was indexed with 'aud full'")
            return

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
        console.print(f"[error]Error: {e}[/error]", stderr=True, highlight=False)
        raise click.ClickException(str(e)) from e
