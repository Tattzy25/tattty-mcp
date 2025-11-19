-- MCP + Mixedbread relational schema snapshot (documentation only)
-- This DDL captures the transport, tooling, and storage metadata currently implemented.

PRAGMA foreign_keys = ON;

CREATE TABLE transport_endpoints (
    path TEXT NOT NULL,
    method TEXT NOT NULL,
    description TEXT NOT NULL,
    requires_session BOOLEAN NOT NULL DEFAULT FALSE,
    supports_stream BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (path, method)
);

CREATE TABLE session_policies (
    policy_name TEXT PRIMARY KEY,
    ttl_seconds INTEGER NOT NULL,
    heartbeat_seconds INTEGER NOT NULL,
    queue_type TEXT NOT NULL,
    enforcement_notes TEXT
);

CREATE TABLE event_types (
    event_name TEXT PRIMARY KEY,
    dispatch_phase TEXT NOT NULL,
    payload_example TEXT NOT NULL,
    notes TEXT
);

CREATE TABLE tools (
    tool_name TEXT PRIMARY KEY,
    request_model TEXT NOT NULL,
    description TEXT NOT NULL,
    supports_progress BOOLEAN NOT NULL DEFAULT FALSE,
    supports_stream BOOLEAN NOT NULL DEFAULT FALSE,
    diagnostic_hook TEXT,
    transport_namespace TEXT NOT NULL DEFAULT 'tools'
);

CREATE TABLE groq_to_stability_request_fields (
    field_name TEXT PRIMARY KEY,
    data_type TEXT NOT NULL,
    required BOOLEAN NOT NULL,
    description TEXT NOT NULL
);

CREATE TABLE groq_to_stability_result_fields (
    field_name TEXT PRIMARY KEY,
    data_type TEXT NOT NULL,
    description TEXT NOT NULL,
    parent_field TEXT
);

CREATE TABLE mixbread_metadata_fields (
    field_name TEXT PRIMARY KEY,
    data_type TEXT NOT NULL,
    description TEXT NOT NULL
);

CREATE TABLE environment_variables (
    name TEXT PRIMARY KEY,
    required BOOLEAN NOT NULL,
    default_value TEXT,
    description TEXT NOT NULL
);

CREATE TABLE external_dependencies (
    name TEXT PRIMARY KEY,
    purpose TEXT NOT NULL,
    auth_mode TEXT NOT NULL,
    notes TEXT
);

CREATE TABLE settings_fields (
    field_name TEXT PRIMARY KEY,
    data_type TEXT NOT NULL,
    default_value TEXT,
    description TEXT NOT NULL
);

-- Pre-populate metadata ----------------------------------------------------

INSERT INTO transport_endpoints (path, method, description, requires_session, supports_stream) VALUES
('/mcp', 'POST', 'JSON-RPC entry point handling initialize, tools/list, tools/call.', FALSE, FALSE),
('/mcp', 'GET', 'Server-sent events stream for progress + final results.', TRUE, TRUE),
('/', 'GET', 'Root summary describing service + protocol version.', FALSE, FALSE),
('/health', 'GET', 'Lightweight readiness probe.', FALSE, FALSE),
('/health/deep', 'GET', 'Performs Groq/Stability/Mixedbread diagnostics.', FALSE, FALSE),
('/health/railway', 'GET', 'Returns metrics snapshot formatted for Railway health checks.', FALSE, FALSE),
('/admin/*', 'GET', 'Admin dashboard (requires MCP_ADMIN_TOKEN when configured).', FALSE, FALSE);

INSERT INTO session_policies VALUES
('default', 3600, 15, 'asyncio.Queue[str]', 'Heartbeats emitted when idle; tasks canceled + session_closed notification when TTL expires.');

INSERT INTO event_types VALUES
('notifications/progress', 'tool execution', '{"jsonrpc":"2.0","method":"notifications/progress","params":{"requestId":"<id>","tool":"<name>","progress":66,"total":100,"message":"Generating image..."}}', 'Sent whenever a tool reports progress via callback.'),
('notifications/heartbeat', 'idle keepalive', '{"jsonrpc":"2.0","method":"notifications/heartbeat","params":{"sessionId":"sess_1234","timestamp":1732046400}}', 'Maintains SSE connection health while queue is empty.'),
('notifications/session_closed', 'cleanup', '{"jsonrpc":"2.0","method":"notifications/session_closed","params":{"sessionId":"sess_1234"}}', 'Delivered when TTL expires or server shuts down session.'),
('result', 'completion', '{"jsonrpc":"2.0","id":1,"result":{"content":[{"type":"text","text":"{...tool payload...}"}]}}', 'Final tool output mirrored through SSE + HTTP response.');

