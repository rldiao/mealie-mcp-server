# Test Guidance

These conventions supplement the [repository guidance](../AGENTS.md).

## Test Strategy

- Tests must not call a real Mealie instance or require credentials, except
  the opt-in live tests in [`integration/`](integration/), which run only when
  `MEALIE_INTEGRATION=1` and start a disposable Mealie in Docker.
- Live tests create uniquely named data through `unique` and register its
  deletion with `cleanup`, so they can also run against a shared instance.
- Prefer the shared `FakeFetcher` fixture in
  [`tests/conftest.py`](conftest.py). It runs real mixin request construction while
  recording method, URL, JSON, and query parameters.
- Use the `invoke` fixture to exercise registered MCP tools through FastMCP
  rather than calling nested wrapper functions directly.
- Extend `FakeFetcher` with the smallest endpoint behavior needed for a new test;
  keep canned responses schema-valid.
- Unknown fake routes must fail. Use `fetcher.responses[method, path]` for
  isolated response overrides, including malformed-response tests; never restore
  a catch-all success response.

## Required Coverage for Changes

- API mixin changes: assert HTTP method, endpoint, field casing, omitted `None`
  values, and list serialization.
- Tool changes: test registration, successful invocation, validation failure,
  and client failure behavior.
- Model changes: test both valid parsing and rejected invalid input.
- Update flows: verify fetch-and-merge behavior does not erase fields omitted
  by the caller.
- Delete flows: verify empty response normalization remains structured and
  successful.
- Prompts: assert referenced tool names exist and preferences are included only
  when provided.

## Commands

- Run all tests: `uv run pytest -q`
- Run a focused file: `uv run pytest -q tests/test_recipe_tools.py`
- Run the live Mealie tests: `MEALIE_INTEGRATION=1 uv run pytest -q tests/integration`
- Lint tests and source: `uv run ruff check src tests`
- Keep tests deterministic and independent of execution order.
