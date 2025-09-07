"""Module resolution for TypeScript/JavaScript projects with tsconfig.json support."""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any


class ModuleResolver:
    """Resolves module imports for TypeScript/JavaScript projects.
    
    Handles:
    - TypeScript path aliases from tsconfig.json
    - Webpack aliases from webpack.config.js
    - Node.js module resolution algorithm
    - Relative and absolute imports
    """
    
    def __init__(self, project_root: Optional[str] = None, db_path: str = ".pf/repo_index.db"):
        """Initialize resolver with database path - NO filesystem access.
        
        Args:
            project_root: Deprecated parameter, kept for compatibility
            db_path: Path to the indexed database
        """
        if project_root:
            self.project_root = Path(project_root).resolve()
        else:
            self.project_root = Path.cwd()
        
        self.db_path = Path(db_path)
        self.configs_by_context: Dict[str, Any] = {}
        self.path_mappings_by_context: Dict[str, Dict[str, List[str]]] = {}
        self.webpack_aliases: Dict[str, str] = {}  # Kept for compatibility
        
        # For backward compatibility
        self.base_url: Optional[str] = None
        self.path_mappings: Dict[str, List[str]] = {}
        
        # Load all configs from database ONCE
        self._load_all_configs_from_db()
        
    def _load_all_configs_from_db(self) -> None:
        """Load ALL tsconfig files from database and organize by context."""
        if not self.db_path.exists():
            print(f"[DEBUG] No database found at {self.db_path}, resolver disabled")
            return
        
        import sqlite3
        import os
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        try:
            # Get ALL tsconfig files from cache
            cursor.execute("""
                SELECT path, content, context_dir 
                FROM config_files 
                WHERE type = 'tsconfig'
            """)
            
            configs = cursor.fetchall()
            print(f"[DEBUG] Found {len(configs)} cached tsconfig files")
            
            for path, content, context_dir in configs:
                try:
                    # Use the json5 library if available, otherwise strip comments manually
                    try:
                        import json5
                        config = json5.loads(content)
                    except ImportError:
                        # Strip comments carefully (tsconfig allows comments)
                        # First remove single-line comments (but not inside strings)
                        lines = content.split('\n')
                        cleaned_lines = []
                        for line in lines:
                            # Simple approach: if line contains //, take everything before it
                            # unless it's inside quotes
                            comment_pos = line.find('//')
                            if comment_pos >= 0:
                                # Check if it's inside a string (crude but works for tsconfig)
                                before_comment = line[:comment_pos]
                                if before_comment.count('"') % 2 == 0:
                                    # Even number of quotes before //, so it's a real comment
                                    line = before_comment
                            cleaned_lines.append(line)
                        content = '\n'.join(cleaned_lines)
                        
                        # Remove multi-line comments (/* ... */) more carefully
                        # This is tricky with @/* patterns, so skip if risky
                        if '/*' in content and '*/' in content and '@/*' not in content:
                            content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
                        
                        # Remove trailing commas before closing brackets/braces
                        content = re.sub(r',(\s*[}\]])', r'\1', content)
                        
                        config = json.loads(content)
                    
                    # Handle root config with references
                    if context_dir is None:
                        refs = config.get("references", [])
                        if refs:
                            print(f"[DEBUG] Root config has {len(refs)} project references, skipping")
                            continue
                        context_dir = "root"
                    
                    # Store the config
                    self.configs_by_context[context_dir] = config
                    
                    # Extract compiler options
                    compiler_opts = config.get("compilerOptions", {})
                    base_url = compiler_opts.get("baseUrl", ".")
                    paths = compiler_opts.get("paths", {})
                    
                    print(f"[DEBUG] {context_dir}/tsconfig.json: baseUrl='{base_url}', {len(paths)} path mappings")
                    
                    # Process path mappings with context
                    mappings = {}
                    for alias_pattern, targets in paths.items():
                        normalized_alias = alias_pattern.rstrip("*")
                        normalized_targets = []
                        
                        for target in targets:
                            # Apply context-specific baseUrl resolution
                            target = target.rstrip("*")
                            
                            if context_dir == "backend" and base_url == "./src":
                                # Backend: @config/* -> config/* with baseUrl=./src
                                # Resolves to: backend/src/config/*
                                full_target = f"{context_dir}/src/{target}"
                            elif context_dir == "frontend" and base_url == ".":
                                # Frontend: @/* -> ./src/* with baseUrl=.
                                # Resolves to: frontend/src/*
                                if target.startswith("./"):
                                    target = target[2:]  # Remove ./
                                full_target = f"{context_dir}/{target}"
                            else:
                                # Unknown pattern, use as-is
                                full_target = target
                            
                            normalized_targets.append(full_target)
                        
                        mappings[normalized_alias] = normalized_targets
                        if os.environ.get("THEAUDITOR_DEBUG"):
                            print(f"[DEBUG]   {normalized_alias} -> {normalized_targets[0] if normalized_targets else 'None'}")
                    
                    self.path_mappings_by_context[context_dir] = mappings
                    
                    # For backward compatibility, expose root/first context mappings
                    if not self.path_mappings and mappings:
                        self.path_mappings = mappings
                        self.base_url = base_url
                    
                except (json.JSONDecodeError, KeyError) as e:
                    print(f"[WARNING] Failed to parse {path}: {e}")
                    
        except sqlite3.OperationalError as e:
            print(f"[WARNING] config_files table not found, using empty mappings: {e}")
            
        finally:
            conn.close()
        
        print(f"[DEBUG] Loaded configs for: {list(self.configs_by_context.keys())}")
    
    def _load_tsconfig(self) -> None:
        """Deprecated method kept for backward compatibility."""
        pass
    
    def resolve(self, import_path: str, containing_file_path: str) -> str:
        """Resolve an import path to its actual file location.
        
        Args:
            import_path: The import string (e.g., '@/utils/helpers')
            containing_file_path: The file where the import was found
            
        Returns:
            The resolved path relative to project root, or the original path if no alias matches
        """
        # Handle relative imports first (start with . or ..)
        if import_path.startswith("."):
            return import_path
        
        print(f"\n[DEBUG] Resolving import: '{import_path}' from file: {containing_file_path}")
        
        # Check if import matches any TypeScript path aliases
        for alias_prefix, target_patterns in self.path_mappings.items():
            if import_path.startswith(alias_prefix):
                # Extract the part after the alias
                suffix = import_path[len(alias_prefix):]
                print(f"[DEBUG] Matched alias '{alias_prefix}', suffix: '{suffix}'")
                
                # Try each target pattern (there can be multiple)
                for target_pattern in target_patterns:
                    print(f"[DEBUG] Trying target pattern: '{target_pattern}'")
                    # Construct the resolved path
                    if self.base_url:
                        # Resolve relative to baseUrl
                        base_path = self.project_root / self.base_url
                        resolved_path = base_path / target_pattern / suffix
                        print(f"[DEBUG] Resolved path (with baseUrl): {resolved_path}")
                    else:
                        # Resolve relative to project root
                        resolved_path = self.project_root / target_pattern / suffix
                        print(f"[DEBUG] Resolved path (no baseUrl): {resolved_path}")
                    
                    # Try common file extensions if path doesn't have one
                    if not resolved_path.suffix:
                        for ext in ['.ts', '.tsx', '.js', '.jsx', '.d.ts']:
                            test_path = resolved_path.with_suffix(ext)
                            if test_path.exists():
                                # Return path relative to project root with normalized separators
                                try:
                                    result = str(test_path.relative_to(self.project_root)).replace("\\", "/")
                                    print(f"[DEBUG] SUCCESS: Resolved to existing file: {result}")
                                    return result
                                except ValueError:
                                    # Path is outside project root
                                    result = str(test_path).replace("\\", "/")
                                    print(f"[DEBUG] SUCCESS: Resolved to existing file (outside root): {result}")
                                    return result
                        
                        # Also check for index files
                        for index_name in ['index.ts', 'index.tsx', 'index.js', 'index.jsx']:
                            test_path = resolved_path / index_name
                            if test_path.exists():
                                try:
                                    return str(test_path.relative_to(self.project_root)).replace("\\", "/")
                                except ValueError:
                                    return str(test_path).replace("\\", "/")
                    
                    # If file exists as-is, return it
                    if resolved_path.exists():
                        try:
                            return str(resolved_path.relative_to(self.project_root)).replace("\\", "/")
                        except ValueError:
                            return str(resolved_path).replace("\\", "/")
                    
                    # Return the transformed path even if file doesn't exist
                    # (graph builder will handle non-existent files)
                    try:
                        relative_path = str(resolved_path.relative_to(self.project_root))
                        # Remove leading slash/backslash and normalize separators
                        return relative_path.replace("\\", "/").lstrip("/")
                    except ValueError:
                        # Path is outside project root - return modified import
                        return target_pattern + suffix
        
        # No alias matched - return original path
        print(f"[DEBUG] No alias matched for '{import_path}', returning original")
        return import_path
    
    def resolve_with_context(self, import_path: str, source_file: str, context: str) -> str:
        """Resolve import using the appropriate context's path mappings.
        
        Args:
            import_path: The import string (e.g., '@config/app')
            source_file: The file containing the import
            context: Which tsconfig context ('backend', 'frontend', 'root')
            
        Returns:
            Resolved path or original if no match
        """
        import os
        
        # Handle relative imports (no alias resolution needed)
        if import_path.startswith("."):
            return import_path
        
        # Get mappings for this context
        mappings = self.path_mappings_by_context.get(context, {})
        
        if not mappings and os.environ.get("THEAUDITOR_DEBUG"):
            print(f"[DEBUG] No mappings for context '{context}'")
        
        # Try each alias mapping
        for alias_prefix, target_patterns in mappings.items():
            if import_path.startswith(alias_prefix):
                # Extract suffix after alias
                suffix = import_path[len(alias_prefix):]
                
                # Use first target pattern (TypeScript uses first match)
                if target_patterns:
                    resolved = target_patterns[0] + suffix
                    if os.environ.get("THEAUDITOR_DEBUG"):
                        print(f"[DEBUG] Resolved: {import_path} -> {resolved} (context: {context})")
                    return resolved
        
        # No alias matched - return original
        return import_path
    
    def resolve_webpack_aliases(self, webpack_config_path: str) -> None:
        """Parse webpack.config.js for resolve.alias mappings.
        
        Args:
            webpack_config_path: Path to webpack configuration file
        """
        # This would require JavaScript execution or AST parsing
        # For now, this is a stub for future enhancement
        # Could use subprocess to run Node.js and extract config
        pass
    
    def resolve_with_node_algorithm(self, import_path: str, containing_file: str) -> Optional[str]:
        """Implement Node.js module resolution algorithm.
        
        Follows Node.js rules:
        1. Check relative paths
        2. Check node_modules in current and parent directories
        3. Check global modules
        
        Args:
            import_path: The module to resolve
            containing_file: The file containing the import
            
        Returns:
            Resolved path or None if not found
        """
        containing_dir = Path(containing_file).parent
        
        # For node_modules imports (not relative)
        if not import_path.startswith("."):
            # Walk up directory tree looking for node_modules
            current = containing_dir
            while current != current.parent:
                node_modules = current / "node_modules" / import_path
                
                # Check for package.json main field
                package_json = node_modules / "package.json"
                if package_json.exists():
                    try:
                        pkg_data = json.loads(package_json.read_text())
                        main = pkg_data.get("main", "index.js")
                        main_file = node_modules / main
                        if main_file.exists():
                            return str(main_file.relative_to(self.project_root)).replace("\\", "/")
                    except (json.JSONDecodeError, IOError) as e:
                        print(f"[WARNING] Could not parse package.json from {package_json}: {e}")
                        # Continue checking other resolution methods
                
                # Check for index.js
                index_file = node_modules / "index.js"
                if index_file.exists():
                    return str(index_file.relative_to(self.project_root)).replace("\\", "/")
                
                # Check if it's a file with common extensions
                for ext in ['.js', '.ts', '.jsx', '.tsx', '.json']:
                    file = node_modules.with_suffix(ext)
                    if file.exists():
                        return str(file.relative_to(self.project_root)).replace("\\", "/")
                
                current = current.parent
        
        return None