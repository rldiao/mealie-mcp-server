"""Tests for the recipe-authoring tools (structured ingredients, full create,
patch fields, concise output, image and asset uploads)."""

import json
import logging
import uuid
from copy import deepcopy

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from mealie.client import MealieApiError
from tools.recipe_tools import _compose_recipe


async def test_recipe_creation_tool_schema_is_consolidated(server):
    mcp, _ = server
    tools = await mcp.list_tools()
    names = [tool.name for tool in tools]
    assert names.count("create_recipe") == 1
    assert "create_recipe_full" not in names
    schema = next(tool.inputSchema for tool in tools if tool.name == "create_recipe")
    assert schema["required"] == ["name"]
    assert set(schema["properties"]) == {
        "name", "description", "org_url", "total_time", "prep_time", "cook_time",
        "perform_time", "recipe_yield", "servings", "image_url", "ingredients",
        "instructions", "tags", "tools", "notes", "nutrition", "settings",
    }


async def test_create_recipe_with_name_only(invoke, fetcher):
    result = await invoke("create_recipe", name="Minimal")
    assert result["name"] == "Minimal"
    assert result["slug"] == fetcher.created_slug
    assert fetcher.requests[0]["json"] == {"name": "Minimal"}
    assert [(r["method"], r["url"]) for r in fetcher.requests] == [
        ("POST", "/api/recipes"),
        ("GET", "/api/recipes/test-recipe"),
        ("PUT", "/api/recipes/test-recipe"),
    ]


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


async def test_create_recipe_forwards_instruction_summary(invoke, fetcher):
    await invoke(
        "create_recipe",
        name="Summaries",
        ingredients=["200 g basmati rice"],
        instructions=[
            {"text": "Rinse the rice.", "summary": "Prep"},
            {"text": "Boil it.", "summary": "Cook", "title": "On the stove"},
        ],
    )
    steps = fetcher.last("PUT", "/api/recipes/")["json"]["recipeInstructions"]

    assert steps[0]["summary"] == "Prep"
    # summary travels on its own: an omitted title is left out of the payload
    assert "title" not in steps[0]
    assert steps[1]["summary"] == "Cook"
    assert steps[1]["title"] == "On the stove"


