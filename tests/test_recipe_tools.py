"""Tests for the recipe-authoring tools (structured ingredients, full create,
patch fields, concise output, image and asset uploads)."""

import pytest
from mcp.server.fastmcp.exceptions import ToolError


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


async def test_create_recipe_full_sets_nutrition(invoke, fetcher):
    await invoke(
        "create_recipe_full",
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


async def test_create_recipe_full_without_nutrition_sends_empty_object(invoke, fetcher):
    await invoke("create_recipe_full", name="Plain", ingredients=["1 onion"])
    body = fetcher.last("PUT", "/api/recipes/")["json"]
    assert body["nutrition"] == {}


async def test_patch_recipe_sets_nutrition(invoke, fetcher):
    await invoke(
        "patch_recipe",
        slug="test-recipe",
        nutrition={"calories": "450", "fatContent": "12"},
    )
    body = fetcher.last("PATCH", "/api/recipes/")["json"]
    assert body == {"nutrition": {"calories": "450", "fatContent": "12"}}


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
