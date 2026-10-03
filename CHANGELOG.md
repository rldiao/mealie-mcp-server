# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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

### Added

- `create_recipe` and `update_recipe` accept a `nutrition` argument covering
  Mealie's full key set (calories, macros, cholesterol, sodium, sugars, and the
  fat breakdown). Numbers are converted to the strings Mealie stores. Mealie
  replaces the whole nutrition object on write, so `update_recipe` clears any key
  not passed.
- `parse_ingredients` wraps Mealie's server-side
  ingredient parser, resolving free text such as `"1/4 cup chopped onion"`
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

- Assets and nutrition could be written but not seen. `showAssets` and
  `showNutrition` gate the corresponding UI cards, and nothing in the server
  could read or write them, so an asset uploaded through
  `upload_recipe_asset_file` was present in the API response yet invisible in
  the Mealie UI whenever the household default left the toggle off.
