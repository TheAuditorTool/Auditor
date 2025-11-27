"""
Async Patterns Fixture (Python)

Tests extraction of:
- async def functions
- await call chains (function awaits function awaits function)
- Async context managers (async with)
- Async generators (async for)
- asyncio.gather for parallel operations
- Async error handling (try/except in async context)
- Async decorators
- Mixed sync/async code

Validates that:
- Async functions are extracted to symbols table
- await calls are captured in function_calls table
- Async call graph shows await chains
- Async context managers are tracked
- Control flow through async/await is correct
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Any

# ==============================================================================
# Basic Async Functions
# ==============================================================================

async def simple_async_function():
    """
    Basic async function.
    Tests: async def extraction.
    """
    await asyncio.sleep(0.1)
    return "completed"


async def async_with_params(user_id: int, timeout: float = 1.0):
    """
    Async function with parameters.
    Tests: Parameter extraction on async functions.
    """
    await asyncio.sleep(timeout)
    return f"User {user_id} data"


# ==============================================================================
# Await Call Chains (Function Awaits Function Awaits Function)
# ==============================================================================

async def fetch_user_profile(profile_id: int) -> dict[str, Any]:
    """
    Fetch user profile from database (simulated).
    Tests: Leaf async function in call chain.
    """
    await asyncio.sleep(0.05)  # Simulate DB query
    return {
        "profile_id": profile_id,
        "bio": "Software engineer",
        "avatar_url": f"https://example.com/avatar/{profile_id}"
    }


async def fetch_user_permissions(user_id: int) -> list[str]:
    """
    Fetch user permissions from auth service (simulated).
    Tests: Another leaf async function.
    """
    await asyncio.sleep(0.05)  # Simulate API call
    return ["read", "write", "admin"]


async def fetch_user_data(user_id: int) -> dict[str, Any]:
    """
    Fetch core user data from database.
    Tests: Intermediate async function - awaits another async function.
    """
    await asyncio.sleep(0.1)  # Simulate DB query

    # Await another async function (call chain!)
    profile = await fetch_user_profile(user_id)

    return {
        "user_id": user_id,
        "username": f"user_{user_id}",
        "email": f"user{user_id}@example.com",
        "profile": profile
    }


async def fetch_user(user_id: int) -> dict[str, Any]:
    """
    Fetch complete user object (3-level await chain).
    Tests: Top-level async function that chains multiple awaits.

    Call chain:
    fetch_user → await fetch_user_data → await fetch_user_profile
    fetch_user → await fetch_user_permissions
    """
    # First await - fetches data which itself awaits profile
    data = await fetch_user_data(user_id)

    # Second await - fetches permissions in parallel conceptually
    permissions = await fetch_user_permissions(user_id)

    # Combine results
    return {
        **data,
        "permissions": permissions
    }


# ==============================================================================
# Parallel Async Operations (asyncio.gather)
# ==============================================================================

async def process_item(item_id: int) -> str:
    """
    Process a single item.
    Tests: Async function called in parallel.
    """
    await asyncio.sleep(0.1)
    return f"Processed item {item_id}"


async def process_batch(items: list[int]) -> list[str]:
    """
    Process multiple items in parallel using asyncio.gather.
    Tests: Parallel async execution - multiple await points.
    """
    # Create tasks for parallel execution
    tasks = [process_item(item_id) for item_id in items]

    # Await all tasks in parallel
    results = await asyncio.gather(*tasks)

    return results


async def fetch_user_and_posts(user_id: int) -> dict[str, Any]:
    """
    Fetch user and their posts in parallel.
    Tests: Multiple independent await calls (parallel pattern).
    """
    # Execute both fetches in parallel
    user_data, posts_data = await asyncio.gather(
        fetch_user_data(user_id),
        fetch_posts_for_user(user_id)
    )

    return {
        "user": user_data,
        "posts": posts_data
    }


async def fetch_posts_for_user(user_id: int) -> list[dict[str, Any]]:
    """
    Fetch all posts for a user.
    Tests: Async function returning list of dicts.
    """
    await asyncio.sleep(0.1)
    return [
        {"post_id": 1, "title": "First post", "author_id": user_id},
        {"post_id": 2, "title": "Second post", "author_id": user_id}
    ]


# ==============================================================================
# Async Context Managers (async with)
# ==============================================================================

class AsyncDatabaseConnection:
    """
    Async context manager for database connections.
    Tests: __aenter__ and __aexit__ extraction.
    """

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.connected = False

    async def __aenter__(self):
        """
        Async context manager enter.
        Tests: __aenter__ async method extraction.
        """
        await asyncio.sleep(0.05)  # Simulate connection setup
        self.connected = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Async context manager exit.
        Tests: __aexit__ async method extraction.
        """
        await asyncio.sleep(0.02)  # Simulate connection teardown
        self.connected = False

    async def execute(self, query: str) -> list[dict[str, Any]]:
        """
        Execute database query.
        Tests: Async method on context manager class.
        """
        if not self.connected:
            raise RuntimeError("Not connected")

        await asyncio.sleep(0.1)  # Simulate query execution
        return [{"result": "data"}]


