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


# ============================================================================
# PATTERN 1: If/Elif/Else Conditional Calls
# ============================================================================

def check_permissions(user):
    """Test basic conditional function calls."""
    if user.is_admin:
        delete_all_users()  # Conditional call: only when user.is_admin

    if user.is_moderator:
        ban_user()  # Conditional call: only when user.is_moderator
    else:
        report_user()  # Conditional call: in else branch


def process_data(data, debug=False):
    """Test elif pattern."""
    if data is None:
        return None
    elif len(data) == 0:
        initialize_empty()  # Conditional call: in elif branch
    elif len(data) > 1000:
        process_large_dataset()  # Conditional call: in elif branch
    else:
        process_normal()  # Conditional call: in else branch


# ============================================================================
# PATTERN 2: Guard Clauses (Early Returns)
# ============================================================================

def validate_input(value):
    """Test guard clause pattern."""
    if value is None:
        return  # Guard clause (early return)

    if value < 0:
        raise ValueError("Negative value")  # Guard clause (early raise)

    process_valid_input(value)  # Normal flow after guards


def authenticate_user(credentials):
    """Test guard clauses with function calls."""
    if not credentials:
        log_invalid_credentials()  # Guard: called only when credentials are missing
        return False

    if not verify_signature(credentials):
        log_failed_auth()  # Guard: called only when signature fails
        return False

    return True


# ============================================================================
# PATTERN 3: Exception-Dependent Code Paths
# ============================================================================

def risky_operation(filename):
    """Test exception-dependent calls."""
    try:
        data = open(filename).read()
        process_file(data)
    except FileNotFoundError:
        create_default_file()  # Exception-dependent: only called if FileNotFoundError
    except PermissionError:
        request_elevated_permissions()  # Exception-dependent: only called if PermissionError
    finally:
        cleanup()  # Always called (not conditional)


def network_request(url):
    """Test nested try/except."""
    try:
        response = fetch_url(url)
        return response
    except TimeoutError:
        retry_with_backoff()  # Exception-dependent
    except ConnectionError:
        switch_to_fallback_server()  # Exception-dependent


# ============================================================================
# PATTERN 4: Nested Conditionals
# ============================================================================

def complex_authorization(user, resource):
    """Test nested conditional calls."""
    if user.is_authenticated:
        if resource.is_public:
            grant_read_access()  # Nested conditional: nesting_level=2
        else:
            if user.owns_resource(resource):
                grant_full_access()  # Nested conditional: nesting_level=3
            else:
                deny_access()  # Nested conditional: nesting_level=3


def nested_validation(config):
    """Test deeply nested conditionals."""
    if config.debug:
        if config.verbose:
            enable_detailed_logging()  # Nesting level 2
            if config.trace:
                enable_stack_traces()  # Nesting level 3


# ============================================================================
# PATTERN 5: Conditional Assignments and Returns
# ============================================================================

def conditional_assignment(flag):
    """Test assignments with conditional function calls."""
    if flag:
        result = expensive_computation()  # Conditional: function call on right side
    else:
        result = default_value()  # Conditional: function call in else
    return result


def conditional_return(mode):
    """Test return statements with conditional function calls."""
    if mode == "fast":
        return quick_process()  # Conditional: return with function call
    elif mode == "accurate":
        return detailed_process()  # Conditional: elif return with function call
    else:
        return fallback_process()  # Conditional: else return with function call


# ============================================================================
# Helper Functions (Stubs)
# ============================================================================

def delete_all_users(): pass
def ban_user(): pass
def report_user(): pass
def initialize_empty(): pass
def process_large_dataset(): pass
def process_normal(): pass
def process_valid_input(value): pass
def log_invalid_credentials(): pass
def verify_signature(credentials): pass
def log_failed_auth(): pass
def process_file(data): pass
def create_default_file(): pass
def request_elevated_permissions(): pass
def cleanup(): pass
def fetch_url(url): pass
def retry_with_backoff(): pass
def switch_to_fallback_server(): pass
def grant_read_access(): pass
def grant_full_access(): pass
def deny_access(): pass
def enable_detailed_logging(): pass
def enable_stack_traces(): pass
def expensive_computation(): pass
def default_value(): pass
def quick_process(): pass
def detailed_process(): pass
def fallback_process(): pass
