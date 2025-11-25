# Boundary Analysis → Taint Analysis Integration Handoff

## Executive Summary

**What**: Boundary analysis measures distance from entry points to security controls (validation, auth, sanitization)

**Why**: Taint analysis detects data flow violations (untrusted→sink). Boundary analysis detects control placement violations (distance from entry).

**Integration Goal**: Add boundary distance to taint findings to create complete picture:
- **Taint**: "User input flows to SQL query (SQLi vulnerability)"
- **+ Boundary**: "Validation occurs at distance 3 (data spreads before validation)"
- **= Complete Finding**: "SQLi vulnerability with late validation (distance 3 creates 3 unvalidated code paths)"

## Core Concepts

### Boundary Distance

```python
# Distance 0 (PERFECT):
@app.post('/user')
def create_user(data: UserSchema):  # ← Validation AT entry (distance 0)
    db.insert('users', data)        # ← Safe! Data validated

# Distance 3 (RISKY):
@app.post('/user')
def create_user(request):           # ← Entry point
    service.create(request.json)    # ← Distance 1 (no validation yet)
        def create(data):
            process(data)            # ← Distance 2 (still no validation)
                def process(data):
                    validate(data)   # ← Distance 3 (TOO LATE! Data spread)
```

**Why Distance Matters**:
- Distance 0-1: Data validated before spreading
- Distance 3+: Data flows through N functions → N potential unvalidated code paths

### Truth Courier Compliance

**CRITICAL**: Boundary analysis reports FACTS, not recommendations.

**CORRECT** (factual):
- "Validation occurs at distance 3"
- "Data flows through 3 functions before validation control"
- "Distance 3 creates 3 potential unvalidated code paths"

**WRONG** (prescriptive):
- ❌ "Fix: Move validation to entry"
- ❌ "You should validate at distance 0"
- ❌ "Recommendation: Add schema validation"

## Architecture Overview

**UPDATED 2025-11-25**: distance.py now uses XGraphAnalyzer + graphs.db (the "Ferrari")
instead of BFS over function_call_args. This enables boundaries to see through
middleware/decorator connections via InterceptorStrategy virtual edges.

```
theauditor/boundaries/
├── __init__.py                          # Public API
├── distance.py                          # Distance calculator (uses graphs.db!)
├── boundary_analyzer.py                 # Entry → validation distance
└── TAINT_TEAM_HANDOFF.md               # ← You are here

theauditor/graph/
├── store.py                             # XGraphStore - loads from graphs.db
├── analyzer.py                          # XGraphAnalyzer - pathfinding algorithms
└── strategies/interceptors.py           # InterceptorStrategy - creates middleware edges
```

### Key Functions

**1. `calculate_distance(db_path, entry_file, entry_line, control_file, control_line) -> Optional[int]`**

Calculates call-chain distance between two points using XGraphAnalyzer on `graphs.db`.
Now sees interceptor/middleware edges! Falls back to repo_index.db if graphs.db unavailable.

```python
from theauditor.boundaries.distance import calculate_distance

# How far is validation from entry?
distance = calculate_distance(
    db_path='.pf/repo_index.db',
    entry_file='src/routes/users.js',
    entry_line=34,          # Entry point
    control_file='src/validators/user.js',
    control_line=12         # Validation control
)
# Returns: 2 (validation is 2 function calls from entry)
```

**2. `find_all_paths_to_controls(db_path, entry_file, entry_line, control_patterns, max_depth) -> List[Dict]`**

Finds all control points reachable from entry point.

```python
from theauditor.boundaries.distance import find_all_paths_to_controls

# Find all validation controls from this entry point
controls = find_all_paths_to_controls(
    db_path='.pf/repo_index.db',
    entry_file='src/routes/users.js',
    entry_line=34,
    control_patterns=['validate', 'sanitize', 'check'],
    max_depth=5
)
# Returns: [
#     {
#         'control_function': 'validateUser',
#         'control_file': 'src/validators/user.js',
#         'control_line': 12,
#         'distance': 2,
#         'path': ['create_user', 'processUser', 'validateUser']
#     }
# ]
```

