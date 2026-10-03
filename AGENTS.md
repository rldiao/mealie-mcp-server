# Repository Guidance

## Project Structure

- This is a Python 3.12+ MCP server backed by the Mealie HTTP API.
- [`src/mealie/`](src/mealie/) contains API mixins and the shared HTTP client.
- [`src/tools/`](src/tools/) contains FastMCP-facing tool registrations.
- [`src/models/`](src/models/) contains Pydantic request and response models.
- [`src/server.py`](src/server.py) wires configuration, the client, prompts, and
  tools together.
- Use the SDK import `from mcp.server.fastmcp import FastMCP`; there is no
  standalone `fastmcp` dependency.

## Development Workflow

- Install all development dependencies with `uv sync --extra dev`.
- Before committing, run `uv run ruff check src tests` and `uv run pytest -q`.
- Keep [`uv.lock`](uv.lock) synchronized whenever
  [`pyproject.toml`](pyproject.toml) changes.
- Make focused commits. Do not stage generated files, local logs, `.env`,
  `.DS_Store`, or debug artifacts.
- The shared working tree may contain user changes. Inspect `git status` first
  and preserve unrelated work.
- Before pushing `main`, fetch the remote and inspect divergence. Rebase without
  overwriting newer remote functionality.

## Behavioral Constraints

- Never log API keys, request bodies, response bodies, recipe content, user data,
  or shopping-list content.
- Logging for stdio transport must go to stderr. Do not add an unconditional file
  logger or write protocol-adjacent output to stdout.
- Startup must fail on unsuccessful Mealie health checks; always call
  `raise_for_status()`.
- Close the HTTP client during shutdown.
- Keep MCP tool names and prompt references synchronized.
- Preserve Mealie field casing at the API boundary, such as `recipeId`,
  `entryType`, and `perPage`.

## Adding an API Capability

1. Add or extend the appropriate mixin in [`src/mealie/`](src/mealie/).
2. Ensure the mixin is inherited by `MealieFetcher` in
   [`src/mealie/__init__.py`](src/mealie/__init__.py).
3. Add the FastMCP wrapper in [`src/tools/`](src/tools/).
4. Register and export the wrapper through
   [`src/tools/__init__.py`](src/tools/__init__.py).
5. Add tests for request method, URL, parameters or payload, validation, success,
   and failure behavior.

See [source guidance](src/AGENTS.md) and [test guidance](tests/AGENTS.md) for
layer-specific conventions.
