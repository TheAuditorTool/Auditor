"""Core taint analysis engine.

This module contains the main taint analysis function and TaintPath class.
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, TYPE_CHECKING
from collections import defaultdict

if TYPE_CHECKING:
    from .memory_cache import MemoryCache

from .sources import TAINT_SOURCES, SECURITY_SINKS, SANITIZERS
from .config import TaintConfig
from .database import (
    find_taint_sources,
    find_security_sinks,
    build_call_graph,
    get_containing_function,
)
from .propagation import trace_from_source, deduplicate_paths


class TaintPath:
    """Represents a taint flow path from source to sink."""
    
    def __init__(self, source: Dict[str, Any], sink: Dict[str, Any], path: List[Dict[str, Any]]):
        self.source = source
        self.sink = sink
        self.path = path
        self.vulnerability_type = self._classify_vulnerability()
    
    def _classify_vulnerability(self) -> str:
        """Classify the vulnerability based on sink type - factual categorization."""
        sink_name = self.sink.get("name", "").lower()
        sink_category = self.sink.get("category", "")
        
        # Use category if available, otherwise infer from name
        if sink_category:
            category_map = {
                "sql": "SQL Injection",
                "command": "Command Injection", 
                "xss": "Cross-Site Scripting (XSS)",
                "path": "Path Traversal",
                "ldap": "LDAP Injection",
                "nosql": "NoSQL Injection"
            }
            return category_map.get(sink_category, "Data Exposure")
        
        # Fallback: infer from sink name patterns
        for vuln_type, sinks in SECURITY_SINKS.items():
            if any(s.lower() in sink_name for s in sinks):
                return {
                    "sql": "SQL Injection",
                    "command": "Command Injection",
                    "xss": "Cross-Site Scripting (XSS)",
                    "path": "Path Traversal",
                    "ldap": "LDAP Injection",
                    "nosql": "NoSQL Injection"
                }.get(vuln_type, "Data Exposure")
        
        return "Data Exposure"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization with guaranteed structure."""
        # Ensure source dict has all required keys
        source_dict = self.source or {}
        source_dict.setdefault("name", "unknown_source")
        source_dict.setdefault("file", "unknown_file")
        source_dict.setdefault("line", 0)
        source_dict.setdefault("pattern", "unknown_pattern")
        
        # Ensure sink dict has all required keys
        sink_dict = self.sink or {}
        sink_dict.setdefault("name", "unknown_sink")
        sink_dict.setdefault("file", "unknown_file")
        sink_dict.setdefault("line", 0)
        sink_dict.setdefault("pattern", "unknown_pattern")
        
        return {
            "source": source_dict,
            "sink": sink_dict,
            "path": self.path or [],
            "path_length": len(self.path) if self.path else 0,
            "vulnerability_type": self.vulnerability_type
        }


