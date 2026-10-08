"""Offline regression coverage for shopping-list workflows."""

import logging
from copy import deepcopy

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from mealie.client import MealieApiError
from models.shopping_list import ShoppingListItemCreate, ShoppingListItemUpdate

ITEMS = "/api/households/shopping/items"
LISTS = "/api/households/shopping/lists"
COLLECTION = {"createdItems": [], "updatedItems": [], "deletedItems": []}
CURRENT_ITEM = {
    "id": "item-1",
    "shoppingListId": "list-1",
    "note": "Existing note",
    "quantity": 4,
    "checked": True,
    "unitId": "unit-1",
    "foodId": "food-1",
    "labelId": "label-1",
    "extras": {"preserve": "metadata"},
    "recipeReferences": [{"recipeId": "recipe-1", "recipeQuantity": 2}],
}


@pytest.fixture(autouse=True)
def shopping_responses(fetcher):
    fetcher.responses.update(
        {
            ("GET", f"{ITEMS}/item-1"): deepcopy(CURRENT_ITEM),
            ("GET", f"{ITEMS}/item-2"): {**deepcopy(CURRENT_ITEM), "id": "item-2"},
            ("GET", ITEMS): {"items": [], "page": 1, "perPage": 50, "total": 0},
            ("POST", ITEMS): deepcopy(COLLECTION),
            ("POST", f"{ITEMS}/create-bulk"): deepcopy(COLLECTION),
            ("PUT", ITEMS): deepcopy(COLLECTION),
            ("PUT", f"{ITEMS}/item-1"): deepcopy(COLLECTION),
            ("DELETE", ITEMS): {"success": True},
            ("DELETE", f"{ITEMS}/item-1"): {"success": True},
            ("POST", f"{LISTS}/list-1/recipe/recipe-1"): {"id": "list-1"},
            ("POST", f"{LISTS}/list-1/recipe/recipe-1/delete"): {"id": "list-1"},
        }
    )


@pytest.mark.parametrize("camel_case", [False, True])
async def test_bulk_shopping_create_aliases_and_nulls(invoke, fetcher, camel_case):
    item = {
        "shopping_list_id": "list-1",
        "note": None,
        "quantity": 0,
        "checked": False,
        "unit_id": None,
        "food_id": "food-1",
        "label_id": None,
        "recipe_references": [],
        "extras": None,
    }
    aliases = {
        "shopping_list_id": "shoppingListId",
        "unit_id": "unitId",
        "food_id": "foodId",
        "label_id": "labelId",
        "recipe_references": "recipeReferences",
    }
    wire = {aliases.get(key, key): value for key, value in item.items()}
    result = await invoke("create_shopping_list_items_bulk", items=[wire if camel_case else item])
    assert result == COLLECTION
    assert fetcher.last()["method"] == "POST"
    assert fetcher.last()["url"] == f"{ITEMS}/create-bulk"
    assert fetcher.last()["json"] == [wire]


@pytest.mark.parametrize(
    "invalid",
    [
        {"note": "Missing list"},
        {"shopping_list_id": " "},
        {"shopping_list_id": "list-1", "quantity": None},
        {"shopping_list_id": "list-1", "quantity": float("inf")},
        {"shopping_list_id": "list-1", "shoppingListId": "other-list"},
    ],
)
async def test_invalid_later_shopping_create_does_not_write(invoke, fetcher, invalid):
    with pytest.raises(ToolError):
        await invoke(
            "create_shopping_list_items_bulk",
            items=[{"shopping_list_id": "list-1", "note": "Valid"}, invalid],
        )
    assert fetcher.requests == []


async def test_bulk_shopping_updates_fetch_all_and_preserve_omitted_fields(invoke, fetcher):
    result = await invoke(
        "update_shopping_list_items_bulk",
        items=[
            {"id": "item-1", "quantity": 0, "checked": False, "food_id": None},
            {
                "id": "item-2",
                "shoppingListId": "list-1",
                "note": None,
                "unitId": None,
                "extras": None,
                "recipeReferences": [],
            },
        ],
    )
    assert result == COLLECTION
    assert [(request["method"], request["url"]) for request in fetcher.requests] == [
        ("GET", f"{ITEMS}/item-1"),
        ("GET", f"{ITEMS}/item-2"),
        ("PUT", ITEMS),
    ]
    assert fetcher.last()["json"] == [
        {**CURRENT_ITEM, "quantity": 0, "checked": False, "foodId": None},
        {
            **CURRENT_ITEM,
            "id": "item-2",
            "note": None,
            "unitId": None,
            "extras": None,
            "recipeReferences": [],
        },
    ]
    assert fetcher.responses["GET", f"{ITEMS}/item-1"] == CURRENT_ITEM


@pytest.mark.parametrize(
    "invalid",
    [
        {"checked": True},
        {"id": "item-2"},
        {"id": " ", "checked": True},
        {"id": "item-2", "shoppingListId": None, "checked": True},
        {"id": "item-2", "quantity": None},
    ],
)
async def test_invalid_later_shopping_update_does_not_fetch_or_write(
    invoke, fetcher, invalid
):
    with pytest.raises(ToolError):
        await invoke(
            "update_shopping_list_items_bulk",
            items=[{"id": "item-1", "checked": False}, invalid],
        )
    assert fetcher.requests == []


