"""Offline regression coverage for meal-planning workflows."""

import json
import logging
from copy import deepcopy

import httpx
import pytest
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import ValidationError

from mealie.client import MealieApiError
from models.mealplan import MealPlanEntry

MEALPLANS = "/api/households/mealplans"
CURRENT_MEAL = {
    "id": "meal-1",
    "date": "2026-10-01",
    "entryType": "dinner",
    "recipeId": "recipe-1",
    "title": "Existing meal",
    "text": "Preserved text",
    "groupId": "group-1",
    "userId": "user-1",
}


@pytest.fixture(autouse=True)
def mealplan_responses(fetcher):
    fetcher.responses.update(
        {
            ("GET", f"{MEALPLANS}/meal-1"): deepcopy(CURRENT_MEAL),
            ("GET", f"{MEALPLANS}/today"): [],
        }
    )


@pytest.mark.parametrize(
    "dates",
    [
        {},
        {"start_date": "2026-10-01"},
        {"end_date": "2026-10-07"},
        {"start_date": "2026-10-01", "end_date": "2026-10-07"},
    ],
)
async def test_mealplan_date_filter_wire_keys(invoke, fetcher, dates):
    await invoke("get_all_mealplans", **dates, page=2, per_page=7)
    request = fetcher.last()
    assert request["method"] == "GET"
    assert request["url"] == MEALPLANS
    assert request["params"] == {**dates, "page": 2, "perPage": 7}


@pytest.mark.parametrize(
    "dates",
    [
        {"start_date": "2026-02-30"},
        {"end_date": "20261007"},
        {"start_date": "2026-10-07", "end_date": "2026-10-01"},
    ],
)
async def test_invalid_mealplan_filters_do_not_request(invoke, fetcher, dates):
    with pytest.raises(ToolError):
        await invoke("get_all_mealplans", **dates)
    assert fetcher.requests == []


@pytest.mark.parametrize(
    "changes",
    [
        {"date": "2026-02-30"},
        {"date": "20261001"},
        {"entry_type": "snack"},
        {"recipe_id": "   "},
        {"title": "  ", "recipe_id": None},
        {"title": None, "recipe_id": None},
    ],
)
@pytest.mark.parametrize("bulk", [False, True])
async def test_mealplan_validation_is_consistent(invoke, fetcher, changes, bulk):
    entry = {"date": "2026-10-01", "title": "Meal", **changes}
    with pytest.raises(ToolError):
        if bulk:
            await invoke(
                "create_mealplan_bulk",
                entries=[{"date": "2026-10-01", "title": "Valid"}, entry],
            )
        else:
            await invoke("create_mealplan", **entry)
    assert fetcher.requests == []


def test_mealplan_model_validates_business_rules_and_default():
    assert MealPlanEntry(date="2024-02-29", recipe_id="recipe-1").entry_type == "breakfast"
    with pytest.raises(ValidationError):
        MealPlanEntry(date="2026-10-01")


async def test_single_and_bulk_mealplan_payloads_and_success(invoke, fetcher):
    await invoke("create_mealplan", date="2026-10-01", recipe_id="recipe-1")
    assert fetcher.last()["json"] == {
        "date": "2026-10-01",
        "entryType": "breakfast",
        "recipeId": "recipe-1",
    }
    result = await invoke(
        "create_mealplan_bulk",
        entries=[
            {"date": "2026-10-02", "recipe_id": "recipe-2", "entry_type": "lunch"},
            {"date": "2026-10-03", "title": "Meal"},
        ],
    )
    assert result == {"message": "Successfully created 2 mealplan entries"}
    assert [request["json"] for request in fetcher.requests[-2:]] == [
        {"date": "2026-10-02", "recipeId": "recipe-2", "entryType": "lunch"},
        {"date": "2026-10-03", "title": "Meal", "entryType": "breakfast"},
    ]


async def test_bulk_mealplan_failure_reports_only_completed_progress(
    invoke, fetcher, monkeypatch, caplog
):
    original = fetcher._handle_request
    attempts = 0
    private = "PRIVATE-RESPONSE-BODY"

    def fail_second(method, url, **kwargs):
        nonlocal attempts
        if method == "POST" and url == MEALPLANS:
            attempts += 1
            if attempts == 2:
                fetcher.failures[url] = MealieApiError(502, private, private)
        return original(method, url, **kwargs)

    monkeypatch.setattr(fetcher, "_handle_request", fail_second)
    caplog.set_level(logging.DEBUG)
    with pytest.raises(ToolError) as error:
        await invoke(
            "create_mealplan_bulk",
            entries=[{"date": "2026-10-01", "title": "PRIVATE-TITLE"}] * 3,
        )
    progress = json.loads(str(error.value).split("Progress: ", 1)[1])
    assert progress == {
        "completed": [{"index": 0, "id": "generated-0001"}],
        "failed_index": 1,
    }
    assert attempts == 2
    assert private not in str(error.value)
    assert private not in caplog.text
    assert "PRIVATE-TITLE" not in caplog.text
    assert "generated-0001" not in caplog.text


