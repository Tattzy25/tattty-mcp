"""Tool for replacing backgrounds and relighting subjects via Stability AI."""
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
    poll_async_result,
    post_stability,
    stability_diagnostics,
)


class ReplaceBackgroundRequest(BaseStabilityRequest):
    subject_image: ImageInput = Field(..., description="Foreground subject image.")
    background_prompt: str | None = Field(
        default=None,
        description="Text prompt describing the desired background.",
    )
    background_reference: ImageInput | None = Field(
        default=None,
        description="Reference image used to derive the new background.",
    )
    negative_prompt: str | None = Field(
        default=None,
        description="Details that should be excluded from the resulting background.",
    )
    foreground_prompt: str | None = Field(
        default=None,
        description="Optional prompt to adjust the subject itself.",
    )
    preserve_original_subject: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="0-1 weighting for preserving the subject's appearance.",
    )
    keep_original_background: bool | None = Field(
        default=None,
        description="Request to composite the generated background with the original.",
    )
    original_background_depth: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="How much of the original depth map to retain.",
    )
    light_source_direction: Literal["above", "below", "left", "right"] | None = Field(
        default=None,
        description="Directional hint for relighting.",
    )
    light_source_strength: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Strength applied to the chosen light source direction.",
    )
    light_reference: ImageInput | None = Field(
        default=None,
        description="Image describing the lighting setup to mimic.",
    )
    seed: int | None = Field(
        default=None,
        ge=0,
        le=4294967294,
        description="Deterministic seed for reproducible replace background results.",
    )
    output_format: Literal["jpeg", "png", "webp"] = Field(
        default="png", description="Image encoding for the generated result."
    )

    @root_validator(skip_on_failure=True)
    def _require_background_instruction(cls, values):
        if not values.get("background_prompt") and not values.get("background_reference"):
            raise ValueError("Provide either background_prompt or background_reference")
        if values.get("light_source_strength") is not None and not (
            values.get("light_reference") or values.get("light_source_direction")
        ):
            raise ValueError(
                "light_source_strength requires either light_reference or light_source_direction"
            )
        return values


def run(request: ReplaceBackgroundRequest) -> dict:
    api_key = get_api_key(request.stability_api_key)
    files = build_file_payload(
        {
            "image": request.subject_image,
            "background_image": request.background_reference,
            "light_image": request.light_reference,
        }
    )
    data = clean_payload(
        {
            "background_prompt": request.background_prompt,
            "negative_prompt": request.negative_prompt,
            "foreground_prompt": request.foreground_prompt,
            "preserve_original_subject": request.preserve_original_subject,
            "keep_original_background": _bool_to_str(request.keep_original_background),
            "original_background_depth": request.original_background_depth,
            "light_source_direction": request.light_source_direction,
            "light_source_strength": request.light_source_strength,
            "seed": request.seed,
            "output_format": request.output_format,
        }
    )
    response = post_stability(
        "/v2beta/stable-image/edit/replace-background-and-relight",
        api_key,
        data=data,
        files=files,
    )
    job = response.json()
    result_id = job.get("id")
    if not result_id:
        raise RuntimeError("Stability API did not return an async job id")
    final_response = poll_async_result(result_id, api_key)
    return format_image_response(final_response)


def _bool_to_str(value: bool | None) -> str | None:
    if value is None:
        return None
    return "true" if value else "false"


def diagnostics() -> dict:
    return stability_diagnostics()
