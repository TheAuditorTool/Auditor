"""Refactoring impact analysis command.

This command analyzes the impact of refactoring changes and detects
inconsistencies between frontend and backend, API contract mismatches,
and data model evolution issues.
"""

import json
import os
import sqlite3
from pathlib import Path
from typing import Dict, List, Set, Any, Optional

import click


@click.command()
@click.option("--file", "-f", help="File to analyze refactoring impact from")
@click.option("--line", "-l", type=int, help="Line number in the file")
@click.option("--migration-dir", "-m", default="backend/migrations", 
              help="Directory containing database migrations")
@click.option("--migration-limit", "-ml", type=int, default=0,
              help="Number of recent migrations to analyze (0=all, default=all)")
@click.option("--expansion-mode", "-e", 
              type=click.Choice(["none", "direct", "full"]),
              default="none",
              help="Dependency expansion mode: none (affected only), direct (1 level), full (transitive)")
@click.option("--auto-detect", "-a", is_flag=True, 
              help="Auto-detect refactoring from recent migrations")
@click.option("--workset", "-w", is_flag=True,
              help="Use current workset for analysis")
@click.option("--output", "-o", type=click.Path(),
              help="Output file for detailed report")
def refactor(file: Optional[str], line: Optional[int], migration_dir: str,
             migration_limit: int, expansion_mode: str,
             auto_detect: bool, workset: bool, output: Optional[str]) -> None:
    """Analyze refactoring impact and find inconsistencies.
    
    This command helps detect issues introduced by refactoring such as:
    - Data model changes (fields moved between tables)
    - API contract mismatches (frontend expects old structure)
    - Missing updates in dependent code
    - Cross-stack inconsistencies
    
    Examples:
        # Analyze impact from a specific model change
        aud refactor --file models/Product.ts --line 42
        
        # Auto-detect refactoring from migrations
        aud refactor --auto-detect
        
        # Analyze current workset
        aud refactor --workset
    """
    
    # Find repository root
    repo_root = Path.cwd()
    while repo_root != repo_root.parent:
        if (repo_root / ".git").exists():
            break
        repo_root = repo_root.parent
    
    pf_dir = repo_root / ".pf"
    db_path = pf_dir / "repo_index.db"
    
    if not db_path.exists():
        click.echo("Error: No index found. Run 'aud index' first.", err=True)
        raise click.Abort()
    
    # Import components here to avoid import errors
    try:
        from theauditor.impact_analyzer import analyze_impact
        from theauditor.universal_detector import UniversalPatternDetector
        from theauditor.pattern_loader import PatternLoader
        from theauditor.fce import run_fce
    except ImportError as e:
        click.echo(f"Error importing components: {e}", err=True)
        raise click.Abort()
    # Initialize components
    pattern_loader = PatternLoader()
    pattern_detector = UniversalPatternDetector(
        repo_root, 
        pattern_loader,
        exclude_patterns=[]
    )
    
    click.echo("\nRefactoring Impact Analysis")
    click.echo("-" * 60)
    
    # Step 1: Determine what to analyze
    affected_files = set()
    
    if auto_detect:
        click.echo("Auto-detecting refactoring from migrations...")
        affected_files.update(_analyze_migrations(repo_root, migration_dir, migration_limit))
        
        if not affected_files:
            click.echo("No affected files found from migrations.")
            click.echo("Tip: Check if your migrations contain schema change operations")
            return
        
    elif workset:
        click.echo("Analyzing workset files...")
        workset_file = pf_dir / "workset.json"
        if workset_file.exists():
            with open(workset_file, 'r') as f:
                workset_data = json.load(f)
                affected_files.update(workset_data.get("files", []))
        else:
            click.echo("Error: No workset found. Create one with 'aud workset'", err=True)
            raise click.Abort()
            
    elif file and line:
        click.echo(f"Analyzing impact from {file}:{line}...")
        
        # Run impact analysis
        impact_result = analyze_impact(
            db_path=str(db_path),
            target_file=file,
            target_line=line,
            trace_to_backend=True
        )
        
        if not impact_result.get("error"):
            # Extract affected files from impact analysis
            upstream_files = [dep["file"] for dep in impact_result.get("upstream", [])]
            downstream_files = [dep["file"] for dep in impact_result.get("downstream", [])]
            upstream_trans_files = [dep["file"] for dep in impact_result.get("upstream_transitive", [])]
            downstream_trans_files = [dep["file"] for dep in impact_result.get("downstream_transitive", [])]
            
            all_impact_files = set(upstream_files + downstream_files + upstream_trans_files + downstream_trans_files)
            affected_files.update(all_impact_files)
            
            # Show immediate impact
            summary = impact_result.get("impact_summary", {})
            click.echo(f"\nDirect impact: {summary.get('direct_upstream', 0)} upstream, "
                      f"{summary.get('direct_downstream', 0)} downstream")
            click.echo(f"Total files affected: {summary.get('affected_files', len(affected_files))}")
            
            # Check for cross-stack impact
            if impact_result.get("cross_stack_impact"):
                click.echo("\n⚠️  Cross-stack impact detected!")
                for impact in impact_result["cross_stack_impact"]:
                    click.echo(f"  • {impact['file']}:{impact['line']} - {impact['type']}")
    else:
        click.echo("Error: Specify --file and --line, --auto-detect, or --workset", err=True)
        raise click.Abort()
    
    if not affected_files:
        click.echo("No files to analyze.")
        return
    
    # Step 2b: Expand affected files based on mode
    if affected_files:
        expanded_files = _expand_affected_files(
            affected_files, 
            str(db_path), 
            expansion_mode,
            repo_root
        )
    else:
        expanded_files = set()
    
    # Update workset with expanded files
    click.echo(f"\nCreating workset from {len(expanded_files)} files...")
    temp_workset_file = pf_dir / "temp_workset.json"
    with open(temp_workset_file, 'w') as f:
        json.dump({"files": list(expanded_files)}, f)
    
    # Step 3: Run pattern detection with targeted file list
    if expanded_files:
        click.echo(f"Running pattern detection on {len(expanded_files)} files...")
        
        # Check if batch method is available
        if hasattr(pattern_detector, 'detect_patterns_for_files'):
            # Use optimized batch method if available
            findings = pattern_detector.detect_patterns_for_files(
                list(expanded_files),
                categories=None
            )
        else:
            # Fallback to individual file processing
            findings = []
            for i, file_path in enumerate(expanded_files, 1):
                if i % 10 == 0:
                    click.echo(f"  Scanning file {i}/{len(expanded_files)}...", nl=False)
                    click.echo("\r", nl=False)
                
                # Convert to relative path for pattern detector
                try:
                    rel_path = Path(file_path).relative_to(repo_root).as_posix()
                except ValueError:
                    rel_path = file_path
                
                file_findings = pattern_detector.detect_patterns(
                    categories=None, 
                    file_filter=rel_path
                )
                findings.extend(file_findings)
            
            click.echo(f"\n  Found {len(findings)} patterns")
    else:
        findings = []
        click.echo("No files to analyze after expansion")
    
    patterns = findings
    
    # Step 4: Run FCE correlation with refactoring rules
    click.echo("Running correlation analysis...")
    
    # Run the FCE to get correlations
    fce_results = run_fce(
        root_path=str(repo_root),
        capsules_dir=str(pf_dir / "capsules"),
        manifest_path="manifest.json",
        workset_path=str(temp_workset_file),
        db_path="repo_index.db",
        timeout=600,
        print_plan=False
    )
    
    # Extract correlations from FCE results
    correlations = []
    if fce_results.get("success") and fce_results.get("results"):
        fce_data = fce_results["results"]
        if "correlations" in fce_data and "factual_clusters" in fce_data["correlations"]:
            correlations = fce_data["correlations"]["factual_clusters"]
    
    # Step 5: Identify mismatches
    mismatches = _find_mismatches(patterns, correlations, affected_files)
    
    # Generate report
    report = _generate_report(affected_files, patterns, correlations, mismatches)
    
    # Display summary
    click.echo("\n" + "=" * 60)
    click.echo("Refactoring Analysis Summary")
    click.echo("=" * 60)
    
    click.echo(f"\nFiles analyzed: {len(affected_files)}")
    click.echo(f"Patterns detected: {len(patterns)}")
    click.echo(f"Correlations found: {len(correlations)}")
    
    if mismatches["api"]:
        click.echo(f"\nAPI Mismatches: {len(mismatches['api'])}")
        for mismatch in mismatches["api"][:5]:  # Show top 5
            click.echo(f"  • {mismatch['description']}")
            
    if mismatches["model"]:
        click.echo(f"\nData Model Mismatches: {len(mismatches['model'])}")
        for mismatch in mismatches["model"][:5]:  # Show top 5
            click.echo(f"  • {mismatch['description']}")
            
    if mismatches["contract"]:
        click.echo(f"\nContract Mismatches: {len(mismatches['contract'])}")
        for mismatch in mismatches["contract"][:5]:  # Show top 5
            click.echo(f"  • {mismatch['description']}")
    
    # Risk assessment
    risk_level = _assess_risk(mismatches, len(affected_files))
    click.echo(f"\nRisk Level: {risk_level}")
    
    # Recommendations
    recommendations = _generate_recommendations(mismatches)
    if recommendations:
        click.echo("\nRecommendations:")
        for rec in recommendations:
            click.echo(f"  ✓ {rec}")
    
    # Save detailed report if requested
    if output:
        with open(output, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        click.echo(f"\nDetailed report saved to: {output}")
    
    # Suggest next steps
    click.echo("\nNext Steps:")
    click.echo("  1. Review the mismatches identified above")
    click.echo("  2. Run 'aud impact --file <file> --line <line>' for detailed impact")
    click.echo("  3. Use 'aud detect-patterns --workset' for pattern-specific issues")
    click.echo("  4. Run 'aud full' for comprehensive analysis")


def _expand_affected_files(
    affected_files: Set[str], 
    db_path: str, 
    expansion_mode: str,
    repo_root: Path
) -> Set[str]:
    """Expand affected files with their dependencies based on mode."""
    if expansion_mode == "none":
        return affected_files
    
    expanded = set(affected_files)
    total_files = len(affected_files)
    
    click.echo(f"\nExpanding {total_files} affected files with {expansion_mode} mode...")
    
    if expansion_mode in ["direct", "full"]:
        from theauditor.impact_analyzer import analyze_impact
        import sqlite3
        import os
        
        for i, file_path in enumerate(affected_files, 1):
            if i % 5 == 0 or i == total_files:
                click.echo(f"  Analyzing dependencies {i}/{total_files}...", nl=False)
                click.echo("\r", nl=False)
            
            # Find a representative line (first function/class)
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT line FROM symbols 
                WHERE path = ? AND type IN ('function', 'class')
                ORDER BY line LIMIT 1
            """, (file_path,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                line = result[0]
                try:
                    impact = analyze_impact(
                        db_path=db_path,
                        target_file=file_path,
                        target_line=line,
                        trace_to_backend=(expansion_mode == "full")
                    )
                    
                    # Add direct dependencies
                    for dep in impact.get("upstream", []):
                        expanded.add(dep["file"])
                    for dep in impact.get("downstream", []):
                        if dep["file"] != "external":
                            expanded.add(dep["file"])
                    
                    # Add transitive if full mode
                    if expansion_mode == "full":
                        for dep in impact.get("upstream_transitive", []):
                            expanded.add(dep["file"])
                        for dep in impact.get("downstream_transitive", []):
                            if dep["file"] != "external":
                                expanded.add(dep["file"])
                except Exception as e:
                    # Don't fail entire analysis for one file
                    if os.environ.get("THEAUDITOR_DEBUG"):
                        click.echo(f"\n  Warning: Could not analyze {file_path}: {e}")
        
        click.echo(f"\n  Expanded from {total_files} to {len(expanded)} files")
    
    return expanded


def _analyze_migrations(repo_root: Path, migration_dir: str, migration_limit: int = 0) -> List[str]:
    """Analyze migration files to detect schema changes.
    
    Args:
        repo_root: Repository root path
        migration_dir: Migration directory path
        migration_limit: Number of recent migrations to analyze (0=all)
    """
    migration_path = repo_root / migration_dir
    affected_files = []
    
    if not migration_path.exists():
        # Try common locations (most common first!)
        found_migrations = False
        for common_path in ["backend/migrations", "migrations", "db/migrations", 
                           "database/migrations", "frontend/migrations"]:
            test_path = repo_root / common_path
            if test_path.exists():
                # Check if it actually contains migration files
                import glob
                test_migrations = (glob.glob(str(test_path / "*.js")) + 
                                 glob.glob(str(test_path / "*.ts")) +
                                 glob.glob(str(test_path / "*.sql")))
                if test_migrations:
                    migration_path = test_path
                    found_migrations = True
                    click.echo(f"Found migrations in: {common_path}")
                    break
        
        if not found_migrations:
            click.echo("\n⚠️  WARNING: No migration files found in standard locations:", err=True)
            click.echo("    • backend/migrations/", err=True)
            click.echo("    • migrations/", err=True)
            click.echo("    • db/migrations/", err=True)
            click.echo("    • database/migrations/", err=True)
            click.echo("    • frontend/migrations/ (yes, we check here too)", err=True)
            click.echo(f"\n    Current directory searched: {migration_dir}", err=True)
            click.echo(f"    Use --migration-dir <path> to specify your migration folder\n", err=True)
            return affected_files
    
    if migration_path.exists():
        # Look for migration files
        import glob
        import re
        
        migrations = sorted(glob.glob(str(migration_path / "*.js")) + 
                          glob.glob(str(migration_path / "*.ts")) +
                          glob.glob(str(migration_path / "*.sql")))
        
        if not migrations:
            click.echo(f"\n⚠️  WARNING: Directory '{migration_path}' exists but contains no migration files", err=True)
            click.echo(f"    Expected: .js, .ts, or .sql files", err=True)
            return affected_files
        
        # Determine which migrations to analyze
        total_migrations = len(migrations)
        if migration_limit > 0:
            migrations_to_analyze = migrations[-migration_limit:]
            click.echo(f"Analyzing {len(migrations_to_analyze)} most recent migrations (out of {total_migrations} total)")
        else:
            migrations_to_analyze = migrations
            click.echo(f"Analyzing ALL {total_migrations} migration files")
            if total_migrations > 20:
                click.echo("⚠️  Large migration set detected. Consider using --migration-limit for faster analysis")
        
        # Enhanced pattern matching
        schema_patterns = {
            'column_ops': r'(?:removeColumn|dropColumn|renameColumn|addColumn|alterColumn|modifyColumn)',
            'table_ops': r'(?:createTable|dropTable|renameTable|alterTable)',
            'index_ops': r'(?:addIndex|dropIndex|createIndex|removeIndex)',
            'fk_ops': r'(?:addForeignKey|dropForeignKey|addConstraint|dropConstraint)',
            'type_changes': r'(?:changeColumn|changeDataType|alterType)'
        }
        
        tables_affected = set()
        operations_found = set()
        
        # Process migrations with progress indicator
        for i, migration_file in enumerate(migrations_to_analyze, 1):
            if i % 10 == 0 or i == len(migrations_to_analyze):
                click.echo(f"  Processing migration {i}/{len(migrations_to_analyze)}...", nl=False)
                click.echo("\r", nl=False)
            
            try:
                with open(migration_file, 'r') as f:
                    content = f.read()
                    
                    # Check all pattern categories
                    for pattern_name, pattern_regex in schema_patterns.items():
                        if re.search(pattern_regex, content, re.IGNORECASE):
                            operations_found.add(pattern_name)
                            
                            # Extract table/model names (improved regex)
                            # Handles: "table", 'table', `table`, tableName
                            tables = re.findall(r"['\"`](\w+)['\"`]|(?:table|Table)Name:\s*['\"`]?(\w+)", content)
                            for match in tables:
                                # match is a tuple from multiple capture groups
                                table = match[0] if match[0] else match[1] if len(match) > 1 else None
                                if table and table not in ['table', 'Table', 'column', 'Column']:
                                    tables_affected.add(table)
            except Exception as e:
                click.echo(f"\nWarning: Could not read migration {migration_file}: {e}")
                continue
        
        click.echo(f"\nFound {len(operations_found)} types of operations affecting {len(tables_affected)} tables")
        
        # Map tables to model files
        for table in tables_affected:
            model_file = _find_model_file(repo_root, table)
            if model_file:
                affected_files.append(str(model_file))
        
        # Deduplicate
        affected_files = list(set(affected_files))
        click.echo(f"Mapped to {len(affected_files)} model files")
    
    return affected_files


def _find_model_file(repo_root: Path, table_name: str) -> Optional[Path]:
    """Find model file corresponding to a database table."""
    # Convert table name to likely model name
    model_names = [
        table_name,  # exact match
        table_name.rstrip('s'),  # singular
        ''.join(word.capitalize() for word in table_name.split('_')),  # PascalCase
    ]
    
    for model_name in model_names:
        # Check common model locations
        for pattern in [f"**/models/{model_name}.*", f"**/{model_name}.model.*", 
                       f"**/entities/{model_name}.*"]:
            import glob
            matches = glob.glob(str(repo_root / pattern), recursive=True)
            if matches:
                return Path(matches[0])
    
    return None


def _find_mismatches(patterns: List[Dict], correlations: List[Dict], 
                    affected_files: Set[str]) -> Dict[str, List[Dict]]:
    """Identify mismatches from patterns and correlations."""
    mismatches = {
        "api": [],
        "model": [],
        "contract": []
    }
    
    # Analyze patterns for known refactoring issues
    for pattern in patterns:
        if pattern.get("rule_id") in ["PRODUCT_PRICE_FIELD_REMOVED", 
                                      "PRODUCT_SKU_MOVED_TO_VARIANT"]:
            mismatches["model"].append({
                "type": "field_moved",
                "description": pattern.get("message", "Field moved between models"),
                "file": pattern.get("file"),
                "line": pattern.get("line")
            })
        elif pattern.get("rule_id") in ["API_ENDPOINT_PRODUCT_PRICE"]:
            mismatches["api"].append({
                "type": "endpoint_deprecated",
                "description": pattern.get("message", "API endpoint no longer exists"),
                "file": pattern.get("file"),
                "line": pattern.get("line")
            })
        elif pattern.get("rule_id") in ["FRONTEND_BACKEND_CONTRACT_MISMATCH"]:
            mismatches["contract"].append({
                "type": "contract_mismatch",
                "description": pattern.get("message", "Frontend/backend contract mismatch"),
                "file": pattern.get("file"),
                "line": pattern.get("line")
            })
    
    # Analyze correlations for co-occurring issues
    for correlation in correlations:
        if correlation.get("confidence", 0) > 0.8:
            category = "contract" if "contract" in correlation.get("name", "").lower() else \
                      "api" if "api" in correlation.get("name", "").lower() else "model"
            
            mismatches[category].append({
                "type": "correlation",
                "description": correlation.get("description", "Correlated issue detected"),
                "confidence": correlation.get("confidence"),
                "facts": correlation.get("matched_facts", [])
            })
    
    return mismatches


def _assess_risk(mismatches: Dict[str, List], file_count: int) -> str:
    """Assess the risk level of the refactoring."""
    total_issues = sum(len(issues) for issues in mismatches.values())
    
    if total_issues > 20 or file_count > 50:
        return "HIGH"
    elif total_issues > 10 or file_count > 20:
        return "MEDIUM"
    else:
        return "LOW"


def _generate_recommendations(mismatches: Dict[str, List]) -> List[str]:
    """Generate actionable recommendations based on mismatches."""
    recommendations = []
    
    if mismatches["model"]:
        recommendations.append("Update frontend interfaces to match new model structure")
        recommendations.append("Run database migrations in all environments")
        
    if mismatches["api"]:
        recommendations.append("Update API client to use new endpoints")
        recommendations.append("Add deprecation notices for old endpoints")
        
    if mismatches["contract"]:
        recommendations.append("Synchronize TypeScript interfaces with backend models")
        recommendations.append("Add API versioning to prevent breaking changes")
    
    if sum(len(issues) for issues in mismatches.values()) > 10:
        recommendations.append("Consider breaking this refactoring into smaller steps")
        recommendations.append("Add integration tests before proceeding")
    
    return recommendations


def _generate_report(affected_files: Set[str], patterns: List[Dict], 
                    correlations: List[Dict], mismatches: Dict) -> Dict:
    """Generate detailed report of the refactoring analysis."""
    return {
        "summary": {
            "files_analyzed": len(affected_files),
            "patterns_detected": len(patterns),
            "correlations_found": len(correlations),
            "total_mismatches": sum(len(issues) for issues in mismatches.values())
        },
        "affected_files": list(affected_files),
        "patterns": patterns,
        "correlations": correlations,
        "mismatches": mismatches,
        "risk_assessment": _assess_risk(mismatches, len(affected_files)),
        "recommendations": _generate_recommendations(mismatches)
    }


# Register command
refactor_command = refactor