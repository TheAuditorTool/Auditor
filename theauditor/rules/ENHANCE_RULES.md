# Rules Enhancement Backlog

Consolidated list of detection gaps and enhancement opportunities identified during the fidelity migration.

**Process:** Review after all migrations complete. Prioritize by impact. Implement or reject.

---

## frameworks/nextjs_analyze.py

### 1. Server Actions Security (Next.js 14+)

**What:** Detect security issues in Next.js Server Actions (`"use server"` directive)

**Why:** Server Actions run on the server but are invoked from client. Common vulnerabilities:
- Missing authentication checks in action functions
- Exposed internal APIs through actions
- CSRF-like attacks on action endpoints
- Sensitive data in action return values

**How:**
- Query symbols for functions with `"use server"` in same file
- Check for auth patterns before database/API calls
- Flag actions that return sensitive data patterns

**CWE:** CWE-862 (Missing Authorization), CWE-200 (Information Exposure)

---

### 2. Middleware Security

**What:** Analyze `middleware.ts/js` for security issues

**Why:** Middleware runs on every request. Misconfigurations expose entire app:
- Missing path matching (catches too much/little)
- Auth bypass via path manipulation
- Exposed headers in responses
- Missing rate limiting at edge

**How:**
- Find `middleware.ts` or `middleware.js` in project root or `src/`
- Check for `matcher` config completeness
- Verify auth checks cover protected routes

**CWE:** CWE-863 (Incorrect Authorization), CWE-770 (Resource Exhaustion)

---

### 3. Server/Client Component Boundary

**What:** Detect sensitive data crossing server/client boundary

**Why:** Server Components can pass props to Client Components. Sensitive data in props gets serialized to client:
- Database records with internal fields
- User objects with hashed passwords
- API keys passed as props

**How:**
- Track data flow from Server Component queries to Client Component props
- Flag props containing sensitive patterns passed to `"use client"` components

**CWE:** CWE-200 (Information Exposure)

---

### 4. Revalidation Security

**What:** Check `revalidatePath`/`revalidateTag` for cache poisoning

**Why:** Improper revalidation can:
- Allow attackers to poison cached pages
- Cause denial of service via excessive revalidation
- Expose stale sensitive data

**How:**
- Find revalidation calls with user-controlled paths
- Check for rate limiting on revalidation triggers

**CWE:** CWE-525 (Information Exposure Through Browser Caching)

---

## frameworks/react_analyze.py

### 5. React Server Components Security

**What:** Detect RSC-specific vulnerabilities in React 18+ apps

**Why:** RSCs introduce new attack surface:
- Async components with unhandled rejections exposing errors
- Server-only code accidentally bundled to client
- Streaming responses with sensitive data

**How:**
- Identify async Server Components
- Check for `server-only` package usage
- Flag sensitive data in streamed responses

**CWE:** CWE-209 (Error Message Information Leak), CWE-200

---

### 6. Hydration Mismatch Security

**What:** Detect hydration mismatches that expose server data

**Why:** When server/client render differently, React logs detailed errors that may contain:
- Server-side state
- User data
- Internal structure

**How:**
- Find conditional rendering based on `typeof window`
- Check for `suppressHydrationWarning` with sensitive content
- Flag dynamic content without proper SSR handling

**CWE:** CWE-209 (Error Message Information Leak)

---

### 7. Props Drilling of Sensitive Data

**What:** Track sensitive data passed through multiple component layers

**Why:** Deep props drilling of tokens/credentials:
- Makes audit difficult
- Increases exposure surface
- Often ends up in client bundles

**How:**
- Track props with sensitive names through component hierarchy
- Flag chains longer than 3 levels with sensitive data

**CWE:** CWE-200 (Information Exposure)

---

### 8. useRef DOM Abuse

**What:** Detect security-relevant DOM manipulation via useRef

**Why:** useRef bypasses React's virtual DOM, enabling:
- Direct innerHTML manipulation
- Event handler injection
- Script execution via DOM

**How:**
- Track useRef assignments to DOM elements
- Check for `.innerHTML`, `.outerHTML` on ref.current
- Flag direct event handler assignment

**CWE:** CWE-79 (XSS)

---

### 9. Dynamic import() Security

**What:** Check dynamic imports for user-controlled paths

**Why:** Dynamic imports with user input enable:
- Arbitrary module loading
- Code injection
- Prototype pollution via module loading

**How:**
- Find `import()` calls
- Check if argument contains user input sources
- Verify allowlist pattern for dynamic paths

**CWE:** CWE-94 (Code Injection)

---

## frameworks/vue_analyze.py

### 10. Vue 3 Composition API Security

**What:** Analyze Composition API patterns for security issues

**Why:** Composition API introduces new patterns not covered by Options API checks:
- `ref()` and `reactive()` with sensitive data
- `provide/inject` for sensitive state
- Composables exposing internals

**How:**
- Track `ref()`, `reactive()` containing sensitive patterns
- Check `provide()` calls for sensitive data exposure
- Analyze composable return values

**CWE:** CWE-200 (Information Exposure)

---

### 11. Pinia/Vuex State Exposure

**What:** Detect sensitive data in global state stores

**Why:** Global state is:
- Accessible from any component
- Often persisted to localStorage
- Visible in Vue DevTools
- Serialized during SSR

**How:**
- Find store definitions (Pinia `defineStore`, Vuex modules)
- Check state for sensitive patterns
- Verify persistence plugins don't store secrets

**CWE:** CWE-922 (Insecure Storage), CWE-200

---

### 12. Vue Router Navigation Guards Bypass

**What:** Detect bypassable navigation guards

**Why:** Client-side guards can be bypassed:
- Direct URL access
- Browser back button
- Missing server-side validation
- Race conditions in async guards

**How:**
- Find `beforeEnter`, `beforeEach` guards
- Check for corresponding server-side auth
- Flag guards with async operations without proper await

**CWE:** CWE-862 (Missing Authorization)

---

### 13. Nuxt SSR Vulnerabilities

**What:** Nuxt-specific SSR security checks

**Why:** Nuxt SSR has unique attack surface:
- `asyncData`/`fetch` with user input
- Server middleware security
- `useAsyncData` error exposure
- Nitro server routes

**How:**
- Check `asyncData` for injection patterns
- Analyze server middleware auth
- Find exposed server routes without protection

**CWE:** CWE-79 (XSS), CWE-862 (Missing Authorization)

---

### 14. Custom Directive Security

**What:** Analyze custom Vue directives for DOM manipulation issues

**Why:** Custom directives directly manipulate DOM:
- `bind`/`mounted` hooks can inject HTML
- User input in directive values flows to DOM
- No automatic escaping

**How:**
- Find `directive()` registrations
- Check `el.innerHTML` assignments in hooks
- Track user input to directive binding values

**CWE:** CWE-79 (XSS)

---

## Priority Recommendation

| Priority | Enhancement | Impact | Complexity |
|----------|-------------|--------|------------|
| HIGH | Server Actions Security | Critical - new attack surface | Medium |
| HIGH | RSC Security | Critical - new React paradigm | Medium |
| HIGH | Navigation Guards Bypass | Auth bypass | Low |
| MEDIUM | Middleware Security | Full app exposure | Low |
| MEDIUM | State Store Exposure | Data leak | Low |
| MEDIUM | Dynamic import() | Code injection | Low |
| LOW | Hydration Mismatch | Info leak | Medium |
| LOW | Props Drilling | Audit quality | High |
| LOW | Custom Directives | Edge case | Low |

---

*Generated during fidelity migration. Review and prioritize after migration complete.*
