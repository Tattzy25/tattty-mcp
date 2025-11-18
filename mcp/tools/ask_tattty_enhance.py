"""Ask Tattty enhancer: polishes first-person stories via Groq."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

from pydantic import BaseModel, Field

from .groq_chat import GroqChatRequest, diagnostics as groq_diag, run as groq_run

MODEL_NAME = "openai/gpt-oss-120b"
PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "ask_tattty_system.txt"


class AskTatttyEnhanceRequest(BaseModel):
    story: str = Field(..., description="Raw first-person story supplied by the user.")
    guidance: str | None = Field(
        default=None,
        description="Optional extra notes about tone, imagery, or platform context.",
    )
    temperature: float = Field(0.4, ge=0.0, le=2.0, description="Sampling temperature for Groq.")
    max_tokens: int = Field(
        65536,
        ge=64,
        le=65536,
        description="Token cap for the enhanced story (defaults to Groq max).",
    )
    top_p: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Nucleus sampling parameter (leave unset for Groq defaults).",
    )
    model: str = Field(
        default=MODEL_NAME,
        description="Groq model name. Defaults to openai/gpt-oss-120b per TaTTTy branding.",
    )


@lru_cache(maxsize=1)
def _load_system_prompt() -> str:
    if not PROMPT_PATH.exists():
        raise FileNotFoundError(
            f"Ask Tattty system prompt missing at {PROMPT_PATH}. Did you delete the prompts file?"
        )
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def _compose_user_payload(story: str, guidance: str | None) -> str:
    story = story.strip()
    if not guidance:
        return story
    return f"{story}\n\nAdditional guidance:\n{guidance.strip()}"


def run(request: AskTatttyEnhanceRequest) -> Dict[str, Any]:
    system_prompt = _load_system_prompt()
    user_message = _compose_user_payload(request.story, request.guidance)

    groq_request = GroqChatRequest(
        prompt=user_message,
        system_prompt=system_prompt,
        model=request.model,
        max_tokens=request.max_tokens,
        temperature=request.temperature,
        top_p=request.top_p,
    )

    response = groq_run(groq_request)
    enhanced_story = response["content"].strip()

    return {
        "enhanced_story": enhanced_story,
        "model": response.get("model", request.model),
        "usage": response.get("usage"),
    }


def diagnostics() -> Dict[str, Any]:
    issues: list[str] = []
    try:
        _load_system_prompt()
    except FileNotFoundError:
        issues.append("ask_tattty_system.txt not found")
    except Exception as exc:  # pragma: no cover - defensive guard
        issues.append(f"prompt load error: {exc}")

    groq_status = groq_diag()
    if groq_status.get("status") != "ok":
        issues.append("Groq credentials missing or invalid")

    if issues:
        return {"status": "error", "detail": "; ".join(issues)}

    return {"status": "ok", "model": MODEL_NAME}
