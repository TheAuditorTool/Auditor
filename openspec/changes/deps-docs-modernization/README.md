# Deps & Docs Modernization OpenSpec

**Status**: PROPOSED - Ready for Implementation
**Priority**: CRITICAL - Production Safety Issues
**Timeline**: 4 Weeks (Week 1 is Emergency Fix)

## Quick Summary

This OpenSpec addresses **THREE CRITICAL PRODUCTION BUGS**:

1. **Docker Downgrades**: `aud deps --upgrade-all` can downgrade Postgres 17→15 (DATA LOSS RISK)
2. **AI Hallucinations**: Docs system only fetches README, causing AI to use deprecated APIs
3. **Performance**: Python deps parsed from disk every time (2-5 second penalty)

## The Problem (Verified)

```bash
# Current Behavior (BROKEN)
cd C:/Users/santa/Desktop/DEIC
aud deps --upgrade-all

postgres: 17-alpine3.21 → 15.15-trixie        # DOWNGRADE!
python: 3.12-alpine → 3.15.0a1-windowsservercore  # ALPHA!
redis: 7-alpine → 8.4-rc1-bookworm            # RC!
```

**Root Cause**: String sort on Docker tags (`"8" > "1" alphabetically`)

## The Solution

### Week 1: EMERGENCY FIX (Stop Production Disasters)
- Semantic version parsing (17 > 15, not "8" > "1")
- Stability filtering (no alpha/beta/rc unless flagged)
- Base image preservation (alpine stays alpine)

### Week 2: Database Parity
- Store Python deps in database (like npm)
- 2-5 second speedup on `aud deps`

### Week 3: Documentation Crawling
- Replace regex with BeautifulSoup
- Crawl actual docs, not just README
- Version-specific content

### Week 4: AI Extraction
- Generate prompts for semantic extraction
- Extract concrete code patterns
- Detect breaking changes

## Files Structure

```
deps-docs-modernization/
├── proposal.md          # Full technical proposal
├── verification.md      # Hypothesis testing (all bugs confirmed)
├── tasks.md            # 259 atomic implementation tasks
├── design.md           # Technical architecture
├── specs/
│   ├── dependency-management/
│   │   └── spec.md     # Docker/PyPI requirements
│   └── documentation-system/
│       └── spec.md     # Docs/AI requirements
└── README.md           # This file
```

## Success Metrics

**Week 1 (Production Safety)**:
- ✅ Zero downgrades
- ✅ Zero alpha/beta/rc (unless flagged)
- ✅ Base images preserved

**Weeks 2-4 (Enhancement)**:
- ✅ Python deps in database
- ✅ 5+ doc pages per package
- ✅ Version-specific syntax
- ✅ Sub-1 second deps command

## Implementation Priority

**WEEK 1 IS CRITICAL** - Production safety fixes MUST ship first.

The remaining weeks can be done incrementally, but Week 1 prevents:
- Database corruption from downgrades
- Production crashes from alpha builds
- Container bloat from base switches

## Validation

```bash
# Validate OpenSpec structure
openspec validate deps-docs-modernization

# View detailed proposal
openspec show deps-docs-modernization

# Check task breakdown (259 tasks)
openspec list
```

## Next Steps

1. **Architect Review** - Approve Week 1 emergency fixes
2. **Lead Auditor Review** - Verify hypothesis testing
3. **Begin Week 1** - Stop production disasters
4. **Continue Weeks 2-4** - Enhance functionality

## Key Innovation

**ZERO FALLBACK POLICY** - No fallback logic allowed. If something's wrong, fix the root cause, don't paper over it.

This follows CLAUDE.md principles:
- Hard failures expose bugs
- Database-first, file parsing as last resort
- Semantic parsing, not string manipulation

## Contact

- **Author**: Lead Coder (Opus AI via Architect)
- **Date**: 2025-01-16
- **Change ID**: deps-docs-modernization

---

**Ready for implementation. Week 1 fixes are production-critical.**