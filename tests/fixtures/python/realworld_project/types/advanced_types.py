"""Advanced type system patterns - Protocol, Generic, TypedDict, Literal, @overload."""

from typing import Generic, Literal, Protocol, TypedDict, TypeVar, overload, runtime_checkable


@runtime_checkable
class Serializable(Protocol):
    """Protocol for serializable objects.

    Should be extracted as a Protocol with runtime_checkable=True.
    """

    def to_dict(self) -> dict: ...
    def from_dict(self, data: dict) -> None: ...


class Cacheable(Protocol):
    """Protocol for cacheable objects (not runtime checkable)."""

    def get_cache_key(self) -> str: ...
    def invalidate_cache(self) -> None: ...


T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")


class Repository[T]:
    """Generic repository pattern.

    Should be extracted as a Generic with type_params=['T'].
    """

    def __init__(self):
        self._items: list[T] = []

    def add(self, item: T) -> None:
        self._items.append(item)

    def get(self, index: int) -> T:
        return self._items[index]


class Cache[K, V]:
    """Generic cache with key-value types.

    Should be extracted as a Generic with type_params=['K', 'V'].
    """

    def __init__(self):
        self._store: dict[K, V] = {}

    def set(self, key: K, value: V) -> None:
        self._store[key] = value

    def get(self, key: K) -> V | None:
        return self._store.get(key)


class UserDict(TypedDict):
    """TypedDict for user data.

    Should be extracted with fields including is_required status.
    """

    id: int
    username: str
    email: str
    is_active: bool


class OptionalUserDict(TypedDict, total=False):
    """TypedDict with optional fields."""

    id: int
    username: str
    email: str


class MixedRequiredDict(TypedDict):
    """TypedDict with mixed required/optional fields (Python 3.11+)."""

    id: int
    username: str


def set_log_level(level: Literal["DEBUG", "INFO", "WARNING", "ERROR"]) -> None:
    """Function with Literal parameter type.

    Should be extracted as Literal usage in parameter context.
    """
    print(f"Log level set to {level}")


def get_status() -> Literal["active", "inactive", "pending"]:
    """Function with Literal return type.

    Should be extracted as Literal usage in return context.
    """
    return "active"


def process_mode(mode: Literal[1, 2, 3]) -> int:
    """Literal with integer values."""
    return mode * 2


status: Literal["running", "stopped"] = "running"
http_method: Literal["GET", "POST", "PUT", "DELETE"] = "GET"


@overload
def process_data(data: str) -> str: ...


@overload
def process_data(data: int) -> int: ...


@overload
def process_data(data: list) -> list: ...


def process_data(data):
    """Function with multiple overload signatures.

    Should be extracted with 3 overload variants.
    """
    if isinstance(data, str):
        return data.upper()
    elif isinstance(data, int):
        return data * 2
    elif isinstance(data, list):
        return [x * 2 for x in data]
    return data


@overload
def fetch_user(user_id: int) -> dict: ...


@overload
def fetch_user(user_id: str) -> dict: ...


def fetch_user(user_id):
    """Fetch user by ID (int or string).

    Should be extracted with 2 overload variants.
    """
    return {"id": user_id}


class DataProcessor(Generic[T], Protocol):
    """Protocol that is also Generic.

    Should be extracted as both Protocol AND Generic.
    """

    def process(self, item: T) -> T: ...


def handle_result(result: Literal["success", "failure"]) -> Literal[200, 500]:
    """Multiple Literal types in signature."""
    if result == "success":
        return 200
    return 500
