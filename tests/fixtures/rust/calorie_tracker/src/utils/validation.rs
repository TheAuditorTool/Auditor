//! Input validation utilities.

use crate::{CalorieTrackerError, Result};

/// Validate an email address format
pub fn validate_email(email: &str) -> Result<()> {
    if email.is_empty() {
        return Err(CalorieTrackerError::Validation {
            field: "email".into(),
            message: "Email cannot be empty".into(),
        });
    }

    if email.len() > 254 {
        return Err(CalorieTrackerError::Validation {
            field: "email".into(),
            message: "Email too long (max 254 characters)".into(),
        });
    }

    // Basic format check: must have @ and at least one . after @
    let at_pos = email.find('@').ok_or_else(|| CalorieTrackerError::Validation {
        field: "email".into(),
        message: "Invalid email format: missing @".into(),
    })?;

    let domain = &email[at_pos + 1..];
    if !domain.contains('.') {
        return Err(CalorieTrackerError::Validation {
            field: "email".into(),
            message: "Invalid email format: missing domain".into(),
        });
    }

    let local = &email[..at_pos];
    if local.is_empty() {
        return Err(CalorieTrackerError::Validation {
            field: "email".into(),
            message: "Invalid email format: empty local part".into(),
        });
    }

    // Check for invalid characters
    for c in email.chars() {
        if c.is_whitespace() {
            return Err(CalorieTrackerError::Validation {
                field: "email".into(),
                message: "Email cannot contain whitespace".into(),
            });
        }
    }

    Ok(())
}

/// Validate a username
pub fn validate_username(username: &str) -> Result<()> {
    if username.is_empty() {
        return Err(CalorieTrackerError::Validation {
            field: "username".into(),
            message: "Username cannot be empty".into(),
        });
    }

    if username.len() < 3 {
        return Err(CalorieTrackerError::Validation {
            field: "username".into(),
            message: "Username must be at least 3 characters".into(),
        });
    }

    if username.len() > 32 {
        return Err(CalorieTrackerError::Validation {
            field: "username".into(),
            message: "Username cannot exceed 32 characters".into(),
        });
    }

    // First character must be alphabetic
    if !username.chars().next().unwrap().is_alphabetic() {
        return Err(CalorieTrackerError::Validation {
            field: "username".into(),
            message: "Username must start with a letter".into(),
        });
    }

    // Only alphanumeric and underscore allowed
    for c in username.chars() {
        if !c.is_alphanumeric() && c != '_' {
            return Err(CalorieTrackerError::Validation {
                field: "username".into(),
                message: "Username can only contain letters, numbers, and underscores".into(),
            });
        }
    }

    // Reserved usernames
    let reserved = ["admin", "root", "system", "api", "www", "mail", "ftp", "null"];
    if reserved.contains(&username.to_lowercase().as_str()) {
        return Err(CalorieTrackerError::Validation {
            field: "username".into(),
            message: "This username is reserved".into(),
        });
    }

    Ok(())
}

/// Validate a password meets security requirements
pub fn validate_password(password: &str) -> Result<()> {
    if password.len() < 8 {
        return Err(CalorieTrackerError::Validation {
            field: "password".into(),
            message: "Password must be at least 8 characters".into(),
        });
    }

    if password.len() > 128 {
        return Err(CalorieTrackerError::Validation {
            field: "password".into(),
            message: "Password cannot exceed 128 characters".into(),
        });
    }

    let has_uppercase = password.chars().any(|c| c.is_uppercase());
    let has_lowercase = password.chars().any(|c| c.is_lowercase());
    let has_digit = password.chars().any(|c| c.is_ascii_digit());
    let has_special = password.chars().any(|c| !c.is_alphanumeric());

    if !has_uppercase {
        return Err(CalorieTrackerError::Validation {
            field: "password".into(),
            message: "Password must contain at least one uppercase letter".into(),
        });
    }

    if !has_lowercase {
        return Err(CalorieTrackerError::Validation {
            field: "password".into(),
            message: "Password must contain at least one lowercase letter".into(),
        });
    }

    if !has_digit {
        return Err(CalorieTrackerError::Validation {
            field: "password".into(),
            message: "Password must contain at least one digit".into(),
        });
    }

    if !has_special {
        return Err(CalorieTrackerError::Validation {
            field: "password".into(),
            message: "Password must contain at least one special character".into(),
        });
    }

    // Check for common weak passwords
    let common_passwords = [
        "password", "12345678", "qwerty", "admin", "letmein",
        "welcome", "monkey", "dragon", "master", "password1",
    ];

    let lower = password.to_lowercase();
    for weak in &common_passwords {
        if lower.contains(weak) {
            return Err(CalorieTrackerError::Validation {
                field: "password".into(),
                message: "Password is too common".into(),
            });
        }
    }

    Ok(())
}

/// Sanitize user input by removing potentially dangerous characters
pub fn sanitize_input(input: &str) -> String {
    input
        .chars()
        .filter(|c| {
            // Allow alphanumeric, common punctuation, and spaces
            c.is_alphanumeric()
                || *c == ' '
                || *c == '.'
                || *c == ','
                || *c == '-'
                || *c == '_'
                || *c == '\''
                || *c == '"'
                || *c == '('
                || *c == ')'
        })
        .collect::<String>()
        .trim()
        .to_string()
}