**3. `measure_boundary_quality(controls) -> Dict`**

Assesses boundary quality based on control distances.

```python
from theauditor.boundaries.distance import measure_boundary_quality

quality = measure_boundary_quality(controls)
# Returns: {
#     'quality': 'acceptable',  # clear|acceptable|fuzzy|missing
#     'reason': "Single control point 'validateUser' at distance 2",
#     'facts': [
#         'Validation occurs 2 function call(s) after entry',
#         'Data flows through 2 intermediate function(s) before validation',
#         'Single validation control point detected'
#     ]
# }
```

## Database Schema

**Primary**: graphs.db (XGraphStore) - contains call graph with interceptor edges
**Fallback**: repo_index.db - used for symbol resolution and when graphs.db unavailable

Boundary analysis uses these tables:

### 1. `symbols` (Function Definitions)
```sql
CREATE TABLE symbols (
    path TEXT,           -- File path
    name TEXT,           -- Symbol name (function, class, etc.)
    type TEXT,           -- 'function', 'method', 'arrow_function'
    line INTEGER,        -- Start line
    end_line INTEGER,    -- End line
    ...
);
```

**Usage**: Find which function contains a given line number.

### 2. `function_call_args` (Call Graph)
```sql
CREATE TABLE function_call_args (
    file TEXT,                -- Where the call happens
    line INTEGER,             -- Line of the call
    caller_function TEXT,     -- Who is calling
    callee_function TEXT,     -- Who is being called
    callee_file_path TEXT,    -- Where callee is defined
    argument_expr TEXT,       -- Call argument expressions
    ...
);
```

**Usage**: Build call graph for BFS distance calculation.

### 3. `python_routes` / `js_routes` (Entry Points)
```sql
CREATE TABLE python_routes (
    file TEXT,
    line INTEGER,
    framework TEXT,
    method TEXT,          -- GET, POST, etc.
    pattern TEXT,         -- Route path (e.g., '/api/users')
    handler_function TEXT,
    has_auth BOOLEAN,
    ...
);
```

**Usage**: Identify HTTP entry points for boundary analysis.

### 4. `python_validators` (Validation Controls)
```sql
CREATE TABLE python_validators (
    file TEXT,
    line INTEGER,
    validator_type TEXT,   -- 'field', 'root', 'decorator'
    library TEXT,          -- 'pydantic', 'marshmallow'
    field_name TEXT,
    ...
);
```

**Usage**: Find validation control points (Pydantic, Marshmallow).

## Integration Points with Taint Analysis

### 1. Taint Finding Enhancement

**Current Taint Finding**:
```python
{
    'source': {
        'type': 'http_request',
        'name': 'request.args.user_id',
        'file': 'routes/users.py',
        'line': 34
    },
    'sink': {
        'type': 'sql_query',
        'name': 'cursor.execute',
        'file': 'database.py',
        'line': 67
    },
    'severity': 'CRITICAL',
    'vulnerability': 'SQL Injection'
}
```

**Enhanced with Boundary Distance**:
```python
{
    'source': {...},
    'sink': {...},
    'severity': 'CRITICAL',
    'vulnerability': 'SQL Injection',

    # NEW: Boundary context
    'boundary': {
        'entry_point': 'GET /api/user',
        'entry_file': 'routes/users.py',
        'entry_line': 34,
        'validation_controls': [
            {
                'control_function': 'validate_user_id',
                'control_file': 'validators/user.py',
                'control_line': 12,
                'distance': 3,
                'path': ['get_user', 'fetch_user_data', 'validate_user_id']
            }
        ],
        'quality': 'fuzzy',
        'facts': [
            'Validation occurs 3 function calls after entry',
            'Data flows through 3 functions before validation control',
            'Distance 3 creates 3 potential unvalidated code paths'
        ]
    }
}
```

### 2. Multi-Tenant RLS Integration

**Existing**: `multi_tenant_analyze.py` detects missing tenant filters

**Enhancement**: Add distance from authenticated `tenant_id` to query

