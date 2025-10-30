"""
Complex Type Hints Fixture (Python)

Tests extraction of:
- Nested generics: List[Dict[str, Union[int, str]]]
- Optional and Union types
- Variadic tuples: Tuple[int, ...]
- Callable type hints: Callable[[int, str], bool]
- TypeVar and Generic (custom generic classes)
- Protocol and structural subtyping
- Literal types
- Type aliases
- Forward references

Validates that complex type annotations are correctly extracted and stored.
"""

from typing import (
    List, Dict, Set, Tuple, Optional, Union, Any, Callable,
    TypeVar, Generic, Protocol, runtime_checkable,
    Literal, Final, ClassVar, Sequence, Mapping, Iterable,
    Type, cast, overload
)
from collections.abc import Iterator
from dataclasses import dataclass


# ==============================================================================
# TypeVar and Generic Classes
# ==============================================================================

T = TypeVar('T')
K = TypeVar('K')
V = TypeVar('V')
TNum = TypeVar('TNum', int, float)  # Constrained TypeVar


class Container(Generic[T]):
    """
    Generic container class.
    Tests: Generic class with single type parameter.
    """

    def __init__(self, value: T) -> None:
        self.value: T = value

    def get(self) -> T:
        """Get the contained value."""
        return self.value

    def set(self, value: T) -> None:
        """Set the contained value."""
        self.value = value


class Pair(Generic[K, V]):
    """
    Generic pair class with two type parameters.
    Tests: Generic class with multiple type parameters.
    """

    def __init__(self, key: K, value: V) -> None:
        self.key: K = key
        self.value: V = value

    def get_key(self) -> K:
        """Get the key."""
        return self.key

    def get_value(self) -> V:
        """Get the value."""
        return self.value


class Repository(Generic[T]):
    """
    Generic repository pattern.
    Tests: Generic base class for specialized repositories.
    """

    def __init__(self, model_class: Type[T]) -> None:
        self.model_class: Type[T] = model_class
        self.storage: List[T] = []

    def add(self, item: T) -> None:
        """Add item to repository."""
        self.storage.append(item)

    def get_all(self) -> List[T]:
        """Get all items."""
        return self.storage

    def find(self, predicate: Callable[[T], bool]) -> Optional[T]:
        """Find first item matching predicate."""
        for item in self.storage:
            if predicate(item):
                return item
        return None


# ==============================================================================
# Nested Generic Types
# ==============================================================================

def process_nested_dict(
    data: Dict[str, List[Dict[str, Union[int, str, None]]]]
) -> List[str]:
    """
    Function with deeply nested generic types.
    Tests: Dict[str, List[Dict[str, Union[int, str, None]]]]
    """
    results: List[str] = []
    for key, value_list in data.items():
        for item_dict in value_list:
            for k, v in item_dict.items():
                if v is not None:
                    results.append(f"{key}.{k} = {v}")
    return results


def transform_complex_structure(
    input_data: List[Tuple[str, Dict[str, Any]]]
) -> Dict[str, List[Tuple[str, Any]]]:
    """
    Transform complex nested structure.
    Tests: List[Tuple[str, Dict[str, Any]]] -> Dict[str, List[Tuple[str, Any]]]
    """
    output: Dict[str, List[Tuple[str, Any]]] = {}
    for key, value_dict in input_data:
        if key not in output:
            output[key] = []
        for k, v in value_dict.items():
            output[key].append((k, v))
    return output


def process_optional_lists(
    data: Optional[List[Optional[Dict[str, Optional[int]]]]]
) -> List[int]:
    """
    Function with multiple Optional layers.
    Tests: Optional[List[Optional[Dict[str, Optional[int]]]]]
    """
    results: List[int] = []
    if data is not None:
        for item in data:
            if item is not None:
                for value in item.values():
                    if value is not None:
                        results.append(value)
    return results


# ==============================================================================
# Union Types
# ==============================================================================

def handle_multiple_types(
    value: Union[int, str, List[int], Dict[str, Any]]
) -> str:
    """
    Function accepting multiple distinct types.
    Tests: Union[int, str, List[int], Dict[str, Any]]
    """
    if isinstance(value, int):
        return f"Integer: {value}"
    elif isinstance(value, str):
        return f"String: {value}"
    elif isinstance(value, list):
        return f"List: {len(value)} items"
    elif isinstance(value, dict):
        return f"Dict: {len(value)} keys"
    return "Unknown"


def parse_value(
    value: Union[str, int, float, bool, None]
) -> Optional[Union[int, float]]:
    """
    Parse value to numeric type.
    Tests: Union[str, int, float, bool, None] -> Optional[Union[int, float]]
    """
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            try:
                return float(value)
            except ValueError:
                return None
    return None


