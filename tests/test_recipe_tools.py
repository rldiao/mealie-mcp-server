"""Tests for the recipe-authoring tools (structured ingredients, full create,
patch fields, concise output)."""

import pytest


async def test_create_recipe_accepts_flat_and_structured(invoke, fetcher):
    await invoke(
        "create_recipe",
        name="Mixed",
        ingredients=[
            "200 g basmati rice",
            {
                "quantity": 2,
                "food": {"id": "f1", "name": "egg"},
                "note": "large",
                "referenceId": "a1000001-0000-4000-8000-000000000001",
            },
        ],
        instructions=[
            "Boil the rice.",
            {
                "text": "Fry the eggs.",
                "title": "Eggs",
                "ingredientReferences": [
                    {"referenceId": "a1000001-0000-4000-8000-000000000001"}
                ],
            },
        ],
    )
    body = fetcher.last("PUT", "/api/recipes/")["json"]
    ings = body["recipeIngredient"]
    steps = body["recipeInstructions"]

    assert ings[0]["note"] == "200 g basmati rice"
    assert ings[1]["quantity"] == 2
    assert ings[1]["food"] == {
        "id": "f1",
        "name": "egg",
        "description": "",
        "aliases": [],
        "householdsWithIngredientFood": [],
    }
    # already a valid UUID -> passes through unchanged
    assert ings[1]["referenceId"] == "a1000001-0000-4000-8000-000000000001"
    assert steps[0]["ingredientReferences"] == []
    assert steps[1]["title"] == "Eggs"
    assert steps[1]["ingredientReferences"] == [
        {"referenceId": "a1000001-0000-4000-8000-000000000001"}
    ]


async def test_create_recipe_full_sets_metadata_tags_tools_and_image(invoke, fetcher):
    await invoke(
        "create_recipe_full",
        name="Full",
        description="A dish",
        org_url="https://example.com/r",
        total_time="30 min",
        prep_time="10 min",
        recipe_yield="4 Portionen",
        servings=2,
        image_url="https://example.com/img.jpg",
        ingredients=["1 onion"],
        instructions=["Chop the onion."],
        tags=[{"id": "t1", "name": "Quick"}],
        tools=[{"id": "k1", "name": "Pfanne"}],
    )
    body = fetcher.last("PUT", "/api/recipes/")["json"]
    assert body["description"] == "A dish"
    assert body["orgURL"] == "https://example.com/r"
    assert body["totalTime"] == "30 min"
    assert body["recipeServings"] == 2
    assert body["recipeYield"] == "4 Portionen"
    assert body["recipeIngredient"][0]["note"] == "1 onion"
    # slug derived from the name (Mealie requires it on organizer refs)
    assert body["tags"] == [{"id": "t1", "name": "Quick", "slug": "quick"}]
    assert body["tools"][0]["id"] == "k1"
    assert body["tools"][0]["slug"] == "pfanne"
    # image is scraped server-side after the recipe content is written
    assert fetcher.last("POST", "/image") is not None


async def test_patch_recipe_maps_all_fields(invoke, fetcher):
    await invoke(
        "patch_recipe",
        slug="test-recipe",
        total_time="35 min",
        prep_time="10 min",
        cook_time="25 min",
        perform_time="20 min",
        servings=4,
        org_url="https://example.com/r",
        recipe_yield="4 Portionen",
        tags=[{"id": "t1", "name": "Quick"}],
        tools=[{"id": "k1", "name": "Pfanne"}],
    )
    body = fetcher.last("PATCH", "/api/recipes/")["json"]
    assert body == {
        "recipeYield": "4 Portionen",
        "recipeServings": 4,
        "totalTime": "35 min",
        "prepTime": "10 min",
        "cookTime": "25 min",
        "performTime": "20 min",
        "orgURL": "https://example.com/r",
        "tags": [{"id": "t1", "name": "Quick", "slug": "quick"}],
        "tools": [{"id": "k1", "name": "Pfanne", "slug": "pfanne"}],
    }


