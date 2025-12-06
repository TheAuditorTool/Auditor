const express = require("express");
const app = express();

const handlers = {
  create: createUser,
  update: updateUser,
  delete: deleteUser,
};

app.post("/action", (req, res) => {
  const action = req.query.action;
  const handler = handlers[action];
  handler(req.body);
});

function createUser(data) {
  const query = `INSERT INTO users VALUES ('${data.name}')`;
  db.execute(query);
}

function updateUser(data) {
  db.query("UPDATE users SET name = '" + data.name + "'");
}

function deleteUser(data) {
  db.query(`DELETE FROM users WHERE id = ${data.id}`);
}

const actions = {
  login,
  register,
  logout,
};

app.post("/auth", (req, res) => {
  const cmd = req.body.command;
  const fn = actions[cmd];
  fn(req.body);
});

function login(credentials) {
  const sql = `SELECT * FROM users WHERE username='${credentials.user}'`;
  return db.query(sql);
}

function register(userData) {
  eval(`user = ${JSON.stringify(userData)}`);
}

function logout(session) {
  db.execute("DELETE FROM sessions WHERE id=" + session.id);
}

const routes = {
  api: {
    users: {
      get: getUsers,
      post: createUser,
    },
    posts: {
      get: getPosts,
    },
  },
};

app.all("/api/:resource/:method", (req, res) => {
  const resource = req.params.resource;
  const method = req.params.method;
  const handler = routes.api[resource][method];
  handler(req.body, res);
});

function getUsers(params, res) {
  const query = `SELECT * FROM users WHERE role='${params.role}'`;
  res.send(db.query(query));
}

function getPosts(params, res) {
  res.send(db.query("SELECT * FROM posts WHERE author=" + params.author));
}

const safeHandlers = {
  validate: validateInput,
  sanitize: sanitizeInput,
};

app.post("/safe", (req, res) => {
  const op = req.query.op;
  const handler = safeHandlers[op];
  const clean = handler(req.body);
  db.query(`INSERT INTO logs VALUES ('${clean}')`);
});

function validateInput(data) {
  if (/^[a-zA-Z0-9]+$/.test(data.value)) {
    return data.value;
  }
  throw new Error("Invalid input");
}

function sanitizeInput(data) {
  return data.value.replace(/[^a-zA-Z0-9]/g, "");
}