INSERT INTO tools VALUES
('echo', 'EchoRequest', 'Returns supplied text with metadata echo.', FALSE, FALSE, 'echo_diag', 'tools'),
('ask_tattty_enhance', 'AskTatttyEnhanceRequest', 'Groq-powered story enhancer with optional streaming.', FALSE, TRUE, 'ask_tattty_diag', 'tools'),
('resize_image', 'ResizeImageRequest', 'Downloads image, resizes, responds with base64 PNG.', FALSE, FALSE, 'resize_image_diag', 'tools'),
('text_stats', 'TextStatsRequest', 'Counts characters, words, sentences.', FALSE, FALSE, 'text_stats_diag', 'tools'),
('groq_chat', 'GroqChatRequest', 'Direct Groq chat completion bridge.', FALSE, FALSE, 'groq_diag', 'tools'),
('groq_to_stability', 'GroqToStabilityRequest', 'Chain: Groq prompt -> Stability SD3.5 render -> Mixedbread upload.', TRUE, FALSE, 'groq_to_stability_diag', 'tools'),
('stability_sd35_generate', 'Sd35GenerateRequest', 'Raw SD3.5 generation.', FALSE, FALSE, 'sd35_diag', 'tools'),
('stability_remove_background', 'RemoveBackgroundRequest', 'Stability remove-background edit.', FALSE, FALSE, 'remove_background_diag', 'tools'),
('stability_replace_background', 'ReplaceBackgroundRequest', 'Stability replace-background edit.', FALSE, FALSE, 'replace_background_diag', 'tools'),
('stability_upscale_conservative', 'ConservativeUpscaleRequest', 'Conservative 4x upscaling.', FALSE, FALSE, 'upscale_conservative_diag', 'tools'),
('stability_control_sketch', 'ControlSketchRequest', 'Sketch guidance for SD3.5.', FALSE, FALSE, 'control_sketch_diag', 'tools'),
('stability_control_structure', 'ControlStructureRequest', 'Structure guidance control.', FALSE, FALSE, 'control_structure_diag', 'tools'),
('stability_control_style', 'ControlStyleRequest', 'Style guide control.', FALSE, FALSE, 'control_style_diag', 'tools'),
('stability_control_style_transfer', 'ControlStyleTransferRequest', 'Style transfer combining init + style image.', FALSE, FALSE, 'control_style_transfer_diag', 'tools');

INSERT INTO groq_to_stability_request_fields VALUES
('selections', 'json object', TRUE, 'Key/value selections describing style, color, mood, placement, size, model, aspect_ratio, etc.'),
('additional_notes', 'array<string>', FALSE, 'Free-form bullet points appended to Groq context.'),
('context_override', 'string', FALSE, 'Full context string that bypasses selections when provided.'),
('groq_prompt_template', 'string', TRUE, 'Template with {context} placeholder passed to Groq.'),
('system_prompt', 'string', FALSE, 'Optional Groq system instructions (defaults to rewrite directive).'),
('groq_model', 'string', TRUE, 'Groq completion model (default mixtral-8x7b-32768).'),
('max_tokens', 'integer', TRUE, 'Groq max output tokens (1-2048, default 512).'),
('temperature', 'float', TRUE, 'Groq sampling temperature (0-2, default 0.2).'),
('top_p', 'float', FALSE, 'Groq nucleus sampling parameter (0-1).'),
('stability', 'json object', TRUE, 'Nested StabilityGenerationOptions payload for SD3.5.'),
('mixbread', 'json object', FALSE, 'Optional MixedbreadOptions overrides (API key, store, metadata customizations).');

INSERT INTO groq_to_stability_result_fields VALUES
('context', 'string', 'Normalized context string derived from selections/notes.', NULL),
('groq_prompt', 'string', 'Final prompt sent to Groq after template substitution.', NULL),
('composed_prompt', 'string', 'Groq response text forwarded to Stability.', NULL),
('groq', 'json object', 'Full Groq API response body.', NULL),
('stability', 'json object', 'Stability SD3.5 response including image array + IDs.', NULL),
('mixbread', 'json object', 'Upload status + resulting store metadata.', NULL),
('mixbread.status', 'string', 'ok | skipped | error result of upload.', 'mixbread'),
('mixbread.file_id', 'string', 'Mixedbread file identifier used for downstream tooling.', 'mixbread'),
('mixbread.store_file', 'json object', 'Store association payload including metadata.', 'mixbread');