@asynccontextmanager
async def get_db_connection(connection_string: str):
    """
    Async context manager using @asynccontextmanager decorator.
    Tests: Decorator-based async context manager.
    """
    # Setup
    connection = AsyncDatabaseConnection(connection_string)
    await connection.__aenter__()

    try:
        yield connection
    finally:
        # Teardown
        await connection.__aexit__(None, None, None)


async def query_database(query: str) -> list[dict[str, Any]]:
    """
    Query database using async context manager.
    Tests: async with statement - context manager usage.
    """
    async with AsyncDatabaseConnection("postgresql://localhost") as conn:
        results = await conn.execute(query)
        return results


async def query_with_decorator_context_manager(query: str) -> list[dict[str, Any]]:
    """
    Query using decorator-based context manager.
    Tests: async with using @asynccontextmanager.
    """
    async with get_db_connection("postgresql://localhost") as conn:
        results = await conn.execute(query)
        return results


# ==============================================================================
# Async Generators (async for)
# ==============================================================================

async def generate_numbers(count: int):
    """
    Async generator yielding numbers.
    Tests: async generator (yield in async function).
    """
    for i in range(count):
        await asyncio.sleep(0.01)
        yield i


async def fetch_paginated_results(page_size: int = 10):
    """
    Async generator simulating paginated API results.
    Tests: Realistic async generator pattern.
    """
    page = 0
    while page < 5:  # Fetch 5 pages
        await asyncio.sleep(0.1)  # Simulate API call

        # Yield batch of results
        yield [{"id": page * page_size + i, "data": f"item_{i}"} for i in range(page_size)]
        page += 1


async def consume_async_generator():
    """
    Consume async generator using async for.
    Tests: async for loop - consuming async generator.
    """
    results = []

    async for number in generate_numbers(10):
        results.append(number)

    return results


async def process_paginated_data():
    """
    Process paginated data from async generator.
    Tests: async for with complex generator.
    """
    all_items = []

    async for batch in fetch_paginated_results(page_size=10):
        # Process each batch
        for item in batch:
            all_items.append(item)

    return all_items


# ==============================================================================
# Async Error Handling
# ==============================================================================

class AsyncOperationError(Exception):
    """Custom exception for async operations."""
    pass


async def risky_async_operation(should_fail: bool = False):
    """
    Async function that may raise exception.
    Tests: Exception raising in async context.
    """
    await asyncio.sleep(0.05)

    if should_fail:
        raise AsyncOperationError("Operation failed")

    return "success"


async def handle_async_errors(should_fail: bool = False):
    """
    Async function with try/except.
    Tests: Exception handling in async context.
    """
    try:
        result = await risky_async_operation(should_fail)
        return result
    except AsyncOperationError as e:
        # Handle error
        return f"Error: {e}"


async def retry_async_operation(max_attempts: int = 3):
    """
    Retry async operation with exponential backoff.
    Tests: Complex async error handling with retry logic.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            result = await risky_async_operation(should_fail=(attempt < max_attempts))
            return result
        except AsyncOperationError:
            if attempt == max_attempts:
                raise

            # Exponential backoff
            delay = 2 ** (attempt - 1) * 0.1
            await asyncio.sleep(delay)


# ==============================================================================
# Async Decorators
# ==============================================================================

def async_timer(func):
    """
    Decorator to time async function execution.
    Tests: Decorator on async function (from Task 3).
    """
    async def wrapper(*args, **kwargs):
        import time
        start = time.time()
        result = await func(*args, **kwargs)
        elapsed = time.time() - start
        print(f"Async {func.__name__} took {elapsed:.2f}s")
        return result
    return wrapper


def async_retry(max_attempts: int = 3):
    """
    Parameterized decorator for async retry logic.
    Tests: Parameterized decorator on async function.
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception:
                    if attempt == max_attempts:
                        raise
                    await asyncio.sleep(0.1 * attempt)
        return wrapper
    return decorator


