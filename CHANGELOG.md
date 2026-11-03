# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Unreleased

### Added

- Mealie 3.30 support:
  - `create_mealplan`, `create_mealplan_bulk`, and `update_mealplan` take
    `end_date` for entries that span a week; `update_mealplan` also takes
    `clear_end_date`.
  - `get_all_mealplans` takes `include_week_entries`. Mealie leaves week-long
    entries out of the list unless it is set.
  - Recipe instruction steps accept `durationSeconds`.

### Changed

- Refreshed `openapi.json` to the Mealie v3.30.0 spec.

## 0.2.0 - 2026-10-18

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
- Support for Mealie 3.25 to 3.29 features:
  - Structured recipe times: `total_time_seconds`, `prep_time_seconds`, and
    `perform_time_seconds` on `create_recipe` and `update_recipe`.
  - `get_recipes` takes `query_filter`, `order_by`, `order_direction`, and
    `cookbook`, e.g. `totalTimeSeconds <= 1800` or `rating >= 4`.
  - `recipe_scale` on meal plan entries, and the `snack`, `drink`, and
    `dessert` meal types.
  - Recipe notes can be linked to instruction steps (`referenceId` on notes,
    `noteReferences` on steps).
  - `merge_organizers` merges a duplicate tag, category, tool, label, food, or
    unit into another, and `get_empty_foods`, `get_empty_tools`, and
    `get_empty_labels` list unused ones.
  - `set_food_substitutions` sets common "may be replaced by" substitutions.
  - `get_mealplan_ical_feed` and `set_mealplan_ical_feed` manage the public
    calendar feed of the meal plan.
- Cookbooks (`get_cookbooks`, `create_cookbook`, `update_cookbook`,
  `delete_cookbook`), meal plan rules (`get_mealplan_rules`,
  `create_mealplan_rule`, `update_mealplan_rule`, `delete_mealplan_rule`),
  `create_random_mealplan`, and per-user ratings (`rate_recipe`,
  `get_my_recipe_ratings`). The MCP inventory is now 95 tools.
- Opt-in integration tests run the tools against a disposable Mealie in
  Docker (`MEALIE_INTEGRATION=1`), plus a nightly workflow against the latest
  Mealie image.

### Fixed

- `set_food_on_hand`, `mark_foods_on_hand`, `set_tool_on_hand`, and
  `mark_tools_on_hand` reported success without changing anything, because
  they wrote household IDs where Mealie expects household slugs.
- `update_label` always failed with HTTP 422; it now fetches the label and
  merges the change, as Mealie's PUT requires the full record.
- `get_recipe(concise=True)` now includes `lastMade`, which Mealie 3 stores
  per household rather than on the recipe.
- `update_mealplan` and `delete_mealplan` accept the integer IDs Mealie
  returns for meal plan entries.
- The last-made timestamp no longer uses the deprecated `datetime.utcnow`.

- Recipes now expose `showAssets` and `showNutrition` through their settings.
  Previously, uploaded assets and nutrition could be stored but hidden in the
  Mealie UI when household defaults disabled those cards.
