"""JSX Rule Registry and Requirement System.

This module provides a registry for tracking which analysis rules require
which JSX extraction modes (preserved vs transformed).

CRITICAL: This ensures rules get the correct data format for their analysis:
- Preserved mode: For structural analysis (accessibility, prop validation)
- Transformed mode: For data flow analysis (taint tracking)
- Both: For correlation rules that need both perspectives
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set
import sqlite3
import logging

logger = logging.getLogger(__name__)


class JsxMode(Enum):
    """JSX processing modes for rules."""
    PRESERVED = "preserved"      # Original JSX syntax
    TRANSFORMED = "transformed"   # React.createElement
    BOTH = "both"               # Needs correlation
    AGNOSTIC = "agnostic"       # Works with either


@dataclass(frozen=True)
class RuleJsxRequirement:
    """Complete rule JSX requirement specification."""

    rule_name: str
    jsx_mode: JsxMode
    required_tables: List[str]
    validates_jsx_structure: bool
    tracks_data_flow: bool

    def get_table_suffix(self) -> str:
        """Get table suffix for this rule's requirements."""
        if self.jsx_mode == JsxMode.PRESERVED:
            return "_jsx"
        return ""

    def validate_database_ready(self, db_path: str) -> bool:
        """Check if database has required tables for this rule."""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        for table in self.required_tables:
            if self.jsx_mode == JsxMode.PRESERVED:
                table = f"{table}_jsx"

            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,)
            )
            if not cursor.fetchone():
                conn.close()
                logger.warning(f"Required table {table} not found for rule {self.rule_name}")
                return False

        conn.close()
        return True


# Complete rule registry
JSX_RULE_REQUIREMENTS: Dict[str, RuleJsxRequirement] = {
    # JSX Structure Rules (need preserved)
    "react_accessibility": RuleJsxRequirement(
        rule_name="react_accessibility",
        jsx_mode=JsxMode.PRESERVED,
        required_tables=["function_returns", "symbols"],
        validates_jsx_structure=True,
        tracks_data_flow=False
    ),

    "jsx_prop_validation": RuleJsxRequirement(
        rule_name="jsx_prop_validation",
        jsx_mode=JsxMode.PRESERVED,
        required_tables=["function_returns", "symbols", "assignments"],
        validates_jsx_structure=True,
        tracks_data_flow=False
    ),

    "jsx_key_prop": RuleJsxRequirement(
        rule_name="jsx_key_prop",
        jsx_mode=JsxMode.PRESERVED,
        required_tables=["function_returns", "symbols"],
        validates_jsx_structure=True,
        tracks_data_flow=False
    ),

    "jsx_conditional_rendering": RuleJsxRequirement(
        rule_name="jsx_conditional_rendering",
        jsx_mode=JsxMode.PRESERVED,
        required_tables=["function_returns", "assignments"],
        validates_jsx_structure=True,
        tracks_data_flow=False
    ),

    # Data Flow Rules (need transformed)
    "taint_analysis": RuleJsxRequirement(
        rule_name="taint_analysis",
        jsx_mode=JsxMode.TRANSFORMED,
        required_tables=["function_call_args", "assignments", "symbols"],
        validates_jsx_structure=False,
        tracks_data_flow=True
    ),

    "xss_detection": RuleJsxRequirement(
        rule_name="xss_detection",
        jsx_mode=JsxMode.TRANSFORMED,
        required_tables=["function_call_args", "assignments", "function_returns"],
        validates_jsx_structure=False,
        tracks_data_flow=True
    ),

    "data_flow_analysis": RuleJsxRequirement(
        rule_name="data_flow_analysis",
        jsx_mode=JsxMode.TRANSFORMED,
        required_tables=["assignments", "function_call_args", "function_returns"],
        validates_jsx_structure=False,
        tracks_data_flow=True
    ),

    # Correlation Rules (need both)
    "jsx_xss_correlation": RuleJsxRequirement(
        rule_name="jsx_xss_correlation",
        jsx_mode=JsxMode.BOTH,
        required_tables=["function_returns", "function_call_args"],
        validates_jsx_structure=True,
        tracks_data_flow=True
    ),

    "component_prop_flow": RuleJsxRequirement(
        rule_name="component_prop_flow",
        jsx_mode=JsxMode.BOTH,
        required_tables=["function_returns", "assignments", "function_call_args"],
        validates_jsx_structure=True,
        tracks_data_flow=True
    ),

    # Agnostic Rules (work with either)
    "react_hooks": RuleJsxRequirement(
        rule_name="react_hooks",
        jsx_mode=JsxMode.AGNOSTIC,
        required_tables=["react_hooks", "variable_usage"],
        validates_jsx_structure=False,
        tracks_data_flow=False
    ),

    "component_detection": RuleJsxRequirement(
        rule_name="component_detection",
        jsx_mode=JsxMode.AGNOSTIC,
        required_tables=["react_components", "function_returns"],
        validates_jsx_structure=False,
        tracks_data_flow=False
    ),
}


