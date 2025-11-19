"""Utility tool that enumerates all MCP tools exposed by this server."""
from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class ListToolsRequest(BaseModel):
    include_schema: bool = Field(
        default=True,
        description="Whether to include the JSON schema for each tool's request model.",
    )
    only_progress_supported: bool | None = Field(
        default=None,
        description="If set, filter results to tools whose supports_progress flag matches this value.",
    )
    name_prefix: str | None = Field(
        default=None,
        description="Optional case-insensitive prefix to filter tool names (e.g. 'stability_').",
    )


def _serialize_tool(name: str, definition) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "name": name,
        "description": definition.description,
        "supports_progress": definition.supports_progress,
    }
    if definition.diagnostic:
        payload["has_diagnostics"] = True
    if definition.stream_handler:
        payload["supports_streaming"] = True
    return payload


def run(request: ListToolsRequest) -> Dict[str, List[Dict[str, Any]]]:
    # Local import avoids circular dependency at module import time.
    from . import TOOL_REGISTRY

    name_prefix = request.name_prefix.lower() if request.name_prefix else None

    tools: List[Dict[str, Any]] = []
    for name, definition in sorted(TOOL_REGISTRY.items()):
        if name_prefix and not name.lower().startswith(name_prefix):
            continue
        if request.only_progress_supported is not None:
            if definition.supports_progress != request.only_progress_supported:
                continue

        payload = _serialize_tool(name, definition)
        if request.include_schema:
            payload["inputSchema"] = definition.request_model.model_json_schema()
        tools.append(payload)

    return {"tools": tools}