def trace_taint(db_path: str, max_depth: int = 5, registry=None, 
                use_cfg: bool = False, stage3: bool = False,
                use_memory_cache: bool = True, memory_limit_mb: int = 12000,
                cache: Optional['MemoryCache'] = None) -> Dict[str, Any]:
    """
    Perform taint analysis by tracing data flow from sources to sinks.
    
    Args:
        db_path: Path to the SQLite database
        max_depth: Maximum depth to trace taint propagation
        registry: Optional TaintRegistry with enriched patterns from rules
        use_cfg: Enable flow-sensitive CFG analysis (Stage 2)
        stage3: Enable inter-procedural CFG with caching (Stage 3)
        use_memory_cache: Enable in-memory caching for performance (default: True)
        memory_limit_mb: Memory limit for cache in MB (default: 12000)
        cache: Optional pre-loaded MemoryCache to use (avoids reload)
        
    Returns:
        Dictionary containing:
        - taint_paths: List of source-to-sink vulnerability paths
        - sources_found: Number of taint sources identified
        - sinks_found: Number of security sinks identified
        - vulnerabilities: Count by vulnerability type
    """
    import sqlite3
    import os
    
    # Create configuration instead of modifying globals
    # This ensures thread safety and reentrancy
    
    # Load framework data to enhance analysis
    frameworks = []
    frameworks_path = Path(".pf/frameworks.json")
    if frameworks_path.exists():
        try:
            with open(frameworks_path, 'r') as f:
                frameworks = json.load(f)
        except (json.JSONDecodeError, IOError):
            # Gracefully continue without framework data
            pass
    
    # CRITICAL: Use registry if provided, otherwise use framework enhancement
    if registry:
        # Use registry's enriched patterns (from rules)
        dynamic_sources = {}
        for category, patterns in registry.sources.items():
            dynamic_sources[category] = [p.pattern for p in patterns]
        
        dynamic_sinks = {}
        for category, patterns in registry.sinks.items():
            dynamic_sinks[category] = [p.pattern for p in patterns]
        
        # Registry already has all framework patterns from rules
        # Skip the framework enhancement below
    else:
        # Original framework enhancement logic
        # Dynamically extend taint sources based on detected frameworks
        # Create local copies to avoid modifying global constants
        dynamic_sources = dict(TAINT_SOURCES)
        dynamic_sinks = dict(SECURITY_SINKS)
        
        # Add framework-specific patterns
        for fw_info in frameworks:
            framework = fw_info.get("framework", "").lower()
            language = fw_info.get("language", "").lower()
            
            # Django-specific sources (uppercase patterns)
            if framework == "django" and language == "python":
                if "python" not in dynamic_sources:
                    dynamic_sources["python"] = []
                    django_sources = [
                    "request.GET",
                    "request.POST",
                    "request.FILES",
                    "request.META",
                    "request.session",
                    "request.COOKIES",
                    "request.user",
                    "request.path",
                    "request.path_info",
                    "request.method",
                ]
                # Add Django sources if not already present
                for source in django_sources:
                    if source not in dynamic_sources["python"]:
                        dynamic_sources["python"].append(source)
            
            # Flask-specific sources (already mostly covered but ensure completeness)
            elif framework == "flask" and language == "python":
                if "python" not in dynamic_sources:
                    dynamic_sources["python"] = []
                flask_sources = [
                "request.args",
                "request.form",
                "request.json",
                "request.data",
                "request.values",
                "request.files",
                "request.cookies",
                "request.headers",
                "request.get_json",
                "request.get_data",
                "request.environ",
                "request.view_args",
                ]
                for source in flask_sources:
                    if source not in dynamic_sources["python"]:
                        dynamic_sources["python"].append(source)
            
            # FastAPI-specific sources 
            elif framework == "fastapi" and language == "python":
                if "python" not in dynamic_sources:
                    dynamic_sources["python"] = []
                fastapi_sources = [
                # Starlette Request object (used in FastAPI)
                "Request",
                "request.url",
                "request.headers",
                "request.cookies",
                "request.query_params",
                "request.path_params",
                "request.client",
                "request.session",
                "request.auth",
                "request.user",
                "request.state",
                # FastAPI dependency injection parameters
                "Query(",
                "Path(",
                "Body(",
                "Header(",
                "Cookie(",
                "Form(",
                "File(",
                "UploadFile(",
                "Depends(",
                # FastAPI security
                "HTTPBearer",
                "HTTPBasic",
                "OAuth2PasswordBearer",
                "APIKeyHeader",
                "APIKeyCookie",
                "APIKeyQuery",
                ]
                for source in fastapi_sources:
                    if source not in dynamic_sources["python"]:
                        dynamic_sources["python"].append(source)
            
            # Express/Node.js sources
            elif framework in ["express", "fastify", "koa"] and language == "javascript":
                if "js" not in dynamic_sources:
                    dynamic_sources["js"] = []
                node_sources = [
                "req.body",
                "req.query",
                "req.params",
                "req.headers",
                "req.cookies",
                "req.ip",
                "req.hostname",
                "req.path",
                "req.url",
                ]
                for source in node_sources:
                    if source not in dynamic_sources["js"]:
                        dynamic_sources["js"].append(source)
                
                # CRITICAL FIX: Add Express.js specific sinks
                if "xss" not in dynamic_sinks:
                    dynamic_sinks["xss"] = []
                # Ensure it's a list (not a reference to the original)
                if not isinstance(dynamic_sinks["xss"], list):
                    dynamic_sinks["xss"] = list(dynamic_sinks["xss"])
                express_xss_sinks = [
                # Express response methods with chained status
                "res.status().json",
                "res.status().send", 
                "res.status().jsonp",
                "res.status().end",
                # Other Express response methods
                "res.redirect",
                "res.cookie",
                "res.header",
                "res.set",
                "res.jsonp",
                "res.sendFile",  # Path traversal risk
                "res.download",  # Path traversal risk
                "res.sendStatus",
                "res.format",
                "res.attachment",
                "res.append",
                "res.location",
                ]
                for sink in express_xss_sinks:
                    if sink not in dynamic_sinks["xss"]:
                        dynamic_sinks["xss"].append(sink)
                
                # Add Express SQL sinks for ORMs commonly used with Express
                if "sql" not in dynamic_sinks:
                    dynamic_sinks["sql"] = []
                # Ensure it's a list (not a reference to the original)
                if not isinstance(dynamic_sinks["sql"], list):
                    dynamic_sinks["sql"] = list(dynamic_sinks["sql"])
                express_sql_sinks = [
                "models.sequelize.query",  # Sequelize raw queries
                "sequelize.query",
                "knex.raw",  # Knex.js raw queries
                "db.raw",
                "db.query",
                "pool.query",  # Direct pg pool queries
                "client.query",  # Direct database client queries
                ]
                for sink in express_sql_sinks:
                    if sink not in dynamic_sinks["sql"]:
                        dynamic_sinks["sql"].append(sink)
                
                # Add path traversal sinks specific to Express/Node.js
                if "path" not in dynamic_sinks:
                    dynamic_sinks["path"] = []
                # Ensure it's a list (not a reference to the original)
                if not isinstance(dynamic_sinks["path"], list):
                    dynamic_sinks["path"] = list(dynamic_sinks["path"])
                express_path_sinks = [
                "res.sendFile",
                "res.download", 
                "fs.promises.readFile",
                "fs.promises.writeFile",
                "fs.promises.unlink",
                "fs.promises.rmdir",
                "fs.promises.mkdir",
                "require",  # Dynamic require with user input
                ]
                for sink in express_path_sinks:
                    if sink not in dynamic_sinks["path"]:
                        dynamic_sinks["path"].append(sink)
    
    # Create immutable config with all patterns
    if registry:
        # Use registry configuration
        config = TaintConfig().with_registry(registry)
    else:
        # Use enhanced configuration with frameworks
        config = TaintConfig(
            sources=dynamic_sources,
            sinks=dynamic_sinks,
            sanitizers=SANITIZERS
        )
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Attempt to preload database into memory cache for performance
    # CRITICAL FIX: Use provided cache if available (avoids reload in pipeline)
    if use_memory_cache:
        if cache is None:  # Only create if not provided
            from .memory_cache import attempt_cache_preload
            cache = attempt_cache_preload(cursor, memory_limit_mb)
            if cache:
                print(f"[TAINT] Memory cache enabled: {cache.get_memory_usage_mb():.1f}MB used", file=sys.stderr)
            else:
                print("[TAINT] Memory cache disabled: falling back to disk queries", file=sys.stderr)
        else:
            # Using pre-loaded cache from pipeline
            print(f"[TAINT] Using pre-loaded cache: {cache.get_memory_usage_mb():.1f}MB", file=sys.stderr)
    else:
        cache = None  # Explicitly disable cache if not requested
    
    try:
        # Step 1: Find all taint sources in the codebase
        # Pass config sources instead of global TAINT_SOURCES
        sources = find_taint_sources(cursor, config.sources, cache=cache)
        
        # Step 2: Find all security sinks in the codebase
        # Pass config sinks instead of global SECURITY_SINKS
        sinks = find_security_sinks(cursor, config.sinks, cache=cache)
        
        # Step 3: Build a call graph for efficient traversal
        call_graph = build_call_graph(cursor)
        
        # Step 4: Trace taint flow from each source
        taint_paths = []
        
        for source in sources:
            # Find what function contains this source
            source_function = get_containing_function(cursor, source)
            if not source_function:
                continue
            
            # Trace taint propagation from this source
            paths = trace_from_source(
                cursor, source, source_function, sinks, call_graph, max_depth, use_cfg, stage3, cache=cache
            )
            taint_paths.extend(paths)
        
        # Step 5: Deduplicate paths
        unique_paths = deduplicate_paths(taint_paths)
        
        # Step 6: Build factual summary with vulnerability counts
        # Count vulnerabilities by type (factual categorization, not interpretation)
        vulnerabilities_by_type = defaultdict(int)
        for path in unique_paths:
            vuln_type = path.vulnerability_type
            vulnerabilities_by_type[vuln_type] += 1
        
        # Convert paths to dictionaries
        path_dicts = [p.to_dict() for p in unique_paths]
        
        # Create summary for pipeline integration
        summary = {
            "total_count": len(unique_paths),
            "by_type": dict(vulnerabilities_by_type),
            # Basic counts for pipeline - no severity interpretation
            "critical_count": 0,  # Base analyzer doesn't assign severity
            "high_count": 0,
            "medium_count": 0,
            "low_count": 0
        }
        
        return {
            "success": True,
            "taint_paths": path_dicts,  # Keep original key for backward compatibility
            "vulnerabilities": path_dicts,  # Expected key for pipeline
            "paths": path_dicts,  # Add expected key for report generation
            "sources_found": len(sources),
            "sinks_found": len(sinks),
            "total_vulnerabilities": len(unique_paths),  # Expected field name
            "total_flows": len(unique_paths),  # Keep for compatibility
            "vulnerabilities_by_type": dict(vulnerabilities_by_type),
            "summary": summary
        }
        
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            return {
                "success": False,
                "error": "Database is corrupted or incomplete. Run 'aud index' to rebuild the repository index.",
                "taint_paths": [],
                "vulnerabilities": [],
                "paths": [],  # Include both keys for compatibility
                "sources_found": 0,
                "sinks_found": 0,
                "total_vulnerabilities": 0,
                "total_flows": 0,
                "vulnerabilities_by_type": {},
                "summary": {"total_count": 0, "by_type": {}, "critical_count": 0, "high_count": 0, "medium_count": 0, "low_count": 0}
            }
        else:
            return {
                "success": False,
                "error": str(e),
                "taint_paths": [],
                "vulnerabilities": [],
                "paths": [],
                "sources_found": 0,
                "sinks_found": 0,
                "total_vulnerabilities": 0,
                "total_flows": 0,
                "vulnerabilities_by_type": {},
                "summary": {"total_count": 0, "by_type": {}, "critical_count": 0, "high_count": 0, "medium_count": 0, "low_count": 0}
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "taint_paths": [],
            "vulnerabilities": [],
            "paths": [],  # Include both keys for compatibility
            "sources_found": 0,
            "sinks_found": 0,
            "total_vulnerabilities": 0,
            "total_flows": 0,
            "vulnerabilities_by_type": {},
            "summary": {"total_count": 0, "by_type": {}, "critical_count": 0, "high_count": 0, "medium_count": 0, "low_count": 0}
        }
    finally:
        conn.close()
        # No need to restore globals - we never modified them!


