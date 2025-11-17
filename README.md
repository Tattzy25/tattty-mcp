# Streamable MCP HTTP Toolkit

A production-ready FastAPI application that exposes MCP-style tools over plain HTTP. The server ships with three tools (echo, resize-image, text-stats), supports bearer auth, per-IP rate limiting, OpenAPI docs, an authenticated admin panel, health checks (including Railway-specific reporting), structured JSON logging, and can be deployed via Docker, ngrok, or any container platform.

## Prerequisites

- Python 3.12+
- PowerShell (Windows) or any POSIX shell
- Optional: Docker for container deployments

## Quick Start

```powershell
cd C:\Users\relay\Downloads\TATTTY-MCP
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn mcp.server:app --host 0.0.0.0 --port 8000
```

Swagger UI is available at `http://localhost:8000/docs`.

## Configuring the Server

All tunables live in `mcp/config.yaml`:

| Key | Description | Default |
| --- | --- | --- |
| `host` | Interface for uvicorn | `0.0.0.0` |
| `port` | Listening port | `8000` |
| `log_level` | Uvicorn log level | `info` |
| `allow_anonymous` | Allow unauthenticated access | `true` |
| `secret_key` | Required when `allow_anonymous=false` | `null` |
| `rate_limit_per_ip` | Requests/minute per IP (built-in limiter) | `30` |
| `admin_token` | Enables the `/admin` console when set | `null` |
| `log_directory` | Folder for JSON logs | `logs` |
| `cors.*` | Allowed origins/methods/headers | `*` |

Environment overrides are also supported (e.g. `MCP_PORT=9000`, `MCP_ADMIN_TOKEN=supersecret`, `MCP_LOG_DIR=C:\\data\\logs`).

## Built-in Tools

| Tool | Description | Sample Call |
| --- | --- | --- |
| `echo` | Returns your message plus metadata. | `curl -X POST http://localhost:8000/mcp/echo -H "Content-Type: application/json" -d '{"message":"Hi"}'` |
| `resize_image` | Resizes a remote image and returns base64 PNG/JPEG/WEBP. | `curl -X POST http://localhost:8000/mcp/resize_image -H "Content-Type: application/json" -d '{"image_url":"https://i.imgur.com/xyz.png","width":320,"height":240,"format":"PNG"}'` |
| `text_stats` | Counts characters, words, sentences, and reading time. | `curl -X POST http://localhost:8000/mcp/text_stats -H "Content-Type: application/json" -d '{"text":"Hello world!"}'` |

Add more tools by dropping a new module in `mcp/tools/` and registering it inside `mcp/tools/__init__.py`.

## Admin & Observability

Set `MCP_ADMIN_TOKEN` (or `admin_token` inside `config.yaml`) to enable the authenticated control panel at `/admin`. Provide the token via query string (`/admin?token=...`) or the `X-Admin-Token` header. The dashboard offers:

- Deep health runs plus a Railway-formatted snapshot on-demand
- Runtime settings management (`allow_anonymous`, rate limit, shared secret)
- Live metrics (uptime, request counters, recent request log)
- Tail of the structured JSON log stored under `logs/mcp.log` (override via `MCP_LOG_DIR`)

All dashboard actions proxy to JSON APIs under `/admin/api/*`, which you can call directly from external observability tools if desired.

## Health Checks

In addition to the lightweight `/health`, two richer endpoints ship with the server:

- `/health/deep` — exercises disk space, outbound HTTP, Pillow, and every MCP tool diagnostic.
- `/health/railway` — wraps the deep check with hostname, metrics, and platform data. This format matches Railway's deployment health expectations (HTTP 200 within a 5-minute deploy window, hitting the `healthcheck.railway.app` hostname, per Tavily docs).

Deployments on Railway should point the health check to `/health/railway`. The endpoint responds quickly, surfaces failures in the JSON payload, and remains idle outside deploy windows, exactly as Railway's documentation describes.

## Running via Docker

```powershell
docker build -t mcp-toolkit .
docker run -p 8000:8000 --env MCP_ALLOW_ANONYMOUS=true mcp-toolkit
```

Deploy the same image to Render/Railway/Fly.io or your own VPS. Expose `/mcp/<tool>` endpoints publicly; `/docs` auto-documents the API.

## Public Sharing with ngrok

```powershell
ngrok http 8000
```

Forward the resulting URL to collaborators (e.g. `https://abcd1234.ngrok.io/mcp/echo`).

## Rate Limiting & Auth

- A lightweight in-memory limiter caps every IP at 30 requests/minute. Adjust `rate_limit_per_ip` (or set to `null`) to tune or disable.
- Set `allow_anonymous: false` and provide `secret_key` to require `Authorization: Bearer <key>` headers per tool call.
- Use `MCP_ADMIN_TOKEN` to protect the admin panel and its APIs.

## Testing

Install the optional dev dependency and run the smoke tests below:

```powershell
pip install httpx  # required for FastAPI TestClient
& .\.venv\Scripts\python.exe -c "from fastapi.testclient import TestClient; from mcp.server import app; client=TestClient(app); assert client.post('/mcp/echo', json={'message':'ping'}).status_code==200"
```

## Deployment Notes

1. Commit this repo to GitHub.
2. Hook Render/Railway/Fly.io to the repo and deploy using the provided Dockerfile.
3. Share `/docs` for discovery or `/openapi.json` for programmatic integration.

### Next Ideas

- Wrap CLI utilities (ffmpeg, pandoc, git) directly from tool handlers.
- Stream large responses via `StreamingResponse` for chunked tool output.
- Ship logs to a managed service (Papertrail, Logtail) for observability.
