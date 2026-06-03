"""Regression tests for the 2026-06-03 live E2E bug report (BUG-1/2/3)."""

import uuid

# --- BUG-1: update_* must fetch-merge so id/name stay in the PUT body -------


async def test_update_food_fetch_merges_and_keeps_id(invoke, fetcher):
    await invoke("update_food", food_id="food-1", description="new desc")
    put = fetcher.last("PUT", "/api/foods/food-1")["json"]
    assert put["id"] == "food-1"  # required by Mealie; was null before the fix
    assert put["name"] == "Existing"  # preserved (full-replace would null it)
    assert put["pluralName"] == "Existings"  # preserved
    assert put["description"] == "new desc"  # applied


async def test_update_tool_fetch_merges_and_keeps_id(invoke, fetcher):
    await invoke("update_tool", tool_id="k1", name="Topf")
    put = fetcher.last("PUT", "/api/organizers/tools/k1")["json"]
    assert put["id"] == "k1"
    assert put["name"] == "Topf"  # applied
    assert put["description"] == "old"  # preserved


# --- BUG-2: tags/tools need a slug; derive one when the caller omits it -----


async def test_create_recipe_full_fills_organizer_slug(invoke, fetcher):
    await invoke(
        "create_recipe_full",
        name="R",
        tags=[{"id": "t1", "name": "Vegetarisch"}],  # slug omitted -> derived
        tools=[{"id": "k1", "name": "Pfanne", "slug": "my-pfanne"}],  # slug kept
    )
    body = fetcher.last("PUT", "/api/recipes/")["json"]
    assert body["tags"][0] == {"id": "t1", "name": "Vegetarisch", "slug": "vegetarisch"}
    assert body["tools"][0]["slug"] == "my-pfanne"


async def test_patch_recipe_fills_organizer_slug_with_umlaut(invoke, fetcher):
    await invoke("patch_recipe", slug="r", tags=[{"id": "t1", "name": "Feta-Käse"}])
    body = fetcher.last("PATCH", "/api/recipes/")["json"]
    assert body["tags"][0]["slug"] == "feta-kase"  # ä transliterated, hyphenated


# --- BUG-3: non-UUID referenceId is coerced to a stable UUID, link intact ---


async def test_reference_id_coerced_and_link_preserved(invoke, fetcher):
    await invoke(
        "create_recipe",
        name="R",
        ingredients=[{"note": "2 eggs", "referenceId": "ing-1"}],
        instructions=[
            {"text": "Fry", "ingredientReferences": [{"referenceId": "ing-1"}]}
        ],
    )
    body = fetcher.last("PUT", "/api/recipes/")["json"]
    ing_ref = body["recipeIngredient"][0]["referenceId"]
    step_ref = body["recipeInstructions"][0]["ingredientReferences"][0]["referenceId"]
    assert uuid.UUID(ing_ref).version == 4  # Mealie requires UUID v4
    assert ing_ref == step_ref  # same source id -> same UUID, link preserved
    assert ing_ref != "ing-1"


async def test_reference_id_valid_uuid_passes_through(invoke, fetcher):
    valid = "a1000001-0000-4000-8000-000000000001"  # already a v4 UUID
    await invoke(
        "create_recipe",
        name="R",
        ingredients=[{"note": "x", "referenceId": valid}],
        instructions=["step"],
    )
    body = fetcher.last("PUT", "/api/recipes/")["json"]
    assert body["recipeIngredient"][0]["referenceId"] == valid
