"""FastMCP-compliant JSON-RPC server with HTTP streaming."""
from __future__ import annotations

import asyncio
import inspect
import json
import logging
import time
import uuid
from typing import Any, Awaitable, AsyncGenerator, Dict

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from .admin.router import router as admin_router
from .config import Settings, load_settings
from .health import railway_health_snapshot, run_deep_health
from .logging_utils import configure_logging
from .metrics import MetricsCollector
from .rate_limit import RateLimiter
from .tools import TOOL_REGISTRY, ToolDefinition

logger = logging.getLogger("mcp.server")

JSONRPC_VERSION = "2.0"
PROTOCOL_VERSION = "2025-03-26"
SESSION_TTL_SECONDS = 3600
HEARTBEAT_SECONDS = 15.0

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


class Session:
    """Tracks per-client state for JSON-RPC + SSE streaming."""

    def __init__(self, session_id: str) -> None:
        self.id = session_id
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.created_at = time.monotonic()
        self.updated_at = self.created_at
        self.tasks: set[asyncio.Task[Any]] = set()

    def touch(self) -> None:
        self.updated_at = time.monotonic()

    def expired(self, ttl: float) -> bool:
        return (time.monotonic() - self.updated_at) > ttl

    def enqueue(self, payload: Dict[str, Any]) -> None:
        message = json.dumps(payload, separators=(",", ":"))
        self.queue.put_nowait(message)
        self.touch()

    def add_task(self, task: asyncio.Task[Any]) -> None:
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)


class SessionStore:
    def __init__(self, ttl_seconds: int) -> None:
        self._sessions: dict[str, Session] = {}
        self._ttl = ttl_seconds
        self._lock = asyncio.Lock()

    async def create(self) -> Session:
        session_id = f"sess_{uuid.uuid4().hex[:16]}"
        session = Session(session_id)
        async with self._lock:
            self._sessions[session_id] = session
        return session

    async def get(self, session_id: str | None) -> Session | None:
        if not session_id:
            return None
        async with self._lock:
            session = self._sessions.get(session_id)
        if session and session.expired(self._ttl):
            await self.remove(session_id)
            return None
        if session:
            session.touch()
        return session

    async def remove(self, session_id: str) -> None:
        async with self._lock:
            session = self._sessions.pop(session_id, None)
        if not session:
            return
        for task in list(session.tasks):
            task.cancel()
        session.enqueue(
            {
                "jsonrpc": JSONRPC_VERSION,
                "method": "notifications/session_closed",
                "params": {"sessionId": session_id},
            }
        )

    async def cleanup(self) -> None:
        async with self._lock:
            expired = [sid for sid, sess in self._sessions.items() if sess.expired(self._ttl)]
        for sid in expired:
            await self.remove(sid)


def _jsonrpc_error(id_value: Any, code: int, message: str, data: Any | None = None) -> Dict[str, Any]:
    error: Dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": JSONRPC_VERSION, "id": id_value, "error": error}


def _json_dumps(payload: Any) -> str:
    def _default(value: Any) -> str:
        return str(value)

    return json.dumps(payload, default=_default, separators=(",", ":"))


