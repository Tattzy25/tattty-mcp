"""Pipeline tool that calls Groq to craft a prompt and then Stability SD3.5 to render the image."""
from __future__ import annotations

import base64
from uuid import uuid4
from typing import Any, Dict, Literal

import httpx
from pydantic import BaseModel, Field, root_validator

from .groq_chat import (
    GroqChatRequest,
    diagnostics as groq_diagnostics,
    run as groq_run,
)
from .mixbread_client import (
    add_file_to_store,
    get_mixbread_api_key,
    get_mixbread_store_id,
    upload_file,
)
from .stability_common import BaseStabilityRequest, ImageInput
from .stability_sd35_generate import (
    Sd35GenerateRequest,
    diagnostics as stability_diagnostics,
    run as stability_run,
)

DEFAULT_GROQ_TEMPLATE = (
    "You are enhancing creative briefs for Stability AI. Given the context below, "
    "write a single concise prompt tailored for Stability SD3.5. "
    "Return only the rewritten prompt without commentary.\n\nContext:\n{context}\n"
)


class StabilityGenerationOptions(BaseStabilityRequest):
    model: Literal["sd3.5-large", "sd3.5-large-turbo"] = Field(
        default="sd3.5-large",
        description="Stability SD3.5 model variant to call after Groq returns a prompt.",
    )
    mode: Literal["text-to-image", "image-to-image"] = Field(
        default="text-to-image",
        description="Render mode for SD3.5. image-to-image requires init_image + strength.",
    )
    init_image: ImageInput | None = Field(
        default=None,
        description="Reference image for image-to-image flows.",
    )
    strength: float | None = Field(
        default=0.35,
        ge=0.0,
        le=1.0,
        description="Influence of init_image (only used for image-to-image).",
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
        description="Aspect ratio when mode=text-to-image.",
    )
    negative_prompt: str | None = Field(
        default=None,
        description="Words or concepts to avoid.",
    )
    seed: int | None = Field(
        default=None,
        ge=0,
        le=4294967294,
        description="Optional deterministic seed.",
    )
    output_format: Literal["png", "jpeg", "webp"] = Field(
        default="png",
        description="Image encoding format.",
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
    ] | None = Field(
        default=None,
        description="Optional built-in style preset.",
    )

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


class MixbreadOptions(BaseModel):
    enabled: bool = Field(
        default=True,
        description="Whether to store the generated image + metadata inside a Mixedbread store.",
    )
    api_key: str | None = Field(
        default=None,
        description="Optional override for MIXBREAD_API_KEY.",
    )
    store_id: str | None = Field(
        default=None,
        description="Optional override for MIXBREAD_STORE_ID.",
    )
    external_id: str | None = Field(
        default=None,
        description="Custom identifier to reuse for overwrites (defaults to a UUID).",
    )
    overwrite: bool | None = Field(
        default=True,
        description="Controls whether uploads with the same external_id should overwrite previous ones.",
    )
    metadata_overrides: Dict[str, Any] | None = Field(
        default=None,
        description="Extra metadata to merge into the Mixbread record.",
    )
    parsing_strategy: Literal["express", "balanced", "high_quality"] | None = Field(
        default=None,
        description="Optional parsing strategy for Mixbread ingestion.",
    )
    chunking_strategy: Dict[str, Any] | None = Field(
        default=None,
        description="Advanced chunking configuration passed through to Mixbread.",
    )
    config: Dict[str, Any] | None = Field(
        default=None,
        description="Advanced ingestion config forwarded as-is.",
    )
    contextualization: bool | None = Field(
        default=None,
        description="Toggle Mixbread contextualization per upload.",
    )


class GroqToStabilityRequest(BaseModel):
    selections: Dict[str, str] = Field(
        default_factory=dict,
        description="Key/value selections from the UI (style, color, mood, etc.).",
    )
    additional_notes: list[str] | None = Field(
        default=None,
        description="Extra bullet points appended to the Groq context.",
    )
    context_override: str | None = Field(
        default=None,
        description="Provide a fully formatted context string. Overrides selections/notes when set.",
    )
    groq_prompt_template: str = Field(
        default=DEFAULT_GROQ_TEMPLATE,
        description="Template passed to Groq. The string can reference {context}.",
    )
    system_prompt: str | None = Field(
        default="You rewrite briefs into detailed Stability prompts. Return only plain text.",
        description="Optional system instructions for Groq.",
    )
    groq_model: str = Field(default="mixtral-8x7b-32768", description="Groq model name to use.")
    max_tokens: int = Field(512, ge=1, le=2048, description="Max tokens for Groq completion.")
    temperature: float = Field(0.2, ge=0.0, le=2.0, description="Sampling temperature for Groq.")
    top_p: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Nucleus sampling parameter for Groq (optional).",
    )
    stability: StabilityGenerationOptions = Field(
        default_factory=StabilityGenerationOptions,
        description="Rendering options forwarded to Stability after Groq responds.",
    )
    mixbread: MixbreadOptions | None = Field(
        default=None,
        description="Configure whether/how the resulting image should be stored inside Mixbread.",
    )

    @root_validator
    def _ensure_context_source(cls, values):
        if not values.get("context_override") and not values.get("selections"):
            raise ValueError("Provide either selections or context_override for Groq")
        return values


