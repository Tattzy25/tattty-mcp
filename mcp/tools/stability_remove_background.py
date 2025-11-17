"""Tool for removing image backgrounds via Stability AI."""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from .stability_common import (
    BaseStabilityRequest,
    ImageInput,
    build_file_payload,
    clean_payload,
    format_image_response,
    get_api_key,
    post_stability,
    stability_diagnostics,
)


class RemoveBackgroundRequest(BaseStabilityRequest):
    image: ImageInput = Field(..., description="Foreground image whose background will be removed.")
    output_format: Literal["png", "webp"] = Field(
        default="png", description="Transparent formats supported by Stability AI."
    )


def run(request: RemoveBackgroundRequest) -> dict:
    api_key = get_api_key(request.stability_api_key)
    files = build_file_payload({"image": request.image})
    data = clean_payload({"output_format": request.output_format})
    response = post_stability(
        "/v2beta/stable-image/edit/remove-background",
        api_key,
        data=data,
        files=files,
    )
    return format_image_response(response)


def diagnostics() -> dict:
    return stability_diagnostics()
