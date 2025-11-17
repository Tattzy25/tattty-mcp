"""Shared helpers for Stability AI-backed MCP tools."""
from __future__ import annotations

import base64
import os
import time
from typing import Any, Dict
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, Field, HttpUrl, root_validator

STABILITY_API_BASE = os.environ.get("STABILITY_API_BASE", "https://api.stability.ai")
DEFAULT_TIMEOUT = float(os.environ.get("STABILITY_HTTP_TIMEOUT", "90"))
ASYNC_POLL_INTERVAL = float(os.environ.get("STABILITY_POLL_INTERVAL", "5"))
ASYNC_MAX_ATTEMPTS = int(os.environ.get("STABILITY_POLL_ATTEMPTS", "24"))


class BaseStabilityRequest(BaseModel):
    """Common field for optionally overriding the Stability API key."""

    stability_api_key: str | None = Field(
        default=None,
        description=(
            "Optional Stability API key override. Defaults to the STABILITY_API_KEY env variable."
        ),
    )


class ImageInput(BaseModel):
    """Represents an image payload that can be fetched via URL or provided inline as base64."""

    url: HttpUrl | None = Field(
        default=None,
        description="HTTPS URL that hosts the image to be sent to Stability AI.",
    )
    base64_data: str | None = Field(
        default=None,
        description="Base64-encoded image bytes. data: URIs are also supported.",
    )
    filename: str | None = Field(
        default=None,
        description="Optional filename hint that will be sent to the Stability API.",
    )
    content_type: str | None = Field(
        default=None,
        description="Optional MIME type override (defaults to request headers or image/png).",
    )

    @root_validator(skip_on_failure=True)
    def _ensure_source(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if not values.get("url") and not values.get("base64_data"):
            raise ValueError("Provide either 'url' or 'base64_data' for ImageInput")
        return values


def stability_diagnostics() -> dict:
    if os.environ.get("STABILITY_API_KEY"):
        return {"status": "ok"}
    return {"status": "error", "detail": "STABILITY_API_KEY is missing"}


def get_api_key(override: str | None) -> str:
    api_key = override or os.environ.get("STABILITY_API_KEY")
    if not api_key:
        raise ValueError("STABILITY_API_KEY is not configured and no override was provided")
    return api_key


def _strip_data_url(data: str) -> str:
    if data.startswith("data:"):
        try:
            _, payload = data.split(",", 1)
            return payload
        except ValueError:
            return data
    return data


def _decode_base64(data: str) -> bytes:
    cleaned = _strip_data_url(data.strip())
    return base64.b64decode(cleaned)


def _filename_from_url(url: HttpUrl, fallback: str) -> str:
    parsed = urlsplit(str(url))
    name = os.path.basename(parsed.path)
    return name or fallback


def _download_url(url: HttpUrl) -> tuple[bytes, str | None]:
    with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
        response = client.get(str(url))
        response.raise_for_status()
        return response.content, response.headers.get("content-type")


def _prepare_file(field: str, image: ImageInput) -> tuple[str, bytes, str]:
    if image.url:
        content, detected_type = _download_url(image.url)
        filename = image.filename or _filename_from_url(image.url, f"{field}.bin")
        content_type = image.content_type or detected_type or "application/octet-stream"
        return filename, content, content_type

    if not image.base64_data:
        raise ValueError(f"Image input '{field}' is missing both url and base64 data")
    content = _decode_base64(image.base64_data)
    filename = image.filename or f"{field}.bin"
    content_type = image.content_type or "application/octet-stream"
    return filename, content, content_type


def build_file_payload(images: Dict[str, ImageInput | None]) -> Dict[str, tuple[str, bytes, str]]:
    files: Dict[str, tuple[str, bytes, str]] = {}
    for field, image in images.items():
        if not image:
            continue
        files[field] = _prepare_file(field, image)
    return files


def clean_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


def request_stability(
    method: str,
    endpoint: str,
    api_key: str,
    *,
    data: Dict[str, Any] | None = None,
    files: Dict[str, tuple[str, bytes, str]] | None = None,
    accept: str | None = "application/json",
) -> httpx.Response:
    url = f"{STABILITY_API_BASE}{endpoint}"
    headers = {"Authorization": f"Bearer {api_key}"}
    if accept:
        headers["Accept"] = accept

    with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
        response = client.request(method.upper(), url, headers=headers, data=data, files=files)
    response.raise_for_status()
    return response


def post_stability(
    endpoint: str,
    api_key: str,
    *,
    data: Dict[str, Any] | None = None,
    files: Dict[str, tuple[str, bytes, str]] | None = None,
    accept: str | None = "application/json",
) -> httpx.Response:
    payload = data or None
    file_payload = files or None
    return request_stability("POST", endpoint, api_key, data=payload, files=file_payload, accept=accept)


def execute_image_tool(
    endpoint: str,
    api_key: str,
    *,
    payload: Dict[str, Any],
    image_inputs: Dict[str, ImageInput | None],
    accept: str | None = "application/json",
) -> dict:
    files = build_file_payload(image_inputs)
    response = post_stability(endpoint, api_key, data=payload, files=files if files else None, accept=accept)
    return format_image_response(response)


def format_image_response(response: httpx.Response) -> dict:
    content_type = response.headers.get("content-type", "application/octet-stream")
    request_id = response.headers.get("x-request-id")
    finish_reason = response.headers.get("finish-reason")
    seed_header = response.headers.get("seed")

    if "application/json" in content_type:
        payload = response.json()
        images = _extract_images(payload)
        return {
            "request_id": request_id,
            "content_type": content_type,
            "finish_reason": finish_reason or (images[0].get("finish_reason") if images else None),
            "seed": seed_header or (images[0].get("seed") if images else None),
            "images": images,
            "raw": payload,
        }

    encoded = base64.b64encode(response.content).decode("ascii")
    return {
        "request_id": request_id,
        "content_type": content_type,
        "finish_reason": finish_reason,
        "seed": seed_header,
        "images": [
            {
                "base64": encoded,
                "seed": seed_header,
                "finish_reason": finish_reason,
                "mime_type": content_type,
            }
        ],
    }


def _extract_images(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        if "image" in payload and isinstance(payload["image"], str):
            return [
                {
                    "base64": payload.get("image"),
                    "seed": payload.get("seed"),
                    "finish_reason": payload.get("finish_reason"),
                    "mime_type": _infer_mime(payload),
                }
            ]
        if "images" in payload and isinstance(payload["images"], list):
            return [
                {
                    "base64": item.get("image"),
                    "seed": item.get("seed"),
                    "finish_reason": item.get("finish_reason"),
                    "mime_type": _infer_mime(payload),
                }
                for item in payload["images"]
                if isinstance(item, dict) and item.get("image")
            ]
        if "artifacts" in payload and isinstance(payload["artifacts"], list):
            items: list[dict[str, Any]] = []
            for artifact in payload["artifacts"]:
                if not isinstance(artifact, dict):
                    continue
                base64_key = artifact.get("base64") or artifact.get("image")
                if not base64_key:
                    continue
                items.append(
                    {
                        "base64": base64_key,
                        "seed": artifact.get("seed"),
                        "finish_reason": artifact.get("finish_reason"),
                        "mime_type": _infer_mime(payload),
                    }
                )
            if items:
                return items
    return []


def _infer_mime(payload: dict[str, Any]) -> str | None:
    return payload.get("mime_type") or payload.get("content_type")


def poll_async_result(
    result_id: str,
    api_key: str,
    *,
    accept: str | None = "application/json",
    poll_interval: float = ASYNC_POLL_INTERVAL,
    max_attempts: int = ASYNC_MAX_ATTEMPTS,
) -> httpx.Response:
    attempts = 0
    while attempts < max_attempts:
        attempts += 1
        response = request_stability(
            "GET",
            f"/v2beta/results/{result_id}",
            api_key,
            accept=accept,
        )
        if response.status_code == 202:
            time.sleep(poll_interval)
            continue
        return response
    raise TimeoutError(
        f"Timed out waiting for async Stability result {result_id} after {max_attempts} attempts"
    )


__all__ = [
    "BaseStabilityRequest",
    "ImageInput",
    "build_file_payload",
    "clean_payload",
    "execute_image_tool",
    "format_image_response",
    "get_api_key",
    "poll_async_result",
    "post_stability",
    "stability_diagnostics",
]
