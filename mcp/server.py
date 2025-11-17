"""FastAPI application that exposes MCP-style tool endpoints."""
from __future__ import annotations

import inspect
import logging
import time
from typing import Any, Awaitable, Dict

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .admin.router import router as admin_router
from .config import Settings, load_settings
from .health import railway_health_snapshot, run_deep_health
from .logging_utils import configure_logging
from .metrics import MetricsCollector
from .rate_limit import RateLimiter
from .tools import TOOL_REGISTRY, ToolDefinition

logger = logging.getLogger("mcp.server")


HandlerReturn = Awaitable[Dict[str, Any]] | Dict[str, Any]


def _validate_auth(request: Request, settings: Settings) -> None:
    if settings.allow_anonymous:
        return

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    if token != settings.secret_key:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid credentials")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    metrics = MetricsCollector()
    rate_limiter = RateLimiter()
    log_path = configure_logging(settings.log_directory)

    app = FastAPI(
        title="Streamable MCP Tooling API",
        version="1.0.0",
        description="Expose local tools over HTTP following the Model Context Protocol style.",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    if settings.cors:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors.allow_origins,
            allow_methods=settings.cors.allow_methods,
            allow_headers=settings.cors.allow_headers,
        )

    app.state.settings = settings
    app.state.metrics = metrics
    app.state.log_path = log_path
    app.state.rate_limiter = rate_limiter

    @app.middleware("http")
    async def _instrument_requests(request: Request, call_next):  # type: ignore[override]
        start = time.perf_counter()
        client_ip = request.client.host if request.client else "unknown"
        response = None
        try:
            if settings.rate_limit_per_ip:
                await rate_limiter.check(client_ip, settings.rate_limit_per_ip)
            response = await call_next(request)
            return response
        except HTTPException as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            await metrics.record(request.url.path, request.method, exc.status_code, duration_ms)
            raise
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            await metrics.record(request.url.path, request.method, 500, duration_ms)
            raise
        finally:
            if response is not None:
                duration_ms = (time.perf_counter() - start) * 1000
                await metrics.record(request.url.path, request.method, response.status_code, duration_ms)

    @app.get("/", tags=["meta"])
    async def root_summary() -> Dict[str, Any]:
        return {
            "service": "mcp-toolkit",
            "description": "HTTP-accessible MCP-compatible tool runner",
            "tools": list(TOOL_REGISTRY.keys()),
        }

    @app.get("/health", tags=["meta"])
    async def health_check() -> Dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/deep", tags=["meta"])
    async def deep_health() -> Dict[str, Any]:
        return await run_deep_health()

    @app.get("/health/railway", tags=["meta"])
    async def railway_health() -> Dict[str, Any]:
        snapshot = await metrics.snapshot()
        return await railway_health_snapshot(snapshot)

    @app.get("/mcp/tools", tags=["tools"])
    async def list_tools() -> Dict[str, Any]:
        response = []
        for name, definition in TOOL_REGISTRY.items():
            response.append(
                {
                    "name": name,
                    "description": definition.description,
                    "schema": definition.request_model.model_json_schema(),
                }
            )
        return {"status": "ok", "tools": response}

    @app.post("/mcp/{tool_name}", tags=["tools"])
    async def run_tool(tool_name: str, request: Request) -> JSONResponse:
        _validate_auth(request, settings)

        definition: ToolDefinition | None = TOOL_REGISTRY.get(tool_name)
        if not definition:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown tool '{tool_name}'")

        try:
            payload = await request.json()
        except Exception as exc:  # pragma: no cover - FastAPI already validates JSON
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body") from exc

        try:
            typed_request = definition.request_model(**payload)
        except Exception as exc:
            logger.debug("Validation error for tool %s: %s", tool_name, exc)
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

        handler_result: HandlerReturn
        try:
            handler_result = definition.handler(typed_request)
            if inspect.isawaitable(handler_result):
                handler_result = await handler_result
        except HTTPException:
            raise
        except Exception as exc:  # pragma: no cover - runtime safety
            logger.exception("Tool '%s' failed", tool_name)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Tool failed") from exc

        return JSONResponse({"status": "ok", "tool": tool_name, "result": handler_result})

    app.include_router(admin_router)

    return app


app = create_app()
