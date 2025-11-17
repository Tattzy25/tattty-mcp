"""Admin panel routes and helpers."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Form, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..config import Settings
from ..health import railway_health_snapshot, run_deep_health
from ..logging_utils import tail_file

TEMPLATE_DIR = Path(__file__).with_name("templates")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

router = APIRouter(prefix="/admin", tags=["admin"])


def _extract_token(request: Request) -> str | None:
    header = request.headers.get("x-admin-token")
    if header:
        return header
    cookie = request.cookies.get("admin_token")
    if cookie:
        return cookie
    return request.query_params.get("token")


def _require_admin(request: Request) -> None:
    settings: Settings = request.app.state.settings
    if not settings.admin_token:
        return
    supplied = _extract_token(request)
    if supplied != settings.admin_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")


def _set_cookie_if_needed(response: Response, request: Request) -> None:
    settings: Settings = request.app.state.settings
    token = _extract_token(request)
    if not settings.admin_token or token != settings.admin_token:
        return
    if request.cookies.get("admin_token") == token:
        return
    response.set_cookie("admin_token", token, httponly=True, max_age=3600)


@router.get("/")
async def dashboard(request: Request) -> Response:
    _require_admin(request)
    metrics = await request.app.state.metrics.snapshot()
    deep = await run_deep_health()
    settings: Settings = request.app.state.settings
    context = {
        "request": request,
        "settings": settings,
        "metrics": metrics,
        "deep_status": deep["status"],
        "deep_json": json.dumps(deep, indent=2),
        "metrics_json": json.dumps(metrics, indent=2),
        "token_hint": _extract_token(request) or "",
    }
    response = templates.TemplateResponse("admin/dashboard.html", context)
    _set_cookie_if_needed(response, request)
    return response


@router.post("/settings")
async def update_settings(
    request: Request,
    allow_anonymous: str = Form("off"),
    rate_limit_per_ip: str | None = Form(None),
    secret_key: str | None = Form(None),
    token: str | None = Form(None),
) -> Response:
    _require_admin(request)
    settings: Settings = request.app.state.settings

    settings.allow_anonymous = allow_anonymous == "on"
    settings.rate_limit_per_ip = int(rate_limit_per_ip) if rate_limit_per_ip else None
    if secret_key is not None:
        settings.secret_key = secret_key or None

    redirect = RedirectResponse(url=f"/admin?token={token or ''}", status_code=status.HTTP_303_SEE_OTHER)
    _set_cookie_if_needed(redirect, request)
    return redirect


@router.get("/api/metrics")
async def metrics_api(request: Request) -> Dict[str, Any]:
    _require_admin(request)
    return await request.app.state.metrics.snapshot()


@router.get("/api/health/deep")
async def deep_health_api(request: Request) -> Dict[str, Any]:
    _require_admin(request)
    return await run_deep_health()


@router.get("/api/health/railway")
async def railway_health_api(request: Request) -> Dict[str, Any]:
    _require_admin(request)
    metrics = await request.app.state.metrics.snapshot()
    return await railway_health_snapshot(metrics)


@router.get("/api/logs")
async def logs_api(request: Request, lines: int = 120) -> JSONResponse:
    _require_admin(request)
    log_path: Path = request.app.state.log_path
    content = tail_file(log_path, lines)
    return JSONResponse({"path": str(log_path), "tail": content})