# Mark Foods On-Hand Implementation Plan

**Goal:** Add `set_food_on_hand` (by id) and `mark_foods_on_hand` (by name, auto-creating unknown foods) so common ingredients can be marked or cleared as on-hand for the current household without using the Mealie web UI.

**Architecture:** Two new `FoodsMixin` methods in `src/mealie/foods.py` fetch-merge the food record's `householdsWithIngredientFood` list (Mealie tracks on-hand status per household rather than as a single boolean) and PUT it back, using `UserMixin.get_current_user()` to resolve the current household id. `set_foods_on_hand_by_name` additionally resolves names to foods via `get_foods(search=...)` with case-insensitive matching, creating missing foods via `create_food`, following the same pattern `RecipeMixin.add_recipe_tags` uses for tag names. Thin MCP tool wrappers in `src/tools/foods_tools.py` expose both.

**Tech Stack:** Python 3.12, FastMCP (`mcp.server.fastmcp`), pytest (async), uv, ruff.

Spec: `docs/superpowers/specs/2026-08-29-food-on-hand-design.md`

---

### Task 1: Extend the test double for households, users/self, and a real foods store

**Files:** `tests/conftest.py`

- [x] Add `self.foods = []` to `FakeFetcher.__init__`.
- [x] Add a `GET /api/users/self` fake returning `{"id": "user-1", "householdId": "household-1", "email": "test@example.com"}` (previously fell through to a generic `{"ok": True}` stub).
- [x] Replace the generic `/api/foods` branches (list, create, single GET, PUT) with logic backed by `self.foods`: `GET /api/foods` filters by `search` (case-insensitive substring on `name`); `POST /api/foods` appends a new record with a generated id and `householdsWithIngredientFood: []`; `GET /api/foods/{id}` looks up the store first, falling back to the old generic stub (now including `householdsWithIngredientFood: []`) for ids not in the store; `PUT /api/foods/{id}` echoes the body and updates the store entry in place.
- [x] Leave the units/tools generic list/create/GET/PUT branches untouched.
- [x] Confirm `test_organizer_tools.py::test_get_foods_forwards_search_and_pagination` / `test_create_food` still pass — they only assert on the recorded request, not response content.

Run: `uv run pytest -q` — all existing tests still pass.

---

### Task 2: Implement the `FoodsMixin` on-hand methods

**Files:** `src/mealie/foods.py`

- [x] Add `List` to the `typing` import.
- [x] Add `set_food_on_hand(self, food_id, on_hand=True)`: validates `food_id`, fetches the existing food and current household id, merges `household_id` into/out of `householdsWithIngredientFood`, PUTs the merged record.
- [x] Add `set_foods_on_hand_by_name(self, names, on_hand=True)`: validates `names` non-empty, resolves the household id once, then per name searches `get_foods(search=name)` for a case-insensitive exact match (creating via `create_food` if none found), applies the same on-hand merge, and PUTs. Returns `{"updated": [...], "created": [...]}`.

---

### Task 3: Implement the MCP tool wrappers

**Files:** `src/tools/foods_tools.py`

- [x] Add `List` to the `typing` import.
- [x] Add `set_food_on_hand(food_id: str, on_hand: bool = True)` tool, thin wrapper with the same try/except/`ToolError` pattern as `update_food`.
- [x] Add `mark_foods_on_hand(names: List[str], on_hand: bool = True)` tool, thin wrapper calling `mealie.set_foods_on_hand_by_name`.
- No changes needed in `src/tools/__init__.py` — both live inside the already-registered `register_foods_tools`.

---

### Task 4: Tests

**Files:** `tests/test_food_on_hand_tools.py` (new), `tests/test_organizer_tools.py`

- [x] `set_food_on_hand` marks on, unmarks, is idempotent when re-marking, and validates a non-empty `food_id`.
- [x] `mark_foods_on_hand` reuses an existing food by name (no `POST /api/foods`), creates a missing food and reports it in `created`, clears the household when `on_hand=False`, and validates a non-empty `names` list.
- [x] Added `set_food_on_hand` and `mark_foods_on_hand` to the parametrized `test_tool_is_registered` list in `test_organizer_tools.py`.

Run: `uv run pytest -q` — 74 passed (9 new).
Run: `uv run ruff check src tests` — no errors.

---

### Task 5: Document the new tools

**Files:** `README.md`

- [x] Added `set_food_on_hand` and `mark_foods_on_hand` bullets to the Food Tools section, bumped its count to 7 operations and the total tool count to 64.

---

## Self-Review Notes

- **Spec coverage:** mixin methods (Task 2), MCP tools (Task 3), test fixture support (Task 1), tests for mark/clear/idempotent/create/validate (Task 4), README bullets (Task 5) — all spec sections covered.
- **Type consistency:** both mixin methods and their tool wrappers share parameter names (`food_id`, `names`, `on_hand`) — no positional-only remapping like `add_recipe_tags`'s `tags`/`tag_names` split was needed here.
- **Behavior verified against schema, not assumption:** the bundled `openapi.json`'s `IngredientFood-Output` schema was inspected directly to confirm `householdsWithIngredientFood: string[]` is the real on-hand field (an earlier global `onHand: bool` field, still referenced in some Mealie docs/older versions, does not exist in this schema snapshot) before writing the mixin.
