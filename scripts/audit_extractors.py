"""
EXTRACTOR OUTPUT AUDIT - TRUTH SERUM

This script runs every Python extractor against a comprehensive sample
and reports the ACTUAL dictionary keys each one returns.

NO GUESSING. NO HALLUCINATING. JUST FACTS.
"""

import ast
import sys
import os

# Add project root to path
sys.path.insert(0, os.getcwd())

from theauditor.ast_extractors.python.utils.context import build_file_context
from theauditor.ast_extractors.python import (
    control_flow_extractors, security_extractors, testing_extractors,
    async_extractors, state_mutation_extractors, exception_flow_extractors,
    data_flow_extractors, behavioral_extractors, performance_extractors,
    fundamental_extractors, operator_extractors, collection_extractors,
    class_feature_extractors, type_extractors, protocol_extractors,
    stdlib_pattern_extractors, advanced_extractors, flask_extractors,
    framework_extractors, django_web_extractors, django_advanced_extractors,
    validation_extractors, orm_extractors, core_extractors,
    task_graphql_extractors
)

# The "Kitchen Sink" Code Sample - triggers as many extractors as possible
CODE = '''
import os
import re
import json
import logging
from typing import List, TypedDict, Literal, Generic, TypeVar, Protocol
from dataclasses import dataclass
from enum import Enum
from abc import ABC, abstractmethod
from contextlib import contextmanager
from functools import lru_cache, cached_property
from itertools import chain
from collections import defaultdict
import threading
import datetime
from pathlib import Path
import weakref
from contextvars import ContextVar

# Flask imports (for framework extractors)
try:
    from flask import Flask, Blueprint, request
    from celery import Celery
except ImportError:
    pass

# Django imports
try:
    from django.db import models
    from django.views.generic import ListView
    from django import forms
    from django.contrib import admin
except ImportError:
    pass

# Global mutation
GLOBAL_VAR = 0
ctx_var: ContextVar[int] = ContextVar('ctx_var', default=0)

T = TypeVar('T')

class Status(Enum):
    ACTIVE = 1
    INACTIVE = 2

class MyProtocol(Protocol):
    def method(self) -> int: ...

class UserDict(TypedDict):
    name: str
    age: int

# Metaclass
class Meta(type):
    pass

# Decorators & Class Features
@dataclass(frozen=True)
class User(ABC, metaclass=Meta):
    name: str
    __slots__ = ['age']

    def __init__(self):
        self.x = 1  # Instance mutation
        self._private = 2
        self.__mangled = 3

    @property
    def prop(self):
        return self.x

    @cached_property
    def cached(self):
        return self.x * 2

    @abstractmethod
    def abstract_method(self): pass

    @classmethod
    def class_method(cls): pass

    @staticmethod
    def static_method(): pass

    def __len__(self): return 0  # Protocol
    def __iter__(self): yield self.x
    def __contains__(self, item): return False
    def __getitem__(self, key): return self.x
    def __setitem__(self, key, value): pass
    def __delitem__(self, key): pass
    def __call__(self): pass
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def __getstate__(self): return {}
    def __setstate__(self, state): pass
    def __copy__(self): return self
    def __deepcopy__(self, memo): return self

    def __get__(self, obj, type=None): return self
    def __set__(self, obj, value): pass
    def __delete__(self, obj): pass

class ChildClass(User):
    """Multiple inheritance test"""
    pass

# Generic class
class Container(Generic[T]):
    def __init__(self, value: T):
        self.value = value

# Async & Control Flow
async def process_data(items: List[int]) -> int:
    global GLOBAL_VAR
    GLOBAL_VAR += 1  # Global mutation

    # Loops
    for i in items:
        pass
    for idx, val in enumerate(items):
        pass
    for k, v in {'a': 1}.items():
        pass
    for x in range(10):
        pass
    for a, b in zip([1], [2]):
        pass

    while True:
        break

    async for item in async_gen():
        pass

    # Branching & Exceptions
    try:
        if len(items) > 10:
            raise ValueError("Too many")
        elif len(items) == 0:
            pass
        else:
            pass
    except ValueError as e:
        logging.error(e)
        raise
    except (TypeError, KeyError):
        pass
    finally:
        cleanup()

    # Match statement (Python 3.10+)
    match items:
        case [x, y]:
            pass
        case _:
            pass

    # Data Flow & I/O
    with open("file.txt", "w") as f:
        f.write("data")  # I/O

    async with async_context():
        pass

    # Operators
    x = 1 + 2
    y = x if x > 0 else 0
    z = x and y or 0
    if (w := 5) > 0:  # Walrus
        pass
    a = x @ y  # Matrix mult
    b = x in [1, 2, 3]
    c = x < y < z  # Chained comparison

    # Collections
    d = {'a': 1}
    d.get('a')
    d.setdefault('b', 2)
    d.update({'c': 3})

    l = [1, 2, 3]
    l.append(4)
    l.extend([5])
    l.pop()

    s = {1, 2, 3}
    s.add(4)
    s.union({5})

    st = "hello"
    st.upper()
    st.split()
    st.format()
    f"{st} world"  # f-string

    # Builtins
    len(l)
    sum(l)
    map(str, l)
    filter(bool, l)
    sorted(l)

    # Comprehensions
    list_comp = [x*2 for x in range(10) if x > 5]
    dict_comp = {k: v for k, v in d.items()}
    set_comp = {x for x in l}
    gen_exp = (x for x in l)

    # Slicing
    sl = l[1:3]
    sl2 = l[::2]

    # Tuple unpacking
    a, b, *rest = [1, 2, 3, 4]

    # None patterns
    if x is None:
        pass
    if x is not None:
        pass

    # Truthiness
    if items:
        pass
    if not items:
        pass

    # Assert & Del
    assert x > 0, "x must be positive"
    del d['a']

    # Break/Continue/Pass
    for i in range(10):
        if i == 5:
            continue
        if i == 8:
            break
        pass

    # Await
    result = await async_func()

    return x

# Generator
def my_generator():
    yield 1
    yield from [2, 3]

# Async generator
async def async_gen():
    yield 1

# Context manager
@contextmanager
def my_context():
    yield

# Lambda
fn = lambda x: x * 2

# Recursion
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

# Memoization
@lru_cache(maxsize=128)
def cached_func(x):
    return x * 2

# Security patterns
def vulnerable_func(user_input):
    # SQL Injection
    query = "SELECT * FROM users WHERE name = " + user_input
    cursor.execute(query)

    # Command Injection
    os.system("ls " + user_input)

    # Path Traversal
    path = "/base/" + user_input
    open(path)

    # Dangerous eval
    eval(user_input)
    exec(user_input)

    # Hardcoded secrets
    password = "secret123"
    api_key = "sk-12345"

# Auth decorator
def requires_auth(f):
    pass

@requires_auth
def protected_route():
    pass

# Testing patterns
def test_something():
    assert 1 == 1
    assert "hello" in "hello world"

class TestCase:
    def setUp(self):
        pass
    def tearDown(self):
        pass
    def test_method(self):
        self.assertEqual(1, 1)
        self.assertTrue(True)
        self.assertRaises(ValueError, int, "x")

# Pytest fixtures
def pytest_fixture():
    pass

# Regex
pattern = re.compile(r'\\d+')
re.match(r'hello', 'hello world')
re.search(r'world', 'hello world')

# JSON
json.dumps({'a': 1})
json.loads('{"a": 1}')

# Datetime
datetime.datetime.now()
datetime.date.today()

# Path
Path('/tmp').exists()
Path('/tmp').mkdir()

# Logging
logger = logging.getLogger(__name__)
logger.info("message")
logger.error("error")

# Threading
lock = threading.Lock()
with lock:
    pass

# Weakref
ref = weakref.ref(User)

# Bytes
b = b'hello'
b.decode('utf-8')
'hello'.encode('utf-8')

# Ellipsis
def stub():
    ...

# Overload (typing)
from typing import overload

@overload
def process(x: int) -> int: ...
@overload
def process(x: str) -> str: ...
def process(x):
    return x

# Literal type
Mode = Literal['r', 'w', 'a']

# Import patterns
from os.path import join as path_join
# from . import relative_module  # Would fail in standalone file
# from ..parent import something  # Would fail in standalone file

# Export patterns (Phase 6 verification - triggers extract_python_exports)
__all__ = ['process_data', 'User', 'vulnerable_func']
'''


