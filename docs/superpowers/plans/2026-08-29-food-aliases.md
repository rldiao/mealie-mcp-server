# Manage Food Aliases Implementation Plan

**Goal:** Add `set_food_aliases`, `add_food_alias`, and `remove_food_alias` so a food's alias list can be fully managed (replace, add one, remove one) without hand-editing the Mealie web UI.

**Architecture:** Three new `FoodsMixin` methods in `src/mealie/foods.py` fetch-merge the food record's `aliases` list (each entry a `{"name": str}` dict) and PUT it back, following the same fetch-merge pattern as `update_food`/`set_food_on_hand`. Thin MCP tool wrappers in `src/tools/foods_tools.py` expose all three, mirroring the `set_recipe_tags`/`add_recipe_tags` replace-vs-additive precedent, plus a dedicated remove so callers don't have to fetch-filter-set manually.

**Tech Stack:** Python 3.12, FastMCP (`mcp.server.fastmcp`), pytest (async), uv, ruff.

Spec: `docs/superpowers/specs/2026-08-29-food-aliases-design.md`

---

### Task 1: Implement the `FoodsMixin` alias methods

**Files:** `src/mealie/foods.py`

- [x] `set_food_aliases(self, food_id, aliases)`: validates `food_id` and that `aliases` is not `None`, fetches the existing food, converts the name list to de-duplicated (case-insensitive) `{"name": ...}` dicts, PUTs the merged record.
- [x] `add_food_alias(self, food_id, alias)`: validates both args non-empty, fetches the existing food, appends `{"name": alias}` if not already present case-insensitively, PUTs.
- [x] `remove_food_alias(self, food_id, alias)`: validates both args non-empty, fetches the existing food, filters out any case-insensitive match, PUTs.

---

### Task 2: Implement the MCP tool wrappers

**Files:** `src/tools/foods_tools.py`

- [x] Add `set_food_aliases(food_id: str, aliases: List[str])`, `add_food_alias(food_id: str, alias: str)`, and `remove_food_alias(food_id: str, alias: str)` tools — thin wrappers with the same try/except/`ToolError` pattern as the rest of the file.
- No changes needed in `src/tools/__init__.py` — all three live inside the already-registered `register_foods_tools`.

---

### Task 3: Tests

**Files:** `tests/test_food_alias_tools.py` (new), `tests/conftest.py`, `tests/test_organizer_tools.py`

- [x] Added `"aliases": []` to the generic single-food GET fallback in `FakeFetcher` (food ids not pre-seeded into `self.foods`); no other fixture changes needed since the existing `self.foods` store already round-trips fetch-merge PUTs.
- [x] `set_food_aliases` replaces the list, de-dupes case-insensitively, clears with an empty list, validates `food_id`.
- [x] `add_food_alias` appends and skips a case-insensitive duplicate, validates `alias`.
- [x] `remove_food_alias` removes a case-insensitive match and no-ops when absent, validates `alias`.
- [x] Added `set_food_aliases`, `add_food_alias`, `remove_food_alias` to the parametrized `test_tool_is_registered` list in `test_organizer_tools.py`.

Run: `uv run pytest -q` — 87 passed (13 new).
Run: `uv run ruff check src tests` — no errors.

---

### Task 4: Document the new tools

**Files:** `README.md`

- [x] Added three bullets to the Food Tools section, bumped its count to 10 operations and the total tool count to 67.

---

## Self-Review Notes

- **Spec coverage:** mixin methods (Task 1), MCP tools (Task 2), tests for replace/dedupe/clear/add/skip-duplicate/remove/no-op/validate (Task 3), README bullets (Task 4) — all spec sections covered.
- **Consistency with prior on-hand feature:** reuses the same `FoodsMixin`/`foods_tools.py` fetch-merge pattern and the same `self.foods`-backed `FakeFetcher` store added for `set_food_on_hand`, requiring no new fake endpoint plumbing.
- **No placeholders:** every method is fully implemented, not stubbed.