async def test_get_recipe_concise_includes_orgurl_tags_tools(invoke, fetcher):
    fetcher.recipe = {
        **fetcher.recipe,
        "orgURL": "https://example.com/r",
        "tags": [{"id": "t1", "name": "Quick", "slug": "quick"}],
        "tools": [
            {"id": "k1", "name": "Pfanne", "slug": "pfanne", "householdsWithTool": []}
        ],
    }
    out = await invoke("get_recipe_concise", slug="test-recipe")
    assert out["orgURL"] == "https://example.com/r"
    assert out["tags"] == [{"id": "t1", "name": "Quick", "slug": "quick"}]
    assert out["tools"][0]["name"] == "Pfanne"


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


COS_REF = "a1000001-0000-4000-8000-000000000001"
ROMAINE_ID = "a1000001-0000-4000-8000-000000000002"
EXISTING_SUBS = [
    {
        "substituteFoodId": ROMAINE_ID,
        "note": None,
        "substituteFood": {"id": ROMAINE_ID, "name": "Romaine"},
    }
]


async def test_create_recipe_sends_ingredient_substitutions(invoke, fetcher):
    await invoke(
        "create_recipe",
        name="Salad",
        ingredients=[
            {
                "note": "Cos lettuce",
                "substitutions": [
                    {"substituteFoodId": ROMAINE_ID},
                    {"note": "any crisp lettuce"},
                ],
            }
        ],
        instructions=["Toss."],
    )
    ing = fetcher.last("PUT", "/api/recipes/")["json"]["recipeIngredient"][0]
    assert ing["substitutions"] == [
        {"substituteFoodId": ROMAINE_ID},
        {"note": "any crisp lettuce"},
    ]


async def test_create_recipe_rejects_empty_substitution(invoke, fetcher):
    from mcp.server.fastmcp.exceptions import ToolError

    with pytest.raises(ToolError):
        await invoke(
            "create_recipe",
            name="Salad",
            ingredients=[{"note": "Cos", "substitutions": [{}]}],
            instructions=["Toss."],
        )
    assert fetcher.last("PUT", "/api/recipes/") is None


async def test_update_recipe_keeps_existing_links_when_omitted(invoke, fetcher):
    fetcher.recipe = {
        **fetcher.recipe,
        "recipeIngredient": [
            {
                "note": "Cos",
                "referenceId": COS_REF,
                "substitutions": EXISTING_SUBS,
                "referencedRecipe": {"id": "r1", "slug": "dressing"},
            }
        ],
    }

    await invoke(
        "update_recipe",
        slug="test-recipe",
        ingredients=[{"note": "Cos lettuce", "referenceId": COS_REF}, "1 tsp salt"],
        instructions=["Toss."],
    )

    ings = fetcher.last("PUT", "/api/recipes/test-recipe")["json"]["recipeIngredient"]
    assert ings[0]["note"] == "Cos lettuce"
    assert ings[0]["substitutions"] == EXISTING_SUBS
    assert ings[0]["referencedRecipe"] == {"id": "r1", "slug": "dressing"}
    assert "substitutions" not in ings[1]


async def test_update_recipe_explicit_substitutions_replace_or_clear(invoke, fetcher):
    fetcher.recipe = {
        **fetcher.recipe,
        "recipeIngredient": [
            {"note": "Cos", "referenceId": COS_REF, "substitutions": EXISTING_SUBS},
            {
                "note": "buttermilk",
                "referenceId": "a1000001-0000-4000-8000-000000000003",
                "substitutions": [{"note": "kefir"}],
            },
        ],
    }

    await invoke(
        "update_recipe",
        slug="test-recipe",
        ingredients=[
            {"note": "Cos", "referenceId": COS_REF, "substitutions": []},
            {
                "note": "buttermilk",
                "referenceId": "a1000001-0000-4000-8000-000000000003",
                "substitutions": [{"note": "plain yoghurt, thinned"}],
            },
        ],
        instructions=["Toss."],
    )

    ings = fetcher.last("PUT", "/api/recipes/test-recipe")["json"]["recipeIngredient"]
    assert ings[0]["substitutions"] == []
    assert ings[1]["substitutions"] == [{"note": "plain yoghurt, thinned"}]


async def test_update_recipe_surfaces_client_failure(invoke, fetcher):
    from mcp.server.fastmcp.exceptions import ToolError

    def boom(*args, **kwargs):
        raise RuntimeError("mealie down")

    fetcher.update_recipe = boom
    with pytest.raises(ToolError):
        await invoke(
            "update_recipe",
            slug="test-recipe",
            ingredients=[{"note": "Cos", "substitutions": [{"note": "Romaine"}]}],
            instructions=["Toss."],
        )


