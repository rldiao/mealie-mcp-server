"""Tests for the tool ownership tools (set_tool_on_hand, mark_tools_on_hand).

Mealie tracks tool ownership per household via the ``householdsWithTool``
list on a tool record. The fake fetcher's GET /api/users/self returns
householdId "household-1".
"""

import pytest
from mcp.server.fastmcp.exceptions import ToolError

TOOL_URL = "/api/organizers/tools"


def _tool(households):
    return {
        "id": "t1",
        "name": "Dutch Oven",
        "slug": "dutch-oven",
        "householdsWithTool": households,
    }


# --- set_tool_on_hand -------------------------------------------------------


async def test_set_tool_on_hand_marks_on(invoke, fetcher):
    fetcher.responses["GET", f"{TOOL_URL}/t1"] = _tool(["household-2"])

    await invoke("set_tool_on_hand", tool_id="t1")

    req = fetcher.last("PUT", f"{TOOL_URL}/t1")
    assert req["json"]["id"] == "t1"
    assert req["json"]["name"] == "Dutch Oven"
    assert req["json"]["slug"] == "dutch-oven"
    assert req["json"]["householdsWithTool"] == ["household-2", "household-1"]


async def test_set_tool_on_hand_unmarks_only_current_household(invoke, fetcher):
    fetcher.responses["GET", f"{TOOL_URL}/t1"] = _tool(["household-1", "household-2"])

    await invoke("set_tool_on_hand", tool_id="t1", on_hand=False)

    req = fetcher.last("PUT", f"{TOOL_URL}/t1")
    assert req["json"]["householdsWithTool"] == ["household-2"]


async def test_set_tool_on_hand_is_idempotent(invoke, fetcher):
    fetcher.responses["GET", f"{TOOL_URL}/t1"] = _tool(["household-1"])

    await invoke("set_tool_on_hand", tool_id="t1", on_hand=True)

    req = fetcher.last("PUT", f"{TOOL_URL}/t1")
    assert req["json"]["householdsWithTool"] == ["household-1"]


async def test_set_tool_on_hand_validates_tool_id(invoke, fetcher):
    with pytest.raises(ToolError):
        await invoke("set_tool_on_hand", tool_id="")
    assert fetcher.requests == []


async def test_set_tool_on_hand_requires_household(invoke, fetcher):
    fetcher.responses["GET", "/api/users/self"] = {"id": "user-1"}

    with pytest.raises(ToolError):
        await invoke("set_tool_on_hand", tool_id="t1")
    assert fetcher.last("PUT") is None


async def test_set_tool_on_hand_surfaces_api_failure(invoke, fetcher):
    fetcher.fail_on(f"{TOOL_URL}/t1")

    with pytest.raises(ToolError):
        await invoke("set_tool_on_hand", tool_id="t1")
    assert fetcher.last("PUT") is None


# --- mark_tools_on_hand -----------------------------------------------------


async def test_mark_tools_on_hand_matches_existing_tool(invoke, fetcher):
    fetcher.responses["GET", TOOL_URL] = {"items": [_tool([])]}

    result = await invoke("mark_tools_on_hand", names=["dutch oven"])

    assert fetcher.last("GET", TOOL_URL)["params"]["search"] == "dutch oven"
    assert fetcher.last("POST", TOOL_URL) is None
    req = fetcher.last("PUT", f"{TOOL_URL}/t1")
    assert req["json"]["householdsWithTool"] == ["household-1"]
    assert result["created"] == []
    assert len(result["updated"]) == 1


async def test_mark_tools_on_hand_creates_missing_tool(invoke, fetcher):
    result = await invoke("mark_tools_on_hand", names=[" Stand Mixer ", ""])

    assert fetcher.last("POST", TOOL_URL)["json"] == {"name": "Stand Mixer"}
    put = fetcher.last("PUT", f"{TOOL_URL}/generated-0001")
    assert put["json"]["householdsWithTool"] == ["household-1"]
    assert result["created"] == ["Stand Mixer"]


async def test_mark_tools_on_hand_clears_household(invoke, fetcher):
    fetcher.responses["GET", TOOL_URL] = {"items": [_tool(["household-1"])]}

    await invoke("mark_tools_on_hand", names=["Dutch Oven"], on_hand=False)

    req = fetcher.last("PUT", f"{TOOL_URL}/t1")
    assert req["json"]["householdsWithTool"] == []


async def test_mark_tools_on_hand_validates_names(invoke, fetcher):
    with pytest.raises(ToolError):
        await invoke("mark_tools_on_hand", names=[])
    assert fetcher.requests == []
