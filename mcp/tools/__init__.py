"""Tool registry for the MCP HTTP service."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, Dict

from pydantic import BaseModel

from .ask_tattty_enhance import (
    AskTatttyEnhanceRequest,
    diagnostics as ask_tattty_diag,
    run as ask_tattty_run,
)
from .echo import EchoRequest, diagnostics as echo_diag, run as echo_run
from .groq_chat import GroqChatRequest, diagnostics as groq_diag, run as groq_run
from .groq_to_stability import (
    GroqToStabilityRequest,
    diagnostics as groq_to_stability_diag,
    run as groq_to_stability_run,
)
from .resize_image import (
    ResizeImageRequest,
    diagnostics as resize_image_diag,
    run as resize_image_run,
)
from .stability_control_sketch import (
    ControlSketchRequest,
    diagnostics as control_sketch_diag,
    run as control_sketch_run,
)
from .stability_control_structure import (
    ControlStructureRequest,
    diagnostics as control_structure_diag,
    run as control_structure_run,
)
from .stability_control_style import (
    ControlStyleRequest,
    diagnostics as control_style_diag,
    run as control_style_run,
)
from .stability_control_style_transfer import (
    ControlStyleTransferRequest,
    diagnostics as control_style_transfer_diag,
    run as control_style_transfer_run,
)
from .stability_remove_background import (
    RemoveBackgroundRequest,
    diagnostics as remove_background_diag,
    run as remove_background_run,
)
from .stability_replace_background import (
    ReplaceBackgroundRequest,
    diagnostics as replace_background_diag,
    run as replace_background_run,
)
from .stability_sd35_generate import (
    Sd35GenerateRequest,
    diagnostics as sd35_diag,
    run as sd35_run,
)
from .stability_upscale_conservative import (
    ConservativeUpscaleRequest,
    diagnostics as upscale_conservative_diag,
    run as upscale_conservative_run,
)
from .text_stats import TextStatsRequest, diagnostics as text_stats_diag, run as text_stats_run

ToolHandler = Callable[[BaseModel], Awaitable[dict] | dict]


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    request_model: type[BaseModel]
    handler: ToolHandler
    description: str
    diagnostic: Callable[[], dict] | None = None


TOOL_REGISTRY: Dict[str, ToolDefinition] = {
    "echo": ToolDefinition(
        request_model=EchoRequest,
        handler=echo_run,
        description="Returns the supplied string along with request metadata.",
        diagnostic=echo_diag,
    ),
    "ask_tattty_enhance": ToolDefinition(
        request_model=AskTatttyEnhanceRequest,
        handler=ask_tattty_run,
        description="Polish first-person stories with the TaTTTy enhancer (Groq).",
        diagnostic=ask_tattty_diag,
    ),
    "resize_image": ToolDefinition(
        request_model=ResizeImageRequest,
        handler=resize_image_run,
        description="Downloads an image, resizes it, and returns a base64-encoded PNG.",
        diagnostic=resize_image_diag,
    ),
    "text_stats": ToolDefinition(
        request_model=TextStatsRequest,
        handler=text_stats_run,
        description="Counts characters, words, and sentences in supplied text.",
        diagnostic=text_stats_diag,
    ),
    "groq_chat": ToolDefinition(
        request_model=GroqChatRequest,
        handler=groq_run,
        description="Calls the Groq chat completion API and returns the reply.",
        diagnostic=groq_diag,
    ),
    "groq_to_stability": ToolDefinition(
        request_model=GroqToStabilityRequest,
        handler=groq_to_stability_run,
        description="Compose a prompt with Groq and immediately render it with Stability SD3.5.",
        diagnostic=groq_to_stability_diag,
    ),
    "stability_sd35_generate": ToolDefinition(
        request_model=Sd35GenerateRequest,
        handler=sd35_run,
        description="Generate images with Stability SD3.5 Large or Large Turbo.",
        diagnostic=sd35_diag,
    ),
    "stability_remove_background": ToolDefinition(
        request_model=RemoveBackgroundRequest,
        handler=remove_background_run,
        description="Remove backgrounds using the Stability edit/remove-background endpoint.",
        diagnostic=remove_background_diag,
    ),
    "stability_replace_background": ToolDefinition(
        request_model=ReplaceBackgroundRequest,
        handler=replace_background_run,
        description="Replace backgrounds and relight subjects via Stability's async tool.",
        diagnostic=replace_background_diag,
    ),
    "stability_upscale_conservative": ToolDefinition(
        request_model=ConservativeUpscaleRequest,
        handler=upscale_conservative_run,
        description="Conservative 4x upscaling with optional creativity control.",
        diagnostic=upscale_conservative_diag,
    ),
    "stability_control_sketch": ToolDefinition(
        request_model=ControlSketchRequest,
        handler=control_sketch_run,
        description="Sketch-to-image control guidance for SD3.5.",
        diagnostic=control_sketch_diag,
    ),
    "stability_control_structure": ToolDefinition(
        request_model=ControlStructureRequest,
        handler=control_structure_run,
        description="Structure guidance control for layout-preserving generations.",
        diagnostic=control_structure_diag,
    ),
    "stability_control_style": ToolDefinition(
        request_model=ControlStyleRequest,
        handler=control_style_run,
        description="Style guide control to match a reference's aesthetic.",
        diagnostic=control_style_diag,
    ),
    "stability_control_style_transfer": ToolDefinition(
        request_model=ControlStyleTransferRequest,
        handler=control_style_transfer_run,
        description="Style transfer combining init and style reference images.",
        diagnostic=control_style_transfer_diag,
    ),
}

__all__ = ["ToolDefinition", "TOOL_REGISTRY"]