async def test_create_recipe_sets_metadata_tags_tools_and_image(invoke, fetcher):
    await invoke(
        "create_recipe",
        name="Full",
        description="A dish",
        org_url="https://example.com/r",
        total_time="30 min",
        prep_time="10 min",
        cook_time="20 min",
        perform_time="15 min",
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
    assert body["prepTime"] == "10 min"
    assert body["cookTime"] == "20 min"
    assert body["performTime"] == "15 min"
    assert body["recipeServings"] == 2
    assert body["recipeYield"] == "4 Portionen"
    assert body["recipeIngredient"][0]["note"] == "1 onion"
    # slug derived from the name (Mealie requires it on organizer refs)
    assert body["tags"] == [{"id": "t1", "name": "Quick", "slug": "quick"}]
    assert body["tools"][0]["id"] == "k1"
    assert body["tools"][0]["slug"] == "pfanne"
    # image is scraped server-side after the recipe content is written
    assert fetcher.last("POST", "/image") is not None


async def test_update_recipe_maps_all_fields(invoke, fetcher):
    await invoke(
        "update_recipe",
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


async def test_create_recipe_sets_nutrition(invoke, fetcher):
    await invoke(
        "create_recipe",
        name="Nutritious",
        nutrition={"calories": "450", "proteinContent": 20, "sodiumContent": "310"},
    )
    body = fetcher.last("PUT", "/api/recipes/")["json"]
    # numbers are coerced to the strings Mealie stores; unset keys are omitted
    assert body["nutrition"] == {
        "calories": "450",
        "proteinContent": "20",
        "sodiumContent": "310",
    }


async def test_create_recipe_without_nutrition_sends_empty_object(invoke, fetcher):
    await invoke("create_recipe", name="Plain", ingredients=["1 onion"])
    body = fetcher.last("PUT", "/api/recipes/")["json"]
    assert body["nutrition"] == {}


async def test_update_recipe_sets_nutrition(invoke, fetcher):
    await invoke(
        "update_recipe",
        slug="test-recipe",
        nutrition={"calories": "450", "fatContent": "12"},
    )
    body = fetcher.last("PATCH", "/api/recipes/")["json"]
    # only the given values change and the nutrition card is switched on
    assert body == {
        "nutrition": {"calories": "450", "fatContent": "12"},
        "settings": {**fetcher.recipe["settings"], "showNutrition": True},
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
    out = await invoke("get_recipe", slug="test-recipe", concise=True)
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


async def test_update_recipe_sets_notes(invoke, fetcher):
    await invoke(
        "update_recipe",
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


async def test_update_recipe_empty_notes_clears_them(invoke, fetcher):
    await invoke("update_recipe", slug="test-recipe", notes=[])
    assert fetcher.last("PATCH", "/api/recipes/")["json"] == {"notes": []}


async def test_update_recipe_rejects_empty_note(invoke, fetcher):
    from mcp.server.fastmcp.exceptions import ToolError

    with pytest.raises(ToolError):
        await invoke(
            "update_recipe", slug="test-recipe", notes=[{"title": " ", "text": ""}]
        )
    assert fetcher.last("PATCH", "/api/recipes/") is None


async def test_update_recipe_notes_surfaces_client_failure(invoke, fetcher):
    from mcp.server.fastmcp.exceptions import ToolError

    def boom(*args, **kwargs):
        raise RuntimeError("mealie down")

    fetcher.patch_recipe = boom
    with pytest.raises(ToolError):
        await invoke("update_recipe", slug="test-recipe", notes=[{"text": "x"}])


async def test_create_recipe_sets_notes(invoke, fetcher):
    await invoke(
        "create_recipe",
        name="Salad",
        notes=[{"title": "Serving", "text": "Chill the bowl first."}],
    )
    body = fetcher.last("PUT", "/api/recipes/")["json"]
    assert body["notes"] == [{"title": "Serving", "text": "Chill the bowl first."}]


async def test_update_recipe_merges_nutrition_and_shows_it(invoke, fetcher):
    fetcher.recipe = {
        **fetcher.recipe,
        "nutrition": {"calories": "400", "fatContent": "20", "sodiumContent": "300"},
        "settings": {"public": True, "showNutrition": False},
    }

    await invoke(
        "update_recipe",
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


async def test_update_recipe_rejects_empty_or_unknown_nutrition(invoke, fetcher):
    from mcp.server.fastmcp.exceptions import ToolError

    with pytest.raises(ToolError):
        await invoke("update_recipe", slug="test-recipe", nutrition={})
    with pytest.raises(ToolError):
        await invoke("update_recipe", slug="test-recipe", nutrition={"protein": 30})
    assert fetcher.last("PATCH", "/api/recipes/") is None


async def test_update_recipe_nutrition_surfaces_client_failure(invoke, fetcher):
    from mcp.server.fastmcp.exceptions import ToolError

    def boom(*args, **kwargs):
        raise RuntimeError("mealie down")

    fetcher.patch_recipe = boom
    with pytest.raises(ToolError):
        await invoke("update_recipe", slug="test-recipe", nutrition={"calories": 1})


async def test_create_recipe_nutrition_turns_on_display(invoke, fetcher):
    await invoke(
        "create_recipe",
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


@pytest.mark.parametrize("arguments", [{}, {"concise": False}])
async def test_get_recipe_preserves_full_response(invoke, fetcher, arguments):
    fetcher.recipe["futureField"] = {"nested": [1, None]}
    fetcher.recipe["recipeInstructions"] = [{"text": "Cook."}]
    result = await invoke("get_recipe", slug="test-recipe", **arguments)
    assert result == fetcher.recipe
    assert [(r["method"], r["url"]) for r in fetcher.requests] == [
        ("GET", "/api/recipes/test-recipe")
    ]


@pytest.mark.parametrize("concise", [False, True])
async def test_get_recipe_surfaces_failures(invoke, fetcher, concise):
    fetcher.fail_on("/api/recipes/test-recipe", 500)
    with pytest.raises(ToolError, match="Error fetching recipe"):
        await invoke("get_recipe", slug="test-recipe", concise=concise)


@pytest.mark.parametrize(
    "arguments,changed,unchanged",
    [
        ({"ingredients": ["2 onions"]}, "recipeIngredient", "recipeInstructions"),
        ({"instructions": ["Chop."]}, "recipeInstructions", "recipeIngredient"),
        ({"ingredients": []}, "recipeIngredient", "recipeInstructions"),
        ({"instructions": []}, "recipeInstructions", "recipeIngredient"),
    ],
)
async def test_update_recipe_combines_content_and_metadata(
    invoke, fetcher, arguments, changed, unchanged
):
    fetcher.recipe["recipeIngredient"] = [{"note": "Original"}]
    fetcher.recipe["recipeInstructions"] = [{"text": "Original"}]
    fetcher.recipe["nutrition"] = {"calories": "100", "proteinContent": "20"}
    original = deepcopy(fetcher.recipe)
    result = await invoke(
        "update_recipe",
        slug="test-recipe",
        name="Updated",
        description="New description",
        nutrition={"calories": "200"},
        settings={"showAssets": False},
        **arguments,
    )
    assert result["name"] == "Updated"
    assert result["description"] == "New description"
    assert result[changed] != original[changed]
    assert result[unchanged] == original[unchanged]
    if not next(iter(arguments.values())):
        assert result[changed] == []
    # nutrition merges per field; supplying it also switches the card on
    assert result["nutrition"] == {"calories": "200", "proteinContent": "20"}
    assert result["settings"] == {
        **original["settings"], "showAssets": False, "showNutrition": True,
    }
    assert [r["method"] for r in fetcher.requests] == ["GET", "PUT"]


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"ingredients": None, "instructions": None, "description": None},
        {"ingredients": ["2 onions"], "settings": {"showAssets": "invalid"}},
    ],
)
async def test_update_recipe_validates_before_requests(invoke, fetcher, arguments):
    with pytest.raises(ToolError):
        await invoke("update_recipe", slug="test-recipe", **arguments)
    assert fetcher.requests == []


@pytest.mark.parametrize("method", ["GET", "PUT", "PATCH"])
async def test_update_recipe_propagates_failure_without_fallback(
    invoke, fetcher, monkeypatch, method
):
    original_request = fetcher._handle_request

    def fail_method(request_method, url, **kwargs):
        result = original_request(request_method, url, **kwargs)
        if request_method == method:
            raise MealieApiError(500, "Update failed")
        return result

    monkeypatch.setattr(fetcher, "_handle_request", fail_method)
    arguments = {"description": "Updated"} if method == "PATCH" else {"ingredients": []}
    with pytest.raises(ToolError, match="Error updating recipe"):
        await invoke("update_recipe", slug="test-recipe", **arguments)
    assert [r["method"] for r in fetcher.requests] == (
        ["GET", "PUT"] if method == "PUT" else [method]
    )


@pytest.mark.parametrize(
    "file_name,explicit_extension,expected",
    [
        ("photo.jpg", None, "jpg"),
        ("photo.JPEG", None, "jpeg"),
        ("photo with spaces.png", None, "png"),
        ("archive.tar.webp", None, "webp"),
        ("photo.jpg", "png", "png"),
        # a leading dot is accepted and stripped, like Mealie itself does
        ("photo.jpg", ".png", "png"),
    ],
)
async def test_upload_recipe_image_sends_extension_form_field(
    invoke, fetcher, tmp_path, file_name, explicit_extension, expected
):
    """Mealie's PUT /recipes/{slug}/image requires a separate `extension` form
    field; omitting it returns 422 Field required."""
    path = tmp_path / file_name
    path.write_bytes(b"image-bytes")

    kwargs = {} if explicit_extension is None else {"extension": explicit_extension}
    await invoke(
        "upload_recipe_image_file", slug="test-recipe", image_path=str(path), **kwargs
    )

    req = fetcher.last("PUT", "/api/recipes/test-recipe/image")
    assert req["data"] == {"extension": expected}
    assert req["files"]["image"] == (file_name, b"image-bytes")
    assert req["json"] is None


async def test_upload_recipe_image_rejects_missing_file(invoke, fetcher, tmp_path):
    with pytest.raises(ToolError):
        await invoke(
            "upload_recipe_image_file",
            slug="test-recipe",
            image_path=str(tmp_path / "nope.jpg"),
        )
    assert fetcher.last("PUT", "/image") is None


async def test_upload_recipe_image_rejects_file_without_extension(
    invoke, fetcher, tmp_path
):
    path = tmp_path / "photo"
    path.write_bytes(b"image-bytes")

    with pytest.raises(ToolError):
        await invoke(
            "upload_recipe_image_file", slug="test-recipe", image_path=str(path)
        )
    assert fetcher.last("PUT", "/image") is None


async def test_upload_recipe_asset_sends_name_icon_and_extension(
    invoke, fetcher, tmp_path
):
    """POST /recipes/{slug}/assets requires name, icon and extension form fields."""
    path = tmp_path / "nutrition notes.pdf"
    path.write_bytes(b"asset-bytes")

    out = await invoke(
        "upload_recipe_asset_file", slug="test-recipe", asset_path=str(path)
    )

    req = fetcher.last("POST", "/api/recipes/test-recipe/assets")
    assert req["data"] == {
        "name": "nutrition notes",
        "icon": "mdi-file",
        "extension": "pdf",
    }
    assert req["files"]["file"] == ("nutrition notes.pdf", b"asset-bytes")
    assert out["fileName"] == "nutrition notes.pdf"


async def test_upload_recipe_asset_honors_explicit_fields(invoke, fetcher, tmp_path):
    path = tmp_path / "scan.pdf"
    path.write_bytes(b"asset-bytes")

    await invoke(
        "upload_recipe_asset_file",
        slug="test-recipe",
        asset_path=str(path),
        name="Original scan",
        icon="mdi-file-pdf-box",
        extension="PDF",
    )

    req = fetcher.last("POST", "/assets")
    assert req["data"] == {
        "name": "Original scan",
        "icon": "mdi-file-pdf-box",
        "extension": "pdf",
    }


async def test_upload_recipe_asset_rejects_missing_file(invoke, fetcher, tmp_path):
    with pytest.raises(ToolError):
        await invoke(
            "upload_recipe_asset_file",
            slug="test-recipe",
            asset_path=str(tmp_path / "nope.pdf"),
        )
    assert fetcher.last("POST", "/assets") is None


async def test_update_recipe_merges_settings_onto_current(invoke, fetcher):
    await invoke("update_recipe", slug="test-recipe", settings={"showAssets": False})

    body = fetcher.last("PATCH", "/api/recipes/")["json"]
    # Mealie drops toggles omitted from a settings PATCH, so the tool reads the
    # current object and sends it whole -- locked must survive untouched.
    assert body["settings"] == {
        "public": False,
        "showNutrition": True,
        "showAssets": False,
        "landscapeView": False,
        "disableComments": False,
        "locked": True,
    }


async def test_update_recipe_settings_reads_current_first(invoke, fetcher):
    await invoke("update_recipe", slug="test-recipe", settings={"public": True})

    # the merge needs the existing settings, so a GET precedes the PATCH
    methods = [r["method"] for r in fetcher.requests]
    assert methods == ["GET", "PATCH"]


async def test_update_recipe_without_settings_issues_no_extra_get(invoke, fetcher):
    await invoke("update_recipe", slug="test-recipe", description="Just a description")

    assert [r["method"] for r in fetcher.requests] == ["PATCH"]
    assert "settings" not in fetcher.last("PATCH", "/api/recipes/")["json"]


async def test_create_recipe_merges_settings_onto_seeded(invoke, fetcher):
    await invoke(
        "create_recipe", name="Visible", settings={"showAssets": True}
    )

    body = fetcher.last("PUT", "/api/recipes/")["json"]
    assert body["settings"]["showAssets"] is True
    # the toggles Mealie seeded are preserved rather than reset to model defaults
    assert body["settings"]["locked"] is True
    assert body["settings"]["showNutrition"] is True


async def test_create_recipe_without_settings_preserves_seeded(invoke, fetcher):
    await invoke("create_recipe", name="Plain")

    body = fetcher.last("PUT", "/api/recipes/")["json"]
    assert body["settings"]["locked"] is True
    assert body["settings"]["showAssets"] is True


@pytest.mark.parametrize(
    "tool_name,arguments,method",
    [
        ("create_recipe", {"name": "Combined recipe"}, "PUT"),
        ("update_recipe", {"slug": "test-recipe"}, "PATCH"),
    ],
)
async def test_nutrition_and_settings_can_be_set_together(
    invoke, fetcher, tool_name, arguments, method
):
    await invoke(
        tool_name,
        **arguments,
        nutrition={"calories": 450, "proteinContent": 20},
        settings={"showNutrition": False},
    )

    body = fetcher.last(method, "/api/recipes/")["json"]
    assert body["nutrition"] == {"calories": "450", "proteinContent": "20"}
    assert body["settings"]["showNutrition"] is False
    assert body["settings"]["locked"] is True
    assert body["settings"]["showAssets"] is True


@pytest.mark.parametrize("tool_name", ["create_recipe", "update_recipe"])
@pytest.mark.parametrize("field", ["food", "unit"])
async def test_authoring_validates_nested_ingredients_before_requests(
    invoke, fetcher, tool_name, field
):
    arguments = {
        "ingredients": [{field: {"id": "a0819c33-1a5e-4374-9151-ed85160c0049"}}],
        "instructions": [],
    }
    arguments.update(
        {"slug": "test-recipe"} if tool_name == "update_recipe" else {"name": "Recipe"}
    )
    with pytest.raises(ToolError):
        await invoke(tool_name, **arguments)
    assert fetcher.requests == []


async def test_shared_composition_keeps_deterministic_instruction_links(invoke, fetcher):
    arguments = {
        "ingredients": [{"note": "Onion", "referenceId": "onion"}],
        "instructions": [
            {"text": "Chop", "ingredientReferences": [{"referenceId": "onion"}]}
        ],
    }
    reference_ids = []
    for tool_name, identifier in (
        ("create_recipe", {"name": "Recipe"}),
        ("update_recipe", {"slug": "test-recipe"}),
    ):
        await invoke(tool_name, **identifier, **arguments)
        written = fetcher.last("PUT")["json"]
        reference_id = written["recipeIngredient"][0]["referenceId"]
        assert uuid.UUID(reference_id).version == 4
        assert written["recipeInstructions"][0]["ingredientReferences"] == [
            {"referenceId": reference_id}
        ]
        reference_ids.append(reference_id)
    assert len(set(reference_ids)) == 1


@pytest.mark.parametrize(
    "arguments",
    [
        {"name": ""},
        {"name": " \t"},
        {"image_url": ""},
        {"image_url": " \t"},
        {"ingredients": [{"food": {"name": 123}}]},
        {"instructions": [{"title": "Missing text"}]},
        {"tags": [{"id": "a0819c33-1a5e-4374-9151-ed85160c0049"}]},
        {"tools": [{"name": "Missing id"}]},
        {"settings": {"showAssets": "not-a-bool"}},
        {"nutrition": {"calories": []}},
        {"servings": float("inf")},
        {"ingredients": [{"quantity": float("inf")}]},
    ],
)
async def test_creation_preflights_all_content(invoke, fetcher, arguments):
    with pytest.raises(ToolError):
        await invoke("create_recipe", **{"name": "Recipe", **arguments})
    assert fetcher.requests == []


@pytest.mark.parametrize(
    "stage,method,endpoint,occurrence",
    [
        ("fetch", "GET", "/api/recipes/test-recipe", 1),
        ("populate", "PUT", "/api/recipes/test-recipe", 1),
        ("image", "POST", "/api/recipes/test-recipe/image", 1),
        ("fetch_image", "GET", "/api/recipes/test-recipe", 2),
    ],
)
async def test_creation_failures_return_recoverable_progress(
    invoke, fetcher, monkeypatch, caplog, stage, method, endpoint, occurrence
):
    original_request = fetcher._handle_request
    matching_calls = 0

    def fail_stage(request_method, url, **kwargs):
        nonlocal matching_calls
        result = original_request(request_method, url, **kwargs)
        if (request_method, url) == (method, endpoint):
            matching_calls += 1
            if matching_calls == occurrence:
                raise MealieApiError(500, "private-api-response")
        return result

    monkeypatch.setattr(fetcher, "_handle_request", fail_stage)
    caplog.set_level(logging.DEBUG, logger="mealie-mcp")
    with pytest.raises(ToolError) as error:
        await invoke(
            "create_recipe",
            name="private-recipe-name",
            ingredients=["private-ingredient"],
            image_url="https://example.com/private-image",
        )
    # FastMCP prefixes ToolError with the tool name; the recovery object follows.
    message = str(error.value)
    recovery = json.loads(message[message.index("{") :])
    assert recovery["created_slug"] == fetcher.created_slug
    assert recovery["stage"] == stage
    assert sum(
        r["method"] == "POST" and r["url"] == "/api/recipes"
        for r in fetcher.requests
    ) == 1
    assert all(r["method"] != "DELETE" for r in fetcher.requests)
    assert "private-api-response" not in message
    for private in (
        "private-recipe-name",
        "private-ingredient",
        "private-image",
        "private-api-response",
        fetcher.created_slug,
    ):
        assert private not in caplog.text


async def test_initial_creation_failure_does_not_claim_a_created_recipe(
    invoke, fetcher
):
    fetcher.fail_on("/api/recipes", 500)
    with pytest.raises(ToolError) as error:
        await invoke("create_recipe", name="Recipe", ingredients=[], instructions=[])
    assert "created_slug" not in str(error.value)
    assert len(fetcher.requests) == 1


async def test_basic_creation_failure_exposes_created_slug(invoke, fetcher):
    fetcher.fail_on("/api/recipes/test-recipe", 500)
    with pytest.raises(ToolError) as error:
        await invoke("create_recipe", name="Recipe", ingredients=[], instructions=[])
    message = str(error.value)
    recovery = json.loads(message[message.index("{") :])
    assert recovery["created_slug"] == fetcher.created_slug
    assert recovery["stage"] == "fetch"
    assert [r["method"] for r in fetcher.requests] == ["POST", "GET"]


async def test_import_fetch_failure_exposes_created_slug(invoke, fetcher, monkeypatch):
    monkeypatch.setattr(
        fetcher, "import_recipe_from_url", lambda *args, **kwargs: fetcher.created_slug
    )
    fetcher.fail_on("/api/recipes/test-recipe", 500)
    with pytest.raises(ToolError) as error:
        await invoke("import_recipe_from_url", url="https://example.com/recipe")
    message = str(error.value)
    recovery = json.loads(message[message.index("{") :])
    assert recovery["created_slug"] == fetcher.created_slug
    assert recovery["stage"] == "fetch"
    assert [r["method"] for r in fetcher.requests] == ["GET"]


@pytest.mark.parametrize(
    "tool_name,arguments,method",
    [
        ("create_recipe", {"name": "Recipe"}, "PUT"),
        ("update_recipe", {"slug": "test-recipe"}, "PATCH"),
    ],
)
async def test_authoring_accepts_fractional_servings(
    invoke, fetcher, tool_name, arguments, method
):
    result = await invoke(tool_name, **arguments, servings=2.5)
    assert result["recipeServings"] == 2.5
    assert fetcher.last(method)["json"]["recipeServings"] == 2.5
    assert "created_slug" not in result
    assert "stage" not in result


async def test_concise_recipe_accepts_fractional_and_nullable_response(invoke, fetcher):
    fetcher.recipe.update(
        recipeServings=2.5,
        recipeYieldQuantity=1.5,
        dateAdded=None,
        dateUpdated=None,
        createdAt=None,
        updatedAt=None,
        recipeInstructions=None,
        recipeCategory=None,
        tags=None,
        nutrition=None,
        settings=None,
        assets=None,
        notes=None,
        extras=None,
        comments=None,
    )
    result = await invoke("get_recipe", slug="test-recipe", concise=True)
    assert result["recipeServings"] == 2.5
    assert result["recipeYieldQuantity"] == 1.5
    assert "tags" not in result


@pytest.mark.parametrize("tool_name", ["create_recipe", "update_recipe"])
async def test_authoring_preserves_unmodeled_and_nullable_fetched_fields(
    invoke, fetcher, tool_name
):
    fetcher.recipe.update(
        futureField={"nested": [1, None]},
        recipeServings=2.5,
        recipeYieldQuantity=1.5,
        dateAdded=None,
        recipeCategory=None,
        nutrition=None,
        settings={**fetcher.recipe["settings"], "futureToggle": True},
        tools=[{"id": "t", "name": "Tool", "slug": "tool", "futureField": True}],
    )
    original = deepcopy(fetcher.recipe)
    arguments = {"ingredients": [], "instructions": []}
    arguments.update(
        {"slug": "test-recipe"} if tool_name == "update_recipe" else {"name": "Recipe"}
    )
    await invoke(tool_name, **arguments)
    written = fetcher.last("PUT")["json"]
    for field in (
        "futureField", "recipeServings", "recipeYieldQuantity", "dateAdded",
        "recipeCategory", "nutrition", "settings", "tools",
    ):
        assert written[field] == original[field]
    assert written["recipeIngredient"] == []
    assert written["recipeInstructions"] == []


async def test_creation_none_leaves_content_unchanged_and_empty_lists_clear(
    invoke, fetcher
):
    fetcher.recipe.update(
        recipeIngredient=[{"note": "Keep", "futureField": True}],
        recipeInstructions=None,
        tags=[{"id": "t", "name": "Tag", "slug": "tag"}],
    )
    await invoke("create_recipe", name="Recipe", ingredients=None, tags=[])
    written = fetcher.last("PUT")["json"]
    assert written["recipeIngredient"] == [{"note": "Keep", "futureField": True}]
    assert written["recipeInstructions"] is None
    assert written["tags"] == []


@pytest.mark.parametrize("tool_name", ["create_recipe", "update_recipe"])
async def test_settings_merge_preserves_unknown_keys_with_nutrition_merge(
    invoke, fetcher, tool_name
):
    fetcher.recipe["settings"] = {"locked": True, "futureToggle": True}
    fetcher.recipe["nutrition"] = {"calories": "300", "proteinContent": "20"}
    arguments = (
        {"name": "Recipe"} if tool_name == "create_recipe" else {"slug": "test-recipe"}
    )
    await invoke(
        tool_name,
        **arguments,
        settings={"showAssets": False, "showNutrition": False},
        nutrition={"calories": 350, "proteinContent": None},
    )
    written = fetcher.last("PUT" if tool_name == "create_recipe" else "PATCH")["json"]
    # an explicit showNutrition toggle wins over the nutrition default
    assert written["settings"] == {
        "locked": True, "futureToggle": True, "showAssets": False,
        "showNutrition": False,
    }
    assert written["nutrition"] == {"calories": "350", "proteinContent": None}


def test_recipe_composition_is_pure_and_handles_nullable_settings():
    current = {"futureField": {"nested": []}, "settings": None, "nutrition": None}
    changes = {"settings": {"showAssets": False}}
    original = deepcopy(current)
    composed = _compose_recipe(current, changes)
    composed["futureField"]["nested"].append(1)
    composed["settings"]["showAssets"] = True
    assert current == original
    assert changes == {"settings": {"showAssets": False}}
    assert composed["nutrition"] is None


@pytest.mark.parametrize("tool_name", ["create_recipe", "update_recipe"])
async def test_authoring_handles_nullable_current_settings(invoke, fetcher, tool_name):
    fetcher.recipe["settings"] = None
    arguments = (
        {"name": "Recipe"} if tool_name == "create_recipe" else {"slug": "test-recipe"}
    )
    await invoke(tool_name, **arguments, settings={"showAssets": False})
    written = fetcher.last("PUT" if tool_name == "create_recipe" else "PATCH")["json"]
    assert written["settings"] == {"showAssets": False}


async def test_recipe_logs_exclude_search_content_and_validation_details(
    invoke, fetcher, caplog
):
    caplog.set_level(logging.DEBUG, logger="mealie-mcp")
    await invoke(
        "get_recipes",
        search="private-search",
        tags=["private-tag"],
        categories=["private-category"],
    )
    await invoke(
        "create_recipe", name="private-name", org_url="https://example.com/private-source"
    )
    await invoke("get_recipe", slug="private-slug")
    with pytest.raises(ToolError):
        await invoke(
            "create_recipe",
            name="private-name",
            ingredients=[{"food": {"id": "private-validation-input"}}],
        )
    for private in (
        "private-search", "private-tag", "private-category", "private-name",
        "private-source", "private-slug", "private-validation-input",
    ):
        assert private not in caplog.text


def test_recipe_api_upload_logs_exclude_filenames_and_identifiers(fetcher, caplog):
    caplog.set_level(logging.DEBUG, logger="mealie-mcp")
    fetcher.upload_recipe_image("private-slug", b"private-content", "private-file.png")
    fetcher.upload_recipe_asset("private-slug", b"private-content", "private-file.pdf")
    for private in ("private-slug", "private-content", "private-file"):
        assert private not in caplog.text
