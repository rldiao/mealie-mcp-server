"""Positive / happy-path tests: tools succeed on valid input and return
sensible results (complements the request-shape and regression tests)."""

import pytest


@pytest.mark.parametrize("tool", ["get_foods", "get_units", "get_tools"])
async def test_lookups_return_items(invoke, tool):
    out = await invoke(tool, search="x")
    assert isinstance(out, dict)
    assert "items" in out and isinstance(out["items"], list)


async def test_food_crud_roundtrip(invoke):
    created = await invoke("create_food", name="Reis", plural_name="Reissorten")
    assert created["id"]
    got = await invoke("get_food", food_id="f1")
    assert got["id"] == "f1"
    updated = await invoke("update_food", food_id="f1", description="grain")
    assert updated["id"] == "f1"
    assert updated["description"] == "grain"
    assert updated["name"] == "Existing"  # untouched field preserved
    deleted = await invoke("delete_food", food_id="f1")
    assert deleted.get("success") is True


async def test_unit_and_tool_create_return_id(invoke):
    unit = await invoke("create_unit", name="Gramm", abbreviation="g")
    assert unit["id"] and unit["name"] == "Gramm"
    tool = await invoke("create_tool", name="Kochtopf")
    assert tool["id"] and tool["name"] == "Kochtopf"
    assert (await invoke("delete_tool", tool_id="k1")).get("success") is True


async def test_create_recipe_returns_populated_recipe(invoke):
    out = await invoke(
        "create_recipe",
        name="Happy",
        ingredients=["200 g rice"],
        instructions=["Boil it."],
    )
    assert out["recipeIngredient"][0]["note"] == "200 g rice"
    assert out["recipeInstructions"][0]["text"] == "Boil it."


async def test_create_recipe_full_returns_full_recipe(invoke):
    out = await invoke(
        "create_recipe_full",
        name="Full Happy",
        description="a dish",
        org_url="https://example.com/r",
        total_time="30 min",
        recipe_yield="2 Portionen",
        servings=2,
        ingredients=["1 onion"],
        instructions=["Chop."],
        tags=[{"id": "t1", "name": "Quick"}],
        tools=[{"id": "k1", "name": "Pfanne"}],
    )
    assert out["name"] == "Full Happy"
    assert out["orgURL"] == "https://example.com/r"
    assert out["totalTime"] == "30 min"
    assert out["recipeServings"] == 2
    assert out["tags"][0]["slug"] == "quick"
    assert out["tools"][0]["name"] == "Pfanne"


async def test_patch_recipe_returns_updated_fields(invoke):
    out = await invoke("patch_recipe", slug="r", servings=4, prep_time="10 min")
    assert out["recipeServings"] == 4
    assert out["prepTime"] == "10 min"


async def test_get_recipe_concise_returns_summary(invoke, fetcher):
    fetcher.recipe = {**fetcher.recipe, "totalTime": "35 min"}
    out = await invoke("get_recipe_concise", slug="test-recipe")
    assert out["name"]
    assert out["slug"]
    assert out["totalTime"] == "35 min"