```python
# Current finding:
{
    'rule': 'multi-tenant-direct-id-access',
    'message': 'SELECT by ID without tenant validation',
    'file': 'routes/records.py',
    'line': 45
}

# Enhanced with boundary distance:
{
    'rule': 'multi-tenant-direct-id-access',
    'message': 'SELECT by ID without tenant validation',
    'file': 'routes/records.py',
    'line': 45,

    # NEW: tenant_id boundary distance
    'tenant_boundary': {
        'tenant_id_source': 'req.user.tenantId',  # Authenticated (GOOD)
        'tenant_check_distance': 2,                # Distance from auth to check
        'tenant_check_location': 'AFTER_QUERY',    # Check happens AFTER DB access (BAD)
        'facts': [
            'Tenant validation occurs at distance 2 (after database access)',
            'Query executes before tenant check',
            'Tenant check distance 2 leaves window for cross-tenant access'
        ]
    }
}
```

### 3. Sanitization Boundary Integration

**Taint Analysis**: Detects user input → SQL sink

**Boundary Analysis**: Measures distance to parameterization/sanitization

```python
# Taint finding:
{
    'source': 'request.args.name',
    'sink': 'cursor.execute(f"SELECT * FROM users WHERE name={name}")',
    'vulnerability': 'SQL Injection'
}

# + Boundary context:
{
    'source': 'request.args.name',
    'sink': 'cursor.execute(...)',
    'vulnerability': 'SQL Injection',

    'sanitization_boundary': {
        'parameterization_distance': None,  # No parameterization found
        'sanitization_distance': None,      # No sanitization found
        'facts': [
            'No sanitization control detected in call chain',
            'User input flows directly to SQL string construction',
            'Distance to sanitization: None (missing boundary)'
        ]
    }
}
```

## Integration Steps

### Step 1: Import Boundary Functions in Taint Analysis

```python
# In theauditor/taint/analysis.py (or wherever taint findings are created)

from theauditor.boundaries.distance import (
    find_all_paths_to_controls,
    measure_boundary_quality
)

def create_taint_finding(source, sink, path, db_path):
    """Create taint finding with boundary context."""

    # Existing taint finding logic
    finding = {
        'source': source,
        'sink': sink,
        'severity': 'CRITICAL',
        'vulnerability': detect_vulnerability_type(source, sink)
    }

    # NEW: Add boundary context
    try:
        validation_controls = find_all_paths_to_controls(
            db_path=db_path,
            entry_file=source['file'],
            entry_line=source['line'],
            control_patterns=['validate', 'sanitize', 'check', 'escape'],
            max_depth=5
        )

        quality = measure_boundary_quality(validation_controls)

        finding['boundary'] = {
            'entry_point': f"{source['file']}:{source['line']}",
            'validation_controls': validation_controls,
            'quality': quality['quality'],
            'facts': quality['facts']
        }
    except Exception as e:
        # Gracefully degrade if boundary analysis fails
        finding['boundary'] = {'error': str(e)}

    return finding
```

### Step 2: Update Taint Report Format

```python
# In theauditor/taint/core.py (or report generation)

def format_taint_finding(finding):
    """Format taint finding with boundary context."""

    output = []
    output.append(f"[{finding['severity']}] {finding['vulnerability']}")
    output.append(f"  Source: {finding['source']['name']} ({finding['source']['file']}:{finding['source']['line']})")
    output.append(f"  Sink: {finding['sink']['name']} ({finding['sink']['file']}:{finding['sink']['line']})")

    # NEW: Boundary context
    if 'boundary' in finding:
        boundary = finding['boundary']
        output.append(f"  Boundary Quality: {boundary['quality']}")

        if boundary.get('validation_controls'):
            controls = boundary['validation_controls']
            for ctrl in controls:
                output.append(f"    - {ctrl['control_function']} at distance {ctrl['distance']}")
                output.append(f"      Path: {' -> '.join(ctrl['path'])}")

        for fact in boundary.get('facts', []):
            output.append(f"    Fact: {fact}")

    return '\n'.join(output)
```

### Step 3: Add Boundary Findings to Database

**Option A: Extend Existing Taint Findings Table**

