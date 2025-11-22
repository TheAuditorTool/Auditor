# Node React App Fixture

React SPA fixture for testing React hooks with tainted dependencies, component extraction, and hook anti-patterns.

## Purpose

Simulates a production React application with:
- Comprehensive React hook usage (useState, useEffect, useCallback, useMemo, useContext)
- Custom hooks (useAuth)
- Tainted dependencies in dependency arrays
- Taint flows from props → useEffect → API calls
- localStorage as taint source
- Hook anti-patterns (missing useCallback)
- Security vulnerabilities (tainted userId, localStorage token manipulation)

## Framework Patterns Included

### 1. UserProfile Component (171 lines)

**Comprehensive hook composition**:

```jsx
function UserProfile({ userId, showDetails }) {
  // 4 useState hooks
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [orders, setOrders] = useState([]);

  // 2 useEffect hooks with tainted dependencies
  useEffect(() => {
    // TAINT FLOW: userId (prop) → API call
    axios.get(`/api/users/${userId}`);
  }, [userId]); // ← TAINTED DEPENDENCY

  useEffect(() => {
    axios.get(`/api/users/${userId}/orders`);
  }, [userId, showDetails]); // ← MULTIPLE tainted dependencies

  // useCallback with tainted dependency
  const handleUpdate = useCallback(async (updates) => {
    await axios.put(`/api/users/${userId}`, updates);
  }, [userId]); // ← TAINTED DEPENDENCY

  // 2 useMemo hooks
  const fullName = useMemo(() => { ... }, [user]);
  const orderStats = useMemo(() => { ... }, [orders]);
}
```

**Tests**:
- react_component_hooks: 9 hook instances extracted
- react_hook_dependencies: userId, showDetails, user, orders in dependency arrays
- Taint flows: userId → 3 different API endpoints
- useMemo with computed values from tainted data

### 2. ProductList Component - ANTI-PATTERN (95 lines)

**Hook anti-pattern** (missing useCallback):

```jsx
function ProductList({ category, searchTerm }) {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(false);

  // ANTI-PATTERN: fetchProducts recreated every render
  // Should use: useCallback(async () => { ... }, [category, searchTerm])
  const fetchProducts = async () => {
    const params = new URLSearchParams();
    if (category) params.append('category', category);
    if (searchTerm) params.append('search', searchTerm);
    await axios.get(`/api/products?${params.toString()}`);
  };

  useEffect(() => {
    fetchProducts();
  }, [category, searchTerm]); // fetchProducts not in deps (would cause issues)
}
```

**Tests**:
- Hook anti-pattern detection: useState + useEffect but NOT useCallback
- Query: Find components with this pattern
- Expected: ProductList should be detected

### 3. Dashboard Component (102 lines)

**Complex hook composition** with custom hook:

```jsx
function Dashboard({ filter }) {
  const { user } = useAuth(); // Custom hook
  const [stats, setStats] = useState(null);
  const [notifications, setNotifications] = useState([]);

  // Tainted by user.id (from localStorage token)
  useEffect(() => {
    axios.get(`/api/users/${user.id}/stats`);
  }, [user]);

  // Multiple tainted dependencies
  const refreshNotifications = useCallback(async () => {
    const params = filter ? `?filter=${filter}` : '';
    await axios.get(`/api/users/${user.id}/notifications${params}`);
  }, [user, filter]); // ← TAINTED: user (from localStorage), filter (from prop)

  useEffect(() => {
    refreshNotifications();
  }, [refreshNotifications]);

  const unreadCount = useMemo(() => {
    return notifications.filter(n => !n.read).length;
  }, [notifications]);
}
```

**Tests**:
- useContext extraction (via useAuth custom hook)
- Taint propagation from localStorage → user.id → API calls
- useCallback with multiple tainted dependencies

### 4. useAuth Custom Hook (104 lines)

**Custom hook pattern**:

```jsx
function useAuth() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // TAINT SOURCE: localStorage (user-controlled)
  useEffect(() => {
    const token = localStorage.getItem('authToken'); // ← TAINT SOURCE

    if (token) {
      // TAINT SINK: Set Authorization header
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      axios.get('/api/auth/me');
    }
  }, []); // Empty deps = run once

  const login = useCallback(async (email, password) => {
    const response = await axios.post('/api/auth/login', { email, password });
    const { token, user } = response.data;

    // TAINT SINK: Store in localStorage
    localStorage.setItem('authToken', token);
    axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  }, []);

  const logout = useCallback(async () => {
    localStorage.removeItem('authToken');
    delete axios.defaults.headers.common['Authorization'];
  }, [user]);

  return { user, login, logout, isAuthenticated: !!user };
}
```

