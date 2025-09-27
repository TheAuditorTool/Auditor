# Rule Migration Standard Operating Procedure (SOP)

## Executive Summary

This SOP documents the complete process for migrating TheAuditor's 30 security rules from regex/YML patterns to database-driven detection, fixing extraction gaps, and preparing for real-world testing.

## The Three Distinct Problems (NEVER CONFUSE THESE)

### Problem 1: DATABASE GAP ✅ (Can be stored, just isn't)
**What**: Data from code that CAN go in database but extractors aren't capturing
**Examples**:
- Framework context (Express vs Fastify)
- Validation middleware chains
- Safe sinks per framework (res.json, res.jsonp)
- Authentication decorators
**Solution**: Enhance extractors to capture this data during indexing

### Problem 2: NON-CODE FILES 🔧 (Config files)
**What**: Configuration files that are NOT code
**Examples**:
- docker-compose.yml
- nginx.conf
- prisma.schema
- package.json
**Current Problem**: YML pattern files doing SEPARATE os.walks (5x slower)
**Solution**: Integrate into single indexer pass, cache to `.pf/.config_cache/`
**NOTE**: Empty tables like `compose_services` were failed attempts - configs DON'T go in code database

### Problem 3: NON-AST PATTERNS IN CODE ✅ (Partially working)
**What**: Patterns IN code files that can't be parsed as AST but CAN be stored as strings
**Working Example**: SQL in template literals - 4,723 records in `sql_queries` table
**Missing**:
- React hooks patterns
- Vue reactivity patterns
- Dynamic imports
- JWT patterns in strings
- API endpoint patterns in templates
**Solution**: Add regex patterns like SQL_QUERY_PATTERNS, extract during indexing

## Core Architecture Facts (NEVER FORGET)

1. **repo_index.db is OUR database** - Built by indexer from user's code, NOT their database
2. **Single-pass indexer** - ONE walk through files during `aud index`
3. **Rules NEVER walk files** - Only query database and caches
4. **Empty tables are NORMAL** - Not every project uses Docker/Prisma/nginx
5. **Multi-layer fallbacks are MANDATORY** - Primary table + fallback + context filtering

## The Golden Standard: SQL Rules

Location: `theauditor/rules/sql/*_analyze.py`

These show the CORRECT pattern:
- NO AST traversal (stated in comment at top)
- NO FILE I/O
- Pure database queries with fallbacks
- ~100 lines per rule (NOT 500+)
- Multi-layer detection handles empty tables

```python
# Example from sql_injection_analyze.py
cursor.execute("SELECT COUNT(*) FROM sql_queries")
if query_count == 0:
    # Fallback when primary table is empty
    findings.extend(_find_sql_injection_in_function_calls(cursor))
else:
    # Use primary table
    findings.extend(_find_string_concatenation_in_queries(cursor))
```

## Phase Breakdown

### Phase 1: Rule Migration ✅ (COMPLETED)
- 30 rules refactored from regex/YML to StandardRuleContext
- All using database queries instead of file I/O
- Status: DONE

### Phase 2: Database Gap Filling (CURRENT)
For each of the 30 rule files, methodically:

#### Step 2.1: Read and Analyze
1. Read the rule file (e.g., `theauditor/rules/auth/jwt_detect.py`)
2. Read its documentation (usually comments at top)
3. Identify what data it needs from database
4. Check if that data exists in current tables

#### Step 2.2: Categorize Missing Data
Determine which category the missing data falls into:
- **AST-extractable**: Functions, classes, symbols → Already works
- **String patterns**: Like SQL queries → Add to config.py patterns
- **Framework context**: Express vs Fastify → Add to extractor logic
- **Config files**: Never in code database → Handle separately

#### Step 2.3: Add Extraction
Based on category:

**For String Patterns** (like SQL):
1. Add to `theauditor/indexer/config.py`:
```python
JWT_PATTERNS = [
    re.compile(r'jwt\.sign\s*\([^)]+\)'),
    re.compile(r'jsonwebtoken.*secret.*["\']([^"\']+)["\']'),
    # etc.
]
```

2. Add extraction method or extend existing in `BaseExtractor`:
```python
def extract_jwt_patterns(self, content: str) -> List[Dict]:
    # Similar to extract_sql_queries()
```

