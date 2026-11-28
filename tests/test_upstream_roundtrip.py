"""Focused upstream regressions; no live service or credentials required."""

import json
from contextlib import contextmanager
from unittest.mock import patch
import httpx
import pytest
from mealie import MealieFetcher
from server import ServerConfig, create_server


@contextmanager
def real_backend(handler=None):
    """Keep all product layers; replace only the external HTTP transport."""
    requests = []

    def respond(request):
        if request.url.path == "/api/app/about":
            return httpx.Response(200, json={"version": "v3.28.0"})
        if request.url.path == "/api/users/self":
            return httpx.Response(200, json={"admin": False})
        requests.append(request)
        return handler(request) if handler else httpx.Response(200, json={})

    client = httpx.Client(
        base_url="http://mealie.invalid", transport=httpx.MockTransport(respond)
    )
    with patch("mealie.client.httpx.Client", return_value=client):
        backend = MealieFetcher("http://mealie.invalid", "synthetic-test-only")
    try:
        yield backend, requests
    finally:
        backend.close()


@pytest.mark.parametrize("version", ["3.28", "3.29"])
async def test_mealie_ingredient_and_step_roundtrip_preserves_version_times(version):
    ingredient = {
        "quantity": 2,
        "unit": {"name": "gram", "id": "8d8dbe47-811e-4f27-9ed3-cfa87b6962ba"},
        "food": {"name": "rice", "id": "b54bd00d-68af-4d6b-8fcf-0cb24220df6f"},
        "referencedRecipe": {
            "id": "526fd567-ecdc-47c7-95de-c4f41ab18806",
            "slug": "linked",
        },
        "note": "synthetic",
        "display": "old rendered text",
        "title": "section",
        "originalText": "2 g rice",
        "substitutions": [
            {"substituteFoodId": None, "note": "water", "substituteFood": None}
        ],
        "referenceId": "428a7081-f8cd-4406-a6c6-9317ba661aa9",
    }
    step = {
        "id": "53c99c94-00d2-4014-9e47-f4ee8bf84174",
        "title": "section",
        "summary": "heading",
        "text": "mix",
        "ingredientReferences": [{"referenceId": ingredient["referenceId"]}],
        "noteReferences": [{"referenceId": "cc1d58da-2620-4d01-8384-f28bb931d4fb"}],
    }
    current = {
        "slug": "roundtrip",
        "name": "test",
        "recipeIngredient": [ingredient],
        "recipeInstructions": [step],
    }

    times = {"totalTime": "30 min", "prepTime": "10 min", "performTime": "20 min"} if version == "3.28" else {"totalTime": None, "totalTimeSeconds": 1800, "prepTimeSeconds": 600, "performTimeSeconds": 1200}
    current.update(times)

    def respond(request):
        return httpx.Response(
            200,
            json=json.loads(request.content) if request.method == "PUT" else current,
        )

    with real_backend(respond) as (backend, requests):
        mcp = create_server(ServerConfig("http://mealie.invalid", "synthetic"))
        mcp.client_provider._client = backend
        fetched = backend.get_recipe("roundtrip")
        await mcp.call_tool(
            "update_recipe",
            {
                "slug": "roundtrip",
                "ingredients": fetched["recipeIngredient"],
                "instructions": fetched["recipeInstructions"],
            },
        )
        payload = json.loads(requests[-1].content)
        expected = {k: v for k, v in ingredient.items() if k != "display"}
        assert payload["recipeIngredient"] == [expected]
        assert payload["recipeInstructions"] == [step]
        assert {key: payload[key] for key in times} == times


async def test_concise_recipe_preserves_readable_ingredient_display():
    def respond(request):
        return httpx.Response(
            200,
            json={
                "userId": "synthetic-user",
                "householdId": "synthetic-household",
                "groupId": "synthetic-group",
                "name": "synthetic",
                "slug": "r",
                "recipeIngredient": [{"quantity": 200, "display": "200 g rice"}],
            },
        )

    with real_backend(respond) as (backend, requests):
        mcp = create_server(ServerConfig("http://mealie.invalid", "synthetic"))
        mcp.client_provider._client = backend
        result = await mcp.call_tool("get_recipe", {"slug": "r", "concise": True})
        assert "200 g rice" in str(result)


@pytest.mark.parametrize(
    "flags",
    [
        {"isFood": True, "disableAmount": False},
        {"isFood": False, "disableAmount": True},
        {},
    ],
)
async def test_version_optional_ingredient_flags_roundtrip_without_inventing_defaults(
    flags,
):
    from models.recipe import RecipeIngredient

    ingredient = {"quantity": 2, "note": "synthetic", **flags}
    parsed = RecipeIngredient.model_validate(ingredient).model_dump(
        exclude_none=True, exclude_unset=True
    )
    assert {k: parsed[k] for k in flags if k in parsed} == flags
    current = {"slug": "legacy", "recipeIngredient": [ingredient]}

    def respond(request):
        return httpx.Response(
            200,
            json=json.loads(request.content) if request.method == "PUT" else current,
        )

    with real_backend(respond) as (backend, requests):
        mcp = create_server(ServerConfig("http://mealie.invalid", "synthetic"))
        mcp.client_provider._client = backend
        await mcp.call_tool(
            "update_recipe", {"slug": "legacy", "ingredients": [ingredient]}
        )
        saved = json.loads(requests[-1].content)["recipeIngredient"][0]
        assert {k: saved[k] for k in ("isFood", "disableAmount") if k in saved} == flags
