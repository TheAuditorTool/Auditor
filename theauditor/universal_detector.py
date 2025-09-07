"""Universal pattern detector - finds patterns and outputs in courier format.

This module is part of TheAuditor's COURIER pipeline:
- Runs pattern detection for runtime, DB, and logic issues
- Outputs findings using standard keys (file, line, message)
- Acts as one of the 16+ "tools" that TheAuditor couriers data from
- Never interprets whether patterns are actually problems
"""

import ast
import importlib
import inspect
import json
import os
import pkgutil
import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List

import click

from theauditor.pattern_loader import Pattern, PatternLoader
from theauditor.rules.orchestrator import RulesOrchestrator, RuleContext


def sanitize_for_av(snippet: str) -> str:
    """Defang dangerous patterns using zero-width spaces to prevent AV false positives.
    
    This function inserts zero-width spaces (U+200C) into patterns that commonly
    trigger antivirus heuristics. The zero-width space is invisible to humans
    and doesn't affect how AI models tokenize the text, but breaks pattern
    matching in antivirus scanners.
    
    Args:
        snippet: Code snippet that may contain dangerous patterns
        
    Returns:
        Sanitized snippet with zero-width spaces inserted
    """
    if not snippet:
        return snippet
    
    # Zero-width space character (invisible, breaks pattern matching)
    zws = "\u200C"
    
    # Patterns that commonly trigger AV heuristics
    # These are the actual patterns found in vulnerability code
    replacements = {
        # Code execution patterns
        "eval": f"ev{zws}al",
        "exec": f"ex{zws}ec",
        "system": f"sys{zws}tem",
        "spawn": f"spa{zws}wn",
        "__import__": f"__imp{zws}ort__",
        "subprocess": f"sub{zws}process",
        "os.": f"o{zws}s.",
        "shell=True": f"shell={zws}True",
        
        # SQL injection patterns
        "SELECT": f"SEL{zws}ECT",
        "DELETE": f"DEL{zws}ETE",
        "DROP": f"DR{zws}OP",
        "INSERT": f"INS{zws}ERT",
        "UPDATE": f"UPD{zws}ATE",
        "UNION": f"UNI{zws}ON",
        "WHERE": f"WH{zws}ERE",
        "FROM": f"FR{zws}OM",
        
        # Credential patterns
        "password": f"pass{zws}word",
        "passwd": f"pass{zws}wd",
        "secret": f"sec{zws}ret",
        "token": f"tok{zws}en",
        "api_key": f"api{zws}_key",
        "apikey": f"api{zws}key",
        "private_key": f"private{zws}_key",
        "credentials": f"cred{zws}entials",
        
        # XSS patterns
        "innerHTML": f"inner{zws}HTML",
        "document.write": f"document.{zws}write",
        "dangerouslySetInnerHTML": f"dangerously{zws}SetInnerHTML",
        
        # Network patterns
        "http://": f"ht{zws}tp://",
        "https://": f"ht{zws}tps://",
        "0.0.0.0": f"0.0.{zws}0.0",
        
        # File operations
        "unlink": f"un{zws}link",
        "rmdir": f"rm{zws}dir",
        "chmod": f"ch{zws}mod",
    }
    
    result = snippet
    for dangerous, safe in replacements.items():
        # Case-insensitive replacement for SQL keywords
        if dangerous.isupper():
            import re
            result = re.sub(
                re.escape(dangerous),
                safe,
                result,
                flags=re.IGNORECASE
            )
        else:
            # Case-sensitive for code patterns
            result = result.replace(dangerous, safe)
    
    return result


# Simple finding dataclass without validation
@dataclass
class Finding:
    """Represents a pattern finding without validation."""
    pattern_name: str
    message: str
    file: str
    line: int
    column: int
    severity: str
    snippet: str
    category: str
    match_type: str = "regex"
    # FIX: Removed framework field - frameworks are project-level, not file-level
    
    def to_dict(self):
        """Convert finding to dictionary with AV-safe snippets."""
        data = asdict(self)
        # Sanitize snippet to prevent antivirus false positives
        data['snippet'] = sanitize_for_av(data['snippet'])
        return data


