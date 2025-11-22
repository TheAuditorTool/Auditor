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


# ============================================================================
# Instance Mutations (self.x = value)
# ============================================================================

class Counter:
    """Test class for instance mutations."""

    instances = 0  # Class attribute (not an instance mutation)

    def __init__(self):
        """Expected mutations in constructor."""
        self.count = 0  # Expected mutation (is_init=True)
        self.items = []  # Expected mutation (is_init=True)
        Counter.instances += 1  # Class mutation (will be extracted separately)

    def increment(self):
        """Unexpected mutation - SIDE EFFECT."""
        self.count += 1  # Augmented assignment mutation (is_init=False)

    def add_item(self, item):
        """Method call mutation - SIDE EFFECT."""
        self.items.append(item)  # Method call mutation (is_init=False)

    def reset(self):
        """Direct assignment mutation - SIDE EFFECT."""
        self.count = 0  # Direct assignment mutation (is_init=False)

    def clear_items(self):
        """Method call mutation - SIDE EFFECT."""
        self.items.clear()  # Method call mutation (is_init=False)

    def update_multiple(self):
        """Multiple mutations in single method - SIDE EFFECTS."""
        self.count += 1  # Augmented mutation
        self.items.append("new")  # Method call mutation
        self.status = "updated"  # New attribute creation (direct assignment)


# ============================================================================
# Nested Attribute Mutations (self.config.x = value)
# ============================================================================

class ConfigHolder:
    """Test nested attribute mutations."""

    def __init__(self):
        """Setup nested object."""
        self.config = type('obj', (object,), {})()  # Create simple object
        self.config.debug = False  # Nested attribute mutation (is_init=True)

    def enable_debug(self):
        """Nested mutation - SIDE EFFECT."""
        self.config.debug = True  # Nested attribute mutation (is_init=False)


# ============================================================================
# Property Setters (Expected Mutations)
# ============================================================================

class Temperature:
    """Test property setter detection."""

    def __init__(self):
        self._celsius = 0  # Expected mutation (is_init=True)

    @property
    def celsius(self):
        """Getter has no mutations."""
        return self._celsius

    @celsius.setter
    def celsius(self, value):
        """Setter mutation is expected (is_property_setter=True)."""
        self._celsius = value  # Expected mutation in property setter


# ============================================================================
# Dunder Methods (Expected Mutations)
# ============================================================================

class CustomList:
    """Test dunder method detection."""

    def __init__(self):
        self._data = []  # Expected mutation (is_init=True, is_dunder_method=True)

    def __setitem__(self, key, value):
        """Dunder method with expected mutations."""
        self._data.append((key, value))  # Expected mutation (is_dunder_method=True)


# ============================================================================
# Class Mutations (ClassName.x = value, cls.x = value)
# ============================================================================

class Singleton:
    """Test class attribute mutations."""

    _instance = None  # Class attribute
    call_count = 0  # Class attribute

    @classmethod
    def get_instance(cls):
        """Class method with class mutation."""
        if cls._instance is None:
            cls._instance = Singleton()  # Class mutation (cls.x = value)
        cls.call_count += 1  # Class mutation (cls.x += 1)
        return cls._instance


def standalone_class_mutation():
    """Function with direct class mutation."""
    Counter.instances = 0  # Class mutation (ClassName.x = value)


# ============================================================================
# Global Mutations (global x; x = value)
# ============================================================================

_global_cache = {}
_global_counter = 0


def update_cache(key, value):
    """Global mutation example."""
    global _global_cache
    _global_cache[key] = value  # Global mutation


def increment_counter():
    """Global augmented assignment."""
    global _global_counter
    _global_counter += 1  # Global mutation with augmented assignment


# ============================================================================
# Argument Mutations (def foo(lst): lst.append(x))
# ============================================================================

def modify_list(items):
    """Mutates list argument - SIDE EFFECT."""
    items.append("modified")  # Argument mutation (type: append)


def modify_dict(data):
    """Mutates dict argument - SIDE EFFECT."""
    data["modified"] = True  # Argument mutation (type: setitem)


def modify_set(elements):
    """Mutates set argument - SIDE EFFECT."""
    elements.add("new_element")  # Argument mutation (type: add)


# ============================================================================
# Pure Functions (NO mutations - control group)
# ============================================================================

def pure_calculation(x, y):
    """Pure function with no mutations."""
    result = x + y  # Local variable (not a mutation)
    return result  # No side effects


class ImmutableCounter:
    """Immutable pattern - no mutations outside __init__."""

    def __init__(self, initial):
        self.value = initial  # Expected mutation (is_init=True)

    def incremented(self):
        """Returns new instance instead of mutating."""
        return ImmutableCounter(self.value + 1)  # No mutation, returns new object
