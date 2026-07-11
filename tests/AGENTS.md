# Test guidance

## Test strategy

- Tests must not call a real Mealie instance or require credentials.
- Prefer the shared `FakeFetcher` fixture in `tests/conftest.py`. It runs real mixin request construction while recording method, URL, JSON, and query parameters.
- Use the `invoke` fixture to exercise registered MCP tools through FastMCP rather than calling nested wrapper functions directly.
- Extend `FakeFetcher` with the smallest endpoint behavior needed for a new test; keep canned responses schema-valid.

## Required coverage for changes

- API mixin changes: assert HTTP method, endpoint, field casing, omitted `None` values, and list serialization.
- Tool changes: test registration, successful invocation, validation failure, and client failure behavior.
- Model changes: test both valid parsing and rejected invalid input.
- Update flows: verify fetch-and-merge behavior does not erase fields omitted by the caller.
- Delete flows: verify empty response normalization remains structured and successful.
- Prompts: assert referenced tool names exist and preferences are included only when provided.

## Commands

- Run all tests: `uv run pytest -q`
- Run a focused file: `uv run pytest -q tests/test_recipe_tools.py`
- Lint tests and source: `uv run ruff check src tests`
- Keep tests deterministic and independent of execution order.

