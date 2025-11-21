"""Test file for indexing."""

import os
import sys
from pathlib import Path

def test_function(arg1, arg2):
    """A test function."""
    result = arg1 + arg2
    return result

class TestClass:
    """A test class."""

    def __init__(self, name):
        self.name = name

    def greet(self):
        return f"Hello, {self.name}"

# Call the function
output = test_function(1, 2)
print(output)

# Create an instance
obj = TestClass("World")
print(obj.greet())