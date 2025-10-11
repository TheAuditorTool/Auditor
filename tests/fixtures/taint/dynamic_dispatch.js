// Test fixture: Dynamic dispatch taint flows via object literals
// Expected: Taint analyzer should detect flows through dynamic handlers

const express = require('express');
const app = express();

// Test 1: Direct object literal dispatch (VULNERABLE)
const handlers = {
    create: createUser,
    update: updateUser,
    delete: deleteUser
};

app.post('/action', (req, res) => {
    const action = req.query.action;  // TAINT SOURCE
    const handler = handlers[action];  // Dynamic dispatch
    handler(req.body);                 // TAINT SINK - should be detected
});

function createUser(data) {
    // Vulnerable: uses tainted data in SQL
    const query = `INSERT INTO users VALUES ('${data.name}')`;  // SQL INJECTION
    db.execute(query);
}

function updateUser(data) {
    // Also vulnerable
    db.query("UPDATE users SET name = '" + data.name + "'");
}

function deleteUser(data) {
    db.query(`DELETE FROM users WHERE id = ${data.id}`);
}

// Test 2: Shorthand syntax dispatch (VULNERABLE)
const actions = {
    login,
    register,
    logout
};

app.post('/auth', (req, res) => {
    const cmd = req.body.command;   // TAINT SOURCE
    const fn = actions[cmd];        // Dynamic dispatch
    fn(req.body);                   // TAINT SINK
});

function login(credentials) {
    const sql = `SELECT * FROM users WHERE username='${credentials.user}'`;
    return db.query(sql);
}

function register(userData) {
    eval(`user = ${JSON.stringify(userData)}`);  // CODE INJECTION
}

function logout(session) {
    db.execute("DELETE FROM sessions WHERE id=" + session.id);
}

// Test 3: Nested object dispatch (VULNERABLE)
const routes = {
    api: {
        users: {
            get: getUsers,
            post: createUser
        },
        posts: {
            get: getPosts
        }
    }
};

app.all('/api/:resource/:method', (req, res) => {
    const resource = req.params.resource;  // TAINT SOURCE
    const method = req.params.method;      // TAINT SOURCE
    const handler = routes.api[resource][method];  // Nested dispatch
    handler(req.body, res);                // TAINT SINK
});

function getUsers(params, res) {
    const query = `SELECT * FROM users WHERE role='${params.role}'`;
    res.send(db.query(query));
}

function getPosts(params, res) {
    res.send(db.query("SELECT * FROM posts WHERE author=" + params.author));
}

// Test 4: Safe dispatch (NOT VULNERABLE - sanitized)
const safeHandlers = {
    validate: validateInput,
    sanitize: sanitizeInput
};

app.post('/safe', (req, res) => {
    const op = req.query.op;
    const handler = safeHandlers[op];
    const clean = handler(req.body);  // Sanitized
    db.query(`INSERT INTO logs VALUES ('${clean}')`);  // SAFE
});

function validateInput(data) {
    if (/^[a-zA-Z0-9]+$/.test(data.value)) {
        return data.value;
    }
    throw new Error('Invalid input');
}

function sanitizeInput(data) {
    return data.value.replace(/[^a-zA-Z0-9]/g, '');
}