async def _maybe_await(result: HandlerReturn) -> Dict[str, Any]:
    if inspect.isawaitable(result):
        return await result  # type: ignore[return-value]
    return result  # type: ignore[return-value]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    metrics = MetricsCollector()
    rate_limiter = RateLimiter()
    log_path = configure_logging(settings.log_directory)
    session_store = SessionStore(SESSION_TTL_SECONDS)

    app = FastAPI(
        title="FastMCP JSON-RPC Server",
        version="1.0.0",
        description="Implements the MCP HTTP transport with JSON-RPC 2.0 and SSE progress streams.",
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
    app.state.session_store = session_store

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
            "service": "fastmcp-server",
            "description": "JSON-RPC MCP endpoint with SSE streaming.",
            "protocolVersion": PROTOCOL_VERSION,
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

    async def _ensure_session(session_id: str | None) -> Session:
        session = await session_store.get(session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired session")
        return session

    async def _event_generator(request: Request, session: Session) -> AsyncGenerator[str, None]:
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(session.queue.get(), timeout=HEARTBEAT_SECONDS)
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    heartbeat = {
                        "jsonrpc": JSONRPC_VERSION,
                        "method": "notifications/heartbeat",
                        "params": {"sessionId": session.id, "timestamp": time.time()},
                    }
                    yield f"data: {_json_dumps(heartbeat)}\n\n"
        finally:
            session.touch()

    def _emit_progress(session: Session, request_id: Any, tool: str, progress: int, message: str) -> None:
        session.enqueue(
            {
                "jsonrpc": JSONRPC_VERSION,
                "method": "notifications/progress",
                "params": {
                    "requestId": request_id,
                    "tool": tool,
                    "progress": progress,
                    "total": 100,
                    "message": message,
                },
            }
        )

    async def _execute_tool(
        *,
        session: Session,
        rpc_id: Any,
        definition: ToolDefinition,
        typed_request,
        tool_name: str,
    ) -> None:
        def progress_callback(progress: int, message: str) -> None:
            _emit_progress(session, rpc_id, tool_name, progress, message)

        if not definition.supports_progress:
            progress_callback(0, f"Running {tool_name}")

        try:
            if definition.supports_progress:
                result = definition.handler(typed_request, progress_callback=progress_callback)
            else:
                result = definition.handler(typed_request)
            resolved = await _maybe_await(result)
        except HTTPException as exc:
            session.enqueue(
                _jsonrpc_error(
                    rpc_id,
                    -32000,
                    "HTTP error",
                    {"status": exc.status_code, "detail": exc.detail},
                )
            )
            return
        except Exception as exc:  # pragma: no cover - runtime safety
            logger.exception("Tool '%s' failed", tool_name)
            session.enqueue(_jsonrpc_error(rpc_id, -32603, "Tool failed", str(exc)))
            return

        if not definition.supports_progress:
            progress_callback(100, "Complete")

        session.enqueue(
            {
                "jsonrpc": JSONRPC_VERSION,
                "id": rpc_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": _json_dumps(resolved),
                        }
                    ]
                },
            }
        )

    def _list_tools_payload() -> list[Dict[str, Any]]:
        tools: list[Dict[str, Any]] = []
        for name, definition in TOOL_REGISTRY.items():
            tools.append(
                {
                    "name": name,
                    "description": definition.description,
                    "inputSchema": definition.request_model.model_json_schema(),
                }
            )
        return tools

    @app.post("/mcp")
    async def mcp_post_handler(request: Request) -> Response:
        _validate_auth(request, settings)
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(_jsonrpc_error(None, -32700, "Parse error"), status_code=400)

        if not isinstance(body, dict):
            return JSONResponse(_jsonrpc_error(None, -32600, "Invalid Request"), status_code=400)

        method = body.get("method")
        rpc_id = body.get("id")
        params = body.get("params", {})

        if method == "initialize":
            session = await session_store.create()
            result = {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
                "serverInfo": {"name": "tattzy-mcp", "version": "1.0.0"},
                "sessionId": session.id,
            }
            response = JSONResponse({"jsonrpc": JSONRPC_VERSION, "id": rpc_id, "result": result})
            response.headers["Mcp-Session-Id"] = session.id
            return response

        session_id = request.headers.get("Mcp-Session-Id")
        try:
            session = await _ensure_session(session_id)
        except HTTPException as exc:
            return JSONResponse(_jsonrpc_error(rpc_id, -32000, exc.detail), status_code=exc.status_code)

        response_headers = {"Mcp-Session-Id": session.id}

        if method == "tools/list":
            result = {"tools": _list_tools_payload()}
            return JSONResponse(
                {"jsonrpc": JSONRPC_VERSION, "id": rpc_id, "result": result},
                headers=response_headers,
            )

        if method == "tools/call":
            tool_name = params.get("name") if isinstance(params, dict) else None
            arguments = params.get("arguments", {}) if isinstance(params, dict) else {}
            definition = TOOL_REGISTRY.get(tool_name)
            if not definition:
                return JSONResponse(_jsonrpc_error(rpc_id, -32601, "Tool not found"), headers=response_headers)

            try:
                typed_request = definition.request_model(**arguments)
            except Exception as exc:
                return JSONResponse(
                    _jsonrpc_error(rpc_id, -32602, "Invalid params", str(exc)),
                    headers=response_headers,
                )

            task = asyncio.create_task(
                _execute_tool(
                    session=session,
                    rpc_id=rpc_id,
                    definition=definition,
                    typed_request=typed_request,
                    tool_name=tool_name,
                )
            )
            session.add_task(task)
            session_store_task = asyncio.create_task(session_store.cleanup())
            session.add_task(session_store_task)
            return JSONResponse(
                {"jsonrpc": JSONRPC_VERSION, "id": rpc_id, "result": {"status": "processing"}},
                headers=response_headers,
            )

        return JSONResponse(
            _jsonrpc_error(rpc_id, -32601, "Method not found"),
            headers=response_headers,
        )

    @app.get("/mcp")
    async def mcp_sse_handler(request: Request) -> StreamingResponse:
        _validate_auth(request, settings)
        session_id = request.headers.get("Mcp-Session-Id")
        session = await _ensure_session(session_id)

        headers = {
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
            "Mcp-Session-Id": session.id,
        }

        async def streamer() -> AsyncGenerator[str, None]:
            async for chunk in _event_generator(request, session):
                yield chunk

        return StreamingResponse(streamer(), headers=headers, media_type="text/event-stream")

    app.include_router(admin_router)

    return app


app = create_app()
