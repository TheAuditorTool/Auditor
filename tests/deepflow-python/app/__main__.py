"""Entry point for running the application with `python -m app`.

DeepFlow Python - Multi-hop taint analysis validation fixture.

WARNING: This application contains intentional security vulnerabilities
for testing purposes. DO NOT deploy in production.
"""

import uvicorn


def main():
    """Run the FastAPI application."""
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
