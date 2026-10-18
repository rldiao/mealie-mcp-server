"""Tests for the meal plan iCal feed tools."""

import logging

import pytest
from mcp.server.fastmcp.exceptions import ToolError

ICAL = "/api/households/mealplans/ical"
TOKEN = "private-feed-token"
FEED_URL = f"https://mealie.example/sub{ICAL}/{TOKEN}"


def token_response(token):
    return {"householdId": "22222222-2222-2222-2222-222222222222", "mealplanIcalToken": token}


async def test_get_feed_returns_subscribe_url(invoke, fetcher):
    fetcher.responses["GET", ICAL] = token_response(TOKEN)
    assert await invoke("get_mealplan_ical_feed") == {"enabled": True, "feedUrl": FEED_URL}
    assert [(r["method"], r["url"], r["json"]) for r in fetcher.requests] == [
        ("GET", ICAL, None)
    ]


async def test_get_feed_reports_disabled(invoke, fetcher):
    fetcher.responses["GET", ICAL] = token_response(None)
    assert await invoke("get_mealplan_ical_feed") == {"enabled": False, "feedUrl": None}


@pytest.mark.parametrize(
    "enabled, method, token, expected",
    [
        (True, "POST", TOKEN, {"enabled": True, "feedUrl": FEED_URL}),
        (False, "DELETE", None, {"enabled": False, "feedUrl": None}),
    ],
)
async def test_set_feed_enables_or_disables(
    invoke, fetcher, enabled, method, token, expected
):
    fetcher.responses[method, ICAL] = token_response(token)
    assert await invoke("set_mealplan_ical_feed", enabled=enabled) == expected
    assert [(r["method"], r["url"], r["json"]) for r in fetcher.requests] == [
        (method, ICAL, None)
    ]


async def test_set_feed_requires_enabled(invoke, fetcher):
    with pytest.raises(ToolError):
        await invoke("set_mealplan_ical_feed")
    assert fetcher.requests == []


@pytest.mark.parametrize(
    "tool, arguments, message",
    [
        ("get_mealplan_ical_feed", {}, "Error fetching mealplan iCal feed"),
        ("set_mealplan_ical_feed", {"enabled": True}, "Error changing mealplan iCal feed"),
    ],
)
async def test_feed_failures_are_tool_errors(invoke, fetcher, tool, arguments, message):
    fetcher.fail_on(ICAL, status_code=403)
    with pytest.raises(ToolError, match=message):
        await invoke(tool, **arguments)


async def test_feed_token_is_never_logged(invoke, fetcher, caplog):
    caplog.set_level(logging.DEBUG, logger="mealie-mcp")
    fetcher.responses["GET", ICAL] = token_response(TOKEN)
    fetcher.responses["POST", ICAL] = token_response(TOKEN)
    await invoke("get_mealplan_ical_feed")
    await invoke("set_mealplan_ical_feed", enabled=True)
    assert caplog.records
    assert TOKEN not in caplog.text
