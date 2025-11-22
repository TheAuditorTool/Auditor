"""
Python generator patterns for testing extract_generators().

Test fixture demonstrating:
- Generator functions (yield)
- Generator expressions
- yield from (delegation)
- send() usage (bidirectional communication)
- Infinite generators (DoS risk)
"""

# 1. Simple generator function
def count_up_to(n):
    """Basic generator - yields values 0 to n."""
    i = 0
    while i < n:
        yield i
        i += 1


# 2. Generator with multiple yields
def fibonacci():
    """Generator with multiple yield statements."""
    a, b = 0, 1
    yield a
    yield b
    while True:
        a, b = b, a + b
        yield b


# 3. Infinite generator (SECURITY RISK: DoS if not controlled)
def infinite_stream():
    """Infinite generator - while True with yield (DoS risk)."""
    counter = 0
    while True:
        yield counter
        counter += 1


# 4. Generator with yield from (delegation)
def delegating_generator():
    """Generator using yield from to delegate to another generator."""
    yield from range(5)
    yield from count_up_to(3)


# 5. Generator with send() usage (bidirectional communication)
def accumulator():
    """Generator with send() - bidirectional communication."""
    total = 0
    while True:
        value = yield total
        if value is not None:
            total += value


# 6. Generator with conditional yields
def filter_positives(numbers):
    """Generator with conditional yield."""
    for num in numbers:
        if num > 0:
            yield num


# 7. Generator that yields tuples
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


# 8. Generator with yield from in loop (multiple delegations)
def chain_generators(*generators):
    """Chain multiple generators using yield from."""
    for generator in generators:
        yield from generator


# 9. Generator expression in function (NOT a generator function itself)
def process_data(items):
    """Function using generator expression (not a generator function)."""
    # Generator expression: (x for x in iterable)
    squares = (x * x for x in items)
    return list(squares)


# 10. Generator expression in list comprehension context
def sum_squares(n):
    """Function with generator expression for memory efficiency."""
    return sum(x * x for x in range(n))


# 11. Nested generator expression
def flatten_matrix(matrix):
    """Generator expression with nested iteration."""
    return list(item for row in matrix for item in row)


# 12. Generator with exception handling
def safe_generator(items):
    """Generator with try/except around yield."""
    for item in items:
        try:
            yield item * 2
        except TypeError:
            yield None


# 13. Generator using send() with initial value
def coroutine_style():
    """Coroutine-style generator with send() usage."""
    value = yield
    while value is not None:
        result = value * 2
        value = yield result


# 14. Generator with yield from and send()
def delegating_coroutine():
    """Generator using both yield from and send()."""
    result = yield from accumulator()
    return result


# 15. Infinite generator with conditional break (NOT infinite)
def pseudo_infinite():
    """Looks infinite but has break condition (NOT flagged as infinite)."""
    counter = 0
    while True:
        if counter > 1000:
            break
        yield counter
        counter += 1


# 16. Generator with no yields (regular function, not a generator)
def regular_function():
    """Regular function, no yield - should NOT be extracted."""
    return 42


# 17. Multiple generator expressions in same function
def multi_generator_expressions(data):
    """Function with multiple generator expressions."""
    evens = (x for x in data if x % 2 == 0)
    odds = (x for x in data if x % 2 != 0)
    return list(evens), list(odds)


# 18. Generator with yield in nested function
def outer_generator():
    """Generator with nested function (inner not extracted separately)."""
    def inner():
        yield 1
        yield 2

    yield from inner()
    yield 3


# Security Patterns Demonstrated:
# - infinite_stream: while True with yield = DoS risk (resource exhaustion)
# - fibonacci: infinite generator without break (memory leak if not controlled)
# - accumulator, coroutine_style: send() usage = bidirectional taint flow
# - delegating_generator, chain_generators: yield from = taint propagation through delegation
# - Generator expressions: memory efficiency but potential for resource exhaustion in hot paths
