//! Taint flow patterns for testing taint analysis
//!
//! This module demonstrates various data flow patterns:
//! - Direct source → sink flows
//! - Multi-hop flows (through multiple functions)
//! - Sanitization patterns
//! - Field access chains
//! - Closure captures
//! - Cross-module flows

use std::collections::HashMap;
use std::fs::{self, File};
use std::io::{self, Read, Write, BufRead, BufReader};
use std::path::Path;
use std::process::Command;

// ============================================================================
// SOURCES - User input, files, environment, network
// ============================================================================

/// Read user input from stdin (TAINT SOURCE)
pub fn read_user_input() -> String {
    let mut input = String::new();
    io::stdin().read_line(&mut input).unwrap_or(0);
    input.trim().to_string()
}

/// Read user input with prompt (TAINT SOURCE)
pub fn prompt_user(message: &str) -> String {
    print!("{}", message);
    io::stdout().flush().ok();
    read_user_input()
}

/// Read environment variable (TAINT SOURCE)
pub fn read_env_var(name: &str) -> Option<String> {
    std::env::var(name).ok()
}

/// Read all environment variables (TAINT SOURCE)
pub fn read_all_env_vars() -> HashMap<String, String> {
    std::env::vars().collect()
}

/// Read file contents (TAINT SOURCE)
pub fn read_file(path: &str) -> io::Result<String> {
    fs::read_to_string(path)
}

/// Read file lines (TAINT SOURCE)
pub fn read_file_lines(path: &str) -> io::Result<Vec<String>> {
    let file = File::open(path)?;
    let reader = BufReader::new(file);
    reader.lines().collect()
}

/// Read command line arguments (TAINT SOURCE)
pub fn read_cli_args() -> Vec<String> {
    std::env::args().collect()
}

/// User input struct (fields are tainted)
#[derive(Debug, Clone)]
pub struct UserInput {
    pub username: String,
    pub password: String,
    pub query: String,
    pub file_path: String,
    pub command: String,
}

impl UserInput {
    /// Read all fields from user (TAINT SOURCE)
    pub fn from_prompts() -> Self {
        Self {
            username: prompt_user("Username: "),
            password: prompt_user("Password: "),
            query: prompt_user("Query: "),
            file_path: prompt_user("File path: "),
            command: prompt_user("Command: "),
        }
    }

    /// Create from environment variables (TAINT SOURCE)
    pub fn from_env() -> Self {
        Self {
            username: read_env_var("APP_USERNAME").unwrap_or_default(),
            password: read_env_var("APP_PASSWORD").unwrap_or_default(),
            query: read_env_var("APP_QUERY").unwrap_or_default(),
            file_path: read_env_var("APP_FILE_PATH").unwrap_or_default(),
            command: read_env_var("APP_COMMAND").unwrap_or_default(),
        }
    }
}

// ============================================================================
// SINKS - Dangerous operations
// ============================================================================

/// Execute shell command (DANGEROUS SINK - Command Injection)
pub fn execute_command(cmd: &str) -> io::Result<String> {
    let output = Command::new("sh")
        .arg("-c")
        .arg(cmd) // SINK: cmd could be tainted
        .output()?;

    Ok(String::from_utf8_lossy(&output.stdout).to_string())
}

/// Execute command with arguments (DANGEROUS SINK)
pub fn execute_with_args(program: &str, args: &[&str]) -> io::Result<String> {
    let output = Command::new(program) // SINK: program could be tainted
        .args(args) // SINK: args could be tainted
        .output()?;

    Ok(String::from_utf8_lossy(&output.stdout).to_string())
}

/// Write to file (DANGEROUS SINK - Path Traversal)
pub fn write_file(path: &str, content: &str) -> io::Result<()> {
    fs::write(path, content) // SINK: path could be tainted (path traversal)
}

/// Delete file (DANGEROUS SINK)
pub fn delete_file(path: &str) -> io::Result<()> {
    fs::remove_file(path) // SINK: path could be tainted
}

/// SQL query execution (DANGEROUS SINK - SQL Injection)
pub fn execute_sql(connection: &str, query: &str) -> Result<Vec<String>, &'static str> {
    // Simulated SQL execution
    println!("Executing on {}: {}", connection, query); // SINK: query could be tainted
    Ok(vec!["result".to_string()])
}

/// Log message (POTENTIAL SINK - Log Injection)
pub fn log_message(level: &str, message: &str) {
    println!("[{}] {}", level, message); // SINK: message could contain control chars
}

/// HTML output (POTENTIAL SINK - XSS)
pub fn render_html(template: &str, data: &str) -> String {
    template.replace("{data}", data) // SINK: data could be tainted
}

// ============================================================================
// DIRECT FLOWS - Tainted data goes directly to sink
// ============================================================================

/// VULNERABLE: Direct command injection
pub fn vulnerable_direct_command() {
    let user_cmd = read_user_input(); // SOURCE
    execute_command(&user_cmd).ok(); // SINK - direct flow
}

