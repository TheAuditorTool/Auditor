# Angular Enterprise Framework Test Suite

**Purpose**: Comprehensive Angular 17.x fixture for decorator extraction (@Component, @Injectable, @NgModule), dependency injection, RxJS patterns, route guards, and HTTP client usage.

**Version**: Angular 17.x
**Lines of Code**: ~700 lines
**Created**: 2025-10-31

---

## Overview

This fixture demonstrates enterprise Angular patterns critical for static analysis:

- **Decorators**: @Component, @Injectable, @NgModule, @Input, @Output
- **Dependency Injection**: Constructor-based DI, providedIn: 'root', multi-providers
- **RxJS**: Observables, BehaviorSubject, operators (map, tap, catchError, retry, shareReplay, takeUntil)
- **State Management**: Service-based state with BehaviorSubject patterns
- **HTTP Client**: REST API calls with request/response transformation
- **Route Guards**: CanActivate implementation for authentication
- **Lifecycle Hooks**: OnInit, OnDestroy with proper cleanup

---

## File Structure

```
node-angular-app/
├── package.json                    # Angular 17.x dependencies
├── spec.yaml                       # 7 verification tests
├── README.md                       # This file
└── src/
    └── app/
        ├── app.module.ts           # @NgModule with DI configuration (85 lines)
        ├── models/
        │   └── user.model.ts       # TypeScript interfaces
        ├── services/
        │   ├── user.service.ts     # CRUD service with HttpClient (177 lines)
        │   ├── auth.service.ts     # Authentication service (90 lines)
        │   ├── api.service.ts      # Base API service
        │   └── state.service.ts    # Global state management
        ├── components/
        │   └── user-list/
        │       └── user-list.component.ts  # @Component with @Input/@Output (71 lines)
        └── guards/
            └── auth.guard.ts       # CanActivate route guard (31 lines)
```

---

## Key Patterns Demonstrated

### 1. Module Configuration (@NgModule)

**File**: `app.module.ts`

```typescript
@NgModule({
  declarations: [
    AppComponent,
    UserListComponent,
    UserDetailComponent,
    LoginComponent,
    DashboardComponent
  ],
  imports: [
    BrowserModule,
    HttpClientModule,
    FormsModule,
    ReactiveFormsModule,
    RouterModule.forRoot(routes)
  ],
  providers: [
    UserService,
    AuthService,
    AuthGuard,
    {
      provide: HTTP_INTERCEPTORS,
      useClass: AuthInterceptor,
      multi: true
    }
  ],
  bootstrap: [AppComponent]
})
export class AppModule {}
```

**Patterns**:
- Component declarations
- Module imports
- Service providers (global scope)
- HTTP interceptors (multi-provider pattern)
- Router configuration

### 2. Injectable Services (@Injectable)

**File**: `user.service.ts`

```typescript
@Injectable({
  providedIn: 'root'  // Global singleton
})
export class UserService {
  private usersSubject = new BehaviorSubject<User[]>([]);
  public users$ = this.usersSubject.asObservable();

  constructor(
    private http: HttpClient,       // DI: Angular's HTTP client
    private apiService: ApiService,  // DI: Custom API service
    private stateService: StateService  // DI: State management
  ) {}

  getUsers(filters?: UserFilters): Observable<User[]> {
    return this.http.get<User[]>(this.apiUrl, { params }).pipe(
      retry(2),                      // Retry failed requests
      tap((users) => this.usersSubject.next(users)),  // Update state
      shareReplay(1),                // Cache for multiple subscribers
      catchError(this.handleError)
    );
  }

  createUser(userData: Partial<User>): Observable<User> {
    // TAINT FLOW: userData (user input) -> HTTP POST
    return this.http.post<User>(this.apiUrl, userData).pipe(
      tap((newUser) => {
        const currentUsers = this.usersSubject.value;
        this.usersSubject.next([...currentUsers, newUser]);
      }),
      catchError(this.handleError)
    );
  }
}
```

**Patterns**:
- Constructor dependency injection (3 services)
- BehaviorSubject for reactive state
- RxJS operators: retry, tap, shareReplay, catchError
- HTTP GET/POST/PUT/DELETE with typed responses
- State synchronization after mutations

