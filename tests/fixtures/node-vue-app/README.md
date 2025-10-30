# Node Vue App Fixture

Vue 3 SPA fixture for testing Composition API, reactive patterns, computed properties, watchers, lifecycle hooks, and taint flows through Vue reactive system.

## Purpose

Simulates a production Vue 3 application with:
- Comprehensive Composition API usage (ref, computed, watch, watchEffect, lifecycle hooks)
- Custom composables (useAuth)
- v-model two-way binding with tainted data
- Computed properties depending on tainted refs
- Watchers on tainted props and refs
- Taint flows: props → ref → computed → axios API calls
- localStorage as taint source in composables
- Multi-source taint (user.id from token + filter from input)

## Framework Patterns Included

### 1. UserProfile Component (200 lines)

**Comprehensive Composition API usage**:

```vue
<script>
import { ref, computed, watch, watchEffect, onMounted, onUnmounted } from 'vue';

export default {
  props: {
    userId: { type: Number, required: true },  // TAINT SOURCE
    showDetails: { type: Boolean, default: false }  // TAINT SOURCE
  },

  setup(props) {
    // Reactive refs
    const user = ref(null);
    const orders = ref([]);

    // Computed property
    const fullName = computed(() => {
      if (!user.value) return '';
      return `${user.value.firstName} ${user.value.lastName}`;
    });

    // Computed with reduce
    const orderStats = computed(() => {
      return {
        total: orders.value.reduce((sum, order) => sum + order.amount, 0),
        count: orders.value.length
      };
    });

    // Async function with tainted prop
    async function fetchUser() {
      // TAINT FLOW: props.userId -> axios API call
      const response = await axios.get(`/api/users/${props.userId}`);
      user.value = response.data;
    }

    // Watch on tainted prop
    watch(() => props.userId, (newUserId) => {
      fetchUser();
    });

    // Watch on tainted prop with conditional
    watch(() => props.showDetails, (newShowDetails) => {
      if (newShowDetails) {
        fetchOrders();
      }
    });

    // watchEffect with auto-tracked dependencies
    watchEffect(() => {
      if (props.userId && props.showDetails) {
        lastSeen.value = new Date();
      }
    });

    // Lifecycle hooks
    onMounted(() => {
      fetchUser();
    });

    onUnmounted(() => {
      user.value = null;
    });

    return { user, fullName, orderStats };
  }
};
</script>
```

**Tests**:
- ref declarations: 5 (user, loading, error, orders, lastSeen)
- computed properties: 2 (fullName, orderStats)
- watchers: 3 (userId, showDetails, watchEffect)
- lifecycle hooks: 2 (onMounted, onUnmounted)
- Taint flows: props.userId → 3 different API endpoints

### 2. ProductList Component (213 lines)

**v-model and computed filters**:

```vue
<template>
  <div class="product-list">
    <input v-model="searchTerm" type="text" placeholder="Search..." />
    <select v-model="selectedCategory">
      <option value="">All Categories</option>
    </select>

    <div v-for="product in filteredProducts" :key="product.id">
      {{ product.name }}
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted } from 'vue';

export default {
  props: {
    category: { type: String, default: '' }  // TAINT SOURCE
  },

  setup(props) {
    const products = ref([]);
    const searchTerm = ref('');  // TAINT SOURCE: v-model user input
    const selectedCategory = ref(props.category);  // TAINT SOURCE: prop

    // Computed property with tainted filter logic
    const filteredProducts = computed(() => {
      let filtered = products.value;

      // TAINT FLOW: searchTerm (user input) -> filter logic
      if (searchTerm.value) {
        filtered = filtered.filter(p =>
          p.name.toLowerCase().includes(searchTerm.value.toLowerCase())
        );
      }

      // TAINT FLOW: selectedCategory (user input) -> filter logic
      if (selectedCategory.value) {
        filtered = filtered.filter(p => p.category === selectedCategory.value);
      }

      return filtered;
    });

    // Async function with multi-source taint
    async function fetchProducts() {
      const params = new URLSearchParams();

      // MULTI-SOURCE TAINT: searchTerm + selectedCategory -> API call
      if (searchTerm.value) {
        params.append('search', searchTerm.value);
      }
      if (selectedCategory.value) {
        params.append('category', selectedCategory.value);
      }

      const response = await axios.get(`/api/products?${params.toString()}`);
      products.value = response.data;
    }

    // Watch on v-model ref
    watch(selectedCategory, () => {
      fetchProducts();
    });

    // Watch on prop
    watch(() => props.category, (newCategory) => {
      selectedCategory.value = newCategory;
    });

    return { searchTerm, selectedCategory, filteredProducts };
  }
};
</script>
```

