"""Rust taint source and sink pattern registration.

Registers Rust-specific patterns for taint analysis:
- Sources: stdin, env, file read, web framework inputs (Actix, Axum, Rocket, Warp)
- Sinks: Command execution, SQL queries, file writes, unsafe pointer operations, network

Pattern Format Notes:
- TaintRegistry uses EXACT string matching against function_call_args.callee_function
- Patterns include BOTH qualified (std::env::var) and unqualified (env::var) forms
- Database stores: Type::method (Command::new), module::function (std::env::var)

This is a PATTERN-ONLY module - analyze() returns empty results.
Actual taint analysis happens via TaintRegistry using these registered patterns.
"""

from theauditor.rules.base import (
    RuleMetadata,
    RuleResult,
    StandardRuleContext,
)
from theauditor.utils.logging import logger

METADATA = RuleMetadata(
    name="rust_injection",
    category="security",
    target_extensions=[".rs"],
    exclude_patterns=["test/", "tests/", "benches/"],
    execution_scope="database",
)


def analyze(context: StandardRuleContext) -> RuleResult:
    """Pattern-only module for taint analysis.

    This rule does not perform direct analysis. Instead, it registers
    source/sink patterns via register_taint_patterns() which are used
    by the taint analysis engine.

    Returns empty RuleResult - actual findings come from taint analysis.
    """
    return RuleResult(findings=[], manifest={"pattern_module": True})


def register_taint_patterns(taint_registry):
    """Register Rust source and sink patterns.

    Called by orchestrator.collect_rule_patterns() after module is discovered
    via find_rust_injection_issues().

    Categories map to TaintRegistry.CATEGORY_TO_VULN_TYPE at taint/core.py:27-47:
    - user_input -> "Unvalidated Input"
    - http_request -> "Unvalidated Input"
    - command -> "Command Injection"
    - sql -> "SQL Injection"
    - path -> "Path Traversal"
    - code_injection -> "Code Injection"
    - ssrf -> "Server-Side Request Forgery (SSRF)"
    """
    source_count = 0
    sink_count = 0

    stdin_sources = [
        "io::stdin",
        "std::io::stdin",
        "std::io::Stdin::read_line",
        "read_user_input",
        "BufReader::new",
    ]
    for pattern in stdin_sources:
        taint_registry.register_source(pattern, "user_input", "rust")
        source_count += 1

    env_sources = [
        "std::env::args",
        "args",
        "std::env::var",
        "env::var",
        "std::env::vars",
        "getenv",
        "read_env_var",
    ]
    for pattern in env_sources:
        taint_registry.register_source(pattern, "user_input", "rust")
        source_count += 1

    file_sources = [
        "std::fs::read_to_string",
        "fs::read_to_string",
        "read_file",
        "read_file_lines",
        "serde_json::from_reader",
    ]
    for pattern in file_sources:
        taint_registry.register_source(pattern, "user_input", "rust")
        source_count += 1

    actix_sources = [
        "Json",
        "web::Json",
        "web::Path",
        "web::Query",
        "web::Form",
        "web::Data",
        "HttpRequest::match_info",
        "HttpRequest::query_string",
    ]
    for pattern in actix_sources:
        taint_registry.register_source(pattern, "http_request", "rust")
        source_count += 1

    axum_sources = [
        "axum::extract::Json",
        "axum::extract::Path",
        "axum::extract::Query",
        "axum::extract::Form",
        "axum::extract::State",
    ]
    for pattern in axum_sources:
        taint_registry.register_source(pattern, "http_request", "rust")
        source_count += 1

    rocket_sources = [
        "rocket::request",
        "rocket::form",
        "rocket::data",
        "rocket::State",
    ]
    for pattern in rocket_sources:
        taint_registry.register_source(pattern, "http_request", "rust")
        source_count += 1

    warp_sources = [
        "warp::body::json",
        "warp::path::param",
        "warp::query",
        "warp::body::form",
    ]
    for pattern in warp_sources:
        taint_registry.register_source(pattern, "http_request", "rust")
        source_count += 1

    command_sinks = [
        "Command::new",
        "execute_command",
        "command",
        "command_line",
        "std::process::Command",
        "std::process::Command::new",
    ]
    for pattern in command_sinks:
        taint_registry.register_sink(pattern, "command", "rust")
        sink_count += 1

    sql_sinks = [
        "sqlx::query",
        "sqlx::query_as",
        "sqlx::query_scalar",
        "execute_sql",
        "diesel::sql_query",
        "diesel::insert_into",
        "diesel::update",
        "diesel::delete",
        "rusqlite::Connection::execute",
        "postgres::Client::execute",
        "tokio_postgres::Client::execute",
    ]
    for pattern in sql_sinks:
        taint_registry.register_sink(pattern, "sql", "rust")
        sink_count += 1

    file_sinks = [
        "std::fs::write",
        "fs::write",
        "write_file",
        "std::fs::File::create",
        "File::create",
        "OpenOptions::open",
    ]
    for pattern in file_sinks:
        taint_registry.register_sink(pattern, "path", "rust")
        sink_count += 1

    unsafe_sinks = [
        "ptr::write",
        "ptr::write_volatile",
        "ptr::read",
        "ptr::read_volatile",
        "std::ptr::write",
        "std::ptr::read",
        "std::mem::transmute",
        "write_unchecked",
        "ptr::copy_nonoverlapping",
    ]
    for pattern in unsafe_sinks:
        taint_registry.register_sink(pattern, "code_injection", "rust")
        sink_count += 1

    network_sinks = [
        "connect",
        "TcpStream::connect",
        "std::net::TcpStream::connect",
        "reqwest::get",
        "reqwest::Client::get",
        "hyper::Client::get",
    ]
    for pattern in network_sinks:
        taint_registry.register_sink(pattern, "ssrf", "rust")
        sink_count += 1

    logger.debug(f"Registered {source_count} Rust source patterns")
    logger.debug(f"Registered {sink_count} Rust sink patterns")
