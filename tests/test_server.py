"""Startup and transport checks without a live Mealie instance."""

import json
import runpy
from unittest.mock import Mock, patch

import httpx
import pytest


@pytest.fixture
def load_server(monkeypatch, request):
    monkeypatch.setenv("MEALIE_BASE_URL", "http://mealie.invalid")
    monkeypatch.setenv("MEALIE_API_KEY", "test-placeholder")
    for name in ("MCP_TRANSPORT", "MCP_HOST", "MCP_PORT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda: None)

    def load(health_status=200):
        requests = []
        shutdown = Mock()

        def respond(api_request):
            requests.append(api_request)
            if api_request.url.path == "/api/app/about":
                return httpx.Response(health_status, json={})
            assert api_request.url.path == "/api/recipes"
            return httpx.Response(200, json={"items": [], "total": 0})

        client = httpx.Client(
            base_url="http://mealie.invalid",
            transport=httpx.MockTransport(respond),
        )
        request.addfinalizer(client.close)
        with (
            patch("mealie.client.httpx.Client", return_value=client),
            patch("atexit.register", shutdown),
        ):
            namespace = runpy.run_module("server", run_name="transport_test_server")
        return namespace, client, shutdown, requests

    return load


@pytest.mark.parametrize("transport", [None, "streamable-http"])
def test_transport_selection(load_server, monkeypatch, transport):
    if transport:
        monkeypatch.setenv("MCP_TRANSPORT", transport)
        monkeypatch.setenv("MCP_HOST", "0.0.0.0")
        monkeypatch.setenv("MCP_PORT", "8766")

    server, client, shutdown, requests = load_server()
    mcp = server["mcp"]
    assert mcp.settings.host == ("0.0.0.0" if transport else "127.0.0.1")
    assert mcp.settings.port == (8766 if transport else 8765)
    with patch.object(mcp, "run") as run:
        server["main"]()
    run.assert_called_once_with(transport=transport or "stdio")
    assert requests[0].url.path == "/api/app/about"
    shutdown.assert_called_once_with(server["mealie"].close)
    shutdown.call_args.args[0]()
    assert client.is_closed


def test_startup_rejects_failed_health_check(load_server):
    with pytest.raises(httpx.HTTPStatusError):
        load_server(health_status=503)


def test_transport_failure_propagates(load_server):
    server, _, _, _ = load_server()
    with patch.object(server["mcp"], "run", side_effect=ValueError("Invalid transport")):
        with pytest.raises(ValueError, match="Invalid transport"):
            server["main"]()


async def test_http_sessions_initialize_list_and_call_tools(load_server):
    server, _, _, requests = load_server()
    app = server["mcp"].streamable_http_app()
    session_ids = set()

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://127.0.0.1:8765",
        ) as client:
            for _ in range(2):
                headers = {"Accept": "application/json, text/event-stream"}
                response = await client.post(
                    "/mcp",
                    headers=headers,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2025-03-26",
                            "capabilities": {},
                            "clientInfo": {"name": "test", "version": "1"},
                        },
                    },
                )
                assert response.status_code == 200
                assert '"name":"mealie"' in response.text
                session_id = response.headers["mcp-session-id"]
                assert session_id not in session_ids
                session_ids.add(session_id)
                headers["Mcp-Session-Id"] = session_id

                response = await client.post(
                    "/mcp",
                    headers=headers,
                    json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                )
                assert response.status_code == 202
                response = await client.post(
                    "/mcp",
                    headers=headers,
                    json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                )
                assert response.status_code == 200
                assert "parse_ingredients" in response.text

                response = await client.post(
                    "/mcp",
                    headers=headers,
                    json={
                        "jsonrpc": "2.0",
                        "id": 3,
                        "method": "tools/call",
                        "params": {"name": "get_recipes", "arguments": {}},
                    },
                )
                assert response.status_code == 200
                event = next(
                    line[6:]
                    for line in response.text.splitlines()
                    if line.startswith("data: ")
                )
                result = json.loads(event)
                assert "error" not in result
                assert result["result"].get("isError") is not True

    assert sum(req.url.path == "/api/recipes" for req in requests) == 2
