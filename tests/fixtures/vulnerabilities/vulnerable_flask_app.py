"""
Real-world Flask application with vulnerable dependencies and code patterns.

This fixture is used to test:
1. Vulnerability scanner finds CVEs in dependencies
2. SAST rules find code vulnerabilities (SQL injection, XSS, etc.)
3. FCE correlates dependency CVEs with vulnerable code usage
4. Multi-CWE vulnerabilities link to code patterns
"""

import sqlite3

import yaml
from flask import Flask, render_template_string, request
from PIL import Image

app = Flask(__name__)


@app.route("/user/<user_id>")
def get_user(user_id):
    """
    SQL injection vulnerability - directly interpolates user input.

    This should correlate with Django CVE-2022-28346 which also has CWE-89.
    FCE should link: dependency vuln (Django) -> code vuln (this function) -> symbols using db
    """
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()

    query = f"SELECT * FROM users WHERE id = '{user_id}'"
    cursor.execute(query)

    user = cursor.fetchone()
    conn.close()
    return {"user": user}


@app.route("/search")
def search():
    """
    XSS vulnerability - renders user input directly in template.

    This demonstrates CWE-79 which may correlate with dependency vulns.
    """
    search_term = request.args.get("q", "")

    template = f"<h1>Search results for: {search_term}</h1>"
    return render_template_string(template)


@app.route("/config", methods=["POST"])
def update_config():
    """
    Arbitrary code execution via unsafe YAML loading.

    This directly uses vulnerable PyYAML 5.1 with unsafe load().
    FCE should link: PyYAML CVE -> this function -> unsafe yaml.load call
    """
    config_data = request.data.decode("utf-8")

    config = yaml.load(config_data, Loader=yaml.FullLoader)

    return {"config": config}


@app.route("/upload", methods=["POST"])
def upload_image():
    """
    Image processing vulnerability - Pillow DoS.

    Uses vulnerable Pillow 6.0.0 which has decompression bomb vulnerability.
    FCE should link: Pillow CVE (CWE-400) -> this function -> Image.open usage
    """
    if "file" not in request.files:
        return {"error": "No file"}, 400

    file = request.files["file"]

    img = Image.open(file)
    img.verify()

    return {"width": img.width, "height": img.height}


def init_db():
    """
    Initialize database with vulnerable schema.

    This demonstrates lack of input validation and potential injection points.
    """
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            email TEXT,
            role TEXT DEFAULT 'user'
        )
    """)

    cursor.execute("INSERT INTO users VALUES ('1', 'admin', 'admin@example.com', 'admin')")

    conn.commit()
    conn.close()


SECRET_KEY = "hardcoded-secret-key-12345"
DATABASE_PASSWORD = "admin123"


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
