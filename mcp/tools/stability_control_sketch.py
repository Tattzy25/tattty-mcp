"""Tool for Stability AI control sketch guidance."""
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


class ControlSketchRequest(BaseStabilityRequest):
    prompt: str = Field(..., description="Prompt describing the desired final image.")
    image: ImageInput = Field(..., description="Reference sketch used for layout guidance.")
    control_strength: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="How strongly to enforce the provided sketch.",
    )
    negative_prompt: str | None = Field(
        default=None, description="Elements to discourage in the final image."
    )
    seed: int | None = Field(default=None, ge=0, le=4294967294)
    output_format: Literal["png", "jpeg", "webp"] = Field(
        default="png", description="Desired output encoding."
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
    ] | None = Field(default=None)


def run(request: ControlSketchRequest) -> dict:
    api_key = get_api_key(request.stability_api_key)
    payload = clean_payload(
        {
            "prompt": request.prompt,
            "control_strength": request.control_strength,
            "negative_prompt": request.negative_prompt,
            "seed": request.seed,
            "output_format": request.output_format,
            "style_preset": request.style_preset,
        }
    )
    return execute_image_tool(
        "/v2beta/stable-image/control/sketch",
        api_key,
        payload=payload,
        image_inputs={"image": request.image},
    )


def diagnostics() -> dict:
    return stability_diagnostics()
