## ADDED Requirements

### Requirement: Go Parser Compatibility (CRITICAL)
The indexer SHALL use a tree-sitter-go grammar that supports Go 1.18+ syntax.

#### Scenario: Generic function parsing
- **WHEN** a Go file contains `func Map[T any](s []T) []T`
- **THEN** the parser SHALL NOT produce ERROR nodes
- **AND** the indexer SHALL extract type parameter information

#### Scenario: Generic type parsing
- **WHEN** a Go file contains `type Stack[T comparable] struct`
- **THEN** the parser SHALL NOT produce ERROR nodes
- **AND** the indexer SHALL extract type parameter information

### Requirement: Vendor Directory Exclusion
The indexer SHALL exclude vendor directories during file walking.

#### Scenario: Vendor exclusion
- **WHEN** a Go project contains a vendor/ directory
- **THEN** the indexer SHALL NOT traverse or index files within vendor/
- **AND** the database SHALL NOT contain symbols from vendored dependencies

### Requirement: Go Language Extraction
The indexer SHALL extract Go language constructs from .go files using tree-sitter parsing.

#### Scenario: Package extraction
- **WHEN** a Go file contains a package declaration
- **THEN** the indexer SHALL extract package name and associate with file path
- **AND** the indexer SHALL store data in go_packages table

#### Scenario: Import extraction
- **WHEN** a Go file contains import statements
- **THEN** the indexer SHALL extract import path, optional alias, and dot-import flag
- **AND** the indexer SHALL store data in go_imports table

#### Scenario: Struct extraction
- **WHEN** a Go file contains a struct type definition
- **THEN** the indexer SHALL extract struct name, visibility (exported), and fields
- **AND** the indexer SHALL store data in go_structs and go_struct_fields tables
- **AND** struct tags (json, db, etc.) SHALL be extracted

#### Scenario: Interface extraction
- **WHEN** a Go file contains an interface type definition
- **THEN** the indexer SHALL extract interface name, visibility, and method signatures
- **AND** the indexer SHALL store data in go_interfaces and go_interface_methods tables

#### Scenario: Function extraction
- **WHEN** a Go file contains a function declaration (no receiver)
- **THEN** the indexer SHALL extract function name, parameters, return types, and visibility
- **AND** the indexer SHALL store data in go_functions and go_func_params tables

#### Scenario: Method extraction
- **WHEN** a Go file contains a method (function with receiver)
- **THEN** the indexer SHALL extract receiver type, method name, parameters, return types
- **AND** the indexer SHALL store data in go_methods table
- **AND** pointer receivers vs value receivers SHALL be distinguished

### Requirement: Go Variable Extraction
The indexer SHALL extract variable declarations with package-level detection.

#### Scenario: Package-level variable extraction
- **WHEN** a Go file contains a `var` declaration at package scope (not inside a function)
- **THEN** the indexer SHALL extract variable name, type, and initial value
- **AND** the indexer SHALL set is_package_level=1 in go_variables table
- **AND** security rules MAY use this flag to detect race conditions

#### Scenario: Local variable distinction
- **WHEN** a Go file contains a `var` declaration inside a function
- **THEN** the indexer SHALL set is_package_level=0 in go_variables table

### Requirement: Go Type Parameter Extraction
The indexer SHALL extract generic type parameters from Go 1.18+ code.

#### Scenario: Function type parameter extraction
- **WHEN** a Go file contains `func Map[T any, U comparable](...)`
- **THEN** the indexer SHALL extract each type parameter (T, U)
- **AND** the indexer SHALL extract constraints (any, comparable)
- **AND** the indexer SHALL store data in go_type_params table with parent_kind='function'

#### Scenario: Type type parameter extraction
- **WHEN** a Go file contains `type Stack[T any] struct`
- **THEN** the indexer SHALL extract type parameter T
- **AND** the indexer SHALL store data in go_type_params table with parent_kind='type'

### Requirement: Go Schema Tables
The indexer SHALL store Go extraction data in dedicated normalized tables.

#### Scenario: Core entity tables exist
- **WHEN** the database is initialized
- **THEN** tables go_packages, go_imports, go_structs, go_interfaces, go_functions, go_methods SHALL exist

#### Scenario: Junction tables exist
- **WHEN** the database is initialized
- **THEN** tables go_struct_fields, go_interface_methods, go_func_params, go_func_returns SHALL exist

#### Scenario: Concurrency tables exist
- **WHEN** the database is initialized
- **THEN** tables go_goroutines, go_channels, go_channel_ops, go_defer_statements, go_captured_vars SHALL exist

#### Scenario: New analysis tables exist
- **WHEN** the database is initialized
- **THEN** tables go_variables, go_type_params, go_middleware SHALL exist

### Requirement: Go Concurrency Tracking
The indexer SHALL track goroutine spawn points and channel operations.

#### Scenario: Goroutine extraction
- **WHEN** a Go file contains a `go` statement
- **THEN** the indexer SHALL extract the spawn site, containing function, and spawned expression
- **AND** anonymous function spawns SHALL be flagged

#### Scenario: Channel declaration extraction
- **WHEN** a Go file contains a channel type declaration or `make(chan T)`
- **THEN** the indexer SHALL extract channel name, element type, and buffer size if specified