### 3. Authentication Service

**File**: `auth.service.ts`

```typescript
@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private currentUserSubject: BehaviorSubject<any>;
  public currentUser$: Observable<any>;
  private tokenKey = 'auth_token';

  constructor(
    private http: HttpClient,
    private router: Router
  ) {
    const storedUser = localStorage.getItem('currentUser');
    this.currentUserSubject = new BehaviorSubject<any>(
      storedUser ? JSON.parse(storedUser) : null
    );
    this.currentUser$ = this.currentUserSubject.asObservable();
  }

  login(credentials: { email: string; password: string }): Observable<any> {
    // TAINT FLOW: credentials -> API -> localStorage
    return this.http.post<any>('/api/auth/login', credentials).pipe(
      map((response) => {
        if (response && response.token) {
          localStorage.setItem(this.tokenKey, response.token);
          localStorage.setItem('currentUser', JSON.stringify(response.user));
          this.currentUserSubject.next(response.user);
        }
        return response;
      })
    );
  }

  logout(): void {
    localStorage.removeItem(this.tokenKey);
    localStorage.removeItem('currentUser');
    this.currentUserSubject.next(null);
    this.router.navigate(['/login']);
  }
}
```

**Patterns**:
- Token storage in localStorage (XSS vulnerability pattern)
- BehaviorSubject for authentication state
- Observable streams for reactive updates
- Router navigation on logout

### 4. Component with Decorators

**File**: `user-list.component.ts`

```typescript
@Component({
  selector: 'app-user-list',
  templateUrl: './user-list.component.html',
  styleUrls: ['./user-list.component.css']
})
export class UserListComponent implements OnInit, OnDestroy {
  @Input() filters: any;                      // Parent -> child data
  @Output() userSelected = new EventEmitter<User>();  // Child -> parent event
  @Output() userDeleted = new EventEmitter<string>();

  users: User[] = [];
  loading = false;
  error: string | null = null;
  private destroy$ = new Subject<void>();

  constructor(private userService: UserService) {}

  ngOnInit(): void {
    this.loadUsers();
  }

  ngOnDestroy(): void {
    this.destroy$.next();      // Trigger unsubscribe
    this.destroy$.complete();  // Complete subject
  }

  loadUsers(): void {
    this.loading = true;
    this.userService
      .getUsers(this.filters)
      .pipe(takeUntil(this.destroy$))  // Auto-unsubscribe on destroy
      .subscribe({
        next: (users) => {
          this.users = users;
          this.loading = false;
        },
        error: (err) => {
          this.error = err.message;
          this.loading = false;
        }
      });
  }

  onSelectUser(user: User): void {
    this.userSelected.emit(user);  // Emit to parent
  }
}
```

**Patterns**:
- @Input/@Output decorators for component communication
- Lifecycle hooks: OnInit, OnDestroy
- Proper subscription cleanup with takeUntil pattern
- Service injection via constructor
- EventEmitter for parent-child communication

### 5. Route Guards (CanActivate)

**File**: `auth.guard.ts`

```typescript
@Injectable({
  providedIn: 'root'
})
export class AuthGuard implements CanActivate {
  constructor(
    private router: Router,
    private authService: AuthService
  ) {}

  canActivate(
    route: ActivatedRouteSnapshot,
    state: RouterStateSnapshot
  ): boolean {
    if (this.authService.isAuthenticated) {
      return true;
    }

    // Not authenticated, redirect to login
    this.router.navigate(['/login'], {
      queryParams: { returnUrl: state.url }
    });
    return false;
  }
}
```

**Patterns**:
- CanActivate interface implementation
- Authentication check before route activation
- Redirect with returnUrl for post-login navigation

---

## RxJS Operators Used

| Operator | File | Purpose |
|----------|------|---------|
| `map` | auth.service.ts, user.service.ts | Transform response data |
| `tap` | user.service.ts | Side effects (state updates, logging) |
| `catchError` | user.service.ts | Error handling |
| `retry` | user.service.ts | Automatic retry on failure |
| `shareReplay` | user.service.ts | Cache for multiple subscribers |
| `takeUntil` | user-list.component.ts | Auto-unsubscribe on component destroy |

---

