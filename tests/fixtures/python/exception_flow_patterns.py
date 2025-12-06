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


class ValidationError(Exception):
    """Custom exception for testing."""

    pass


def validate_age(age):
    """Test basic raise with message."""
    if age < 0:
        raise ValueError(
            "Age cannot be negative"
        )  # Expected: exception_type='ValueError', message='Age cannot be negative'
    if age > 150:
        raise ValueError(
            "Age too high"
        )  # Expected: exception_type='ValueError', message='Age too high'
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
        raise ValueError("Invalid data format") from e


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


def return_none_strategy(x):
    """Test 'return_none' handling strategy."""
    try:
        return 1 / x
    except ZeroDivisionError:
        return None


def re_raise_strategy(data):
    """Test 're_raise' handling strategy."""
    try:
        process(data)
    except ValueError:
        raise


def log_and_continue_strategy(file_path):
    """Test 'log_and_continue' handling strategy."""
    try:
        open_file(file_path)
    except FileNotFoundError:
        print("File not found")
        pass


def convert_to_other_strategy(value):
    """Test 'convert_to_other' handling strategy."""
    try:
        return int(value)
    except ValueError:
        raise TypeError("Invalid type")


def multiple_exception_types(data):
    """Test catching multiple exception types."""
    try:
        process(data)
    except (ValueError, TypeError):
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
    except ValueError as e:
        print(str(e))


def cleanup_lock():
    """Test finally with cleanup call."""
    lock.acquire()
    try:
        perform_operation()
    finally:
        lock.release()


def cleanup_multiple():
    """Test finally with multiple cleanup calls."""
    file = open("data.txt")
    lock.acquire()
    try:
        process(file)
    finally:
        file.close()
        lock.release()


def finally_no_cleanup():
    """Test finally without cleanup calls."""
    try:
        operation()
    finally:
        pass


def finally_with_assignment():
    """Test finally with assignment (still cleanup)."""
    try:
        compute()
    finally:
        cleanup_resources()


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
    with (
        db.session() as session
    ):  # Expected: resource_type='database', variable_name='session', is_async=False
        session.query(User).all()


async def async_context_manager():
    """Test async context manager."""
    async with (
        aiohttp.ClientSession() as session
    ):  # Expected: resource_type='network', variable_name='session', is_async=True
        await session.get("https://api.example.com")


def multiple_context_managers():
    """Test multiple context managers."""
    with open("input.txt") as f_in, open("output.txt", "w") as f_out:
        data = f_in.read()
        f_out.write(data)


def nested_context_managers():
    """Test nested context managers."""
    with lock1:
        with lock2:
            critical_operation()


def complex_exception_handling(file_path):
    """Test all patterns together."""

    try:
        with open(file_path) as f:
            data = f.read()

            if not data:
                raise ValueError("Empty file")

            return process(data)

    except FileNotFoundError as e:
        print(f"File not found: {e}")
        return None

    except ValueError:
        raise

    finally:
        cleanup_temp_files()


def transaction_pattern():
    """Test database transaction pattern."""
    try:
        with db.transaction() as tx:
            tx.execute("INSERT INTO users ...")

            if error_condition:
                raise RuntimeError("Transaction failed")

    except RuntimeError:
        pass

    finally:
        close_connection()


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
    except ValueError:
        handle_value_error()
    except TypeError:
        handle_type_error()
    except Exception:
        handle_generic_error()


def raise_in_function_call():
    """Test raise inside function call (still detected)."""

    pass


if __name__ == "__main__":
    raise NotImplementedError("This script should not be run directly")