@pytest.mark.parametrize(
    "error",
    [
        TimeoutError("PRIVATE-TIMEOUT"),
        ConnectionError("PRIVATE-CONNECTION"),
        httpx.ReadTimeout("PRIVATE-HTTPX"),
    ],
)
async def test_bulk_mealplan_network_failures_retain_progress(
    invoke, fetcher, monkeypatch, error
):
    original = fetcher.create_mealplan
    attempts = 0

    def fail_second(**kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 2:
            raise error
        return original(**kwargs)

    monkeypatch.setattr(fetcher, "create_mealplan", fail_second)
    with pytest.raises(ToolError) as failure:
        await invoke(
            "create_mealplan_bulk",
            entries=[{"date": "2026-10-01", "title": "Meal"}] * 3,
        )
    progress = json.loads(str(failure.value).split("Progress: ", 1)[1])
    assert progress["completed"] == [{"index": 0, "id": "generated-0001"}]
    assert progress["failed_index"] == 1
    assert attempts == 2
    assert "PRIVATE-" not in str(failure.value)


@pytest.mark.parametrize(
    "arguments, expected_recipe",
    [
        ({"title": "New title"}, "recipe-1"),
        ({"title": "New title", "recipe_id": None}, "recipe-1"),
        ({"recipe_id": "recipe-2"}, "recipe-2"),
        ({"clear_recipe": True}, None),
    ],
)
async def test_mealplan_update_preserves_fields_and_distinguishes_clear(
    invoke, fetcher, arguments, expected_recipe
):
    await invoke("update_mealplan", entry_id="meal-1", **arguments)
    expected = {**CURRENT_MEAL, "recipeId": expected_recipe}
    if "title" in arguments:
        expected["title"] = arguments["title"]
    assert [request["method"] for request in fetcher.requests] == ["GET", "PUT"]
    assert fetcher.last()["json"] == expected


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"clear_recipe": True, "recipe_id": "replacement"},
        {"date": "2026-02-30"},
        {"entry_type": "snack"},
    ],
)
async def test_invalid_mealplan_updates_make_no_requests(invoke, fetcher, arguments):
    with pytest.raises(ToolError):
        await invoke("update_mealplan", entry_id="meal-1", **arguments)
    assert fetcher.requests == []


async def test_cannot_clear_last_mealplan_content(invoke, fetcher):
    with pytest.raises(ToolError):
        await invoke("update_mealplan", entry_id="meal-1", title="", clear_recipe=True)
    assert [request["method"] for request in fetcher.requests] == ["GET"]


async def test_todays_mealplan_preserves_list_result(invoke, fetcher):
    assert await invoke("get_todays_mealplan") == []
    assert fetcher.last()["url"] == f"{MEALPLANS}/today"


async def test_invalid_mealplan_delete_makes_no_requests(invoke, fetcher):
    with pytest.raises(ToolError):
        await invoke("delete_mealplan", item_id=" ")
    assert fetcher.requests == []


async def test_typed_mealplan_bulk_tool_schema_preserves_envelope(server):
    mcp, _ = server
    schemas = {tool.name: tool.inputSchema for tool in await mcp.list_tools()}
    meal_schema = schemas["create_mealplan_bulk"]
    assert "entries" in meal_schema["properties"]
    meal = meal_schema["$defs"]["MealPlanEntry"]
    assert {"date", "recipe_id", "title", "entry_type"} <= set(meal["properties"])
    assert meal["properties"]["entry_type"]["default"] == "breakfast"
    assert meal["properties"]["entry_type"]["enum"] == ["breakfast", "lunch", "dinner", "side"]


async def test_mealplan_logs_exclude_content_and_identifiers(invoke, fetcher, caplog):
    caplog.set_level(logging.DEBUG)
    private = "PRIVATE-WORKFLOW-CONTENT"
    await invoke("create_mealplan", date="2026-10-01", title=private, recipe_id=private)
    with pytest.raises(ToolError):
        await invoke("create_mealplan", date=private, title=private)
    with pytest.raises(ToolError):
        await invoke(
            "create_mealplan_bulk",
            entries=[{"date": "2026-10-01", "title": private}, {"date": private}],
        )
    fetcher.fail_on(MEALPLANS, message=private)
    with pytest.raises(ToolError):
        await invoke("create_mealplan", date="2026-10-01", title=private)
    assert private not in caplog.text