def _format_context(request: GroqToStabilityRequest) -> str:
    if request.context_override:
        return request.context_override.strip()

    lines: list[str] = []
    for key, value in request.selections.items():
        if not value:
            continue
        lines.append(f"{key}: {value}".strip())
    for note in request.additional_notes or []:
        if not note:
            continue
        lines.append(str(note).strip())
    return "\n".join(filter(None, lines)).strip()


def run(request: GroqToStabilityRequest) -> dict:
    context = _format_context(request)
    groq_prompt = request.groq_prompt_template.format(context=context)

    groq_request = GroqChatRequest(
        prompt=groq_prompt,
        system_prompt=request.system_prompt,
        model=request.groq_model,
        max_tokens=request.max_tokens,
        temperature=request.temperature,
        top_p=request.top_p,
    )
    groq_response = groq_run(groq_request)
    composed_prompt = groq_response["content"].strip()

    stability_payload = request.stability.dict(exclude_none=True)
    stability_payload["prompt"] = composed_prompt
    stability_request = Sd35GenerateRequest(**stability_payload)
    stability_response = stability_run(stability_request)

    mixbread_options = request.mixbread or MixbreadOptions()
    mixbread_result: dict | None = None
    if mixbread_options.enabled:
        mixbread_result = _store_with_mixbread(
            request=request,
            context=context,
            groq_prompt=groq_prompt,
            composed_prompt=composed_prompt,
            stability_response=stability_response,
            options=mixbread_options,
        )
    else:
        mixbread_result = {"status": "disabled"}

    return {
        "context": context,
        "groq_prompt": groq_prompt,
        "composed_prompt": composed_prompt,
        "groq": groq_response,
        "stability": stability_response,
        "mixbread": mixbread_result,
    }


def _store_with_mixbread(
    *,
    request: GroqToStabilityRequest,
    context: str,
    groq_prompt: str,
    composed_prompt: str,
    stability_response: dict,
    options: MixbreadOptions,
) -> dict:
    images = stability_response.get("images") or []
    if not images:
        return {"status": "skipped", "detail": "No images returned from Stability"}
    primary = images[0]
    image_base64 = primary.get("base64")
    if not image_base64:
        return {"status": "skipped", "detail": "Primary Stability image missing base64 payload"}

    try:
        api_key = get_mixbread_api_key(options.api_key)
        store_id = get_mixbread_store_id(options.store_id)
    except ValueError as exc:
        return {"status": "skipped", "detail": str(exc)}

    try:
        image_bytes = base64.b64decode(image_base64)
    except Exception as exc:  # pragma: no cover - defensive
        return {"status": "error", "detail": f"Failed to decode Stability image: {exc}"}

    mime_type = primary.get("mime_type") or f"image/{request.stability.output_format}"
    extension = request.stability.output_format.lower().replace("jpeg", "jpg")
    filename = f"tattty-{uuid4().hex}.{extension}"

    stability_options = request.stability.dict(exclude_none=True, exclude={"init_image"})
    metadata: Dict[str, Any] = {
        "selections": request.selections,
        "notes": request.additional_notes,
        "context": context,
        "groq_prompt": groq_prompt,
        "composed_prompt": composed_prompt,
        "stability": {
            "options": stability_options,
            "seed": primary.get("seed") or stability_response.get("seed"),
            "finish_reason": primary.get("finish_reason") or stability_response.get("finish_reason"),
            "request_id": stability_response.get("request_id"),
        },
    }
    if options.metadata_overrides:
        metadata.update(options.metadata_overrides)

    try:
        uploaded = upload_file(
            file_bytes=image_bytes,
            filename=filename,
            mime_type=mime_type,
            api_key=api_key,
        )
        store_file = add_file_to_store(
            api_key=api_key,
            store_id=store_id,
            file_id=uploaded["id"],
            metadata=metadata,
            external_id=options.external_id,
            overwrite=options.overwrite,
            config=options.config,
            parsing_strategy=options.parsing_strategy,
            chunking_strategy=options.chunking_strategy,
            contextualization=options.contextualization,
        )
        return {
            "status": "ok",
            "file_id": uploaded["id"],
            "store_file": store_file,
        }
    except httpx.HTTPStatusError as exc:  # type: ignore[name-defined]
        detail = exc.response.text if exc.response is not None else str(exc)
        return {"status": "error", "detail": detail}
    except Exception as exc:  # pragma: no cover - defensive
        return {"status": "error", "detail": str(exc)}


def diagnostics() -> dict:
    groq_status = groq_diagnostics()
    stability_status = stability_diagnostics()
    status = "ok" if groq_status.get("status") == "ok" and stability_status.get("status") == "ok" else "error"
    return {"status": status, "groq": groq_status, "stability": stability_status}
