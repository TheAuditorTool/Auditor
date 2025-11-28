const express = require("express");
const lodash = require("lodash");
const marked = require("marked");
const minimist = require("minimist");

const app = express();
app.use(express.json());

app.post("/merge-config", (req, res) => {
  const defaultConfig = { theme: "light", timeout: 5000 };

  const merged = lodash.merge(defaultConfig, req.body);

  res.json({ config: merged });
});

app.post("/render-markdown", (req, res) => {
  const { markdown } = req.body;

  const html = marked(markdown);

  res.send(html);
});

function parseArgs(args) {
  return minimist(args);
}

app.get("/parse", (req, res) => {
  const args = req.query.args ? req.query.args.split(" ") : [];
  const parsed = parseArgs(args);

  res.json({ parsed });
});

app.get("/user/:id", (req, res) => {
  const userId = req.params.id;

  const query = `SELECT * FROM users WHERE id = '${userId}'`;

  res.json({ query });
});

const DB_PASSWORD = "hardcoded-password-123";
const API_KEY = "sk-1234567890abcdef";

app.listen(3000, () => {
  console.log("Vulnerable server running on port 3000");
});

module.exports = app;
