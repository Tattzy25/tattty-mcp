"""Lightweight Mixedbread API helper for uploading files and adding them to a store."""
from __future__ import annotations

import os
from typing import Any, Dict

import httpx

MIXBREAD_API_BASE = os.environ.get("MIXBREAD_API_BASE", "https://api.mixedbread.com")
DEFAULT_TIMEOUT = float(os.environ.get("MIXBREAD_HTTP_TIMEOUT", "60"))


def _auth_headers(api_key: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


def get_mixbread_api_key(override: str | None = None) -> str:
    api_key = override or os.environ.get("MIXBREAD_API_KEY")
    if not api_key:
        raise ValueError("MIXBREAD_API_KEY is not configured")
    return api_key


def get_mixbread_store_id(override: str | None = None) -> str:
    store_id = override or os.environ.get("MIXBREAD_STORE_ID")
    if not store_id:
        raise ValueError("MIXBREAD_STORE_ID is not configured")
    return store_id


def upload_file(
    *,
    file_bytes: bytes,
    filename: str,
    mime_type: str,
    api_key: str,
) -> dict:
    url = f"{MIXBREAD_API_BASE}/v1/files"
    headers = _auth_headers(api_key)
    files = {"file": (filename, file_bytes, mime_type)}
    with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
        response = client.post(url, headers=headers, files=files)
    response.raise_for_status()
    return response.json()


def add_file_to_store(
    *,
    api_key: str,
    store_id: str,
    file_id: str,
    metadata: Dict[str, Any] | None = None,
    external_id: str | None = None,
    overwrite: bool | None = None,
    config: Dict[str, Any] | None = None,
    parsing_strategy: str | None = None,
    chunking_strategy: Dict[str, Any] | None = None,
    contextualization: bool | None = None,
) -> dict:
    url = f"{MIXBREAD_API_BASE}/v1/stores/{store_id}/files"
    headers = _auth_headers(api_key)
    body: Dict[str, Any] = {"file_id": file_id}
    if external_id:
        body["external_id"] = external_id
    if overwrite is not None:
        body["overwrite"] = overwrite
    if metadata:
        body["metadata"] = metadata
    if config:
        body["config"] = config
    if parsing_strategy:
        body["parsing_strategy"] = parsing_strategy
    if chunking_strategy:
        body["chunking_strategy"] = chunking_strategy
    if contextualization is not None:
        body["contextualization"] = contextualization

    with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
        response = client.post(url, headers=headers, json=body)
    response.raise_for_status()
    return response.json()


__all__ = [
    "add_file_to_store",
    "get_mixbread_api_key",
    "get_mixbread_store_id",
    "upload_file",
]