**Tests**:
- v-model bindings: 2 (searchTerm, selectedCategory)
- computed properties: 2 (filteredProducts, totalProducts)
- watchers: 2 (selectedCategory, props.category)
- Multi-source taint: searchTerm + selectedCategory → API

### 3. Dashboard Component (282 lines)

**Complex reactivity with composable**:

```vue
<script>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import { useAuth } from '../composables/useAuth';

export default {
  props: {
    filter: { type: String, default: '' }  // TAINT SOURCE
  },

  setup(props) {
    // Use auth composable
    // TAINT: user.id comes from localStorage token
    const { user, isAuthenticated } = useAuth();

    const stats = ref(null);
    const notifications = ref([]);
    const notificationFilter = ref(props.filter);  // TAINT SOURCE

    // Computed with array filter
    const unreadCount = computed(() => {
      return notifications.value.filter(n => !n.read).length;
    });

    // Computed with tainted filter logic
    const filteredNotifications = computed(() => {
      let filtered = notifications.value;

      // TAINT FLOW: notificationFilter (user input) -> filter logic
      if (notificationFilter.value) {
        switch (notificationFilter.value) {
          case 'unread':
            filtered = filtered.filter(n => !n.read);
            break;
          case 'orders':
            filtered = filtered.filter(n => n.type === 'order');
            break;
        }
      }

      return filtered;
    });

    // Async function with tainted user.id from composable
    async function fetchStats() {
      if (!user.value) return;

      // TAINT FLOW: user.value.id (from localStorage) -> axios API call
      const response = await axios.get(`/api/users/${user.value.id}/stats`);
      stats.value = response.data;
    }

    // Async function with multi-source taint
    async function fetchNotifications() {
      if (!user.value) return;

      const params = new URLSearchParams();

      // MULTI-SOURCE TAINT: user.id (from token) + notificationFilter (user input)
      if (notificationFilter.value) {
        params.append('filter', notificationFilter.value);
      }

      const response = await axios.get(
        `/api/users/${user.value.id}/notifications?${params.toString()}`
      );
      notifications.value = response.data;
    }

    // Watch on composable ref
    watch(user, (newUser) => {
      if (newUser) {
        fetchStats();
        fetchNotifications();
      }
    });

    // Watch on v-model ref
    watch(notificationFilter, () => {
      fetchNotifications();
    });

    // Lifecycle with interval
    onMounted(() => {
      // Auto-refresh every 30 seconds
      refreshInterval = setInterval(() => {
        if (user.value) {
          fetchNotifications();
        }
      }, 30000);
    });

    onUnmounted(() => {
      clearInterval(refreshInterval);
    });

    return { user, stats, notifications, unreadCount, filteredNotifications };
  }
};
</script>
```

**Tests**:
- Composable usage: useAuth
- refs: 3 (stats, notifications, notificationFilter)
- computed: 2 (unreadCount, filteredNotifications)
- watchers: 3 (user from composable, notificationFilter, props.filter)
- lifecycle: 2 with interval setup/cleanup
- Multi-source taint: user.id (from localStorage) + notificationFilter → API

### 4. useAuth Composable (146 lines)

**Custom composable with localStorage taint**:

```javascript
import { ref, computed, onMounted } from 'vue';
import axios from 'axios';

export function useAuth() {
  const user = ref(null);
  const token = ref(null);

  // Computed properties
  const isAuthenticated = computed(() => !!user.value);
  const isAdmin = computed(() => user.value?.role === 'admin');

  // Load user from localStorage
  async function loadUser() {
    // TAINT SOURCE: localStorage (user-controlled)
    const storedToken = localStorage.getItem('authToken');

    if (storedToken) {
      token.value = storedToken;

      // TAINT SINK: Set Authorization header
      axios.defaults.headers.common['Authorization'] = `Bearer ${storedToken}`;

      const response = await axios.get('/api/auth/me');
      user.value = response.data;
    }
  }

  // Login function
  async function login(email, password) {
    const response = await axios.post('/api/auth/login', { email, password });
    const { token: authToken, user: userData } = response.data;

    // TAINT SINK: Store token in localStorage
    localStorage.setItem('authToken', authToken);
    axios.defaults.headers.common['Authorization'] = `Bearer ${authToken}`;

    user.value = userData;
  }

  // Logout function
  async function logout() {
    localStorage.removeItem('authToken');
    delete axios.defaults.headers.common['Authorization'];
    user.value = null;
  }

  onMounted(() => {
    loadUser();
  });

  return { user, isAuthenticated, isAdmin, login, logout };
}
```

