"""Minimal MCP-compatible FastAPI application."""
from __future__ import annotations

from pathlib import Path

try:  # pragma: no cover - best-effort optional dependency
	from dotenv import load_dotenv
except ImportError:  # pragma: no cover - fallback when dependency missing
	load_dotenv = None  # type: ignore[assignment]

if load_dotenv:
	_repo_root = Path(__file__).resolve().parents[1]
	_dotenv_path = _repo_root / ".env"
	if _dotenv_path.exists():
		load_dotenv(dotenv_path=_dotenv_path, override=False)
	else:
		load_dotenv(override=False)

from .config import Settings, load_settings
from .server import create_app

__all__ = ["Settings", "load_settings", "create_app"]
