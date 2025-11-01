"""Taint source, sink, and sanitizer definitions.

This module contains all the constant definitions for taint analysis:
- TAINT_SOURCES: Where untrusted data originates
- SECURITY_SINKS: Where untrusted data should not flow
- SANITIZERS: Functions that clean/validate data

PERFORMANCE: All patterns use frozensets for O(1) lookup instead of O(N) lists.
"""

import platform

# Detect if running on Windows for character encoding
IS_WINDOWS = platform.system() == "Windows"


# Define taint sources (where untrusted data originates)
# Refined to focus on truly external/untrusted input sources
# PERFORMANCE: frozensets provide O(1) membership testing
TAINT_SOURCES = {
    # JavaScript/TypeScript sources - Web request data only
    "js": frozenset([
        "req.body",
        "req.query",
        "req.params",
        "req.headers",
        "req.cookies",
        "request.body",
        "request.query",
        "request.params",
        "ctx.request.body",
        "ctx.query",
        "ctx.params",
        "document.location",
        "window.location",
        "document.URL",
        "document.referrer",
        "localStorage.getItem",
        "sessionStorage.getItem",
        "URLSearchParams",
        "postMessage",
    ]),
    # Python sources - Web and CLI input only
    "python": frozenset([
        "request.args",
        "request.form",
        "request.json",
        "request.data",
        "request.values",
        "request.files",
        "request.cookies",
        "request.headers",
        "request.get_json",
        "request.get_data",
        "input",  # User console input
        "raw_input",  # Python 2 user input
        "sys.argv",  # Command line arguments
        "click.argument",  # Click CLI arguments
        "click.option",  # Click CLI options
        "argparse.parse_args",  # Argparse arguments
    ]),
    # Network sources only - removed generic file operations
    "network": frozenset([
        "socket.recv",
        "socket.recvfrom",
        "websocket.receive",
        "stdin.read",  # Console input
    ]),
    # Web scraping and data extraction sources
    "web_scraping": frozenset([
        # Requests library
        "requests.get",
        "requests.post",
        "requests.put",
        "requests.patch",
        "requests.delete",
        "response.text",
        "response.content",
        "response.json",
        "resp.text",
        "resp.content",
        "resp.json",

        # urllib
        "urlopen",
        "urllib.request.urlopen",
        "urllib2.urlopen",

        # BeautifulSoup HTML parsing
        "BeautifulSoup",
        "soup.find",
        "soup.find_all",
        "soup.select",
        "soup.select_one",
        "element.text",
        "element.get_text",
        "element.string",
        "tag.text",
        "tag.get_text",

        # Playwright browser automation
        "page.content",
        "page.inner_text",
        "page.inner_html",
        "page.locator",
        "page.text_content",
        "element.inner_text",
        "element.inner_html",
        "element.text_content",

        # Selenium browser automation
        "driver.page_source",
        "driver.find_element",
        "element.text",
        "element.get_attribute",
        "webdriver.page_source",

        # Scrapy framework
        "response.body",
        "response.text",
        "response.css",
        "response.xpath",
        "selector.get",
        "selector.getall",
    ]),
    # File I/O and data loading sources
    "file_io": frozenset([
        # Basic file operations
        "open",
        "file.read",
        "file.readline",
        "file.readlines",

        # JSON operations
        "json.load",
        "json.loads",
        "json.JSONDecoder",

        # CSV/Excel operations
        "csv.reader",
        "csv.DictReader",
        "pd.read_csv",
        "pd.read_excel",
        "pd.read_json",
        "pd.read_html",
        "pd.read_sql",
        "pandas.read_csv",
        "pandas.read_excel",

        # YAML operations
        "yaml.load",
        "yaml.safe_load",
        "yaml.full_load",

        # XML operations
        "etree.parse",
        "etree.fromstring",
        "xml.parse",
        "ElementTree.parse",

        # Environment variables
        "os.getenv",
        "os.environ.get",
        "environ.get",
    ]),
    # Database category REMOVED - internal database data is trusted, not a taint source

    # Rust sources - Web frameworks, CLI, and network input
    "rust": frozenset([
        # Standard library input sources
        "std::io::stdin",
        "io::stdin",
        "stdin",
        "Stdin::read_line",
        "std::env::args",
        "env::args",
        "std::env::vars",
        "env::vars",
        "std::env::var",
        "env::var",

        # File I/O sources
        "std::fs::read",
        "std::fs::read_to_string",
        "fs::read",
        "fs::read_to_string",
        "File::open",
        "BufReader::read_line",

        # Network sources
        "TcpStream::read",
        "UdpSocket::recv",
        "UdpSocket::recv_from",

        # actix-web framework
        "HttpRequest::body",
        "HttpRequest::query_string",
        "HttpRequest::match_info",
        "HttpRequest::headers",
        "HttpRequest::cookie",
        "web::Query",
        "web::Json",
        "web::Form",
        "web::Path",

        # Rocket framework
        "rocket::request::Form",
        "rocket::request::Query",
        "rocket::Data",
        "Request::headers",
        "Request::cookies",

        # Axum framework
        "axum::extract::Query",
        "axum::extract::Json",
        "axum::extract::Form",
        "axum::extract::Path",
        "axum::body::Body",
        "Request::body",

        # Warp framework
        "warp::body::json",
        "warp::body::form",
        "warp::query",
        "warp::path",

        # Hyper (low-level HTTP)
        "hyper::Body",
        "Request::body",

        # Serde JSON parsing (commonly used with HTTP)
        "serde_json::from_str",
        "serde_json::from_slice",
        "serde_json::from_reader",
    ]),
    # GraphQL sources - Resolver arguments and field inputs
    "graphql": frozenset([
        # Resolver function arguments (untrusted client input)
        "args",  # GraphQL field arguments
        "parent",  # Parent resolver return value
        "context",  # Request context (may contain auth, headers, etc.)
        "info",  # GraphQL execution info

        # Python GraphQL frameworks
        "resolve_args",  # Graphene
        "obj",  # Graphene parent object
        "info.context",  # Graphene context access
        "root",  # Ariadne parent object
        "value",  # Strawberry parent object

        # JavaScript/TypeScript GraphQL frameworks
        "args.",  # Apollo resolver args access
        "context.",  # Apollo context access
        "parent.",  # Apollo parent access
        "@Args",  # NestJS decorator
        "@Context",  # NestJS decorator
        "@Root",  # Type-GraphQL decorator
        "@Arg",  # Type-GraphQL decorator
        "@Ctx",  # Type-GraphQL decorator
    ])
}

