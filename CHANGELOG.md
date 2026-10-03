# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- `create_recipe_full` and `patch_recipe` accept a `nutrition` argument covering
  Mealie's full key set (calories, macros, cholesterol, sodium, sugars, and the
  fat breakdown). Numbers are converted to the strings Mealie stores. Mealie
  replaces the whole nutrition object on write, so `patch_recipe` clears any key
  not passed.
- `parse_ingredient` and `parse_ingredients` wrap Mealie's server-side
  ingredient parser, resolving free text such as `"1/4 cup chopped onion"`
  against the instance's food and unit vocabulary in one request instead of
  searching `get_foods` and `get_units` per ingredient. Results are flattened to
  `{input, confidence, quantity, unit, food, note}` and can be passed straight
  to `create_recipe_full`; `verbose=True` returns Mealie's untouched response.
  Both accept Mealie's `nlp`, `brute`, and `openai` parser backends.
- `create_recipe_full` and `patch_recipe` accept a `settings` argument for
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
