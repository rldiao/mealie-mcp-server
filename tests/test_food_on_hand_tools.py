"""Tests for the on-hand marking tools (set_food_on_hand, mark_foods_on_hand).

Mealie tracks on-hand status per household via the
``householdsWithIngredientFood`` list on a food record. The fake fetcher's
GET /api/users/self returns householdId "family".
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
    assert req["json"]["householdsWithIngredientFood"] == ["family"]


async def test_set_food_on_hand_unmarks(invoke, fetcher):
    fetcher.foods = [
        {"id": "f1", "name": "Salt", "householdsWithIngredientFood": ["family"]}
    ]

    await invoke("set_food_on_hand", food_id="f1", on_hand=False)

    req = fetcher.last("PUT", "/api/foods/f1")
    assert req["json"]["householdsWithIngredientFood"] == []


async def test_set_food_on_hand_is_idempotent(invoke, fetcher):
    fetcher.foods = [
        {"id": "f1", "name": "Salt", "householdsWithIngredientFood": ["family"]}
    ]

    await invoke("set_food_on_hand", food_id="f1", on_hand=True)

    req = fetcher.last("PUT", "/api/foods/f1")
    assert req["json"]["householdsWithIngredientFood"] == ["family"]


async def test_set_food_on_hand_validates_food_id(invoke, fetcher):
    with pytest.raises(ToolError):
        await invoke("set_food_on_hand", food_id="")


# --- mark_foods_on_hand -----------------------------------------------------


async def test_mark_foods_on_hand_matches_existing_food(invoke, fetcher):
    fetcher.foods = [{"id": "f1", "name": "Salt", "householdsWithIngredientFood": []}]

    result = await invoke("mark_foods_on_hand", names=["salt"])

    assert fetcher.last("POST", "/api/foods") is None
    req = fetcher.last("PUT", "/api/foods/f1")
    assert req["json"]["householdsWithIngredientFood"] == ["family"]
    assert result["created"] == []


async def test_mark_foods_on_hand_creates_missing_food(invoke, fetcher):
    result = await invoke("mark_foods_on_hand", names=["Flour"])

    create_call = fetcher.last("POST", "/api/foods")
    assert create_call["json"] == {"name": "Flour"}

    created_id = fetcher.foods[0]["id"]
    put_call = fetcher.last("PUT", f"/api/foods/{created_id}")
    assert put_call["json"]["householdsWithIngredientFood"] == ["family"]
    assert result["created"] == ["Flour"]


async def test_mark_foods_on_hand_clears_household(invoke, fetcher):
    fetcher.foods = [
        {"id": "f1", "name": "Salt", "householdsWithIngredientFood": ["family"]}
    ]

    await invoke("mark_foods_on_hand", names=["Salt"], on_hand=False)

    req = fetcher.last("PUT", "/api/foods/f1")
    assert req["json"]["householdsWithIngredientFood"] == []


async def test_mark_foods_on_hand_validates_names(invoke, fetcher):
    with pytest.raises(ToolError):
        await invoke("mark_foods_on_hand", names=[])


async def test_mark_foods_on_hand_matches_alias_instead_of_creating(invoke, fetcher):
    fetcher.foods = [
        {
            "id": "f1",
            "name": "Green Onion",
            "aliases": [{"name": "Scallion"}],
            "householdsWithIngredientFood": [],
        }
    ]

    result = await invoke("mark_foods_on_hand", names=["scallion"])

    assert fetcher.last("POST", "/api/foods") is None
    req = fetcher.last("PUT", "/api/foods/f1")
    assert req["json"]["name"] == "Green Onion"
    assert req["json"]["householdsWithIngredientFood"] == ["family"]
    assert result["created"] == []


async def test_mark_foods_on_hand_matches_plural_name(invoke, fetcher):
    fetcher.foods = [
        {
            "id": "f1",
            "name": "Egg",
            "pluralName": "Eggs",
            "householdsWithIngredientFood": [],
        }
    ]

    result = await invoke("mark_foods_on_hand", names=["Eggs"])

    assert fetcher.last("POST", "/api/foods") is None
    assert result["created"] == []


async def test_mark_foods_on_hand_prefers_exact_name_over_alias(invoke, fetcher):
    fetcher.foods = [
        {
            "id": "f1",
            "name": "Spring Onion",
            "aliases": [{"name": "Onion"}],
            "householdsWithIngredientFood": [],
        },
        {"id": "f2", "name": "Onion", "householdsWithIngredientFood": []},
    ]

    await invoke("mark_foods_on_hand", names=["onion"])

    assert fetcher.last("PUT", "/api/foods/f2") is not None
    assert fetcher.last("PUT", "/api/foods/f1") is None


async def test_set_food_label_by_name_matches_alias(invoke, fetcher):
    fetcher.foods = [
        {"id": "f1", "name": "Green Onion", "aliases": [{"name": "Scallion"}]}
    ]

    await invoke("set_food_label_by_name", food_name="Scallion", label_name="Produce")

    assert fetcher.last("PUT", "/api/foods/f1") is not None


# --- get_on_hand_foods -------------------------------------------------------


async def test_get_on_hand_foods_lists_only_current_household(invoke, fetcher):
    fetcher.foods = [
        {"id": "f1", "name": "Salt", "householdsWithIngredientFood": ["family"]},
        {"id": "f2", "name": "Flour", "householdsWithIngredientFood": ["other"]},
        {"id": "f3", "name": "Rice", "householdsWithIngredientFood": []},
        {
            "id": "f4",
            "name": "Eggs",
            "label": {"id": "l1", "name": "Dairy"},
            "householdsWithIngredientFood": ["other", "family"],
        },
    ]

    result = await invoke("get_on_hand_foods")

    assert result == {
        "household": "family",
        "count": 2,
        "items": [
            {"id": "f4", "name": "Eggs", "label": "Dairy"},
            {"id": "f1", "name": "Salt", "label": None},
        ],
    }
    req = fetcher.last("GET", "/api/foods")
    assert req["params"]["page"] == 1
    assert "perPage" in req["params"]


async def test_get_on_hand_foods_pages_through_all_foods(invoke, fetcher):
    fetcher.foods = [
        {"id": f"f{i}", "name": f"Food {i:03d}", "householdsWithIngredientFood": ["family"]}
        for i in range(250)
    ]

    result = await invoke("get_on_hand_foods")

    assert result["count"] == 250
    pages = [r["params"]["page"] for r in fetcher.requests if r["url"] == "/api/foods"]
    assert pages == [1, 2]


async def test_get_on_hand_foods_reports_client_failure(invoke, fetcher):
    fetcher.fail_on("/api/foods")

    with pytest.raises(ToolError, match="Error fetching on-hand foods"):
        await invoke("get_on_hand_foods")