# Define sanitizers that clean/validate data for different vulnerability types
# PERFORMANCE: frozensets provide O(1) membership testing
SANITIZERS = {
    # SQL sanitizers - Functions that properly escape or parameterize queries
    "sql": frozenset([
        "escape_string",
        "mysql_real_escape_string",
        "mysqli_real_escape_string",
        "pg_escape_string",
        "sqlite3.escape_string",
        "sqlalchemy.text",
        "db.prepare",
        "parameterize",
        "prepared_statement",
        "bind_param",
        "execute_prepared",
        "psycopg2.sql.SQL",
        "psycopg2.sql.Identifier",
        "psycopg2.sql.Literal",
        # Rust SQL sanitizers (parameterized queries)
        "diesel::insert_into",
        "diesel::update",
        "diesel::delete",
        "diesel::dsl::insert_into",
        "sqlx::query",  # Safe when used with parameterized queries
        "sqlx::query_as",
        "postgres::Statement::query",  # Prepared statements
        "rusqlite::Statement::query",  # Prepared statements
    ]),
    # XSS sanitizers - HTML escaping functions
    "xss": frozenset([
        "escape_html",
        "html.escape",
        "cgi.escape",
        "markupsafe.escape",
        "DOMPurify.sanitize",
        "bleach.clean",
        "strip_tags",
        "sanitize_html",
        "escape_javascript",
        "json.dumps",  # When used for JSON encoding
        "JSON.stringify",
        "encodeURIComponent",
        "encodeURI",
        "_.escape",  # Lodash escape
        "escapeHtml",
        "htmlspecialchars",
        "htmlentities",
    ]),
    # Path traversal sanitizers
    "path": frozenset([
        "os.path.basename",
        "Path.basename",
        "secure_filename",
        "sanitize_filename",
        "normalize_path",
        "realpath",
        "abspath",
        "path.resolve",
        "path.normalize",
        "werkzeug.utils.secure_filename",
        # Rust path sanitizers
        "Path::canonicalize",
        "std::fs::canonicalize",
        "Path::file_name",
        "Path::components",
    ]),
    # Command injection sanitizers
    "command": frozenset([
        "shlex.quote",
        "pipes.quote",
        "escapeshellarg",
        "escapeshellcmd",
        "shell_escape",
        "quote",
        "escape_shell",
    ]),
    # General validation functions + modern framework patterns
    "validation": frozenset([
        # Generic validation patterns (existing)
        "validate",
        "validator",
        "is_valid",
        "check_input",
        "sanitize",
        "clean",
        "filter_var",
        "assert_valid",
        "verify",

        # Zod (TypeScript schema validation - popular in Next.js, tRPC)
        ".parse",           # schema.parse(data) - throws on invalid
        ".parseAsync",      # schema.parseAsync(data) - async validation
        ".safeParse",       # schema.safeParse(data) - returns result object
        "z.parse",          # z.string().parse(data) - direct Zod call
        "schema.parse",     # Explicit schema reference

        # Joi (Node.js validation - Hapi ecosystem)
        ".validateAsync",   # schema.validateAsync(data)
        "Joi.validate",     # Joi.object().validate(data)
        "schema.validate",  # Explicit schema reference

        # Yup (React form validation - Formik integration)
        "yup.validate",     # yup.string().validate(data)
        "yup.validateSync", # yup.object().validateSync(data)
        "schema.validateSync", # Explicit schema reference
        ".isValid",         # schema.isValid(data)

        # express-validator (Express middleware)
        "validationResult", # validationResult(req) - extracts validation errors
        "matchedData",      # matchedData(req) - extracts validated data only
        "checkSchema",      # checkSchema(schema) - schema-based validation

        # class-validator (NestJS/TypeORM ecosystems)
        "validateSync",     # validateSync(object) - synchronous validation
        "validateOrReject", # validateOrReject(object) - async, throws on error

        # AJV (JSON Schema validator - high performance)
        "ajv.validate",     # ajv.compile(schema); validate(data)
        "ajv.compile",      # Compiles schema for validation
        "validator.validate" # validator(data) - compiled validator function
    ])
}

