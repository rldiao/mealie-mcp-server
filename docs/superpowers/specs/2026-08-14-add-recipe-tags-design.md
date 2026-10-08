# Add Recipe Tags — Design

## Problem

The server can already *replace* a recipe's entire tag list (`set_recipe_tags`,
`update_recipe_categories_and_tags`), but there is no way to add a tag to a
recipe while preserving the tags it already has. Both existing tools also
require the caller to already know the tag's UUID (via `get_tags`), which adds
an extra round trip for the common case of "tag this recipe as X" where X may
not exist as a tag yet.

## Goal

Add a tool that appends one or more tags to a recipe by name:

- Existing tags on the recipe are preserved (additive, not a replacement).
- Tag names that don't yet exist in Mealie are created automatically.
- Tag names that already exist (in Mealie, or already on the recipe) are
  reused rather than duplicated.

## Non-goals

- Removing tags (covered by the existing `set_recipe_tags` with a smaller
  list, or an empty list to clear).
- Bulk-tagging multiple recipes in one call.

## Design

### 1. Mixin method — `RecipeMixin.add_recipe_tags` (`src/mealie/recipe.py`)

```python
def add_recipe_tags(self, slug: str, tag_names: List[str]) -> Dict[str, Any]
```

Behavior:

1. Validate `slug` is non-empty and `tag_names` is a non-empty list of
   non-empty strings.
2. Fetch the recipe via `self.get_recipe(slug)` to read its current `tags`
   list (list of `{id, name, slug, ...}` dicts).
3. Build a working list starting from the recipe's existing tags, and an
   index of existing tag names (lower-cased) for de-duplication — both
   against tags already on the recipe and against duplicates within the
   input list itself.
4. For each requested name, in order:
   - Skip it if its lower-cased form is already in the index (already
     tagged, or already handled earlier in this same call).
   - Otherwise, search Mealie's existing tags with
     `self.get_tags(search=name)` and look for an item whose `name` matches
     case-insensitively. If found, reuse that tag object.
   - If no match is found, create it with `self.create_tag(name)` and use
     the returned tag object.
   - Append the resolved tag object to the working list and add its name to
     the de-duplication index.
5. PATCH the recipe with the merged tag list:
   `self._handle_request("PATCH", f"/api/recipes/{slug}", json={"tags": merged})`.
6. Return the response (the updated recipe).

This mirrors the existing cross-mixin pattern already used by
`set_recipe_tags`, which calls `self.get_tag(tid)` from `TagsMixin` even
though the method lives in `RecipeMixin` — both mixins are composed onto
`MealieFetcher`.

### 2. MCP tool wrapper — `add_recipe_tags` (`src/tools/recipe_tools.py`)

```python
@mcp.tool()
def add_recipe_tags(slug: str, tags: List[str]) -> Dict[str, Any]
```

Thin wrapper following the same try/except/`ToolError` pattern as the other
tools in this file (e.g. `set_recipe_tags`). Docstring calls out the two
things that distinguish it from `set_recipe_tags`:

- It is additive — existing tags are kept.
- Tag names that don't exist yet are created automatically; no need to call
  `get_tags`/`create_tag` first.

No new Pydantic model is needed: the tool takes plain tag-name strings, not
`OrganizerRef` objects, since avoiding the "look up the ID first" step is the
point of this tool.

### 3. Test fixture support (`tests/conftest.py`)

`FakeFetcher` currently has no handling for the tag *list* endpoint
(`GET /api/organizers/tags`, used with a `search` param) or tag *create*
endpoint (`POST /api/organizers/tags`) — only single-tag-by-id GET is faked.
Add:

- `self.tags: List[Dict[str, Any]] = []` in `__init__`, acting as a tiny
  in-memory tag store tests can pre-seed.
- `GET /api/organizers/tags` → filters `self.tags` by the `search` param
  (case-insensitive substring on `name`) and returns a paginated-shaped
  response (`items`, `page`, `perPage`, `total`).
- `POST /api/organizers/tags` → creates a new tag dict from the request
  body, appends it to `self.tags`, and returns it.

### 4. Tests (`tests/test_recipe_tools.py`)

- Adding a brand-new tag name creates it (`POST /api/organizers/tags` is
  called) and PATCHes the recipe with the new tag included alongside any
  pre-existing tags.
- Adding a tag name that already exists in Mealie (pre-seeded in
  `fetcher.tags`) reuses it — no `POST /api/organizers/tags` call — and the
  reused tag's id appears in the PATCH body.
- Adding a tag name already present on the recipe is a no-op for that tag:
  no create call, and it isn't duplicated in the PATCH body.
- Empty `slug` or empty `tags` list raises a `ToolError`.

### 5. Docs (`README.md`)

Add one bullet for `add_recipe_tags` to the "Recipe Tools" list, next to
`set_recipe_tags`.

## Open questions

None — scope confirmed with the user: name-based lookup with auto-create,
accepting a list of tags per call.