class JsxRuleOrchestrator:
    """Orchestrates rule execution based on JSX requirements."""

    def __init__(self, db_path: str):
        """Initialize the orchestrator with database path.

        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = db_path
        self._validate_database()

    def _validate_database(self):
        """Validate that database has necessary tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Check for extraction_metadata table
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='extraction_metadata'"
        )
        if not cursor.fetchone():
            logger.warning("extraction_metadata table not found - JSX mode detection may fail")

        conn.close()

    def get_available_jsx_modes(self) -> Set[str]:
        """Determine which JSX modes are available in the database.

        Returns:
            Set of available JSX modes
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        available_modes = set()

        # Check for preserved mode tables
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='function_returns_jsx'"
        )
        if cursor.fetchone():
            available_modes.add("preserved")

        # Check for transformed mode tables (standard tables)
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='function_returns'"
        )
        if cursor.fetchone():
            available_modes.add("transformed")

        # If both are available, "both" mode is supported
        if "preserved" in available_modes and "transformed" in available_modes:
            available_modes.add("both")

        conn.close()
        return available_modes

    def execute_rules(self, rule_names: Optional[List[str]] = None) -> List[Dict]:
        """Execute rules with proper JSX mode routing.

        Args:
            rule_names: List of rule names to execute, or None for all

        Returns:
            List of findings from all executed rules
        """
        if rule_names is None:
            rule_names = list(JSX_RULE_REQUIREMENTS.keys())

        # Get available modes
        available_modes = self.get_available_jsx_modes()
        if not available_modes:
            logger.error("No JSX extraction data available in database")
            return []

        # Group rules by JSX mode requirement
        preserved_rules = []
        transformed_rules = []
        both_rules = []
        agnostic_rules = []

        for rule_name in rule_names:
            req = JSX_RULE_REQUIREMENTS.get(rule_name)
            if not req:
                # Unknown rule, default to transformed
                logger.warning(f"Unknown rule {rule_name}, defaulting to transformed mode")
                transformed_rules.append(rule_name)
                continue

            # Check if database has required tables
            if not req.validate_database_ready(self.db_path):
                logger.warning(f"Skipping rule {rule_name} - required tables not available")
                continue

            # Route to appropriate execution mode
            if req.jsx_mode == JsxMode.PRESERVED:
                if "preserved" in available_modes:
                    preserved_rules.append(rule_name)
                else:
                    logger.warning(f"Rule {rule_name} requires preserved mode but it's not available")
            elif req.jsx_mode == JsxMode.TRANSFORMED:
                if "transformed" in available_modes:
                    transformed_rules.append(rule_name)
                else:
                    logger.warning(f"Rule {rule_name} requires transformed mode but it's not available")
            elif req.jsx_mode == JsxMode.BOTH:
                if "both" in available_modes:
                    both_rules.append(rule_name)
                else:
                    logger.warning(f"Rule {rule_name} requires both modes but they're not available")
            else:  # AGNOSTIC
                agnostic_rules.append(rule_name)

        # Execute rules in correct context
        findings = []

        if preserved_rules:
            logger.info(f"Executing {len(preserved_rules)} rules in preserved JSX mode")
            ctx = self._create_context(jsx_mode='preserved')
            for rule in preserved_rules:
                findings.extend(self._execute_rule(rule, ctx))

        if transformed_rules:
            logger.info(f"Executing {len(transformed_rules)} rules in transformed JSX mode")
            ctx = self._create_context(jsx_mode='transformed')
            for rule in transformed_rules:
                findings.extend(self._execute_rule(rule, ctx))

        if both_rules:
            logger.info(f"Executing {len(both_rules)} rules with both JSX modes")
            # These rules need access to both datasets
            for rule in both_rules:
                findings.extend(self._execute_correlation_rule(rule))

        if agnostic_rules:
            logger.info(f"Executing {len(agnostic_rules)} mode-agnostic rules")
            ctx = self._create_context(jsx_mode='agnostic')
            for rule in agnostic_rules:
                findings.extend(self._execute_rule(rule, ctx))

        return findings

    def _create_context(self, jsx_mode: str) -> Dict:
        """Create execution context for rules.

        Args:
            jsx_mode: The JSX mode for this context

        Returns:
            Context dictionary with database path and mode info
        """
        return {
            'db_path': self.db_path,
            'jsx_mode': jsx_mode,
            'table_suffix': '_jsx' if jsx_mode == 'preserved' else ''
        }

    def _execute_rule(self, rule_name: str, context: Dict) -> List[Dict]:
        """Execute a single rule.

        Args:
            rule_name: Name of the rule to execute
            context: Execution context

        Returns:
            List of findings from the rule
        """
        # This would dynamically import and execute the rule
        # For now, returning empty list as placeholder
        logger.debug(f"Executing rule {rule_name} with context {context}")
        return []

    def _execute_correlation_rule(self, rule_name: str) -> List[Dict]:
        """Execute a correlation rule that needs both JSX modes.

        Args:
            rule_name: Name of the correlation rule

        Returns:
            List of findings from the rule
        """
        # Correlation rules get special handling with access to both datasets
        preserved_ctx = self._create_context(jsx_mode='preserved')
        transformed_ctx = self._create_context(jsx_mode='transformed')

        # This would execute the correlation rule with both contexts
        logger.debug(f"Executing correlation rule {rule_name}")
        return []


def get_rule_jsx_requirements(rule_name: str) -> Optional[RuleJsxRequirement]:
    """Get JSX requirements for a specific rule.

    Args:
        rule_name: Name of the rule

    Returns:
        RuleJsxRequirement or None if rule not found
    """
    return JSX_RULE_REQUIREMENTS.get(rule_name)


def register_rule_jsx_requirement(rule_name: str, jsx_mode: JsxMode,
                                 required_tables: List[str],
                                 validates_jsx_structure: bool = False,
                                 tracks_data_flow: bool = False):
    """Register JSX requirements for a new rule.

    Args:
        rule_name: Name of the rule
        jsx_mode: JSX mode required
        required_tables: List of required database tables
        validates_jsx_structure: Whether rule validates JSX structure
        tracks_data_flow: Whether rule tracks data flow
    """
    JSX_RULE_REQUIREMENTS[rule_name] = RuleJsxRequirement(
        rule_name=rule_name,
        jsx_mode=jsx_mode,
        required_tables=required_tables,
        validates_jsx_structure=validates_jsx_structure,
        tracks_data_flow=tracks_data_flow
    )
    logger.info(f"Registered JSX requirements for rule {rule_name}")