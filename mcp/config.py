"""Configuration helpers for the MCP FastAPI server."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml
from pydantic import BaseModel, Field


class CorsConfig(BaseModel):
    """Cross-origin resource sharing configuration."""

    allow_origins: list[str] = Field(default_factory=lambda: ["*"])
    allow_methods: list[str] = Field(default_factory=lambda: ["*"])
    allow_headers: list[str] = Field(default_factory=lambda: ["*"])


class Settings(BaseModel):
    """Server runtime configuration loaded from YAML or environment."""

    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"
    allow_anonymous: bool = True
    secret_key: str | None = None
    rate_limit_per_ip: int | None = 30
    cors: CorsConfig = Field(default_factory=CorsConfig)
    admin_token: str | None = None
    log_directory: Path = Field(default_factory=lambda: Path("logs"))

    @property
    def rate_limit_label(self) -> str | None:
        """Return slowapi-compatible rate limit string (e.g. "30/minute")."""
        if self.rate_limit_per_ip:
            return f"{self.rate_limit_per_ip}/minute"
        return None


def _read_config_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        content = yaml.safe_load(file) or {}
    if not isinstance(content, dict):
        raise ValueError("config.yaml must contain a mapping at the top level")
    return content


def _apply_env_overrides(data: Dict[str, Any]) -> Dict[str, Any]:
    """Allow environment variables to override config values."""

    overrides: Dict[str, tuple[str, callable]] = {
        "MCP_HOST": ("host", str),
        "MCP_PORT": ("port", int),
        "MCP_LOG_LEVEL": ("log_level", str),
        "MCP_ALLOW_ANONYMOUS": ("allow_anonymous", lambda v: v.lower() in {"1", "true", "yes"}),
        "MCP_SECRET_KEY": ("secret_key", str),
        "MCP_RATE_LIMIT": ("rate_limit_per_ip", int),
        "MCP_ADMIN_TOKEN": ("admin_token", str),
        "MCP_LOG_DIR": ("log_directory", lambda value: Path(value)),
    }

    for env_key, (field_name, caster) in overrides.items():
        if env_key in os.environ:
            data[field_name] = caster(os.environ[env_key])

    return data


def load_settings() -> Settings:
    """Load settings from config.yaml (and optional MCP_CONFIG path)."""

    default_path = Path(__file__).with_name("config.yaml")
    config_env = os.environ.get("MCP_CONFIG")
    config_path = Path(config_env) if config_env else default_path

    if config_path.is_dir():
        config_path = config_path / "config.yaml"

    raw = _read_config_file(config_path)
    merged = _apply_env_overrides(raw)
    return Settings(**merged)
