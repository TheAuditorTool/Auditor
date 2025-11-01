"""Central registry for taint sources and sinks.

This module provides a unified registry for all taint patterns, combining
the battle-tested hardcoded patterns with dynamic registration capabilities.
"""

from typing import Dict, List, Set
from dataclasses import dataclass
import sqlite3

# Import the GOOD hardcoded patterns from taint.sources
from theauditor.taint.sources import TAINT_SOURCES, SECURITY_SINKS, SANITIZERS


@dataclass
class TaintPattern:
    """Represents a taint source or sink pattern."""
    pattern: str
    category: str
    language: str
    dynamic: bool = False  # Track if dynamically added


class TaintRegistry:
    """Central registry for all taint patterns.
    
    This provides:
    1. Access to hardcoded patterns (the GOOD ones from 4 days of work)
    2. Dynamic registration from rules
    3. Query interface for pattern matching
    4. Bridge between taint analyzer and rule systems
    """
    
    def __init__(self):
        # Start with the battle-tested hardcoded patterns (650+ patterns)
        self.sources = self._convert_to_registry(TAINT_SOURCES, is_source=True)
        self.sinks = self._convert_to_registry(SECURITY_SINKS, is_source=False)
        self.sanitizers = SANITIZERS.copy()
        
        # Track dynamic additions for debugging
        self.dynamic_sources: Set[str] = set()
        self.dynamic_sinks: Set[str] = set()
    
    def _convert_to_registry(self, patterns_dict: Dict, is_source: bool) -> Dict[str, List[TaintPattern]]:
        """Convert hardcoded pattern dict to registry format.
        
        Args:
            patterns_dict: Dictionary of patterns from taint_analyzer
            is_source: Whether these are source patterns (vs sinks)
            
        Returns:
            Registry-formatted dictionary with TaintPattern objects
        """
        registry = {}
        for category, patterns in patterns_dict.items():
            registry[category] = []
            for pattern in patterns:
                # Detect language from category
                if category in ["js", "javascript", "typescript"]:
                    lang = "javascript"
                elif category in ["python", "py"]:
                    lang = "python"
                elif category == "network":
                    lang = "any"
                elif category == "web_scraping":
                    lang = "python"  # Most web scraping is Python
                elif category == "file_io":
                    lang = "any"
                else:
                    lang = "any"
                
                registry[category].append(TaintPattern(
                    pattern=pattern,
                    category=category,
                    language=lang,
                    dynamic=False  # These are all hardcoded patterns
                ))
        return registry
    
    def register_source(self, pattern: str, category: str, language: str = "any"):
        """Allow rules to register additional taint sources dynamically.
        
        Args:
            pattern: The taint source pattern (e.g., "getUserInput")
            category: Category for the pattern (e.g., "user_input")
            language: Language this applies to (default "any")
        """
        if category not in self.sources:
            self.sources[category] = []
        
        # Check if pattern already exists
        existing = [p for p in self.sources[category] if p.pattern == pattern]
        if not existing:
            self.sources[category].append(TaintPattern(
                pattern=pattern,
                category=category,
                language=language,
                dynamic=True
            ))
            self.dynamic_sources.add(pattern)
    
    def register_sink(self, pattern: str, category: str, language: str = "any"):
        """Allow rules to register additional security sinks dynamically.
        
        Args:
            pattern: The sink pattern (e.g., "dangerousFunction")
            category: Category for the pattern (e.g., "code_execution")
            language: Language this applies to (default "any")
        """
        if category not in self.sinks:
            self.sinks[category] = []
        
        # Check if pattern already exists
        existing = [p for p in self.sinks[category] if p.pattern == pattern]
        if not existing:
            self.sinks[category].append(TaintPattern(
                pattern=pattern,
                category=category,
                language=language,
                dynamic=True
            ))
            self.dynamic_sinks.add(pattern)
    
    def get_all_sources(self) -> List[str]:
        """Get all source patterns for taint analysis.
        
        Returns:
            Flat list of all source patterns
        """
        patterns = []
        for category_patterns in self.sources.values():
            patterns.extend([p.pattern for p in category_patterns])
        return patterns
    
    def get_all_sinks(self) -> List[Dict[str, str]]:
        """Get all sink patterns in taint analyzer format.
        
        Returns:
            List of sink dictionaries with pattern and category
        """
        sinks = []
        for category, patterns in self.sinks.items():
            for pattern in patterns:
                sinks.append({
                    "pattern": pattern.pattern,
                    "category": category,
                    "name": pattern.pattern,
                    "type": "sink"
                })
        return sinks
    
    def get_sources_by_language(self, language: str) -> List[str]:
        """Get source patterns for a specific language.
        
        Args:
            language: Language to filter by (e.g., "python", "javascript")
            
        Returns:
            List of source patterns for that language
        """
        patterns = []
        for category_patterns in self.sources.values():
            for p in category_patterns:
                if p.language == language or p.language == "any":
                    patterns.append(p.pattern)
        return patterns
    
    def get_sinks_by_language(self, language: str) -> List[str]:
        """Get sink patterns for a specific language.
        
        Args:
            language: Language to filter by (e.g., "python", "javascript")
            
        Returns:
            List of sink patterns for that language
        """
        patterns = []
        for category_patterns in self.sinks.values():
            for p in category_patterns:
                if p.language == language or p.language == "any":
                    patterns.append(p.pattern)
        return patterns
    
    def is_sanitizer(self, function_name: str) -> bool:
        """Check if a function is a known sanitizer.
        
        Args:
            function_name: Name of the function to check
            
        Returns:
            True if the function is a known sanitizer
        """
        if not function_name:
            return False
        
        func_lower = function_name.lower()
        
        # Check all sanitizer categories
        for sanitizer_list in self.sanitizers.values():
            for sanitizer in sanitizer_list:
                if sanitizer.lower() in func_lower or func_lower in sanitizer.lower():
                    return True
        
        return False
    
    def get_stats(self) -> Dict[str, int]:
        """Get statistics about registered patterns.
        
        Returns:
            Dictionary with counts of various pattern types
        """
        total_sources = sum(len(patterns) for patterns in self.sources.values())
        total_sinks = sum(len(patterns) for patterns in self.sinks.values())
        total_sanitizers = sum(len(patterns) for patterns in self.sanitizers.values())
        
        return {
            "total_sources": total_sources,
            "total_sinks": total_sinks,
            "total_sanitizers": total_sanitizers,
            "dynamic_sources": len(self.dynamic_sources),
            "dynamic_sinks": len(self.dynamic_sinks),
            "source_categories": len(self.sources),
            "sink_categories": len(self.sinks),
            "sanitizer_categories": len(self.sanitizers)
        }