/**
 * Test resolveSQLLiteral function standalone
 */

function resolveSQLLiteral(argExpr) {
    const trimmed = argExpr.trim();

    // Plain string (single or double quotes)
    if ((trimmed.startsWith('"') && trimmed.endsWith('"')) ||
        (trimmed.startsWith("'") && trimmed.endsWith("'"))) {
        return trimmed.slice(1, -1);
    }

    // Template literal
    if (trimmed.startsWith('`') && trimmed.endsWith('`')) {
        // Check for interpolation
        if (trimmed.includes('${')) {
            // Dynamic interpolation - can't analyze
            return null;
        }

        // Static template literal - unescape and return
        let unescaped = trimmed.slice(1, -1);  // Remove backticks
        unescaped = unescaped.replace(/\\`/g, '`').replace(/\\\\/g, '\\');
        return unescaped;
    }

    // Complex expression (variable, concatenation, etc.) - can't analyze
    return null;
}

// Test cases
const testCases = [
    { input: '"SELECT * FROM users"', expected: 'SELECT * FROM users' },
    { input: "'SELECT * FROM users'", expected: 'SELECT * FROM users' },
    { input: '`SELECT * FROM users`', expected: 'SELECT * FROM users' },
    { input: '`SELECT * FROM ${table}`', expected: null },
    { input: '`\n      ALTER TABLE users\n      ADD CONSTRAINT...\n    `', expected: '\n      ALTER TABLE users\n      ADD CONSTRAINT...\n    ' },
];

console.log('Testing resolveSQLLiteral():\n');
for (const { input, expected } of testCases) {
    const result = resolveSQLLiteral(input);
    const pass = result === expected;
    const status = pass ? 'PASS' : 'FAIL';
    console.log(`[${status}] ${input.substring(0, 50)}...`);
    if (!pass) {
        console.log(`  Expected: ${expected}`);
        console.log(`  Got: ${result}`);
    }
}
