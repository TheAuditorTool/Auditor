"""
Real-world Flask application with vulnerable dependencies and code patterns.

This fixture is used to test:
1. Vulnerability scanner finds CVEs in dependencies
2. SAST rules find code vulnerabilities (SQL injection, XSS, etc.)
3. FCE correlates dependency CVEs with vulnerable code usage
4. Multi-CWE vulnerabilities link to code patterns
"""

import sqlite3
from flask import Flask, request, render_template_string
import yaml  # PyYAML - has CVE-2020-14343 in version 5.1
from PIL import Image  # Pillow - has CVE-2020-35653 in version 6.0.0


app = Flask(__name__)

# VULNERABLE PATTERN 1: SQL Injection (CWE-89)
# Links to Django CVE-2022-28346 (CWE-89, CWE-1321) from requirements.txt
@app.route('/user/<user_id>')
def get_user(user_id):
    """
    SQL injection vulnerability - directly interpolates user input.

    This should correlate with Django CVE-2022-28346 which also has CWE-89.
    FCE should link: dependency vuln (Django) -> code vuln (this function) -> symbols using db
    """
    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()

    # VULNERABLE: String formatting instead of parameterized query
    query = f"SELECT * FROM users WHERE id = '{user_id}'"
    cursor.execute(query)

    user = cursor.fetchone()
    conn.close()
    return {"user": user}


# VULNERABLE PATTERN 2: XSS via Template Injection (CWE-79)
@app.route('/search')
def search():
    """
    XSS vulnerability - renders user input directly in template.

    This demonstrates CWE-79 which may correlate with dependency vulns.
    """
    search_term = request.args.get('q', '')

    # VULNERABLE: Directly renders user input without escaping
    template = f"<h1>Search results for: {search_term}</h1>"
    return render_template_string(template)


# VULNERABLE PATTERN 3: YAML Deserialization (CWE-20, CWE-94)
# Links to PyYAML CVE-2020-14343 (CWE-20, CWE-94) from requirements.txt
@app.route('/config', methods=['POST'])
def update_config():
    """
    Arbitrary code execution via unsafe YAML loading.

    This directly uses vulnerable PyYAML 5.1 with unsafe load().
    FCE should link: PyYAML CVE -> this function -> unsafe yaml.load call
    """
    config_data = request.data.decode('utf-8')

    # VULNERABLE: Uses full_load on untrusted input (CVE-2020-14343)
    # PyYAML 5.1 has arbitrary code execution vulnerability
    config = yaml.load(config_data, Loader=yaml.FullLoader)

    return {"config": config}


# VULNERABLE PATTERN 4: Image Processing DoS (CWE-400)
# Links to Pillow CVE-2020-35653 (CWE-400) from requirements.txt
@app.route('/upload', methods=['POST'])
def upload_image():
    """
    Image processing vulnerability - Pillow DoS.

    Uses vulnerable Pillow 6.0.0 which has decompression bomb vulnerability.
    FCE should link: Pillow CVE (CWE-400) -> this function -> Image.open usage
    """
    if 'file' not in request.files:
        return {"error": "No file"}, 400

    file = request.files['file']

    # VULNERABLE: Pillow 6.0.0 has CVE-2020-35653 (decompression bomb)
    img = Image.open(file)
    img.verify()

    return {"width": img.width, "height": img.height}


# HELPER FUNCTION: Database initialization (also vulnerable)
def init_db():
    """
    Initialize database with vulnerable schema.

    This demonstrates lack of input validation and potential injection points.
    """
    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()

    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            email TEXT,
            role TEXT DEFAULT 'user'
        )
    ''')

    # VULNERABLE: No input validation, allows special characters
    cursor.execute("INSERT INTO users VALUES ('1', 'admin', 'admin@example.com', 'admin')")

    conn.commit()
    conn.close()


# VULNERABLE PATTERN 5: Hardcoded secret (CWE-798)
SECRET_KEY = "hardcoded-secret-key-12345"  # SAST should flag this
DATABASE_PASSWORD = "admin123"  # SAST should flag this


if __name__ == '__main__':
    init_db()
    app.run(debug=True)  # SAST should flag debug=True in production