#### Scenario: Channel operation extraction
- **WHEN** a Go file contains channel send (`ch <- val`) or receive (`<-ch`) operations
- **THEN** the indexer SHALL extract the operation type, channel name, and containing function

#### Scenario: Defer statement extraction
- **WHEN** a Go file contains a defer statement
- **THEN** the indexer SHALL extract the deferred call, containing function, and line

### Requirement: Go Captured Variable Tracking (CRITICAL for race detection)
The indexer SHALL track variables captured by anonymous goroutine closures.

#### Scenario: Captured variable extraction
- **WHEN** a Go file contains `go func() { use(x) }()` where x is defined outside the closure
- **THEN** the indexer SHALL extract variable x as a captured variable
- **AND** the indexer SHALL store data in go_captured_vars table

#### Scenario: Loop variable capture detection
- **WHEN** a captured variable is defined in an enclosing for/range loop
- **THEN** the indexer SHALL set is_loop_var=1 in go_captured_vars table
- **AND** this pattern SHALL be flagged by race condition detection rules

### Requirement: Go Error Handling Tracking
The indexer SHALL track error return patterns and handling.

#### Scenario: Error return detection
- **WHEN** a function signature includes `error` in return types
- **THEN** the indexer SHALL mark the function as returning error in go_error_returns table

#### Scenario: Ignored error detection
- **WHEN** a function call result is assigned to `_` and the function returns error
- **THEN** the indexer SHALL flag the call site as ignoring error

### Requirement: Go Framework Detection
The indexer SHALL detect common Go web frameworks and ORMs.

#### Scenario: net/http standard library detection (CRITICAL)
- **WHEN** a Go project imports `net/http`
- **THEN** the indexer SHALL detect route handlers via http.HandleFunc/http.Handle
- **AND** the indexer SHALL extract path and handler function name
- **Note**: net/http is MORE common in Go than frameworks; missing it is a major gap

#### Scenario: Gin detection
- **WHEN** a Go project imports `github.com/gin-gonic/gin`
- **THEN** the indexer SHALL detect route handlers and extract HTTP method and path

#### Scenario: Echo detection
- **WHEN** a Go project imports `github.com/labstack/echo`
- **THEN** the indexer SHALL detect route handlers and extract HTTP method and path

#### Scenario: Fiber detection
- **WHEN** a Go project imports `github.com/gofiber/fiber`
- **THEN** the indexer SHALL detect route handlers and extract HTTP method and path

### Requirement: Go Middleware Detection
The indexer SHALL detect middleware registration in web frameworks.

#### Scenario: Middleware extraction
- **WHEN** a Go file contains `.Use(middleware)` calls on router variables
- **THEN** the indexer SHALL extract the middleware function name
- **AND** the indexer SHALL store data in go_middleware table
- **AND** the indexer SHALL detect if middleware is global or group-specific

#### Scenario: Security middleware linking
- **WHEN** middleware is registered before route handlers
- **THEN** the indexer SHALL enable queries to determine which routes are protected
- **AND** security auditing MAY use this to find unprotected routes

#### Scenario: GORM detection
- **WHEN** a Go project imports `gorm.io/gorm`
- **THEN** the indexer SHALL detect model structs and query patterns

#### Scenario: gRPC detection
- **WHEN** a Go project imports `google.golang.org/grpc`
- **THEN** the indexer SHALL detect service definitions and RPC handlers

### Requirement: Go Security Pattern Detection
The indexer SHALL detect security-relevant patterns in Go code.

#### Scenario: SQL injection detection
- **WHEN** SQL query strings are constructed via fmt.Sprintf or string concatenation
- **THEN** the indexer SHALL flag it as a SQL injection finding

#### Scenario: Command injection detection
- **WHEN** `os/exec.Command()` is called with user-controlled input
- **THEN** the indexer SHALL flag it as a command injection finding

#### Scenario: Template injection detection
- **WHEN** `template.HTML()` or `template.JS()` is called with user input
- **THEN** the indexer SHALL flag it as a template injection finding

#### Scenario: Insecure random detection
- **WHEN** `math/rand` is used in a crypto or security context
- **THEN** the indexer SHALL flag it as crypto misuse (should use crypto/rand)

#### Scenario: Ignored error in security context
- **WHEN** an error from a security-sensitive function is ignored
- **THEN** the indexer SHALL flag it as a security finding

#### Scenario: Race condition pattern detection
- **WHEN** shared variables are accessed from goroutines without sync primitives
- **THEN** the indexer SHALL flag it as a potential race condition

#### Scenario: Captured loop variable race detection (HIGH PRIORITY)
- **WHEN** go_captured_vars contains entries with is_loop_var=1
- **THEN** the security rules SHALL flag it as a high-confidence race condition
- **AND** the finding SHALL include the goroutine spawn site and captured variable name

#### Scenario: Package-level variable race detection
- **WHEN** a goroutine accesses a variable from go_variables WHERE is_package_level=1
- **AND** no sync.Mutex usage is detected in the same function
- **THEN** the security rules SHALL flag it as a potential race condition
