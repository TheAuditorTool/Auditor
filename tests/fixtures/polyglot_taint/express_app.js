const express = require("express");
const app = express();

app.use(express.json());

app.post("/execute", (req, res) => {
  const userCode = req.body.code;
  const result = eval(userCode);
  res.json({ result });
});

app.get("/user/:id", (req, res) => {
  const userId = req.params.id;
  const query = `SELECT * FROM users WHERE id = ${userId}`;
  res.json({ query });
});

app.get("/ping", (req, res) => {
  const host = req.query.host;
  const cmd = `ping ${host}`;
  res.json({ cmd });
});

module.exports = app;
