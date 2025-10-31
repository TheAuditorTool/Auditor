# Python Phase 3 - Detailed Pre-Implementation Specifications

**The Sweet Spot: Not high-level bullshit, not copy-paste code, but exact specs you can code from**

---

## EXTRACTOR SPECIFICATIONS

### Flask Block (10 Extractors)

#### Extractor 1: `extract_flask_app_factories`

**Purpose**: Find Flask application factory patterns and direct instantiations

**What to detect**:
1. Functions that create and return Flask instances
2. Module-level Flask() instantiations
3. Configuration methods called on app
4. Blueprint registrations within factories

**Input patterns to find**:
```python
# Pattern 1: Factory function
def create_app(config=None):
    app = Flask(__name__)
    app.config.from_object(config)
    app.register_blueprint(api_bp)
    return app

# Pattern 2: Module-level
app = Flask(__name__)

# Pattern 3: Make function
def make_app():
    return Flask(__name__)
```

**Return format**:
```python
{
    'line': int,                    # Line number where pattern starts
    'factory_name': str,            # Function name or '<module>'
    'app_var': str,                 # Variable name for app instance
    'config_methods': str,          # Comma-separated: 'from_object,from_envvar'
    'blueprint_count': int,         # Number of blueprints registered
    'blueprints': str,              # Comma-separated blueprint names
    'is_factory': bool              # True if function returns app
}
```

**Database schema needed**:
- Table: `python_flask_apps`
- Columns: All fields from return format
- Primary key: (file, line, factory_name)
- Indexes: file, factory_name

**Algorithm approach**:
1. Walk AST for FunctionDef nodes
2. Inside each function, look for `Flask()` calls assigned to variables
3. Track that variable name
4. Look for method calls on that variable (.config.*, .register_blueprint)
5. Check if function returns that variable
6. Also scan module level for Flask() assignments

**Test cases**:
- Factory with config and blueprints
- Simple factory with just return
- Module-level app
- Multiple apps in one file
- Factory that doesn't return (sets global)

---

#### Extractor 2: `extract_flask_extensions`

**Purpose**: Find Flask extension usage and initialization patterns

**What to detect**:
1. Known extension class instantiations (SQLAlchemy, LoginManager, etc.)
2. init_app() pattern for lazy initialization
3. Extensions initialized with app vs without

**Known extensions to track**:
- SQLAlchemy (flask-sqlalchemy)
- LoginManager (flask-login)
- Mail (flask-mail)
- Migrate (flask-migrate)
- CORS (flask-cors)
- JWT (flask-jwt-extended)
- Bcrypt (flask-bcrypt)
- SocketIO (flask-socketio)
- Cache (flask-caching)
- Limiter (flask-limiter)

**Input patterns to find**:
```python
# Pattern 1: Direct initialization
db = SQLAlchemy(app)

# Pattern 2: Lazy initialization
login = LoginManager()
login.init_app(app)

# Pattern 3: With config
cache = Cache(app, config={'CACHE_TYPE': 'simple'})
```

**Return format**:
```python
{
    'line': int,
    'extension_type': str,     # 'flask-sqlalchemy', 'flask-login', etc.
    'class_name': str,         # 'SQLAlchemy', 'LoginManager'
    'app_arg': str,            # App variable if passed to constructor
    'has_config': bool         # True if config kwargs present
}
```

**Database schema needed**:
- Table: `python_flask_extensions`
- Columns: All fields from return format
- Primary key: (file, line, extension_type)
- Indexes: file, extension_type

**Algorithm approach**:
1. Create dict mapping class names to extension types
2. Walk AST for Call nodes
3. Check if function name matches known extensions
4. Check if first arg is app variable
5. Check for init_app calls (attribute.method pattern)

---

#### Extractor 3: `extract_flask_request_hooks`

**Purpose**: Find Flask request lifecycle hooks

**Hook types to detect**:
- before_request
- after_request
- before_first_request (deprecated but still used)
- teardown_request
- teardown_appcontext
- context_processor
- url_defaults
- url_value_preprocessor

**Input patterns to find**:
```python
@app.before_request
def check_auth():
    pass

@app.after_request
def add_headers(response):
    return response

@blueprint.before_request
def blueprint_hook():
    pass
```

**Return format**:
```python
{
    'line': int,
    'hook_type': str,           # 'before_request', 'after_request', etc.
    'function_name': str,
    'app_instance': str,        # 'app', 'blueprint', variable name
    'accepts_response': bool,   # True for after_request
    'accepts_error': bool       # True for teardown_*
}
```