**Tests**:
- Custom hook naming (starts with 'use')
- Hook composition within custom hook
- localStorage as taint source
- Taint flow: localStorage → axios headers

## Populated Tables

| Table | Row Count (est) | Purpose |
|---|---|---|
| `react_components` | 3 | UserProfile, ProductList, Dashboard |
| `react_component_hooks` | 20+ | Which hooks each component uses |
| `react_hook_dependencies` | 15+ | Dependency arrays (userId, user, filter, etc.) |
| `symbols` | 10+ | Components, functions, custom hooks |
| `function_calls` | 15+ | axios.get, axios.post, localStorage calls |

## Sample Verification Queries

### Find all React hooks by component

```sql
SELECT
  component_name,
  hook_name,
  file,
  line
FROM react_component_hooks
WHERE file LIKE '%node-react-app%'
ORDER BY component_name, line;
```

**Expected**: 20+ hook instances across 3 components + 1 custom hook

### Find hooks with tainted userId dependency

```sql
SELECT
  rhd.hook_component,
  rhd.hook_name,
  rhd.dependency_name,
  rhd.hook_file,
  rhd.hook_line
FROM react_hook_dependencies rhd
WHERE rhd.hook_file LIKE '%node-react-app%'
  AND rhd.dependency_name = 'userId'
ORDER BY rhd.hook_file, rhd.hook_line;
```

**Expected**: 4 hooks with userId dependency (UserProfile: 3x useEffect + 1x useCallback)

### Find hooks with multiple tainted dependencies

```sql
SELECT
  hook_component,
  hook_name,
  hook_file,
  hook_line,
  GROUP_CONCAT(dependency_name, ', ') AS all_dependencies
FROM react_hook_dependencies
WHERE hook_file LIKE '%node-react-app%'
GROUP BY hook_file, hook_line, hook_component, hook_name
HAVING COUNT(dependency_name) > 1;
```

**Expected**: 3+ hooks (UserProfile useEffect with [userId, showDetails], Dashboard useCallback with [user, filter])

### Detect hook anti-pattern

```sql
SELECT
  rc.name AS component_name,
  GROUP_CONCAT(DISTINCT rch.hook_name) AS hooks_used
FROM symbols rc
JOIN react_component_hooks rch
  ON rc.path = rch.file
WHERE rc.path LIKE '%node-react-app%'
  AND rc.type IN ('function', 'component')
GROUP BY rc.name
HAVING
  hooks_used LIKE '%useState%'
  AND hooks_used LIKE '%useEffect%'
  AND hooks_used NOT LIKE '%useCallback%';
```

**Expected**: 1 component (ProductList - anti-pattern)

### Track taint from localStorage

```sql
SELECT
  function_name,
  callee_function,
  file,
  line
FROM function_calls
WHERE file LIKE '%useAuth%'
  AND callee_function LIKE '%localStorage%'
ORDER BY line;
```

**Expected**: 3 calls (getItem, setItem, removeItem)

## Testing Use Cases

1. **React Hook Extraction**: Verify all hook types are extracted (useState, useEffect, useCallback, useMemo, useContext)
2. **Tainted Dependencies**: Test hooks depending on props from external sources (userId, filter, searchTerm)
3. **Custom Hooks**: Verify custom hook extraction and composition
4. **Hook Anti-Patterns**: Test detection of useState + useEffect without useCallback
5. **Taint Flow Analysis**: Track userId (prop) → useEffect → API call
6. **localStorage Security**: Test localStorage as taint source
7. **Multi-Source Taint**: Test hooks with multiple tainted dependencies

## How to Use

### 1. Index from TheAuditor Root

```bash
cd C:/Users/santa/Desktop/TheAuditor
aud index
```

### 2. Query Extracted Data

```bash
# Find all React components
aud context query --table react_components --filter "file LIKE '%node-react-app%'"

# Find hooks with tainted dependencies
aud context query --table react_hook_dependencies --filter "dependency_name = 'userId'"
```

### 3. Run Anti-Pattern Detection

```bash
# Detect components with hook anti-patterns
aud detect-patterns --rule react-hook-anti-pattern --file tests/fixtures/node-react-app/
```

## Files Structure

```
node-react-app/
├── package.json               # Dependencies
├── components/
│   ├── UserProfile.jsx        # Comprehensive hooks (171 lines)
│   ├── ProductList.jsx        # Anti-pattern example (95 lines)
│   └── Dashboard.jsx          # Complex composition (102 lines)
├── hooks/
│   └── useAuth.js             # Custom hook (104 lines)
├── spec.yaml                  # 18 verification rules (340 lines)
└── README.md                  # This file

Total: 499 lines of React code
```

