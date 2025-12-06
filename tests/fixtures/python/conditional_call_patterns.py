"""Test fixture for conditional call pattern extraction.

This file contains examples of all conditional call patterns that should be extracted:
- Functions called in if/elif/else blocks
- Guard clauses (early returns)
- Exception-dependent code paths
- Nested conditionals

Expected extractions:
- ~8 if/elif/else conditional calls
- ~3 guard clause patterns
- ~2 exception-dependent calls
- ~2 nested conditional calls
"""


def check_permissions(user):
    """Test basic conditional function calls."""
    if user.is_admin:
        delete_all_users()

    if user.is_moderator:
        ban_user()
    else:
        report_user()


def process_data(data, debug=False):
    """Test elif pattern."""
    if data is None:
        return None
    elif len(data) == 0:
        initialize_empty()
    elif len(data) > 1000:
        process_large_dataset()
    else:
        process_normal()


def validate_input(value):
    """Test guard clause pattern."""
    if value is None:
        return

    if value < 0:
        raise ValueError("Negative value")

    process_valid_input(value)


def authenticate_user(credentials):
    """Test guard clauses with function calls."""
    if not credentials:
        log_invalid_credentials()
        return False

    if not verify_signature(credentials):
        log_failed_auth()
        return False

    return True


def risky_operation(filename):
    """Test exception-dependent calls."""
    try:
        data = open(filename).read()
        process_file(data)
    except FileNotFoundError:
        create_default_file()
    except PermissionError:
        request_elevated_permissions()
    finally:
        cleanup()


def network_request(url):
    """Test nested try/except."""
    try:
        response = fetch_url(url)
        return response
    except TimeoutError:
        retry_with_backoff()
    except ConnectionError:
        switch_to_fallback_server()


def complex_authorization(user, resource):
    """Test nested conditional calls."""
    if user.is_authenticated:
        if resource.is_public:
            grant_read_access()
        else:
            if user.owns_resource(resource):
                grant_full_access()
            else:
                deny_access()


def nested_validation(config):
    """Test deeply nested conditionals."""
    if config.debug and config.verbose:
        enable_detailed_logging()
        if config.trace:
            enable_stack_traces()


def conditional_assignment(flag):
    """Test assignments with conditional function calls."""
    if flag:
        result = expensive_computation()
    else:
        result = default_value()
    return result


def conditional_return(mode):
    """Test return statements with conditional function calls."""
    if mode == "fast":
        return quick_process()
    elif mode == "accurate":
        return detailed_process()
    else:
        return fallback_process()


def delete_all_users():
    pass


def ban_user():
    pass


def report_user():
    pass


def initialize_empty():
    pass


def process_large_dataset():
    pass


def process_normal():
    pass


def process_valid_input(value):
    pass


def log_invalid_credentials():
    pass


def verify_signature(credentials):
    pass


def log_failed_auth():
    pass


def process_file(data):
    pass


def create_default_file():
    pass


def request_elevated_permissions():
    pass


def cleanup():
    pass


def fetch_url(url):
    pass


def retry_with_backoff():
    pass


def switch_to_fallback_server():
    pass


def grant_read_access():
    pass


def grant_full_access():
    pass


def deny_access():
    pass


def enable_detailed_logging():
    pass


def enable_stack_traces():
    pass


def expensive_computation():
    pass


def default_value():
    pass


def quick_process():
    pass


def detailed_process():
    pass


def fallback_process():
    pass
