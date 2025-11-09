# Plant Frontend Coverage Report

## Executive Summary

TheAuditor has **partial frontend coverage** but **ZERO frontend → backend taint flow tracking**. While 95% of frontend files are indexed and React components/hooks are extracted, the taint analysis completely ignores frontend as a source of untrusted data.

## 1. Database Coverage

### File Coverage
- **Actual frontend files**: 112 total
  - .tsx files: 72
  - .ts files: 37
  - .jsx files: 0
  - .js files: 3
- **Files indexed in DB**: 106 (95% coverage)
- **Missing files**: 6 (mostly config files like tailwind.config.js, vite-env.d.ts)

### Component & Framework Coverage
- **React components**: 192 indexed across 55 files
- **React hooks**: 1,478 usage instances across 68 files
- **Component hook usage**: 457 tracked connections
- **Vue components**: 0 (no Vue code found)
- **API calls**: 209 detected (fetch/axios patterns)
- **Gaps found**:
  - FormData usage: 0 detected (but exists in code)
  - URL params: Only 3 instances detected (useParams, URLSearchParams)
  - DOM selectors: 489 detected but not categorized as sources

## 2. Frontend → Backend Flows

### API Call Detection
- **Frontend API calls found**: 209
  - Includes: fetchFacilities, fetchByZone, fetchPlants, api.post, etc.
  - Detected via function_call_args_jsx table
- **Backend endpoints found**: 181
  - All from backend/src/routes/*.ts files
  - Properly captured with HTTP methods and paths

### Cross-Boundary Taint Flows
- **Connected to backend**: 0
- **Cross-boundary taint flows**: NO
- **Frontend → Backend flows**: 0
- **Backend → Frontend flows**: 0
- **Root Cause**: Taint analysis only recognizes backend patterns (req.body, req.query) as sources

## 3. Framework Extraction Gaps

### Missing Frontend Patterns
- **User input sources not tracked**:
  - Form inputs (e.target.value detected in assignments but not as taint sources)
  - localStorage/sessionStorage (6 uses detected but not as sources)
  - Cookies (8 uses detected but not as sources)
  - URL parameters (minimal detection)

### Missing Frontend Sinks
- **XSS sinks not tracked**:
  - innerHTML: 0 detected (good - not used)
  - dangerouslySetInnerHTML: Not tracked
  - eval: 0 detected (good - not used)
  - document.write: Not tracked

### Vue Code
- **Vue code found**: NO (0 .vue files in project)

## 4. Taint Coverage Gaps

### Sources Missed (Frontend)
- User form inputs (event.target.value)
- File uploads (FormData)
- URL search parameters
- Browser storage (localStorage, sessionStorage)
- Cookies (document.cookie)
- PostMessage events
- WebSocket messages

### Sinks Missed (Frontend)
- API calls (fetch/axios posts with user data)
- DOM manipulation (innerHTML, insertAdjacentHTML)
- Client-side navigation (window.location)
- Browser storage writes
- PostMessage sends

### Current Taint Patterns (Backend Only)
- **Actual source patterns used**:
  - req.body
  - query
  - accountId
  - data
  - batchId
  - superAdminId
- **All patterns are Express.js backend patterns**

## 5. Integration Verdict

### Frontend Taint Sources Feeding Backend: **NO**
- Evidence: 0 flows with source_file="frontend/*"
- Root cause: Taint discovery only looks for backend patterns
- Impact: Cannot trace user input from forms to API to database

### Full Stack Provenance: **NO**
- Evidence: All 92 resolved flows are backend → backend
- Missing: Frontend → Backend API boundary crossing
- Example flow that SHOULD exist but doesn't:
  ```
  frontend/src/components/plants/PlantForm.tsx (user input)
    → frontend/src/services/api.ts (axios.post)
    → backend/src/routes/plants.routes.ts (endpoint)
    → backend/src/controllers/plants.controller.ts (req.body)
    → backend/src/services/plants.service.ts (database query)
  ```

## 6. Critical Findings

### What Works
1. **Frontend file indexing**: 95% coverage
2. **React component extraction**: Components and hooks properly identified
3. **API call detection**: Frontend API calls are found
4. **Backend endpoint mapping**: All Express routes captured

### What's Broken
1. **No frontend taint sources**: Frontend user inputs not recognized
2. **No cross-boundary flows**: API calls not connected to backend endpoints
3. **No frontend security analysis**: XSS, client-side injection not tracked
4. **Framework-specific gaps**: Form handling, event handlers not categorized

## 7. Recommendations

### Immediate Fixes Needed
1. Add frontend taint source patterns to discovery
2. Connect frontend API calls to backend endpoints via path matching
3. Add browser-specific sinks (DOM, storage, navigation)
4. Track form inputs and event handlers as sources

### Implementation Path
1. Extend `taint/discovery.py` to include frontend patterns
2. Add cross-file resolver for API boundary (match axios.post('/api/plants') to router.post('/plants'))
3. Create frontend-specific vulnerability categories (XSS, client-storage leaks)
4. Add JSX-specific taint propagation rules

## Conclusion

TheAuditor successfully indexes frontend code but **completely fails at security analysis** for it. The frontend is treated as inert display logic rather than a critical attack surface. Without frontend → backend taint tracking, TheAuditor misses the primary attack vector in modern web applications: **user input flowing from browser forms through API calls to backend databases**.

**Current State**: Frontend coverage = 95%, Frontend security analysis = 0%
**Required State**: Full stack taint propagation from browser to database