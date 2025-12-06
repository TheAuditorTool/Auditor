"""
Complex Decorators Fixture (Python)

Tests extraction of:
- Stacked decorators (3+ deep) on functions and methods
- Parameterized decorators with arguments
- Custom decorator implementations (wrapping, unwrapping)
- Class decorators
- Property decorators with getter/setter/deleter
- Decorator chains in CFG (control flow graph)

Validates that:
- Decorators are captured in function_calls or decorators table
- CFG includes decorator invocations before function execution
- Decorator parameters are extracted correctly
- Security-relevant decorators (auth, validation, rate_limit) are visible
"""

from collections.abc import Callable
from functools import wraps
from typing import Any


def simple_decorator(func: Callable) -> Callable:
    """Simple decorator without arguments."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        print(f"Before {func.__name__}")
        result = func(*args, **kwargs)
        print(f"After {func.__name__}")
        return result

    return wrapper


def timer(func: Callable) -> Callable:
    """Decorator to time function execution."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        import time

        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        print(f"{func.__name__} took {elapsed:.2f}s")
        return result

    return wrapper


def log_calls(func: Callable) -> Callable:
    """Decorator to log function calls."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        print(f"Calling {func.__name__} with args={args}, kwargs={kwargs}")
        return func(*args, **kwargs)

    return wrapper


def cache(timeout: int = 60):
    """
    Parameterized decorator - caches function results.
    Tests: Decorator with arguments extraction.
    """

    def decorator(func: Callable) -> Callable:
        cache_store = {}

        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = str(args) + str(kwargs)
            if cache_key in cache_store:
                print(f"Cache hit for {func.__name__}")
                return cache_store[cache_key]

            result = func(*args, **kwargs)
            cache_store[cache_key] = result
            return result

        return wrapper

    return decorator


def rate_limit(requests: int = 100, window: int = 60):
    """
    Parameterized decorator - rate limiting.
    Tests: Multiple decorator parameters.
    """

    def decorator(func: Callable) -> Callable:
        call_log = []

        @wraps(func)
        def wrapper(*args, **kwargs):
            import time

            now = time.time()

            cutoff = now - window
            call_log[:] = [t for t in call_log if t > cutoff]

            if len(call_log) >= requests:
                raise Exception(f"Rate limit exceeded: {requests} requests per {window}s")

            call_log.append(now)
            return func(*args, **kwargs)

        return wrapper

    return decorator


def retry(max_attempts: int = 3, delay: float = 1.0):
    """
    Parameterized decorator - retry failed calls.
    Tests: Decorator with multiple parameters.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            import time

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts:
                        raise
                    print(f"Attempt {attempt} failed: {e}. Retrying in {delay}s...")
                    time.sleep(delay)

        return wrapper

    return decorator


class AuthError(Exception):
    """Authentication error."""

    pass


def require_auth(func: Callable) -> Callable:
    """
    Security decorator - requires authentication.
    Tests: Auth decorator extraction for security analysis.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        user = kwargs.get("user")
        if not user or not getattr(user, "is_authenticated", False):
            raise AuthError("Authentication required")
        return func(*args, **kwargs)

    return wrapper


def require_role(role: str):
    """
    Parameterized auth decorator - requires specific role.
    Tests: Role-based access control decorator.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = kwargs.get("user")
            if not user or not hasattr(user, "roles"):
                raise AuthError(f"Role '{role}' required")

            if role not in getattr(user, "roles", []):
                raise AuthError(f"Insufficient permissions. Role '{role}' required")

            return func(*args, **kwargs)

        return wrapper

    return decorator


def require_permissions(*permissions: str):
    """
    Variadic auth decorator - requires multiple permissions.
    Tests: Decorator with *args (variable arguments).
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = kwargs.get("user")
            user_perms = getattr(user, "permissions", [])

            missing = [p for p in permissions if p not in user_perms]
            if missing:
                raise AuthError(f"Missing permissions: {missing}")

            return func(*args, **kwargs)

        return wrapper

    return decorator


def validate_input(schema: dict):
    """
    Validation decorator - validates input against schema.
    Tests: Validation decorator extraction (security-relevant).
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            for key, validator in schema.items():
                if key in kwargs:
                    value = kwargs[key]
                    if not validator(value):
                        raise ValueError(f"Validation failed for {key}: {value}")

            return func(*args, **kwargs)

        return wrapper

    return decorator


