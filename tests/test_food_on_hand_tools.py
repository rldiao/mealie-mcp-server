"""Tests for the on-hand marking tools (set_food_on_hand, mark_foods_on_hand).

Mealie tracks on-hand status per household via the
``householdsWithIngredientFood`` list on a food record. The fake fetcher's
GET /api/users/self returns householdId "household-1".
"""

import pytest
from mcp.server.fastmcp.exceptions import ToolError

# --- set_food_on_hand -----------------------------------------------------


async def test_set_food_on_hand_marks_on(invoke, fetcher):
    fetcher.foods = [{"id": "f1", "name": "Salt", "householdsWithIngredientFood": []}]

    await invoke("set_food_on_hand", food_id="f1")

    req = fetcher.last("PUT", "/api/foods/f1")
    assert req["json"]["id"] == "f1"
    assert req["json"]["name"] == "Salt"
    assert req["json"]["householdsWithIngredientFood"] == ["household-1"]


async def test_set_food_on_hand_unmarks(invoke, fetcher):
    fetcher.foods = [
        {"id": "f1", "name": "Salt", "householdsWithIngredientFood": ["household-1"]}
    ]

    await invoke("set_food_on_hand", food_id="f1", on_hand=False)

    req = fetcher.last("PUT", "/api/foods/f1")
    assert req["json"]["householdsWithIngredientFood"] == []


async def test_set_food_on_hand_is_idempotent(invoke, fetcher):
    fetcher.foods = [
        {"id": "f1", "name": "Salt", "householdsWithIngredientFood": ["household-1"]}
    ]

    await invoke("set_food_on_hand", food_id="f1", on_hand=True)

    req = fetcher.last("PUT", "/api/foods/f1")
    assert req["json"]["householdsWithIngredientFood"] == ["household-1"]


async def test_set_food_on_hand_validates_food_id(invoke, fetcher):
    with pytest.raises(ToolError):
        await invoke("set_food_on_hand", food_id="")


# --- mark_foods_on_hand -----------------------------------------------------


async def test_mark_foods_on_hand_matches_existing_food(invoke, fetcher):
    fetcher.foods = [{"id": "f1", "name": "Salt", "householdsWithIngredientFood": []}]

    result = await invoke("mark_foods_on_hand", names=["salt"])

    assert fetcher.last("POST", "/api/foods") is None
    req = fetcher.last("PUT", "/api/foods/f1")
    assert req["json"]["householdsWithIngredientFood"] == ["household-1"]
    assert result["created"] == []


async def test_mark_foods_on_hand_creates_missing_food(invoke, fetcher):
    result = await invoke("mark_foods_on_hand", names=["Flour"])

    create_call = fetcher.last("POST", "/api/foods")
    assert create_call["json"] == {"name": "Flour"}

    created_id = fetcher.foods[0]["id"]
    put_call = fetcher.last("PUT", f"/api/foods/{created_id}")
    assert put_call["json"]["householdsWithIngredientFood"] == ["household-1"]
    assert result["created"] == ["Flour"]


async def test_mark_foods_on_hand_clears_household(invoke, fetcher):
    fetcher.foods = [
        {"id": "f1", "name": "Salt", "householdsWithIngredientFood": ["household-1"]}
    ]

    await invoke("mark_foods_on_hand", names=["Salt"], on_hand=False)

    req = fetcher.last("PUT", "/api/foods/f1")
    assert req["json"]["householdsWithIngredientFood"] == []


async def test_mark_foods_on_hand_validates_names(invoke, fetcher):
    with pytest.raises(ToolError):
        await invoke("mark_foods_on_hand", names=[])
