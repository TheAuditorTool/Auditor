"""Test fixture for state mutation pattern extraction.

This file contains various state mutation patterns to verify extraction correctness.
Used by: Task 1.1.2 verification of extract_instance_mutations()

Expected extractions:
- Instance mutations: 8 total (2 in __init__, 6 in other methods)
- Class mutations: 2 total
- Global mutations: 2 total
- Argument mutations: 3 total
- Augmented assignments: multiple across all categories
"""


class Counter:
    """Test class for instance mutations."""

    instances = 0

    def __init__(self):
        """Expected mutations in constructor."""
        self.count = 0
        self.items = []
        Counter.instances += 1

    def increment(self):
        """Unexpected mutation - SIDE EFFECT."""
        self.count += 1

    def add_item(self, item):
        """Method call mutation - SIDE EFFECT."""
        self.items.append(item)

    def reset(self):
        """Direct assignment mutation - SIDE EFFECT."""
        self.count = 0

    def clear_items(self):
        """Method call mutation - SIDE EFFECT."""
        self.items.clear()

    def update_multiple(self):
        """Multiple mutations in single method - SIDE EFFECTS."""
        self.count += 1
        self.items.append("new")
        self.status = "updated"


class ConfigHolder:
    """Test nested attribute mutations."""

    def __init__(self):
        """Setup nested object."""
        self.config = type("obj", (object,), {})()
        self.config.debug = False

    def enable_debug(self):
        """Nested mutation - SIDE EFFECT."""
        self.config.debug = True


class Temperature:
    """Test property setter detection."""

    def __init__(self):
        self._celsius = 0

    @property
    def celsius(self):
        """Getter has no mutations."""
        return self._celsius

    @celsius.setter
    def celsius(self, value):
        """Setter mutation is expected (is_property_setter=True)."""
        self._celsius = value


class CustomList:
    """Test dunder method detection."""

    def __init__(self):
        self._data = []

    def __setitem__(self, key, value):
        """Dunder method with expected mutations."""
        self._data.append((key, value))


class Singleton:
    """Test class attribute mutations."""

    _instance = None
    call_count = 0

    @classmethod
    def get_instance(cls):
        """Class method with class mutation."""
        if cls._instance is None:
            cls._instance = Singleton()
        cls.call_count += 1
        return cls._instance


def standalone_class_mutation():
    """Function with direct class mutation."""
    Counter.instances = 0


_global_cache = {}
_global_counter = 0


def update_cache(key, value):
    """Global mutation example."""
    global _global_cache
    _global_cache[key] = value


def increment_counter():
    """Global augmented assignment."""
    global _global_counter
    _global_counter += 1


def modify_list(items):
    """Mutates list argument - SIDE EFFECT."""
    items.append("modified")  # Argument mutation (type: append)


def modify_dict(data):
    """Mutates dict argument - SIDE EFFECT."""
    data["modified"] = True  # Argument mutation (type: setitem)


def modify_set(elements):
    """Mutates set argument - SIDE EFFECT."""
    elements.add("new_element")  # Argument mutation (type: add)


def pure_calculation(x, y):
    """Pure function with no mutations."""
    result = x + y
    return result


class ImmutableCounter:
    """Immutable pattern - no mutations outside __init__."""

    def __init__(self, initial):
        self.value = initial

    def incremented(self):
        """Returns new instance instead of mutating."""
        return ImmutableCounter(self.value + 1)
