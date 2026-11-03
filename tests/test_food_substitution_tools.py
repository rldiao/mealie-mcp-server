"""Tests for set_food_substitutions (common, food-level substitutions)."""

import pytest
from mcp.server.fastmcp.exceptions import ToolError


async def test_set_food_substitutions_replaces_list_and_keeps_fields(invoke, fetcher):
    fetcher.foods = [
        {
            "id": "f1",
            "name": "Buttermilk",
            "labelId": "l1",
            "aliases": [{"name": "Cultured milk"}],
            "substitutions": [{"substituteFoodId": "old", "note": None}],
        }
    ]

    await invoke(
        "set_food_substitutions",
        food_id="f1",
        substitutions=[
            {"substituteFoodId": "f2", "note": "add 1 tbsp lemon juice"},
            {"note": "  yogurt thinned with water  "},
        ],
    )

    assert [(r["method"], r["url"]) for r in fetcher.requests] == [
        ("GET", "/api/foods/f1"),
        ("PUT", "/api/foods/f1"),
    ]
    body = fetcher.last("PUT", "/api/foods/f1")["json"]
    assert body["substitutions"] == [
        {"substituteFoodId": "f2", "note": "add 1 tbsp lemon juice"},
        {"note": "yogurt thinned with water"},
    ]
    assert body["labelId"] == "l1"
    assert body["aliases"] == [{"name": "Cultured milk"}]


async def test_set_food_substitutions_can_clear(invoke, fetcher):
    fetcher.foods = [
        {"id": "f1", "name": "Buttermilk", "substitutions": [{"note": "milk"}]}
    ]
    await invoke("set_food_substitutions", food_id="f1", substitutions=[])
    assert fetcher.last("PUT", "/api/foods/f1")["json"]["substitutions"] == []


@pytest.mark.parametrize(
    "food_id, substitutions",
    [
        (" ", [{"note": "milk"}]),
        ("f1", [{"note": "   "}]),
        ("f1", [{}]),
        ("f1", [{"substituteFoodId": "f1"}]),
    ],
)
async def test_set_food_substitutions_validates_before_request(
    invoke, fetcher, food_id, substitutions
):
    with pytest.raises(ToolError):
        await invoke(
            "set_food_substitutions", food_id=food_id, substitutions=substitutions
        )
    assert fetcher.requests == []


async def test_set_food_substitutions_failure_is_tool_error(invoke, fetcher):
    fetcher.foods = [{"id": "f1", "name": "Buttermilk"}]
    fetcher.fail_on("/api/foods/f1", status_code=422)
    with pytest.raises(ToolError, match="Error setting food substitutions"):
        await invoke(
            "set_food_substitutions", food_id="f1", substitutions=[{"note": "milk"}]
        )
