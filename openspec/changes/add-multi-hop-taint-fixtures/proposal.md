# Proposal: Multi-Hop Taint Analysis Validation Fixtures

## Why

TheAuditor claims deep interprocedural dataflow analysis (marketing: "59 hops, 19 cross-file transitions, 8 files traversed") but verification against real codebases (plant, plantflow, TheAuditor itself) shows maximum actual depth of **3 hops** with 2-3 cross-file transitions. This gap exists because:

1. **Real-world codebases have flat architecture**: Most apps follow `request -> service -> ORM` (2-3 hops)
2. **Depth limits were conservative**: Original limits were 5-10 (now raised: query=10, IFDS=15, trace=25)
3. **No purpose-built test infrastructure**: Cannot distinguish "tool limitation" from "codebase limitation"

Without intentionally deep test projects, we cannot:
- Verify the taint engine actually tracks 10+ hop chains
- Validate cross-file parameter binding works across 5+ files
- Confirm sanitizer detection interrupts chains correctly
- Benchmark performance on deep chains
- Make honest marketing claims

## What Changes

**New test projects (outside TheAuditor codebase):**

1. **deepflow-python/** - FastAPI + SQLAlchemy + PostgreSQL
   - 16-layer architecture with intentional vulnerability chains
   - SQLi, Command Injection, Path Traversal chains (10-16 hops each)
   - Sanitized paths that MUST be detected as safe
   - Actually runs (not test fixtures)

2. **deepflow-typescript/** - Express + Sequelize + React frontend
   - 18-20 layer architecture with deeper chains
   - SQLi, XSS, NoSQL Injection, Prototype Pollution chains
   - Frontend-to-backend traces (React -> Express -> DB)
   - Actually runs (not test fixtures)

**New capability spec:**
- `taint-validation` spec documenting fixture requirements
- Success criteria for each vulnerability type
- Expected output format from `aud full`

## Impact

- **Affected specs**: None (new capability)
- **Affected code**: None (external test projects)
- **Risk level**: LOW - these are isolated test projects, not TheAuditor modifications
- **Breaking changes**: None

## Success Criteria

After `aud full --offline` on each project:

| Metric | Python Target | TypeScript Target |
|--------|--------------|-------------------|
| Max chain depth | 16+ hops | 20+ hops |
| Cross-file transitions | 8+ files/chain | 10+ files/chain |
| Vulnerability types | 5 distinct | 6 distinct |
| Sanitized paths detected | 3+ | 3+ |
| Frontend-to-backend traces | N/A | 5+ |

## Verification Commands

```bash
# After indexing deepflow-python
cd deepflow-python && aud full --offline
python -c "
import json
with open('.pf/raw/taint_analysis.json') as f:
    data = json.load(f)
paths = data.get('paths', [])
max_depth = max(p.get('path_length', 0) for p in paths) if paths else 0
print(f'Max depth: {max_depth}')
depths = {}
for p in paths:
    d = p.get('path_length', 0)
    depths[d] = depths.get(d, 0) + 1
print(f'Distribution: {dict(sorted(depths.items()))}')
# Cross-file count per chain
for p in paths[:5]:
    files = set(step.get('file', step.get('from_file', '')) for step in p.get('path', []))
    print(f'  Chain {p.get(\"vulnerability_type\", \"?\")}: {len(files)} files, {p.get(\"path_length\", 0)} hops')
"

# After indexing deepflow-typescript
cd deepflow-typescript && aud full --offline
# Same verification script
```

## Out of Scope

- Modifying TheAuditor's taint engine (limits already raised: query.py max=10, ifds_analyzer.py max=15, core.py max=25)
- Adding new vulnerability pattern detection
- Performance optimization
- UI/reporting changes