# ==============================================================================
# Callable Types
# ==============================================================================

def apply_transform(
    items: List[int],
    transform: Callable[[int], str]
) -> List[str]:
    """
    Apply transformation function to items.
    Tests: Callable[[int], str]
    """
    return [transform(item) for item in items]


def filter_items(
    items: List[T],
    predicate: Callable[[T], bool]
) -> List[T]:
    """
    Filter items using predicate.
    Tests: Generic function with Callable[[T], bool]
    """
    return [item for item in items if predicate(item)]


def compose_functions(
    f: Callable[[int], str],
    g: Callable[[str], bool]
) -> Callable[[int], bool]:
    """
    Compose two functions.
    Tests: Callable composition - returns Callable[[int], bool]
    """
    def composed(x: int) -> bool:
        return g(f(x))
    return composed


def higher_order_function(
    mapper: Callable[[T], V],
    items: List[T]
) -> Callable[[Callable[[V], bool]], List[T]]:
    """
    Higher-order function returning function.
    Tests: Complex callable returning callable.
    """
    def filter_by_mapped(predicate: Callable[[V], bool]) -> List[T]:
        return [item for item in items if predicate(mapper(item))]
    return filter_by_mapped


# ==============================================================================
# Tuple Types (including variadic)
# ==============================================================================

def process_fixed_tuple(
    data: Tuple[str, int, float]
) -> str:
    """
    Process fixed-size tuple.
    Tests: Tuple[str, int, float]
    """
    name, count, value = data
    return f"{name}: {count} items worth {value}"


def process_variadic_tuple(
    args: Tuple[int, ...]
) -> int:
    """
    Process variadic tuple.
    Tests: Tuple[int, ...] (unlimited ints)
    """
    return sum(args)


def combine_tuples(
    first: Tuple[str, ...],
    second: Tuple[int, ...]
) -> List[Tuple[str, int]]:
    """
    Combine two variadic tuples.
    Tests: Multiple variadic tuples.
    """
    return [(s, i) for s, i in zip(first, second)]


def complex_tuple_processing(
    data: List[Tuple[str, Optional[Tuple[int, str, ...]]]]
) -> Dict[str, List[int]]:
    """
    Process complex nested tuples.
    Tests: List[Tuple[str, Optional[Tuple[int, str, ...]]]]
    """
    result: Dict[str, List[int]] = {}
    for key, values in data:
        if values is not None and len(values) > 0:
            if isinstance(values[0], int):
                result[key] = [values[0]]
    return result


# ==============================================================================
# Protocol (Structural Subtyping)
# ==============================================================================

@runtime_checkable
class Comparable(Protocol):
    """
    Protocol for comparable types.
    Tests: Protocol definition with abstract methods.
    """

    def __lt__(self, other: Any) -> bool:
        ...

    def __le__(self, other: Any) -> bool:
        ...


@runtime_checkable
class Drawable(Protocol):
    """
    Protocol for drawable objects.
    Tests: Protocol with method signatures.
    """

    def draw(self) -> str:
        ...

    def get_position(self) -> Tuple[int, int]:
        ...


def sort_comparable_items(
    items: List[Comparable]
) -> List[Comparable]:
    """
    Sort items using Protocol.
    Tests: Function parameter with Protocol type.
    """
    return sorted(items)


def draw_all(
    drawables: Sequence[Drawable]
) -> List[str]:
    """
    Draw all drawable objects.
    Tests: Sequence[Drawable] where Drawable is Protocol.
    """
    return [d.draw() for d in drawables]


# ==============================================================================
# Literal Types
# ==============================================================================

def get_status(
    status: Literal["pending", "approved", "rejected"]
) -> str:
    """
    Function with Literal type.
    Tests: Literal["pending", "approved", "rejected"]
    """
    return f"Status is {status}"


def set_log_level(
    level: Literal[0, 1, 2, 3]
) -> None:
    """
    Set log level with Literal numeric type.
    Tests: Literal[0, 1, 2, 3]
    """
    print(f"Log level set to {level}")


def process_mode(
    mode: Literal["read", "write", "append"],
    binary: Literal[True, False] = False
) -> str:
    """
    Process with multiple Literal parameters.
    Tests: Multiple Literal types in signature.
    """
    return f"Mode: {mode}, Binary: {binary}"


# ==============================================================================
# Type Aliases
# ==============================================================================

# Simple type aliases
UserId = int
Username = str
Email = str

# Complex type aliases
UserData = Dict[str, Union[str, int, None]]
UserList = List[UserData]
UserMap = Dict[UserId, UserData]

