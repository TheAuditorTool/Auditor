// Package vulnerable demonstrates security anti-patterns for testing security rules.
package vulnerable

import (
	"crypto/md5"
	"crypto/sha1"
	"crypto/tls"
	"database/sql"
	"fmt"
	"html/template"
	"math/rand"
	"os"
	"os/exec"
	"path/filepath"
)

// Hardcoded secrets - SECURITY ISSUE
const (
	APIKey      = "sk_live_1234567890abcdef"
	SecretToken = "super_secret_token_12345"
	Password    = "admin123"
)

// Package-level secret variable
var DatabasePassword = "production_password_123"

// SQLInjection demonstrates SQL injection vulnerability
func SQLInjection(db *sql.DB, userInput string) error {
	// BAD: String concatenation in SQL query
	query := fmt.Sprintf("SELECT * FROM users WHERE name = '%s'", userInput)
	_, err := db.Query(query)
	return err
}

// SQLInjectionSprintfWhere demonstrates another SQL injection pattern
func SQLInjectionSprintfWhere(db *sql.DB, field, value string) error {
	// BAD: fmt.Sprintf with user input in WHERE clause
	query := fmt.Sprintf("SELECT * FROM products WHERE %s = '%s'", field, value)
	_, err := db.Exec(query)
	return err
}

// CommandInjection demonstrates command injection vulnerability
func CommandInjection(userInput string) error {
	// BAD: User input directly in exec.Command
	cmd := exec.Command("bash", "-c", "echo "+userInput)
	return cmd.Run()
}

// CommandInjectionVariable demonstrates command injection with variable
func CommandInjectionVariable(cmdName string, args ...string) error {
	// BAD: Command name from variable (not literal)
	cmd := exec.Command(cmdName, args...)
	return cmd.Run()
}

// TemplateInjection demonstrates template injection vulnerability
func TemplateInjection(userInput string) template.HTML {
	// BAD: User input directly to template.HTML (bypasses escaping)
	return template.HTML(userInput)
}

// TemplateJSInjection demonstrates JS template injection
func TemplateJSInjection(userInput string) template.JS {
	// BAD: User input to template.JS
	return template.JS(userInput)
}

// PathTraversal demonstrates path traversal vulnerability
func PathTraversal(c interface{ Param(string) string }) ([]byte, error) {
	// BAD: User input in filepath.Join without sanitization
	filename := c.Param("file")
	path := filepath.Join("/var/data", filename)
	return os.ReadFile(path)
}

// InsecureRandom demonstrates using math/rand for crypto
func InsecureRandom() string {
	// BAD: math/rand for security token generation
	const chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
	token := make([]byte, 32)
	for i := range token {
		token[i] = chars[rand.Intn(len(chars))]
	}
	return string(token)
}

// WeakHashMD5 demonstrates weak hashing with MD5
func WeakHashMD5(password string) []byte {
	// BAD: MD5 for password hashing
	hash := md5.Sum([]byte(password))
	return hash[:]
}

// WeakHashSHA1 demonstrates weak hashing with SHA1
func WeakHashSHA1(password string) []byte {
	// BAD: SHA1 for password hashing
	hash := sha1.Sum([]byte(password))
	return hash[:]
}

// InsecureTLSSkipVerify demonstrates InsecureSkipVerify vulnerability
func InsecureTLSSkipVerify() *tls.Config {
	// BAD: InsecureSkipVerify disables certificate validation
	return &tls.Config{
		InsecureSkipVerify: true,
	}
}

// WeakTLSVersion demonstrates weak TLS version
func WeakTLSVersion() *tls.Config {
	// BAD: TLS 1.0 is deprecated and insecure
	return &tls.Config{
		MinVersion: tls.VersionTLS10,
	}
}

// RaceConditionLoopVar demonstrates captured loop variable race
func RaceConditionLoopVar(items []string) {
	for i, item := range items {
		// BAD: i and item captured in closure - data race!
		go func() {
			fmt.Printf("%d: %s\n", i, item)
		}()
	}
}

// RaceConditionPackageVar demonstrates package-level variable race
var counter int

func RaceConditionPackageVar() {
	// BAD: Accessing package-level variable from goroutine without sync
	go func() {
		counter++
	}()
	go func() {
		counter++
	}()
}

// PanicInLibrary demonstrates panic in non-main package (anti-pattern)
func PanicInLibrary(data interface{}) {
	if data == nil {
		// BAD: Library code should return error, not panic
		panic("data cannot be nil")
	}
}

// TypeAssertionNoPanic demonstrates type assertion without ok check
func TypeAssertionNoPanic(i interface{}) string {
	// BAD: Type assertion without comma-ok - will panic if wrong type
	s := i.(string)
	return s
}
