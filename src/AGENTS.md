# Source guidance

## Layers

- Keep HTTP transport and error normalization in `mealie/client.py`.
- Keep endpoint-specific request construction in `mealie/*` mixins.
- Keep MCP descriptions, argument schemas, and user-facing error behavior in `tools/*_tools.py`.
- Keep tool registration centralized in `tools/__init__.py` and aggregate API behavior in `mealie/__init__.py`.
- Avoid putting network calls or business logic directly in `server.py`.

## HTTP client rules

- Route normal API operations through `_handle_request`.
- Use explicit timeouts and translate HTTP, timeout, and connection failures consistently.
- Successful empty or JSON-null DELETE responses should remain normalized to a structured success response.
- Do not debug-log request parameters, payloads, raw response data, or failed request bodies.
- Multipart requests must let `httpx` generate the content boundary; set JSON content type only for JSON requests.

## MCP tool rules

- Tool annotations and docstrings must match actual accepted arguments and returned values.
- Use Pydantic models for non-trivial structured input.
- Validate identifiers and required update fields before issuing an API request.
- Preserve partial-update semantics: when Mealie requires full replacement, fetch the current record and merge intentionally.
- Catch expected client failures at the tool boundary and return the project’s established structured error form.
- Treat tool renames as compatibility changes; update prompts and tests in the same commit.

## Imports and startup

- Source is packaged from `src/` using Hatchling; keep imports compatible with both `uv run src/server.py` and the `mealie-mcp-server` entry point.
- Importing `server.py` reads environment variables and establishes the Mealie client. Unit tests should normally test mixins and registration without importing the server module.

