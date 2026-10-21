"""Focused upstream regressions; no live service or credentials required."""

import json
from contextlib import contextmanager
from unittest.mock import patch
import httpx
import pytest
from mcp.server.fastmcp.exceptions import ToolError
from mealie import MealieFetcher
from server import ServerConfig, create_server


@contextmanager
def real_backend(handler=None, version="v3.28.0"):
    """Keep all product layers; replace only the external HTTP transport."""
    requests = []

    def respond(request):
        if request.url.path == "/api/app/about":
            return httpx.Response(200, json={"version": version})
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


async def test_partial_progress_keeps_sanitized_error_cause():
    def respond(request):
        if request.method == "POST":
            return httpx.Response(200, json="created")
        return httpx.Response(422, json={"detail": "SENSITIVE synthetic-backend-body"})

    with real_backend(respond) as (backend, requests):
        mcp = create_server(ServerConfig("http://mealie.invalid", "synthetic"))
        mcp.client_provider._client = backend
        with pytest.raises(ToolError) as error:
            await mcp.call_tool("create_recipe", {"name": "synthetic"})
        message = str(error.value)
        assert "HTTP 422" in message
        assert "created_slug" in message
        assert "SENSITIVE" not in message


@pytest.mark.parametrize("failure", [httpx.ReadTimeout, httpx.ConnectError])
async def test_url_import_timeout_is_unknown_outcome_and_never_retried(failure):
    def respond(request):
        raise failure("SENSITIVE URL and private backend context", request=request)

    with real_backend(respond) as (backend, requests):
        mcp = create_server(ServerConfig("http://mealie.invalid", "synthetic"))
        mcp.client_provider._client = backend
        with pytest.raises(ToolError) as error:
            await mcp.call_tool(
                "import_recipe_from_url", {"url": "https://example.org/recipe"}
            )
        assert "unknown" in str(error.value).lower()
        assert "SENSITIVE" not in str(error.value)
        assert len(requests) == 1
        assert requests[0].extensions["timeout"]["read"] == 300


@pytest.mark.parametrize(
    ("tool", "args"),
    [
        ("import_recipe_from_url", {"url": "file:///etc/passwd"}),
        (
            "set_recipe_image_from_url",
            {"slug": "valid", "image_url": "ftp://example.org/image"},
        ),
        ("create_recipe", {"name": "valid", "image_url": "file:///etc/passwd"}),
    ],
)
async def test_non_http_urls_rejected_before_any_request(tool, args):
    with real_backend() as (backend, requests):
        mcp = create_server(ServerConfig("http://mealie.invalid", "synthetic"))
        mcp.client_provider._client = backend
        with pytest.raises(ToolError):
            await mcp.call_tool(tool, args)
        assert requests == []


@pytest.mark.parametrize("tool", ["import_recipe_from_url", "import_recipe_with_ai"])
@pytest.mark.parametrize("status", [502, 503, 504])
async def test_import_proxy_failure_has_unknown_outcome(tool, status):
    def respond(request):
        if request.url.path == "/api/groups/self":
            return httpx.Response(
                200,
                json={
                    "aiProviderSettings": {
                        "aiEnabled": True,
                        "imageProviderEnabled": False,
                        "audioProviderEnabled": False,
                    }
                },
            )
        return httpx.Response(status, text="SENSITIVE synthetic proxy body")

    with real_backend(respond) as (backend, requests):
        mcp = create_server(
            ServerConfig("http://mealie.invalid", "synthetic", enable_ai_import=True)
        )
        mcp.client_provider._client = backend
        args = (
            {"url": "https://example.org/recipe"}
            if tool.endswith("url")
            else {"content": "synthetic text recipe"}
        )
        with pytest.raises(ToolError) as error:
            await mcp.call_tool(tool, args)
        assert "unknown" in str(error.value).lower()
        assert "SENSITIVE" not in str(error.value)
        assert sum(r.method == "POST" for r in requests) == 1


@pytest.mark.parametrize("version", ["v3.28.0", "v3.29.0"])
@pytest.mark.parametrize("source", ["Family notebook", "", "https://example.org/recipe"])
async def test_source_metadata_keeps_accepted_text_on_both_versions(version, source):
    with real_backend(version=version) as (backend, requests):
        mcp = create_server(ServerConfig("http://mealie.invalid", "synthetic"))
        mcp.client_provider._client = backend
        await mcp.call_tool("update_recipe", {"slug": "valid", "org_url": source})
        assert json.loads(requests[-1].content)["orgURL"] == source


@pytest.mark.parametrize("version", ["v3.28.0", "v3.29.0"])
@pytest.mark.parametrize("source", [
    "www.example.org/recipe",
    "Recipe: https://example.org/recipe",
    "https://example.org/recipe?q=" + "a" * 2100,
], ids=["without-scheme", "share-text", "long-query"])
async def test_native_recipe_source_formats_are_not_restricted(version, source):
    with real_backend(lambda request: httpx.Response(200, json="created" if request.method == "POST" else {"slug": "created"}), version) as (backend, requests):
        mcp = create_server(ServerConfig("http://mealie.invalid", "synthetic"))
        mcp.client_provider._client = backend
        await mcp.call_tool("import_recipe_from_url", {"url": source})
        assert json.loads(next(r.content for r in requests if r.method == "POST"))["url"] == source


@pytest.mark.parametrize("tool", ["set_recipe_image_from_url", "create_recipe"])
async def test_long_http_image_urls_keep_their_complete_query(invoke, fetcher, tool):
    url = "https://example.org/image?signature=" + "a" * 2100
    args = {"name": "synthetic", "image_url": url} if tool == "create_recipe" else {"slug": "test-recipe", "image_url": url}
    await invoke(tool, **args)
    assert any(request["json"] and request["json"].get("url") == url for request in fetcher.requests)
