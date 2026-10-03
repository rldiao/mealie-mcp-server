[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/rldiao-mealie-mcp-server-badge.png)](https://mseep.ai/app/rldiao-mealie-mcp-server)

# Mealie MCP Server

A comprehensive Model Context Protocol (MCP) server that enables AI assistants to interact with your [Mealie](https://github.com/mealie-recipes/mealie) recipe database through clients like Claude Desktop.

## ✨ Features

### 🍽️ Recipe Management

- **CRUD Operations**: Create, read, update, patch, duplicate, and delete recipes
- **Advanced Search**: Filter by text, categories, tags, and tools with AND/OR logic
- **Image Management**: Upload images or scrape from URLs
- **Asset Uploads**: Attach documents and files to recipes
- **Metadata Tracking**: Mark recipes as made, track last made dates
- **Nutrition**: Set per-serving nutrition when creating or patching a recipe
- **Ingredient Parsing**: Resolve free-text ingredients against your food and unit vocabulary
- **Display Settings**: Control per-recipe visibility toggles such as showAssets and showNutrition

### 🛒 Shopping Lists

- **List Management**: Create, update, and delete shopping lists
- **Item Operations**: Add, update, check off, and remove items
- **Bulk Operations**: Create, update, or delete multiple items at once
- **Recipe Integration**: Automatically add recipe ingredients to shopping lists

### 🏷️ Organization

- **Categories**: Organize recipes with categories (Breakfast, Dinner, etc.)
- **Tags**: Tag recipes for easy filtering (Quick, Healthy, Family Favorite)
- **Advanced Filtering**: Search and filter with full pagination support
- **Empty Detection**: Find unused categories and tags

### 📅 Meal Planning

- **Meal Plans**: View and manage meal plans
- **Bulk Creation**: Add multiple meals at once
- **Today's Menu**: Quick access to today's planned meals

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- Running Mealie instance with API key
- Package manager [uv](https://docs.astral.sh/uv/getting-started/installation/)

### Installation

#### Option 1: Using fastmcp (Recommended)

Install the server directly with the `fastmcp` command:

```bash
fastmcp install src/server.py \
  --env-var MEALIE_BASE_URL=https://your-mealie-instance.com \
  --env-var MEALIE_API_KEY=your-mealie-api-key
```

#### Option 2: Using uvx

Run directly from GitHub without cloning:

```json
{
  "mcpServers": {
    "mealie-mcp-server": {
      "command": "uvx",
      "args": ["git+https://github.com/rldiao/mealie-mcp-server"],
      "env": {
        "MEALIE_BASE_URL": "https://your-mealie-instance.com",
        "MEALIE_API_KEY": "your-mealie-api-key"
      }
    }
  }
}
```

Restart Claude Desktop to load the server.

## 🌐 Remote Access (HTTP Transport)

By default, the server runs over stdio, which works for local clients like Claude Desktop. To make it reachable remotely (e.g. from claude.ai custom connectors, or multiple devices), run it with the streamable-http transport instead.

### Configuration

Set these environment variables:

| Variable        | Default     | Description                                          |
|-----------------|-------------|-------------------------------------------------------|
| `MCP_TRANSPORT` | `stdio`     | `stdio` or `streamable-http`                          |
| `MCP_HOST`      | `127.0.0.1` | Bind address (use `0.0.0.0` in containers)            |
| `MCP_PORT`      | `8765`      | Port to listen on                                     |

### Example

```bash
export MCP_TRANSPORT=streamable-http
export MCP_HOST=0.0.0.0
export MCP_PORT=8765
python src/server.py
```

The server will expose its MCP endpoint at `http://<host>:<port>/mcp`.

⚠️ **Security note**: streamable-http mode has no built-in authentication. If exposing this beyond your local network, put it behind a reverse proxy that enforces auth (bearer token, basic auth, or OAuth) before it reaches the internet.

## 🐳 Docker

A `Dockerfile` is included for running the server as a persistent container — useful for pairing it with a self-hosted Mealie instance (e.g. via Docker Compose) rather than launching it per-session from Claude Desktop.

### Build

```bash
docker build -t mealie-mcp-server .
```

### Run standalone

```bash
docker run -d \
  --name mealie-mcp \
  -e MEALIE_BASE_URL=http://your-mealie-host:9000 \
  -e MEALIE_API_KEY=your-mealie-api-key \
  -e MCP_TRANSPORT=streamable-http \
  -e MCP_HOST=0.0.0.0 \
  -e MCP_PORT=8765 \
  -p 8765:8765 \
  mealie-mcp-server
```

### Run alongside Mealie via Docker Compose

```yaml
services:
  mealie-mcp:
    build: .
    container_name: mealie-mcp
    restart: unless-stopped
    environment:
      MEALIE_BASE_URL: http://mealie:9000   # internal service name, no need to expose Mealie publicly
      MEALIE_API_KEY: ${MEALIE_API_KEY}
      MCP_TRANSPORT: streamable-http
      MCP_HOST: "0.0.0.0"
      MCP_PORT: "8765"
    expose:
      - "8765"
    networks:
      - mealie_net
```

⚠️ As noted above, `streamable-http` has no built-in authentication — put a reverse proxy (with bearer token, basic auth, or OAuth) in front of it if it needs to be reachable outside your local network.

## 📖 Usage Examples

### Recipe Operations

```
"Search for chicken recipes"
"Create a new recipe for pasta carbonara"
"Duplicate my lasagna recipe"
"Mark the meatloaf recipe as made today"
"Upload an image for the chocolate cake recipe"
```

### Shopping Lists

```
"Create a shopping list for this week"
"Add eggs and milk to my shopping list"
"Add all ingredients from the lasagna recipe to my shopping list"
"Check off milk on my shopping list"
"Delete all checked items from my shopping list"
```

### Organization

```
"Show me all my recipe categories"
"Create a new tag called 'Quick Meals'"
"Find all recipes tagged with 'healthy'"
"Show me categories that have no recipes"
```

### Advanced Filtering

```
"Find recipes that have both 'quick' AND 'healthy' tags"
"Search for breakfast recipes containing 'eggs'"
"Show me all vegetarian dinner recipes"
```

## 🎯 Available Tools

### Recipe Tools (13 operations)

- `get_recipes` - List/search recipes with advanced filtering
- `get_recipe_detailed` - Get complete recipe details
- `get_recipe_concise` - Get recipe summary
- `create_recipe` - Create new recipe (flat or structured ingredients)
- `create_recipe_full` - Create a recipe with full content (including nutrition and display settings) in one call
- `update_recipe` - Update recipe (full replacement)
- `patch_recipe` - Update specific fields only (including nutrition and display settings)
- `duplicate_recipe` - Clone a recipe
- `mark_recipe_last_made` - Update last made timestamp
- `set_recipe_image_from_url` - Set image from URL
- `upload_recipe_image_file` - Upload image file
- `upload_recipe_asset_file` - Upload document/asset
- `delete_recipe` - Delete recipe

### Shopping List Tools (14 operations)

- `get_shopping_lists` - List all shopping lists
- `create_shopping_list` - Create new list
- `get_shopping_list` - Get list by ID
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

### Category Tools (7 operations)

- `get_categories` - List/search categories
- `get_empty_categories` - Find unused categories
- `create_category` - Create new category
- `get_category` - Get by ID
- `get_category_by_slug` - Get by slug
- `update_category` - Update category
- `delete_category` - Delete category

### Tag Tools (7 operations)

- `get_tags` - List/search tags
- `get_empty_tags` - Find unused tags
- `create_tag` - Create new tag
- `get_tag` - Get by ID
- `get_tag_by_slug` - Get by slug
- `update_tag` - Update tag
- `delete_tag` - Delete tag

### Food Tools (5 operations)
- `get_foods` - List/search foods (resolve ids for structured ingredients)
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

### Recipe Tool Tools (6 operations)
- `get_tools` - List/search recipe tools (includes `householdsWithTool`)
- `create_tool` - Create a new tool
- `get_tool` - Get by ID
- `get_tool_by_slug` - Get by slug
- `update_tool` - Update tool
- `delete_tool` - Delete tool

### Parser Tools (2 operations)

- `parse_ingredient` - Resolve one free-text ingredient line
- `parse_ingredients` - Resolve a whole recipe's ingredients in one request

### Meal Plan Tools (4 operations)

- `get_all_mealplans` - List meal plans
- `create_mealplan` - Create meal plan entry
- `create_mealplan_bulk` - Create multiple entries
- `get_todays_mealplan` - Get today's meals

**Total: 62 tools** providing comprehensive Mealie API coverage

## 🔧 Development

### Setup

1. Clone the repository:

```bash
git clone <repository-url>
cd mealie-mcp-server
```

2. Install dependencies:

```bash
uv sync
```

3. Configure environment:

```bash
cp .env.template .env
# Edit .env with your Mealie instance details
```

4. Run MCP inspector for testing:

```bash
uv run mcp dev src/server.py
```

### Project Structure

```
mealie-mcp-server/
├── src/
│   ├── mealie/              # API client mixins
│   │   ├── client.py        # Base HTTP client
│   │   ├── recipe.py        # Recipe operations
│   │   ├── shopping_list.py # Shopping list operations
│   │   ├── categories.py    # Category operations
│   │   ├── tags.py          # Tag operations
│   │   ├── mealplan.py      # Meal plan operations
│   │   ├── parser.py        # Ingredient parser
│   │   └── __init__.py      # MealieFetcher aggregator
│   ├── tools/               # MCP tool definitions
│   │   ├── recipe_tools.py
│   │   ├── shopping_list_tools.py
│   │   ├── categories_tools.py
│   │   ├── tags_tools.py
│   │   ├── mealplan_tools.py
│   │   ├── parser_tools.py
│   │   └── __init__.py
│   ├── models/              # Pydantic models
│   ├── server.py            # MCP server entry point
│   └── prompts.py           # Server prompts
├── CHANGELOG.md             # Version history
└── README.md
```

## 📚 Important Notes

### Filtering by Tags/Categories

When filtering recipes, you **must use slugs or UUIDs**, not display names:

✅ **Correct:**

```
"Get recipes with tags=['quick-meals', 'healthy']"
```

❌ **Incorrect:**

```
"Get recipes with tags=['Quick Meals', 'Healthy']"
```

Use `get_tags()` or `get_categories()` first to find the correct slugs.

### Nutrition Is Replaced, Not Merged

Mealie replaces the whole `nutrition` object on write. `patch_recipe` follows
suit, so pass every value you want to keep:

```
# clears every nutrition value except fat
patch_recipe(slug="...", nutrition={"fatContent": "12"})
```

### Parsing Ingredients in Bulk

Resolving ingredients by hand costs one to two `get_foods` / `get_units` calls
each. `parse_ingredients` does a whole recipe in one request and returns results
that can be handed straight to `create_recipe_full`:

```
parse_ingredients(ingredients=["1/4 cup chopped onion", "2 large eggs"])
# -> [{"input": "1/4 cup chopped onion", "confidence": 0.99, "quantity": 0.25,
#      "unit": {"id": "...", "name": "cup"},
#      "food": {"id": "...", "name": "onion"}, "note": "chopped"}, ...]
```

A `null` unit or food means your instance has no matching entry — create one
with `create_food` / `create_unit`, or leave the text in the note. Pass
`verbose=True` for Mealie's full response including per-field confidences.

### Uploaded Assets and Nutrition Can Be Stored but Hidden

A recipe's `settings` object controls what the UI renders. `showAssets` and
`showNutrition` gate the assets and nutrition cards, so an asset uploaded with
`upload_recipe_asset_file` can be present in the API response and still be
invisible in the web UI. Flip the toggle with:

```
patch_recipe(slug="...", settings={"showAssets": True})
```

Mealie seeds a new recipe's settings from the household preferences
(`recipeShowAssets`, `recipeShowNutrition`, ...), so the defaults differ per
instance — check rather than assume.

Only the toggles you pass are changed. The tool reads the recipe's current
settings and sends the merged object, because Mealie does not reliably preserve
toggles omitted from a settings PATCH.

### Field Preservation

When updating shopping list items, the server automatically preserves all existing fields. You only need to specify the fields you want to change:

```
# Only updates 'checked' field, preserves note, quantity, etc.
update_shopping_list_item(item_id="...", checked=True)
```

## 🐛 Known Issues

None currently! All features have been tested end-to-end with Claude Desktop.

## 🔄 Changelog

See [CHANGELOG.md](CHANGELOG.md) for a detailed list of changes and version history.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Credits

- [Mealie](https://github.com/mealie-recipes/mealie) - The recipe management system
- [FastMCP](https://github.com/jlowin/fastmcp) - The MCP framework

## 📞 Support

For issues and questions:

- Check the [CHANGELOG.md](CHANGELOG.md) for recent updates
- Review the Mealie API documentation
- Open an issue on GitHub

## 🔗 Related Links

- [Mealie Documentation](https://docs.mealie.io)
- [MCP Protocol Specification](https://modelcontextprotocol.io)
- [Claude Desktop](https://claude.ai/download)
