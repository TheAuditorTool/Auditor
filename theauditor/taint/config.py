"""Taint analysis configuration management.

This module provides immutable configuration for taint analysis,
eliminating the need for global state modification.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import json
from pathlib import Path


@dataclass(frozen=True)
class TaintConfig:
    """Immutable configuration for taint analysis.
    
    This class encapsulates all configuration needed for taint analysis,
    including sources, sinks, and optional registry patterns. It's immutable
    to ensure thread safety and prevent accidental modification.
    """
    
    sources: Dict[str, List[str]] = field(default_factory=dict)
    sinks: Dict[str, List[str]] = field(default_factory=dict)
    sanitizers: List[str] = field(default_factory=list)
    registry: Optional[Any] = None  # TaintRegistry if provided
    
    @classmethod
    def from_defaults(cls) -> 'TaintConfig':
        """Create config with default sources and sinks.
        
        Returns:
            TaintConfig with standard TAINT_SOURCES and SECURITY_SINKS
        """
        from .sources import TAINT_SOURCES, SECURITY_SINKS, SANITIZERS
        
        return cls(
            sources=dict(TAINT_SOURCES),
            sinks=dict(SECURITY_SINKS),
            sanitizers=list(SANITIZERS)
        )
    
    def with_frameworks(self, frameworks: List[Dict[str, Any]]) -> 'TaintConfig':
        """Create new config enhanced with framework-specific patterns.
        
        This method returns a NEW TaintConfig instance with additional
        framework patterns, preserving immutability.
        
        Args:
            frameworks: List of framework detection results
            
        Returns:
            New TaintConfig with framework patterns added
        """
        # Create mutable copies of sources and sinks
        enhanced_sources = dict(self.sources)
        enhanced_sinks = dict(self.sinks)
        
        # Add framework-specific patterns
        for fw_info in frameworks:
            framework = fw_info.get("framework", "").lower()
            language = fw_info.get("language", "").lower()
            
            # Django-specific sources
            if framework == "django" and language == "python":
                if "python" not in enhanced_sources:
                    enhanced_sources["python"] = []
                
                django_sources = [
                    "request.GET", "request.POST", "request.FILES",
                    "request.META", "request.session", "request.COOKIES",
                    "request.user", "request.path", "request.path_info",
                    "request.method"
                ]
                
                for source in django_sources:
                    if source not in enhanced_sources["python"]:
                        enhanced_sources["python"].append(source)
            
            # Flask-specific sources
            elif framework == "flask" and language == "python":
                if "python" not in enhanced_sources:
                    enhanced_sources["python"] = []
                
                flask_sources = [
                    "request.args", "request.form", "request.json",
                    "request.data", "request.values", "request.files",
                    "request.cookies", "request.headers", "request.get_json",
                    "request.get_data", "request.environ", "request.view_args"
                ]
                
                for source in flask_sources:
                    if source not in enhanced_sources["python"]:
                        enhanced_sources["python"].append(source)
            
            # FastAPI-specific sources
            elif framework == "fastapi" and language == "python":
                if "python" not in enhanced_sources:
                    enhanced_sources["python"] = []
                
                fastapi_sources = [
                    "Request", "request.url", "request.headers",
                    "request.cookies", "request.query_params", "request.path_params",
                    "request.client", "request.session", "request.auth",
                    "request.user", "request.state",
                    "Query(", "Path(", "Body(", "Header(", "Cookie(",
                    "Form(", "File(", "UploadFile(", "Depends(",
                    "HTTPBearer", "HTTPBasic", "OAuth2PasswordBearer",
                    "APIKeyHeader", "APIKeyCookie", "APIKeyQuery"
                ]
                
                for source in fastapi_sources:
                    if source not in enhanced_sources["python"]:
                        enhanced_sources["python"].append(source)
            
            # Express/Node.js patterns
            elif framework in ["express", "fastify", "koa"] and language == "javascript":
                if "js" not in enhanced_sources:
                    enhanced_sources["js"] = []
                
                node_sources = [
                    "req.body", "req.query", "req.params", "req.headers",
                    "req.cookies", "req.ip", "req.hostname", "req.path", "req.url"
                ]
                
                for source in node_sources:
                    if source not in enhanced_sources["js"]:
                        enhanced_sources["js"].append(source)
                
                # Express-specific sinks
                if "xss" not in enhanced_sinks:
                    enhanced_sinks["xss"] = []
                
                express_xss_sinks = [
                    "res.status().json", "res.status().send", "res.status().jsonp",
                    "res.status().end", "res.redirect", "res.cookie",
                    "res.header", "res.set", "res.jsonp", "res.sendFile",
                    "res.download", "res.sendStatus", "res.format",
                    "res.attachment", "res.append", "res.location"
                ]
                
                for sink in express_xss_sinks:
                    if sink not in enhanced_sinks["xss"]:
                        enhanced_sinks["xss"].append(sink)
                
                # Express SQL sinks
                if "sql" not in enhanced_sinks:
                    enhanced_sinks["sql"] = []
                
                express_sql_sinks = [
                    "models.sequelize.query", "sequelize.query", "knex.raw",
                    "db.raw", "db.query", "pool.query", "client.query"
                ]
                
                for sink in express_sql_sinks:
                    if sink not in enhanced_sinks["sql"]:
                        enhanced_sinks["sql"].append(sink)
                
                # Express path traversal sinks
                if "path" not in enhanced_sinks:
                    enhanced_sinks["path"] = []
                
                express_path_sinks = [
                    "res.sendFile", "res.download", "fs.promises.readFile",
                    "fs.promises.writeFile", "fs.promises.unlink",
                    "fs.promises.rmdir", "fs.promises.mkdir", "require"
                ]
                
                for sink in express_path_sinks:
                    if sink not in enhanced_sinks["path"]:
                        enhanced_sinks["path"].append(sink)
        
        # Return NEW config with enhanced patterns
        return TaintConfig(
            sources=enhanced_sources,
            sinks=enhanced_sinks,
            sanitizers=list(self.sanitizers),
            registry=self.registry
        )
    
    def with_registry(self, registry: Any) -> 'TaintConfig':
        """Create new config with TaintRegistry patterns.
        
        Args:
            registry: TaintRegistry with rule-based patterns
            
        Returns:
            New TaintConfig using registry patterns
        """
        if not registry:
            return self
        
        # Extract patterns from registry
        registry_sources = {}
        for category, patterns in registry.sources.items():
            registry_sources[category] = [p.pattern for p in patterns]
        
        registry_sinks = {}
        for category, patterns in registry.sinks.items():
            registry_sinks[category] = [p.pattern for p in patterns]
        
        # Return NEW config with registry patterns
        return TaintConfig(
            sources=registry_sources,
            sinks=registry_sinks,
            sanitizers=list(self.sanitizers),
            registry=registry
        )
    
    @classmethod
    def load_from_file(cls, config_path: str) -> 'TaintConfig':
        """Load configuration from JSON file.
        
        Args:
            config_path: Path to configuration JSON
            
        Returns:
            TaintConfig loaded from file
        """
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(path, 'r') as f:
            data = json.load(f)
        
        return cls(
            sources=data.get('sources', {}),
            sinks=data.get('sinks', {}),
            sanitizers=data.get('sanitizers', [])
        )
    
    def save_to_file(self, config_path: str):
        """Save configuration to JSON file.
        
        Args:
            config_path: Path to save configuration
        """
        path = Path(config_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            'sources': self.sources,
            'sinks': self.sinks,
            'sanitizers': self.sanitizers
        }
        
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, sort_keys=True)