def audit():
    print("=" * 80)
    print("EXTRACTOR OUTPUT AUDIT - TRUTH SERUM")
    print("=" * 80)

    # Build Context
    tree = ast.parse(CODE)
    context = build_file_context(tree, CODE, "audit_dummy.py")

    # All extractor modules
    modules = [
        ("core_extractors", core_extractors),
        ("control_flow_extractors", control_flow_extractors),
        ("security_extractors", security_extractors),
        ("testing_extractors", testing_extractors),
        ("async_extractors", async_extractors),
        ("state_mutation_extractors", state_mutation_extractors),
        ("exception_flow_extractors", exception_flow_extractors),
        ("data_flow_extractors", data_flow_extractors),
        ("behavioral_extractors", behavioral_extractors),
        ("performance_extractors", performance_extractors),
        ("fundamental_extractors", fundamental_extractors),
        ("operator_extractors", operator_extractors),
        ("collection_extractors", collection_extractors),
        ("class_feature_extractors", class_feature_extractors),
        ("type_extractors", type_extractors),
        ("protocol_extractors", protocol_extractors),
        ("stdlib_pattern_extractors", stdlib_pattern_extractors),
        ("advanced_extractors", advanced_extractors),
        ("flask_extractors", flask_extractors),
        ("framework_extractors", framework_extractors),
        ("django_web_extractors", django_web_extractors),
        ("django_advanced_extractors", django_advanced_extractors),
        ("validation_extractors", validation_extractors),
        ("orm_extractors", orm_extractors),
        ("task_graphql_extractors", task_graphql_extractors),
    ]

    all_results = {}

    for module_name, module in modules:
        print(f"\n{'='*60}")
        print(f"MODULE: {module_name}")
        print("=" * 60)

        for name in sorted(dir(module)):
            if name.startswith('extract_'):
                func = getattr(module, name)
                if not callable(func):
                    continue
                try:
                    results = func(context)
                    if results and len(results) > 0:
                        if isinstance(results[0], dict):
                            keys = sorted(list(results[0].keys()))
                            print(f"\n{name}:")
                            print(f"  COUNT: {len(results)}")
                            print(f"  KEYS: {keys}")

                            # VALUE SAMPLING for Fidelity Check (Truth Serum Upgrade)
                            sample_keys = [k for k in keys if k.endswith('_type') or k in ('operation', 'operator', 'name', 'kind')]
                            if sample_keys:
                                print("  VALUE SAMPLES (discriminators):")
                                for k in sample_keys:
                                    # Get unique values for this key across all results, limit to 8
                                    values = sorted(list(set(str(r.get(k, '')) for r in results if r.get(k))))[:8]
                                    if values:
                                        print(f"    {k}: {values}")

                            all_results[f"{module_name}.{name}"] = {
                                "count": len(results),
                                "keys": keys
                            }
                        elif isinstance(results, tuple):
                            # Some extractors return tuples
                            print(f"\n{name}:")
                            print(f"  RETURNS TUPLE of {len(results)} items")
                            for i, item in enumerate(results):
                                if item and isinstance(item, list) and len(item) > 0 and isinstance(item[0], dict):
                                    print(f"    [{i}]: {sorted(item[0].keys())}")
                        else:
                            print(f"\n{name}: RETURNS {type(results[0])}")
                    else:
                        print(f"\n{name}: [NO DATA - sample code needs pattern]")
                except TypeError as e:
                    if "positional argument" in str(e):
                        print(f"\n{name}: [SKIP - needs extra args]")
                    else:
                        print(f"\n{name}: [ERROR] {e}")
                except Exception as e:
                    print(f"\n{name}: [ERROR] {type(e).__name__}: {e}")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY: EXTRACTORS WITH DATA")
    print("=" * 80)
    for extractor, data in sorted(all_results.items()):
        print(f"{extractor}: {data['keys']}")


if __name__ == "__main__":
    audit()
