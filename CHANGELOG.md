# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Unreleased

### Changed

- **Breaking:** Consolidated `create_recipe_full` into `create_recipe` and removed
  the old tool name. Switch callers of `create_recipe_full` to `create_recipe`
  without changing their arguments. Only `name` is required; ingredients,
  instructions, metadata, nutrition, and display settings are optional. Existing
  `create_recipe` calls remain supported.
- **Breaking:** Consolidated detailed/concise recipe reads into `get_recipe`
  (`concise=True` for a summary), and `patch_recipe` into `update_recipe`.
  Recipe updates accept optional ingredients, instructions, and metadata in one
  call while preserving omitted fields.
- **Breaking:** Removed `set_recipe_categories` and `set_recipe_tags`; use
  `update_recipe_categories_and_tags` with either or both ID lists.
- **Breaking:** Removed `get_category_by_slug`, `get_tag_by_slug`, and
  `get_tool_by_slug`. Their corresponding `get_*` tools accept exactly one ID
  or slug argument.
- **Breaking:** Removed `parse_ingredient`; use `parse_ingredients` with a
  one-element list and read its first result. All lines are validated before
  sending the request. The MCP inventory is reduced from 70 to 61 tools.
- Require `mcp` 1.30 or later. With `MCP_HOST` set to a local address (`127.0.0.1`, `localhost`, `::1`), the SDK enables its DNS rebinding protection and answers `421 Invalid Host header` to any other `Host`; behind a proxy on the same machine, have it send a loopback `Host`; bind `0.0.0.0` only in a container or private network, or with authentication enabled.

### Added

- Optional OAuth resource-server authentication for the `streamable-http`
  transport, disabled unless `MCP_AUTH_ISSUER` is set. Requests to `/mcp` need a
  bearer access token from your OpenID Connect provider, verified against its
  published keys (`iss`, `aud`, `exp`, and optionally a group from
  `MCP_AUTH_REQUIRED_GROUP`). Unauthenticated requests receive `401` with a
  challenge pointing to RFC 9728 protected resource metadata at
  `<MCP_PUBLIC_URL>/.well-known/oauth-protected-resource/mcp`. Configure it with
  `MCP_AUTH_ISSUER`, `MCP_AUTH_AUDIENCE`, `MCP_AUTH_REQUIRED_GROUP`,
  `MCP_AUTH_USERNAME_CLAIM`, and `MCP_PUBLIC_URL`; startup fails if these are
  incomplete, set without the issuer, or combined with `stdio` or `sse`. Mealie
  is still called with `MEALIE_API_KEY`; the client's token is never forwarded.
- `MEALIE_AUTH_MODE=reverse-proxy` calls Mealie as each authenticated user
  instead of with `MEALIE_API_KEY`. The username from the verified access token
  is exchanged for that user's Mealie token through Mealie's trusted
  reverse-proxy sign-in (`GET /api/auth/reverse-proxy`, Mealie's
  `REVERSE_PROXY_AUTH_*` settings); the identity provider's token is never
  forwarded. Configure it with `MEALIE_REVERSE_PROXY_SECRET`,
  `MEALIE_REVERSE_PROXY_USER_HEADER`, and `MEALIE_REVERSE_PROXY_SECRET_HEADER`;
  startup fails without `MCP_AUTH_ISSUER` or the secret. Per-user clients are
  cached in memory (at most 256) and renewed before their token expires; tool
  calls without an authenticated user fail instead of falling back to another
  account, and users without a Mealie account get a readable tool error.
- `create_recipe` and `update_recipe` accept a `nutrition` argument covering
  Mealie's full key set (calories, macros, cholesterol, sodium, sugars, and the
  fat breakdown). Numbers are converted to the strings Mealie stores. Mealie
  replaces the whole nutrition object on write, so when `nutrition` is supplied,
  `update_recipe` clears nutrition keys not included in that object.
- `parse_ingredients` wraps Mealie's server-side ingredient parser, resolving
  free text such as `"1/4 cup chopped onion"`
  against the instance's food and unit vocabulary in one request instead of
  searching `get_foods` and `get_units` per ingredient. Results are flattened to
  `{input, confidence, quantity, unit, food, note}` and can be passed straight
  to `create_recipe`; `verbose=True` returns Mealie's untouched response.
  It accepts Mealie's `nlp`, `brute`, and `openai` parser backends.
- `create_recipe` and `update_recipe` accept a `settings` argument for
  Mealie's per-recipe display toggles (`public`, `showNutrition`, `showAssets`,
  `landscapeView`, `disableComments`, `disableAmount`, `locked`). Any subset may
  be passed; the tools read the recipe's current settings and send the merged
  object, so toggles left out keep their value.

### Fixed

- With `LOG_LEVEL=DEBUG`, SSE response chunks (tool results, including recipe
  content) are no longer logged by `sse_starlette`.
- Recipes now expose `showAssets` and `showNutrition` through their settings.
  Previously, uploaded assets and nutrition could be stored but hidden in the
  Mealie UI when household defaults disabled those cards.
