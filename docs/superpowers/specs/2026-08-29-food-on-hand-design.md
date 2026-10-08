# Mark Foods On-Hand — Design

## Problem

There is no way to mark a food as "on hand" (i.e. present in the pantry) via
the MCP server. Doing this in the Mealie web UI requires opening each food's
edit page individually, which doesn't scale for a batch of common pantry
staples.

This Mealie instance does not model on-hand status as a simple global
`onHand: bool` on the food. Instead, `IngredientFood` carries
`householdsWithIngredientFood: string[]`, a list of household IDs for which
the food is considered on-hand. A food is on-hand for the current household
iff that household's id is present in the list. The current household id is
available via the existing `UserMixin.get_current_user()`
(`GET /api/users/self` → `householdId`).

## Goal

Add tools to mark (or clear) on-hand status:

- By food id, for callers that already have it (`set_food_on_hand`).
- By name, for the common case of "mark these pantry staples on hand"
  without knowing Mealie UUIDs (`mark_foods_on_hand`). Names are matched
  case-insensitively against existing foods; unmatched names are created,
  mirroring how `add_recipe_tags` handles tag names.
- Both directions: `on_hand=True` to mark, `on_hand=False` to clear, so
  running out of an ingredient can also be reflected.

## Non-goals

- Modeling on-hand status for households other than the caller's current one.
- A bulk Mealie API call — no such endpoint exists for foods, so the by-name
  tool issues one PUT per resolved food.

## Design

### 1. Mixin methods (`src/mealie/foods.py`)

```python
def set_food_on_hand(self, food_id: str, on_hand: bool = True) -> Dict[str, Any]
def set_foods_on_hand_by_name(self, names: List[str], on_hand: bool = True) -> Dict[str, Any]
```

`set_food_on_hand`:

1. Validate `food_id` is non-empty.
2. Fetch the existing food via `self.get_food(food_id)` (fetch-merge, same
   reasoning as `update_food` — Mealie's PUT replaces the whole record).
3. Fetch `household_id = self.get_current_user().get("householdId")`.
4. Copy `existing["householdsWithIngredientFood"]`; append `household_id` if
   `on_hand` and not already present, or filter it out otherwise.
5. `PUT /api/foods/{food_id}` with the existing record merged with the
   updated list.

`set_foods_on_hand_by_name`:

1. Validate `names` is a non-empty list.
2. Resolve `household_id` once.
3. For each name (stripped, blanks skipped): search
   `self.get_foods(search=name)` and match case-insensitively on `name`
   (same approach as `add_recipe_tags`'s tag matching); create it via
   `self.create_food(name)` if no match, recording the name as created.
4. Apply the same on-hand list merge as `set_food_on_hand`, PUT per food.
5. Return `{"updated": [...], "created": [...]}`.

### 2. MCP tool wrappers (`src/tools/foods_tools.py`)

```python
@mcp.tool()
def set_food_on_hand(food_id: str, on_hand: bool = True) -> Dict[str, Any]

@mcp.tool()
def mark_foods_on_hand(names: List[str], on_hand: bool = True) -> Dict[str, Any]
```

Thin wrappers with the same try/except/`ToolError` pattern as the rest of
`foods_tools.py`. `mark_foods_on_hand` is the primary user-facing entry point
for "mark my common ingredients on hand."

### 3. Test fixture support (`tests/conftest.py`)

`FakeFetcher` had no handling for `GET /api/users/self` (fell through to a
generic stub) and its `/api/foods` list/create/single-GET/PUT branches
returned fixed canned data rather than a real store, which can't support
name-matching assertions. Add:

- `self.foods: List[Dict[str, Any]] = []` in `__init__`.
- `GET /api/users/self` → `{"id": "user-1", "householdId": "household-1", "email": "test@example.com"}`.
- `GET /api/foods` → filters `self.foods` by `search` (case-insensitive
  substring on `name`), paginated-shaped response.
- `POST /api/foods` → creates a food dict from the body plus a generated id
  and `householdsWithIngredientFood: []`, appends to `self.foods`.
- `GET /api/foods/{id}` → looks up `self.foods` by id if present, else falls
  back to the old generic stub (now including
  `"householdsWithIngredientFood": []`).
- `PUT /api/foods/{id}` → echoes the body and updates the matching entry in
  `self.foods` in place.

Units/tools keep their existing generic canned responses untouched.

### 4. Tests (`tests/test_food_on_hand_tools.py`)

- `set_food_on_hand` marks on, unmarks, and is idempotent when re-marking.
- `set_food_on_hand` validates a non-empty `food_id`.
- `mark_foods_on_hand` reuses an existing food by name (no create call).
- `mark_foods_on_hand` creates a missing food and reports it in `created`.
- `mark_foods_on_hand(on_hand=False)` clears the household from a matched food.
- `mark_foods_on_hand` validates a non-empty `names` list.
- Both tool names added to the existing `test_tool_is_registered` parametrization.

### 5. Docs (`README.md`)

Add two bullets to the "Food Tools" section for `set_food_on_hand` and
`mark_foods_on_hand`, and bump the operation counts.

## Open questions

None — scope confirmed with the user: ship both a by-id and by-name tool,
auto-create missing foods by name, support both mark/clear directions via an
`on_hand` bool.