async def test_duplicate_shopping_updates_are_rejected_before_requests(invoke, fetcher):
    with pytest.raises(ToolError):
        await invoke(
            "update_shopping_list_items_bulk",
            items=[{"id": "item-1", "checked": True}, {"id": "item-1", "quantity": 0}],
        )
    assert fetcher.requests == []


@pytest.mark.parametrize("failure", ["fetch", "invalid_record", "put"])
async def test_bulk_shopping_failure_never_writes_an_incomplete_batch(
    invoke, fetcher, failure
):
    if failure == "fetch":
        fetcher.fail_on(f"{ITEMS}/item-2")
    elif failure == "invalid_record":
        fetcher.responses["GET", f"{ITEMS}/item-2"] = {"id": "item-2"}
    else:
        fetcher.responses.pop(("PUT", ITEMS))
        original = fetcher._handle_request

        def fail_put(method, url, **kwargs):
            if method == "PUT":
                fetcher.failures[url] = MealieApiError(502, "Failure")
            return original(method, url, **kwargs)

        fetcher._handle_request = fail_put
    with pytest.raises(ToolError):
        await invoke(
            "update_shopping_list_items_bulk",
            items=[{"id": "item-1", "checked": False}, {"id": "item-2", "checked": False}],
        )
    assert [request["method"] for request in fetcher.requests] == (
        ["GET", "GET", "PUT"] if failure == "put" else ["GET", "GET"]
    )


async def test_single_shopping_update_preserves_false_zero_and_other_fields(invoke, fetcher):
    await invoke("update_shopping_list_item", item_id="item-1", quantity=0, checked=False)
    assert fetcher.last()["json"] == {**CURRENT_ITEM, "quantity": 0, "checked": False}


async def test_single_shopping_creation_omits_unset_fields(invoke, fetcher):
    await invoke(
        "create_shopping_list_item", shopping_list_id="list-1", note="Item", quantity=0
    )
    assert fetcher.last()["json"] == {"shoppingListId": "list-1", "note": "Item", "quantity": 0}


async def test_bulk_shopping_deletion_uses_repeated_id_query(invoke, fetcher):
    assert await invoke("delete_shopping_list_items_bulk", item_ids=["item-1", "item-2"]) == {
        "success": True
    }
    assert fetcher.last()["method"] == "DELETE"
    assert fetcher.last()["url"] == ITEMS
    assert fetcher.last()["params"] == {"ids": ["item-1", "item-2"]}
    assert fetcher.last()["json"] is None


@pytest.mark.parametrize(
    "tool, arguments",
    [
        ("create_shopping_list", {"name": " "}),
        ("update_shopping_list", {"list_id": "list-1", "name": " "}),
        ("get_shopping_list", {"list_id": " "}),
        ("delete_shopping_list", {"list_id": " "}),
        ("get_shopping_list_item", {"item_id": " "}),
        ("delete_shopping_list_item", {"item_id": " "}),
        ("update_shopping_list_item", {"item_id": "item-1"}),
        ("create_shopping_list_items_bulk", {"items": []}),
        ("update_shopping_list_items_bulk", {"items": []}),
        ("delete_shopping_list_items_bulk", {"item_ids": ["item-1", " "]}),
    ],
)
async def test_invalid_shopping_inputs_make_no_requests(invoke, fetcher, tool, arguments):
    with pytest.raises(ToolError):
        await invoke(tool, **arguments)
    assert fetcher.requests == []


async def test_typed_shopping_bulk_tool_schemas_preserve_envelopes(server):
    mcp, _ = server
    schemas = {tool.name: tool.inputSchema for tool in await mcp.list_tools()}
    for name, model in (
        ("create_shopping_list_items_bulk", "ShoppingListItemCreate"),
        ("update_shopping_list_items_bulk", "ShoppingListItemUpdate"),
    ):
        assert "items" in schemas[name]["properties"]
        assert model in schemas[name]["$defs"]


def test_shopping_models_normalize_aliases_without_injecting_defaults():
    item = ShoppingListItemCreate(
        shopping_list_id="list-1", shoppingListId="list-1", food_id=None
    )
    assert item.model_dump(by_alias=True, exclude_unset=True) == {
        "shoppingListId": "list-1", "foodId": None
    }
    patch = ShoppingListItemUpdate(id="item-1", checked=False, quantity=0)
    assert patch.model_dump(by_alias=True, exclude_unset=True) == {
        "id": "item-1", "checked": False, "quantity": 0
    }
    assert ShoppingListItemCreate(shopping_list_id="list-1", id=None).model_dump(
        by_alias=True, exclude_unset=True
    ) == {"shoppingListId": "list-1", "id": None}


async def test_shopping_logs_exclude_content_and_identifiers(invoke, fetcher, caplog):
    caplog.set_level(logging.DEBUG)
    private = "PRIVATE-WORKFLOW-CONTENT"
    await invoke("create_shopping_list", name=private)
    await invoke("update_shopping_list", list_id="list-1", name=private)
    await invoke("get_shopping_list_items", search=private)
    await invoke("create_shopping_list_item", shopping_list_id="list-1", note=private)
    await invoke("add_recipe_to_shopping_list", list_id="list-1", recipe_id="recipe-1")
    await invoke("remove_recipe_from_shopping_list", list_id="list-1", recipe_id="recipe-1")
    fetcher.fail_on(LISTS, message=private)
    with pytest.raises(ToolError):
        await invoke("create_shopping_list", name=private)
    for marker in (private, "list-1", "recipe-1"):
        assert marker not in caplog.text
