"""Test fixture for behavioral pattern extraction.

This file contains examples of all behavioral patterns that should be extracted:
- Recursion (direct, mutual, tail)
- Generator yields (enhanced)
- Properties (computed, validated)
- Dynamic attributes (__getattr__, __setattr__, etc.)

Expected extractions:
- ~8 recursion patterns
- ~10 generator yields
- ~6 property patterns
- ~4 dynamic attribute patterns
"""


def factorial(n):
    """Test direct recursion with base case."""
    if n <= 0:
        return 1
    return n * factorial(n - 1)


def tail_factorial(n, acc=1):
    """Test tail recursion."""
    if n <= 0:
        return acc
    return tail_factorial(n - 1, n * acc)


def fibonacci(n):
    """Test direct recursion with multiple base cases."""
    if n <= 0:
        return 0
    if n == 1:
        return 1
    return fibonacci(n - 1) + fibonacci(n - 2)


def is_even(n):
    """Test mutual recursion (is_even calls is_odd)."""
    if n == 0:
        return True
    return is_odd(n - 1)


def is_odd(n):
    """Test mutual recursion (is_odd calls is_even)."""
    if n == 0:
        return False
    return is_even(n - 1)


async def async_countdown(n):
    """Test async recursion."""
    if n <= 0:
        return
    await async_countdown(n - 1)


def simple_generator():
    """Test simple yield."""
    yield 1
    yield 2
    yield 3


def conditional_generator(n):
    """Test conditional yield."""
    for i in range(n):
        if i % 2 == 0:
            yield i


def generator_with_loop():
    """Test yield in loop."""
    for x in [1, 2, 3, 4, 5]:
        yield x * 2


def yield_from_example():
    """Test yield from delegation."""
    yield from range(10)
    yield from simple_generator()


def filtered_generator(data):
    """Test yield with filtering."""
    for item in data:
        if item > 0:
            yield item


def nested_loop_generator():
    """Test yield in nested loop."""
    for i in range(3):
        for j in range(3):
            yield (i, j)


class Rectangle:
    """Test property patterns."""

    def __init__(self, width, height):
        self._width = width
        self._height = height

    @property
    def width(self):
        """Simple property getter (just returns stored value)."""
        return self._width

    @width.setter
    def width(self, value):
        """Property setter with validation."""
        if value < 0:
            raise ValueError("Width cannot be negative")
        self._width = value

    @property
    def area(self):
        """Computed property (has computation)."""
        return self._width * self._height

    @property
    def perimeter(self):
        """Another computed property."""
        return 2 * (self._width + self._height)

    @area.setter
    def area(self, value):
        """Property setter without validation (just assignment)."""
        self._area_cache = value

    @property.deleter
    def area(self):
        """Property deleter."""
        del self._area_cache


class User:
    """Test another property pattern."""

    def __init__(self, name):
        self._name = name
        self._age = 0

    @property
    def name(self):
        """Simple getter."""
        return self._name

    @property
    def age(self):
        """Simple getter."""
        return self._age

    @age.setter
    def age(self, value):
        """Setter with validation."""
        if value < 0 or value > 150:
            raise ValueError("Invalid age")
        self._age = value


class DynamicDict:
    """Test __getattr__ and __setattr__ patterns."""

    def __init__(self):
        self._data = {}

    def __getattr__(self, name):
        """Dynamic attribute access (fallback)."""
        return self._data.get(name)

    def __setattr__(self, name, value):
        """Dynamic attribute assignment."""
        if name == "_data":
            object.__setattr__(self, name, value)
        else:
            self._data[name] = value


class ValidatedAttributes:
    """Test __setattr__ with validation."""

    def __init__(self):
        self._validated = {}

    def __setattr__(self, name, value):
        """Validate attributes on assignment."""
        if name == "_validated":
            object.__setattr__(self, name, value)
        else:
            if not isinstance(value, (int, str)):
                raise TypeError("Only int and str allowed")
            self._validated[name] = value


class ProxyClass:
    """Test __getattribute__ (intercepts ALL attribute access)."""

    def __init__(self, wrapped):
        object.__setattr__(self, "_wrapped", wrapped)

    def __getattribute__(self, name):
        """Intercept all attribute access."""
        if name == "_wrapped":
            return object.__getattribute__(self, name)
        wrapped = object.__getattribute__(self, "_wrapped")
        return getattr(wrapped, name)


class ResourceManager:
    """Test __delattr__ pattern."""

    def __init__(self):
        self._resources = {}

    def __delattr__(self, name):
        """Custom deletion logic."""
        if name in self._resources:
            self._resources[name].cleanup()
            del self._resources[name]


class LazyProperty:
    """Descriptor implementing lazy property pattern."""

    def __init__(self, func):
        self.func = func
        self.name = func.__name__

    def __get__(self, instance, owner):
        """Lazy evaluation of property."""
        if instance is None:
            return self

        value = self.func(instance)
        setattr(instance, self.name, value)
        return value


class TreeNode:
    """Test recursion + properties + generators together."""

    def __init__(self, value, left=None, right=None):
        self._value = value
        self._left = left
        self._right = right

    @property
    def value(self):
        """Simple property getter."""
        return self._value

    @property
    def height(self):
        """Computed property with recursion."""
        if self._left is None and self._right is None:
            return 0
        left_height = self._left.height if self._left else 0
        right_height = self._right.height if self._right else 0
        return 1 + max(left_height, right_height)

    def inorder_traversal(self):
        """Generator with recursion."""
        if self._left:
            yield from self._left.inorder_traversal()
        yield self._value
        if self._right:
            yield from self._right.inorder_traversal()


def tree_search(node, target):
    """Recursive tree search."""
    if node is None:
        return False
    if node.value == target:
        return True

    return tree_search(node._left, target) or tree_search(node._right, target)
