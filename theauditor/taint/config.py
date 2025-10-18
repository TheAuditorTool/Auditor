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
    sanitizers: Dict[str, List[str]] = field(default_factory=dict)  # FIXED: Must match sources/sinks structure
    registry: Optional[Any] = None  # TaintRegistry if provided
    
    @classmethod
    def from_defaults(cls) -> 'TaintConfig':
        """Create config with default sources and sinks.

        Returns:
            TaintConfig with standard TAINT_SOURCES and SECURITY_SINKS
        """
        from .sources import TAINT_SOURCES, SECURITY_SINKS, SANITIZERS

        return cls(
            sources={k: list(v) for k, v in TAINT_SOURCES.items()},
            sinks={k: list(v) for k, v in SECURITY_SINKS.items()},
            sanitizers={k: list(v) for k, v in SANITIZERS.items()}  # FIXED: Preserve dict structure
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

        # CRITICAL FIX: MERGE registry patterns with defaults, don't replace
        # This preserves the 106 hardcoded sources even when registry is used

        # Merge sources
        merged_sources = dict(self.sources)
        for category, patterns in registry_sources.items():
            if category not in merged_sources:
                merged_sources[category] = []
            # Add new patterns, avoid duplicates
            existing_patterns = set(merged_sources[category])
            for pattern in patterns:
                if pattern not in existing_patterns:
                    merged_sources[category].append(pattern)

        # Merge sinks
        merged_sinks = dict(self.sinks)
        for category, patterns in registry_sinks.items():
            if category not in merged_sinks:
                merged_sinks[category] = []
            existing_patterns = set(merged_sinks[category])
            for pattern in patterns:
                if pattern not in existing_patterns:
                    merged_sinks[category].append(pattern)

        # HARD FAILURE: If merged result is empty, fail loudly
        if not merged_sources and not merged_sinks:
            raise ValueError(
                "TaintRegistry contains no sources or sinks. "
                "Cannot perform taint analysis with empty patterns. "
                "This indicates a configuration error or failed rule loading."
            )

        # Return NEW config with MERGED patterns
        return TaintConfig(
            sources=merged_sources,
            sinks=merged_sinks,
            sanitizers=dict(self.sanitizers),
            registry=registry
        )

    # DELETED: with_frameworks() method (96 lines)
    # Framework patterns are defined in sources.py and loaded via TaintRegistry
    # No need for duplicate definition here
    
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
            sanitizers=data.get('sanitizers', {})
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