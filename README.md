# Mealie MCP Server

[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/rldiao-mealie-mcp-server-badge.png)](https://mseep.ai/app/rldiao-mealie-mcp-server)

A Model Context Protocol (MCP) server that connects AI assistants to your
[Mealie](https://github.com/mealie-recipes/mealie) recipe database through clients
such as Claude Desktop.

## Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Remote Access](#remote-access)
- [Authentication (OAuth resource server)](#authentication-oauth-resource-server)
- [Docker](#docker)
- [Usage Examples](#usage-examples)
- [Available Tools](#available-tools)
- [Development](#development)
- [Important Notes](#important-notes)
- [Support and Contributing](#support-and-contributing)
- [License and Credits](#license-and-credits)

## Features

- **Recipes:** Create, read, update, import, duplicate, and delete recipes.
- **Search:** Filter by text, categories, tags, and tools with AND/OR logic.
- **Images and assets:** Upload recipe images and files, or set images from URLs.
- **Nutrition and display:** Set per-serving nutrition and recipe visibility
  settings such as `showAssets` and `showNutrition`.
- **Ingredients:** Resolve free-text ingredients against Mealie's food and unit
  vocabulary.
- **Shopping lists:** Manage lists and items, perform bulk operations, and add
  recipe ingredients with quantity scaling.
- **Organization:** Manage categories, tags, foods, units, and recipe tools; find
  unused categories and tags.
- **Meal planning:** View, create, update, and delete meal plan entries, create
  multiple entries, and mark recipes as made today.

## Quick Start

### Prerequisites

- Python 3.12+
- A running Mealie instance and an API key from your account settings
- Package manager [uv](https://docs.astral.sh/uv/getting-started/installation/)

### Installation

#### Option 1: Using the MCP SDK CLI (Recommended)

Clone the repository, then install the server into Claude Desktop with the
`mcp` command supplied by the Python MCP SDK (no standalone `fastmcp` package
is needed):

```bash
git clone https://github.com/rldiao/mealie-mcp-server.git
cd mealie-mcp-server
uv sync --locked
uv run mcp install src/server.py --with-editable . \
  --env-var MEALIE_BASE_URL=https://your-mealie-instance.com \
  --env-var MEALIE_API_KEY=your-mealie-api-key
```

#### Option 2: Using uvx

Add this to your MCP client's configuration to run directly from GitHub without
cloning (in Claude Desktop, use `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "mealie-mcp-server": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/rldiao/mealie-mcp-server",
        "mealie-mcp-server"
      ],
      "env": {
        "MEALIE_BASE_URL": "https://your-mealie-instance.com",
        "MEALIE_API_KEY": "your-mealie-api-key"
      }
    }
  }
}
```

Restart Claude Desktop to load the server.

## Configuration

Set environment variables in your MCP client configuration or shell. For a local
checkout, you can also copy [`.env.template`](.env.template) to `.env` and fill in
your instance details. Never commit your API key.

| Variable | Default | Description |
| --- | --- | --- |
| `MEALIE_BASE_URL` | Required | Mealie base URL, including protocol and port if needed |
| `MEALIE_API_KEY` | Required in `api-key` mode | API key from your Mealie account settings |
| `MEALIE_ENABLE_AI_IMPORT` | `false` | Opt in to AI recipe import; accepts `true`/`false` (case-insensitive) |
| `MCP_TRANSPORT` | `stdio` | `stdio`, `streamable-http`, or legacy `sse` |
| `MCP_HOST` | `127.0.0.1` | HTTP bind address; use `0.0.0.0` in containers |
| `MCP_PORT` | `8765` | HTTP port, from 1 to 65535 |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` |

Optional OAuth settings for the HTTP endpoint are described in
[Authentication (OAuth resource server)](#authentication-oauth-resource-server);
calling Mealie as each authenticated user instead of with `MEALIE_API_KEY` is
described in
[Acting as each user](#acting-as-each-user-mealie-reverse-proxy-sign-in).

## Remote Access

The default stdio transport is for local clients. To serve HTTP clients, configure
your Mealie credentials as described above and run from the checkout:

```bash
export MCP_TRANSPORT=streamable-http
export MCP_HOST=127.0.0.1
export MCP_PORT=8765
uv run mealie-mcp-server
```

The server will expose its MCP endpoint at `http://<host>:<port>/mcp`.

**Security:** By default, HTTP transports do not authenticate clients; see
[Authentication (OAuth resource server)](#authentication-oauth-resource-server).
Without it, anyone who can reach the endpoint can use the configured Mealie
credentials through its tools. Keep it on a trusted interface; for remote access,
enable authentication and serve the endpoint over HTTPS.

With `MCP_HOST` set to a local address (`127.0.0.1`, `localhost`, `::1`), the SDK enables its DNS rebinding protection and answers `421 Invalid Host header` to any other `Host`; for a proxy on the same machine, prefer having the proxy send a loopback `Host` (for example nginx `proxy_set_header Host $proxy_host;` or equivalent). Bind `0.0.0.0` only inside a container or private network, or with authentication enabled: otherwise the unauthenticated endpoint, and the Mealie API key behind it, is reachable on every interface, bypassing the proxy.

## Authentication (OAuth resource server)

Enable authentication when the HTTP endpoint is reachable from outside a trusted
network, for example as a remote connector in claude.ai. The server then acts as an
OAuth 2.0 resource server: every request to `/mcp` must carry a bearer access token
issued by your OpenID Connect provider. The server checks the token's signature
against the provider's published keys, its `iss`, `aud`, and `exp` claims, and
optionally a group membership. It does not issue tokens; clients obtain them from
the provider.

Authentication stays disabled unless `MCP_AUTH_ISSUER` is set. It is supported only
with `MCP_TRANSPORT=streamable-http`: startup fails with `stdio` or `sse`, and also
when another variable below is set without `MCP_AUTH_ISSUER`, so a typo in the
issuer cannot leave the endpoint open.

| Variable | Default | Description |
| --- | --- | --- |
| `MCP_AUTH_ISSUER` | Unset (authentication disabled) | Issuer URL, exactly as in the tokens' `iss` claim; discovery is read from `<issuer>/.well-known/openid-configuration` |
| `MCP_AUTH_AUDIENCE` | Required with `MCP_AUTH_ISSUER` | Value expected in the `aud` claim, usually the OAuth client ID |
| `MCP_AUTH_REQUIRED_GROUP` | Unset (no group check) | Group required in the `groups` claim of the token, or of the userinfo response when the token has none |
| `MCP_AUTH_USERNAME_CLAIM` | `preferred_username` | Claim naming the user, read from the token or the userinfo response; tokens without it are rejected |
| `MCP_PUBLIC_URL` | Required with `MCP_AUTH_ISSUER` | Public base URL that clients use, such as `https://mcp.example.com`, without a path; never an internal address |

A request without a valid token receives `401 Unauthorized` with a challenge that
points to the protected resource metadata (RFC 9728):

```text
WWW-Authenticate: Bearer error="invalid_token", error_description="...", resource_metadata="https://mcp.example.com/.well-known/oauth-protected-resource/mcp"
```

That document, served by this server, names the resource
(`https://mcp.example.com/mcp`) and the issuer as its authorization server; MCP
clients follow it to start the OAuth flow. A reverse proxy in front of the server
must forward both `/mcp` and `/.well-known/oauth-protected-resource/mcp`.

The server never forwards the client's access token to Mealie. By default, tool
calls still use `MEALIE_API_KEY`, so every authenticated user acts through that
key's Mealie account; see
[Acting as each user](#acting-as-each-user-mealie-reverse-proxy-sign-in) to call
Mealie as each user instead. Rejected tokens are logged with a short reason code only, never the token.

### Example: authentik and claude.ai

1. In authentik, create an OAuth2/OpenID provider with client type
   **Confidential** and strict redirect URIs
   `https://claude.ai/api/mcp/auth_callback` and
   `https://claude.com/api/mcp/auth_callback`.
2. Select the scopes `openid`, `profile` (which carries `preferred_username` and
   `groups`), and `offline_access` (refresh tokens).
3. Keep the access token validity short, such as `minutes=10`. Group memberships
   are frozen in the access token, so removing someone from the required group
   takes effect only when their current token expires.
4. Create an application for the provider and bind it to the group you require.
5. Start the server with:

   ```bash
   export MCP_TRANSPORT=streamable-http
   export MCP_HOST=0.0.0.0
   export MCP_AUTH_ISSUER=https://auth.example.com/application/o/mealie-mcp/
   export MCP_AUTH_AUDIENCE=<client ID>
   export MCP_AUTH_REQUIRED_GROUP=mealie-mcp-users
   export MCP_PUBLIC_URL=https://mcp.example.com
   uv run mealie-mcp-server
   ```

6. In claude.ai, add a custom connector with the URL `https://mcp.example.com/mcp`
   and enter the client ID and secret in its advanced settings.

Start the server through the `mealie-mcp-server` entry point (or
`uv run src/server.py`). The instance that `mcp run` and `mcp dev` discover has no
token verifier, so it refuses to start when `MCP_AUTH_ISSUER` is set.

### Acting as each user (Mealie reverse-proxy sign-in)

By default, every authenticated user reaches Mealie through `MEALIE_API_KEY`.
With `MEALIE_AUTH_MODE=reverse-proxy`, the server instead calls Mealie as the
user behind each request, so recipes, meal plans, and shopping lists belong to
that user's own Mealie account:

1. The username is taken from the verified access token (the claim named by
   `MCP_AUTH_USERNAME_CLAIM`).
2. The server exchanges it for a Mealie token of that user through Mealie's
   trusted reverse-proxy sign-in (`GET /api/auth/reverse-proxy` with the
   username and shared-secret headers).
3. Tool calls use that Mealie token. The identity provider's access token is
   never forwarded to Mealie.

This mode requires authentication (`MCP_AUTH_ISSUER`) and ignores
`MEALIE_API_KEY`. Tool calls without an authenticated user fail; they never fall
back to another account. A user without a Mealie account gets a readable tool
error asking them to sign in to Mealie once in a browser.

| Variable | Default | Description |
| --- | --- | --- |
| `MEALIE_AUTH_MODE` | `api-key` | `api-key` calls Mealie with `MEALIE_API_KEY`; `reverse-proxy` calls Mealie as each authenticated user and requires `MCP_AUTH_ISSUER` |
| `MEALIE_REVERSE_PROXY_SECRET` | Required in `reverse-proxy` mode; refused (when non-blank) in `api-key` mode | Secret shared with Mealie's `REVERSE_PROXY_AUTH_SECRET` |
| `MEALIE_REVERSE_PROXY_USER_HEADER` | `X-Forwarded-User` | Header carrying the username; must match Mealie's `REVERSE_PROXY_AUTH_HEADER` |
| `MEALIE_REVERSE_PROXY_SECRET_HEADER` | `X-Mealie-Reverse-Proxy-Secret` | Header carrying the secret; must match Mealie's `REVERSE_PROXY_AUTH_SECRET_HEADER` |

The three `MEALIE_REVERSE_PROXY_*` variables are refused when `MEALIE_AUTH_MODE` is
`api-key` (blank counts as unset), so a typo in the mode cannot silently ignore them.

Configure Mealie with:

```bash
REVERSE_PROXY_AUTH_ENABLED=true
REVERSE_PROXY_AUTH_SIGNUP_ENABLED=false
REVERSE_PROXY_AUTH_SECRET=<the same long random value as MEALIE_REVERSE_PROXY_SECRET>
```

Before enabling it:

- The secret lets its holder act as **any** Mealie account. Generate a long random
  value, store it as a secret, and never log or share it.
- Block `/api/auth/reverse-proxy` on any public proxy in front of Mealie, so only
  this server can reach the exchange route, for example through an internal
  service address.
- The username claim (`MCP_AUTH_USERNAME_CLAIM`, default `preferred_username`) is
  trusted as the Mealie identity. It must be unique and set by an administrator,
  never editable by users, and never an unverified email. Mealie matches the header
  value against usernames and then emails, case-insensitively, so a user who can
  change this claim can act as another account, including an admin.
- With sign-up disabled, Mealie accounts are not created by this server: each
  user signs in to the Mealie website once (for example through OIDC) before
  using the tools.
- Per-user Mealie clients are cached in memory (at most 256, least recently used
  first out) and renewed before their Mealie token expires. Restarting the server
  clears the cache.

## Docker

The [Dockerfile](Dockerfile) runs the server as a persistent container.

### Build

```bash
docker build -t mealie-mcp-server .
```

### Standalone

```bash
docker run -d \
  --name mealie-mcp \
  -e MEALIE_BASE_URL=http://your-mealie-host:9000 \
  -e MEALIE_API_KEY=your-mealie-api-key \
  -e MCP_TRANSPORT=streamable-http \
  -e MCP_HOST=0.0.0.0 \
  -e MCP_PORT=8765 \
  -p 127.0.0.1:8765:8765 \
  mealie-mcp-server
```

The port is published only on the host's loopback interface. See
[Remote Access](#remote-access) before making it reachable remotely.

### Docker Compose

Add this service to the Compose file that runs Mealie. The example assumes that
the Mealie service is named `mealie` and both services use a network named
`mealie_net`, defined in that Compose file. Set `MEALIE_API_KEY` in the shell or
Compose `.env` file.

```yaml
services:
  mealie-mcp:
    build: .
    container_name: mealie-mcp
    restart: unless-stopped
    environment:
      MEALIE_BASE_URL: http://mealie:9000
      MEALIE_API_KEY: ${MEALIE_API_KEY}
      MCP_TRANSPORT: streamable-http
      MCP_HOST: "0.0.0.0"
      MCP_PORT: "8765"
    expose:
      - "8765"
    networks:
      - mealie_net
```

`expose` does not publish a host port. Connect a reverse proxy on the same network
for remote access, following the [HTTP security guidance](#remote-access).

## Usage Examples

```text
"Search for chicken recipes"
"Create a new recipe for pasta carbonara"
"Mark the meatloaf recipe as made today"
"Create a shopping list for this week"
"Add all ingredients from the lasagna recipe to my shopping list"
"Plan chicken soup for lunch on Friday"
```

See [Usage Examples](USAGE_EXAMPLES.md) for detailed workflows and troubleshooting.

## Available Tools

### Recipe Tools (12 operations)

- `get_recipes` - List/search recipes with advanced filtering
- `get_recipe` - Get complete recipe details, or a summary with `concise=true`
- `create_recipe` - Create a recipe; only the name is required, with optional
  ingredients, instructions, metadata, nutrition, and display settings
- `import_recipe_from_url` - Import a recipe from a web page
- `update_recipe` - Update content or metadata, including nutrition and display
  settings; omitted fields are preserved, and empty lists clear content
- `duplicate_recipe` - Clone a recipe
- `mark_recipe_last_made` - Update last made timestamp
- `set_recipe_image_from_url` - Set image from URL
- `upload_recipe_image_file` - Upload image file
- `upload_recipe_asset_file` - Upload document/asset
- `update_recipe_categories_and_tags` - Replace or clear categories, tags, or both using IDs
- `delete_recipe` - Delete recipe

### Shopping List Tools (15 operations)

- `get_shopping_lists` - List all shopping lists
- `create_shopping_list` - Create new list
- `get_shopping_list` - Get list by ID
- `update_shopping_list` - Rename a list while preserving other fields
- `delete_shopping_list` - Delete list
- `add_recipe_to_shopping_list` - Add recipe ingredients
- `remove_recipe_from_shopping_list` - Remove recipe ingredients
- `get_shopping_list_items` - List all items
- `get_shopping_list_item` - Get item by ID
- `create_shopping_list_item` - Create single item
- `create_shopping_list_items_bulk` - Create multiple items
- `update_shopping_list_item` - Update item (preserves fields)
- `update_shopping_list_items_bulk` - Update multiple items
- `delete_shopping_list_item` - Delete single item
- `delete_shopping_list_items_bulk` - Delete multiple items

### Category Tools (6 operations)

- `get_categories` - List/search categories
- `get_empty_categories` - Find unused categories
- `create_category` - Create new category
- `get_category` - Get by exactly one of `category_id` or `category_slug`
- `update_category` - Update category
- `delete_category` - Delete category

### Tag Tools (6 operations)

- `get_tags` - List/search tags
- `get_empty_tags` - Find unused tags
- `create_tag` - Create new tag
- `get_tag` - Get by exactly one of `tag_id` or `tag_slug`
- `update_tag` - Update tag
- `delete_tag` - Delete tag

### Food Tools (5 operations)

- `get_foods` - List/search foods (resolve IDs for structured ingredients)
- `create_food` - Create a new food
- `get_food` - Get by ID
- `update_food` - Update food
- `delete_food` - Delete food

### Unit Tools (5 operations)

- `get_units` - List/search units
- `create_unit` - Create a new unit
- `get_unit` - Get by ID
- `update_unit` - Update unit
- `delete_unit` - Delete unit

### Kitchen Tools (5 operations)

- `get_tools` - List/search recipe tools (includes `householdsWithTool`)
- `create_tool` - Create a new tool
- `get_tool` - Get by exactly one of `tool_id` or `tool_slug`
- `update_tool` - Update tool
- `delete_tool` - Delete tool

### Parser Tools (1 operation)

- `parse_ingredients` - Resolve one or more ingredient lines in one request; always returns a list

### Meal Plan Tools (6 operations)

- `get_all_mealplans` - List meal plans
- `create_mealplan` - Create meal plan entry
- `create_mealplan_bulk` - Create multiple entries
- `update_mealplan` - Update an entry while preserving omitted fields
- `delete_mealplan` - Delete an entry
- `get_todays_mealplan` - Get today's meals

**Total: 61 tools**

With `MEALIE_ENABLE_AI_IMPORT=true`, `import_recipe_with_ai` adds one optional
recipe operation: **62 total tools, including 13 recipe tools**. It is absent
from discovery and cannot be called when disabled.

### Migrating consolidated tools (breaking change)

Redundant MCP names have been removed, not retained as aliases. Refresh your
client's tool list and update saved calls:

| Removed tool | Replacement |
| --- | --- |
| `create_recipe_full` | `create_recipe` with the same arguments |
| `get_recipe_detailed` | `get_recipe` (full details by default) |
| `get_recipe_concise` | `get_recipe` with `concise=true` |
| `patch_recipe` | `update_recipe` with the same arguments |
| `set_recipe_categories` | `update_recipe_categories_and_tags` with `category_ids` |
| `set_recipe_tags` | `update_recipe_categories_and_tags` with `tag_ids` |
| `get_category_by_slug` | `get_category` with `category_slug` |
| `get_tag_by_slug` | `get_tag` with `tag_slug` |
| `get_tool_by_slug` | `get_tool` with `tool_slug` |
| `parse_ingredient` | `parse_ingredients(ingredients=[...])`; read the first result |

Existing `create_recipe` and `update_recipe` calls remain supported. Recipe
updates can now combine content and metadata, with omitted or null fields left
unchanged. Ingredient and instruction lists replace only the provided fields.
Nutrition remains a whole-object replacement, while settings are merged.

Distinct operations remain separate: single and bulk writes have different
response/failure contracts; paginated lists differ from individual lookups,
unused-organizer queries, and today's meal plans. Recipe URL import, image URL
scraping, and file uploads also perform different operations.

### Optional AI recipe import

Set `MEALIE_ENABLE_AI_IMPORT=true` in your MCP client's environment, shell, or
local `.env`. Restart the server and refresh the client's tool list. This applies
to stdio, SSE, and Streamable HTTP. Offline SDK discovery remains configuration-
and network-free, listing only default tools; optional registration occurs at
runtime startup (or when passing an explicit enabled `ServerConfig`).

`import_recipe_with_ai` requires **Mealie 3.23.0+** and a default AI provider
configured for the API user's group. It accepts any combination of:

- `content`: plain text, raw HTML, or JSON; also used for corrections or notes.
- `url`: an HTTP(S) recipe or video URL, fetched by Mealie and saved as the source.
- `image_paths`: ordered image paths accessible to the **MCP server's filesystem**,
  not a remote caller's computer. Multiple photos become one recipe; the first
  becomes its cover image.

At least one nonblank source is required. Sources are combined, with pasted
content taking precedence when they disagree. Optional `translate_language`
requests translation. `create_new_organizers` defaults to `false`: matching
existing tags, categories, and kitchen tools may be assigned, but new ones are
created only when explicitly requested.

Before each import the server reads `/api/groups/self` to check `aiEnabled` and,
for photos, `imageProviderEnabled`. Missing/malformed capabilities or a failed
lookup produce an explicit error, not a silent disabled result. Video detection
and the audio-provider requirement are handled by Mealie. These checks establish
configuration, not provider connectivity, credentials, or available quota.

**This tool immediately creates and saves a recipe.** Source material is processed
by Mealie's configured AI providers and may incur charges. Review the returned
recipe for accuracy. The import has a 300-second read timeout; other API calls
retain their existing timeouts. No imports are automatically retried. After a
timeout or connection failure, check Mealie before retrying or switching tools:
creation may already have succeeded. If the follow-up fetch fails, the error
includes `created_slug` and `stage`; retrieve that recipe rather than importing again.

Choose the tool according to the task:

| Task | Tool |
| --- | --- |
| Ordinary recipe webpage | `import_recipe_from_url` |
| Unstructured text, photos, video, combined sources, translation, or explicit AI import | `import_recipe_with_ai` (opt-in) |
| Save already-composed ingredients and instructions | `create_recipe` |
| Attach a photo to an existing recipe without extracting content | `upload_recipe_image_file` |

The opt-in controls only this new tool. It does not disable Mealie's own AI
fallback for URL scraping or other existing AI features. See
[Mealie's AI import documentation](https://mealie.io/documentation/getting-started/installation/ai-providers/#import-with-ai)
and [usage examples](USAGE_EXAMPLES.md#optional-ai-import).

## Development

### Setup

After [cloning the repository](#installation), install development dependencies:

```bash
uv sync --locked --extra dev
```

For manual testing, configure your Mealie instance:

```bash
cp .env.template .env
# Edit .env with your Mealie instance details
```

Launch the MCP Inspector:

```bash
uv run mcp dev src/server.py
```

Run the offline checks; these do not require a Mealie instance or credentials:

```bash
uv run ruff check src tests
uv run pytest -q
```

### Project Structure

| Path | Purpose |
| --- | --- |
| [`src/mealie/`](src/mealie/) | HTTP client and API mixins |
| [`src/tools/`](src/tools/) | FastMCP tool definitions and registration |
| [`src/models/`](src/models/) | Pydantic request and response models |
| [`src/server.py`](src/server.py) | Configuration, lifecycle, and entry point |
| [`src/prompts.py`](src/prompts.py) | MCP prompts |
| [`tests/`](tests/) | Offline tests and fixtures |

Repository conventions are in [AGENTS.md](AGENTS.md), with focused guidance for
[source code](src/AGENTS.md) and [tests](tests/AGENTS.md).

The automated suite uses fake HTTP responses and includes local HTTP-transport
checks. It does not replace compatibility testing against your deployed Mealie
version.

## Important Notes

The calls below use Python-style notation to illustrate MCP tool arguments; they
are not standalone Python scripts.

### Filtering by Tags and Categories

When filtering recipes, you **must use slugs or UUIDs**, not display names:

Use `get_tags()` or `get_categories()` first to find the correct slugs:

```python
get_recipes(tags=["quick-meals", "healthy"])
```

For example, pass `quick-meals`, not the display name `Quick Meals`.

### Nutrition Is Replaced, Not Merged

Mealie replaces the whole `nutrition` object on write. `update_recipe` follows
suit, so pass every value you want to keep:

```python
# Clears every nutrition value except fat.
update_recipe(slug="...", nutrition={"fatContent": "12"})
```

### Parsing Ingredients in Bulk

Resolving ingredients by hand costs one to two `get_foods` / `get_units` calls
each. `parse_ingredients` does a whole recipe in one request and returns results
that can be handed straight to `create_recipe`:

```python
parse_ingredients(ingredients=["1/4 cup chopped onion", "2 large eggs"])
# -> [{"input": "1/4 cup chopped onion", "confidence": 0.99, "quantity": 0.25,
#      "unit": {"id": "...", "name": "cup"},
#      "food": {"id": "...", "name": "onion"}, "note": "chopped"}, ...]
```

A `null` unit or food means your instance has no matching entry; create one
with `create_food` / `create_unit`, or leave the text in the note. Pass
`verbose=True` for Mealie's full response including per-field confidences.

### Uploaded Assets and Nutrition Can Be Stored but Hidden

A recipe's `settings` object controls what the UI renders. `showAssets` and
`showNutrition` gate the assets and nutrition cards, so an asset uploaded with
`upload_recipe_asset_file` can be present in the API response and still be
invisible in the web UI. Flip the toggle with:

```python
update_recipe(slug="...", settings={"showAssets": True})
```

Mealie seeds a new recipe's settings from the household preferences
(`recipeShowAssets`, `recipeShowNutrition`, ...), so the defaults differ per
instance. Check rather than assume.

Only the toggles you pass are changed. The tool reads the recipe's current
settings and sends the merged object, because Mealie does not reliably preserve
toggles omitted from a settings PATCH.

### Field Preservation

When updating shopping list items, both single and bulk updates fetch the current
records and preserve omitted fields. You only need to specify the fields you
want to change:

```python
# Only updates 'checked' field, preserves note, quantity, etc.
update_shopping_list_item(item_id="...", checked=True)
```

Bulk shopping inputs accept snake_case names such as `shopping_list_id` and
Mealie's camelCase names such as `shoppingListId`. Conflicting aliases and
duplicate IDs in a bulk update are rejected before writing.

### Meal Plan Validation and Clearing

Meal dates must use `YYYY-MM-DD`, and entry types must be `breakfast`, `lunch`,
`dinner`, or `side`. Creation requires a recipe or a nonblank title. Bulk meal
plans are validated in full before any entries are created.

Omitted update fields remain unchanged. To remove an existing recipe link,
use `update_mealplan(entry_id="...", clear_recipe=True, title="Leftovers")`.
Do not combine `clear_recipe` with a replacement `recipe_id`.

### Recovering from Partially Completed Writes

Recipe creation/population and bulk meal-plan creation require multiple API
requests and are not atomic. If a later request fails, the tool error includes
recovery information identifying completed work. Inspect that information and
the current Mealie state rather than blindly retrying the entire operation.
A failed or timed-out request may have completed remotely.

## Support and Contributing

- Check the [changelog](CHANGELOG.md) for changes and migration notes.
- Review the [usage guide](USAGE_EXAMPLES.md) and
  [Mealie documentation](https://docs.mealie.io).
- Report problems through [GitHub issues](https://github.com/rldiao/mealie-mcp-server/issues).
- For pull requests, follow the [development workflow](#development) and include
  tests for behavior changes.

## License and Credits

Licensed under the [MIT License](LICENSE).

- [Mealie](https://github.com/mealie-recipes/mealie) - The recipe management system
- [Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk) - SDK and
  bundled FastMCP server
- [Model Context Protocol](https://modelcontextprotocol.io) - Protocol documentation
- [Claude Desktop](https://claude.ai/download)
