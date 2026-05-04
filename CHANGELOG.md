# Changelog

All notable changes to the Mealie MCP Server.

## [Unreleased] - 2025-01-05

### 🎉 Major Feature Additions

This release adds **44+ new API operations** across shopping lists, categories, tags, and recipe enhancements, bringing the MCP server to near-complete API coverage.

### ✨ New Features

#### Shopping Lists (17 new operations)
- **Shopping List Management**
  - `get_shopping_lists` - List all shopping lists with search and filtering
  - `create_shopping_list` - Create new shopping list
  - `get_shopping_list` - Get specific list by ID
  - `update_shopping_list` - Update list details
  - `delete_shopping_list` - Delete shopping list
  - `add_recipe_to_shopping_list` - Add recipe ingredients to list with quantity multiplier
  - `remove_recipe_from_shopping_list` - Remove recipe ingredients from list

- **Shopping List Items**
  - `get_shopping_list_items` - List all items with search and pagination
  - `get_shopping_list_item` - Get specific item by ID
  - `create_shopping_list_item` - Create single item with full field support (note, quantity, unit, food, label)
  - `create_shopping_list_items_bulk` - Bulk create multiple items
  - `update_shopping_list_item` - Update item with automatic field preservation
  - `update_shopping_list_items_bulk` - Bulk update multiple items
  - `delete_shopping_list_item` - Delete single item
  - `delete_shopping_list_items_bulk` - Bulk delete using query parameters

#### Categories (7 new operations)
- `get_categories` - List all categories with search, filtering, and pagination
- `get_empty_categories` - Find categories with no recipes
- `create_category` - Create new category
- `get_category` - Get category by ID
- `get_category_by_slug` - Get category by slug
- `update_category` - Update category details
- `delete_category` - Delete category

#### Tags (7 new operations)
- `get_tags` - List all tags with search, filtering, and pagination
- `get_empty_tags` - Find tags with no recipes
- `create_tag` - Create new tag
- `get_tag` - Get tag by ID
- `get_tag_by_slug` - Get tag by slug
- `update_tag` - Update tag details
- `delete_tag` - Delete tag

#### Recipe Enhancements (13+ new operations)
- **CRUD Operations**
  - `patch_recipe` - Partial recipe updates (only specified fields)
  - `duplicate_recipe` - Clone existing recipe with optional name override
  - `delete_recipe` - Delete recipe permanently

- **Recipe Metadata**
  - `mark_recipe_last_made` - Update last made timestamp (auto-generates if not provided)

- **Image & Asset Management**
  - `set_recipe_image_from_url` - Scrape and set recipe image from URL
  - `upload_recipe_image_file` - Upload image file (multipart)
  - `upload_recipe_asset_file` - Upload asset/document file (multipart)

- **URL Import**
  - `import_recipe_from_url` - Create a recipe by scraping a URL using Mealie's server-side scraper (`recipe-scrapers` library); returns the created recipe so callers can verify the scrape result

- **Advanced Filtering**
  - `require_all_tags` - AND logic for tag filtering (default: OR)
  - `require_all_categories` - AND logic for category filtering
  - `require_all_tools` - AND logic for tool filtering

### 🔧 Enhancements

#### Search & Filtering
- Added comprehensive search parameters to all list endpoints:
  - `search` - Full-text search
  - `query_filter` - Advanced query filtering
  - `order_by` - Sort by any field
  - `order_direction` - Sort ascending/descending
  - `order_by_null_position` - Handle null values in sorting
  - `pagination_seed` - Consistent pagination across requests

#### Multipart Upload Support
- Enhanced base client to support both JSON and multipart/form-data requests
- Automatic Content-Type header management based on request type
- Full support for file uploads (images, assets, documents)

### 🐛 Bug Fixes

#### Critical Fixes
1. **Shopping List Item Update - Field Preservation**
   - **Issue:** Updating an item cleared any fields not explicitly provided in the update
   - **Fix:** Implemented fetch-merge-update pattern that preserves all existing fields
   - **Impact:** Prevents data loss when updating shopping list items

2. **Delete Operations - Empty Response Handling**
   - **Issue:** DELETE operations returning `null` or empty responses caused validation errors
   - **Fix:** Added normalization for `null` JSON responses and empty content
   - **Impact:** All delete operations now work correctly (categories, tags, shopping lists, recipes)

3. **Recipe Duplicate - Missing Request Body**
   - **Issue:** API requires JSON body but tool wasn't sending one
   - **Fix:** Always send proper JSON body (empty object or with name override)
   - **Impact:** Recipe duplication now works without errors

4. **Recipe Last Made - Missing Timestamp**
   - **Issue:** API requires timestamp field but tool sent empty object
   - **Fix:** Auto-generate current UTC timestamp if not provided
   - **Impact:** Marking recipes as made now works seamlessly

#### Documentation Improvements
- **Tag/Category Filtering Clarification**
  - Added explicit documentation that filtering requires **slugs or UUIDs**, not display names
  - Tool descriptions now include examples: `tags=["quick-meals"]` ✅ vs `tags=["Quick Meals"]` ❌
  - Prevents silent filter failures due to incorrect identifiers

### 📝 API Changes

#### New Mixin Classes
- `ShoppingListMixin` - Complete shopping list and item management
- `CategoriesMixin` - Recipe category organization
- `TagsMixin` - Recipe tag management

#### Updated Mixins
- `RecipeMixin` - Enhanced with PATCH, duplicate, delete, images, assets, and advanced filtering
- `MealieClient` - Enhanced response handling for empty/null responses and multipart uploads

#### New Tool Modules
- `shopping_list_tools.py` - 14 shopping list tools
- `categories_tools.py` - 7 category tools
- `tags_tools.py` - 7 tag tools

#### Updated Tool Modules
- `recipe_tools.py` - Added 7 new recipe tools

### 🔄 Breaking Changes

**None** - All changes are backwards compatible. Existing tools continue to work as before.

### 📊 API Coverage

**Before This Release:**
- Recipe operations: 5 tools
- Mealplan operations: 4 tools
- **Total: 9 tools**

**After This Release:**
- Recipe operations: 13 tools
- Mealplan operations: 4 tools
- Shopping list operations: 14 tools
- Category operations: 7 tools
- Tag operations: 7 tools
- **Total: 45 tools**

**Coverage Increase:** +400% (from 9 to 45 tools)

### 🧪 Testing

All features tested end-to-end with Claude Desktop:
- ✅ Shopping list CRUD and bulk operations
- ✅ Category CRUD with empty response handling
- ✅ Tag CRUD operations
- ✅ Recipe filtering by slugs (with AND/OR logic)
- ✅ Recipe PATCH, duplicate, and last-made operations
- ✅ Field preservation on updates
- ✅ Delete operation response handling

### 📚 Documentation

- Enhanced tool descriptions with usage examples
- Added parameter documentation for all new features
- Clarified slug vs display name usage for filtering
- Documented multipart upload capabilities

### 🙏 Credits

- Based on the original [mealie-mcp-server](https://github.com/rldiao/mealie-mcp-server) by @rldiao
- Mealie API by [mealie-recipes](https://github.com/mealie-recipes/mealie)
- Built with [FastMCP](https://github.com/jlowin/fastmcp)

---

## [0.1.0] - Previous Release

Initial release with basic recipe and mealplan operations.

### Features
- Basic recipe operations (get, create, update)
- Mealplan operations (get, create, bulk)
- User and group management endpoints