@async_timer
@async_retry(max_attempts=3)
async def decorated_async_function(param: str):
    """
    Async function with stacked decorators.
    Tests: Multiple decorators on async function.
    """
    await asyncio.sleep(0.1)
    return f"Result for {param}"


# ==============================================================================
# Mixed Sync/Async Code
# ==============================================================================

def sync_helper(data: str) -> str:
    """
    Synchronous helper function.
    Tests: Sync function called from async context.
    """
    return data.upper()


async def async_calling_sync(data: str) -> str:
    """
    Async function calling sync function.
    Tests: Call graph includes sync function call from async context.
    """
    await asyncio.sleep(0.05)

    # Call sync function
    result = sync_helper(data)

    return result


async def run_in_executor(func, *args):
    """
    Run sync function in thread pool executor.
    Tests: asyncio.get_event_loop().run_in_executor pattern.
    """
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, func, *args)
    return result


# ==============================================================================
# Async Class Methods
# ==============================================================================

class AsyncService:
    """
    Service class with async methods.
    Tests: Async instance methods extraction.
    """

    def __init__(self, service_name: str):
        self.service_name = service_name

    async def initialize(self):
        """
        Async initialization method.
        Tests: Async instance method.
        """
        await asyncio.sleep(0.1)
        print(f"{self.service_name} initialized")

    async def fetch_data(self, data_id: int) -> dict[str, Any]:
        """
        Async data fetching method.
        Tests: Async instance method with return value.
        """
        await asyncio.sleep(0.1)
        return {"data_id": data_id, "service": self.service_name}

    async def process(self, items: list[int]) -> list[str]:
        """
        Process multiple items asynchronously.
        Tests: Async method calling other async methods.
        """
        results = []
        for item_id in items:
            data = await self.fetch_data(item_id)
            results.append(str(data))
        return results

    @staticmethod
    async def static_async_method(value: str) -> str:
        """
        Async static method.
        Tests: @staticmethod with async def.
        """
        await asyncio.sleep(0.05)
        return value.upper()

    @classmethod
    async def from_config(cls, config: dict[str, Any]):
        """
        Async class method (factory pattern).
        Tests: @classmethod with async def.
        """
        instance = cls(config.get("service_name", "default"))
        await instance.initialize()
        return instance


# ==============================================================================
# Async Comprehensions
# ==============================================================================

async def async_comprehension_example():
    """
    Async comprehensions and expressions.
    Tests: Async list/dict comprehensions.
    """
    # Async list comprehension
    results = [await process_item(i) for i in range(5)]

    # Async dict comprehension
    result_dict = {i: await process_item(i) for i in range(3)}

    return {"list": results, "dict": result_dict}


# ==============================================================================
# Real-World Async Pattern: API Client
# ==============================================================================

class AsyncAPIClient:
    """
    Realistic async API client.
    Tests: Complex async class with multiple patterns.
    """

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key
        self.session = None

    async def __aenter__(self):
        """Context manager enter."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.disconnect()

    async def connect(self):
        """Establish connection."""
        await asyncio.sleep(0.05)
        self.session = "connected"

    async def disconnect(self):
        """Close connection."""
        await asyncio.sleep(0.02)
        self.session = None

    async def get(self, endpoint: str) -> dict[str, Any]:
        """GET request."""
        await asyncio.sleep(0.1)
        return {"endpoint": endpoint, "method": "GET"}

    async def post(self, endpoint: str, data: dict[str, Any]) -> dict[str, Any]:
        """POST request."""
        await asyncio.sleep(0.1)
        return {"endpoint": endpoint, "method": "POST", "data": data}

    async def fetch_multiple(self, endpoints: list[str]) -> list[dict[str, Any]]:
        """
        Fetch multiple endpoints in parallel.
        Tests: asyncio.gather in method.
        """
        tasks = [self.get(endpoint) for endpoint in endpoints]
        results = await asyncio.gather(*tasks)
        return results


async def use_api_client():
    """
    Use async API client with context manager.
    Tests: Complex async pattern usage.
    """
    async with AsyncAPIClient("https://api.example.com", "key123") as client:
        # Single request
        user = await client.get("/users/1")

        # Parallel requests
        results = await client.fetch_multiple(["/users/1", "/users/2", "/users/3"])

        # POST request
        created = await client.post("/users", {"name": "New User"})

        return {"user": user, "results": results, "created": created}