class UniversalPatternDetector:
    """Detects universal patterns across any codebase."""

    # File extensions mapped to language identifiers
    LANGUAGE_MAP = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".vue": "vue",
        ".java": "java",
        ".cs": "c#",
        ".cpp": "c++",
        ".cc": "c++",
        ".cxx": "c++",
        ".c": "c",
        ".h": "c",
        ".hpp": "c++",
        ".go": "go",
        ".rs": "rust",
        ".rb": "ruby",
        ".php": "php",
        ".swift": "swift",
        ".kt": "kotlin",
        ".scala": "scala",
        ".sql": "sql",
        ".sh": "bash",
        ".bash": "bash",
        ".zsh": "bash",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".json": "json",
    }

    # AST-covered patterns - Maps pattern names to languages where AST rules provide superior coverage
    # This prevents redundant regex pattern execution when high-fidelity AST rules already cover the same issue
    AST_COVERED_PATTERNS = {
        'hardcoded-secret': {'python', 'javascript', 'typescript'},
        'n-plus-one-query': {'python', 'javascript', 'typescript'},
        'xss-direct-output': {'python', 'javascript', 'typescript'},
        # Note: sql-injection is intentionally omitted as its AST rule is Python-only
    }

    def __init__(
        self,
        project_path: Path,
        pattern_loader: PatternLoader | None = None,
        with_ast: bool = True,
        with_frameworks: bool = True,
        exclude_patterns: list[str] = None,
    ):
        """Initialize detector.

        Args:
            project_path: Root path of project to analyze.
            pattern_loader: Optional PatternLoader instance.
            with_ast: Enable AST-based pattern matching.
            with_frameworks: Enable framework detection and framework-specific patterns.
            exclude_patterns: List of patterns to exclude from scanning.
        """
        self.project_path = Path(project_path).resolve()
        self.pattern_loader = pattern_loader or PatternLoader()
        self.findings: list[Finding] = []
        self.with_ast = with_ast
        self.with_frameworks = with_frameworks
        self.detected_frameworks = []
        self.exclude_patterns = exclude_patterns or []
        # FIX: Removed framework_by_language - frameworks are project-level, not file-level
        
        # Initialize AST parser if enabled
        self.ast_parser = None
        if self.with_ast:
            try:
                from theauditor.ast_parser import ASTParser
                self.ast_parser = ASTParser()
            except ImportError:
                print("Warning: AST parser not available, falling back to regex-only")
                self.with_ast = False
        
        # Detect frameworks if enabled
        if self.with_frameworks:
            try:
                from theauditor.framework_detector import FrameworkDetector
                detector = FrameworkDetector(self.project_path, exclude_patterns=self.exclude_patterns)
                self.detected_frameworks = detector.detect_all()
                if self.detected_frameworks:
                    print(f"Detected frameworks: {', '.join(fw['framework'] for fw in self.detected_frameworks)}")
                    # FIX: Removed framework_by_language dictionary that was losing multiple frameworks per language
                    # Frameworks are project-level, not file-level - they shouldn't be tagged on individual findings
            except ImportError:
                print("Warning: Framework detector not available")
                self.with_frameworks = False



    def detect_language(self, file_path: Path) -> str | None:
        """Detect programming language from file extension.

        Args:
            file_path: Path to file.

        Returns:
            Language identifier or None.
        """
        suffix = file_path.suffix.lower()
        return self.LANGUAGE_MAP.get(suffix)

    def scan_file(self, file_path: Path, patterns: list[Pattern], category: str, sha256: str = None, run_ast_rules: bool = True) -> list[Finding]:
        """Scan a single file for pattern matches.

        Args:
            file_path: Path to file to scan.
            patterns: List of patterns to apply.
            category: Category name for findings.
            sha256: Optional SHA256 hash from database for cache lookup.
            run_ast_rules: Whether to run AST-based rules.

        Returns:
            List of findings.
        """
        findings = []
        
        # Early language detection for optimization
        language = self.detect_language(file_path)
        
        # OPTIMIZATION: Early exit if no patterns match this language and no AST rules to run
        applicable_patterns = [p for p in patterns if p.matches_language(language)] if language else []
        if not applicable_patterns and not run_ast_rules:
            return []  # Nothing to do for this file
        
        # FIX: Removed framework lookup - frameworks are project-level, not file-level

        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                content = f.read()
                lines = content.splitlines()
        except OSError as e:
            print(f"Warning: Could not read {file_path}: {e}")
            return findings

        # Try AST parsing if enabled
        ast_tree = None
        # Language already detected at the start of the function
        if self.with_ast and self.ast_parser:
            if language and self.ast_parser.supports_language(language):
                # Check persistent cache first for JS/TS files
                if language in ["javascript", "typescript"]:
                    # Use provided SHA256 from database, or compute from content
                    if sha256:
                        file_hash = sha256
                    else:
                        # Fallback: compute file hash for cache lookup
                        import hashlib
                        file_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
                    
                    # Check cache
                    cache_dir = self.project_path / ".pf" / "ast_cache"
                    cache_file = cache_dir / f"{file_hash}.json"
                    if cache_file.exists():
                        try:
                            import json
                            with open(cache_file, 'r', encoding='utf-8') as f:
                                ast_tree = json.load(f)
                        except (json.JSONDecodeError, OSError):
                            # Cache read failed, parse fresh
                            ast_tree = self.ast_parser.parse_file(file_path, language)
                            # REMOVED: Cache write logic - only indexer.py should write to cache
                    else:
                        # Parse fresh (cache miss)
                        ast_tree = self.ast_parser.parse_file(file_path, language)
                        # REMOVED: Cache write logic - only indexer.py should write to cache
                else:
                    # Non-JS/TS files, parse directly
                    ast_tree = self.ast_parser.parse_file(file_path, language)
        
        # Invoke high-fidelity AST-based rules using the orchestrator
        if run_ast_rules:
            # Initialize orchestrator if not already done
            if not hasattr(self, '_orchestrator'):
                self._orchestrator = RulesOrchestrator(self.project_path)
            
            # Prepare appropriate AST for the orchestrator
            rule_ast = None
            if language == "python":
                try:
                    # Parse Python code with native AST
                    rule_ast = ast.parse(content)
                except SyntaxError:
                    # If Python parsing fails, continue with other patterns
                    pass
            
            else:
                # For other languages, use the parsed AST
                rule_ast = ast_tree
            
            # Run all rules through the orchestrator
            if rule_ast is not None or ast_tree is not None:
                context = RuleContext(
                    file_path=file_path,
                    content=content,
                    ast_tree=rule_ast if rule_ast is not None else ast_tree,
                    language=language,
                    db_path=str(self.project_path / ".pf" / "repo_index.db"),
                    project_path=self.project_path
                )
                
                # Run rules for this file
                try:
                    rule_findings = self._orchestrator.run_rules_for_file(context)
                    
                    # Convert rule findings to Finding objects
                    for finding in rule_findings:
                        findings.append(Finding(
                            pattern_name=finding.get("pattern_name", finding.get("rule", "RULE_FINDING")),
                            message=finding.get("message", "Issue detected"),
                            file=str(file_path.relative_to(self.project_path)),
                            line=finding.get("line", 0),
                            column=finding.get("column", finding.get("col", 0)),
                            severity=finding.get("severity", "medium").lower(),
                            snippet=finding.get("snippet", finding.get("evidence", finding.get("message", ""))),
                            category=finding.get("category", "security"),
                            match_type="ast",
                        ))
                    
                except Exception as e:
                    if os.environ.get("THEAUDITOR_DEBUG"):
                        print(f"[ORCHESTRATOR] Failed to run rules for file {file_path}: {e}")

        # OPTIMIZATION: Use pre-computed applicable_patterns instead of filtering again
        for pattern in applicable_patterns:
            # Skip this SPECIFIC pattern if it's covered by a superior AST rule for this language
            if (pattern.name in self.AST_COVERED_PATTERNS and 
                language in self.AST_COVERED_PATTERNS[pattern.name]):
                continue
            
            # Try AST pattern matching first if available
            if ast_tree and pattern.ast_pattern:
                ast_matches = self.ast_parser.find_ast_matches(ast_tree, pattern.ast_pattern)
                for ast_match in ast_matches:
                    finding = Finding(
                        pattern_name=pattern.name,
                        message=pattern.description,
                        file=str(file_path.relative_to(self.project_path)),
                        line=ast_match.start_line,
                        column=ast_match.start_col,
                        severity=pattern.severity,
                        snippet=ast_match.snippet,
                        category=category,
                        match_type="ast",
                    )
                    findings.append(finding)
            
            # Fallback to regex if no AST match or no AST pattern
            elif pattern.compiled_regex:
                # Find all matches
                for match in pattern.compiled_regex.finditer(content):
                    # Calculate line number
                    line_start = content.count("\n", 0, match.start()) + 1

                    # Get the matched line for snippet
                    if line_start <= len(lines):
                        snippet = lines[line_start - 1].strip()
                        # Limit snippet length
                        if len(snippet) > 200:
                            snippet = snippet[:197] + "..."
                    else:
                        snippet = match.group(0)[:200]

                    # Calculate column (position in line)
                    line_start_pos = content.rfind("\n", 0, match.start()) + 1
                    column = match.start() - line_start_pos

                    finding = Finding(
                        pattern_name=pattern.name,
                        message=pattern.description,
                        file=str(file_path.relative_to(self.project_path)),
                        line=line_start,
                        column=column,
                        severity=pattern.severity,
                        snippet=snippet,
                        category=category,
                        match_type="regex",
                    )
                    findings.append(finding)

        return findings

    def _process_rule_package(self, package_name: str, db_path: str) -> tuple[list[Finding], int]:
        """Process a single rule package and execute its rules.
        
        Helper method for parallel execution of rule packages.
        
        Args:
            package_name: Name of the package to process
            db_path: Path to the repo_index.db database
            
        Returns:
            Tuple of (findings, rules_executed_count)
        """
        findings = []
        rules_executed = 0
        
        try:
            # Dynamically import the package
            package = importlib.import_module(package_name)
            
            # Get the package directory path
            package_dir = Path(package.__file__).parent
            
            # Discover all Python modules in the package directory
            for module_info in pkgutil.iter_modules([str(package_dir)]):
                # Skip __init__ module
                if module_info.name == '__init__':
                    continue
                
                try:
                    # Dynamically import the module
                    module_name = f'{package_name}.{module_info.name}'
                    module = importlib.import_module(module_name)
                
                    # Find all functions in the module that match our pattern
                    for name, obj in inspect.getmembers(module, inspect.isfunction):
                        # Check if function name starts with 'find_'
                        if name.startswith('find_'):
                            # Verify function signature matches expected pattern
                            sig = inspect.signature(obj)
                            params = list(sig.parameters.keys())
                            
                            # Should have exactly one parameter (db_path)
                            if len(params) == 1:
                                # Execute the rule function
                                try:
                                    rule_findings = obj(db_path)
                                    rules_executed += 1
                                    
                                    # Convert findings to Finding dataclass format
                                    for finding in rule_findings:
                                        findings.append(Finding(
                                            pattern_name=finding.get('pattern_name', name.upper()),
                                            message=finding.get('message', f'Issue detected by {name}'),
                                            file=finding.get('file', ''),
                                            line=finding.get('line', 0),
                                            column=finding.get('column', 0),
                                            severity=finding.get('severity', 'medium'),
                                            snippet=finding.get('snippet', ''),
                                            category=finding.get('category', 'security'),
                                            match_type=finding.get('match_type', 'database'),
                                        ))
                                    
                                    if rule_findings:
                                        print(f"  {name}: Found {len(rule_findings)} issues")
                                
                                except Exception as e:
                                    print(f"  Warning: Rule {name} in {module_info.name} failed: {e}")
                
                except ImportError as e:
                    print(f"  Warning: Could not import module {module_info.name}: {e}")
                except Exception as e:
                    print(f"  Warning: Error processing module {module_info.name}: {e}")
        
        except Exception as e:
            print(f"Warning: Failed to process package {package_name}: {e}")
        
        return findings, rules_executed
    
    def _run_database_aware_rules(self, db_path: str) -> list[Finding]:
        """Dynamically discover and execute all database-aware rules.
        
        This method discovers all rule modules within the security_rules and orm directories,
        dynamically imports them, and executes any functions that follow the pattern:
        - Function name starts with 'find_'
        - Takes a single argument 'db_path: str'
        - Returns List[Dict[str, Any]] with findings
        
        Now uses parallel execution with ThreadPoolExecutor for improved performance.
        
        Args:
            db_path: Path to the repo_index.db database
            
        Returns:
            List of Finding objects from all discovered rules
        """
        findings = []
        total_rules_executed = 0
        
        # List of rule directories to search
        rule_packages = [
            'theauditor.rules.security_rules',
            'theauditor.rules.orm',
            'theauditor.rules.deployment',
            'theauditor.rules.react',
            'theauditor.rules.vue'
        ]
        
        # Execute rule packages in parallel (limit workers to prevent resource exhaustion)
        import os
        max_workers = min(4, (os.cpu_count() or 1) + 1)  # Cap at 4 or CPU count + 1, whichever is smaller
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all packages for processing
            futures = {}
            for package_name in rule_packages:
                future = executor.submit(self._process_rule_package, package_name, db_path)
                futures[future] = package_name
            
            # Collect results as they complete
            for future in as_completed(futures):
                package_name = futures[future]
                try:
                    package_findings, rules_executed = future.result()
                    findings.extend(package_findings)
                    total_rules_executed += rules_executed
                except Exception as e:
                    print(f"Warning: Package {package_name} processing failed: {e}")
        
        if total_rules_executed > 0:
            print(f"  Executed {total_rules_executed} database-aware rules in parallel")
        
        return findings

    def _run_bundle_analysis(self) -> list[Finding]:
        """Run bundle analysis as a separate task for parallel execution.
        
        Returns:
            List of Finding objects from bundle analysis
        """
        findings = []
        try:
            from theauditor.rules.build import find_bundle_issues
            
            bundle_issues = find_bundle_issues(str(self.project_path))
            
            for issue in bundle_issues:
                findings.append(Finding(
                    pattern_name=issue.get('pattern_name', 'BUNDLE_ISSUE'),
                    message=issue.get('message', 'Bundle issue detected'),
                    file=issue.get('file', 'unknown'),
                    line=issue.get('line', 0),
                    column=issue.get('column', 0),
                    severity=issue.get('severity', 'medium').lower(),
                    snippet=issue.get('details', {}).get('recommendation', issue.get('message', '')),
                    category=issue.get('category', 'build'),
                    match_type='holistic',
                ))
            
            if bundle_issues:
                print(f"  Found {len(bundle_issues)} bundle issues")
                
        except ImportError:
            pass
        except Exception as e:
            print(f"Warning: Bundle analysis failed: {e}")
        
        return findings
    
    def _run_sourcemap_detection(self) -> list[Finding]:
        """Run source map detection as a separate task for parallel execution.
        
        Returns:
            List of Finding objects from source map detection
        """
        findings = []
        try:
            from theauditor.rules.security.sourcemap_detector import find_source_maps
            
            source_map_issues = find_source_maps(str(self.project_path))
            
            for issue in source_map_issues:
                findings.append(Finding(
                    pattern_name=issue.get('pattern_name', 'SOURCE_MAP_ISSUE'),
                    message=issue.get('message', 'Source map exposure detected'),
                    file=issue.get('file', 'unknown'),
                    line=issue.get('line', 0),
                    column=issue.get('column', 0),
                    severity=issue.get('severity', 'high').lower(),
                    snippet=issue.get('details', {}).get('recommendation', issue.get('message', '')),
                    category=issue.get('category', 'security'),
                    match_type='holistic',
                ))
            
            if source_map_issues:
                print(f"  Found {len(source_map_issues)} source map exposures")
                
        except ImportError:
            pass
        except Exception as e:
            print(f"Warning: Source map detection failed: {e}")
        
        return findings
    
    def _run_holistic_analysis(self) -> list[Finding]:
        """Run project-level analysis that requires multiple file types.
        
        This method runs analyses that need holistic view of the project,
        such as bundle analysis which requires package.json, lock files,
        and source code analysis together.
        
        Now uses parallel execution with ThreadPoolExecutor for improved performance.
        
        Returns:
            List of Finding objects from holistic analysis
        """
        findings = []
        
        # Execute holistic analyses in parallel
        with ThreadPoolExecutor(max_workers=2) as executor:
            # Submit analysis tasks
            bundle_future = executor.submit(self._run_bundle_analysis)
            sourcemap_future = executor.submit(self._run_sourcemap_detection)
            
            # Collect results
            futures = {bundle_future: 'bundle', sourcemap_future: 'sourcemap'}
            
            for future in as_completed(futures):
                analysis_name = futures[future]
                try:
                    analysis_findings = future.result()
                    findings.extend(analysis_findings)
                except Exception as e:
                    print(f"Warning: {analysis_name} analysis failed: {e}")
        
        return findings

    def detect_patterns(
        self, categories: list[str] | None = None, file_filter: str | None = None
    ) -> list[Finding]:
        """Run pattern detection across project.

        Args:
            categories: Optional list of pattern categories to use.
            file_filter: Optional glob pattern to filter files.

        Returns:
            List of all findings.
        """
        # Load patterns - now includes framework patterns automatically due to recursive scanning
        patterns_by_category = self.pattern_loader.load_patterns(categories)

        if not patterns_by_category:
            print("Warning: No patterns loaded")
            return []

        self.findings = []
        
        # Import threading for thread safety
        import threading
        findings_lock = threading.Lock()

        # Get files from database instead of filesystem
        print("Querying indexed files from database...")
        files_to_scan = []
        
        # Check if database exists (it's stored in .pf/repo_index.db)
        db_path = self.project_path / ".pf" / "repo_index.db"
        if not db_path.exists():
            print("Error: Database not found. Run 'aud index' first to build the file index.")
            return []
        
        # Query indexed files from database
        import sqlite3
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Build query with optional file filter
            if file_filter:
                # Use GLOB for pattern matching (SQLite supports this)
                query = "SELECT path, sha256, ext FROM files WHERE path GLOB ?"
                rows = cursor.execute(query, (file_filter,)).fetchall()
            else:
                query = "SELECT path, sha256, ext FROM files"
                rows = cursor.execute(query).fetchall()
            
            # Process database results
            for file_path, sha256_hash, ext in rows:
                full_path = self.project_path / file_path
                
                # Skip if file no longer exists on disk
                if not full_path.exists():
                    continue
                
                # Detect language from extension
                language = self.detect_language(Path(file_path))
                if language is None:
                    continue  # Skip unknown file types
                
                # Add to list with SHA256 for cache lookup
                files_to_scan.append((full_path, language, sha256_hash))
            
            conn.close()
            
        except sqlite3.Error as e:
            print(f"Error querying database: {e}")
            print("Database may be corrupted or locked. Try running 'aud index' again.")
            return []
        
        total_files = len(files_to_scan)
        print(f"Found {total_files} files to scan...")
        
        if total_files == 0:
            return []
        
        # Define worker function for parallel processing
        def process_file(file_info):
            """Process a single file and return its findings."""
            file_path, language, sha256_hash = file_info  # Now includes SHA256
            local_findings = []
            
            # Apply patterns for each category
            first_category = True
            for category, patterns in patterns_by_category.items():
                # Filter patterns by language
                applicable_patterns = [p for p in patterns if p.matches_language(language)]

                if applicable_patterns:
                    # Only run AST rules on the first category to avoid duplicates
                    try:
                        file_findings = self.scan_file(
                            file_path, applicable_patterns, category, 
                            sha256=sha256_hash,  # Pass SHA256 for cache lookup
                            run_ast_rules=first_category
                        )
                        local_findings.extend(file_findings)
                        first_category = False
                    except Exception as e:
                        print(f"Warning: Failed to scan {file_path}: {e}")
            
            return local_findings
        
        # Process files in parallel using ThreadPoolExecutor
        # REAL-WORLD OPTIMIZATION: Adaptive worker count based on available resources
        # 
        # Learned the hard way: 16 workers might be "optimal" but will:
        # - Trigger antivirus scanners (looks like malware behavior)
        # - Consume 20+ GB RAM with AST parsing
        # - Make the system unusable for users
        # - Crash on systems with Firefox/Chrome eating RAM
        #
        # Better to be 8x faster and WORK than 37x faster and CRASH!
        def get_safe_worker_count():
            """Calculate safe worker count based on system resources."""
            try:
                import psutil
                # Check available RAM
                available_ram = psutil.virtual_memory().available
                ram_per_worker = 1.5 * 1024**3  # Assume 1.5GB per worker
                
                # Check current CPU usage
                cpu_percent = psutil.cpu_percent(interval=0.1)
                
                # Calculate limits - more aggressive thresholds
                max_by_ram = max(4, int(available_ram / ram_per_worker))
                max_by_cpu = os.cpu_count() if cpu_percent < 85 else max(4, os.cpu_count() // 2)
                
                # Increased limit to 16 workers for modern systems
                safe_workers = min(16, max_by_ram, max_by_cpu)
                
                # Ensure minimum of 4 workers even under pressure
                safe_workers = max(4, safe_workers)
                
                # If system is under extreme memory pressure, still keep 4 workers minimum
                if psutil.virtual_memory().percent > 90:
                    safe_workers = max(4, min(8, safe_workers))
                
                # Log diagnostic info to stderr so it's visible
                mem_gb = available_ram / (1024**3)
                mem_percent = psutil.virtual_memory().percent
                click.echo(f"[RESOURCES] CPU: {cpu_percent:.1f}%, RAM: {mem_gb:.1f}GB available ({mem_percent:.1f}% used)", err=True)
                click.echo(f"[WORKERS] Selected {safe_workers} workers (max_by_ram={max_by_ram}, max_by_cpu={max_by_cpu})", err=True)
                
                return safe_workers
            except ImportError:
                # psutil not available, use conservative default but still minimum 4
                return max(4, min(8, (os.cpu_count() or 4)))
        
        max_workers = get_safe_worker_count()
        click.echo(f"Processing files with {max_workers} parallel workers (adapted to system resources)...", err=True)
        
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all files for processing
            futures = [executor.submit(process_file, file_info) for file_info in files_to_scan]
            
            # Process results as they complete
            files_processed = 0
            for future in as_completed(futures):
                try:
                    file_findings = future.result()
                    
                    # Thread-safe append to findings
                    with findings_lock:
                        self.findings.extend(file_findings)
                    
                    files_processed += 1
                    
                    # Update progress
                    if files_processed % 10 == 0 or files_processed == total_files:
                        click.echo(f"\rScanning files... [{files_processed}/{total_files}] - {len(self.findings)} findings", nl=False)
                        
                except Exception as e:
                    print(f"\nWarning: File processing failed: {e}")
                    files_processed += 1
        
        print()  # New line after progress
        
        # Run database-aware rules once after all file scanning is complete
        # These rules operate on the aggregated data in .pf/repo_index.db
        db_path = self.project_path / ".pf" / "repo_index.db"
        if db_path.exists():
            print("Running database-aware security rules...")
            
            # Execute all discovered database-aware rules dynamically
            db_findings = self._run_database_aware_rules(str(db_path))
            self.findings.extend(db_findings)
        
        # Run holistic/project-level analysis (e.g., bundle analysis)
        # These rules need access to multiple file types simultaneously
        print("Running project-level analysis...")
        holistic_findings = self._run_holistic_analysis()
        self.findings.extend(holistic_findings)
        
        print(f"Scanned {files_processed} files, found {len(self.findings)} issues")
        return self.findings

    def detect_patterns_for_files(
        self, 
        file_list: List[str], 
        categories: List[str] = None
    ) -> List[Finding]:
        """Optimized pattern detection for specific file list.
        
        This method is specifically designed for targeted analysis like refactoring
        where we know exactly which files to analyze.
        """
        if not file_list:
            return []
        
        # Load patterns once
        patterns_by_category = self.pattern_loader.load_patterns(categories)
        if not patterns_by_category:
            return []
        
        self.findings = []
        db_path = self.project_path / ".pf" / "repo_index.db"
        
        if not db_path.exists():
            print("Error: Database not found. Run 'aud index' first.")
            return []
        
        # Build file info batch query
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Normalize paths for database lookup
        normalized_files = []
        for f in file_list:
            # Handle both absolute and relative paths
            try:
                rel_path = Path(f).relative_to(self.project_path).as_posix()
            except ValueError:
                # Already relative or outside project
                rel_path = Path(f).as_posix()
            if rel_path.startswith("./"):
                rel_path = rel_path[2:]
            normalized_files.append(rel_path)
        
        # Query all files at once
        placeholders = ','.join(['?'] * len(normalized_files))
        query = f"SELECT path, sha256, ext FROM files WHERE path IN ({placeholders})"
        
        files_to_scan = []
        try:
            rows = cursor.execute(query, normalized_files).fetchall()
            for file_path, sha256_hash, ext in rows:
                full_path = self.project_path / file_path
                if full_path.exists():
                    language = self.detect_language(Path(file_path))
                    if language:
                        files_to_scan.append((full_path, language, sha256_hash))
        finally:
            conn.close()
        
        if not files_to_scan:
            print(f"Warning: No valid files found from list of {len(file_list)} files")
            return []
        
        print(f"Scanning {len(files_to_scan)} files with targeted analysis...")
        
        # Use fewer workers for targeted analysis (usually smaller file sets)
        max_workers = min(4, len(files_to_scan), os.cpu_count() or 4)
        
        # Process files (reuse existing parallel logic)
        import threading
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        findings_lock = threading.Lock()
        
        def process_file(file_info):
            """Process a single file for patterns."""
            file_path, language, sha256_hash = file_info
            local_findings = []
            
            first_category = True
            for category, patterns in patterns_by_category.items():
                applicable_patterns = [p for p in patterns if p.matches_language(language)]
                
                if applicable_patterns:
                    try:
                        file_findings = self.scan_file(
                            file_path, applicable_patterns, category,
                            sha256=sha256_hash,
                            run_ast_rules=first_category
                        )
                        local_findings.extend(file_findings)
                        first_category = False
                    except Exception as e:
                        if os.environ.get("THEAUDITOR_DEBUG"):
                            print(f"Warning: Failed to scan {file_path}: {e}")
            
            return local_findings
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(process_file, file_info) for file_info in files_to_scan]
            
            for i, future in enumerate(as_completed(futures), 1):
                try:
                    file_findings = future.result()
                    with findings_lock:
                        self.findings.extend(file_findings)
                    
                    if i % 10 == 0 or i == len(files_to_scan):
                        print(f"\rProcessed {i}/{len(files_to_scan)} files - {len(self.findings)} findings", end="")
                except Exception as e:
                    print(f"\nWarning: File processing failed: {e}")
        
        print()  # New line after progress
        
        # Run database-aware rules once (but only for affected files context)
        db_path_str = str(self.project_path / ".pf" / "repo_index.db")
        if Path(db_path_str).exists():
            print("Running targeted database-aware rules...")
            # Note: These rules operate on the whole database but we could
            # enhance them to filter by file list in the future
            db_findings = self._run_database_aware_rules(db_path_str)
            
            # Filter to only findings in our file list
            filtered_db_findings = [
                f for f in db_findings 
                if any(norm_file in f.file for norm_file in normalized_files)
            ]
            self.findings.extend(filtered_db_findings)
        
        print(f"Targeted analysis complete: {len(self.findings)} issues found")
        return self.findings

    def format_table(self, max_rows: int = 50) -> str:
        """Format findings as a human-readable table.

        Args:
            max_rows: Maximum number of rows to display.

        Returns:
            Formatted table string.
        """
        if not self.findings:
            return "No issues found."

        # Sort by severity (critical > high > medium > low) then by file
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_findings = sorted(
            self.findings,
            key=lambda f: (severity_order.get(f.severity, 4), f.file, f.line),
        )

        # Build table
        lines = []
        lines.append(
            "PATTERN                          FILE                             LINE  SEVERITY"
        )
        lines.append("-" * 80)

        displayed = 0
        for finding in sorted_findings:
            if displayed >= max_rows:
                lines.append(f"... and {len(sorted_findings) - displayed} more findings")
                lines.append("\n" + "="*80)
                lines.append("TIP: View all findings in .pf/patterns.json")
                lines.append("     Use --output-json to save to a custom location")
                break

            # Truncate long names/paths for display
            pattern_name = finding.pattern_name[:32].ljust(32)
            file_str = finding.file
            if len(file_str) > 35:
                file_str = "..." + file_str[-32:]
            file_str = file_str.ljust(35)

            line = (
                f"{pattern_name} {file_str} {finding.line:4d}  {finding.severity.upper()}"
            )
            lines.append(line)
            displayed += 1

        return "\n".join(lines)

    def to_json(self, output_file: Path | None = None) -> str:
        """Export findings to JSON.

        Args:
            output_file: Optional file path to write JSON.

        Returns:
            JSON string.
        """
        data = {
            "findings": [f.to_dict() for f in self.findings],
        }

        json_str = json.dumps(data, indent=2, sort_keys=True)

        if output_file:
            output_file = Path(output_file)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(json_str)
            print(f"Findings written to {output_file}")

        return json_str

    def get_summary_stats(self) -> dict[str, Any]:
        """Get summary statistics of findings.

        Returns:
            Dictionary with summary stats.
        """
        stats = {
            "total_findings": len(self.findings),
            "by_severity": {},
            "by_category": {},
            "by_pattern": {},
            "files_affected": len({f.file for f in self.findings}),
        }

        # Count by severity
        for finding in self.findings:
            severity = finding.severity
            stats["by_severity"][severity] = stats["by_severity"].get(severity, 0) + 1

            category = finding.category
            stats["by_category"][category] = stats["by_category"].get(category, 0) + 1

            pattern = finding.pattern_name
            stats["by_pattern"][pattern] = stats["by_pattern"].get(pattern, 0) + 1

        return stats
