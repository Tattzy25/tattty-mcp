"""Tool for Stability AI SD3.5 image generation."""
from __future__ import annotations

from typing import Literal

from pydantic import Field, root_validator

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


class Sd35GenerateRequest(BaseStabilityRequest):
    prompt: str = Field(..., min_length=1, description="Primary text prompt.")
    model: Literal["sd3.5-large", "sd3.5-large-turbo"] = Field(
        default="sd3.5-large",
        description="Model variant to target (large or large-turbo).",
    )
    mode: Literal["text-to-image", "image-to-image"] = Field(
        default="text-to-image",
        description="Use image-to-image when supplying an init image.",
    )
    init_image: ImageInput | None = Field(
        default=None,
        description="Reference image; required when mode=image-to-image.",
    )
    strength: float | None = Field(
        default=0.35,
        ge=0.0,
        le=1.0,
        description="Influence of init_image when mode=image-to-image.",
    )
    aspect_ratio: Literal[
        "21:9",
        "16:9",
        "3:2",
        "5:4",
        "1:1",
        "4:5",
        "2:3",
        "9:16",
        "9:21",
    ] | None = Field(
        default=None,
        description="Aspect ratio for text-to-image requests.",
    )
    negative_prompt: str | None = Field(
        default=None,
        description="Text prompt describing what to avoid.",
    )
    seed: int | None = Field(
        default=None,
        ge=0,
        le=4294967294,
        description="Deterministic seed (optional).",
    )
    output_format: Literal["png", "jpeg", "webp"] = Field(
        default="png", description="Desired output encoding."
    )
    cfg_scale: float | None = Field(
        default=None,
        ge=1.0,
        le=10.0,
        description="Classifier-free guidance scale for text-to-image mode.",
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

    @root_validator(skip_on_failure=True)
    def _validate_mode(cls, values):
        mode = values.get("mode")
        init_image = values.get("init_image")
        strength = values.get("strength")
        if mode == "image-to-image" and not init_image:
            raise ValueError("init_image is required when mode='image-to-image'")
        if mode == "image-to-image" and strength is None:
            raise ValueError("strength must be provided for image-to-image mode")
        if mode == "text-to-image":
            values["init_image"] = None
        return values


def run(request: Sd35GenerateRequest) -> dict:
    api_key = get_api_key(request.stability_api_key)
    files = None
    if request.init_image:
        files = build_file_payload({"image": request.init_image})
    data = clean_payload(
        {
            "prompt": request.prompt,
            "model": request.model,
            "mode": request.mode,
            "strength": request.strength if request.mode == "image-to-image" else None,
            "aspect_ratio": request.aspect_ratio if request.mode == "text-to-image" else None,
            "negative_prompt": request.negative_prompt,
            "cfg_scale": request.cfg_scale if request.mode == "text-to-image" else None,
            "seed": request.seed,
            "output_format": request.output_format,
            "style_preset": request.style_preset,
        }
    )
    response = post_stability(
        "/v2beta/stable-image/generate/sd3",
        api_key,
        data=data,
        files=files,
    )
    return format_image_response(response)


def diagnostics() -> dict:
    return stability_diagnostics()
