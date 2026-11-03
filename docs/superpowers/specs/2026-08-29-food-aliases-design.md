# Manage Food Aliases — Design

## Problem

Mealie foods carry an `aliases` list (`IngredientFoodAlias` objects, each
just `{"name": str}`) used to match alternate names for a food when parsing
recipe ingredients (e.g. "Scallion" as an alias for "Green Onion"). There is
no way to inspect or change this list via the MCP server — the closest
existing tool, `update_food`, only covers `name`/`pluralName`/`description`.

## Goal

Add tools to fully manage a food's aliases:

- Replace the whole list (`set_food_aliases`) — the "update" operation, and
  the only way to clear all aliases (pass an empty list).
- Add one alias without disturbing existing ones (`add_food_alias`) —
  "modify"/create, matching the `add_recipe_tags` precedent for additive
  changes.
- Remove one alias by name (`remove_food_alias`) — "delete", without the
  caller needing to fetch the current list, filter it themselves, then call
  `set_food_aliases`.

Alias names are matched case-insensitively for de-duplication (`set`/`add`)
and removal (`remove`), consistent with how tag/on-hand matching already
works elsewhere in this codebase.

## Non-goals

- Bulk alias operations across multiple foods in one call (aliases are a
  per-food edit, unlike the "mark common ingredients on hand" batch case).
- Validating alias names against Mealie's ingredient parser.

## Design

### 1. Mixin methods (`src/mealie/foods.py`)

```python
def set_food_aliases(self, food_id: str, aliases: List[str]) -> Dict[str, Any]
def add_food_alias(self, food_id: str, alias: str) -> Dict[str, Any]
def remove_food_alias(self, food_id: str, alias: str) -> Dict[str, Any]
```

All three follow the same fetch-merge pattern as `update_food`/`set_food_on_hand`
(Mealie's PUT replaces the whole food record):

- `set_food_aliases`: fetches the food, converts the given name list to
  `[{"name": ...}]` dicts, stripping blanks and de-duplicating
  case-insensitively (first occurrence wins, order preserved), then PUTs the
  merged record.
- `add_food_alias`: fetches the food, and if the given alias isn't already
  present (case-insensitive), appends `{"name": alias}` to the existing
  `aliases` list, then PUTs. If the alias is already present, the PUT still
  runs with an unchanged list (kept simple; no special-cased no-op path).
- `remove_food_alias`: fetches the food, filters `aliases` to drop any entry
  whose `name` matches case-insensitively, then PUTs. No match is a no-op
  PUT with the list unchanged.

### 2. MCP tool wrappers (`src/tools/foods_tools.py`)

```python
@mcp.tool()
def set_food_aliases(food_id: str, aliases: List[str]) -> Dict[str, Any]

@mcp.tool()
def add_food_alias(food_id: str, alias: str) -> Dict[str, Any]

@mcp.tool()
def remove_food_alias(food_id: str, alias: str) -> Dict[str, Any]
```

Thin wrappers, same try/except/`ToolError` pattern as the rest of
`foods_tools.py`.

### 3. Test fixture support (`tests/conftest.py`)

The existing foods store (added for on-hand tracking) already supports
fetch-merge PUT round-tripping via `self.foods`; no new endpoint fakes are
needed. Only change: the generic single-food GET fallback (for food ids not
pre-seeded into `self.foods`) gains `"aliases": []` alongside the existing
`"householdsWithIngredientFood": []` default.

### 4. Tests (`tests/test_food_alias_tools.py`)

- `set_food_aliases` replaces the list, de-dupes case-insensitively, and can
  clear all aliases with an empty list; validates a non-empty `food_id`.
- `add_food_alias` appends to an existing list and skips a case-insensitive
  duplicate; validates a non-empty `alias`.
- `remove_food_alias` removes a case-insensitive match and is a no-op when
  there's no match; validates a non-empty `alias`.
- All three tool names added to the existing `test_tool_is_registered`
  parametrization.

### 5. Docs (`README.md`)

Add three bullets to the "Food Tools" section, bump its operation count and
the total tool count.

## Open questions

None — scope covers replace/add/remove as the user explicitly asked for
"update, delete, modify" of aliases.
