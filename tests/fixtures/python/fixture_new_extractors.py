"""Test fixture for control_flow and protocol extractors."""

# Control Flow Patterns
# ======================

# For loops
for i in range(10):
    pass

for key, value in enumerate(["a", "b", "c"]):
    pass

for x, y in zip([1, 2], [3, 4]):
    pass

for key, value in {"a": 1, "b": 2}.items():
    pass

# While loops
while True:
    break

count = 0
while count < 10:
    count += 1

# Async for
async def async_iterate():
    async for item in async_generator():
        pass

# If statements
if x > 0:
    pass

if x > 0:
    pass
elif x < 0:
    pass
else:
    pass

# Match statements (Python 3.10+)
match value:
    case 1:
        pass
    case 2 if condition:
        pass
    case _:
        pass

# Flow control
for i in range(10):
    if i == 5:
        break
    if i % 2 == 0:
        continue
    pass

# Assert
assert x > 0
assert x > 0, "x must be positive"

# Del
del x
del mylist[0]
del obj.attr

# Imports
import os
import sys as system
from pathlib import Path
from typing import List, Dict
from ..parent import something

# With statements
with open("file.txt") as f:
    pass

async with lock:
    pass

with open("a") as f, open("b") as g:
    pass


# Protocol Patterns
# =================

# Iterator protocol
class MyIterator:
    def __iter__(self):
        return self

    def __next__(self):
        if condition:
            raise StopIteration
        return value

# Container protocol
class MyContainer:
    def __len__(self):
        return 10

    def __getitem__(self, index):
        return self.data[index]

    def __setitem__(self, index, value):
        self.data[index] = value

    def __delitem__(self, index):
        del self.data[index]

    def __contains__(self, item):
        return item in self.data

# Callable protocol
class MyCallable:
    def __call__(self, x, y, *args, **kwargs):
        return x + y

# Comparison protocol
from functools import total_ordering

@total_ordering
class MyComparable:
    def __eq__(self, other):
        return self.value == other.value

    def __lt__(self, other):
        return self.value < other.value

# Arithmetic protocol
class MyNumber:
    def __add__(self, other):
        return MyNumber(self.value + other.value)

    def __radd__(self, other):
        return MyNumber(other + self.value)

    def __iadd__(self, other):
        self.value += other.value
        return self

    def __mul__(self, other):
        return MyNumber(self.value * other.value)

# Pickle protocol
class MyPickleable:
    def __getstate__(self):
        return self.__dict__.copy()

    def __setstate__(self, state):
        self.__dict__.update(state)

    def __reduce__(self):
        return (self.__class__, (self.value,))

# Weakref usage
import weakref

weak_ref = weakref.ref(obj)
weak_proxy = weakref.proxy(obj)
weak_dict = weakref.WeakValueDictionary()

# Context variables
from contextvars import ContextVar

my_var = ContextVar('my_var')
token = my_var.set('value')
value = my_var.get()

# Module attributes
if __name__ == '__main__':
    print(__file__)
    print(__doc__)

__all__ = ['MyIterator', 'MyContainer']

# Class decorators
@dataclass
class MyData:
    x: int
    y: str

@total_ordering
class MyOrdered:
    pass

@custom_decorator(arg=value)
class MyCustom:
    pass
