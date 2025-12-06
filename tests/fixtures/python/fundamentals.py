"""Test fixture for fundamental Python patterns.

This file contains various comprehensions, lambda functions, and other
fundamental Python patterns for extraction testing.
"""

simple_list_comp = list(range(10))
squared_list_comp = [x * x for x in range(10)]
filtered_list_comp = [x for x in range(20) if x % 2 == 0]
complex_filter = [x for x in range(100) if x > 10 and x < 50]


simple_dict_comp = {x: x * 2 for x in range(5)}
filtered_dict_comp = {k: v for k, v in items.items() if v > 0}
key_value_comp = {str(i): i**2 for i in range(10)}


simple_set_comp = set(range(10))
filtered_set_comp = {x for x in numbers if x > 0}
unique_letters = {char.lower() for char in text if char.isalpha()}


simple_gen = (x for x in range(10))
squared_gen = (x * x for x in range(100))
filtered_gen = (x for x in data if predicate(x))


matrix = [[i * j for j in range(3)] for i in range(3)]
flattened = [item for sublist in nested_list for item in sublist]


def simple_lambda(x):
    return x + 1


def double(x):
    return x * 2


def add_ten(x):
    return x + 10


def add(x, y):
    return x + y


def multiply(x, y):
    return x * y


def subtract(x, y, z):
    return x - y - z


multiplier = 5


def scale(x):
    return x * multiplier


def make_adder(n):
    """Function that returns lambda capturing 'n'"""
    return lambda x: x + n


numbers = [1, 2, 3, 4, 5]


doubled = [x * 2 for x in numbers]


evens = list(filter(lambda x: x % 2 == 0, numbers))


data = [(1, "b"), (2, "a"), (3, "c")]
sorted_data = sorted(data, key=lambda x: x[1])


def processor(x):
    return x.strip().lower()


def apply_func(func, value):
    return func(value)


result = apply_func(lambda x: x**2, 5)


def process_data(items):
    """Function with comprehensions and lambdas."""

    filtered = [x for x in items if x > 0]

    transformed = (x * 2 for x in filtered)

    {item: item**2 for item in filtered}

    (x for x in filtered if x % 2 == 0)

    return list(transformed)


def advanced_patterns():
    """Advanced comprehension and lambda patterns."""

    matrix = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    transposed = [[row[i] for row in matrix] for i in range(3)]

    [x for x in range(100) if x % 2 == 0 if x % 3 == 0]

    from functools import reduce

    reduce(lambda x, y: x * y, [1, 2, 3, 4, 5])

    data = [("apple", 5), ("banana", 2), ("cherry", 8)]
    max(data, key=lambda item: item[1])

    return transposed


empty_list = []
empty_dict = dict({}.items())


def with_default(x, y=10):
    return x + y


def variadic(*args):
    return sum(args)


def keyword_lambda(**kwargs):
    return kwargs.get("key", "default")


nested_arg = list(range(10))
