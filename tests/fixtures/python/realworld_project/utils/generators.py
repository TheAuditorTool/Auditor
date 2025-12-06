"""
Python generator patterns for testing extract_generators().

Test fixture demonstrating:
- Generator functions (yield)
- Generator expressions
- yield from (delegation)
- send() usage (bidirectional communication)
- Infinite generators (DoS risk)
"""


def count_up_to(n):
    """Basic generator - yields values 0 to n."""
    i = 0
    while i < n:
        yield i
        i += 1


def fibonacci():
    """Generator with multiple yield statements."""
    a, b = 0, 1
    yield a
    yield b
    while True:
        a, b = b, a + b
        yield b


def infinite_stream():
    """Infinite generator - while True with yield (DoS risk)."""
    counter = 0
    while True:
        yield counter
        counter += 1


def delegating_generator():
    """Generator using yield from to delegate to another generator."""
    yield from range(5)
    yield from count_up_to(3)


def accumulator():
    """Generator with send() - bidirectional communication."""
    total = 0
    while True:
        value = yield total
        if value is not None:
            total += value


def filter_positives(numbers):
    """Generator with conditional yield."""
    for num in numbers:
        if num > 0:
            yield num


def pairs(iterable):
    """Generator yielding pairs of elements."""
    it = iter(iterable)
    while True:
        try:
            a = next(it)
            b = next(it)
            yield (a, b)
        except StopIteration:
            break


def chain_generators(*generators):
    """Chain multiple generators using yield from."""
    for generator in generators:
        yield from generator


def process_data(items):
    """Function using generator expression (not a generator function)."""

    squares = (x * x for x in items)
    return list(squares)


def sum_squares(n):
    """Function with generator expression for memory efficiency."""
    return sum(x * x for x in range(n))


def flatten_matrix(matrix):
    """Generator expression with nested iteration."""
    return [item for row in matrix for item in row]


def safe_generator(items):
    """Generator with try/except around yield."""
    for item in items:
        try:
            yield item * 2
        except TypeError:
            yield None


def coroutine_style():
    """Coroutine-style generator with send() usage."""
    value = yield
    while value is not None:
        result = value * 2
        value = yield result


def delegating_coroutine():
    """Generator using both yield from and send()."""
    result = yield from accumulator()
    return result


def pseudo_infinite():
    """Looks infinite but has break condition (NOT flagged as infinite)."""
    counter = 0
    while True:
        if counter > 1000:
            break
        yield counter
        counter += 1


def regular_function():
    """Regular function, no yield - should NOT be extracted."""
    return 42


def multi_generator_expressions(data):
    """Function with multiple generator expressions."""
    evens = (x for x in data if x % 2 == 0)
    odds = (x for x in data if x % 2 != 0)
    return list(evens), list(odds)


def outer_generator():
    """Generator with nested function (inner not extracted separately)."""

    def inner():
        yield 1
        yield 2

    yield from inner()
    yield 3