## Security Patterns

### 1. Tainted userId in API Calls (MEDIUM)

**Location**: `components/UserProfile.jsx`

**Vulnerable Pattern**:
```jsx
function UserProfile({ userId }) {
  useEffect(() => {
    // userId from props (potentially from URL) used directly
    axios.get(`/api/users/${userId}`);
  }, [userId]);
}
```

**Attack Vector**:
```jsx
// URL: /profile?userId=999
<UserProfile userId={urlParams.get('userId')} />
// Attacker can access any user's data by changing URL parameter
```

**Impact**: Horizontal privilege escalation (access other users' data)

### 2. localStorage Token Manipulation (MEDIUM)

**Location**: `hooks/useAuth.js`

**Vulnerable Pattern**:
```jsx
useEffect(() => {
  const token = localStorage.getItem('authToken'); // User-controlled storage
  axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
}, []);
```

**Attack Vector**:
```javascript
// If attacker has XSS:
localStorage.setItem('authToken', 'malicious-token');
```

**Impact**: Token injection, session hijacking

### 3. Hook Anti-Pattern (LOW)

**Location**: `components/ProductList.jsx`

**Pattern**:
```jsx
// ANTI-PATTERN: fetchProducts recreated every render
const fetchProducts = async () => { ... };

useEffect(() => {
  fetchProducts();
}, [category, searchTerm]); // Can't add fetchProducts to deps
```

**Impact**: Performance issues, potential infinite loops

**Fix**:
```jsx
const fetchProducts = useCallback(async () => { ... }, [category, searchTerm]);

useEffect(() => {
  fetchProducts();
}, [fetchProducts]); // Now safe to add
```

## Advanced Capabilities Tested

From test_enhancements.md, this fixture tests **2 of 7** advanced capabilities:

1. ❌ **API Security Coverage** - N/A (frontend, no server routes)
2. ❌ **SQL Query Surface Area** - N/A (frontend, no SQL)
3. ❌ **Multi-Source Taint Origin** - Partially (multiple props, but not complex assignments)
4. ✅ **React Hook Dependencies** - react_hook_dependencies with tainted props
5. ❌ **Cross-Function Taint Flow** - Partially (props → hooks → API)
6. ❌ **Import Chain Analysis** - Basic (component imports)
7. ✅ **React Hook Anti-Patterns** - Detection of useState + useEffect without useCallback

**React-specific capabilities**:
- ✅ Hook extraction (all types)
- ✅ Dependency array tracking
- ✅ Tainted dependency detection
- ✅ Custom hook extraction
- ✅ Anti-pattern detection

## Comparison to Test Requirements

From test_enhancements.md (lines 345-372), this fixture covers:

| Requirement | Status | Evidence |
|---|---|---|
| useState extraction | ✅ | 10 instances across components |
| useEffect extraction | ✅ | 6 instances with tainted deps |
| useCallback extraction | ✅ | 4 instances (including custom hook) |
| useMemo extraction | ✅ | 3 instances with computed values |
| useContext extraction | ✅ | Dashboard uses useAuth (context consumer) |
| Tainted dependencies | ✅ | userId, searchTerm, category, filter |
| Dependency tracking | ✅ | 15+ dependency array entries |
| Anti-pattern detection | ✅ | ProductList (useState + useEffect, no useCallback) |

## Taint Flow Paths

### Path 1: userId Prop → useEffect → API

```
UserProfile props.userId (SOURCE)
  → useEffect dependency [userId] (PROPAGATION)
  → axios.get(`/api/users/${userId}`) (SINK)
```

### Path 2: localStorage → useAuth → API Headers

```
localStorage.getItem('authToken') (SOURCE)
  → token variable (PROPAGATION)
  → axios.defaults.headers.common['Authorization'] (SINK)
```

### Path 3: Multiple Props → useCallback → API

```
Dashboard props.filter (SOURCE 1)
useAuth → user.id from localStorage (SOURCE 2)
  → useCallback dependencies [user, filter] (PROPAGATION)
  → axios.get(`/api/users/${user.id}/notifications?filter=${filter}`) (SINK)
```

## Related Documentation

- [test_enhancements.md](../../../test_enhancements.md) - React patterns (lines 345-372)
- [FIXTURE_ASSESSMENT.md](../../../FIXTURE_ASSESSMENT.md) - Node ecosystem status
- [node-express-api](../node-express-api/) - Backend API fixture

---

**Created**: 2025-10-31
**Total Code**: 499 lines (meets 400+ target)
**Language**: JavaScript (React)
**Framework**: React 18.x
**Hooks Tested**: useState, useEffect, useCallback, useMemo, useContext, custom hooks
