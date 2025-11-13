"""Test fixture for data flow pattern extraction.

This file contains examples of all data flow patterns that should be extracted:
- I/O operations (file, database, network, process, environment)
- Parameter to return flow
- Closure captures
- Nonlocal access

Expected extractions:
- ~25 I/O operations
- ~15 parameter return flows
- ~8 closure captures
- ~5 nonlocal accesses
"""

import os
import subprocess
import sqlite3


# ============================================================================
# PATTERN 1: I/O Operations
# ============================================================================

def file_write_operation():
    """Test FILE_WRITE I/O operation."""
    with open("output.txt", "w") as f:  # Expected: io_type='FILE_WRITE', target='output.txt', is_static=True
        f.write("Hello World")


def file_read_operation():
    """Test FILE_READ I/O operation."""
    with open("input.txt", "r") as f:  # Expected: io_type='FILE_READ', target='input.txt', is_static=True
        data = f.read()
    return data


def dynamic_file_operation(filename):
    """Test dynamic filename (non-static)."""
    with open(filename, "w") as f:  # Expected: io_type='FILE_WRITE', target=None, is_static=False
        f.write("data")


def database_commit():
    """Test DB_COMMIT I/O operation."""
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users VALUES (?, ?)", ("alice", 25))
    conn.commit()  # Expected: io_type='DB_COMMIT', operation='commit'
    conn.close()


def database_query():
    """Test DB_QUERY I/O operation."""
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")  # Expected: io_type='DB_QUERY', operation='execute', target='SELECT * FROM users', is_static=True
    return cursor.fetchall()


def network_request():
    """Test NETWORK I/O operation."""
    import requests
    response = requests.post("https://api.example.com/data", json={"key": "value"})  # Expected: io_type='NETWORK', operation='requests.post', target='https://api.example.com/data', is_static=True
    return response.json()


def process_spawn():
    """Test PROCESS I/O operation."""
    result = subprocess.run(["ls", "-la"], capture_output=True)  # Expected: io_type='PROCESS', operation='subprocess.run', target='ls', is_static=True
    return result.stdout


def environment_modification():
    """Test ENV_MODIFY I/O operation."""
    os.environ["API_KEY"] = "secret123"  # Expected: io_type='ENV_MODIFY', operation='setenv', target='API_KEY', is_static=True


def pathlib_write():
    """Test Path.write_text() I/O operation."""
    from pathlib import Path
    Path("output.txt").write_text("Hello")  # Expected: io_type='FILE_WRITE', operation contains 'write_text'


def pathlib_read():
    """Test Path.read_text() I/O operation."""
    from pathlib import Path
    return Path("input.txt").read_text()  # Expected: io_type='FILE_READ', operation contains 'read_text'


# ============================================================================
# PATTERN 2: Parameter Return Flow
# ============================================================================

def direct_return(x):
    """Test direct parameter return."""
    return x  # Expected: flow_type='direct', parameter_name='x'


def transformed_return(x):
    """Test transformed parameter return."""
    return x * 2  # Expected: flow_type='transformed', parameter_name='x'


def conditional_return(x, y):
    """Test conditional parameter return."""
    return x if x > 0 else y  # Expected: flow_type='conditional', parameter_name='x' and 'y' (2 records)


def multiple_operations(a, b):
    """Test parameter in complex expression."""
    result = (a + b) * 2
    return result  # Expected: flow_type='transformed', parameter_name='a' and 'b'


def no_param_return():
    """Test return with no parameter reference (should NOT extract)."""
    return 42  # Expected: NO extraction (no parameter flow)


def partial_param_return(x, y):
    """Test return referencing only one param."""
    return x + 10  # Expected: flow_type='transformed', parameter_name='x' (NOT 'y')


async def async_param_return(data):
    """Test async parameter return."""
    return await process_data(data)  # Expected: is_async=True, parameter_name='data'


def string_concat_return(name):
    """Test string concatenation return."""
    return "Hello, " + name  # Expected: flow_type='transformed', parameter_name='name'


# ============================================================================
# PATTERN 3: Closure Captures
# ============================================================================

