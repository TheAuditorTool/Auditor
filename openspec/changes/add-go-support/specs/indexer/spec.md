## ADDED Requirements

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
- **THEN** tables go_goroutines, go_channels, go_channel_ops, go_defer_statements SHALL exist

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

#### Scenario: Gin detection
- **WHEN** a Go project imports `github.com/gin-gonic/gin`
- **THEN** the indexer SHALL detect route handlers and extract HTTP method and path

#### Scenario: Echo detection
- **WHEN** a Go project imports `github.com/labstack/echo`
- **THEN** the indexer SHALL detect route handlers and extract HTTP method and path

#### Scenario: Fiber detection
- **WHEN** a Go project imports `github.com/gofiber/fiber`
- **THEN** the indexer SHALL detect route handlers and extract HTTP method and path

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
