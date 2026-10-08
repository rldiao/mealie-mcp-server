"""Tests for the label tools (get_labels, create_label, get_label, update_label, delete_label)."""

import pytest
from mcp.server.fastmcp.exceptions import ToolError


async def test_get_labels_lists_all(invoke, fetcher):
    fetcher.labels = [{"id": "l1", "name": "Produce", "color": "#4CAF50"}]

    result = await invoke("get_labels")

    assert result["items"] == [{"id": "l1", "name": "Produce", "color": "#4CAF50"}]


async def test_get_labels_filters_by_search(invoke, fetcher):
    fetcher.labels = [
        {"id": "l1", "name": "Produce", "color": "#4CAF50"},
        {"id": "l2", "name": "Dairy", "color": "#2196F3"},
    ]

    result = await invoke("get_labels", search="dairy")

    assert [item["id"] for item in result["items"]] == ["l2"]


async def test_create_label_sends_name_and_color(invoke, fetcher):
    await invoke("create_label", name="Produce", color="#4CAF50")

    req = fetcher.last("POST", "/api/groups/labels")
    assert req["json"] == {"name": "Produce", "color": "#4CAF50"}


async def test_create_label_without_color(invoke, fetcher):
    await invoke("create_label", name="Produce")

    req = fetcher.last("POST", "/api/groups/labels")
    assert req["json"] == {"name": "Produce"}


async def test_get_label_by_id(invoke, fetcher):
    fetcher.labels = [{"id": "l1", "name": "Produce", "color": "#4CAF50"}]

    result = await invoke("get_label", label_id="l1")

    assert result["name"] == "Produce"


async def test_update_label_merges_provided_fields(invoke, fetcher):
    fetcher.labels = [{"id": "l1", "name": "Produce", "color": "#4CAF50"}]

    await invoke("update_label", label_id="l1", color="#8BC34A")

    req = fetcher.last("PUT", "/api/groups/labels/l1")
    assert req["json"] == {"color": "#8BC34A"}


async def test_update_label_requires_a_field(invoke, fetcher):
    with pytest.raises(ToolError):
        await invoke("update_label", label_id="l1")


async def test_delete_label(invoke, fetcher):
    await invoke("delete_label", label_id="l1")

    req = fetcher.last("DELETE", "/api/groups/labels/l1")
    assert req is not None