def outer_function():
    """Test closure capture."""
    counter = 0  # Outer variable

    def inner_function():
        """Inner function capturing outer variable."""
        return counter + 1  # Expected: captured_variable='counter', outer_function='outer_function', is_lambda=False

    return inner_function


def nested_closure():
    """Test nested closure."""
    level1_var = "level1"

    def middle():
        level2_var = "level2"

        def inner():
            return level1_var + level2_var  # Expected: 2 captures (level1_var from outer_function, level2_var from middle)

        return inner

    return middle


def lambda_closure():
    """Test lambda closure."""
    multiplier = 10
    return lambda x: x * multiplier  # Expected: captured_variable='multiplier', is_lambda=True


def closure_with_multiple_captures():
    """Test multiple variable captures."""
    a = 1
    b = 2
    c = 3

    def inner():
        return a + b + c  # Expected: 3 captures (a, b, c)

    return inner


def no_closure():
    """Test function with no closure (should NOT extract)."""
    def inner(x):
        return x * 2  # Expected: NO extraction (no captured variables, only parameter)

    return inner


# ============================================================================
# PATTERN 4: Nonlocal Access
# ============================================================================

def nonlocal_write():
    """Test nonlocal write access."""
    counter = 0

    def increment():
        nonlocal counter
        counter += 1  # Expected: access_type='write', variable_name='counter'

    increment()
    return counter


def nonlocal_read():
    """Test nonlocal read access."""
    value = 42

    def read_value():
        nonlocal value
        return value  # Expected: access_type='read', variable_name='value'

    return read_value()


def nonlocal_multiple_access():
    """Test multiple nonlocal accesses."""
    x = 0
    y = 0

    def modify():
        nonlocal x, y
        x += 1  # Expected: access_type='write', variable_name='x'
        y = x + 1  # Expected: 2 records (read 'x', write 'y')

    modify()
    return x, y


def nonlocal_in_nested_function():
    """Test nonlocal in nested function."""
    state = {"count": 0}

    def outer():
        def inner():
            nonlocal state
            state["count"] += 1  # Expected: access_type='write', variable_name='state' (subscription is secondary)

        inner()

    outer()
    return state


# ============================================================================
# COMBINED PATTERNS (Complex Real-World Example)
# ============================================================================

def complex_data_flow_example(user_id):
    """Test all data flow patterns together."""
    cache = {}  # Outer variable for closure

    # I/O operation: Database query
    conn = sqlite3.connect("users.db")  # I/O: DB connection
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))  # I/O: DB_QUERY
    user_data = cursor.fetchone()
    conn.close()

    def cached_lookup(key):
        """Closure capturing cache variable."""
        nonlocal cache
        if key not in cache:
            # I/O operation: Network request
            import requests
            cache[key] = requests.get(f"https://api.example.com/{key}").json()  # I/O: NETWORK
        return cache[key]  # Closure: captures 'cache', Nonlocal: read 'cache'

    # Parameter return flow
    result = {"user": user_data, "lookup": cached_lookup}
    return result  # Parameter flow: user_id influences return (indirectly)


def transaction_pattern(data):
    """Test database transaction pattern with I/O."""
    conn = sqlite3.connect("app.db")  # I/O: DB connection
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN")  # I/O: DB_QUERY

        # I/O operations
        cursor.execute("INSERT INTO logs VALUES (?)", (data,))  # I/O: DB_QUERY
        cursor.execute("UPDATE stats SET count = count + 1")  # I/O: DB_QUERY

        conn.commit()  # I/O: DB_COMMIT
    except Exception:
        conn.rollback()  # I/O: DB_ROLLBACK
        raise
    finally:
        conn.close()

    return data  # Parameter flow: direct return


def file_processor(input_file, output_file):
    """Test file I/O operations."""
    # I/O: FILE_READ
    with open(input_file, "r") as f_in:  # Dynamic target (parameter)
        data = f_in.read()

    processed = data.upper()  # Transform

    # I/O: FILE_WRITE
    with open(output_file, "w") as f_out:  # Dynamic target (parameter)
        f_out.write(processed)

    return processed  # Parameter flow: input_file influences return
