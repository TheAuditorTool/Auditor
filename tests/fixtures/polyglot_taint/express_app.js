/**
 * Express.js Taint Test Fixture
 *
 * Source: req.body (user input)
 * Sink: eval() (code execution)
 *
 * Expected: Taint flow detected from req.body -> eval
 */

const express = require('express');
const app = express();

app.use(express.json());

// VULNERABLE: req.body flows directly to eval
app.post('/execute', (req, res) => {
    const userCode = req.body.code;
    const result = eval(userCode);  // SINK: Code injection
    res.json({ result });
});

// VULNERABLE: req.params flows to database query (SQL injection)
app.get('/user/:id', (req, res) => {
    const userId = req.params.id;
    const query = `SELECT * FROM users WHERE id = ${userId}`;  // SINK: SQL injection
    // db.query(query);
    res.json({ query });
});

// VULNERABLE: req.query flows to system command
app.get('/ping', (req, res) => {
    const host = req.query.host;
    const cmd = `ping ${host}`;  // SINK: Command injection
    // exec(cmd);
    res.json({ cmd });
});

module.exports = app;
