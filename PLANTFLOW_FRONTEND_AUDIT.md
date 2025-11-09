# PlantFlow Frontend Coverage Audit Report

## Executive Summary

TheAuditor's coverage of the PlantFlow frontend is **GOOD** but has critical gaps in cross-boundary taint flow tracking. While React component extraction and API call detection are robust, the system fails to track taint flows from frontend user inputs to backend sinks.

## 1. Database Coverage Audit

### React Components ✅ GOOD
- **62 unique components** detected (126 instances)
- All components have JSX extraction
- Coverage includes:
  - App.tsx main component
  - Dashboard components (CategoryFormModal, ProductFormModal, etc.)
  - Common components (LanguageToggle)
  - All major UI components tracked

### React Hooks ✅ GOOD
- **826 hook calls** tracked
- **14 unique hook types** detected:
  - useState: 370 calls
  - useQuery: 116 calls
  - useMutation: 86 calls
  - useTranslation: 68 calls
  - Custom hooks (useAuthStore, etc.)
- **421 component-hook relationships** mapped
- **52 hook dependencies** tracked

### API Calls ✅ EXCELLENT
- **193 API calls** detected across 34 files
- Methods tracked:
  - api.get: 87 calls
  - api.post: 59 calls
  - api.put: 42 calls
  - api.delete: 5 calls
  - axios.post: 3 calls
- Endpoints properly extracted with parameters

### JSX Extraction ✅ EXCELLENT
- **Dual-pass extraction working:**
  - symbols_jsx: 6,640 symbols
  - function_call_args_jsx: 3,593 calls
  - assignments_jsx: 1,336 assignments
  - cfg_blocks_jsx: 4,299 blocks
- Both TSX and JSX files properly parsed

### State Management ✅ PARTIAL
- State updates tracked via hooks
- No Redux/MobX/Zustand specific extraction
- Custom store usage (useAuthStore) detected

## 2. Frontend → Backend Flow Verification

### API Call Mapping ⚠️ PARTIAL
- Frontend API calls detected: ✅
- Backend endpoints detected: ✅
- Cross-reference mapping: ❌ MISSING
- Example calls tracked:
  ```
  api.get('/customers?is_b2b=true')
  api.post('/orders', orderData)
  api.delete(`/product-variants/${variantId}`)
  ```

### Cross-Boundary Taint Flows ❌ CRITICAL GAP
- **0 frontend → backend taint flows detected**
- Frontend has 169 user input sources (e.target.value)
- Frontend has 193 API call sinks
- Backend has 64 taint flows (all backend-only)
- **The connection is NOT being made**

## 3. Framework Extraction Verification

### Detected Frameworks ✅
- React v19.1.1
- Vite v7.1.7
- Zod v4.1.11 (validation)

### Missing Framework Support ⚠️
- No Vue components (correct - not used)
- No Angular components (correct - not used)
- React Query/TanStack Query hooks detected but not framework-labeled
- i18n (useTranslation) detected but not framework-labeled

## 4. Taint Source/Sink Coverage

### Sources ✅ GOOD
- **169 user input patterns** (e.target.value)
- Form submissions tracked
- Event handlers detected (onChange, onSubmit, onClick)

### Sinks ✅ GOOD
- **193 API calls** that send data to backend
- No dangerous sinks (innerHTML, eval) - good security
- External API calls tracked

### Flow Analysis ❌ MISSING
- No flows connect frontend sources to backend sinks
- Middleware chain propagation not working for frontend
- Express middleware chains exist but don't connect to frontend

## 5. Cross-File Flow Analysis

### Current State
- **64 taint flows** total (all backend-only)
- **Maximum 4 hops** detected
- **0 cross-boundary flows**
- All flows marked as VULNERABLE (no SANITIZED)

### Comparison with Plant Project

| Metric | PlantFlow | Plant | Analysis |
|--------|-----------|-------|----------|
| React Components | 62 | 119 | PlantFlow is smaller |
| React Hooks | 826 | 1,478 | PlantFlow uses fewer hooks |
| API Calls | 193 | 167 | PlantFlow has MORE API calls |
| Total Taint Flows | 64 | 49 | More flows but... |
| Max Hops (taint_flows) | 4 | 3 | PlantFlow has longer paths |
| Max Hops (resolved) | 4 | 5 | Plant has 5-hop SANITIZED flows |
| Frontend → Backend Flows | 0 | 0 | Both miss cross-boundary |

## Key Findings

### ✅ Strengths
1. **Excellent React extraction** - components, hooks, JSX all working
2. **Strong API call detection** - 193 calls properly tracked
3. **Good user input tracking** - 169 input sources identified
4. **No security anti-patterns** - no eval, innerHTML detected
5. **Better than Plant** in API call detection (193 vs 167)

### ❌ Critical Gaps
1. **No cross-boundary taint flows** - frontend sources don't connect to backend
2. **Missing sanitizer detection** - all flows marked VULNERABLE
3. **No middleware chain propagation** from frontend to backend
4. **API endpoint cross-referencing** not implemented
5. **5-hop flow detection** missing (Plant has it in resolved_flow_audit)

### ⚠️ Architectural Differences
1. PlantFlow has fewer components but more API calls (different architecture)
2. Plant project achieved 5-hop flows through middleware chain analysis
3. PlantFlow's validation (Zod) not being recognized as sanitizer
4. Express middleware chains exist but don't propagate from frontend

## Recommendations

1. **Fix Cross-Boundary Taint Tracking**
   - Connect frontend API calls to backend route handlers
   - Propagate taint from fetch/axios to Express req.body

2. **Implement Sanitizer Detection**
   - Recognize Zod validation as sanitizer
   - Mark flows through validation as SANITIZED

3. **Add API Endpoint Correlation**
   - Match frontend API paths to backend route definitions
   - Create virtual edges in taint graph

4. **Enhance Middleware Chain Analysis**
   - Track data flow through Express middleware
   - Connect frontend requests to middleware chains

## Conclusion

TheAuditor successfully extracts frontend metadata but **fails to connect frontend and backend for security analysis**. The 4-hop vs 5-hop difference is due to missing middleware chain propagation. The system needs cross-boundary taint flow implementation to be effective for full-stack security auditing.