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

        # HARD FAILURE: If registry is empty, fail loudly
        # This prevents silent success with 0 results when registry is malformed
        if not registry_sources and not registry_sinks:
            raise ValueError(
                "TaintRegistry contains no sources or sinks. "
                "Cannot perform taint analysis with empty patterns. "
                "This indicates a configuration error or failed rule loading."
            )

        # Return NEW config with registry patterns
        return TaintConfig(
            sources=registry_sources,
            sinks=registry_sinks,
            sanitizers=list(self.sanitizers),
            registry=registry
        )

    def with_frameworks(self, frameworks: List[Dict[str, str]]) -> 'TaintConfig':
        """Create new config enhanced with framework-specific patterns.

        Args:
            frameworks: List of detected frameworks with name, version, language, path

        Returns:
            New TaintConfig with framework-specific sources/sinks added
        """
        if not frameworks:
            return self

        # Copy existing patterns
        enhanced_sources = dict(self.sources)
        enhanced_sinks = dict(self.sinks)

        # Framework-specific pattern enhancements
        for fw in frameworks:
            fw_name = fw.get('framework', '').lower()
            fw_lang = fw.get('language', '').lower()

            # Django patterns
            if 'django' in fw_name:
                if 'user_input' not in enhanced_sources:
                    enhanced_sources['user_input'] = []
                enhanced_sources['user_input'].extend([
                    'request.GET',
                    'request.POST',
                    'request.FILES',
                    'request.COOKIES',
                ])
                if 'sql_injection' not in enhanced_sinks:
                    enhanced_sinks['sql_injection'] = []
                enhanced_sinks['sql_injection'].extend([
                    '.raw(',
                    '.execute(',
                    'cursor.execute(',
                ])

            # Flask patterns
            elif 'flask' in fw_name:
                if 'user_input' not in enhanced_sources:
                    enhanced_sources['user_input'] = []
                enhanced_sources['user_input'].extend([
                    'request.args',
                    'request.form',
                    'request.files',
                    'request.cookies',
                    'request.json',
                ])

            # Express patterns
            elif 'express' in fw_name:
                if 'user_input' not in enhanced_sources:
                    enhanced_sources['user_input'] = []
                enhanced_sources['user_input'].extend([
                    'req.query',
                    'req.body',
                    'req.params',
                    'req.cookies',
                ])

            # React patterns
            elif 'react' in fw_name:
                if 'xss' not in enhanced_sinks:
                    enhanced_sinks['xss'] = []
                enhanced_sinks['xss'].extend([
                    'dangerouslySetInnerHTML',
                    'innerHTML',
                ])

        # Deduplicate patterns
        for category in enhanced_sources:
            enhanced_sources[category] = list(set(enhanced_sources[category]))
        for category in enhanced_sinks:
            enhanced_sinks[category] = list(set(enhanced_sinks[category]))

        return TaintConfig(
            sources=enhanced_sources,
            sinks=enhanced_sinks,
            sanitizers=list(self.sanitizers),
            registry=self.registry
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