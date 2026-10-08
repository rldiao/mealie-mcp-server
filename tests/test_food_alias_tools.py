"""Tests for the food alias tools (set_food_aliases, add_food_alias, remove_food_alias)."""

import pytest
from mcp.server.fastmcp.exceptions import ToolError

# --- set_food_aliases -------------------------------------------------------


async def test_set_food_aliases_replaces_list(invoke, fetcher):
    fetcher.foods = [
        {
            "id": "f1",
            "name": "Green Onion",
            "aliases": [{"name": "Old Alias"}],
        }
    ]

    await invoke("set_food_aliases", food_id="f1", aliases=["Scallion", "Spring Onion"])

    req = fetcher.last("PUT", "/api/foods/f1")
    assert req["json"]["id"] == "f1"
    assert req["json"]["aliases"] == [{"name": "Scallion"}, {"name": "Spring Onion"}]


async def test_set_food_aliases_dedupes_case_insensitively(invoke, fetcher):
    fetcher.foods = [{"id": "f1", "name": "Green Onion", "aliases": []}]

    await invoke("set_food_aliases", food_id="f1", aliases=["Scallion", "scallion"])

    req = fetcher.last("PUT", "/api/foods/f1")
    assert req["json"]["aliases"] == [{"name": "Scallion"}]


async def test_set_food_aliases_can_clear_all(invoke, fetcher):
    fetcher.foods = [
        {"id": "f1", "name": "Green Onion", "aliases": [{"name": "Scallion"}]}
    ]

    await invoke("set_food_aliases", food_id="f1", aliases=[])

    req = fetcher.last("PUT", "/api/foods/f1")
    assert req["json"]["aliases"] == []


async def test_set_food_aliases_validates_food_id(invoke, fetcher):
    with pytest.raises(ToolError):
        await invoke("set_food_aliases", food_id="", aliases=["Scallion"])


# --- add_food_alias ----------------------------------------------------------


async def test_add_food_alias_appends_to_existing(invoke, fetcher):
    fetcher.foods = [
        {"id": "f1", "name": "Green Onion", "aliases": [{"name": "Scallion"}]}
    ]

    await invoke("add_food_alias", food_id="f1", alias="Spring Onion")

    req = fetcher.last("PUT", "/api/foods/f1")
    assert req["json"]["aliases"] == [
        {"name": "Scallion"},
        {"name": "Spring Onion"},
    ]


async def test_add_food_alias_skips_duplicate(invoke, fetcher):
    fetcher.foods = [
        {"id": "f1", "name": "Green Onion", "aliases": [{"name": "Scallion"}]}
    ]

    await invoke("add_food_alias", food_id="f1", alias="scallion")

    req = fetcher.last("PUT", "/api/foods/f1")
    assert req["json"]["aliases"] == [{"name": "Scallion"}]


async def test_add_food_alias_validates_alias(invoke, fetcher):
    with pytest.raises(ToolError):
        await invoke("add_food_alias", food_id="f1", alias="")


# --- remove_food_alias --------------------------------------------------------


async def test_remove_food_alias_removes_matching_name(invoke, fetcher):
    fetcher.foods = [
        {
            "id": "f1",
            "name": "Green Onion",
            "aliases": [{"name": "Scallion"}, {"name": "Spring Onion"}],
        }
    ]

    await invoke("remove_food_alias", food_id="f1", alias="scallion")

    req = fetcher.last("PUT", "/api/foods/f1")
    assert req["json"]["aliases"] == [{"name": "Spring Onion"}]


async def test_remove_food_alias_no_match_is_noop(invoke, fetcher):
    fetcher.foods = [
        {"id": "f1", "name": "Green Onion", "aliases": [{"name": "Scallion"}]}
    ]

    await invoke("remove_food_alias", food_id="f1", alias="Nonexistent")

    req = fetcher.last("PUT", "/api/foods/f1")
    assert req["json"]["aliases"] == [{"name": "Scallion"}]


async def test_remove_food_alias_validates_alias(invoke, fetcher):
    with pytest.raises(ToolError):
        await invoke("remove_food_alias", food_id="f1", alias="")
