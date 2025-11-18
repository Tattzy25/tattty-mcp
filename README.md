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
| `groq_chat` | Sends a prompt to Groq's chat completion API (requires `GROQ_API_KEY`). | `curl -X POST http://localhost:8000/mcp/groq_chat -H "Content-Type: application/json" -d '{"prompt":"Summarise this server"}'` |
| `ask_tattty_enhance` | Enhances first-person stories with the TaTTTy prompt-polish workflow (Groq `openai/gpt-oss-120b`). | `curl -X POST http://localhost:8000/mcp/ask_tattty_enhance -H "Content-Type: application/json" -d '{"story":"my raw story"}'` |
| `stability_sd35_generate` | Text/image-to-image generation via SD3.5 Large/Large Turbo. | `curl -X POST http://localhost:8000/mcp/stability_sd35_generate -H "Content-Type: application/json" -d '{"prompt":"a neon fox","model":"sd3.5-large"}'` |
| `stability_remove_background` | Removes backgrounds while keeping transparent output. | `curl -X POST http://localhost:8000/mcp/stability_remove_background -H "Content-Type: application/json" -d '{"image":{"url":"https://..."}}'` |
| `stability_replace_background` | Async background replacement + relight with optional references. | `curl -X POST http://localhost:8000/mcp/stability_replace_background -H "Content-Type: application/json" -d '{"subject_image":{"url":"https://..."},"background_prompt":"studio backdrop"}'` |
| `stability_upscale_conservative` | Conservative upscaler with creativity + prompt guidance. | `curl -X POST http://localhost:8000/mcp/stability_upscale_conservative -H "Content-Type: application/json" -d '{"prompt":"hi-res portrait","image":{"url":"https://..."}}'` |
| `stability_control_sketch` | Sketch control (structure derived from a drawing). | `curl -X POST http://localhost:8000/mcp/stability_control_sketch -H "Content-Type: application/json" -d '{"prompt":"render the sketch","image":{"url":"https://..."}}'` |
| `stability_control_structure` | Structure control (layout guidance from reference image). | `curl -X POST http://localhost:8000/mcp/stability_control_structure -H "Content-Type: application/json" -d '{"prompt":"evening city","image":{"url":"https://..."}}'` |
| `stability_control_style` | Style Guide (apply aesthetic from a single reference). | `curl -X POST http://localhost:8000/mcp/stability_control_style -H "Content-Type: application/json" -d '{"prompt":"vintage poster","image":{"url":"https://..."}}'` |
| `stability_control_style_transfer` | Style Transfer (init + style images, optional prompts). | `curl -X POST http://localhost:8000/mcp/stability_control_style_transfer -H "Content-Type: application/json" -d '{"init_image":{"url":"https://..."},"style_image":{"url":"https://..."}}'` |
| `groq_to_stability` | Single call that asks Groq for a revised prompt/context and feeds it into SD3.5. | `curl -X POST http://localhost:8000/mcp/groq_to_stability -H "Content-Type: application/json" -d '{"prompt":"cyberpunk mascot","context":{"audience":"mobile gamers"}}'` |

Add more tools by dropping a new module in `mcp/tools/` and registering it inside `mcp/tools/__init__.py`.

### Stability AI Tools

- Export `STABILITY_API_KEY` (Railway secret, `.env`, etc). All Stability-backed tools default to this server-wide key but also accept an optional `stability_api_key` field per request so you can bring-your-own credential later without redeploying.
- Optional tuning knobs: `STABILITY_API_BASE` (useful for staging), `STABILITY_HTTP_TIMEOUT`, `STABILITY_POLL_INTERVAL`, and `STABILITY_POLL_ATTEMPTS`.
- Every Stability endpoint returns structured JSON with `images` (base64 payloads + metadata) and never exposes `/v2beta/results/{id}` as a public MCP tool. The only async flow (replace-background + relight) polls that endpoint internally and surfaces the ready image in a single response.
- SD3.5 generation restricts `model` to `sd3.5-large` and `sd3.5-large-turbo`, matching the allowed plans.
- Inputs that accept binary data use an `ImageInput` shape: either `{"url": "https://..."}` or `{"base64_data": "..."}` plus optional `filename`/`content_type` hints.

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

### Groq API

- Export `GROQ_API_KEY` (or set in your Railway/Azure/Docker environment) before calling `/mcp/groq_chat`.
- Optional fields: `system_prompt`, `model`, `max_tokens`, `temperature`.
- The tool returns the response content plus Groq usage metadata.

#### Ask Tattty Enhancer

- `/mcp/ask_tattty_enhance` routes raw, first-person stories through the TaTTTy system prompt stored at `mcp/prompts/ask_tattty_system.txt` so copy updates stay centralized.
- Requires `GROQ_API_KEY` and targets Groq model `openai/gpt-oss-120b` by default (override with `model` if Groq adds a newer OSS tier).
- Request body: `story` (required), optional `guidance` (tone, target audience, etc.), plus standard sampling knobs (`temperature`, `max_tokens`, `top_p`).
- Response returns the polished `enhanced_story`, along with the Groq `model` + `usage` metadata you can pipe into downstream tooling.

### Groq → Stability Chain

- `/mcp/groq_to_stability` bundles Groq chat + Stability SD3.5 in one request. Provide the high-level `prompt`, optional `context` metadata (target user, business constraints, etc.), plus `stability_options` to override SD3.5 params like `model`, `creativity_scale`, or `image_reference` URLs/base64.
- Requires both `GROQ_API_KEY` and `STABILITY_API_KEY` to be present (or passed inline using `stability_api_key`). The handler formats the context for Groq, relays the resulting text into SD3.5, and returns the raw Groq message plus Stability image payloads.
- Ideal when front-ends should not juggle two separate API calls. The server performs all chaining, logging, and error reporting in a single MCP tool invocation.
- Set `MIXBREAD_API_KEY` + `MIXBREAD_STORE_ID` to automatically archive each render inside a Mixedbread store. The request body accepts an optional `mixbread` object (enable/disable, override store ID, provide metadata overrides, etc.) if you need per-call control.

### Mixedbread Storage

- Export `MIXBREAD_API_KEY` and `MIXBREAD_STORE_ID` so the server can upload generated PNG/JPEGs to `https://api.mixedbread.com/v1/files` and reference them inside your chosen store with structured metadata (prompt, selections, seeds, etc.).
- Advanced ingestion knobs from the API (`parsing_strategy`, `chunking_strategy`, `contextualization`, `external_id`, `overwrite`, custom `metadata`) can be supplied via the `mixbread` object in `/mcp/groq_to_stability`.
- Mixbread uploads are best-effort; if the API key/store ID are missing, the MCP tool still returns the Groq + Stability result and reports that storage was skipped.

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
