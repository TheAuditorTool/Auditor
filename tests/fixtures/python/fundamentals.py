"""Test fixture for fundamental Python patterns.

This file contains various comprehensions, lambda functions, and other
fundamental Python patterns for extraction testing.
"""

# ============================================================================
# COMPREHENSIONS
# ============================================================================

# List comprehensions
simple_list_comp = [x for x in range(10)]
squared_list_comp = [x * x for x in range(10)]
filtered_list_comp = [x for x in range(20) if x % 2 == 0]
complex_filter = [x for x in range(100) if x > 10 and x < 50]

# Dict comprehensions
simple_dict_comp = {x: x * 2 for x in range(5)}
filtered_dict_comp = {k: v for k, v in items.items() if v > 0}
key_value_comp = {str(i): i ** 2 for i in range(10)}

# Set comprehensions
simple_set_comp = {x for x in range(10)}
filtered_set_comp = {x for x in numbers if x > 0}
unique_letters = {char.lower() for char in text if char.isalpha()}

# Generator expressions
simple_gen = (x for x in range(10))
squared_gen = (x * x for x in range(100))
filtered_gen = (x for x in data if predicate(x))

# Nested comprehensions (nesting_level = 2)
matrix = [[i * j for j in range(3)] for i in range(3)]
flattened = [item for sublist in nested_list for item in sublist]

# ============================================================================
# LAMBDA FUNCTIONS
# ============================================================================

# Simple lambdas
simple_lambda = lambda x: x + 1
double = lambda x: x * 2
add_ten = lambda x: x + 10

# Multi-parameter lambdas
add = lambda x, y: x + y
multiply = lambda x, y: x * y
subtract = lambda x, y, z: x - y - z

# Lambdas with closures (captures outer variables)
multiplier = 5
scale = lambda x: x * multiplier  # Captures 'multiplier'

def make_adder(n):
    """Function that returns lambda capturing 'n'"""
    return lambda x: x + n  # Captures 'n' from outer scope

# Lambda usage contexts
numbers = [1, 2, 3, 4, 5]

# Used in map
doubled = list(map(lambda x: x * 2, numbers))

# Used in filter
evens = list(filter(lambda x: x % 2 == 0, numbers))

# Used in sorted with key
data = [(1, 'b'), (2, 'a'), (3, 'c')]
sorted_data = sorted(data, key=lambda x: x[1])

# Lambda in assignment
processor = lambda x: x.strip().lower()

# Lambda as function argument
def apply_func(func, value):
    return func(value)

result = apply_func(lambda x: x ** 2, 5)

# ============================================================================
# MIXED PATTERNS
# ============================================================================

def process_data(items):
    """Function with comprehensions and lambdas."""
    # List comprehension with filter
    filtered = [x for x in items if x > 0]

    # Lambda in map
    transformed = map(lambda x: x * 2, filtered)

    # Dict comprehension
    lookup = {item: item ** 2 for item in filtered}

    # Generator expression
    gen = (x for x in filtered if x % 2 == 0)

    # Lambda with closure
    threshold = 10
    check = lambda x: x > threshold

    return list(transformed)

def advanced_patterns():
    """Advanced comprehension and lambda patterns."""
    # Nested comprehension
    matrix = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    transposed = [[row[i] for row in matrix] for i in range(3)]

    # Comprehension with multiple filters
    result = [x for x in range(100)
              if x % 2 == 0
              if x % 3 == 0]

    # Lambda in reduce
    from functools import reduce
    product = reduce(lambda x, y: x * y, [1, 2, 3, 4, 5])

    # Lambda in max/min with key
    data = [('apple', 5), ('banana', 2), ('cherry', 8)]
    most_expensive = max(data, key=lambda item: item[1])

    return transposed

# ============================================================================
# EDGE CASES
# ============================================================================

# Empty comprehensions
empty_list = [x for x in []]
empty_dict = {k: v for k, v in {}.items()}

# Lambda with default arguments
with_default = lambda x, y=10: x + y

# Lambda with *args
variadic = lambda *args: sum(args)

# Lambda with **kwargs
keyword_lambda = lambda **kwargs: kwargs.get('key', 'default')

# Comprehension in comprehension argument
nested_arg = [x for x in [y for y in range(10)]]
