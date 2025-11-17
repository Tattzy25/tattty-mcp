"""Tool for Stability AI style transfer control."""
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


class ControlStyleTransferRequest(BaseStabilityRequest):
    init_image: ImageInput = Field(..., description="Image that provides composition and content.")
    style_image: ImageInput = Field(..., description="Image describing the target style.")
    prompt: str | None = Field(
        default=None,
        description="Optional prompt to refine the target output.",
    )
    negative_prompt: str | None = Field(default=None)
    style_strength: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="How strongly to apply the style reference.",
    )
    composition_fidelity: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="How tightly to preserve the original composition.",
    )
    change_strength: float | None = Field(
        default=None,
        ge=0.1,
        le=1.0,
        description="Amount of change allowed relative to the init image.",
    )
    seed: int | None = Field(default=None, ge=0, le=4294967294)
    output_format: Literal["png", "jpeg", "webp"] = Field(default="png")


def run(request: ControlStyleTransferRequest) -> dict:
    api_key = get_api_key(request.stability_api_key)
    payload = clean_payload(
        {
            "prompt": request.prompt,
            "negative_prompt": request.negative_prompt,
            "style_strength": request.style_strength,
            "composition_fidelity": request.composition_fidelity,
            "change_strength": request.change_strength,
            "seed": request.seed,
            "output_format": request.output_format,
        }
    )
    return execute_image_tool(
        "/v2beta/stable-image/control/style-transfer",
        api_key,
        payload=payload,
        image_inputs={"init_image": request.init_image, "style_image": request.style_image},
    )


def diagnostics() -> dict:
    return stability_diagnostics()
