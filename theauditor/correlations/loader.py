"""Correlation rule loader for the Factual Correlation Engine."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class CorrelationRule:
    """Represents a single correlation rule for factual co-occurrence detection."""
    
    name: str
    co_occurring_facts: List[Dict[str, str]]
    description: Optional[str] = None
    confidence: float = 0.8
    compiled_patterns: List[Dict[str, Any]] = field(default_factory=list, init=False, repr=False)
    
    def __post_init__(self):
        """Compile regex patterns in co-occurring facts after initialization."""
        for fact in self.co_occurring_facts:
            if 'tool' not in fact or 'pattern' not in fact:
                raise ValueError(f"Invalid fact in rule '{self.name}': must contain 'tool' and 'pattern' keys")
            
            compiled_fact = {
                'tool': fact['tool'],
                'pattern': fact['pattern']
            }
            
            # Try to compile as regex, if it fails, treat as literal string
            try:
                compiled_fact['compiled_regex'] = re.compile(fact['pattern'], re.IGNORECASE)
                compiled_fact['is_regex'] = True
            except re.error:
                # Not a valid regex, will be used as literal string match
                compiled_fact['is_regex'] = False
            
            self.compiled_patterns.append(compiled_fact)
    
    def matches_finding(self, finding: Dict[str, Any], fact_index: int) -> bool:
        """Check if a finding matches a specific fact pattern.
        
        Args:
            finding: Dictionary containing finding data with 'tool' and 'rule' keys
            fact_index: Index of the fact pattern to check
            
        Returns:
            True if the finding matches the specified fact pattern
        """
        if fact_index >= len(self.compiled_patterns):
            return False
        
        fact = self.compiled_patterns[fact_index]
        
        # Check tool match
        if finding.get('tool') != fact['tool']:
            return False
        
        # Check pattern match against rule or message
        if fact['is_regex']:
            # Check against rule field and message field
            rule_match = fact['compiled_regex'].search(finding.get('rule', ''))
            message_match = fact['compiled_regex'].search(finding.get('message', ''))
            return bool(rule_match or message_match)
        else:
            # Literal string match
            return (fact['pattern'] in finding.get('rule', '') or 
                    fact['pattern'] in finding.get('message', ''))


class CorrelationLoader:
    """Loads and manages correlation rules from YAML files."""
    
    def __init__(self, rules_dir: Optional[Path] = None):
        """Initialize correlation loader.
        
        Args:
            rules_dir: Directory containing correlation rule YAML files.
                      Defaults to theauditor/correlations/rules/
        """
        if rules_dir is None:
            rules_dir = Path(__file__).parent / "rules"
        self.rules_dir = Path(rules_dir)
        self.rules: List[CorrelationRule] = []
        self._loaded = False
    
    def load_rules(self) -> List[CorrelationRule]:
        """Load correlation rules from YAML files.
        
        Returns:
            List of CorrelationRule objects.
            
        Raises:
            FileNotFoundError: If the rules directory doesn't exist.
        """
        if not self.rules_dir.exists():
            # Create directory if it doesn't exist, but return empty list
            self.rules_dir.mkdir(parents=True, exist_ok=True)
            self._loaded = True
            return self.rules
        
        yaml_files = list(self.rules_dir.glob("*.yml")) + list(self.rules_dir.glob("*.yaml"))
        
        # Clear existing rules before loading
        self.rules = []
        
        for yaml_file in yaml_files:
            try:
                rules = self._load_yaml_file(yaml_file)
                self.rules.extend(rules)
            except Exception as e:
                # Log warning but continue loading other files
                print(f"Warning: Failed to load correlation rules from {yaml_file}: {e}")
        
        self._loaded = True
        return self.rules
    
    def _load_yaml_file(self, file_path: Path) -> List[CorrelationRule]:
        """Load correlation rules from a single YAML file.
        
        Args:
            file_path: Path to YAML file.
            
        Returns:
            List of CorrelationRule objects.
            
        Raises:
            ValueError: If the file format is invalid.
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        if not isinstance(data, dict):
            raise ValueError(f"Invalid rule file format in {file_path}: expected dictionary at root")
        
        rules = []
        
        # Support both single rule and multiple rules formats
        if 'rules' in data:
            # Multiple rules format
            rule_list = data['rules']
            if not isinstance(rule_list, list):
                raise ValueError(f"Invalid rule file format in {file_path}: 'rules' must be a list")
            
            for rule_data in rule_list:
                try:
                    rule = self._parse_rule(rule_data)
                    rules.append(rule)
                except (KeyError, ValueError) as e:
                    print(f"Warning: Skipping invalid rule in {file_path}: {e}")
        
        elif 'name' in data and 'co_occurring_facts' in data:
            # Single rule format
            try:
                rule = self._parse_rule(data)
                rules.append(rule)
            except (KeyError, ValueError) as e:
                print(f"Warning: Skipping invalid rule in {file_path}: {e}")
        
        else:
            raise ValueError(f"Invalid rule file format in {file_path}: must contain 'rules' list or single rule with 'name' and 'co_occurring_facts'")
        
        return rules
    
    def _parse_rule(self, rule_data: Dict[str, Any]) -> CorrelationRule:
        """Parse a single rule from dictionary data.
        
        Args:
            rule_data: Dictionary containing rule data.
            
        Returns:
            CorrelationRule object.
            
        Raises:
            KeyError: If required fields are missing.
            ValueError: If data format is invalid.
        """
        if 'name' not in rule_data:
            raise KeyError("Rule must have a 'name' field")
        
        if 'co_occurring_facts' not in rule_data:
            raise KeyError("Rule must have a 'co_occurring_facts' field")
        
        if not isinstance(rule_data['co_occurring_facts'], list):
            raise ValueError("'co_occurring_facts' must be a list")
        
        if len(rule_data['co_occurring_facts']) == 0:
            raise ValueError("'co_occurring_facts' must not be empty")
        
        return CorrelationRule(
            name=rule_data['name'],
            co_occurring_facts=rule_data['co_occurring_facts'],
            description=rule_data.get('description'),
            confidence=rule_data.get('confidence', 0.8)
        )
    
    def get_all_rules(self) -> List[CorrelationRule]:
        """Get all loaded correlation rules.
        
        Returns:
            List of all loaded CorrelationRule objects.
        """
        if not self._loaded:
            self.load_rules()
        
        return self.rules
    
    def validate_rules(self) -> List[str]:
        """Validate all loaded correlation rules.
        
        Returns:
            List of validation error messages.
        """
        if not self._loaded:
            self.load_rules()
        
        errors = []
        
        # Check for duplicate rule names
        names = [rule.name for rule in self.rules]
        for name in names:
            if names.count(name) > 1:
                errors.append(f"Duplicate rule name: {name}")
        
        # Validate each rule
        for rule in self.rules:
            # Check that each rule has at least 2 co-occurring facts
            if len(rule.co_occurring_facts) < 2:
                errors.append(f"Rule '{rule.name}' has fewer than 2 co-occurring facts")
            
            # Check confidence is between 0 and 1
            if not 0 <= rule.confidence <= 1:
                errors.append(f"Rule '{rule.name}' has invalid confidence value: {rule.confidence}")
        
        return errors