"""Offline API path-boundary regressions; synthetic identifiers, no live requests."""

from contextlib import contextmanager
from unittest.mock import patch
import httpx
import pytest
from mcp.server.fastmcp.exceptions import ToolError
from mealie import MealieFetcher
from server import ServerConfig, create_server

ATTACKS = [
    ".",
    "..",
    "../users/self",
    "a/b",
    "a?x=y",
    "a#x",
    "%2F",
    "a\\b",
    "",
    " ",
    "ok\n",
]


@contextmanager
def real_backend(handler=None):
    """Keep all product layers; replace only the external HTTP transport."""
    requests = []

    def respond(request):
        if request.url.path == "/api/app/about":
            return httpx.Response(200, json={"version": "v3.28.0"})
        if request.url.path == "/api/users/self":
            return httpx.Response(200, json={"admin": False})
        requests.append(request)
        return handler(request) if handler else httpx.Response(200, json={})

    client = httpx.Client(
        base_url="http://mealie.invalid", transport=httpx.MockTransport(respond)
    )
    with patch("mealie.client.httpx.Client", return_value=client):
        backend = MealieFetcher("http://mealie.invalid", "synthetic-test-only")
    try:
        yield backend, requests
    finally:
        backend.close()


def sample(schema, root):
    if "$ref" in schema:
        return sample(root["$defs"][schema["$ref"].split("/")[-1]], root)
    if "anyOf" in schema:
        return sample(next(s for s in schema["anyOf"] if s.get("type") != "null"), root)
    if "enum" in schema:
        return schema["enum"][0]
    kind = schema.get("type")
    if kind == "array":
        return [sample(schema["items"], root)]
    if kind == "object":
        return {
            k: sample(schema["properties"][k], root) for k in schema.get("required", [])
        }
    if kind in ("integer", "number"):
        return 1
    if kind == "boolean":
        return False
    return "valid-id"


async def test_every_discoverable_path_argument_rejects_before_transport(tmp_path):
    # These IDs are request-body references, not API path segments.
    body_only = {
        ("create_food", "label_id"),
        ("update_food", "label_id"),
        ("create_shopping_list_item", "shopping_list_id"),
        ("create_shopping_list_item", "unit_id"),
        ("create_shopping_list_item", "food_id"),
        ("create_shopping_list_item", "label_id"),
        ("create_mealplan", "recipe_id"),
        ("update_mealplan", "recipe_id"),
    }
    with real_backend() as (backend, requests):
        mcp = create_server(ServerConfig("http://mealie.invalid", "synthetic"))
        mcp.client_provider._client = backend
        extras = {
            "update_recipe": {"name": "control"},
            "update_recipe_categories_and_tags": {"tag_ids": []},
            "set_recipe_image_from_url": {"image_url": "https://example.org/image.jpg"},
            "update_category": {"name": "control"},
            "update_tag": {"name": "control"},
            "update_food": {"name": "control"},
            "update_unit": {"name": "control"},
            "update_tool": {"name": "control"},
            "update_shopping_list_item": {"note": "control"},
            "update_mealplan": {"title": "control"},
        }
        image = tmp_path / "synthetic.png"
        asset = tmp_path / "synthetic.txt"
        image.write_bytes(b"synthetic image fixture")
        asset.write_text("synthetic asset fixture")
        extras["upload_recipe_image_file"] = {"image_path": str(image)}
        extras["upload_recipe_asset_file"] = {"asset_path": str(asset)}
        checked = set()
        for tool in await mcp.list_tools():
            schema = tool.inputSchema
            for key in schema["properties"]:
                if not (key == "slug" or key.endswith(("_id", "_slug", "_ids"))):
                    continue
                if (tool.name, key) in body_only:
                    continue
                checked.add((tool.name, key))
                base = dict(sample(schema, schema), **extras.get(tool.name, {}))
                many = key.endswith("_ids")
                requests.clear()
                try:
                    await mcp.call_tool(
                        tool.name,
                        dict(base, **{key: ["control-id"] if many else "control-id"}),
                    )
                except ToolError:
                    pass  # Only later fake response validation may fail.
                assert any("control-id" in str(r.url) for r in requests), (
                    tool.name,
                    key,
                )
                for attack in ATTACKS:
                    args = dict(base)
                    args[key] = ["control-id", attack] if many else attack
                    requests.clear()
                    with pytest.raises(ToolError):
                        await mcp.call_tool(tool.name, args)
                    assert requests == [], (tool.name, key, attack)
        assert (
            len(checked) >= 30
        )  # Catalogue shrinkage must not silently remove coverage.


async def test_bulk_update_validates_all_ids_before_fetching_first():
    with real_backend() as (backend, requests):
        mcp = create_server(ServerConfig("http://mealie.invalid", "synthetic"))
        mcp.client_provider._client = backend
        for attack in ATTACKS:
            requests.clear()
            with pytest.raises(ToolError):
                await mcp.call_tool(
                    "update_shopping_list_items_bulk",
                    {
                        "items": [
                            {"id": "valid-id", "note": "first"},
                            {"id": attack, "note": "second"},
                        ]
                    },
                )
            assert requests == []


@pytest.mark.parametrize(
    "url",
    [
        "/api/recipes/../users/self",
        "/api/recipes/a?x",
        "/api/recipes/a#x",
        "/api/recipes/%2f",
    ],
)
def test_central_guard_rejects_invalid_complete_paths(url):
    with real_backend() as (backend, requests):
        with pytest.raises(ValueError):
            backend._handle_request("GET", url)
        assert requests == []


def test_unicode_uuid_and_integer_segments_remain_usable():
    with real_backend() as (backend, requests):
        backend.get_recipe("käse-überbacken")
        backend.get_food("8d8dbe47-811e-4f27-9ed3-cfa87b6962ba")
        backend.delete_mealplan(123)
        assert [r.url.path for r in requests] == [
            "/api/recipes/käse-überbacken",
            "/api/foods/8d8dbe47-811e-4f27-9ed3-cfa87b6962ba",
            "/api/households/mealplans/123",
        ]