def save_taint_analysis(analysis_result: Dict[str, Any], output_path: str = "./.pf/taint_analysis.json"):
    """Save taint analysis results to JSON file with normalized structure."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    
    # Normalize all paths before saving
    if "taint_paths" in analysis_result:
        analysis_result["taint_paths"] = [
            normalize_taint_path(p) for p in analysis_result.get("taint_paths", [])
        ]
    if "paths" in analysis_result:
        analysis_result["paths"] = [
            normalize_taint_path(p) for p in analysis_result.get("paths", [])
        ]
    
    with open(output, "w") as f:
        json.dump(analysis_result, f, indent=2, sort_keys=True)


def normalize_taint_path(path: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a taint path dictionary to ensure all required keys exist."""
    # Ensure top-level keys
    # REMOVED: vulnerability_type and severity - Truth Couriers don't classify
    path.setdefault("path_length", 0)
    path.setdefault("path", [])
    
    # Ensure source structure
    if "source" not in path:
        path["source"] = {}
    path["source"].setdefault("name", "unknown_source")
    path["source"].setdefault("file", "unknown_file")
    path["source"].setdefault("line", 0)
    path["source"].setdefault("pattern", "unknown_pattern")
    
    # Ensure sink structure
    if "sink" not in path:
        path["sink"] = {}
    path["sink"].setdefault("name", "unknown_sink")
    path["sink"].setdefault("file", "unknown_file")
    path["sink"].setdefault("line", 0)
    path["sink"].setdefault("pattern", "unknown_pattern")
    
    return path