## Dependency Injection Graph

```
AppModule
├── UserListComponent
│   └── UserService
│       ├── HttpClient (Angular)
│       ├── ApiService (custom)
│       └── StateService (custom)
├── AuthGuard
│   ├── Router (Angular)
│   └── AuthService
│       ├── HttpClient (Angular)
│       └── Router (Angular)
└── HTTP_INTERCEPTORS (multi-provider)
    └── AuthInterceptor
```

**Key DI Patterns**:
- Constructor injection (standard)
- `providedIn: 'root'` (tree-shakable providers)
- Multi-providers (`multi: true` for interceptors)
- Interface-based providers (`HTTP_INTERCEPTORS` token)

---

## Taint Flows

### 1. Login Credentials → localStorage

**Source**: `auth.service.ts:44`
```typescript
login(credentials: { email: string; password: string }): Observable<any> {
  return this.http.post<any>('/api/auth/login', credentials).pipe(
    map((response) => {
      localStorage.setItem(this.tokenKey, response.token);  // SINK: XSS risk
      localStorage.setItem('currentUser', JSON.stringify(response.user));
    })
  );
}
```

**Risk**: Storing tokens in localStorage is vulnerable to XSS attacks. Better alternative: httpOnly cookies.

### 2. User Data → API POST

**Source**: `user.service.ts:76`
```typescript
createUser(userData: Partial<User>): Observable<User> {
  return this.http.post<User>(this.apiUrl, userData).pipe(  // SINK: HTTP POST
    tap((newUser) => {
      this.usersSubject.next([...currentUsers, newUser]);
    })
  );
}
```

**Risk**: User input flows directly to API without validation. Should validate/sanitize before POST.

### 3. Search Query → API Request

**Source**: `user.service.ts:124`
```typescript
searchUsers(searchQuery: string): Observable<User[]> {
  const params = new HttpParams().set('q', searchQuery);  // SINK: Query param
  return this.http.get<User[]>(`${this.apiUrl}/search`, { params });
}
```

**Risk**: Search query from user input → URL parameter without sanitization. Potential for SQL injection if backend doesn't validate.

### 4. User Filters → HTTP Params

**Source**: `user.service.ts:41`
```typescript
getUsers(filters?: UserFilters): Observable<User[]> {
  let params = new HttpParams();
  if (filters) {
    if (filters.status) params = params.set('status', filters.status);
    if (filters.role) params = params.set('role', filters.role);
    if (filters.search) params = params.set('search', filters.search);  // SINK
  }
  return this.http.get<User[]>(this.apiUrl, { params });
}
```

**Risk**: Filter values from user input → query parameters without validation.

---

## Downstream Consumer Impact

### `aud blueprint` Output

```
Angular Application Structure:
├── Services: 4 (@Injectable)
│   ├── UserService (CRUD operations, 12 methods)
│   ├── AuthService (authentication, 4 methods)
│   ├── ApiService (base API utilities)
│   └── StateService (global state management)
├── Components: 4 (@Component)
│   ├── UserListComponent (@Input: filters, @Output: userSelected, userDeleted)
│   ├── UserDetailComponent
│   ├── LoginComponent
│   └── DashboardComponent
├── Guards: 1 (CanActivate)
│   └── AuthGuard (protects /dashboard, /users routes)
└── Modules: 1 (@NgModule)
    └── AppModule (5 components, 4 services, 1 guard, 1 interceptor)

Dependency Injection:
- UserListComponent → UserService → [HttpClient, ApiService, StateService]
- AuthGuard → [Router, AuthService]
- AuthService → [HttpClient, Router]

RxJS Patterns:
- BehaviorSubject: 2 instances (users$, currentUser$)
- Observables: All HTTP operations
- Operators: retry (3 uses), tap (8 uses), catchError (6 uses), shareReplay (1 use)

HTTP Operations:
- GET: 4 endpoints (users, user by ID, search, stats)
- POST: 3 endpoints (login, create user, bulk update)
- PUT: 1 endpoint (update user)
- DELETE: 1 endpoint (delete user)

Route Protection:
- AuthGuard on /dashboard and /users routes
- Redirect to /login with returnUrl on unauthorized access
```

### `aud taint analyze` Output

