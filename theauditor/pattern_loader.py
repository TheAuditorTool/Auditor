"""Pattern loader for universal issue detection."""

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Pattern:
    """Represents a single detection pattern."""

    name: str
    description: str
    regex: str | None
    languages: list[str]
    severity: str
    ast_pattern: dict | None = None
    confidence: float | None = None
    files: list[str] | None = None
    examples: list[str] | None = None
    counter_examples: list[str] | None = None
    compiled_regex: re.Pattern | None = field(default=None, init=False, repr=False)

    def __post_init__(self):
        """Compile regex pattern after initialization."""
        if self.regex:
            try:
                self.compiled_regex = re.compile(self.regex, re.IGNORECASE | re.MULTILINE)
            except re.error as e:
                raise ValueError(f"Invalid regex in pattern '{self.name}': {e}") from e

    def matches_language(self, language: str) -> bool:
        """Check if pattern applies to given language."""
        return "*" in self.languages or language.lower() in [
            lang.lower() for lang in self.languages
        ]


class PatternLoader:
    """Loads and manages detection patterns from YAML files."""

    def __init__(self, patterns_dir: Path | None = None):
        """Initialize pattern loader.

        Args:
            patterns_dir: Directory containing pattern YAML files.
                         Defaults to theauditor/patterns/
        """
        if patterns_dir is None:
            patterns_dir = Path(__file__).parent / "rules" / "YAML"
        self.patterns_dir = Path(patterns_dir)
        self.patterns: dict[str, list["Pattern"]] = {}
        self._loaded = False

    def load_patterns(self, categories: list[str] | None = None) -> dict[str, list[Pattern]]:
        """Load patterns from YAML files.

        Args:
            categories: Optional list of categories to load (e.g., ['runtime_issues', 'db_issues'])
                       If None, loads all available patterns.

        Returns:
            Dictionary mapping category names to lists of patterns.
        """
        if not self.patterns_dir.exists():
            raise FileNotFoundError(f"Patterns directory not found: {self.patterns_dir}")

        yaml_files = list(self.patterns_dir.glob("**/*.yml")) + list(
            self.patterns_dir.glob("**/*.yaml")
        )

        yaml_files = [f for f in yaml_files if ".template" not in f.suffixes]

        if not yaml_files:
            self._loaded = True
            return {}

        for yaml_file in yaml_files:
            rel_path = yaml_file.relative_to(self.patterns_dir)

            category = str(rel_path.with_suffix(""))

            if categories and category not in categories:
                continue

            try:
                patterns = self._load_yaml_file(yaml_file)
                self.patterns[category] = patterns
            except Exception as e:
                print(f"Warning: Failed to load {yaml_file}: {e}")

        self._loaded = True
        return self.patterns

    def _load_yaml_file(self, file_path: Path) -> list[Pattern]:
        """Load patterns from a single YAML file.

        Args:
            file_path: Path to YAML file.

        Returns:
            List of Pattern objects.
        """
        with open(file_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict) or "patterns" not in data:
            raise ValueError(f"Invalid pattern file format in {file_path}")

        patterns = []
        for pattern_data in data["patterns"]:
            try:
                pattern = Pattern(
                    name=pattern_data["name"],
                    description=pattern_data["description"],
                    regex=pattern_data.get("regex"),
                    languages=pattern_data.get("languages", ["*"]),
                    severity=pattern_data.get("severity", "medium"),
                    ast_pattern=pattern_data.get("ast_pattern"),
                    confidence=pattern_data.get("confidence"),
                    files=pattern_data.get("files"),
                    examples=pattern_data.get("examples"),
                    counter_examples=pattern_data.get("counter_examples"),
                )
                patterns.append(pattern)
            except (KeyError, ValueError) as e:
                print(f"Warning: Skipping invalid pattern in {file_path}: {e}")

        return patterns

    def get_patterns_for_language(self, language: str) -> list[Pattern]:
        """Get all patterns applicable to a specific language.

        Args:
            language: Programming language (e.g., 'python', 'javascript').

        Returns:
            List of applicable patterns.
        """
        if not self._loaded:
            self.load_patterns()

        applicable_patterns = []
        for category_patterns in self.patterns.values():
            for pattern in category_patterns:
                if pattern.matches_language(language):
                    applicable_patterns.append(pattern)

        return applicable_patterns

    def get_all_patterns(self) -> list[Pattern]:
        """Get all loaded patterns.

        Returns:
            List of all patterns from all categories.
        """
        if not self._loaded:
            self.load_patterns()

        all_patterns = []
        for category_patterns in self.patterns.values():
            all_patterns.extend(category_patterns)

        return all_patterns

    def validate_patterns(self) -> dict[str, list[str]]:
        """Validate all loaded patterns.

        Returns:
            Dictionary of validation errors by category.
        """
        if not self._loaded:
            self.load_patterns()

        errors = {}

        for category, patterns in self.patterns.items():
            category_errors = []

            for pattern in patterns:
                names = [p.name for p in patterns]
                if names.count(pattern.name) > 1:
                    category_errors.append(f"Duplicate pattern name: {pattern.name}")

                valid_severities = ["critical", "high", "medium", "low"]
                if pattern.severity not in valid_severities:
                    category_errors.append(
                        f"Invalid severity '{pattern.severity}' for pattern '{pattern.name}'"
                    )

                if pattern.regex and pattern.compiled_regex is None:
                    category_errors.append(f"Failed to compile regex for pattern '{pattern.name}'")

            if category_errors:
                errors[category] = category_errors

        return errors
