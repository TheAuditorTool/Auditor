# Contributing to TheAuditor

Thank you for your interest in contributing to TheAuditor! We're excited to have you join our mission to bring ground truth to AI-assisted development. This guide will help you get started with contributing to the project.

## How to Get Involved

### Reporting Bugs

Found a bug? Please help us fix it!

1. Check existing [GitHub Issues](https://github.com/TheAuditorTool/Auditor/issues) to see if it's already reported
2. If not, create a new issue with:
   - Clear description of the bug
   - Steps to reproduce
   - Expected vs actual behavior
   - Your environment details (OS, Python version, Node.js version)

### Suggesting Enhancements

Have an idea for improving TheAuditor?

1. Review our [ROADMAP.md](ROADMAP.md) to see if it aligns with our vision
2. Check [GitHub Issues](https://github.com/TheAuditorTool/Auditor/issues) for similar suggestions
3. Create a new issue describing:
   - The problem you're trying to solve
   - Your proposed solution
   - Why this would benefit TheAuditor users

## Setting Up Your Development Environment

Follow these steps to get TheAuditor running locally for development:

```bash
# Clone the repository
git clone https://github.com/TheAuditorTool/Auditor.git
cd theauditor

# Create a Python virtual environment
python -m venv .venv

# Activate the virtual environment
# On Linux/macOS:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate

# Install TheAuditor in development mode
pip install -e .

# Optional: Install with ML capabilities
# pip install -e ".[ml]"

# For development with all optional dependencies:
# pip install -e ".[all]"

# MANDATORY: Set up the sandboxed environment
# This is required for TheAuditor to function at all
aud setup-ai --target .
```

The `aud setup-ai --target .` command creates an isolated environment at `.auditor_venv/.theauditor_tools/` with all necessary JavaScript and TypeScript analysis tools. This ensures consistent, reproducible results across all development environments.

## Making Changes & Submitting a Pull Request

### Development Workflow

1. **Fork the repository** on GitHub
2. **Create a feature branch** from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Make your changes** following our code standards (see below)
4. **Write/update tests** if applicable
5. **Commit your changes** with clear, descriptive messages:
   ```bash
   git commit -m "Add GraphQL schema analyzer for type validation"
   ```
6. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```
7. **Create a Pull Request** on GitHub with:
   - Clear description of changes
   - Link to any related issues
   - Test results or examples

## Code Standards

We use **ruff** for both linting and formatting Python code. Before submitting any code, you MUST run:

```bash
# Fix any auto-fixable issues and check for remaining problems
ruff check . --fix

# Format all Python code
ruff format .
```

Your pull request will not be merged if it fails these checks.

### Additional Quality Checks

For comprehensive code quality, you can also run:

```bash
# Type checking (optional but recommended)
mypy theauditor --strict

# Run tests
pytest tests/

# Full linting suite
make lint
```

### Code Style Guidelines

- Follow PEP 8 for Python code
- Use descriptive variable and function names
- Add docstrings to all public functions and classes
- Keep functions focused and small (under 50 lines preferred)
- Write self-documenting code; minimize comments
- Never commit secrets, API keys, or credentials

## Adding Support for New Languages

TheAuditor's modular architecture makes it straightforward to add support for new programming languages. This section provides comprehensive guidance for contributors looking to expand our language coverage.

### Overview

Adding a new language to TheAuditor involves:
- Creating a parser for the language
- Adding framework detection patterns
- Creating security pattern rules
- Writing comprehensive tests
- Updating documentation

### Prerequisites

Before starting, ensure you have:
- Deep knowledge of the target language and its ecosystem
- Understanding of common security vulnerabilities in that language
- Familiarity with AST (Abstract Syntax Tree) concepts
- Python development experience

### Step-by-Step Guide

#### Step 1: Create the Language Extractor

Create a new extractor in `theauditor/indexer/extractors/{language}.py` that inherits from `BaseExtractor`:

```python
from . import BaseExtractor

class {Language}Extractor(BaseExtractor):
    def supported_extensions(self) -> List[str]:
        """Return list of file extensions this extractor supports."""
        return ['.ext', '.ext2']
    
    def extract(self, file_info: Dict[str, Any], content: str, 
                tree: Optional[Any] = None) -> Dict[str, Any]:
        """Extract all relevant information from a file."""
        return {
            'imports': self.extract_imports(content, file_info['ext']),
            'routes': self.extract_routes(content),
            'symbols': [],  # Add symbol extraction logic
            'assignments': [],  # For taint analysis
            'function_calls': [],  # For call graph
            'returns': []  # For data flow
        }
```

The extractor will be automatically registered through the `BaseExtractor` inheritance pattern.

#### Step 2: Create Configuration Parser (Optional)

If your language has configuration files that need parsing, create a parser in `theauditor/parsers/{language}_parser.py`:

```python
class {Language}Parser:
    def parse_file(self, file_path: Path) -> Dict[str, Any]:
        """Parse configuration file and extract security-relevant data."""
        # Parse and return structured data
        return parsed_data
```

#### Step 3: Add Framework Detection

Add your language's frameworks to `theauditor/framework_registry.py`:

```python
# Add to FRAMEWORK_REGISTRY dictionary
"{framework_name}": {
    "language": "{language}",
    "detection_sources": {
        # Package manifest files
        "package.{ext}": [
            ["dependencies"],
            ["devDependencies"],
        ],
        # Or for line-based search
        "requirements.txt": "line_search",
        # Or for content search
        "build.file": "content_search",
    },
    "package_pattern": "{framework_package_name}",
    "import_patterns": ["import {framework}", "from {framework}"],
    "file_markers": ["config.{ext}", "app.{ext}"],
}
```

#### Step 4: Create Language-Specific Patterns

Create security patterns for your language in `theauditor/patterns/{language}.yml`:

Example pattern structure:
```yaml
- name: hardcoded-secret-{language}
  pattern: '(api[_-]?key|secret|token|password)\s*=\s*["\'][^"\']+["\']'
  severity: critical
  category: security
  languages: ["{language}"]
  description: "Hardcoded secret detected in {Language} code"
  cwe: CWE-798
```

#### Step 5: Create AST-Based Rules (Optional but Recommended)

For complex security patterns, create AST-based rules in `theauditor/rules/{language}/`:

```python
"""Security rules for {Language} using AST analysis."""

from typing import Any, Dict, List

def find_{vulnerability}_issues(ast_tree: Any, file_path: str) -> List[Dict[str, Any]]:
    """Find {vulnerability} issues in {Language} code.
    
    Args:
        ast_tree: Parsed AST from {language}_parser
        file_path: Path to the source file
        
    Returns:
        List of findings with standard format
    """
    findings = []
    
    # Implement AST traversal and pattern detection
    for node in walk_ast(ast_tree):
        if is_vulnerable_pattern(node):
            findings.append({
                'pattern_name': '{VULNERABILITY}_ISSUE',
                'message': 'Detailed description of the issue',
                'file': file_path,
                'line': node.line,
                'column': node.column,
                'severity': 'high',
                'snippet': extract_snippet(node),
                'category': 'security',
                'match_type': 'ast'
            })
    
    return findings
```

### Extractor Interface Specification

All language extractors MUST inherit from `BaseExtractor` and implement:

```python
from theauditor.indexer.extractors import BaseExtractor

class LanguageExtractor(BaseExtractor):
    """Extractor for {Language} files."""
    
    def supported_extensions(self) -> List[str]:
        """Return list of supported file extensions."""
        return ['.ext']
    
    def extract(self, file_info: Dict[str, Any], content: str, 
                tree: Optional[Any] = None) -> Dict[str, Any]:
        """Extract all relevant information from a file."""
        return {
            'imports': [],
            'routes': [],
            'symbols': [],
            'assignments': [],
            'function_calls': [],
            'returns': []
        }
```

### Testing Requirements

#### Required Test Coverage

1. **Extractor Tests** (`tests/test_{language}_extractor.py`):
   - Test extracting from valid files
   - Test handling of syntax errors
   - Test symbol extraction
   - Test import extraction
   - Test file extension detection

2. **Pattern Tests** (`tests/patterns/test_{language}_patterns.py`):
   - Test security pattern detection
   - Ensure patterns don't over-match (false positives)

3. **Integration Tests** (`tests/integration/test_{language}_integration.py`):
   - Test language in complete analysis pipeline

#### Test Data

Create test fixtures in `tests/fixtures/{language}/`:
- `valid_code.{ext}` - Valid code samples
- `vulnerable_code.{ext}` - Code with known vulnerabilities
- `edge_cases.{ext}` - Edge cases and corner scenarios

### Submission Checklist

Before submitting your PR, ensure:

- [ ] Extractor inherits from `BaseExtractor` and implements required methods
- [ ] Extractor placed in `theauditor/indexer/extractors/{language}.py`
- [ ] Framework detection added to `framework_detector.py` (if applicable)
- [ ] At least 10 security patterns created in `patterns/{language}.yml`
- [ ] AST-based rules for complex patterns (if applicable)
- [ ] All tests passing with >80% coverage
- [ ] Documentation updated (extractor docstrings, pattern descriptions)
- [ ] Example vulnerable code provided in test fixtures
- [ ] No external dependencies without approval
- [ ] Code follows project style (run `ruff format`)

## Adding New Analyzers

### The Three-Tier Detection Architecture

TheAuditor uses a hybrid approach to detection, prioritizing accuracy and context. When contributing a new rule, please adhere to the following "AST First, Regex as Fallback" philosophy:

-   **Tier 1: Multi-Language AST Rules (Preferred)**
    For complex code patterns in source code (Python, JS/TS, etc.), extend or create a polymorphic AST-based rule in the `/rules` directory. These are the most powerful and accurate and should be the default choice for source code analysis.

-   **Tier 2: Language-Specific AST Rules**
    If a multi-language backend is not feasible, a language-specific AST rule is the next best option. The corresponding regex pattern should then be scoped to exclude the language covered by the AST rule (see `db_issues.yml` for an example).

-   **Tier 3: Regex Patterns (YAML)**
    Regex patterns in `/patterns` should be reserved for:
    1.  Simple patterns where an AST is overkill.
    2.  Configuration files where no AST parser exists (e.g., `.yml`, `.conf`).
    3.  Providing baseline coverage for languages not yet supported by an AST rule.

TheAuditor uses a modular architecture. To add new analysis capabilities:

### Database-Aware Rules
For rules that query across multiple files:
```python
# theauditor/rules/category/new_analyzer.py
def find_new_issues(db_path: str) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    # Query the repo_index.db
    # Return findings in standard format
```

Example ORM analyzer:
```python
# theauditor/rules/orm/sequelize_detector.py
def find_sequelize_issues(db_path: str) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT file, line, query_type, includes FROM orm_queries"
    )
    # Analyze for N+1 queries, death queries, etc.
```

### AST-Based Rules
For semantic code analysis:
```python
# theauditor/rules/framework/new_detector.py
def find_framework_issues(tree: Any, file_path: str) -> List[Dict[str, Any]]:
    # Traverse semantic AST
    # Return findings in standard format
```

### Pattern-Based Rules
Add YAML patterns to `theauditor/patterns/`:
```yaml
name: insecure_api_key
severity: critical
category: security
pattern: 'api[_-]?key\s*=\s*["\'][^"\']+["\']'
description: "Hardcoded API key detected"
```

## Testing

Write tests for any new functionality:

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_your_feature.py

# Run with coverage
pytest --cov=theauditor
```

## Documentation

- Update relevant documentation when making changes
- Add docstrings to new functions and classes
- Update `README.md` if adding new commands or features
- Consider updating `howtouse.md` for user-facing changes

## Getting Help

- Check our [TeamSOP](teamsop.md) for our development workflow
- Review [CLAUDE.md](CLAUDE.md) for AI-assisted development guidelines
- Ask questions in GitHub Issues or Discussions
- Join our community chat (if available)

## License

By contributing to TheAuditor, you agree that your contributions will be licensed under the same license as the project.

---

We're excited to see your contributions! Whether you're fixing bugs, adding features, or improving documentation, every contribution helps make TheAuditor better for everyone.