/// Escape HTML entities to prevent XSS
pub fn escape_html(input: &str) -> String {
    let mut output = String::with_capacity(input.len());

    for c in input.chars() {
        match c {
            '<' => output.push_str("&lt;"),
            '>' => output.push_str("&gt;"),
            '&' => output.push_str("&amp;"),
            '"' => output.push_str("&quot;"),
            '\'' => output.push_str("&#x27;"),
            '/' => output.push_str("&#x2F;"),
            _ => output.push(c),
        }
    }

    output
}

/// Truncate a string to a maximum length, adding ellipsis if needed
pub fn truncate(s: &str, max_chars: usize) -> String {
    if s.chars().count() <= max_chars {
        s.to_string()
    } else {
        let truncated: String = s.chars().take(max_chars.saturating_sub(3)).collect();
        format!("{}...", truncated)
    }
}

/// Normalize whitespace (collapse multiple spaces/newlines to single space)
pub fn normalize_whitespace(s: &str) -> String {
    let mut result = String::with_capacity(s.len());
    let mut last_was_whitespace = true; // Start true to trim leading

    for c in s.chars() {
        if c.is_whitespace() {
            if !last_was_whitespace {
                result.push(' ');
            }
            last_was_whitespace = true;
        } else {
            result.push(c);
            last_was_whitespace = false;
        }
    }

    // Trim trailing
    if result.ends_with(' ') {
        result.pop();
    }

    result
}

/// Check if a string looks like it could be SQL injection
pub fn looks_like_sql_injection(s: &str) -> bool {
    let lower = s.to_lowercase();
    let suspicious_patterns = [
        "select ", " from ", " where ", " union ", " drop ",
        " insert ", " update ", " delete ", "--", "/*", "*/",
        "; ", "' or ", "\" or ", "1=1", "1 = 1",
    ];

    suspicious_patterns.iter().any(|p| lower.contains(p))
}

/// Validate that a string is valid UTF-8 and contains no null bytes
pub fn validate_utf8_no_null(s: &str) -> Result<()> {
    // String is already guaranteed UTF-8 in Rust, just check for null bytes
    if s.contains('\0') {
        return Err(CalorieTrackerError::Validation {
            field: "input".into(),
            message: "Input cannot contain null bytes".into(),
        });
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_validate_email_valid() {
        assert!(validate_email("user@example.com").is_ok());
        assert!(validate_email("user.name@example.co.uk").is_ok());
        assert!(validate_email("user+tag@example.com").is_ok());
    }

    #[test]
    fn test_validate_email_invalid() {
        assert!(validate_email("").is_err());
        assert!(validate_email("no-at-sign").is_err());
        assert!(validate_email("@no-local.com").is_err());
        assert!(validate_email("no-domain@").is_err());
        assert!(validate_email("spaces in@email.com").is_err());
    }

    #[test]
    fn test_validate_username_valid() {
        assert!(validate_username("john").is_ok());
        assert!(validate_username("john_doe").is_ok());
        assert!(validate_username("user123").is_ok());
    }

    #[test]
    fn test_validate_username_invalid() {
        assert!(validate_username("").is_err());
        assert!(validate_username("ab").is_err()); // Too short
        assert!(validate_username("123user").is_err()); // Starts with number
        assert!(validate_username("user@name").is_err()); // Invalid char
        assert!(validate_username("admin").is_err()); // Reserved
    }

    #[test]
    fn test_validate_password() {
        assert!(validate_password("Str0ng!Pass").is_ok());
        assert!(validate_password("short").is_err()); // Too short
        assert!(validate_password("nouppercase1!").is_err());
        assert!(validate_password("NOLOWERCASE1!").is_err());
        assert!(validate_password("NoDigits!!").is_err());
        assert!(validate_password("NoSpecial123").is_err());
    }

    #[test]
    fn test_sanitize_input() {
        assert_eq!(sanitize_input("Hello World"), "Hello World");
        assert_eq!(sanitize_input("<script>alert('xss')</script>"), "scriptalertxssscript");
        assert_eq!(sanitize_input("  trim me  "), "trim me");
    }

    #[test]
    fn test_escape_html() {
        assert_eq!(escape_html("<script>"), "&lt;script&gt;");
        assert_eq!(escape_html("a & b"), "a &amp; b");
        assert_eq!(escape_html("\"quoted\""), "&quot;quoted&quot;");
    }

    #[test]
    fn test_truncate() {
        assert_eq!(truncate("hello", 10), "hello");
        assert_eq!(truncate("hello world", 8), "hello...");
    }

    #[test]
    fn test_normalize_whitespace() {
        assert_eq!(normalize_whitespace("  hello   world  "), "hello world");
        assert_eq!(normalize_whitespace("line1\n\nline2"), "line1 line2");
    }

    #[test]
    fn test_sql_injection_detection() {
        assert!(looks_like_sql_injection("'; DROP TABLE users; --"));
        assert!(looks_like_sql_injection("1' OR '1'='1"));
        assert!(!looks_like_sql_injection("normal search query"));
    }

    #[test]
    fn test_utf8_no_null() {
        assert!(validate_utf8_no_null("hello").is_ok());
        assert!(validate_utf8_no_null("hello\0world").is_err());
    }
}
