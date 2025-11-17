"""Minimal MCP-compatible FastAPI application."""
from .config import Settings, load_settings
from .server import create_app

__all__ = ["Settings", "load_settings", "create_app"]
