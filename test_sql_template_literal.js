/**
 * Test JavaScript template literal SQL extraction.
 */
const db = require('./db');

async function testCase1() {
    // Static template literal (should be extracted)
    const users = await db.query(`SELECT * FROM users WHERE active = true`);
}

async function testCase2() {
    // Template literal with interpolation (should be skipped)
    const table = 'users';
    const dynamic = await db.query(`SELECT * FROM ${table}`);
}

async function testCase3() {
    // Plain string (already working) should still be extracted
    const result = await db.execute("SELECT * FROM posts");
}

async function testCase4() {
    // Multi-line template literal without interpolation (should be extracted)
    const query = await db.query(`
        SELECT id, name, email
        FROM users
        WHERE created_at > '2024-01-01'
    `);
}
