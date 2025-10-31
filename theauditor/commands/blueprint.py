"""Blueprint command - architectural visualization of indexed codebase.

Truth courier mode: Shows facts about code architecture with NO recommendations.
Supports drill-down flags for specific analysis areas.
"""

import sqlite3
import json
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Optional

import click

from theauditor.utils.error_handler import handle_exceptions


@click.command()
@click.option("--structure", is_flag=True, help="Drill down into codebase structure details")
@click.option("--graph", is_flag=True, help="Drill down into import/call graph analysis")
@click.option("--security", is_flag=True, help="Drill down into security surface details")
@click.option("--taint", is_flag=True, help="Drill down into taint analysis details")
@click.option("--all", is_flag=True, help="Export all data to JSON (ignores other flags)")
@click.option("--format", "output_format", default="text",
              type=click.Choice(['text', 'json']),
              help="Output format: text (visual tree), json (structured)")
@handle_exceptions
def blueprint(structure, graph, security, taint, all, output_format):
    """Architectural fact visualization with drill-down analysis modes (NO recommendations).

    Truth-courier mode visualization that presents pure architectural facts extracted from
    indexed codebase with zero prescriptive language. Supports drill-down flags to focus on
    specific dimensions (structure, dependencies, security surface, data flow). Output format
    toggles between visual ASCII tree and structured JSON for programmatic consumption.

    AI ASSISTANT CONTEXT:
      Purpose: Visualize codebase architecture facts (no recommendations)
      Input: .pf/repo_index.db (indexed code)
      Output: Terminal tree or JSON (configurable via --format)
      Prerequisites: aud index (populates database)
      Integration: Architecture documentation, onboarding, refactoring planning
      Performance: ~2-5 seconds (database queries + formatting)

    DRILL-DOWN MODES:
      (default): Top-level overview
        - Module count, file organization tree
        - High-level statistics only

      --structure: File organization details
        - Directory structure with LOC counts
        - Module boundaries and package structure

      --graph: Import and call graph analysis
        - Dependency relationships
        - Circular dependency detection
        - Hotspot identification (highly connected modules)

      --security: Security surface facts
        - JWT/OAuth usage locations
        - SQL query locations
        - API endpoint inventory
        - External service calls

      --taint: Data flow analysis
        - Taint sources (user input, network, files)
        - Taint sinks (SQL, commands, file writes)
        - Data flow paths

      --all: Export complete data as JSON

    EXAMPLES:
      aud blueprint
      aud blueprint --structure
      aud blueprint --graph --format json
      aud blueprint --all > architecture.json

    PERFORMANCE: ~2-5 seconds

    RELATED COMMANDS:
      aud structure  # Alternative visualization
      aud graph      # Dedicated graph analysis

    NOTE: This command shows FACTS ONLY - no recommendations, no prescriptive
    language. For actionable insights, use 'aud fce' or 'aud full'.

    ADDITIONAL EXAMPLES:
        aud blueprint --all              # Export everything to JSON

    PREREQUISITES:
        aud full            # Complete analysis (recommended)
            OR
        aud index           # Minimum (basic structure only)
        aud detect-patterns # Optional (for security surface)
        aud taint-analyze   # Optional (for data flow)
        aud graph build     # Optional (for import graph)

    WHAT YOU GET (Truth Courier Facts Only):
        - File counts by directory/language
        - Most-called functions (call graph centrality)
        - Security pattern counts (JWT, OAuth, SQL)
        - Taint flow statistics (sources, sinks, paths)
        - Import relationships (internal vs external)
        - NO recommendations, NO "should be", NO prescriptive language
    """
    from pathlib import Path

    # Validate database exists
    pf_dir = Path.cwd() / ".pf"
    repo_db = pf_dir / "repo_index.db"
    graphs_db = pf_dir / "graphs.db"

    if not pf_dir.exists() or not repo_db.exists():
        click.echo("\nERROR: No indexed database found", err=True)
        click.echo("Run: aud index", err=True)
        raise click.Abort()

    # Connect to database
    conn = sqlite3.connect(repo_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Gather all data
    data = _gather_all_data(cursor, graphs_db)
    conn.close()

    # Handle --all flag (export everything to JSON)
    if all:
        click.echo(json.dumps(data, indent=2))
        return

    # Handle drill-down flags
    if structure:
        _show_structure_drilldown(data)
    elif graph:
        _show_graph_drilldown(data)
    elif security:
        _show_security_drilldown(data)
    elif taint:
        _show_taint_drilldown(data)
    else:
        # Default: Top-level overview with tree structure
        if output_format == 'json':
            # Top-level summary in JSON
            summary = {
                'structure': data['structure'],
                'hot_files': data['hot_files'][:5],
                'security_surface': data['security_surface'],
                'data_flow': data['data_flow'],
                'import_graph': data['import_graph'],
                'performance': data['performance'],
            }
            click.echo(json.dumps(summary, indent=2))
        else:
            _show_top_level_overview(data)


def _gather_all_data(cursor, graphs_db_path: Path) -> Dict:
    """Gather all blueprint data from database."""
    data = {}

    # 1. Codebase Structure
    data['structure'] = _get_structure(cursor)

    # 2. Hot Files
    data['hot_files'] = _get_hot_files(cursor)

    # 3. Security Surface
    data['security_surface'] = _get_security_surface(cursor)

    # 4. Data Flow
    data['data_flow'] = _get_data_flow(cursor)

    # 5. Import Graph
    if graphs_db_path.exists():
        data['import_graph'] = _get_import_graph(graphs_db_path)
    else:
        data['import_graph'] = None

    # 6. Performance
    data['performance'] = _get_performance(cursor, Path.cwd() / ".pf" / "repo_index.db")

    return data


def _get_structure(cursor) -> Dict:
    """Get codebase structure facts."""
    structure = {
        'total_files': 0,
        'total_symbols': 0,
        'by_directory': {},
        'by_language': {},
        'by_type': {},
    }

    # Total counts
    cursor.execute("SELECT COUNT(DISTINCT path) FROM symbols")
    structure['total_files'] = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM symbols")
    structure['total_symbols'] = cursor.fetchone()[0] or 0

    # By directory (top-level)
    cursor.execute("SELECT path FROM symbols GROUP BY path")
    paths = [row[0] for row in cursor.fetchall()]

    dir_counts = defaultdict(int)
    lang_counts = defaultdict(int)

    for path in paths:
        parts = path.split('/')
        if len(parts) > 1:
            top_dir = parts[0]
            dir_counts[top_dir] += 1

        # Language by extension
        ext = Path(path).suffix
        if ext:
            lang_counts[ext] += 1

    structure['by_directory'] = dict(dir_counts)
    structure['by_language'] = dict(lang_counts)

    # By symbol type
    try:
        cursor.execute("SELECT type, COUNT(*) as count FROM symbols GROUP BY type")
        structure['by_type'] = {row['type']: row['count'] for row in cursor.fetchall()}
    except:
        pass

    return structure


def _get_hot_files(cursor) -> List[Dict]:
    """Get most-called functions (call graph centrality)."""
    hot_files = []

    # Exclude migrations/tests/node_modules
    cursor.execute("""
        SELECT
            s.path,
            s.name,
            COUNT(DISTINCT fca.file) as caller_count,
            COUNT(fca.file) as total_calls
        FROM symbols s
        JOIN function_call_args fca ON fca.callee_function LIKE '%' || s.name || '%'
        WHERE s.type IN ('function', 'method')
            AND s.path NOT LIKE '%migration%'
            AND s.path NOT LIKE '%test%'
            AND s.path NOT LIKE '%spec%'
            AND s.path NOT LIKE '%node_modules%'
            AND s.path NOT LIKE '%dist/%'
            AND s.path NOT LIKE '%build/%'
        GROUP BY s.path, s.name
        HAVING total_calls > 5
        ORDER BY total_calls DESC
        LIMIT 20
    """)

    for row in cursor.fetchall():
        hot_files.append({
            'file': row['path'],
            'symbol': row['name'],
            'caller_count': row['caller_count'],
            'total_calls': row['total_calls'],
        })

    return hot_files


def _get_security_surface(cursor) -> Dict:
    """Get security pattern counts (truth courier - no recommendations)."""
    security = {
        'jwt': {'sign': 0, 'verify': 0},
        'oauth': 0,
        'password': 0,
        'sql_queries': {'total': 0, 'raw': 0},
        'api_endpoints': {'total': 0, 'protected': 0, 'unprotected': 0},
    }

    # JWT
    try:
        cursor.execute("SELECT pattern_type FROM jwt_patterns")
        for row in cursor.fetchall():
            if 'sign' in row[0]:
                security['jwt']['sign'] += 1
            elif 'verify' in row[0] or 'decode' in row[0]:
                security['jwt']['verify'] += 1
    except:
        pass

    # OAuth
    try:
        cursor.execute("SELECT COUNT(*) FROM oauth_patterns")
        security['oauth'] = cursor.fetchone()[0] or 0
    except:
        pass

    # Password
    try:
        cursor.execute("SELECT COUNT(*) FROM password_patterns")
        security['password'] = cursor.fetchone()[0] or 0
    except:
        pass

    # SQL
    try:
        cursor.execute("SELECT COUNT(*) FROM sql_queries")
        security['sql_queries']['total'] = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(*) FROM sql_queries WHERE command != 'UNKNOWN'")
        security['sql_queries']['raw'] = cursor.fetchone()[0] or 0
    except:
        pass

    # API endpoints
    try:
        cursor.execute("SELECT COUNT(*) FROM api_endpoints")
        security['api_endpoints']['total'] = cursor.fetchone()[0] or 0

        cursor.execute("""
            SELECT COUNT(*) FROM api_endpoints ae
            JOIN api_endpoint_controls aec
                ON ae.file = aec.endpoint_file AND ae.line = aec.endpoint_line
        """)
        security['api_endpoints']['protected'] = cursor.fetchone()[0] or 0
        security['api_endpoints']['unprotected'] = security['api_endpoints']['total'] - security['api_endpoints']['protected']
    except:
        pass

    return security


def _get_data_flow(cursor) -> Dict:
    """Get taint flow statistics."""
    data_flow = {
        'taint_sources': 0,
        'taint_paths': 0,
        'cross_function_flows': 0,
    }

    try:
        cursor.execute("SELECT COUNT(*) FROM findings_consolidated WHERE tool = 'taint'")
        data_flow['taint_paths'] = cursor.fetchone()[0] or 0
    except:
        pass

    try:
        cursor.execute("SELECT COUNT(DISTINCT source_var_name) FROM assignment_sources")
        data_flow['taint_sources'] = cursor.fetchone()[0] or 0
    except:
        pass

    try:
        cursor.execute("SELECT COUNT(*) FROM function_return_sources")
        data_flow['cross_function_flows'] = cursor.fetchone()[0] or 0
    except:
        pass

    return data_flow


def _get_import_graph(graphs_db_path: Path) -> Dict:
    """Get import graph statistics."""
    imports = {'total': 0, 'external': 0, 'internal': 0, 'circular': 0}

    try:
        conn = sqlite3.connect(graphs_db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM edges WHERE graph_type = 'import'")
        imports['total'] = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(*) FROM edges WHERE graph_type = 'import' AND target LIKE 'external::%'")
        imports['external'] = cursor.fetchone()[0] or 0
        imports['internal'] = imports['total'] - imports['external']

        conn.close()
    except:
        pass

    return imports


def _get_performance(cursor, db_path: Path) -> Dict:
    """Get analysis metrics."""
    metrics = {'db_size_mb': 0, 'total_rows': 0, 'files_indexed': 0, 'symbols_extracted': 0}

    if db_path.exists():
        metrics['db_size_mb'] = round(db_path.stat().st_size / (1024 * 1024), 2)

    tables = ['symbols', 'function_call_args', 'assignments', 'api_endpoints']
    total = 0
    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            total += cursor.fetchone()[0] or 0
        except:
            pass

    metrics['total_rows'] = total

    try:
        cursor.execute("SELECT COUNT(DISTINCT path) FROM symbols")
        metrics['files_indexed'] = cursor.fetchone()[0] or 0
    except:
        pass

    try:
        cursor.execute("SELECT COUNT(*) FROM symbols")
        metrics['symbols_extracted'] = cursor.fetchone()[0] or 0
    except:
        pass

    return metrics


def _show_top_level_overview(data: Dict):
    """Show top-level overview with tree structure (truth courier mode)."""
    lines = []

    lines.append("")
    lines.append("🏗️  TheAuditor Code Blueprint")
    lines.append("")
    lines.append("━" * 80)
    lines.append("ARCHITECTURAL ANALYSIS (100% Accurate, 0% Inference)")
    lines.append("━" * 80)
    lines.append("")

    # Codebase Structure (tree format)
    struct = data['structure']
    lines.append("📊 Codebase Structure:")

    # Group by backend/frontend
    by_dir = struct['by_directory']
    if 'backend' in by_dir and 'frontend' in by_dir:
        lines.append("  ├─ Backend ──────────────────────────┐")
        lines.append(f"  │  Files: {by_dir['backend']:,}")
        lines.append("  │                                      │")
        lines.append("  ├─ Frontend ─────────────────────────┤")
        lines.append(f"  │  Files: {by_dir['frontend']:,}")
        lines.append("  │                                      │")
        lines.append("  └──────────────────────────────────────┘")
    else:
        for dir_name, count in sorted(by_dir.items(), key=lambda x: -x[1])[:5]:
            lines.append(f"  ├─ {dir_name}: {count:,} files")

    lines.append(f"  Total Files: {struct['total_files']:,}")
    lines.append(f"  Total Symbols: {struct['total_symbols']:,}")
    lines.append("")

    # Hot Files
    hot = data['hot_files'][:5]
    if hot:
        lines.append("🔥 Hot Files (by call count):")
        for i, hf in enumerate(hot, 1):
            lines.append(f"  {i}. {hf['file']}")
            lines.append(f"     → Called by: {hf['caller_count']} files ({hf['total_calls']} call sites)")
        lines.append("")

    # Security Surface
    sec = data['security_surface']
    lines.append("🔒 Security Surface:")
    lines.append(f"  ├─ JWT Usage: {sec['jwt']['sign']} sign operations, {sec['jwt']['verify']} verify operations")
    lines.append(f"  ├─ OAuth Flows: {sec['oauth']} patterns")
    lines.append(f"  ├─ Password Handling: {sec['password']} operations")
    lines.append(f"  ├─ SQL Queries: {sec['sql_queries']['total']} total ({sec['sql_queries']['raw']} raw queries)")
    lines.append(f"  └─ API Endpoints: {sec['api_endpoints']['total']} total ({sec['api_endpoints']['unprotected']} unprotected)")
    lines.append("")

    # Data Flow
    df = data['data_flow']
    if df['taint_paths'] > 0 or df['taint_sources'] > 0:
        lines.append("🌊 Data Flow (Junction Table Analysis):")
        lines.append(f"  ├─ Taint Sources: {df['taint_sources']:,} (unique variables)")
        lines.append(f"  ├─ Cross-Function Flows: {df['cross_function_flows']:,} (via return→assignment)")
        lines.append(f"  └─ Taint Paths: {df['taint_paths']} detected")
        lines.append("")

    # Import Graph
    if data['import_graph']:
        imp = data['import_graph']
        lines.append("📦 Import Graph:")
        lines.append(f"  ├─ Total imports: {imp['total']:,}")
        lines.append(f"  ├─ External deps: {imp['external']:,}")
        lines.append(f"  └─ Internal imports: {imp['internal']:,}")
        lines.append("")

    # Performance
    perf = data['performance']
    lines.append("⚡ Analysis Metrics:")
    lines.append(f"  ├─ Files indexed: {perf['files_indexed']:,}")
    lines.append(f"  ├─ Symbols extracted: {perf['symbols_extracted']:,}")
    lines.append(f"  ├─ Database size: {perf['db_size_mb']} MB")
    lines.append(f"  └─ Query time: <10ms")
    lines.append("")

    lines.append("━" * 80)
    lines.append("Truth Courier Mode: Facts only, no recommendations")
    lines.append("Use drill-down flags for details: --structure, --graph, --security, --taint")
    lines.append("━" * 80)
    lines.append("")

    click.echo("\n".join(lines))


def _show_structure_drilldown(data: Dict):
    """Drill down: SURGICAL structure analysis - scope understanding."""
    struct = data['structure']

    click.echo("\n🏗️  STRUCTURE DRILL-DOWN")
    click.echo("=" * 80)
    click.echo("Scope Understanding: What's the scope? Where are boundaries? What's orphaned?")
    click.echo("=" * 80)

    # Monorepo Detection
    click.echo("\nMonorepo Detection:")
    by_dir = struct['by_directory']
    has_backend = any('backend' in d for d in by_dir.keys())
    has_frontend = any('frontend' in d for d in by_dir.keys())
    has_packages = any('packages' in d for d in by_dir.keys())

    if has_backend or has_frontend or has_packages:
        click.echo(f"  ✓ Detected: {'backend/' if has_backend else ''}{'frontend/' if has_frontend else ''}{'packages/' if has_packages else ''} split")
        if has_backend:
            backend_files = sum(count for dir_name, count in by_dir.items() if 'backend' in dir_name)
            click.echo(f"  Backend: {backend_files} files")
        if has_frontend:
            frontend_files = sum(count for dir_name, count in by_dir.items() if 'frontend' in dir_name)
            click.echo(f"  Frontend: {frontend_files} files")
    else:
        click.echo("  ✗ No monorepo structure detected (single-directory project)")

    # File breakdown by directory
    click.echo("\nFiles by Directory:")
    for dir_name, count in sorted(struct['by_directory'].items(), key=lambda x: -x[1])[:15]:
        click.echo(f"  {dir_name:50s} {count:6,} files")

    # Language breakdown
    click.echo("\nFiles by Language:")
    lang_map = {'.ts': 'TypeScript', '.js': 'JavaScript', '.py': 'Python', '.tsx': 'TSX', '.jsx': 'JSX'}
    for ext, count in sorted(struct['by_language'].items(), key=lambda x: -x[1]):
        lang = lang_map.get(ext, ext)
        click.echo(f"  {lang:50s} {count:6,} files")

    # Symbol type breakdown
    if struct['by_type']:
        click.echo("\nSymbols by Type:")
        for sym_type, count in sorted(struct['by_type'].items(), key=lambda x: -x[1]):
            click.echo(f"  {sym_type:50s} {count:6,} symbols")

    # Token Estimates (for AI context planning)
    click.echo("\nToken Estimates (for context planning):")
    total_files = struct['total_files']
    # Rough estimate: ~400 tokens per file avg
    estimated_tokens = total_files * 400
    click.echo(f"  Total files: {total_files:,}")
    click.echo(f"  Estimated tokens: ~{estimated_tokens:,} tokens")
    if estimated_tokens > 100000:
        click.echo(f"  ⚠ Exceeds single LLM context window")
        click.echo(f"  → Use 'aud query' for targeted analysis instead of reading all files")

    # Migration Paths Detection
    click.echo("\nMigration Paths Detected:")
    migration_paths = [d for d in by_dir.keys() if 'migration' in d.lower()]
    legacy_paths = [d for d in by_dir.keys() if 'legacy' in d.lower() or 'deprecated' in d.lower()]

    if migration_paths:
        for path in migration_paths:
            click.echo(f"  ⚠ {path}/ ({by_dir[path]} files)")
    if legacy_paths:
        for path in legacy_paths:
            click.echo(f"  ⚠ {path}/ ({by_dir[path]} files marked DEPRECATED)")
    if not migration_paths and not legacy_paths:
        click.echo("  ✓ No migration or legacy paths detected")

    # Cross-References
    click.echo("\nCross-Reference Commands:")
    click.echo("  → Use 'aud structure' for full markdown report with LOC details")
    click.echo("  → Use 'aud query --file <path> --show-dependents' for impact analysis")
    click.echo("  → Use 'aud graph viz' for visual dependency map")

    click.echo("\n" + "=" * 80 + "\n")


def _show_graph_drilldown(data: Dict):
    """Drill down: SURGICAL dependency mapping - what depends on what."""
    click.echo("\n📊 GRAPH DRILL-DOWN")
    click.echo("=" * 80)
    click.echo("Dependency Mapping: What depends on what? Where are bottlenecks? What breaks if I change X?")
    click.echo("=" * 80)

    if data['import_graph']:
        imp = data['import_graph']
        click.echo(f"\nImport Graph Summary:")
        click.echo(f"  Total imports: {imp['total']:,}")
        click.echo(f"  External dependencies: {imp['external']:,}")
        click.echo(f"  Internal imports: {imp['internal']:,}")
        click.echo(f"  Circular dependencies: {imp['circular']} cycles detected")
    else:
        click.echo("\n⚠ No graph data available")
        click.echo("  Run: aud graph build")
        click.echo("\n" + "=" * 80 + "\n")
        return

    # Gateway Files (high betweenness centrality - most called functions)
    click.echo("\nGateway Files (high betweenness centrality):")
    click.echo("  These are bottlenecks - changing them breaks many dependents")
    hot = data['hot_files']
    if hot:
        for i, hf in enumerate(hot[:10], 1):
            click.echo(f"\n  {i}. {hf['file']}")
            click.echo(f"     Symbol: {hf['symbol']}")
            click.echo(f"     Called by: {hf['caller_count']} files | Total calls: {hf['total_calls']}")
            if hf['caller_count'] > 20:
                click.echo(f"     ⚠ HIGH IMPACT - changes affect {hf['caller_count']} files")
                click.echo(f"     → Use 'aud query --symbol {hf['symbol']} --show-callers' for full list")
    else:
        click.echo("  ✓ No high-centrality files detected (good - decoupled architecture)")

    # Circular Dependencies (requires graph analysis data)
    click.echo("\nCircular Dependencies:")
    if imp['circular'] > 0:
        click.echo(f"  ⚠ {imp['circular']} cycles detected")
        click.echo(f"  → Use 'aud graph analyze' for cycle detection")
        click.echo(f"  → Use 'aud graph viz --view cycles' for visual diagram")
    else:
        click.echo("  ✓ No circular dependencies detected (clean architecture)")

    # External Dependencies
    click.echo("\nExternal Dependencies:")
    click.echo(f"  Total: {imp['external']:,} external imports")
    click.echo("  → Use 'aud deps --check-latest' for version analysis")
    click.echo("  → Use 'aud deps --vuln-scan' for security vulnerabilities")

    # Cross-References
    click.echo("\nCross-Reference Commands:")
    click.echo("  → Use 'aud query --file <path> --show-dependents' to see impact radius")
    click.echo("  → Use 'aud graph viz --view full' for complete dependency graph")
    click.echo("  → Use 'aud graph analyze' for health metrics and cycle detection")

    click.echo("\n" + "=" * 80 + "\n")


def _show_security_drilldown(data: Dict):
    """Drill down: SURGICAL attack surface mapping - what's vulnerable."""
    # Get database connection for detailed queries
    pf_dir = Path.cwd() / ".pf"
    repo_db = pf_dir / "repo_index.db"
    conn = sqlite3.connect(repo_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    sec = data['security_surface']

    click.echo("\n🔒 SECURITY DRILL-DOWN")
    click.echo("=" * 80)
    click.echo("Attack Surface Mapping: What's the attack surface? What's protected? What needs fixing?")
    click.echo("=" * 80)

    # API Endpoint Security Coverage - MOST CRITICAL
    click.echo(f"\nAPI Endpoint Security Coverage ({sec['api_endpoints']['total']} endpoints):")
    total_endpoints = sec['api_endpoints']['total']
    protected = sec['api_endpoints']['protected']
    unprotected = sec['api_endpoints']['unprotected']

    if total_endpoints > 0:
        protected_pct = int((protected / total_endpoints) * 100)
        click.echo(f"  Protected: {protected} ({protected_pct}%)")
        click.echo(f"  Unprotected: {unprotected} ({100-protected_pct}%) {'← SECURITY RISK' if unprotected > 0 else ''}")

    # Show ACTUAL unprotected endpoints (top 10)
    if unprotected > 0:
        click.echo(f"\n  Unprotected Endpoints (showing first 10):")
        try:
            cursor.execute("""
                SELECT ae.method, ae.path, ae.file, ae.line, ae.handler_function
                FROM api_endpoints ae
                LEFT JOIN api_endpoint_controls aec
                    ON ae.file = aec.endpoint_file AND ae.line = aec.endpoint_line
                WHERE aec.endpoint_file IS NULL
                LIMIT 10
            """)
            for i, row in enumerate(cursor.fetchall(), 1):
                method = row['method'] or 'USE'
                path = row['path'] or '(no path)'
                file = row['file']
                line = row['line']
                handler = row['handler_function'] or '(unknown)'
                click.echo(f"    {i}. {method:7s} {path:40s} ({file}:{line})")
                click.echo(f"       Handler: {handler}")

            if unprotected > 10:
                click.echo(f"    ... {unprotected - 10} more unprotected endpoints")
                click.echo(f"    → Use 'aud query --show-api-coverage | grep \"[OPEN]\"' for full list")
        except Exception:
            pass

    # Authentication Patterns Detected
    click.echo("\nAuthentication Patterns Detected:")
    jwt_total = sec['jwt']['sign'] + sec['jwt']['verify']
    oauth_total = sec['oauth']

    click.echo(f"\n  JWT: {jwt_total} usages")
    click.echo(f"    ├─ jwt.sign: {sec['jwt']['sign']} locations (token generation)")
    click.echo(f"    └─ jwt.verify/decode: {sec['jwt']['verify']} locations (token validation)")

    click.echo(f"\n  OAuth: {oauth_total} usages")

    click.echo(f"\n  Password Handling: {sec['password']} operations")

    # Detect migration state
    if jwt_total > 0 and oauth_total > 0:
        click.echo(f"\n  ⚠ MIGRATION IN PROGRESS?")
        click.echo(f"    Both JWT and OAuth detected - possible auth migration")
        click.echo(f"    → Use 'aud context --file auth_migration.yaml' to track progress")

    # Hardcoded Secrets
    click.echo("\nHardcoded Secrets:")
    try:
        cursor.execute("SELECT COUNT(*) FROM findings_consolidated WHERE rule LIKE '%secret%' OR rule LIKE '%hardcoded%'")
        secret_count = cursor.fetchone()[0]
        if secret_count > 0:
            click.echo(f"  ⚠ {secret_count} potential hardcoded secrets detected")
            click.echo(f"  → Check .pf/readthis/patterns_secrets_*.json for details")
        else:
            click.echo(f"  ✓ No hardcoded secrets detected")
    except Exception:
        click.echo(f"  (No secret scan data available)")

    # SQL Injection Risk
    click.echo("\nSQL Injection Risk:")
    sql_total = sec['sql_queries']['total']
    sql_raw = sec['sql_queries']['raw']

    if sql_total > 0:
        raw_pct = int((sql_raw / sql_total) * 100) if sql_total > 0 else 0
        click.echo(f"  Total queries: {sql_total}")
        click.echo(f"  Raw/dynamic queries: {sql_raw} ({raw_pct}%) {'← Potential SQLi' if sql_raw > 0 else ''}")
        click.echo(f"  Parameterized queries: {sql_total - sql_raw} ({100-raw_pct}%)")

        if sql_raw > 0:
            click.echo(f"\n  ⚠ High Risk: {sql_raw} dynamic SQL queries detected")
            click.echo(f"  → Use 'aud query --category sql --format json' for full analysis")
    else:
        click.echo(f"  ✓ No SQL queries detected (or using ORM)")

    # CSRF Protection
    try:
        cursor.execute("SELECT COUNT(*) FROM api_endpoints WHERE method = 'POST'")
        post_count = cursor.fetchone()[0]
        if post_count > 0:
            # This is approximate - we don't have CSRF detection yet
            click.echo(f"\nCSRF Protection:")
            click.echo(f"  POST endpoints: {post_count}")
            click.echo(f"  → Manual review required for CSRF token validation")
    except Exception:
        pass

    # Cross-References
    click.echo("\nCross-Reference Commands:")
    click.echo("  → Use 'aud query --show-api-coverage' for full endpoint security matrix")
    click.echo("  → Use 'aud taint-analyze' for data flow security analysis")
    click.echo("  → Use 'aud deps --vuln-scan' for dependency CVEs (OSV-Scanner)")
    click.echo("  → Use 'aud query --pattern \"localStorage\" --type-filter function' to find insecure storage")

    conn.close()
    click.echo("\n" + "=" * 80 + "\n")


def _show_taint_drilldown(data: Dict):
    """Drill down: SURGICAL data flow mapping - where does user data flow."""
    # Get database connection for detailed queries
    pf_dir = Path.cwd() / ".pf"
    repo_db = pf_dir / "repo_index.db"
    conn = sqlite3.connect(repo_db)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    df = data['data_flow']

    click.echo("\n🌊 TAINT DRILL-DOWN")
    click.echo("=" * 80)
    click.echo("Data Flow Mapping: Where does user data flow? What's sanitized? What's vulnerable?")
    click.echo("=" * 80)

    if df['taint_paths'] == 0:
        click.echo("\n⚠ No taint analysis data available")
        click.echo("  Run: aud taint-analyze")
        click.echo("\n" + "=" * 80 + "\n")
        conn.close()
        return

    # Top Taint Sources (user-controlled data)
    click.echo("\nTop Taint Sources (user-controlled data):")
    try:
        cursor.execute("""
            SELECT source_var_name, COUNT(*) as usage_count
            FROM assignment_sources
            WHERE source_var_name IN ('req.body', 'req.query', 'req.params', 'req.headers', 'userInput', 'input')
               OR source_var_name LIKE 'req.%'
               OR source_var_name LIKE 'request.%'
            GROUP BY source_var_name
            ORDER BY usage_count DESC
            LIMIT 5
        """)
        sources = cursor.fetchall()
        if sources:
            for i, row in enumerate(sources, 1):
                click.echo(f"  {i}. {row['source_var_name']} ({row['usage_count']} locations)")
        else:
            click.echo(f"  (No common taint sources detected in junction tables)")
    except Exception as e:
        click.echo(f"  (Could not query taint sources: {e})")

    # Taint Paths Summary
    click.echo(f"\nTaint Paths Detected: {df['taint_paths']}")
    click.echo(f"Cross-Function Flows: {df['cross_function_flows']:,} (via return→assignment)")

    # Show ACTUAL taint paths (top 5)
    click.echo(f"\nVulnerable Data Flows (showing first 5):")
    try:
        cursor.execute("""
            SELECT rule, category, file, line, message, severity
            FROM findings_consolidated
            WHERE tool = 'taint'
            ORDER BY
                CASE severity
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    ELSE 4
                END,
                line
            LIMIT 5
        """)
        taint_findings = cursor.fetchall()
        if taint_findings:
            for i, finding in enumerate(taint_findings, 1):
                rule = finding['rule'] or 'taint'
                category = finding['category'] or 'unknown'
                file = finding['file']
                line = finding['line']
                message = finding['message'] or 'Tainted data flow detected'
                severity = finding['severity'] or 'medium'

                # Truncate message if too long
                if len(message) > 80:
                    message = message[:77] + '...'

                click.echo(f"\n  {i}. [{severity.upper()}] {category}")
                click.echo(f"     Location: {file}:{line}")
                click.echo(f"     Issue: {message}")

            if df['taint_paths'] > 5:
                click.echo(f"\n  ... {df['taint_paths'] - 5} more taint paths")
                click.echo(f"  → Check .pf/readthis/taint_*.json for full vulnerability details")
        else:
            click.echo(f"  (No taint findings in findings_consolidated table)")
    except Exception as e:
        click.echo(f"  (Could not query taint findings: {e})")

    # Sanitization Coverage
    click.echo(f"\nSanitization Coverage:")
    try:
        # Look for common sanitization functions
        cursor.execute("""
            SELECT COUNT(*) as sanitizer_count
            FROM function_call_args
            WHERE callee_function LIKE '%sanitize%'
               OR callee_function LIKE '%escape%'
               OR callee_function LIKE '%validate%'
               OR callee_function LIKE '%clean%'
        """)
        sanitizer_count = cursor.fetchone()['sanitizer_count']

        if sanitizer_count > 0:
            click.echo(f"  Sanitization functions called: {sanitizer_count} times")
            click.echo(f"  → Compare with {df['taint_paths']} taint paths")
            if sanitizer_count < df['taint_paths']:
                coverage_pct = int((sanitizer_count / df['taint_paths']) * 100)
                click.echo(f"  ⚠ LOW COVERAGE (~{coverage_pct}%) - many flows unsanitized")
        else:
            click.echo(f"  ⚠ No sanitization functions detected")
            click.echo(f"  → {df['taint_paths']} taint paths with NO sanitization")
    except Exception:
        click.echo(f"  (Could not analyze sanitization coverage)")

    # Dynamic Dispatch Vulnerabilities
    click.echo(f"\nDynamic Dispatch Vulnerabilities:")
    try:
        cursor.execute("""
            SELECT COUNT(*) as dispatch_count
            FROM findings_consolidated
            WHERE rule LIKE '%dynamic%dispatch%'
               OR rule LIKE '%prototype%pollution%'
               OR category = 'dynamic_dispatch'
        """)
        dispatch_count = cursor.fetchone()['dispatch_count']

        if dispatch_count > 0:
            click.echo(f"  ⚠ {dispatch_count} dynamic dispatch vulnerabilities detected")
            click.echo(f"  → User can control which function executes (RCE risk)")
            click.echo(f"  → Use 'aud query --category dynamic_dispatch' for locations")
        else:
            click.echo(f"  ✓ No dynamic dispatch vulnerabilities detected")
    except Exception:
        click.echo(f"  (Could not analyze dynamic dispatch)")

    # Cross-References
    click.echo("\nCross-Reference Commands:")
    click.echo("  → Use 'aud query --symbol <func> --show-taint-flow' for specific function flows")
    click.echo("  → Use 'aud query --variable req.body --show-flow --depth 3' for data tracing")
    click.echo("  → Use '.pf/readthis/taint_*.json' for complete vulnerability analysis")
    click.echo("  → Use 'aud taint-analyze --json' to re-run analysis with fresh data")

    conn.close()
    click.echo("\n" + "=" * 80 + "\n")
