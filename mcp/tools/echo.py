"""Simple echo tool useful for connectivity tests."""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class EchoRequest(BaseModel):
    message: str = Field(..., description="Arbitrary text to echo back")


def run(request: EchoRequest) -> dict:
    """Return the provided message plus lightweight metadata."""

    return {
        "echo": request.message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "length": len(request.message),
    }


def diagnostics() -> dict:
    return {"status": "ok"}
