"""Shared health-check helpers."""
from __future__ import annotations

import asyncio
import platform
import shutil
import socket
import time
from typing import Any, Dict

import httpx
from PIL import Image

from .tools import TOOL_REGISTRY

OUTBOUND_TEST_URL = "https://httpbin.org/status/200"


def _disk_check() -> Dict[str, Any]:
    usage = shutil.disk_usage(".")
    return {
        "status": "ok" if usage.free > 100 * 1024 * 1024 else "warning",
        "total_gb": round(usage.total / (1024 ** 3), 2),
        "free_gb": round(usage.free / (1024 ** 3), 2),
    }


def _pillow_check() -> Dict[str, Any]:
    try:
        image = Image.new("RGBA", (10, 10), color=(255, 0, 0, 255))
        image.resize((5, 5))
        return {"status": "ok"}
    except Exception as exc:  # pragma: no cover
        return {"status": "error", "detail": str(exc)}


async def _http_check() -> Dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(OUTBOUND_TEST_URL)
        return {"status": "ok" if response.status_code == 200 else "error", "code": response.status_code}
    except Exception as exc:  # pragma: no cover
        return {"status": "error", "detail": str(exc)}


def _tool_checks() -> Dict[str, Any]:
    results: Dict[str, Any] = {}
    for name, definition in TOOL_REGISTRY.items():
        if definition.diagnostic is None:
            results[name] = {"status": "unknown"}
            continue
        try:
            results[name] = definition.diagnostic()
        except Exception as exc:  # pragma: no cover
            results[name] = {"status": "error", "detail": str(exc)}
    return results


async def run_deep_health() -> Dict[str, Any]:
    http_result = await _http_check()
    disk_result = _disk_check()
    pillow_result = _pillow_check()
    tool_results = _tool_checks()

    checks = {
        "outbound_http": http_result,
        "disk": disk_result,
        "pillow": pillow_result,
        "tools": tool_results,
    }

    status = "ok"
    for value in checks.values():
        if isinstance(value, dict) and value.get("status") not in {"ok", "unknown"}:
            status = "error"
            break
        if isinstance(value, dict) and "tools" in checks and value is checks["tools"]:
            if any(item.get("status") == "error" for item in value.values()):
                status = "error"
                break

    return {"status": status, "checks": checks}


async def railway_health_snapshot(metrics_snapshot: Dict[str, Any]) -> Dict[str, Any]:
    deep = await run_deep_health()
    hostname = socket.gethostname()
    return {
        "status": deep["status"],
        "timestamp": time.time(),
        "hostname": hostname,
        "metrics": metrics_snapshot,
        "deep": deep["checks"],
        "platform": {
            "python": platform.python_version(),
            "system": platform.system(),
            "release": platform.release(),
        },
    }