**Database schema needed**:
- Table: `python_flask_hooks`
- Columns: All fields from return format
- Primary key: (file, line, function_name)
- Indexes: file, hook_type

---

#### Extractor 4: `extract_flask_error_handlers`

**Purpose**: Find error handler registrations

**Patterns to detect**:
```python
@app.errorhandler(404)
@app.errorhandler(Exception)
app.register_error_handler(500, handler)
```

**Return format**:
```python
{
    'line': int,
    'handler_function': str,
    'error_spec': str,          # '404', 'Exception', 'ValueError'
    'app_instance': str,
    'is_http_code': bool        # True if numeric HTTP code
}
```

---

#### Extractor 5: `extract_flask_template_filters`

**Purpose**: Find Jinja2 custom filters and tests

**Patterns to detect**:
```python
@app.template_filter('currency')
def format_currency(value):
    pass

@app.template_test('prime')
def is_prime(n):
    pass

app.jinja_env.filters['custom'] = my_filter
```

**Return format**:
```python
{
    'line': int,
    'filter_name': str,
    'function_name': str,
    'filter_type': str,         # 'filter' or 'test'
    'app_instance': str
}
```

---

#### Extractor 6: `extract_flask_cli_commands`

**Purpose**: Find Click CLI commands for Flask

**Patterns to detect**:
```python
@app.cli.command()
@click.option('--name')
def init_db(name):
    pass

@app.cli.group()
def database():
    pass
```

**Return format**:
```python
{
    'line': int,
    'command_name': str,
    'function_name': str,
    'is_group': bool,
    'option_count': int,
    'app_instance': str
}
```

---

#### Extractor 7: `extract_flask_websocket_handlers`

**Purpose**: Find Flask-SocketIO event handlers

**Patterns to detect**:
```python
@socketio.on('connect')
def handle_connect():
    pass

@socketio.on('message', namespace='/chat')
def handle_message(data):
    pass
```

**Return format**:
```python
{
    'line': int,
    'event_name': str,          # 'connect', 'message', 'disconnect'
    'handler_function': str,
    'namespace': str,           # '/chat' or None
    'has_data_param': bool
}
```

---

#### Extractor 8: `extract_flask_cors_configs`

**Purpose**: Find CORS configuration patterns

**Patterns to detect**:
```python
CORS(app)
CORS(app, origins=['http://localhost:3000'])
cors = CORS()
cors.init_app(app, resources={r"/api/*": {"origins": "*"}})
```

**Return format**:
```python
{
    'line': int,
    'app_instance': str,
    'has_origins': bool,
    'has_resources': bool,
    'is_lazy': bool             # True if init_app pattern
}
```

---

#### Extractor 9: `extract_flask_rate_limits`

**Purpose**: Find Flask-Limiter rate limiting decorators

**Patterns to detect**:
```python
@limiter.limit("10 per minute")
def slow_endpoint():
    pass

@limiter.limit("1/second", error_message='Too many requests')
def rate_limited():
    pass
```

**Return format**:
```python
{
    'line': int,
    'limit_spec': str,          # "10 per minute", "1/second"
    'function_name': str,
    'has_error_message': bool,
    'limiter_instance': str
}
```

---

#### Extractor 10: `extract_flask_cache_decorators`

**Purpose**: Find Flask-Caching usage

**Patterns to detect**:
```python
@cache.cached(timeout=50)
def get_data():
    pass

@cache.memoize(timeout=300)
def expensive_function(a, b):
    pass
```

**Return format**:
```python
{
    'line': int,
    'cache_type': str,          # 'cached', 'memoize'
    'function_name': str,
    'timeout': int,             # Timeout value if specified
    'cache_instance': str
}
```

---

### Testing Block (8 Extractors)

#### Extractor 11: `extract_unittest_testcases`

**Purpose**: Find unittest.TestCase classes and their test methods

**Patterns to detect**:
```python
class TestMyClass(unittest.TestCase):
    def setUp(self):
        pass

    def test_something(self):
        self.assertEqual(1, 1)

    def tearDown(self):
        pass
```

**Return format**:
```python
{
    'line': int,
    'class_name': str,
    'base_class': str,          # 'TestCase' or custom base
    'test_method_count': int,
    'has_setup': bool,
    'has_teardown': bool,
    'has_class_setup': bool     # setUpClass
}
```

---

#### Extractor 12: `extract_test_assertions`

**Purpose**: Find assertion patterns in tests

**Assertion methods to track**:
- assertEqual, assertNotEqual
- assertTrue, assertFalse
- assertIs, assertIsNot
- assertIsNone, assertIsNotNone
- assertIn, assertNotIn
- assertRaises, assertWarns
- assertAlmostEqual
- assertGreater, assertLess