```
TAINT FLOWS DETECTED:

1. Login Credentials → localStorage (XSS Risk)
   Source: auth.service.ts:44 (login method parameter)
   Sink: auth.service.ts:48 (localStorage.setItem)
   Flow: credentials → HTTP POST → response.token → localStorage
   Risk: HIGH - Tokens in localStorage vulnerable to XSS
   Recommendation: Use httpOnly cookies instead

2. User Data → HTTP POST (Injection Risk)
   Source: user.service.ts:76 (createUser parameter)
   Sink: user.service.ts:77 (http.post)
   Flow: userData → HTTP POST body
   Risk: MEDIUM - Unvalidated user input sent to API
   Recommendation: Validate/sanitize before sending

3. Search Query → API Request (SQL Injection Risk)
   Source: user.service.ts:124 (searchUsers parameter)
   Sink: user.service.ts:125 (HttpParams.set)
   Flow: searchQuery → URL query parameter → backend SQL
   Risk: HIGH - User input in query params without sanitization
   Recommendation: Backend MUST use parameterized queries

4. User Filters → HTTP Params
   Source: user.service.ts:41 (getUsers parameter)
   Sink: user.service.ts:45-47 (params.set)
   Flow: filters.search → URL query parameter
   Risk: MEDIUM - Multiple filter fields without validation
   Recommendation: Whitelist valid filter values
```

### `aud detect-patterns` Output

```
SECURITY PATTERNS DETECTED:

1. Token Storage Vulnerability (auth.service.ts:48, 49)
   Pattern: localStorage.setItem with auth tokens
   Risk: HIGH - XSS can steal tokens
   Fix: Use httpOnly cookies or sessionStorage with short TTL

2. Missing CSRF Protection
   Pattern: HTTP POST/PUT/DELETE without CSRF tokens
   Locations: user.service.ts (lines 77, 92, 110, 154)
   Risk: MEDIUM - State-changing operations without CSRF protection
   Fix: Add CSRF token interceptor

3. Unsubscribed Observables (MEMORY LEAK PREVENTION)
   Pattern: takeUntil(destroy$) in user-list.component.ts:41
   Status: GOOD - Proper cleanup implemented
   Note: Verify all components follow this pattern

4. Error Exposure (user.service.ts:172-174)
   Pattern: console.error with full error details
   Risk: LOW - Error details may leak in production
   Fix: Use logging service with environment-specific behavior

5. BehaviorSubject State Management (GOOD PATTERN)
   Pattern: BehaviorSubject with asObservable() exposure
   Locations: user.service.ts:24-25, auth.service.ts:16-28
   Status: GOOD - Proper encapsulation of state

6. Retry Without Exponential Backoff
   Pattern: retry(2) in user.service.ts:51
   Risk: LOW - May overwhelm failing service
   Fix: Use retryWhen with exponential backoff
```

---

## Verification Tests

**File**: `spec.yaml`

7 verification tests covering:

1. **AppModule extraction** - Verify @NgModule decorator detected
2. **UserService extraction** - Verify @Injectable with DI
3. **AuthService extraction** - Verify authentication service
4. **UserListComponent extraction** - Verify @Component with @Input/@Output
5. **AuthGuard extraction** - Verify CanActivate implementation
6. **Login credentials taint** - Verify credentials → API → localStorage flow
7. **User data taint** - Verify userData → createUser → POST flow

All tests use SQL JOINs on junction tables (not LIKE patterns) for accurate detection.

---

## Why This Fixture Matters

### Current Gap

TheAuditor has **ZERO Angular extraction**. Angular is one of the most popular enterprise frameworks, used in:
- Fortune 500 applications
- Government projects
- Large-scale SaaS platforms

Without Angular extraction, TheAuditor cannot analyze:
- Decorator-based DI patterns
- Component communication (@Input/@Output)
- RxJS data flows
- Route guard authentication
- HTTP interceptor security

### Downstream Impact

Once Angular extractor is built, this fixture enables:

1. **`aud blueprint`**: Show Angular module structure, DI graph, component hierarchy
2. **`aud taint analyze`**: Track data flows through RxJS observables and HTTP operations
3. **`aud detect-patterns`**: Find localStorage vulnerabilities, missing CSRF protection, memory leaks
4. **`aud planning`**: Generate tasks for refactoring Angular services or components
5. **Security audits**: Detect authentication bypasses, XSS risks, injection vulnerabilities