# Define security sinks (functions where external data flows are tracked)
# Categories are for organizational purposes only - Truth Couriers don't classify vulnerabilities
# PERFORMANCE: frozensets provide O(1) membership testing
SECURITY_SINKS = {
    # SQL-related sinks (factual: functions that interact with databases)
    "sql": frozenset([
        "db.query",
        "db.execute",
        "db.exec",
        "db.raw",
        "cursor.execute",
        "connection.execute",
        # REMOVED "query" - too broad, matches inside "req.query" source
        # REMOVED "execute" - too broad, use qualified patterns instead
        "executemany",
        "rawQuery",
        "knex.raw",
        "sequelize.query",
        "mongoose.find",
        "collection.find",
        # Async Python ORMs
        "asyncpg.execute",
        "asyncpg.executemany",
        "asyncpg.fetch",
        "asyncpg.fetchrow",
        "asyncpg.fetchval",
        "tortoise.execute_query",
        "tortoise.execute_sql",
        "databases.execute",
        "databases.fetch_all",
        "databases.fetch_one",
        # Modern JS ORMs
        "prisma.$queryRaw",
        "prisma.$executeRaw",
        "prisma.$queryRawUnsafe",
        "prisma.$executeRawUnsafe",
        "typeorm.query",
        "typeorm.createQueryBuilder",
        "objection.raw",
        "knex.raw",
        "destroy",
        # Rust SQL sinks (raw/unsafe query functions)
        "diesel::sql_query",
        "diesel::dsl::sql",
        "sqlx::query_unchecked",
        "sqlx::raw_sql",
        "postgres::Client::execute",
        "postgres::Client::query",
        "rusqlite::Connection::execute",
        "rusqlite::Connection::query_row",
    ]),
    # Command execution sinks (factual: functions that execute system commands)
    "command": frozenset([
        "os.system",
        "os.popen",
        "subprocess.run",
        "subprocess.call",
        "subprocess.Popen",
        "subprocess.check_call",
        "subprocess.check_output",
        "exec",
        "eval",
        "child_process.exec",
        "child_process.spawn",
        "child_process.execFile",
        "shell.exec",
        # Rust command execution sinks
        "std::process::Command",
        "Command::new",
        "Command::spawn",
        "Command::output",
        "Command::status",
        "process::Command",
    ]),
    # HTML/Response output sinks (factual: functions that output to HTML/HTTP responses)
    "xss": frozenset([
        "innerHTML",
        "outerHTML",
        "document.write",
        "document.writeln",
        "dangerouslySetInnerHTML",
        "insertAdjacentHTML",
        "response.write",
        "res.send",
        "res.write",
        "res.end",
        "res.sendStatus",
        "res.sendFile",
        "res.render",
        "res.json",
        # Rust HTTP response sinks
        "HttpResponse::body",
        "HttpResponse::html",
        "Response::body",
        "warp::reply::html",
        "rocket::response::content::Html",
    ]),
    # File system operation sinks (factual: functions that interact with file system)
    "path": frozenset([
        "fs.readFile",
        "fs.readFileSync",
        "fs.writeFile",
        "fs.writeFileSync",
        "fs.createReadStream",
        "fs.createWriteStream",
        "open",
        "file.open",
        "Path.join",
        "path.join",
        "os.path.join",
        # Rust file system sinks
        "std::fs::read",
        "std::fs::read_to_string",
        "std::fs::write",
        "std::fs::create_dir",
        "std::fs::remove_file",
        "std::fs::remove_dir",
        "File::open",
        "File::create",
        "OpenOptions::open",
    ]),
    # LDAP injection sinks
    "ldap": frozenset([
        "ldap.search",
        "ldap.bind",
        "ldap.modify",
        "ldap.add",
        "ldap.delete",
    ]),
    # NoSQL injection sinks
    "nosql": frozenset([
        "$where",
        "$regex",
        "collection.find",
        "collection.findOne",
        "collection.update",
        "collection.remove",
        "collection.aggregate",
    ]),
    # Dynamic dispatch / Object injection sinks (NEW - v1.2)
    # Factual: member expressions and function calls where user input controls dispatch
    # Patterns: obj[userInput], handlers[req.query.action](), routes[key]
    # Vulnerability types: Prototype pollution, mass assignment, arbitrary function execution
    "dynamic_dispatch": frozenset([
        # Member expression patterns (bracket notation with tainted key)
        "member_expression",  # Generic AST pattern for obj[key]
        "computed_member_expression",  # Explicit computed property access

        # Call expression patterns (tainted callee)
        "dynamic_call",  # Generic pattern for variable()
        "dynamic_invoke",  # Method invocation with tainted reference

        # Common vulnerable patterns in web frameworks
        "handlers[",  # Route handlers accessed dynamically
        "routes[",    # Route maps accessed by user input
        "actions[",   # Action dispatchers
        "commands[",  # Command maps
        "methods[",   # Method maps
        "services[",  # Service locators
        "controllers[",  # Controller dispatch

        # Prototype access (JavaScript prototype pollution)
        "__proto__",
        "prototype",
        "constructor",

        # Python dynamic attribute access
        "getattr",
        "setattr",
        "hasattr",
        "__getattribute__",
        "__getitem__",
        "__setitem__",
    ]),

    # Rust unsafe memory operations (NEW - v1.1 Rust support)
    # Factual: operations that bypass Rust's safety guarantees
    # Vulnerability types: memory corruption, use-after-free, null pointer dereference
    "unsafe": frozenset([
        # Unsafe block marker
        "unsafe",

        # Raw pointer operations
        "ptr::read",
        "ptr::write",
        "ptr::copy",
        "ptr::copy_nonoverlapping",
        "ptr::swap",
        "ptr::replace",
        "ptr::offset",
        "ptr::add",
        "ptr::sub",
        "ptr::offset_from",
        "ptr::read_volatile",
        "ptr::write_volatile",
        "ptr::read_unaligned",
        "ptr::write_unaligned",

        # Type transmutation
        "mem::transmute",
        "mem::transmute_copy",
        "std::mem::transmute",

        # Uninitialized memory
        "mem::uninitialized",
        "mem::zeroed",
        "MaybeUninit::uninit",
        "MaybeUninit::assume_init",

        # Raw slice/array operations
        "slice::from_raw_parts",
        "slice::from_raw_parts_mut",
        "std::slice::from_raw_parts",

        # Manual memory management
        "alloc::alloc",
        "alloc::dealloc",
        "alloc::realloc",
        "Box::from_raw",
        "Box::into_raw",

        # Foreign function interface
        "extern",
        "extern \"C\"",
    ])
}
