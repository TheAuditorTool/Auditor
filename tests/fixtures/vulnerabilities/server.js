/**
 * Vulnerable Node.js application for testing.
 *
 * Tests:
 * 1. Vulnerability scanner finds CVEs in dependencies (lodash, minimist, marked)
 * 2. SAST finds code vulnerabilities (prototype pollution, XSS, etc.)
 * 3. FCE correlates dependency vulns with code usage
 */

const express = require('express');
const lodash = require('lodash');  // lodash 4.17.19 - CVE-2020-8203 (CWE-1321, CWE-915)
const marked = require('marked');  // marked 0.3.6 - CVE-2022-21681 (CWE-79)
const minimist = require('minimist');  // minimist 1.2.5 - CVE-2021-44906 (CWE-1321)

const app = express();
app.use(express.json());

/**
 * VULNERABLE PATTERN 1: Prototype Pollution via lodash
 * Links to lodash CVE-2020-8203 (CWE-1321, CWE-915)
 */
app.post('/merge-config', (req, res) => {
    const defaultConfig = { theme: 'light', timeout: 5000 };

    // VULNERABLE: lodash.merge allows prototype pollution
    // Should link to CVE-2020-8203 dependency finding
    const merged = lodash.merge(defaultConfig, req.body);

    res.json({ config: merged });
});

/**
 * VULNERABLE PATTERN 2: XSS via marked (markdown rendering)
 * Links to marked CVE-2022-21681 (CWE-79)
 */
app.post('/render-markdown', (req, res) => {
    const { markdown } = req.body;

    // VULNERABLE: marked 0.3.6 has XSS vulnerability
    // Should link to CVE-2022-21681 dependency finding
    const html = marked(markdown);

    res.send(html);  // Direct HTML output (XSS)
});

/**
 * VULNERABLE PATTERN 3: Prototype Pollution via minimist
 * Links to minimist CVE-2021-44906 (CWE-1321)
 */
function parseArgs(args) {
    // VULNERABLE: minimist 1.2.5 allows prototype pollution
    // Should link to CVE-2021-44906 dependency finding
    return minimist(args);
}

app.get('/parse', (req, res) => {
    const args = req.query.args ? req.query.args.split(' ') : [];
    const parsed = parseArgs(args);

    res.json({ parsed });
});

/**
 * VULNERABLE PATTERN 4: SQL Injection (code-level vuln)
 * No direct dependency link, but demonstrates CWE-89 in code
 */
app.get('/user/:id', (req, res) => {
    const userId = req.params.id;

    // VULNERABLE: String concatenation in SQL query
    const query = `SELECT * FROM users WHERE id = '${userId}'`;

    // Note: This is a code vuln, not dependency vuln
    // FCE should find both dependency CWEs and code CWEs
    res.json({ query });
});

/**
 * VULNERABLE PATTERN 5: Hardcoded credentials (CWE-798)
 */
const DB_PASSWORD = 'hardcoded-password-123';
const API_KEY = 'sk-1234567890abcdef';

app.listen(3000, () => {
    console.log('Vulnerable server running on port 3000');
});

module.exports = app;