**Tests**:
- Custom composable naming (starts with 'use')
- refs: 3 (user, loading, token)
- computed: 2 (isAuthenticated, isAdmin)
- Taint source: localStorage.getItem('authToken')
- Taint sinks: axios headers, localStorage.setItem
- API calls: 3 (GET /auth/me, POST /auth/login, POST /auth/logout)

## Populated Tables

| Table | Row Count (est) | Purpose |
|---|---|---|
| `vue_components` | 3 | UserProfile, ProductList, Dashboard |
| `vue_refs` | 20+ | ref() declarations across components |
| `vue_computed` | 6 | computed() properties |
| `vue_watchers` | 8+ | watch(), watchEffect() declarations |
| `symbols` | 15+ | Components, composables, functions |
| `function_calls` | 30+ | axios calls, Vue API calls |

## Sample Verification Queries

### Find all Vue components

```sql
SELECT
  name,
  type,
  path,
  line
FROM symbols
WHERE path LIKE '%node-vue-app/src/components/%'
  AND type IN ('component', 'function')
ORDER BY name;
```

**Expected**: 3 components (UserProfile, ProductList, Dashboard)

### Find custom composables

```sql
SELECT
  name,
  type,
  path,
  line
FROM symbols
WHERE path LIKE '%node-vue-app/src/composables/%'
  AND name LIKE 'use%'
ORDER BY name;
```

**Expected**: 1 composable (useAuth)

### Find ref() declarations

```sql
SELECT
  function_name,
  callee_function,
  file,
  line
FROM function_calls
WHERE file LIKE '%node-vue-app%'
  AND callee_function LIKE '%ref%'
ORDER BY file, line;
```

**Expected**: 15+ ref declarations

### Find computed() properties

```sql
SELECT
  function_name,
  callee_function,
  file,
  line
FROM function_calls
WHERE file LIKE '%node-vue-app%'
  AND callee_function LIKE '%computed%'
ORDER BY file, line;
```

**Expected**: 6 computed properties

### Find watchers

```sql
SELECT
  function_name,
  callee_function,
  file,
  line
FROM function_calls
WHERE file LIKE '%node-vue-app%'
  AND callee_function LIKE '%watch%'
ORDER BY file, line;
```

**Expected**: 8+ watch() declarations

### Find lifecycle hooks

```sql
SELECT
  function_name,
  callee_function,
  file,
  line
FROM function_calls
WHERE file LIKE '%node-vue-app%'
  AND (
    callee_function LIKE '%onMounted%'
    OR callee_function LIKE '%onUnmounted%'
  )
ORDER BY file, line;
```

**Expected**: 5 lifecycle hooks

### Find axios API calls

```sql
SELECT
  function_name,
  callee_function,
  file,
  line
FROM function_calls
WHERE file LIKE '%node-vue-app%'
  AND callee_function LIKE '%axios.%'
ORDER BY file, line;
```

**Expected**: 13+ API calls

### Find localStorage access

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

1. **Vue Component Extraction**: Verify all components extracted
2. **Composition API Patterns**: Test ref, computed, watch, watchEffect
3. **Lifecycle Hooks**: Test onMounted, onUnmounted
4. **Custom Composables**: Test useAuth extraction
5. **v-model Bindings**: Test two-way binding with tainted data
6. **Computed Dependencies**: Test computed properties depending on tainted refs
7. **Watchers**: Test watchers on tainted props and refs
8. **Taint Flows**: Test props → ref → computed → API calls
9. **localStorage Security**: Test localStorage as taint source

## How to Use

### 1. Index from TheAuditor Root

```bash
cd C:/Users/santa/Desktop/TheAuditor
aud index
```

### 2. Query Extracted Data

```bash
# Find all Vue components
aud context query --table vue_components --filter "file LIKE '%node-vue-app%'"

# Find computed properties
aud context query --table vue_computed --filter "file LIKE '%node-vue-app%'"
```

### 3. Run Taint Analysis

```bash
# Detect tainted props in API calls
aud detect-patterns --rule tainted-props --file tests/fixtures/node-vue-app/
```

## Files Structure

```
node-vue-app/
├── package.json              # Vue 3.x dependencies
├── src/
│   ├── components/
│   │   ├── UserProfile.vue   # Comprehensive Composition API (200 lines)
│   │   ├── ProductList.vue   # v-model and filters (213 lines)
│   │   └── Dashboard.vue     # Complex reactivity (282 lines)
│   └── composables/
│       └── useAuth.js        # Custom composable (146 lines)
├── spec.yaml                 # 10 verification rules (305 lines)
└── README.md                 # This file

Total: 841 lines of Vue code
```

## Security Patterns

### 1. Tainted Props in API Calls (MEDIUM)

**Location**: `src/components/UserProfile.vue`

