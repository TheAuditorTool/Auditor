"""FastAPI application entry point.

DeepFlow Python - Multi-hop taint analysis validation fixture.

WARNING: This application contains intentional security vulnerabilities
for testing purposes. DO NOT deploy in production.
"""

from fastapi import FastAPI

from app.api.routes import users, reports, admin, safe
from app.database import init_db

app = FastAPI(
    title="DeepFlow Python",
    description="Multi-hop taint analysis validation fixture",
    version="0.1.0",
)

# Include routers - vulnerable endpoints
app.include_router(users.router)
app.include_router(reports.router)
app.include_router(admin.router)

# Include safe router - sanitized path demonstrations
app.include_router(safe.router)


@app.on_event("startup")
async def startup():
    """Initialize database on startup."""
    init_db()


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "DeepFlow Python",
        "description": "Multi-hop taint analysis validation fixture",
        "warning": "CONTAINS INTENTIONAL VULNERABILITIES - DO NOT DEPLOY",
        "endpoints": {
            "/users/search?q=<query>": "SQL Injection (16 hops)",
            "/reports/generate": "Command Injection + XSS + SSRF",
            "/admin/files/{filename}": "Path Traversal (10 hops)",
        },
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}
