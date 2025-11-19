MCP + MIXEDBREAD SCHEMA (CURRENT STATE)
=====================================

1. Transport Layer
------------------
Endpoint Overview:
- POST /mcp
  * Methods: initialize, tools/list, tools/call
  * Content-Type: application/json
  * Headers: optional Authorization: Bearer <secret>, echoes Mcp-Session-Id after initialize
- GET /mcp (SSE)
  * Headers: Mcp-Session-Id required
  * Streams notifications/progress, notifications/heartbeat, final results, notifications/session_closed
Supporting Routes: /, /health, /health/deep, /health/railway, /admin/* (requires MCP_ADMIN_TOKEN when set)

Session Lifecycle:
- SessionStore issues IDs "sess_<16 hex>" (TTL 3600s)
- Session fields: id, queue, created_at, updated_at, tasks
- Heartbeat event every 15 seconds when idle

Event Payloads:
- Progress: {"jsonrpc":"2.0","method":"notifications/progress","params":{"requestId":<rpc_id>,"tool":<name>,"progress":0-100,"total":100,"message":"..."}}
- Heartbeat: {"jsonrpc":"2.0","method":"notifications/heartbeat","params":{"sessionId":<id>,"timestamp":<epoch>}}
- Final result: {"jsonrpc":"2.0","id":<rpc_id>,"result":{"content":[{"type":"text","text":<JSON-stringified tool result>}]}}
- Session closed: notifications/session_closed

2. Tool Registry (mcp/tools/__init__.py)
---------------------------------------
All tools emit JSON schema via tools/list. Current registry keys:
1. echo – EchoRequest{text, metadata?}
2. ask_tattty_enhance – Groq-based enhancer (stream capable)
3. resize_image – Downloads URL, outputs resized base64 PNG
4. text_stats – Character/word/sentence counts
5. groq_chat – Direct Groq chat completion gateway
6. groq_to_stability – Groq prompt + Stability SD3.5 render + Mixedbread upload (supports progress)
7. stability_sd35_generate – Raw SD3.5 generator
8. stability_remove_background
9. stability_replace_background
10. stability_upscale_conservative
11. stability_control_sketch
12. stability_control_structure
13. stability_control_style
14. stability_control_style_transfer

Each ToolDefinition stores request_model, handler, description, optional diagnostic + stream handler, supports_progress flag.

3. groq_to_stability Payloads
-----------------------------
Request (GroqToStabilityRequest):
- selections: Record<string,string> (style, color, mood, placement, size, model, aspect_ratio, etc.)
- additional_notes?: string[]
- context_override?: string (if provided, bypasses selections)
- groq_prompt_template (default = DEFAULT_GROQ_TEMPLATE)
- system_prompt (default instructs Groq to output plain prompt)
- groq_model, max_tokens, temperature, top_p
- stability: StabilityGenerationOptions
  * model ∈ {sd3.5-large, sd3.5-large-turbo}
  * mode: text-to-image | image-to-image (with init_image + strength)
  * aspect_ratio ∈ {21:9,16:9,3:2,5:4,1:1,4:5,2:3,9:16,9:21}
  * negative_prompt?, seed?, output_format (png|jpeg|webp), cfg_scale?, style_preset?
- mixbread?: MixbreadOptions
  * enabled (default true), api_key override?, store_id override?, external_id?, overwrite?, metadata_overrides?, parsing_strategy?, chunking_strategy?, config?, contextualization?

Result (before SSE stringification):
{
  "context": "...",             // derived from selections/notes
  "groq_prompt": "...",         // templated prompt sent to Groq
  "composed_prompt": "...",     // Groq response text
  "groq": { ... full Groq response ... },
  "stability": {
    "images": [
      {
        "base64": "...",
        "mime_type": "image/png",
        "seed": <int>,
        "finish_reason": "SUCCESS"
      }
    ],
    "request_id": "...",
    "seed": <int>,
    "finish_reason": "SUCCESS"
  },
  "mixbread": {
    "status": "ok" | "skipped" | "error",
    "file_id": "file_abc123",   // present when status ok
    "store_file": {
      "id": "store_file_xyz",
      "store_id": "tattzy-generations",
      "metadata": {
        "selections": {...},
        "notes": [...],
        "context": "...",
        "groq_prompt": "...",
        "composed_prompt": "...",
        "stability": {
          "options": { model, mode, aspect_ratio, etc. },
          "seed": <int>,
          "finish_reason": "SUCCESS",
          "request_id": "..."
        }
      }
    }
  }
}
Frontend Behavior:
- Render only the Mixedbread image (download URL from store_file) while still persisting composed_prompt (enhanced prompt) and mixbread.file_id for follow-on tools.

4. Mixedbread Helper Module (mcp/tools/mixbread_client.py)
---------------------------------------------------------
Environment variables:
- MIXBREAD_API_KEY (required unless request override supplied)
- MIXBREAD_STORE_ID (required unless request override supplied)
- MIXBREAD_API_BASE (default https://api.mixedbread.com)
- MIXBREAD_HTTP_TIMEOUT (default 60 seconds)

Helper functions:
- get_mixbread_api_key(override?)
- get_mixbread_store_id(override?)
- upload_file(file_bytes, filename, mime_type, api_key) ⇒ POST {base}/v1/files
- add_file_to_store(api_key, store_id, file_id, metadata?, external_id?, overwrite?, config?, parsing_strategy?, chunking_strategy?, contextualization?) ⇒ POST {base}/v1/stores/<store>/files

Stored metadata baseline:
{
  "selections": {...},
  "notes": [...],
  "context": "...",
  "groq_prompt": "...",
  "composed_prompt": "...",
  "stability": {
    "options": {... minus init_image ...},
    "seed": <int>,
    "finish_reason": "...",
    "request_id": "..."
  }
}
Filename pattern: tattty-<uuid>.{png|jpg|webp}; mime_type inherits from Stability output.

5. Settings & Runtime
---------------------
Settings model (mcp/config.py):
- host, port, log_level, allow_anonymous, secret_key, rate_limit_per_ip, cors (allow_origins/methods/headers lists), admin_token, log_directory.
- Environment overrides via MCP_HOST, MCP_PORT, MCP_LOG_LEVEL, MCP_ALLOW_ANONYMOUS, MCP_SECRET_KEY, MCP_RATE_LIMIT, MCP_ADMIN_TOKEN, MCP_LOG_DIR, MCP_CONFIG.

Runtime components:
- MetricsCollector for /health/railway snapshots
- RateLimiter (default 30/min/IP)
- Logging to ./logs via logging_utils.configure_logging
- Admin router for dashboard (HTML templates in mcp/admin/templates)

6. External Dependencies
------------------------
- Groq API (chat completions for prompt enhancement)
- Stability AI SD3.5 (text/image generation)
- Mixedbread API (file upload + store ingestion)
- Supporting libraries pinned in requirements.txt: fastapi, uvicorn, httpx, pydantic v2, etc.

This file reflects the complete schema/state of the MCP transport, registered tools, and Mixedbread-backed persistence as of the current codebase.