```sql
-- Add boundary columns to existing taint findings table
ALTER TABLE taint_findings ADD COLUMN validation_distance INTEGER;
ALTER TABLE taint_findings ADD COLUMN boundary_quality TEXT;  -- 'clear'|'acceptable'|'fuzzy'|'missing'
ALTER TABLE taint_findings ADD COLUMN boundary_facts TEXT;    -- JSON array
```

**Option B: New Boundary Findings Table** (Recommended for separation of concerns)

```sql
CREATE TABLE boundary_findings (
    id INTEGER PRIMARY KEY,
    analysis_date TEXT NOT NULL,

    -- Entry point
    entry_type TEXT NOT NULL,        -- 'http_route'|'cli_command'|'message_handler'
    entry_point TEXT NOT NULL,       -- Route path or command name
    entry_file TEXT NOT NULL,
    entry_line INTEGER NOT NULL,

    -- Control point
    control_function TEXT,           -- NULL if missing
    control_file TEXT,
    control_line INTEGER,
    control_type TEXT,               -- 'validation'|'authorization'|'sanitization'

    -- Distance measurement
    distance INTEGER,                -- NULL if no control found
    call_path TEXT,                  -- JSON array: ['func1', 'func2', 'func3']

    -- Quality assessment
    quality TEXT NOT NULL,           -- 'clear'|'acceptable'|'fuzzy'|'missing'
    quality_reason TEXT NOT NULL,    -- Human-readable reason
    facts TEXT NOT NULL,             -- JSON array of factual observations

    -- Severity (for filtering)
    severity TEXT NOT NULL,          -- 'CRITICAL'|'HIGH'|'MEDIUM'|'LOW'

    -- Link to taint finding (if applicable)
    taint_finding_id INTEGER,        -- Foreign key to taint_findings table (NULL if standalone)

    FOREIGN KEY (taint_finding_id) REFERENCES taint_findings(id)
);

CREATE INDEX idx_boundary_findings_quality ON boundary_findings(quality);
CREATE INDEX idx_boundary_findings_severity ON boundary_findings(severity);
CREATE INDEX idx_boundary_findings_entry ON boundary_findings(entry_file, entry_line);
```

### Step 4: Pipeline Integration

**Current Pipeline** (`aud full`):
1. Index (`aud index`)
2. Taint Analysis (`aud taint-analyze`)
3. Rules (`aud detect-patterns`)
4. FCE Correlation (`aud fce`)
5. Report Generation (`aud report`)

**Enhanced Pipeline** (`aud full`):
1. Index (`aud index`)
2. Taint Analysis (`aud taint-analyze`) **← Enhanced with boundary context**
3. **Boundary Analysis** (`aud boundaries`) **← NEW standalone analysis**
4. Rules (`aud detect-patterns`)
5. FCE Correlation (`aud fce`) **← Correlates taint + boundary findings**
6. Report Generation (`aud report`) **← Includes boundary context**

## Example Integration Code

### Minimal Integration (Taint Analysis Enhancement)

```python
# In theauditor/taint/analysis.py

from theauditor.boundaries.distance import find_all_paths_to_controls, measure_boundary_quality

class TaintFlowAnalyzer:
    def __init__(self, cache, cursor=None):
        self.cache = cache
        self.cursor = cursor
        self.db_path = None  # Set this to repo_index.db path

    def analyze_interprocedural(self, sources, sinks, call_graph, max_depth=5):
        taint_paths = []

        for source in sources:
            # Existing taint analysis logic...
            paths = self._analyze_function_cfg(source, source_function, sinks, call_graph, max_depth)

            # NEW: Enhance each taint path with boundary context
            for path in paths:
                path = self._add_boundary_context(path)

            taint_paths.extend(paths)

        return taint_paths

    def _add_boundary_context(self, taint_path):
        """Add boundary distance to taint path."""

        if not self.db_path:
            return taint_path  # Skip if no db_path available

        try:
            # Find validation controls from source
            controls = find_all_paths_to_controls(
                db_path=self.db_path,
                entry_file=taint_path['source']['file'],
                entry_line=taint_path['source']['line'],
                control_patterns=['validate', 'sanitize', 'check', 'escape'],
                max_depth=5
            )

            quality = measure_boundary_quality(controls)

            taint_path['boundary'] = {
                'validation_controls': controls,
                'quality': quality['quality'],
                'facts': quality['facts']
            }

        except Exception as e:
            # Gracefully degrade - boundary analysis is enhancement, not blocker
            taint_path['boundary'] = {'error': str(e)}

        return taint_path
```