/// VULNERABLE: Direct path traversal
pub fn vulnerable_direct_path() {
    let path = read_user_input(); // SOURCE
    let content = read_file(&path).unwrap_or_default(); // SINK - path traversal
    println!("{}", content);
}

/// VULNERABLE: Direct SQL injection
pub fn vulnerable_direct_sql() {
    let query = read_user_input(); // SOURCE
    execute_sql("db://localhost", &query).ok(); // SINK - SQL injection
}

/// VULNERABLE: Environment variable to command
pub fn vulnerable_env_command() {
    if let Some(cmd) = read_env_var("USER_COMMAND") { // SOURCE
        execute_command(&cmd).ok(); // SINK
    }
}

// ============================================================================
// MULTI-HOP FLOWS - Data flows through multiple functions
// ============================================================================

/// Process input through multiple steps
fn step1_receive() -> String {
    read_user_input() // SOURCE
}

fn step2_transform(input: String) -> String {
    input.to_uppercase() // Transformation (doesn't sanitize)
}

fn step3_format(input: String) -> String {
    format!("echo '{}'", input) // Still tainted
}

fn step4_execute(cmd: String) {
    execute_command(&cmd).ok(); // SINK
}

/// VULNERABLE: Multi-hop command injection
pub fn vulnerable_multi_hop() {
    let input = step1_receive();
    let transformed = step2_transform(input);
    let formatted = step3_format(transformed);
    step4_execute(formatted);
}

/// Process through struct fields
pub fn vulnerable_struct_flow() {
    let input = UserInput::from_prompts(); // All fields are tainted

    // Field access chains - each is a taint flow
    execute_command(&input.command).ok(); // SINK via field
    write_file(&input.file_path, "data").ok(); // SINK via field
    execute_sql("db", &input.query).ok(); // SINK via field
}

// ============================================================================
// CLOSURE CAPTURES - Tainted data captured in closures
// ============================================================================

/// VULNERABLE: Closure captures tainted data
pub fn vulnerable_closure_capture() {
    let user_input = read_user_input(); // SOURCE

    let execute = || {
        execute_command(&user_input).ok() // SINK - captured variable
    };

    execute();
}

/// VULNERABLE: Closure as callback
pub fn vulnerable_closure_callback<F>(callback: F)
where
    F: FnOnce(&str),
{
    let input = read_user_input(); // SOURCE
    callback(&input); // Passes tainted data to callback
}

/// VULNERABLE: Calling with dangerous callback
pub fn call_with_dangerous_callback() {
    vulnerable_closure_callback(|data| {
        execute_command(data).ok(); // SINK in callback
    });
}

// ============================================================================
// SANITIZERS - Functions that clean/validate data
// ============================================================================

/// Sanitize input for shell commands
pub fn sanitize_shell_input(input: &str) -> String {
    // Remove dangerous characters
    input
        .chars()
        .filter(|c| c.is_alphanumeric() || *c == ' ' || *c == '-' || *c == '_')
        .collect()
}

/// Sanitize path (prevent traversal)
pub fn sanitize_path(path: &str) -> Option<String> {
    let path = Path::new(path);

    // Reject absolute paths and parent traversal
    if path.is_absolute() {
        return None;
    }

    for component in path.components() {
        if let std::path::Component::ParentDir = component {
            return None;
        }
    }

    Some(path.to_string_lossy().to_string())
}

/// Escape for SQL (simplified)
pub fn escape_sql(input: &str) -> String {
    input.replace('\'', "''").replace('\\', "\\\\")
}

/// Escape for HTML
pub fn escape_html(input: &str) -> String {
    input
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&#x27;")
}

/// Validate is alphanumeric only
pub fn validate_alphanumeric(input: &str) -> bool {
    input.chars().all(|c| c.is_alphanumeric())
}

/// Validate against whitelist
pub fn validate_whitelist(input: &str, allowed: &[&str]) -> bool {
    allowed.contains(&input)
}

// ============================================================================
// SAFE PATTERNS - Properly sanitized flows
// ============================================================================

/// SAFE: Sanitized before shell execution
pub fn safe_sanitized_command() {
    let user_input = read_user_input(); // SOURCE
    let sanitized = sanitize_shell_input(&user_input); // SANITIZER
    execute_command(&format!("echo {}", sanitized)).ok(); // SINK - but sanitized
}

/// SAFE: Path validated before use
pub fn safe_validated_path() {
    let path_input = read_user_input(); // SOURCE

    if let Some(safe_path) = sanitize_path(&path_input) { // SANITIZER
        let full_path = format!("./uploads/{}", safe_path);
        read_file(&full_path).ok(); // SINK - but validated
    } else {
        println!("Invalid path");
    }
}

