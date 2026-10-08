"""Tests for the food label tools (set_food_label, set_food_label_by_name)."""

import pytest
from mcp.server.fastmcp.exceptions import ToolError

# --- set_food_label -----------------------------------------------------------


async def test_set_food_label_assigns_label_id(invoke, fetcher):
    fetcher.foods = [{"id": "f1", "name": "Carrot", "aliases": []}]

    await invoke("set_food_label", food_id="f1", label_id="l1")

    req = fetcher.last("PUT", "/api/foods/f1")
    assert req["json"]["labelId"] == "l1"


async def test_set_food_label_can_clear(invoke, fetcher):
    fetcher.foods = [{"id": "f1", "name": "Carrot", "labelId": "l1", "aliases": []}]

    await invoke("set_food_label", food_id="f1")

    req = fetcher.last("PUT", "/api/foods/f1")
    assert req["json"]["labelId"] is None


async def test_set_food_label_validates_food_id(invoke, fetcher):
    with pytest.raises(ToolError):
        await invoke("set_food_label", food_id="", label_id="l1")


# --- set_food_label_by_name ----------------------------------------------------


async def test_set_food_label_by_name_resolves_existing_label(invoke, fetcher):
    fetcher.foods = [{"id": "f1", "name": "Carrot", "aliases": []}]
    fetcher.labels = [{"id": "l1", "name": "Produce", "color": "#4CAF50"}]

    await invoke("set_food_label_by_name", food_name="carrot", label_name="produce")

    req = fetcher.last("PUT", "/api/foods/f1")
    assert req["json"]["labelId"] == "l1"
    assert len(fetcher.labels) == 1


async def test_set_food_label_by_name_creates_missing_label(invoke, fetcher):
    fetcher.foods = [{"id": "f1", "name": "Carrot", "aliases": []}]

    result = await invoke(
        "set_food_label_by_name", food_name="Carrot", label_name="Produce"
    )

    assert len(fetcher.labels) == 1
    assert fetcher.labels[0]["name"] == "Produce"
    assert result["labelId"] == fetcher.labels[0]["id"]


async def test_set_food_label_by_name_errors_on_unknown_food(invoke, fetcher):
    with pytest.raises(ToolError):
        await invoke(
            "set_food_label_by_name", food_name="Nonexistent", label_name="Produce"
        )


# --- set_foods_label_by_name ----------------------------------------------------


async def test_set_foods_label_by_name_applies_to_all_matches(invoke, fetcher):
    fetcher.foods = [
        {"id": "f1", "name": "Carrot", "aliases": []},
        {"id": "f2", "name": "Onion", "aliases": []},
    ]
    fetcher.labels = [{"id": "l1", "name": "Produce", "color": "#4CAF50"}]

    result = await invoke(
        "set_foods_label_by_name",
        food_names=["Carrot", "Onion"],
        label_name="Produce",
    )

    assert fetcher.last("PUT", "/api/foods/f1")["json"]["labelId"] == "l1"
    assert fetcher.last("PUT", "/api/foods/f2")["json"]["labelId"] == "l1"
    assert len(fetcher.labels) == 1
    assert result["not_found"] == []


async def test_set_foods_label_by_name_creates_label_once(invoke, fetcher):
    fetcher.foods = [
        {"id": "f1", "name": "Carrot", "aliases": []},
        {"id": "f2", "name": "Onion", "aliases": []},
    ]

    await invoke(
        "set_foods_label_by_name",
        food_names=["Carrot", "Onion"],
        label_name="Produce",
    )

    assert len(fetcher.labels) == 1


async def test_set_foods_label_by_name_reports_unmatched_names(invoke, fetcher):
    fetcher.foods = [{"id": "f1", "name": "Carrot", "aliases": []}]
    fetcher.labels = [{"id": "l1", "name": "Produce", "color": "#4CAF50"}]

    result = await invoke(
        "set_foods_label_by_name",
        food_names=["Carrot", "Nonexistent"],
        label_name="Produce",
    )

    assert [f["id"] for f in result["updated"]] == ["f1"]
    assert result["not_found"] == ["Nonexistent"]
    # unmatched name shouldn't stop the label from being created/applied
    assert len(fetcher.labels) == 1


@pytest.mark.parametrize(
    "tool_name,arguments",
    [
        ("mark_foods_on_hand", {"names": ["Secret Saffron"]}),
        ("set_foods_label_by_name", {"food_names": ["Secret Saffron"], "label_name": "Hidden Aisle"}),
        ("create_label", {"name": "Hidden Aisle"}),
    ],
)
async def test_food_and_label_logs_exclude_names(invoke, fetcher, caplog, tool_name, arguments):
    import logging

    fetcher.foods = [{"id": "food-1", "name": "Secret Saffron", "householdsWithIngredientFood": []}]
    with caplog.at_level(logging.DEBUG, logger="mealie-mcp"):
        await invoke(tool_name, **arguments)
    assert "Secret Saffron" not in caplog.text
    assert "Hidden Aisle" not in caplog.text