### Full Integration (Standalone Boundary Analysis + Taint Enhancement)

```python
# In theauditor/pipelines.py (aud full pipeline)

def run_full_pipeline(root_path):
    """Run complete security audit pipeline."""

    db_path = Path(root_path) / ".pf" / "repo_index.db"

    # 1. Index
    run_indexer(root_path)

    # 2. Taint Analysis (enhanced with boundary context)
    taint_findings = run_taint_analysis(db_path, boundary_aware=True)

    # 3. Standalone Boundary Analysis
    boundary_findings = run_boundary_analysis(db_path)

    # 4. Rules
    rule_findings = run_rules(db_path)

    # 5. FCE Correlation (merge taint + boundary + rules)
    correlated_findings = run_fce(
        taint_findings=taint_findings,
        boundary_findings=boundary_findings,
        rule_findings=rule_findings
    )

    # 6. Report Generation
    generate_report(correlated_findings)


def run_boundary_analysis(db_path):
    """Run standalone boundary analysis."""

    from theauditor.boundaries.boundary_analyzer import analyze_input_validation_boundaries

    # Input validation boundaries
    validation_boundaries = analyze_input_validation_boundaries(
        db_path=str(db_path),
        max_entries=100
    )

    # Store in database
    store_boundary_findings(db_path, validation_boundaries)

    return validation_boundaries


def store_boundary_findings(db_path, boundary_results):
    """Store boundary findings in database."""

    import sqlite3
    import json

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Ensure table exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS boundary_findings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_point TEXT,
            entry_file TEXT,
            entry_line INTEGER,
            control_function TEXT,
            distance INTEGER,
            quality TEXT,
            facts TEXT,
            severity TEXT
        )
    """)

    # Insert findings
    for result in boundary_results:
        for violation in result.get('violations', []):
            cursor.execute("""
                INSERT INTO boundary_findings
                (entry_point, entry_file, entry_line, quality, facts, severity)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                result['entry_point'],
                result['entry_file'],
                result['entry_line'],
                result['quality']['quality'],
                json.dumps(result['quality']['facts']),
                violation['severity']
            ))

    conn.commit()
    conn.close()
```

## Testing

Run boundary analysis on TheAuditor itself:

```bash
# Standalone boundary analysis
aud boundaries --type input-validation --max-entries 20

# With taint analysis (after integration)
aud taint-analyze --boundary-aware

# Full pipeline (after integration)
aud full
```

## Questions for Taint Team

1. **Database Schema**: Should we extend `taint_findings` table or create separate `boundary_findings` table?

2. **Performance**: Boundary BFS adds ~5-30s to pipeline. Acceptable tradeoff? Should we make it optional (`--boundary-aware` flag)?

3. **Integration Point**: Where should boundary context be added?
   - Option A: In `TaintFlowAnalyzer._analyze_function_cfg()` (deep integration)
   - Option B: Post-processing after taint paths generated (loose coupling)
   - Option C: Separate analysis + FCE correlation (current approach)

4. **Reporting**: How should boundary context appear in taint reports?
   - Inline with each taint finding?
   - Separate boundary section?
   - Both?

5. **Multi-Tenant**: Should we enhance `multi_tenant_analyze.py` with tenant_id boundary distance?

## Next Steps

1. **Taint Team Reviews This Document**
2. **Decision on Integration Approach** (deep vs loose coupling)
3. **Database Schema Finalization** (extend vs new table)
4. **Implement Integration** (taint team + me)
5. **Test on Real Codebases** (especially multi-tenant SaaS projects)
6. **Update Documentation** (taint-analyze --help, docs)

## Contact

- **Boundary Analysis Author**: Claude (this session)
- **Taint Analysis Team**: You (taint AI in other terminal)
- **Coordination**: User (santa)

Let's build complete security analysis! 🚀
