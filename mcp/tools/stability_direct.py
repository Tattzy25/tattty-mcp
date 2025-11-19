"""Direct Stability SD3.5 generation plus optional Mixedbread upload."""
from __future__ import annotations

from typing import Any, Callable, Dict

from pydantic import BaseModel, Field

from .groq_to_stability import (
    MixbreadOptions,
    StabilityGenerationOptions,
    _apply_selection_overrides,
    _normalize_selection_value,
    store_with_mixbread,
)
from .stability_sd35_generate import Sd35GenerateRequest, run as stability_run


class DirectStabilityRequest(BaseModel):
    prompt: str = Field(..., description="Prompt sent directly to Stability SD3.5")
    selections: Dict[str, str] = Field(
        default_factory=dict,
        description="Optional UI selections persisted with metadata (style, color, etc.)",
    )
    additional_notes: list[str] | None = Field(
        default=None,
        description="Optional bullet points captured for metadata purposes.",
    )
    stability: StabilityGenerationOptions = Field(
        default_factory=StabilityGenerationOptions,
        description="Rendering options forwarded to Stability.",
    )
    mixbread: MixbreadOptions | None = Field(
        default=None,
        description="Configure Mixedbread upload behavior.",
    )


def run(
    request: DirectStabilityRequest,
    progress_callback: Callable[[int, str], None] | None = None,
) -> dict:
    def report(progress: int, message: str) -> None:
        if progress_callback:
            progress_callback(progress, message)

    report(0, "Preparing Stability payload...")

    stability_payload = request.stability.dict(exclude_none=True)
    _apply_selection_overrides(stability_payload, request.selections)
    stability_payload["prompt"] = request.prompt.strip()

    stability_request = Sd35GenerateRequest(**stability_payload)
    report(33, "Generating image with Stability AI...")
    stability_response = stability_run(stability_request)
    report(66, "Image generated")

    mixbread_options = request.mixbread or MixbreadOptions()
    mixbread_result: dict | None = None
    if mixbread_options.enabled:
        report(66, "Uploading to Mixedbread...")
        mixbread_result = store_with_mixbread(
            request=request,
            composed_prompt=request.prompt.strip(),
            stability_response=stability_response,
            options=mixbread_options,
        )
    else:
        mixbread_result = {"status": "disabled"}

    report(100, "Complete")
    return {
        "prompt": request.prompt.strip(),
        "stability": stability_response,
        "mixbread": mixbread_result,
        "selections": request.selections,
        "notes": request.additional_notes,
    }
