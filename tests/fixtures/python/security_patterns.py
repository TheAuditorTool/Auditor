"""
Realistic security patterns - Corporate web application with vulnerabilities.

Real-world user management and reporting system with authentic security issues:
- JWT auth with hardcoded secrets
- User search with SQL injection in admin panel  
- File uploads with path traversal
- Report generation with eval() for calculations
- Password resets with weak crypto
- Admin commands with shell injection
"""
import os, subprocess, jwt, hashlib, bcrypt
from pathlib import Path
from functools import wraps
from Crypto.Cipher import DES

# Auth decorators
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not check_session():
            raise PermissionError()
        return f(*args, **kwargs)
    return wrapper

def admin_only(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not is_admin():
            raise PermissionError()
        return f(*args, **kwargs)
    return wrapper

def permission_required(perm):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not has_permission(perm):
                raise PermissionError()
            return f(*args, **kwargs)
        return wrapper
    return decorator

# JWT with hardcoded secret - VULNERABLE
JWT_SECRET = "production-secret-key-2024"

def create_token(user_id, username, roles):
    payload = {"user_id": user_id, "username": username, "roles": roles}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def verify_token(token):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except:
        return None

# Password hashing - mix of secure and insecure
def hash_password_secure(password):
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode(), salt).decode()

def hash_password_legacy(password):
    # Old system - INSECURE
    return hashlib.md5(password.encode()).hexdigest()

def migrate_password_hash(user_id, old_hash, new_password):
    # Migration from MD5 to bcrypt
    new_hash = hash_password_secure(new_password)
    db.execute(f"UPDATE users SET password='{new_hash}', hash_type='bcrypt' WHERE id={user_id}")

# SQL injection in admin search - VULNERABLE
@admin_only
def search_users_by_name(db, search_term):
    query = f"SELECT * FROM users WHERE name LIKE '%{search_term}%'"
    return db.execute(query)

@admin_only 
def get_user_by_id(db, user_id):
    query = f"SELECT * FROM users WHERE id = {user_id}"
    return db.execute(query)

def find_users_by_email_domain(db, domain):
    # VULNERABLE: user-controlled domain in query
    query = "SELECT email, name FROM users WHERE email LIKE '%" + domain + "'"
    return db.execute(query)

# Path traversal in file operations - VULNERABLE
@login_required
def download_user_file(filename):
    filepath = f"/var/www/uploads/{filename}"
    with open(filepath, 'rb') as f:
        return f.read()

@login_required
def serve_report(report_id, user_path):
    # VULNERABLE: user controls path
    full_path = os.path.join("/var/reports", user_path)
    return Path(full_path).read_bytes()

# Command injection in admin panel - VULNERABLE
@admin_only
def backup_database(db_name, output_path):
    cmd = f"mysqldump {db_name} > {output_path}"
    subprocess.run(cmd, shell=True)

@admin_only
def run_maintenance_script(script_name):
    # VULNERABLE: no validation
    os.system(f"python /opt/scripts/{script_name}")

# Eval in report calculations - VULNERABLE
def calculate_sales_report(formula, data):
    # Users can provide custom formulas
    result = eval(formula, {"data": data, "sum": sum, "len": len})
    return result

def apply_discount_rule(rule_expr, cart_total):
    # VULNERABLE: business rules use eval
    discount = eval(rule_expr)
    return cart_total - discount

# Weak crypto for password resets - VULNERABLE
RESET_KEY = b"reset_secret_key"

def generate_reset_token(user_id):
    cipher = DES.new(RESET_KEY[:8], DES.MODE_ECB)
    padded = str(user_id).encode() + b" " * 8
    return cipher.encrypt(padded[:8]).hex()

def decrypt_reset_token(token):
    cipher = DES.new(RESET_KEY[:8], DES.MODE_ECB)
    return cipher.decrypt(bytes.fromhex(token))

# Helper stubs
def check_session(): return True
def is_admin(): return False  
def has_permission(p): return True
class db:
    @staticmethod
    def execute(q): return []
