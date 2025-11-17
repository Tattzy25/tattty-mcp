"""Groq chat completion tool."""
from __future__ import annotations

import os
from typing import Any, Dict

import httpx
from pydantic import BaseModel, Field

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "mixtral-8x7b-32768"


class GroqChatRequest(BaseModel):
    prompt: str = Field(..., description="User message to send to Groq")
    system_prompt: str | None = Field(
        default="You are a concise assistant returning plain text responses.",
        description="Optional system instructions",
    )
    model: str = Field(DEFAULT_MODEL, description="Groq model name")
    max_tokens: int = Field(512, ge=1, le=8192, description="Maximum tokens to generate")
    temperature: float = Field(0.2, ge=0.0, le=2.0, description="Sampling temperature")
    top_p: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Nucleus sampling parameter. Leave blank to use Groq defaults.",
    )


def _get_api_key() -> str:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set in the environment")
    return api_key


def _call_groq(payload: Dict[str, Any], api_key: str) -> Dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=30) as client:
        response = client.post(GROQ_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()


def run(request: GroqChatRequest) -> dict:
    api_key = _get_api_key()
    messages = []
    if request.system_prompt:
        messages.append({"role": "system", "content": request.system_prompt})
    messages.append({"role": "user", "content": request.prompt})

    payload = {
        "model": request.model,
        "messages": messages,
        "max_tokens": request.max_tokens,
        "temperature": request.temperature,
    }

    if request.top_p is not None:
        payload["top_p"] = request.top_p

    data = _call_groq(payload, api_key)

    choices = data.get("choices", [])
    if not choices:
        raise ValueError("Groq API returned no choices")

    message = choices[0]["message"]["content"].strip()
    usage = data.get("usage", {})

    return {
        "model": data.get("model", request.model),
        "content": message,
        "usage": usage,
        "raw": {"id": data.get("id"), "created": data.get("created")},
    }


def diagnostics() -> dict:
    if os.environ.get("GROQ_API_KEY"):
        return {"status": "ok"}
    return {"status": "error", "detail": "GROQ_API_KEY missing"}
