import express from 'express';

const app = express();

// INTENTIONAL XSS VULNERABILITY - req.body -> res.send without sanitization
app.post('/api/echo', (req, res) => {
  const userInput = req.body.message;
  res.send(`<h1>You said: ${userInput}</h1>`);
});

// INTENTIONAL SQL INJECTION - req.query -> database query
app.get('/api/search', (req, res) => {
  const searchTerm = req.query.q;
  const query = `SELECT * FROM users WHERE name = '${searchTerm}'`;
  // database.raw(query);
  res.json({ query });
});

// INTENTIONAL PATH TRAVERSAL - req.params -> fs.readFile
app.get('/api/file/:filename', (req, res) => {
  const filename = req.params.filename;
  const filepath = `/uploads/${filename}`;
  // fs.readFileSync(filepath);
  res.send(filepath);
});

app.listen(3000);