---

## Angular-Specific Extraction Requirements

### Must Extract:

1. **Decorators**:
   - @Component (selector, template, styles)
   - @Injectable (providedIn scope)
   - @NgModule (declarations, imports, providers, bootstrap)
   - @Input/@Output (component communication)

2. **Dependency Injection**:
   - Constructor parameters (type-based DI)
   - Provider configurations (multi-providers, factory providers)
   - Injection tokens (HTTP_INTERCEPTORS, etc.)

3. **RxJS Patterns**:
   - Observable creation (BehaviorSubject, Subject, of, from)
   - Operators (map, tap, catchError, retry, shareReplay, takeUntil)
   - Subscription patterns (subscribe, async pipe)

4. **HTTP Operations**:
   - Method (GET/POST/PUT/DELETE)
   - URL endpoints
   - Request/response types
   - Query parameters (HttpParams)

5. **Lifecycle Hooks**:
   - OnInit, OnDestroy, OnChanges, etc.
   - Cleanup patterns (Subject completion)

6. **Route Guards**:
   - CanActivate, CanDeactivate implementations
   - Protected routes

### Taint Sources:

- @Input properties (user-controlled data from parent)
- HTTP request parameters (credentials, userData, searchQuery)
- Query parameters (filters, search terms)
- localStorage/sessionStorage reads

### Taint Sinks:

- localStorage.setItem (XSS vulnerability)
- http.post/put (injection risk)
- HttpParams.set (SQL injection risk)
- innerHTML bindings (XSS risk)

---

## Comparison with Other Frameworks

| Pattern | Angular | React | Vue |
|---------|---------|-------|-----|
| **State Management** | BehaviorSubject | useState, Zustand | ref, reactive |
| **DI** | Constructor injection | Props drilling, Context | provide/inject |
| **HTTP** | HttpClient | fetch, Axios, React Query | fetch, Axios |
| **Decorators** | @Component, @Injectable | None (HOCs) | @Component (Vue 2 class API) |
| **Reactivity** | RxJS Observables | Re-renders | Proxy-based reactivity |
| **Lifecycle** | ngOnInit, ngOnDestroy | useEffect | onMounted, onUnmounted |

Angular's decorator-based architecture requires **specialized AST parsing** to extract metadata from TypeScript decorators, making this fixture critical for validating extractor logic.

---

## Testing Checklist

After building the Angular extractor, verify:

- [ ] All 7 spec.yaml tests pass
- [ ] @NgModule, @Component, @Injectable decorators extracted
- [ ] DI graph shows constructor dependencies
- [ ] RxJS operators detected (retry, tap, catchError, shareReplay)
- [ ] HTTP operations extracted (method, URL, params)
- [ ] Taint flows detected: credentials → localStorage, userData → POST
- [ ] Route guards extracted (CanActivate)
- [ ] @Input/@Output decorators linked to parent/child components
- [ ] Lifecycle hooks detected (OnInit, OnDestroy)
- [ ] `aud blueprint` shows Angular structure
- [ ] `aud detect-patterns` finds localStorage XSS risk

---

## Total Lines of Code

- **app.module.ts**: 85 lines
- **user.service.ts**: 177 lines
- **auth.service.ts**: 90 lines
- **user-list.component.ts**: 71 lines
- **auth.guard.ts**: 31 lines
- **spec.yaml**: 120 lines
- **package.json**: 40 lines
- **README.md**: 700+ lines

**Total**: ~1,314 lines (fixture code + documentation)

---

## Next Steps

1. **Build Angular Extractor** (`theauditor/indexer/extractors/angular_extractor.py`)
2. **Run Extraction**: `aud index tests/fixtures/node-angular-app/`
3. **Verify Tests**: Run spec.yaml verification queries
4. **Test on Production**: Apply to real Angular projects (if available)

---

**Created**: 2025-10-31
**Status**: ✅ COMPLETE - Ready for extractor development
**Priority**: CRITICAL - Angular is #1 enterprise framework with zero current support
