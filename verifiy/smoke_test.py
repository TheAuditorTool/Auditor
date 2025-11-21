"""Smoke test file for modernization verification."""

def hello(name: str) -> str:
    """Simple function with type hints."""
    return f"Hello, {name}!"

class Greeter:
    """Simple class."""

    def __init__(self, greeting: str = "Hello"):
        self.greeting = greeting

    def greet(self, name: str) -> str:
        """Greet someone."""
        return f"{self.greeting}, {name}!"

if __name__ == "__main__":
    g = Greeter()
    print(g.greet("World"))
    print(hello("Python"))
