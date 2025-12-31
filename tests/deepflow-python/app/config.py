"""Application configuration."""

import os


class Config:
    """Application configuration from environment variables."""

    DATABASE_URL: str = os.environ.get(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/deepflow"
    )
    DEBUG: bool = os.environ.get("DEBUG", "false").lower() == "true"
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "insecure-dev-key")
    REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    TEMPLATE_DIR: str = os.environ.get("TEMPLATE_DIR", "templates")
    UPLOAD_DIR: str = os.environ.get("UPLOAD_DIR", "/tmp/uploads")
    EXTERNAL_API_URL: str = os.environ.get("EXTERNAL_API_URL", "http://localhost:8080")


config = Config()
