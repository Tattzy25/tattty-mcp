"""Text statistics helper."""
from __future__ import annotations

import math
import re

from pydantic import BaseModel, Field

WORD_PATTERN = re.compile(r"\b[\w'-]+\b")
SENTENCE_PATTERN = re.compile(r"[.!?]+")


class TextStatsRequest(BaseModel):
    text: str = Field(..., description="Input text to analyse")
    words_per_minute: int = Field(200, ge=80, le=400, description="Average reading speed")


def run(request: TextStatsRequest) -> dict:
    """Compute simple statistics for the provided text."""

    stripped = request.text.strip()
    words = WORD_PATTERN.findall(stripped)
    sentences = [segment for segment in SENTENCE_PATTERN.split(stripped) if segment.strip()]

    reading_time_minutes = len(words) / request.words_per_minute if words else 0.0

    return {
        "characters": len(stripped),
        "words": len(words),
        "sentences": len(sentences),
        "estimated_reading_minutes": round(reading_time_minutes, 3),
    }


def diagnostics() -> dict:
    sample = TextStatsRequest(text="hello world")
    result = run(sample)
    return {"status": "ok", "sample_words": result["words"]}
