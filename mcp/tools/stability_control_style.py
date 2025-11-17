"""Tool for Stability AI style guide control."""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from .stability_common import (
    BaseStabilityRequest,
    ImageInput,
    clean_payload,
    execute_image_tool,
    get_api_key,
    stability_diagnostics,
)


class ControlStyleRequest(BaseStabilityRequest):
    prompt: str = Field(..., min_length=1, description="Prompt describing the desired scene.")
    image: ImageInput = Field(..., description="Reference style image.")
    negative_prompt: str | None = Field(default=None)
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
    ] | None = Field(default=None)
    fidelity: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="How closely to follow the reference style.",
    )
    seed: int | None = Field(default=None, ge=0, le=4294967294)
    output_format: Literal["png", "jpeg", "webp"] = Field(default="png")
    style_preset: Literal[
        "enhance",
        "anime",
        "photographic",
        "digital-art",
        "comic-book",
        "fantasy-art",
        "line-art",
        "analog-film",
        "neon-punk",
        "isometric",
        "low-poly",
        "origami",
        "modeling-compound",
        "cinematic",
        "3d-model",
        "pixel-art",
        "tile-texture",
    ] | None = Field(default=None)


def run(request: ControlStyleRequest) -> dict:
    api_key = get_api_key(request.stability_api_key)
    payload = clean_payload(
        {
            "prompt": request.prompt,
            "negative_prompt": request.negative_prompt,
            "aspect_ratio": request.aspect_ratio,
            "fidelity": request.fidelity,
            "seed": request.seed,
            "output_format": request.output_format,
            "style_preset": request.style_preset,
        }
    )
    return execute_image_tool(
        "/v2beta/stable-image/control/style",
        api_key,
        payload=payload,
        image_inputs={"image": request.image},
    )


def diagnostics() -> dict:
    return stability_diagnostics()
