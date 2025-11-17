"""Image resize tool built on Pillow."""
from __future__ import annotations

import base64
import io
from typing import Literal

import requests
from PIL import Image
from pydantic import BaseModel, Field, HttpUrl, PositiveInt

SUPPORTED_FORMATS = {"PNG", "JPEG", "WEBP"}


class ResizeImageRequest(BaseModel):
    image_url: HttpUrl = Field(..., description="Remote image to fetch")
    width: PositiveInt = Field(..., description="Output width in pixels")
    height: PositiveInt = Field(..., description="Output height in pixels")
    format: Literal["PNG", "JPEG", "WEBP"] = Field(
        "PNG", description="Output format; defaults to PNG"
    )


def _encode_image(image: Image.Image, fmt: str) -> str:
    with io.BytesIO() as buffer:
        image.save(buffer, format=fmt)
        return base64.b64encode(buffer.getvalue()).decode("ascii")


def run(request: ResizeImageRequest) -> dict:
    """Download an image, resize it, and return a base64 string."""

    response = requests.get(str(request.image_url), timeout=15)
    response.raise_for_status()

    with Image.open(io.BytesIO(response.content)) as image:
        image = image.convert("RGBA")
        resized = image.resize((request.width, request.height), Image.Resampling.LANCZOS)

    fmt = request.format.upper()
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported format {fmt}")

    encoded = _encode_image(resized, fmt)
    return {
        "format": fmt,
        "width": request.width,
        "height": request.height,
        "base64_image": encoded,
    }


def diagnostics() -> dict:
    image = Image.new("RGBA", (8, 8), color=(0, 0, 0, 255))
    resized = image.resize((4, 4), Image.Resampling.LANCZOS)
    checksum = sum(resized.getdata()[0])
    return {"status": "ok", "checksum": checksum}