3. Store in appropriate table during indexing

**For AST Data**:
1. Enhance AST parser extraction in `python.py` or `javascript.py`
2. Add to appropriate table (symbols, function_calls, etc.)

#### Step 2.4: Test Extraction
1. Run `aud index` on test project
2. Query database to verify data was captured
3. Run the specific rule to verify it uses the data

### Phase 3: Config File Integration
**Goal**: Stop YML files from doing separate os.walks

1. Integrate YML pattern matching into indexer single pass
2. Cache config data to `.pf/.config_cache/` if can't store in DB
3. Rules read from cache instead of walking files

### Phase 4: Real-World Testing (ONLY AFTER 2 & 3)
1. Run on real production codebases
2. Analyze false positive patterns
3. Add framework detection
4. Implement confidence scoring
5. Document what can't be fixed (true limitations)

## File-by-File Work Template

For each rule file:

```markdown
## Rule: [filename]
**Location**: theauditor/rules/[category]/[filename]
**Purpose**: [What it detects]

### Current Implementation
- [ ] Uses database queries (not AST traversal)
- [ ] Has multi-layer fallbacks
- [ ] Under 200 lines

### Data Requirements
**Primary Table**: [table_name]
**Fallback Table**: [table_name]
**Missing Data**:
1. [specific data needed]
2. [specific data needed]

### Extraction Needed
- [ ] AST extraction: [what to extract]
- [ ] String patterns: [patterns to add]
- [ ] Framework context: [context needed]

### Testing
- [ ] Data extracts correctly
- [ ] Rule queries it properly
- [ ] False positive rate acceptable
```

## Common Patterns to Add

### JWT/Auth Patterns
```python
JWT_PATTERNS = [
    r'jwt\.sign\s*\(',
    r'jsonwebtoken',
    r'SECRET|SECRET_KEY|JWT_SECRET',
    r'Bearer\s+[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+'
]
```

### React Patterns
```python
REACT_HOOK_PATTERNS = [
    r'useState\s*\(',
    r'useEffect\s*\(',
    r'useMemo\s*\(',
    r'dangerouslySetInnerHTML'
]
```

### API Endpoint Patterns
```python
API_PATH_PATTERNS = [
    r'/api/[^"\'`\s]+',
    r'endpoint:\s*["\']([^"\']+)["\']',
    r'baseURL.*["\']([^"\']+)["\']'
]
```

## What NOT to Do

1. **DON'T** make rules walk files - they query database only
2. **DON'T** try to store config files in code database
3. **DON'T** add 500+ line AST traversal - follow SQL pattern
4. **DON'T** skip multi-layer fallbacks - tables WILL be empty
5. **DON'T** test on production codebases until extraction is fixed
6. **DON'T** try to evaluate runtime behavior - we only do static analysis

## Success Criteria

### Phase 2 Success
- [ ] All 30 rules have data they need
- [ ] Extraction happens in single indexer pass
- [ ] Rules follow SQL pattern (<200 lines, multi-layer)
- [ ] Database tables populated appropriately

### Phase 3 Success
- [ ] No separate os.walks by YML files
- [ ] Config data cached or handled efficiently
- [ ] Performance improved (not 5x slower)

### Phase 4 Success
- [ ] False positive rate <20% (from current 97-100%)
- [ ] Framework detection working
- [ ] Confidence scoring implemented
- [ ] Clear documentation of unfixable issues

## Key Insights (FROM MIGRATION_STATUS_CORRECTED.md)

"We're not dumb, but we're not psychic."

**What We CAN Do**:
- Extract patterns from code
- Store them in database
- Query for dangerous patterns
- Apply context filtering

**What We CANNOT Do**:
- Evaluate runtime behavior
- Understand framework magic
- Track complex transformations
- Predict developer intent

## The Work Ahead

1. **30 rule files** to review and fix
2. **~5-10 extraction patterns** to add
3. **Single indexer pass** to maintain
4. **Real-world testing** after foundation fixed

Estimated: 1-2 days of methodical work if done file-by-file without getting confused about the architecture.

## Remember

The infrastructure WORKS. SQL proves it with 4,723 extracted queries. We just need to:
1. Add missing extraction patterns
2. Ensure rules use database properly
3. Test on real codebases

This is completion work, not architecture work. The architecture is sound.