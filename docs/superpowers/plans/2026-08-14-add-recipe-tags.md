# Add Recipe Tags Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `add_recipe_tags` capability that appends one or more tags (by name, auto-creating unknown ones) to a recipe without disturbing its existing tags.

**Architecture:** A new `RecipeMixin.add_recipe_tags` method in `src/mealie/recipe.py` fetches the recipe, resolves each requested tag name against the recipe's current tags and Mealie's tag list (creating any that don't exist via the already-composed `TagsMixin`), and PATCHes the merged tag list. A thin `add_recipe_tags` MCP tool in `src/tools/recipe_tools.py` exposes it, following the existing `set_recipe_tags` wrapper pattern.

**Tech Stack:** Python 3.12, FastMCP (`mcp.server.fastmcp`), pytest (async), uv, ruff.

Spec: `docs/superpowers/specs/2026-08-14-add-recipe-tags-design.md`

---

### Task 1: Extend the test double for tag list/search + create endpoints

**Files:**
- Modify: `tests/conftest.py:42-45` (add `self.tags`), `tests/conftest.py:78-83` (add two new endpoint fakes)

The shared `FakeFetcher` already fakes `GET /api/organizers/tags/{id}` (single tag by id) but has no fake for the *list* endpoint (`GET /api/organizers/tags`, used with a `search` query param) or the *create* endpoint (`POST /api/organizers/tags`). Both are needed by `add_recipe_tags`, which looks up a tag by name before deciding whether to create it.

- [ ] **Step 1: Add an in-memory tag store to `FakeFetcher.__init__`**

In `tests/conftest.py`, the `__init__` currently reads:

```python
    def __init__(self):
        self.requests = []
        self.created_slug = "test-recipe"
        self.recipe = dict(BASE_RECIPE)
```

Change it to:

```python
    def __init__(self):
        self.requests = []
        self.created_slug = "test-recipe"
        self.recipe = dict(BASE_RECIPE)
        self.tags = []
```

`self.tags` is a list of `{"id", "name", "slug"}` dicts that tests can pre-seed (to simulate a tag that already exists in Mealie) and that the new fake `POST` handler appends to (to simulate tag creation).

- [ ] **Step 2: Fake the tag list/search and create endpoints**

Still in `tests/conftest.py`, the tag-by-id fake currently reads:

```python
        if method == "GET" and url.startswith("/api/organizers/tags/"):
            item_id = url.rsplit("/", 1)[-1]
            return {"id": item_id, "name": "Tag", "slug": "tag"}
```

Add two new blocks directly after it:

```python
        if method == "GET" and url.startswith("/api/organizers/tags/"):
            item_id = url.rsplit("/", 1)[-1]
            return {"id": item_id, "name": "Tag", "slug": "tag"}
        if method == "GET" and url == "/api/organizers/tags":
            search = (kwargs.get("params") or {}).get("search")
            items = self.tags
            if search:
                items = [t for t in items if search.lower() in t["name"].lower()]
            return {"items": items, "page": 1, "perPage": 50, "total": len(items)}
        if method == "POST" and url == "/api/organizers/tags":
            name = (kwargs.get("json") or {}).get("name")
            tag = {
                "id": f"tag-{len(self.tags) + 1}",
                "name": name,
                "slug": name.lower().replace(" ", "-"),
            }
            self.tags.append(tag)
            return tag
```

- [ ] **Step 3: Run the existing test suite to confirm nothing broke**

Run: `uv run pytest -q`
Expected: All existing tests still PASS (this step only added new, previously-unmatched branches; it didn't change any existing behavior).

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py
git commit -m "test: fake tag list/search and create endpoints in FakeFetcher"
```

---

### Task 2: Write failing tests for the `add_recipe_tags` tool

**Files:**
- Modify: `tests/test_recipe_tools.py` (append new tests at the end of the file)

These tests call the MCP tool `add_recipe_tags`, which doesn't exist yet — they must fail before Task 3/4 implement it.

- [ ] **Step 1: Append the new tests**

Add to the end of `tests/test_recipe_tools.py`:

```python
async def test_add_recipe_tags_creates_new_tag(invoke, fetcher):
    fetcher.recipe = {
        **fetcher.recipe,
        "tags": [{"id": "t1", "name": "Quick", "slug": "quick"}],
    }

    await invoke("add_recipe_tags", slug="test-recipe", tags=["Healthy"])

    create_call = fetcher.last("POST", "/api/organizers/tags")
    assert create_call["json"] == {"name": "Healthy"}

    body = fetcher.last("PATCH", "/api/recipes/test-recipe")["json"]
    assert body["tags"] == [
        {"id": "t1", "name": "Quick", "slug": "quick"},
        {"id": "tag-1", "name": "Healthy", "slug": "healthy"},
    ]


async def test_add_recipe_tags_reuses_existing_mealie_tag(invoke, fetcher):
    fetcher.tags = [{"id": "existing-1", "name": "Healthy", "slug": "healthy"}]
    fetcher.recipe = {**fetcher.recipe, "tags": []}

    await invoke("add_recipe_tags", slug="test-recipe", tags=["healthy"])

    assert fetcher.last("POST", "/api/organizers/tags") is None
    body = fetcher.last("PATCH", "/api/recipes/test-recipe")["json"]
    assert body["tags"] == [{"id": "existing-1", "name": "Healthy", "slug": "healthy"}]


async def test_add_recipe_tags_skips_tag_already_on_recipe(invoke, fetcher):
    fetcher.recipe = {
        **fetcher.recipe,
        "tags": [{"id": "t1", "name": "Quick", "slug": "quick"}],
    }

    await invoke("add_recipe_tags", slug="test-recipe", tags=["Quick", "Quick"])

    assert fetcher.last("POST", "/api/organizers/tags") is None
    body = fetcher.last("PATCH", "/api/recipes/test-recipe")["json"]
    assert body["tags"] == [{"id": "t1", "name": "Quick", "slug": "quick"}]


async def test_add_recipe_tags_validates_inputs(invoke, fetcher):
    from mcp.server.fastmcp.exceptions import ToolError

    with pytest.raises(ToolError):
        await invoke("add_recipe_tags", slug="", tags=["Quick"])

    with pytest.raises(ToolError):
        await invoke("add_recipe_tags", slug="test-recipe", tags=[])
```

This file has no top-level `import pytest` yet (unlike `test_organizer_tools.py`), so add it at the top of `tests/test_recipe_tools.py`, right after the module docstring:

```python
"""Tests for the recipe-authoring tools (structured ingredients, full create,
patch fields, concise output)."""

import pytest
```

- [ ] **Step 2: Run the new tests and confirm they fail**

Run: `uv run pytest tests/test_recipe_tools.py -k add_recipe_tags -v`
Expected: FAIL — `add_recipe_tags` is not a registered tool yet, so `invoke("add_recipe_tags", ...)` raises `ToolError: Unknown tool: add_recipe_tags` (from FastMCP's `ToolManager.call_tool`), which the validation test's `pytest.raises(ToolError)` will incorrectly catch — confirm by running the first three tests individually, which have no `pytest.raises` and must fail outright:

Run: `uv run pytest tests/test_recipe_tools.py::test_add_recipe_tags_creates_new_tag -v`
Expected: FAIL with `ToolError: Unknown tool: add_recipe_tags`

- [ ] **Step 3: Commit**

```bash
git add tests/test_recipe_tools.py
git commit -m "test: add failing tests for add_recipe_tags tool"
```

---

### Task 3: Implement the `add_recipe_tags` mixin method

**Files:**
- Modify: `src/mealie/recipe.py:179-194` (insert new method after `set_recipe_tags`)

- [ ] **Step 1: Add `add_recipe_tags` to `RecipeMixin`**

In `src/mealie/recipe.py`, `set_recipe_tags` currently ends and `set_recipe_categories_and_tags` begins like this:

```python
        logger.info({"message": "Setting recipe tags", "slug": slug, "tag_ids": tag_ids})
        tags = [self.get_tag(tid) for tid in tag_ids]
        return self._handle_request("PATCH", f"/api/recipes/{slug}", json={"tags": tags})

    def set_recipe_categories_and_tags(
```

Insert a new method between them:

```python
        logger.info({"message": "Setting recipe tags", "slug": slug, "tag_ids": tag_ids})
        tags = [self.get_tag(tid) for tid in tag_ids]
        return self._handle_request("PATCH", f"/api/recipes/{slug}", json={"tags": tags})

    def add_recipe_tags(self, slug: str, tag_names: List[str]) -> Dict[str, Any]:
        """Add one or more tags to a recipe without removing existing tags.

        Tag names are matched case-insensitively against the recipe's current
        tags and against Mealie's existing tags; a name with no match is
        created as a new tag.

        Args:
            slug: The slug identifier of the recipe
            tag_names: Tag names to add (created in Mealie if they don't exist)

        Returns:
            JSON response containing the updated recipe details
        """
        if not slug:
            raise ValueError("Recipe slug cannot be empty")
        if not tag_names:
            raise ValueError("Tag names cannot be empty")

        logger.info({"message": "Adding recipe tags", "slug": slug, "tag_names": tag_names})

        recipe = self.get_recipe(slug)
        merged_tags = list(recipe.get("tags", []))
        known_names = {(t.get("name") or "").lower() for t in merged_tags}

        for raw_name in tag_names:
            name = raw_name.strip()
            if not name or name.lower() in known_names:
                continue

            matches = self.get_tags(search=name).get("items", [])
            tag = next(
                (t for t in matches if (t.get("name") or "").lower() == name.lower()),
                None,
            )
            if tag is None:
                tag = self.create_tag(name)

            merged_tags.append(tag)
            known_names.add(name.lower())

        return self._handle_request(
            "PATCH", f"/api/recipes/{slug}", json={"tags": merged_tags}
        )

    def set_recipe_categories_and_tags(
```

This follows the same cross-mixin pattern `set_recipe_tags` already uses (calling `self.get_tag`, a `TagsMixin` method, from within `RecipeMixin`) — `self.get_tags` and `self.create_tag` are available the same way once composed onto `MealieFetcher`.

- [ ] **Step 2: Run the tests again**

Run: `uv run pytest tests/test_recipe_tools.py::test_add_recipe_tags_creates_new_tag -v`
Expected: Still FAILS, but now with `ToolError: Unknown tool: add_recipe_tags` unchanged — the mixin method exists but nothing calls it yet. This confirms the mixin change alone doesn't accidentally make the test pass for the wrong reason (e.g. a typo silently no-op-ing).

- [ ] **Step 3: Commit**

```bash
git add src/mealie/recipe.py
git commit -m "feat: add RecipeMixin.add_recipe_tags"
```

---

### Task 4: Implement the `add_recipe_tags` MCP tool

**Files:**
- Modify: `src/tools/recipe_tools.py:682-703` (insert new tool after `set_recipe_tags`)

- [ ] **Step 1: Add the `add_recipe_tags` tool**

In `src/tools/recipe_tools.py`, the `set_recipe_tags` tool currently ends and `update_recipe_categories_and_tags` begins like this:

```python
        try:
            logger.info({"message": "Setting recipe tags", "slug": slug, "tag_ids": tag_ids})
            return mealie.set_recipe_tags(slug, tag_ids)
        except Exception as e:
            error_msg = f"Error setting tags on recipe '{slug}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug({"message": "Error traceback", "traceback": traceback.format_exc()})
            raise ToolError(error_msg)

    @mcp.tool()
    def update_recipe_categories_and_tags(
```

Insert a new tool between them:

```python
        try:
            logger.info({"message": "Setting recipe tags", "slug": slug, "tag_ids": tag_ids})
            return mealie.set_recipe_tags(slug, tag_ids)
        except Exception as e:
            error_msg = f"Error setting tags on recipe '{slug}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug({"message": "Error traceback", "traceback": traceback.format_exc()})
            raise ToolError(error_msg)

    @mcp.tool()
    def add_recipe_tags(slug: str, tags: List[str]) -> Dict[str, Any]:
        """Add one or more tags to a recipe, keeping any tags it already has.

        Unlike set_recipe_tags (which replaces the whole tag list), this is
        additive: existing tags are preserved. Tag names are matched
        case-insensitively against the recipe's current tags and against
        Mealie's existing tags; any name with no match is created as a new
        tag automatically, so there's no need to call get_tags() first.

        Args:
            slug: The unique text identifier for the recipe.
            tags: Tag names to add, e.g. ["Quick", "Healthy"].

        Returns:
            Dict[str, Any]: The updated recipe details.
        """
        try:
            logger.info({"message": "Adding recipe tags", "slug": slug, "tags": tags})
            return mealie.add_recipe_tags(slug, tags)
        except Exception as e:
            error_msg = f"Error adding tags to recipe '{slug}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug({"message": "Error traceback", "traceback": traceback.format_exc()})
            raise ToolError(error_msg)

    @mcp.tool()
    def update_recipe_categories_and_tags(
```

No changes are needed in `src/tools/__init__.py` — `add_recipe_tags` is registered inside the existing `register_recipe_tools` function, which is already wired up.

- [ ] **Step 2: Run the new tests and confirm they pass**

Run: `uv run pytest tests/test_recipe_tools.py -k add_recipe_tags -v`
Expected: All 4 tests PASS.

- [ ] **Step 3: Run the full test suite and lint**

Run: `uv run pytest -q`
Expected: All tests PASS.

Run: `uv run ruff check src tests`
Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add src/tools/recipe_tools.py
git commit -m "feat: add add_recipe_tags MCP tool"
```

---

### Task 5: Document the new tool in the README

**Files:**
- Modify: `README.md:119-134` (add a bullet to the Recipe Tools list)

- [ ] **Step 1: Add the bullet**

In `README.md`, the Recipe Tools list currently reads:

```markdown
- `set_recipe_image_from_url` - Set image from URL
- `upload_recipe_image_file` - Upload image file
- `upload_recipe_asset_file` - Upload document/asset
- `delete_recipe` - Delete recipe
```

Change it to:

```markdown
- `set_recipe_image_from_url` - Set image from URL
- `upload_recipe_image_file` - Upload image file
- `upload_recipe_asset_file` - Upload document/asset
- `add_recipe_tags` - Add tags by name, keeping existing ones (auto-creates unknown names)
- `delete_recipe` - Delete recipe
```

(The "Recipe Tools (13 operations)" heading above this list is already out of sync with the actual tool count — `set_recipe_categories`, `set_recipe_tags`, and `update_recipe_categories_and_tags` are missing from it too. Fixing that count is out of scope for this change; leave the heading as-is.)

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: document add_recipe_tags in README"
```

---

## Self-Review Notes

- **Spec coverage:** Mixin method (Task 3), MCP tool (Task 4), test fixture support (Task 1), tests for create/reuse/skip/validate (Task 2), README bullet (Task 5) — all five spec sections have a corresponding task.
- **Type consistency:** `add_recipe_tags(self, slug: str, tag_names: List[str])` in the mixin is called as `mealie.add_recipe_tags(slug, tags)` from the tool wrapper — parameter name `tags` at the MCP layer (user-facing) maps positionally to `tag_names` in the mixin (internal), matching the existing convention where `set_recipe_tags(slug, tag_ids)` and the tool's `tag_ids` line up positionally, not by keyword.
- **No placeholders:** every step shows complete, exact code.
