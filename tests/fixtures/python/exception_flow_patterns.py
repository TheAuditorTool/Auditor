"""Test fixture for exception flow pattern extraction.

This file contains examples of all exception flow patterns that should be extracted:
- Exception raises (raise ValueError("msg"))
- Exception catches (except ValueError as e: ...)
- Finally blocks (finally: cleanup())
- Context managers (with open(...) as f: ...)

Expected extractions:
- ~20 exception raises
- ~15 exception catches
- ~6 finally blocks
- ~8 context managers
"""


# ============================================================================
# PATTERN 1: Exception Raises
# ============================================================================

class ValidationError(Exception):
    """Custom exception for testing."""
    pass


def validate_age(age):
    """Test basic raise with message."""
    if age < 0:
        raise ValueError("Age cannot be negative")  # Expected: exception_type='ValueError', message='Age cannot be negative'
    if age > 150:
        raise ValueError("Age too high")  # Expected: exception_type='ValueError', message='Age too high'
    return age


def validate_name(name):
    """Test raise without message."""
    if not name:
        raise ValidationError  # Expected: exception_type='ValidationError', message=None
    return name


def process_data(data):
    """Test exception chaining."""
    try:
        transform(data)
    except KeyError as e:
        raise ValueError("Invalid data format") from e  # Expected: from_exception='e'


def re_raise_example():
    """Test bare raise (re-raise)."""
    try:
        risky_operation()
    except Exception:
        log_error("Failed")
        raise  # Expected: is_re_raise=True, exception_type=None


def conditional_raise(value):
    """Test multiple conditional raises."""
    if value < 0:
        raise ValueError("Negative value")
    elif value > 100:
        raise ValueError("Value too large")
    elif value == 42:
        raise RuntimeError("Special value")


# ============================================================================
# PATTERN 2: Exception Catches
# ============================================================================

def return_none_strategy(x):
    """Test 'return_none' handling strategy."""
    try:
        return 1 / x
    except ZeroDivisionError:
        return None  # Expected: handling_strategy='return_none'


def re_raise_strategy(data):
    """Test 're_raise' handling strategy."""
    try:
        process(data)
    except ValueError:
        raise  # Expected: handling_strategy='re_raise'


def log_and_continue_strategy(file_path):
    """Test 'log_and_continue' handling strategy."""
    try:
        open_file(file_path)
    except FileNotFoundError:
        print("File not found")
        pass  # Expected: handling_strategy='log_and_continue'


def convert_to_other_strategy(value):
    """Test 'convert_to_other' handling strategy."""
    try:
        return int(value)
    except ValueError:
        raise TypeError("Invalid type")  # Expected: handling_strategy='convert_to_other'


def multiple_exception_types(data):
    """Test catching multiple exception types."""
    try:
        process(data)
    except (ValueError, TypeError):  # Expected: exception_types='ValueError,TypeError'
        return None


def bare_except():
    """Test bare except clause."""
    try:
        risky()
    except:  # noqa: E722 - Expected: exception_types='Exception' (catches all)
        pass


def exception_with_variable(data):
    """Test exception with variable binding."""
    try:
        validate(data)
    except ValueError as e:  # Expected: variable_name='e'
        print(str(e))


# ============================================================================
# PATTERN 3: Finally Blocks
# ============================================================================

def cleanup_lock():
    """Test finally with cleanup call."""
    lock.acquire()
    try:
        perform_operation()
    finally:
        lock.release()  # Expected: cleanup_calls='lock.release', has_cleanup=True


def cleanup_multiple():
    """Test finally with multiple cleanup calls."""
    file = open("data.txt")
    lock.acquire()
    try:
        process(file)
    finally:
        file.close()  # Expected: cleanup_calls='file.close,lock.release', has_cleanup=True
        lock.release()


def finally_no_cleanup():
    """Test finally without cleanup calls."""
    try:
        operation()
    finally:
        pass  # Expected: cleanup_calls=None, has_cleanup=False


def finally_with_assignment():
    """Test finally with assignment (still cleanup)."""
    try:
        compute()
    finally:
        cleanup_resources()  # Expected: cleanup_calls='cleanup_resources', has_cleanup=True


# ============================================================================
# PATTERN 4: Context Managers
# ============================================================================

def file_context_manager():
    """Test file context manager."""
    with open("data.txt") as f:  # Expected: resource_type='file', variable_name='f', is_async=False
        data = f.read()
    return data


def lock_context_manager():
    """Test lock context manager."""
    import threading
    lock = threading.Lock()
    with lock:  # Expected: resource_type='lock', variable_name=None, is_async=False
        critical_section()


def database_context_manager():
    """Test database context manager."""
    with db.session() as session:  # Expected: resource_type='database', variable_name='session', is_async=False
        session.query(User).all()


async def async_context_manager():
    """Test async context manager."""
    async with aiohttp.ClientSession() as session:  # Expected: resource_type='network', variable_name='session', is_async=True
        await session.get("https://api.example.com")


def multiple_context_managers():
    """Test multiple context managers."""
    with open("input.txt") as f_in, open("output.txt", "w") as f_out:  # Expected: 2 records
        data = f_in.read()
        f_out.write(data)


def nested_context_managers():
    """Test nested context managers."""
    with lock1:  # Expected: context_expr='lock1'
        with lock2:  # Expected: context_expr='lock2'
            critical_operation()


# ============================================================================
# COMBINED PATTERNS (Complex Real-World Example)
# ============================================================================

def complex_exception_handling(file_path):
    """Test all patterns together."""
    # Context manager
    try:
        with open(file_path) as f:  # Context manager
            data = f.read()

            if not data:
                raise ValueError("Empty file")  # Exception raise

            return process(data)

    except FileNotFoundError as e:  # Exception catch with variable
        print(f"File not found: {e}")
        return None  # return_none strategy

    except ValueError:  # Exception catch without variable
        raise  # re_raise strategy

    finally:
        cleanup_temp_files()  # Finally block with cleanup


def transaction_pattern():
    """Test database transaction pattern."""
    try:
        with db.transaction() as tx:  # Context manager (database)
            tx.execute("INSERT INTO users ...")

            if error_condition:
                raise RuntimeError("Transaction failed")  # Exception raise

    except RuntimeError:
        # Error already logged by context manager
        pass  # pass strategy

    finally:
        close_connection()  # Finally cleanup


# ============================================================================
# EDGE CASES
# ============================================================================

def empty_try_except():
    """Test empty try/except (valid Python)."""
    try:
        pass
    except Exception:
        pass


def multiple_except_handlers():
    """Test multiple except clauses for same try."""
    try:
        operation()
    except ValueError:  # Expected: 3 separate catch records
        handle_value_error()
    except TypeError:
        handle_type_error()
    except Exception:
        handle_generic_error()


def raise_in_function_call():
    """Test raise inside function call (still detected)."""
    # Note: Cannot use raise in lambda (SyntaxError), so this is a placeholder
    pass


# Standalone raises (global scope) - should be detected with in_function='global'
if __name__ == "__main__":
    raise NotImplementedError("This script should not be run directly")
