"""Tool for Stability AI conservative upscaling."""
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


class ConservativeUpscaleRequest(BaseStabilityRequest):
    image: ImageInput = Field(..., description="Low-res image to upscale.")
    prompt: str = Field(..., description="Prompt describing the intended final look.")
    negative_prompt: str | None = Field(
        default=None, description="Elements to avoid after upscaling."
    )
    creativity: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional creativity setting (closer to 0 preserves more details).",
    )
    seed: int | None = Field(default=None, ge=0, le=4294967294)
    output_format: Literal["png", "jpeg", "webp"] = Field(
        default="png", description="Image format for the upscaled output."
    )
    style_preset: Literal[
        "3d-model",
        "analog-film",
        "anime",
        "cinematic",
        "comic-book",
        "digital-art",
        "enhance",
        "fantasy-art",
        "isometric",
        "line-art",
        "low-poly",
        "modeling-compound",
        "neon-punk",
        "origami",
        "photographic",
        "pixel-art",
        "tile-texture",
    ] | None = Field(default=None, description="Optional style preset.")


def run(request: ConservativeUpscaleRequest) -> dict:
    api_key = get_api_key(request.stability_api_key)
    files = build_file_payload({"image": request.image})
    data = clean_payload(
        {
            "prompt": request.prompt,
            "negative_prompt": request.negative_prompt,
            "creativity": request.creativity,
            "seed": request.seed,
            "output_format": request.output_format,
            "style_preset": request.style_preset,
        }
    )
    response = post_stability(
        "/v2beta/stable-image/upscale/conservative",
        api_key,
        data=data,
        files=files,
    )
    return format_image_response(response)


def diagnostics() -> dict:
    return stability_diagnostics()