async def test_patch_recipe_sets_notes(invoke, fetcher):
    await invoke(
        "patch_recipe",
        slug="test-recipe",
        notes=[
            {"title": "Make ahead", "text": "Dressing keeps 3 days."},
            {"text": "Use Romaine if Cos is unavailable."},
        ],
    )
    call = fetcher.last("PATCH", "/api/recipes/")
    assert call["url"] == "/api/recipes/test-recipe"
    assert call["json"] == {
        "notes": [
            {"title": "Make ahead", "text": "Dressing keeps 3 days."},
            {"title": "", "text": "Use Romaine if Cos is unavailable."},
        ]
    }


async def test_patch_recipe_empty_notes_clears_them(invoke, fetcher):
    await invoke("patch_recipe", slug="test-recipe", notes=[])
    assert fetcher.last("PATCH", "/api/recipes/")["json"] == {"notes": []}


async def test_patch_recipe_rejects_empty_note(invoke, fetcher):
    from mcp.server.fastmcp.exceptions import ToolError

    with pytest.raises(ToolError):
        await invoke(
            "patch_recipe", slug="test-recipe", notes=[{"title": " ", "text": ""}]
        )
    assert fetcher.last("PATCH", "/api/recipes/") is None


async def test_patch_recipe_notes_surfaces_client_failure(invoke, fetcher):
    from mcp.server.fastmcp.exceptions import ToolError

    def boom(*args, **kwargs):
        raise RuntimeError("mealie down")

    fetcher.patch_recipe = boom
    with pytest.raises(ToolError):
        await invoke("patch_recipe", slug="test-recipe", notes=[{"text": "x"}])


async def test_create_recipe_full_sets_notes(invoke, fetcher):
    await invoke(
        "create_recipe_full",
        name="Salad",
        notes=[{"title": "Serving", "text": "Chill the bowl first."}],
    )
    body = fetcher.last("PUT", "/api/recipes/")["json"]
    assert body["notes"] == [{"title": "Serving", "text": "Chill the bowl first."}]


async def test_patch_recipe_merges_nutrition_and_shows_it(invoke, fetcher):
    fetcher.recipe = {
        **fetcher.recipe,
        "nutrition": {"calories": "400", "fatContent": "20", "sodiumContent": "300"},
        "settings": {"public": True, "showNutrition": False},
    }

    await invoke(
        "patch_recipe",
        slug="test-recipe",
        nutrition={
            "calories": 450,
            "proteinContent": 32.5,
            "carbohydrateContent": "40",
            "sodiumContent": None,
        },
    )

    call = fetcher.last("PATCH", "/api/recipes/")
    assert call["url"] == "/api/recipes/test-recipe"
    assert call["json"] == {
        "nutrition": {
            "calories": "450",
            "fatContent": "20",
            "sodiumContent": None,
            "proteinContent": "32.5",
            "carbohydrateContent": "40",
        },
        "settings": {"public": True, "showNutrition": True},
    }


async def test_patch_recipe_rejects_empty_or_unknown_nutrition(invoke, fetcher):
    from mcp.server.fastmcp.exceptions import ToolError

    with pytest.raises(ToolError):
        await invoke("patch_recipe", slug="test-recipe", nutrition={})
    with pytest.raises(ToolError):
        await invoke("patch_recipe", slug="test-recipe", nutrition={"protein": 30})
    assert fetcher.last("PATCH", "/api/recipes/") is None


async def test_patch_recipe_nutrition_surfaces_client_failure(invoke, fetcher):
    from mcp.server.fastmcp.exceptions import ToolError

    def boom(*args, **kwargs):
        raise RuntimeError("mealie down")

    fetcher.patch_recipe = boom
    with pytest.raises(ToolError):
        await invoke("patch_recipe", slug="test-recipe", nutrition={"calories": 1})


async def test_create_recipe_full_sets_nutrition(invoke, fetcher):
    await invoke(
        "create_recipe_full",
        name="Salad",
        nutrition={"calories": 320, "proteinContent": 12, "fatContent": 18.5},
    )
    body = fetcher.last("PUT", "/api/recipes/")["json"]
    assert body["nutrition"] == {
        "calories": "320",
        "proteinContent": "12",
        "fatContent": "18.5",
    }
    assert body["settings"]["showNutrition"] is True