**Return format**:
```python
{
    'line': int,
    'assertion_type': str,      # 'assertEqual', 'assertTrue', etc.
    'in_function': str,         # Test function name
    'in_class': str,           # Test class name if applicable
    'has_message': bool        # Custom assertion message
}
```

---

#### Extractor 13: `extract_pytest_plugins`

**Purpose**: Find pytest plugin hooks and fixtures

**Plugin hooks to detect**:
- pytest_configure
- pytest_collection_modifyitems
- pytest_runtest_setup
- pytest_runtest_teardown
- Custom hooks

**Return format**:
```python
{
    'line': int,
    'hook_name': str,
    'function_name': str,
    'is_fixture': bool,
    'fixture_scope': str,       # 'function', 'class', 'module', 'session'
    'has_autouse': bool
}
```

---

#### Extractor 14: `extract_pytest_conftest`

**Purpose**: Find conftest.py specific patterns

**Patterns to detect**:
- Fixtures defined in conftest
- Shared fixtures
- pytest_addoption
- pytest.ini references

**Return format**:
```python
{
    'line': int,
    'pattern_type': str,        # 'fixture', 'option', 'hook'
    'name': str,
    'scope': str,
    'is_shared': bool           # Used by multiple test files
}
```

---

#### Extractor 15: `extract_hypothesis_strategies`

**Purpose**: Find property-based testing with Hypothesis

**Patterns to detect**:
```python
@given(st.integers(), st.text())
def test_property(x, y):
    pass

@hypothesis.strategies.composite
def my_strategy(draw):
    pass
```

**Return format**:
```python
{
    'line': int,
    'test_function': str,
    'strategy_types': str,      # 'integers,text'
    'is_composite': bool,
    'has_settings': bool        # @settings decorator
}
```

---

#### Extractor 16: `extract_doctest_examples`

**Purpose**: Find doctest patterns in docstrings

**Patterns to detect**:
```python
def add(a, b):
    """
    >>> add(2, 3)
    5
    >>> add('a', 'b')
    'ab'
    """
```

**Return format**:
```python
{
    'line': int,
    'in_function': str,
    'example_count': int,
    'has_expected_output': bool
}
```

---

#### Extractor 17: `extract_test_doubles`

**Purpose**: Find mock/stub/spy patterns

**Patterns to detect**:
```python
@mock.patch('module.function')
def test_with_mock(mock_func):
    pass

with mock.patch.object(MyClass, 'method'):
    pass

mock_obj = MagicMock()
mock_obj.return_value = 42
```

**Return format**:
```python
{
    'line': int,
    'mock_type': str,           # 'patch', 'patch.object', 'MagicMock', 'Mock'
    'target': str,              # What's being mocked
    'in_function': str,
    'has_return_value': bool,
    'has_side_effect': bool
}
```

---

#### Extractor 18: `extract_test_coverage_markers`

**Purpose**: Find coverage control comments

**Patterns to detect**:
```python
# pragma: no cover
# pragma: no branch
# coverage: ignore
```

**Return format**:
```python
{
    'line': int,
    'marker_type': str,         # 'no cover', 'no branch', 'ignore'
    'scope': str                # 'line', 'block', 'function'
}
```

---

### Security Block (8 Extractors)

#### Extractor 19: `extract_auth_decorators`

**Purpose**: Find authentication/authorization decorators

**Patterns to detect**:
```python
@login_required
@permission_required('admin')
@roles_required('user', 'moderator')
@jwt_required
@api_key_required
```

**Return format**:
```python
{
    'line': int,
    'decorator_name': str,
    'function_name': str,
    'required_value': str,      # 'admin', 'user,moderator'
    'auth_type': str            # 'session', 'jwt', 'api_key'
}
```

---

#### Extractor 20: `extract_password_hashing`

**Purpose**: Find password hashing/verification patterns

**Libraries to detect**:
- bcrypt
- argon2
- pbkdf2
- werkzeug.security
- django.contrib.auth.hashers
- hashlib (SHA, MD5 - insecure)

**Patterns to detect**:
```python
bcrypt.hashpw(password, bcrypt.gensalt())
argon2.hash(password)
generate_password_hash(password)
check_password_hash(hash, password)
hashlib.md5(password)  # INSECURE
```