def validate_output(validator: Callable):
    """
    Output validation decorator.
    Tests: Post-condition validation.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            if not validator(result):
                raise ValueError(f"Output validation failed for {func.__name__}")
            return result

        return wrapper

    return decorator


@require_auth
@require_role("admin")
@cache(timeout=300)
@rate_limit(requests=10, window=60)
def admin_dashboard(user=None):
    """
    Function with 4 stacked decorators.
    Tests: Deep decorator chain extraction (auth + role + cache + rate_limit).
    CFG should show: require_auth → require_role → cache → rate_limit → function body
    """
    return f"Admin dashboard for {user}"


@validate_input(schema={"email": lambda x: "@" in x, "age": lambda x: x >= 18})
@log_calls
@timer
def create_user(email: str, age: int):
    """
    Function with 3 stacked decorators (validation + logging + timing).
    Tests: Validation + monitoring decorator chain.
    """
    return {"email": email, "age": age}


@retry(max_attempts=5, delay=2.0)
@cache(timeout=600)
@log_calls
def fetch_external_api(url: str):
    """
    Function with 3 stacked decorators (retry + cache + logging).
    Tests: Resilience + caching decorator chain.
    """
    import requests

    return requests.get(url).json()


def singleton(cls):
    """
    Class decorator - singleton pattern.
    Tests: Class-level decorator extraction.
    """
    instances = {}

    @wraps(cls)
    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return get_instance


def add_logging(cls):
    """
    Class decorator - adds logging to all methods.
    Tests: Class decorator that modifies methods.
    """
    original_init = cls.__init__

    def new_init(self, *args, **kwargs):
        print(f"Creating instance of {cls.__name__}")
        original_init(self, *args, **kwargs)

    cls.__init__ = new_init
    return cls


@singleton
@add_logging
class ConfigManager:
    """
    Class with stacked decorators.
    Tests: Multiple class decorators.
    """

    def __init__(self):
        self.config = {}

    def get(self, key: str) -> Any:
        return self.config.get(key)

    def set(self, key: str, value: Any) -> None:
        self.config[key] = value


class APIController:
    """
    Class with decorated methods.
    Tests: Decorator extraction on instance methods.
    """

    @require_auth
    @rate_limit(requests=100, window=60)
    def get_users(self, user=None):
        """
        Method with 2 stacked decorators.
        Tests: Auth + rate limiting on instance method.
        """
        return ["user1", "user2", "user3"]

    @require_auth
    @require_role("admin")
    @validate_input(schema={"user_id": lambda x: isinstance(x, int)})
    def delete_user(self, user_id: int, user=None):
        """
        Method with 3 stacked decorators.
        Tests: Auth + role + validation on instance method.
        """
        return f"Deleted user {user_id}"

    @cache(timeout=120)
    @log_calls
    @timer
    def expensive_operation(self, param: str):
        """
        Method with 3 stacked decorators (caching + logging + timing).
        Tests: Performance decorators on instance method.
        """
        import time

        time.sleep(0.5)
        return f"Result for {param}"


class UtilityClass:
    """
    Class with static/class method decorators.
    Tests: Decorators on static and class methods.
    """

    @staticmethod
    @cache(timeout=300)
    @log_calls
    def validate_email(email: str) -> bool:
        """
        Static method with 2 decorators.
        Tests: Decorators on @staticmethod.
        """
        return "@" in email and "." in email.split("@")[1]

    @classmethod
    @require_permissions("admin.read", "admin.write")
    def from_config(cls, config: dict):
        """
        Class method with decorator.
        Tests: Decorators on @classmethod.
        """
        instance = cls()
        return instance


class User:
    """
    Class with property decorators.
    Tests: @property, @setter, @deleter extraction.
    """

    def __init__(self, name: str, email: str):
        self._name = name
        self._email = email
        self._age = None

    @property
    def name(self) -> str:
        """Name property getter."""
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        """Name property setter with validation."""
        if not value or len(value) < 2:
            raise ValueError("Name must be at least 2 characters")
        self._name = value

    @property
    @cache(timeout=60)
    def email(self) -> str:
        """Email property with caching."""
        return self._email

    @property
    def age(self) -> int:
        """Age property."""
        return self._age

    @age.setter
    @validate_input(schema={"age": lambda x: 0 <= x <= 150})
    def age(self, value: int) -> None:
        """Age setter with validation decorator."""
        self._age = value


def with_transaction(func: Callable) -> Callable:
    """
    Decorator that wraps function in database transaction.
    Tests: Decorator using context manager (important for CFG).
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        print("BEGIN TRANSACTION")
        try:
            result = func(*args, **kwargs)
            print("COMMIT")
            return result
        except Exception:
            print("ROLLBACK")
            raise

    return wrapper


@with_transaction
@validate_input(schema={"amount": lambda x: x > 0})
@log_calls
def transfer_funds(from_account: str, to_account: str, amount: float):
    """
    Function with transaction + validation + logging decorators.
    Tests: CFG includes transaction boundary markers.
    """
    return f"Transferred ${amount} from {from_account} to {to_account}"


def async_timer(func: Callable) -> Callable:
    """
    Async decorator.
    Tests: Decorator on async function.
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        import time

        start = time.time()
        result = await func(*args, **kwargs)
        elapsed = time.time() - start
        print(f"Async {func.__name__} took {elapsed:.2f}s")
        return result

    return wrapper


@async_timer
@cache(timeout=120)
async def async_fetch_data(url: str):
    """
    Async function with decorators.
    Tests: Decorators on async def (preview of Task 4).
    """
    import asyncio

    await asyncio.sleep(0.1)
    return {"url": url, "data": "..."}