INSERT INTO mixbread_metadata_fields VALUES
('selections', 'json object', 'Original UI selection map kept for search filters.'),
('notes', 'array<string>', 'Additional notes included in Groq context.'),
('context', 'string', 'Human-readable context string used for Groq.'),
('groq_prompt', 'string', 'Exact prompt sent to Groq.'),
('composed_prompt', 'string', 'Enhanced prompt saved for future reuse even if not rendered.'),
('stability.options', 'json object', 'Options forwarded to SD3.5 (model, aspect_ratio, etc.).'),
('stability.seed', 'integer', 'Seed returned by Stability.'),
('stability.finish_reason', 'string', 'Finish reason from Stability result.'),
('stability.request_id', 'string', 'Stability request identifier.');

INSERT INTO environment_variables VALUES
('GROQ_API_KEY', TRUE, NULL, 'Bearer token for Groq chat completions.'),
('STABILITY_API_KEY', TRUE, NULL, 'Bearer token for Stability AI SD3.5 endpoints.'),
('MIXBREAD_API_KEY', TRUE, NULL, 'Bearer token for Mixedbread uploads (overridable per request).'),
('MIXBREAD_STORE_ID', TRUE, NULL, 'Store identifier (e.g., tattzy-generations).'),
('MIXBREAD_API_BASE', FALSE, 'https://api.mixedbread.com', 'Override Mixedbread API host if needed.'),
('MIXBREAD_HTTP_TIMEOUT', FALSE, '60', 'HTTP timeout in seconds for Mixedbread requests.'),
('MCP_HOST', FALSE, '0.0.0.0', 'FastAPI bind host.'),
('MCP_PORT', FALSE, '8000', 'FastAPI bind port.'),
('MCP_LOG_LEVEL', FALSE, 'info', 'Server log level.'),
('MCP_ALLOW_ANONYMOUS', FALSE, 'true', 'Whether auth headers are optional.'),
('MCP_SECRET_KEY', FALSE, NULL, 'Shared secret required when anonymous access disabled.'),
('MCP_RATE_LIMIT', FALSE, '30', 'Per-IP requests per minute.'),
('MCP_ADMIN_TOKEN', FALSE, NULL, 'Token required for /admin dashboard.'),
('MCP_LOG_DIR', FALSE, 'logs', 'Directory for structured logs.'),
('MCP_CONFIG', FALSE, NULL, 'Path to custom config.yaml.');

INSERT INTO external_dependencies VALUES
('Groq API', 'Prompt enhancement via chat completions.', 'Bearer', 'Uses mixtral-8x7b-32768 by default but accepts overrides.'),
('Stability SD3.5', 'Image generation, control modes, edits.', 'Bearer', 'Supports sd3.5-large + sd3.5-large-turbo, text/image workflows.',
 'Progress emitted at 33/66/100 for groq_to_stability.'),
('Mixedbread API', 'Permanent storage + semantic search.', 'Bearer', 'Uploads file then associates to store with metadata for future gallery/search.');

INSERT INTO settings_fields VALUES
('host', 'string', '0.0.0.0', 'Bind interface for FastAPI.'),
('port', 'integer', '8000', 'Port FastAPI listens on.'),
('log_level', 'string', 'info', 'Python logging level.'),
('allow_anonymous', 'boolean', 'true', 'When false, Authorization header is mandatory.'),
('secret_key', 'string', NULL, 'Shared secret used for Bearer auth.'),
('rate_limit_per_ip', 'integer', '30', 'Max requests per minute per IP.'),
('cors.allow_origins', 'array<string>', '["*"]', 'Allowed origins for browser clients.'),
('cors.allow_methods', 'array<string>', '["*"]', 'Allowed HTTP methods for CORS.'),
('cors.allow_headers', 'array<string>', '["*"]', 'Allowed HTTP headers for CORS.'),
('admin_token', 'string', NULL, 'Token gating the admin dashboard.'),
('log_directory', 'string', 'logs', 'Directory for log files.');