**Return format**:
```python
{
    'line': int,
    'hash_function': str,       # 'bcrypt.hashpw', 'argon2.hash'
    'hash_type': str,           # 'bcrypt', 'argon2', 'md5'
    'is_verification': bool,    # True for check_password_hash
    'is_secure': bool,          # False for MD5, SHA1
    'has_salt': bool
}
```

---

#### Extractor 21: `extract_jwt_operations`

**Purpose**: Find JWT encoding/decoding

**Patterns to detect**:
```python
jwt.encode(payload, secret, algorithm='HS256')
jwt.decode(token, secret, algorithms=['HS256'])
create_access_token(identity=user_id)
```

**Return format**:
```python
{
    'line': int,
    'operation': str,           # 'encode', 'decode', 'create_access_token'
    'has_algorithm': bool,
    'algorithm': str,           # 'HS256', 'RS256'
    'has_expiry': bool,
    'in_function': str
}
```

---

#### Extractor 22: `extract_csrf_protection`

**Purpose**: Find CSRF protection patterns

**Patterns to detect**:
```python
@csrf_exempt
csrf_token = generate_csrf_token()
validate_csrf(token)
WTForms with CSRF
Flask-WTF CSRF
```

**Return format**:
```python
{
    'line': int,
    'pattern_type': str,        # 'exempt', 'generate', 'validate'
    'is_disabled': bool,        # True for @csrf_exempt
    'framework': str            # 'django', 'flask', 'custom'
}
```

---

#### Extractor 23: `extract_sql_queries`

**Purpose**: Find raw SQL queries (injection risk)

**Patterns to detect**:
```python
cursor.execute("SELECT * FROM users WHERE id = " + user_id)  # BAD
cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))  # GOOD
db.execute(f"DELETE FROM {table}")  # BAD
User.objects.raw("SELECT * FROM users")
```

**Return format**:
```python
{
    'line': int,
    'query_method': str,        # 'execute', 'raw', 'executemany'
    'has_parameters': bool,     # True if parameterized
    'uses_string_format': bool, # True if f-string or %
    'uses_concatenation': bool, # True if + operator
    'risk_level': str           # 'high', 'medium', 'low'
}
```

---

#### Extractor 24: `extract_file_operations`

**Purpose**: Find file operations (path traversal risk)

**Patterns to detect**:
```python
open(user_input)
os.path.join(base, user_input)
pathlib.Path(user_input)
send_file(filename)
```

**Return format**:
```python
{
    'line': int,
    'operation': str,           # 'open', 'path.join', 'send_file'
    'has_user_input': bool,     # If variable, not literal
    'has_validation': bool,     # Checks before operation
    'mode': str                 # 'r', 'w', 'rb', etc.
}
```

---

#### Extractor 25: `extract_subprocess_calls`

**Purpose**: Find subprocess execution (command injection risk)

**Patterns to detect**:
```python
subprocess.run(cmd, shell=True)  # DANGEROUS
subprocess.Popen(['ls', '-l'])
os.system(command)  # DANGEROUS
os.popen(command)
```

**Return format**:
```python
{
    'line': int,
    'function': str,            # 'run', 'Popen', 'system'
    'uses_shell': bool,         # shell=True is dangerous
    'command_type': str,        # 'string', 'list'
    'has_user_input': bool
}
```

---

#### Extractor 26: `extract_eval_exec_usage`

**Purpose**: Find eval/exec usage (code injection risk)

**Patterns to detect**:
```python
eval(user_input)
exec(code_string)
compile(source, '<string>', 'exec')
__import__(module_name)
```

**Return format**:
```python
{
    'line': int,
    'function': str,            # 'eval', 'exec', 'compile', '__import__'
    'has_user_input': bool,
    'in_function': str,
    'risk_level': str           # 'critical', 'high'
}
```

---

### Django Signals Block (4 Extractors)

#### Extractor 27: `extract_django_signals`

**Purpose**: Find Django signal definitions and connections

**Built-in signals to track**:
- pre_save, post_save
- pre_delete, post_delete
- m2m_changed
- request_started, request_finished
- Custom signals

**Patterns to detect**:
```python
from django.dispatch import Signal
my_signal = Signal()

@receiver(post_save, sender=User)
def handle_save(sender, instance, **kwargs):
    pass
```

**Return format**:
```python
{
    'line': int,
    'signal_name': str,
    'signal_type': str,         # 'custom', 'pre_save', 'post_save'
    'sender': str,              # Model class if specified
    'receiver_function': str
}
```

---

#### Extractor 28: `extract_django_receivers`

**Purpose**: Find signal receiver decorators and connections

**Return format**:
```python
{
    'line': int,
    'receiver_function': str,
    'signal': str,
    'sender': str,
    'dispatch_uid': str,        # If specified
    'weak': bool                # weak=False for strong reference
}
```

