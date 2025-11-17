"""Logging helpers for the MCP service."""
from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = record.stack_info
        for key, value in record.__dict__.items():
            if key.startswith("_json"):
                payload[key[6:]] = value
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(log_dir: Path) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "mcp.log"

    formatter = JsonFormatter()
    file_handler = RotatingFileHandler(log_path, maxBytes=2_000_000, backupCount=5)
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    root = logging.getLogger()
    if not root.handlers:
        root.setLevel(logging.INFO)
        root.addHandler(file_handler)
        root.addHandler(stream_handler)

    return log_path


def tail_file(log_path: Path, lines: int = 200) -> str:
    if not log_path.exists():
        return ""
    with log_path.open("r", encoding="utf-8") as file:
        data = file.readlines()
    tail = data[-lines:]
    return "".join(tail)