# Nested type alias
ComplexStructure = Dict[str, List[Tuple[str, Optional[Union[int, str]]]]]


def create_user(
    user_id: UserId,
    username: Username,
    email: Email
) -> UserData:
    """
    Create user using type aliases.
    Tests: Type alias usage in function signature.
    """
    return {
        "id": user_id,
        "username": username,
        "email": email
    }


def get_user_map(
    users: UserList
) -> UserMap:
    """
    Convert user list to map.
    Tests: Complex type alias composition.
    """
    return {user["id"]: user for user in users if "id" in user}


def process_complex_structure(
    data: ComplexStructure
) -> List[str]:
    """
    Process complex aliased structure.
    Tests: Nested type alias with multiple generics.
    """
    results: List[str] = []
    for key, value_list in data.items():
        for item_tuple in value_list:
            name, value = item_tuple
            if value is not None:
                results.append(f"{key}.{name} = {value}")
    return results


# ==============================================================================
# Final and ClassVar
# ==============================================================================

class Configuration:
    """
    Configuration class with Final and ClassVar.
    Tests: Final and ClassVar type annotations.
    """

    # ClassVar - class-level variable
    DEFAULT_TIMEOUT: ClassVar[int] = 30
    MAX_RETRIES: ClassVar[int] = 3

    def __init__(self, timeout: int) -> None:
        # Final - cannot be reassigned after initialization
        self.timeout: Final[int] = timeout
        self.retries: int = 0

    def get_timeout(self) -> int:
        """Get timeout value."""
        return self.timeout


# ==============================================================================
# Overload (Multiple Signatures)
# ==============================================================================

@overload
def get_item(container: Dict[str, int], key: str) -> int:
    ...


@overload
def get_item(container: List[str], key: int) -> str:
    ...


def get_item(container: Union[Dict[str, int], List[str]], key: Union[str, int]) -> Union[int, str]:
    """
    Get item with overloaded signatures.
    Tests: @overload decorator with multiple type signatures.
    """
    if isinstance(container, dict) and isinstance(key, str):
        return container[key]
    elif isinstance(container, list) and isinstance(key, int):
        return container[key]
    raise TypeError("Invalid types")


# ==============================================================================
# Dataclass with Complex Types
# ==============================================================================

@dataclass
class ComplexDataClass:
    """
    Dataclass with complex type annotations.
    Tests: Dataclass fields with nested generics.
    """

    # Simple types
    name: str
    age: int

    # Optional with default
    email: Optional[str] = None

    # Generic collection types
    tags: List[str] = None
    metadata: Dict[str, Any] = None

    # Complex nested types
    attributes: Dict[str, List[Union[int, str, bool]]] = None

    # Callable field
    validator: Optional[Callable[[str], bool]] = None

    # ClassVar
    instance_count: ClassVar[int] = 0

    def __post_init__(self) -> None:
        """Post-init with type annotations."""
        if self.tags is None:
            self.tags = []
        if self.metadata is None:
            self.metadata = {}
        if self.attributes is None:
            self.attributes = {}
        ComplexDataClass.instance_count += 1


# ==============================================================================
# Advanced Generic Patterns
# ==============================================================================

def deep_merge(
    dict1: Dict[K, V],
    dict2: Dict[K, V]
) -> Dict[K, V]:
    """
    Deep merge two dictionaries.
    Tests: Generic function with TypeVar usage.
    """
    result: Dict[K, V] = dict1.copy()
    result.update(dict2)
    return result


def map_values(
    mapping: Mapping[K, V],
    transform: Callable[[V], T]
) -> Dict[K, T]:
    """
    Map values with transformation.
    Tests: Mapping[K, V] -> Dict[K, T] with transformation.
    """
    return {k: transform(v) for k, v in mapping.items()}


def flatten_nested_lists(
    nested: List[List[T]]
) -> List[T]:
    """
    Flatten nested lists.
    Tests: List[List[T]] -> List[T]
    """
    result: List[T] = []
    for sublist in nested:
        result.extend(sublist)
    return result


# ==============================================================================
# Iterator and Generator Types
# ==============================================================================

def generate_items(
    count: int
) -> Iterator[Tuple[int, str]]:
    """
    Generate items as iterator.
    Tests: Iterator[Tuple[int, str]] return type.
    """
    for i in range(count):
        yield (i, f"item_{i}")


def iterate_with_transform(
    items: Iterable[T],
    transform: Callable[[T], V]
) -> Iterator[V]:
    """
    Iterate with transformation.
    Tests: Iterable[T] + Callable[[T], V] -> Iterator[V]
    """
    for item in items:
        yield transform(item)
