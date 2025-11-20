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


# ============================================================================
# PATTERN 1: Loop Complexity
# ============================================================================

def simple_loop():
    """Test simple O(n) loop."""
    result = []
    for i in range(100):
        result.append(i * 2)  # Growing operation
    return result


def nested_loop_2d():
    """Test nested loop O(n^2)."""
    matrix = []
    for i in range(10):
        row = []
        for j in range(10):  # Nested loop (nesting level 2)
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
            for k in range(5):  # Triple nested (nesting level 3)
                row.append(i + j + k)
            plane.append(row)
        cube.append(plane)
    return cube


def while_loop():
    """Test while loop."""
    count = 0
    while count < 100:  # While loop
        count += 1
    return count


def list_comprehension():
    """Test list comprehension (implicit loop)."""
    return [x * 2 for x in range(100)]  # Comprehension (nesting level 1)


def nested_comprehension():
    """Test nested list comprehension."""
    return [[i * j for j in range(10)] for i in range(10)]  # Nested comprehension (nesting level 2)


def loop_no_growing():
    """Test loop without growing operations."""
    total = 0
    for i in range(100):
        total += i  # Augmented assignment (counted as growing operation)
    return total


def dict_comprehension():
    """Test dict comprehension."""
    return {i: i ** 2 for i in range(100)}  # Dict comprehension


# ============================================================================
# PATTERN 2: Resource Usage
# ============================================================================

def large_list_comprehension():
    """Test large list allocation."""
    return [x for x in range(10000)]  # Large list (>1000 elements)


def large_dict_literal():
    """Test large dict literal (>100 elements)."""
    data = {str(i): i for i in range(150)}  # Large dict
    return data


def unclosed_file_handle():
    """Test file handle without context manager."""
    f = open("test.txt")  # File handle without cleanup
    data = f.read()
    # No f.close() - missing cleanup
    return data


def string_concatenation_loop():
    """Test string concatenation in loop (inefficient)."""
    result = ""
    for i in range(100):
        result += str(i)  # String concat in loop (resource usage)
    return result


def large_range_comprehension():
    """Test large range in comprehension."""
    return [x ** 2 for x in range(5000)]  # Large range


def multiple_large_structures():
    """Test multiple large allocations."""
    list1 = [x for x in range(2000)]  # Large list 1
    list2 = [x * 2 for x in range(2000)]  # Large list 2
    dict1 = {i: i ** 2 for i in range(200)}  # Large dict
    return list1, list2, dict1


# ============================================================================
# PATTERN 3: Memoization
# ============================================================================

@functools.lru_cache(maxsize=128)
def fibonacci_memoized(n):
    """Test memoized recursive function."""
    if n <= 1:
        return n
    return fibonacci_memoized(n - 1) + fibonacci_memoized(n - 2)  # Recursive with memoization


def fibonacci_unmemoized(n):
    """Test unmemoized recursive function (opportunity)."""
    if n <= 1:
        return n
    return fibonacci_unmemoized(n - 1) + fibonacci_unmemoized(n - 2)  # Recursive WITHOUT memoization


@functools.lru_cache(maxsize=256)
def expensive_computation(x, y):
    """Test memoization with custom cache size."""
    return x ** y + y ** x  # Expensive computation with LRU cache


# Manual cache example
_manual_cache = {}

def manual_cache_function(key):
    """Test manual caching pattern."""
    if key in _manual_cache:
        return _manual_cache[key]  # Manual cache hit

    result = key ** 2  # Compute
    _manual_cache[key] = result  # Store in manual cache
    return result


def non_recursive_function(x):
    """Test non-recursive function (no memoization needed)."""
    return x * 2  # Simple function, no memoization


@functools.lru_cache
def memoized_no_maxsize(data):
    """Test lru_cache without maxsize (unbounded)."""
    return len(data) * 2  # Memoized, no cache size limit


# ============================================================================
# COMBINED PATTERNS (Complex Real-World Example)
# ============================================================================

def matrix_multiplication(a, b):
    """Test O(n^3) algorithm with growing operations."""
    n = len(a)
    result = []
    for i in range(n):
        row = []
        for j in range(n):
            value = 0
            for k in range(n):  # Triple nested loop (O(n^3))
                value += a[i][k] * b[k][j]  # Augmented assignment (growing operation)
            row.append(value)  # Growing operation
        result.append(row)  # Growing operation
    return result


def process_large_dataset():
    """Test multiple performance patterns together."""
    # Large allocation
    data = [x for x in range(10000)]  # Large list

    # Nested loops with growing operations
    transformed = []
    for i in range(len(data)):
        if i % 2 == 0:
            for j in range(10):  # Nested loop
                transformed.append(data[i] * j)  # Growing operation

    # String concatenation (inefficient)
    output = ""
    for val in transformed[:100]:
        output += str(val) + ","  # String concat in loop

    return output


@functools.lru_cache(maxsize=512)
def recursive_with_cache(n, memo=None):
    """Test recursive function with both lru_cache and manual cache."""
    if n <= 0:
        return 1
    return n * recursive_with_cache(n - 1)  # Recursive with memoization


def nested_loop_search(matrix, target):
    """Test nested loop search O(n^2)."""
    for i in range(len(matrix)):
        for j in range(len(matrix[i])):  # Nested loop
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
                for l in range(len(tensor[i][j][k])):  # 4-level nesting
                    col.append(tensor[i][j][k][l] ** 2)
                row.append(col)
            plane.append(row)
        result.append(plane)
    return result
