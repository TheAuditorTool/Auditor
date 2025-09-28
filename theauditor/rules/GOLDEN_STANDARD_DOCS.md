# Golden Standard Analyzer Documentation

## Overview

This document describes the Golden Standard pattern used by TheAuditor's deployment analyzers. These analyzers demonstrate the **finite patterns approach** - instead of trying to understand infinite runtime possibilities, they check against finite sets of known patterns.

## The Golden Standard Pattern

All analyzers in this directory follow the same architectural pattern:

```
1. Pattern Configuration (dataclass with frozensets)
2. Main Entry Point (StandardRuleContext -> List[StandardFinding])
3. Database-First Loading (query existing extraction)
4. Pattern Matching (simple substring checks)
5. Cross-Record Correlation (join related data)
6. Structured Data Models (dataclasses)
```

## Analyzer Implementations

### 1. nginx_analyze.py

**Purpose**: Detects Nginx security misconfigurations using finite pattern matching.

**Key Patterns**:
- **CRITICAL_HEADERS**: 7 required security headers
- **SENSITIVE_PATHS**: ~20 paths that shouldn't be exposed
- **DEPRECATED_PROTOCOLS**: 8 insecure SSL/TLS protocols
- **WEAK_CIPHERS**: 12 weak encryption ciphers

**Pattern Matching Example**:
```python
# Simple substring check - no regex
if sensitive in location_lower:  # O(1) with frozenset
    if not self._is_path_protected(location):
        report_issue()
```

**Database Query**:
```sql
SELECT file_path, block_type, block_context, directives, level
FROM nginx_configs
ORDER BY file_path, level
```

**Cross-Record Correlation**:
- Checks if rate limiting exists in different blocks for same context
- Correlates security headers across multiple configuration files
- Links SSL configurations with their server blocks

### 2. compose_analyzer.py

**Purpose**: Detects Docker Compose security misconfigurations using finite pattern matching.

**Key Patterns**:
- **SENSITIVE_ENV_PATTERNS**: 16 patterns indicating secrets
- **WEAK_PASSWORDS**: 20 common weak passwords
- **DATABASE_PORTS**: 17 database ports mapped to services
- **DANGEROUS_MOUNTS**: 8 sensitive host paths

**Pattern Matching Example**:
```python
# Check against finite set of dangerous mounts
if any(mount in volume for mount in self.patterns.DANGEROUS_MOUNTS):
    if 'docker.sock' in volume:
        report_critical_issue()
```

**Database Query**:
```sql
SELECT file_path, service_name, image, ports, volumes,
       environment, is_privileged, network_mode
FROM compose_services
```

**Cross-Record Correlation**:
- Links environment variables with their values
- Correlates port mappings with service types
- Connects volume mounts with security implications

## The Finite Patterns Insight

Both analyzers demonstrate the core principle: **security patterns are finite and enumerable**.

### Traditional Approach (Complex)
```python
# Try to understand what the configuration "means"
def analyze_config(config):
    parsed = complex_parser.parse(config)
    semantic_tree = build_semantic_tree(parsed)
    runtime_behavior = predict_runtime(semantic_tree)
    # ... hundreds of lines of complex logic
```

### Finite Patterns Approach (Simple)
```python
# Check against known patterns
def analyze_config(config):
    for bad_pattern in FINITE_BAD_PATTERNS:
        if bad_pattern in config:
            report_issue()

    for good_pattern in FINITE_GOOD_PATTERNS:
        if good_pattern not in config:
            report_missing()
```

## Key Design Principles

### 1. Database-First Architecture
- **Never re-parse files** - Use pre-extracted data from indexer
- **Query existing tables** - nginx_configs, compose_services, etc.
- **Graceful degradation** - Continue if database unavailable

### 2. Simple Pattern Matching
- **No complex regex** - Use substring checks with `in` operator
- **Frozensets for O(1) lookup** - Fast membership testing
- **Case-insensitive where needed** - `.lower()` for comparison

### 3. Structured Data Models
- **Dataclasses for clarity** - Type-safe configuration storage
- **Factory methods** - `from_db_row()` for safe parsing
- **Immutable patterns** - `@dataclass(frozen=True)` for constants

### 4. Cross-Record Correlation
- **Join related data** - Link configurations across files/blocks
- **Track state across analysis** - Build lists then correlate
- **Deduplication** - Process each file only once

## Performance Characteristics

### Time Complexity
- Pattern lookup: **O(1)** with frozensets
- Database query: **O(n)** where n = records
- Pattern matching: **O(n*m)** where m = patterns (m is small, ~20)

### Space Complexity
- Pattern storage: **~1KB** per analyzer
- Database results: **O(n)** where n = configurations
- Findings: **O(f)** where f = issues found

## Adding New Patterns

To add new security patterns:

1. **Add to frozenset**:
```python
DANGEROUS_PATTERNS = frozenset([
    'existing_pattern',
    'new_pattern_here'  # Add new pattern
])
```

2. **Check in analysis**:
```python
if pattern in config_value:
    self.findings.append(StandardFinding(...))
```

3. **No code changes needed** - Pattern matching is data-driven

## Testing Pattern Detection

To verify patterns work:

```bash
# Create test configuration
echo "server { location /.git { } }" > test.conf

# Run analyzer
aud nginx-analyze

# Check findings
cat .pf/readthis/nginx_analyze.json
```

## Future Enhancements

### 1. Pattern Database Table
Instead of hardcoded frozensets, patterns could be stored in database:

```sql
CREATE TABLE security_patterns (
    analyzer TEXT,
    pattern_type TEXT,
    pattern_value TEXT,
    severity TEXT,
    description TEXT
);
```

### 2. Framework-Aware Patterns
Patterns could be framework-specific:

```python
PATTERNS_BY_FRAMEWORK = {
    'nginx': {...},
    'apache': {...},
    'caddy': {...}
}
```

### 3. Confidence Scoring
Add confidence levels to findings:

```python
confidence = 1.0
if pattern_partially_matches:
    confidence *= 0.7
if in_test_file:
    confidence *= 0.5
```

## Conclusion

The Golden Standard analyzers prove that complex security analysis can be reduced to simple pattern matching against finite sets. This approach is:

- **Fast**: O(1) pattern lookups
- **Maintainable**: Add patterns without code changes
- **Reliable**: No complex parsing or prediction
- **Extensible**: Easy to add new patterns or analyzers

By enumerating the finite set of secure/insecure patterns, we transform an AI-hard problem into a simple database query with pattern matching.