**Vulnerable Pattern**:
```javascript
props: {
  userId: { type: Number, required: true }  // From parent (potentially from URL)
},
setup(props) {
  const response = await axios.get(`/api/users/${props.userId}`);
}
```

**Attack Vector**:
```
// URL: /profile?userId=999
// Attacker can access any user's data by changing URL parameter
```

**Impact**: Horizontal privilege escalation

### 2. localStorage Token Manipulation (MEDIUM)

**Location**: `src/composables/useAuth.js`

**Vulnerable Pattern**:
```javascript
const storedToken = localStorage.getItem('authToken');  // User-controlled
axios.defaults.headers.common['Authorization'] = `Bearer ${storedToken}`;
```

**Attack Vector**:
```javascript
// If attacker has XSS:
localStorage.setItem('authToken', 'malicious-token');
```

**Impact**: Token injection, session hijacking

### 3. User Input in Computed Filters (LOW)

**Location**: `src/components/ProductList.vue`

**Pattern**:
```javascript
const searchTerm = ref('');  // v-model user input

const filteredProducts = computed(() => {
  return products.value.filter(p =>
    p.name.toLowerCase().includes(searchTerm.value.toLowerCase())
  );
});
```

**Impact**: Logic bugs in filters, incorrect data display

## Advanced Capabilities Tested

From test_enhancements.md, this fixture tests **3 of 7** advanced capabilities:

1. ❌ **API Security Coverage** - N/A (frontend SPA, no server routes)
2. ❌ **SQL Query Surface Area** - N/A (frontend, no SQL)
3. ✅ **Multi-Source Taint Origin** - searchTerm + selectedCategory → API
4. ❌ **React Hook Dependencies** - N/A (Vue, not React)
5. ✅ **Cross-Function Taint Flow** - props → ref → computed → API calls
6. ✅ **Import Chain Analysis** - import { useAuth } from '../composables/useAuth'
7. ❌ **React Hook Anti-Patterns** - N/A (Vue, not React)

**Vue-specific capabilities**:
- ✅ Vue component extraction
- ✅ Composition API patterns (ref, computed, watch)
- ✅ Custom composables
- ✅ v-model tainted bindings
- ✅ Lifecycle hooks
- ✅ watchEffect with auto-tracked dependencies

## Comparison to Test Requirements

From test_enhancements.md (lines 310-345), this fixture covers:

| Requirement | Status | Evidence |
|---|---|---|
| Vue 3 components | ✅ | 3 components with Composition API |
| ref() declarations | ✅ | 20+ reactive refs |
| computed() properties | ✅ | 6 computed properties |
| watch() / watchEffect() | ✅ | 8+ watchers |
| Lifecycle hooks | ✅ | 5 lifecycle hooks (onMounted, onUnmounted) |
| Custom composables | ✅ | useAuth composable |
| v-model bindings | ✅ | 3 v-model refs with tainted data |
| Taint flows | ✅ | 7+ distinct taint paths |

## Taint Flow Paths

### Path 1: Prop → ref → API Call

```
props.userId (SOURCE - from parent, potentially URL)
  → fetchUser() (PROPAGATION)
  → axios.get(`/api/users/${props.userId}`) (SINK)
```

### Path 2: v-model → Computed → API Call

```
v-model searchTerm (SOURCE - user input)
  → filteredProducts computed property (PROPAGATION)
  → fetchProducts() → axios.get with params (SINK)
```

### Path 3: localStorage → Composable → API Call

```
localStorage.getItem('authToken') (SOURCE - user-controlled)
  → useAuth composable → user.value.id (PROPAGATION)
  → axios.get(`/api/users/${user.value.id}/stats`) (SINK)
```

### Path 4: Multi-Source → API Call

```
user.value.id (SOURCE 1 - from localStorage token)
notificationFilter.value (SOURCE 2 - v-model user input)
  → fetchNotifications() (PROPAGATION)
  → axios.get(`/api/users/${user.id}/notifications?filter=${filter}`) (SINK)
```

### Path 5: Prop → Watch → API Call

```
props.showDetails (SOURCE - boolean prop)
  → watch(() => props.showDetails) (PROPAGATION)
  → fetchOrders() → axios.get (SINK)
```

## Related Documentation

- [test_enhancements.md](../../../test_enhancements.md) - Vue patterns (lines 310-345)
- [FIXTURE_ASSESSMENT.md](../../../FIXTURE_ASSESSMENT.md) - Node ecosystem status
- [node-react-app](../node-react-app/) - React SPA fixture (similar patterns)

---

**Created**: 2025-10-31
**Total Code**: 841 lines (exceeds 400+ target)
**Language**: JavaScript (Vue 3)
**Framework**: Vue 3.3.x Composition API
**Patterns Tested**: Composition API, reactive refs, computed, watchers, composables, taint flows