/// SAFE: SQL escaped
pub fn safe_escaped_sql() {
    let query_param = read_user_input(); // SOURCE
    let escaped = escape_sql(&query_param); // SANITIZER
    let query = format!("SELECT * FROM users WHERE name = '{}'", escaped);
    execute_sql("db", &query).ok(); // SINK - but escaped
}

/// SAFE: HTML escaped
pub fn safe_escaped_html() {
    let user_data = read_user_input(); // SOURCE
    let escaped = escape_html(&user_data); // SANITIZER
    let html = render_html("<div>{data}</div>", &escaped); // SINK - but escaped
    println!("{}", html);
}

/// SAFE: Whitelisted input
pub fn safe_whitelisted() {
    let action = read_user_input(); // SOURCE
    let allowed_actions = ["start", "stop", "restart", "status"];

    if validate_whitelist(&action, &allowed_actions) { // VALIDATOR
        execute_command(&format!("systemctl {}", action)).ok(); // SINK - but validated
    } else {
        println!("Invalid action");
    }
}

// ============================================================================
// CONDITIONAL FLOWS - Flow depends on conditions
// ============================================================================

/// Flow depends on runtime condition
pub fn conditional_flow(is_admin: bool) {
    let input = read_user_input(); // SOURCE

    if is_admin {
        // Admin path - allows execution
        execute_command(&input).ok(); // SINK - only reached if admin
    } else {
        // Regular user path - safe
        println!("Command not allowed: {}", sanitize_shell_input(&input));
    }
}

/// Flow through match expression
pub fn match_flow(mode: &str) {
    let input = read_user_input(); // SOURCE

    match mode {
        "execute" => {
            execute_command(&input).ok(); // SINK
        }
        "log" => {
            log_message("INFO", &input); // Different sink
        }
        "safe" => {
            let safe = sanitize_shell_input(&input);
            println!("{}", safe); // Safe - sanitized
        }
        _ => {}
    }
}

// ============================================================================
// LOOP FLOWS - Data flows through iterations
// ============================================================================

/// Process multiple inputs
pub fn loop_flow() {
    let lines = read_file_lines("commands.txt").unwrap_or_default(); // SOURCE

    for line in lines {
        execute_command(&line).ok(); // SINK - each line flows to sink
    }
}

/// Accumulate tainted data
pub fn accumulate_flow() {
    let mut commands = Vec::new();

    for i in 0..3 {
        let input = prompt_user(&format!("Command {}: ", i)); // SOURCE (multiple)
        commands.push(input);
    }

    // All accumulated data is tainted
    let combined = commands.join(" && ");
    execute_command(&combined).ok(); // SINK
}

// ============================================================================
// PROPAGATION HELPERS - For testing taint propagation rules
// ============================================================================

/// String concatenation propagates taint
pub fn concat_propagation() {
    let tainted = read_user_input(); // SOURCE
    let prefix = "safe_prefix_";
    let combined = format!("{}{}", prefix, tainted); // Combined is tainted
    execute_command(&combined).ok(); // SINK
}

/// Collection operations propagate taint
pub fn collection_propagation() {
    let tainted = read_user_input(); // SOURCE
    let mut vec = vec!["safe1".to_string(), "safe2".to_string()];
    vec.push(tainted); // Vector now contains tainted data

    let joined = vec.join(";");
    execute_command(&joined).ok(); // SINK - taint propagated through collection
}

/// HashMap propagates taint
pub fn hashmap_propagation() {
    let key = read_user_input(); // SOURCE
    let value = read_user_input(); // SOURCE

    let mut map = HashMap::new();
    map.insert(key.clone(), value.clone()); // Both key and value tainted

    // Retrieving still tainted
    if let Some(v) = map.get(&key) {
        execute_command(v).ok(); // SINK
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sanitize_shell_input() {
        assert_eq!(sanitize_shell_input("hello"), "hello");
        assert_eq!(sanitize_shell_input("hello; rm -rf /"), "hello rm -rf ");
        assert_eq!(sanitize_shell_input("$(whoami)"), "whoami");
    }

    #[test]
    fn test_sanitize_path() {
        assert_eq!(sanitize_path("file.txt"), Some("file.txt".to_string()));
        assert_eq!(sanitize_path("../etc/passwd"), None);
        assert_eq!(sanitize_path("/etc/passwd"), None);
        assert_eq!(sanitize_path("subdir/file.txt"), Some("subdir/file.txt".to_string()));
    }

    #[test]
    fn test_escape_sql() {
        assert_eq!(escape_sql("O'Brien"), "O''Brien");
        assert_eq!(escape_sql("test\\value"), "test\\\\value");
    }

    #[test]
    fn test_escape_html() {
        assert_eq!(escape_html("<script>"), "&lt;script&gt;");
        assert_eq!(escape_html("a & b"), "a &amp; b");
    }

    #[test]
    fn test_validate_whitelist() {
        assert!(validate_whitelist("start", &["start", "stop"]));
        assert!(!validate_whitelist("delete", &["start", "stop"]));
    }
}
