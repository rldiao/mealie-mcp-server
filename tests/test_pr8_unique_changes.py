"""Regression coverage for the unique functionality retained from PR #8."""


async def test_update_mealplan_preserves_required_fields(invoke, fetcher):
    await invoke("update_mealplan", entry_id="meal-1", title="New title")
    body = fetcher.last("PUT", "/api/households/mealplans/meal-1")["json"]
    assert body["id"] == "meal-1"
    assert body["groupId"] == "group-1"
    assert body["userId"] == "user-1"
    assert body["date"] == "2026-07-12"
    assert body["title"] == "New title"


async def test_update_shopping_list_preserves_required_fields(invoke, fetcher):
    await invoke("update_shopping_list", list_id="list-1", name="Renamed")
    body = fetcher.last("PUT", "/api/households/shopping/lists/list-1")["json"]
    assert body == {
        "id": "list-1",
        "groupId": "group-1",
        "userId": "user-1",
        "name": "Renamed",
    }


async def test_set_and_clear_recipe_categories(invoke, fetcher):
    await invoke("set_recipe_categories", slug="recipe", category_ids=["cat-1"])
    body = fetcher.last("PATCH", "/api/recipes/recipe")["json"]
    assert body["recipeCategory"][0]["id"] == "cat-1"

    await invoke("set_recipe_categories", slug="recipe", category_ids=[])
    assert fetcher.last("PATCH", "/api/recipes/recipe")["json"] == {
        "recipeCategory": []
    }


async def test_set_and_clear_recipe_tags(invoke, fetcher):
    await invoke("set_recipe_tags", slug="recipe", tag_ids=["tag-1"])
    body = fetcher.last("PATCH", "/api/recipes/recipe")["json"]
    assert body["tags"][0]["id"] == "tag-1"

    await invoke("set_recipe_tags", slug="recipe", tag_ids=[])
    assert fetcher.last("PATCH", "/api/recipes/recipe")["json"] == {"tags": []}


async def test_update_categories_and_tags_in_one_patch(invoke, fetcher):
    await invoke(
        "update_recipe_categories_and_tags",
        slug="recipe",
        category_ids=["cat-1"],
        tag_ids=["tag-1"],
    )
    body = fetcher.last("PATCH", "/api/recipes/recipe")["json"]
    assert body["recipeCategory"][0]["id"] == "cat-1"
    assert body["tags"][0]["id"] == "tag-1"
