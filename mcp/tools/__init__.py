"""Tool registry for the MCP HTTP service."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, Dict

from pydantic import BaseModel

from .echo import EchoRequest, diagnostics as echo_diag, run as echo_run
from .resize_image import (
    ResizeImageRequest,
    diagnostics as resize_image_diag,
    run as resize_image_run,
)
from .text_stats import TextStatsRequest, diagnostics as text_stats_diag, run as text_stats_run

ToolHandler = Callable[[BaseModel], Awaitable[dict] | dict]


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    request_model: type[BaseModel]
    handler: ToolHandler
    description: str
    diagnostic: Callable[[], dict] | None = None


TOOL_REGISTRY: Dict[str, ToolDefinition] = {
    "echo": ToolDefinition(
        request_model=EchoRequest,
        handler=echo_run,
        description="Returns the supplied string along with request metadata.",
        diagnostic=echo_diag,
    ),
    "resize_image": ToolDefinition(
        request_model=ResizeImageRequest,
        handler=resize_image_run,
        description="Downloads an image, resizes it, and returns a base64-encoded PNG.",
        diagnostic=resize_image_diag,
    ),
    "text_stats": ToolDefinition(
        request_model=TextStatsRequest,
        handler=text_stats_run,
        description="Counts characters, words, and sentences in supplied text.",
        diagnostic=text_stats_diag,
    ),
}

__all__ = ["ToolDefinition", "TOOL_REGISTRY"]