---

#### Extractor 29: `extract_django_custom_managers`

**Purpose**: Find custom Django model managers

**Patterns to detect**:
```python
class PublishedManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(status='published')

class Article(models.Model):
    objects = models.Manager()
    published = PublishedManager()
```

**Return format**:
```python
{
    'line': int,
    'manager_class': str,
    'model_class': str,         # Model using this manager
    'attribute_name': str,      # 'published', 'objects'
    'has_get_queryset': bool,
    'custom_methods': str       # Comma-separated method names
}
```

---

#### Extractor 30: `extract_django_querysets`

**Purpose**: Find QuerySet method chains and optimizations

**Patterns to detect**:
```python
User.objects.filter(active=True).select_related('profile')
Article.objects.prefetch_related('comments')
qs.only('id', 'title')
qs.defer('content')
```

**Return format**:
```python
{
    'line': int,
    'model': str,
    'methods': str,             # 'filter,select_related'
    'has_select_related': bool,
    'has_prefetch_related': bool,
    'has_only': bool,
    'has_defer': bool,
    'in_function': str
}
```

---

## DATABASE SCHEMA SQL

```sql
-- Flask tables
CREATE TABLE python_flask_apps (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    factory_name TEXT NOT NULL,
    app_var TEXT,
    config_methods TEXT,
    blueprint_count INTEGER DEFAULT 0,
    blueprints TEXT,
    is_factory BOOLEAN DEFAULT 0,
    PRIMARY KEY (file, line, factory_name)
);
CREATE INDEX idx_python_flask_apps_file ON python_flask_apps(file);

-- Testing tables
CREATE TABLE python_unittest_cases (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    class_name TEXT NOT NULL,
    base_class TEXT,
    test_method_count INTEGER DEFAULT 0,
    has_setup BOOLEAN DEFAULT 0,
    has_teardown BOOLEAN DEFAULT 0,
    has_class_setup BOOLEAN DEFAULT 0,
    PRIMARY KEY (file, line, class_name)
);

-- Security tables
CREATE TABLE python_auth_patterns (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    decorator_name TEXT NOT NULL,
    function_name TEXT NOT NULL,
    required_value TEXT,
    auth_type TEXT,
    PRIMARY KEY (file, line, function_name)
);

-- Django tables
CREATE TABLE python_django_signals (
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    signal_name TEXT NOT NULL,
    signal_type TEXT,
    sender TEXT,
    receiver_function TEXT,
    PRIMARY KEY (file, line, signal_name)
);
```

---

## INTEGRATION POINTS

### Where to add in python.py
- Line ~107: Add result keys in dictionary
- Line ~295: Call extractors after existing ones

### Where to add in storage.py
- Line ~78: Register handlers in field_handlers dict
- Line ~870: Add storage methods after existing ones

### Where to add in python_database.py
- Line ~500: Add database writer methods

### Where to add in python_schema.py
- Line ~700: Add TableSchema definitions
- Line ~900: Register in PYTHON_TABLES dict

---

## TEST SPECIFICATIONS

For each extractor, create test with:

1. **Basic case**: Simple, common pattern
2. **Complex case**: Multiple patterns in one file
3. **Edge case**: Unusual but valid pattern
4. **Negative case**: Should NOT match
5. **Security case**: Vulnerable pattern (if applicable)

Example test structure:
```python
def test_extractor_name():
    # Test case 1: Basic
    code = "..."
    result = extract_X(tree_dict, None)
    assert len(result) == expected
    assert result[0]['field'] == expected_value

    # Test case 2: Complex
    # Test case 3: Edge
    # Test case 4: Negative
    # Test case 5: Security
```

---

## PERFORMANCE REQUIREMENTS

Each extractor must:
- Process file in <10ms
- Use single ast.walk() if possible
- Return empty list for non-matches (not None)
- Handle malformed AST gracefully
- Not exceed 200 lines of code

---

## THIS IS THE SWEET SPOT

✅ **Exact specifications** - Not vague descriptions
✅ **Return formats defined** - Not "figure it out"
✅ **Database schemas provided** - Not "create tables"
✅ **Integration points marked** - Not "wire it up somehow"
✅ **Test cases specified** - Not "test it"
✅ **Patterns to detect shown** - Not "find Flask stuff"

But also:
❌ **Not complete code** - You still write the implementation
❌ **Not copy-paste** - You still think about the algorithm
❌ **Not hand-holding** - You still make decisions

**This is what you can actually code from without confusion.**