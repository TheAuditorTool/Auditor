"""Test fixture for performance pattern extraction.

This file contains examples of all performance patterns that should be extracted:
- Loop complexity (nested loops, growing operations)
- Resource usage (large allocations, file handles)
- Memoization (lru_cache, manual caching, opportunities)

Expected extractions:
- ~12 loop complexity patterns
- ~8 resource usage patterns
- ~6 memoization patterns
"""

import functools


def simple_loop():
    """Test simple O(n) loop."""
    result = []
    for i in range(100):
        result.append(i * 2)
    return result


def nested_loop_2d():
    """Test nested loop O(n^2)."""
    matrix = []
    for i in range(10):
        row = []
        for j in range(10):
            row.append(i * j)
        matrix.append(row)
    return matrix


def nested_loop_3d():
    """Test triple nested loop O(n^3)."""
    cube = []
    for i in range(5):
        plane = []
        for j in range(5):
            row = []
            for k in range(5):
                row.append(i + j + k)
            plane.append(row)
        cube.append(plane)
    return cube


def while_loop():
    """Test while loop."""
    count = 0
    while count < 100:
        count += 1
    return count


def list_comprehension():
    """Test list comprehension (implicit loop)."""
    return [x * 2 for x in range(100)]


def nested_comprehension():
    """Test nested list comprehension."""
    return [[i * j for j in range(10)] for i in range(10)]


def loop_no_growing():
    """Test loop without growing operations."""
    total = 0
    for i in range(100):
        total += i
    return total


def dict_comprehension():
    """Test dict comprehension."""
    return {i: i**2 for i in range(100)}


def large_list_comprehension():
    """Test large list allocation."""
    return list(range(10000))


def large_dict_literal():
    """Test large dict literal (>100 elements)."""
    data = {str(i): i for i in range(150)}
    return data


def unclosed_file_handle():
    """Test file handle without context manager."""
    f = open("test.txt")
    data = f.read()

    return data


def string_concatenation_loop():
    """Test string concatenation in loop (inefficient)."""
    result = ""
    for i in range(100):
        result += str(i)
    return result


def large_range_comprehension():
    """Test large range in comprehension."""
    return [x**2 for x in range(5000)]


def multiple_large_structures():
    """Test multiple large allocations."""
    list1 = list(range(2000))
    list2 = [x * 2 for x in range(2000)]
    dict1 = {i: i**2 for i in range(200)}
    return list1, list2, dict1


@functools.lru_cache(maxsize=128)
def fibonacci_memoized(n):
    """Test memoized recursive function."""
    if n <= 1:
        return n
    return fibonacci_memoized(n - 1) + fibonacci_memoized(n - 2)


def fibonacci_unmemoized(n):
    """Test unmemoized recursive function (opportunity)."""
    if n <= 1:
        return n
    return fibonacci_unmemoized(n - 1) + fibonacci_unmemoized(n - 2)


@functools.lru_cache(maxsize=256)
def expensive_computation(x, y):
    """Test memoization with custom cache size."""
    return x**y + y**x


_manual_cache = {}


def manual_cache_function(key):
    """Test manual caching pattern."""
    if key in _manual_cache:
        return _manual_cache[key]

    result = key**2
    _manual_cache[key] = result
    return result


def non_recursive_function(x):
    """Test non-recursive function (no memoization needed)."""
    return x * 2


@functools.lru_cache
def memoized_no_maxsize(data):
    """Test lru_cache without maxsize (unbounded)."""
    return len(data) * 2


def matrix_multiplication(a, b):
    """Test O(n^3) algorithm with growing operations."""
    n = len(a)
    result = []
    for i in range(n):
        row = []
        for j in range(n):
            value = 0
            for k in range(n):
                value += a[i][k] * b[k][j]
            row.append(value)
        result.append(row)
    return result


def process_large_dataset():
    """Test multiple performance patterns together."""

    data = list(range(10000))

    transformed = []
    for i in range(len(data)):
        if i % 2 == 0:
            for j in range(10):
                transformed.append(data[i] * j)

    output = ""
    for val in transformed[:100]:
        output += str(val) + ","

    return output


@functools.lru_cache(maxsize=512)
def recursive_with_cache(n, memo=None):
    """Test recursive function with both lru_cache and manual cache."""
    if n <= 0:
        return 1
    return n * recursive_with_cache(n - 1)


def nested_loop_search(matrix, target):
    """Test nested loop search O(n^2)."""
    for i in range(len(matrix)):
        for j in range(len(matrix[i])):
            if matrix[i][j] == target:
                return (i, j)
    return None


def triple_nested_tensor_op(tensor):
    """Test O(n^4) operation."""
    result = []
    for i in range(len(tensor)):
        plane = []
        for j in range(len(tensor[i])):
            row = []
            for k in range(len(tensor[i][j])):
                col = []
                for l in range(len(tensor[i][j][k])):
                    col.append(tensor[i][j][k][l] ** 2)
                row.append(col)
            plane.append(row)
        result.append(plane)
    return result
