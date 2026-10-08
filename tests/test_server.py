"""Startup and transport checks without a live Mealie instance."""

import json
import logging
import runpy
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import Mock, patch

import anyio
import httpx
import pytest


@pytest.fixture
def load_server(monkeypatch, request):
    monkeypatch.setenv("MEALIE_BASE_URL", "http://mealie.invalid")
    monkeypatch.setenv("MEALIE_API_KEY", "test-placeholder")
    for name in ("MCP_TRANSPORT", "MCP_HOST", "MCP_PORT", "MEALIE_ENABLE_AI_IMPORT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda: None)

    def load(health_status=200):
        requests = []

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
        factory = Mock(return_value=client)
        monkeypatch.setattr("mealie.client.httpx.Client", factory)
        namespace = runpy.run_module("server", run_name="transport_test_server")
        return namespace, client, requests, factory

    return load


async def test_import_and_discovery_need_no_configuration_or_network(load_server, monkeypatch):
    monkeypatch.delenv("MEALIE_BASE_URL")
    monkeypatch.delenv("MEALIE_API_KEY")
    dotenv = Mock()
    monkeypatch.setattr("dotenv.load_dotenv", dotenv)
    server, _, requests, factory = load_server()
    assert isinstance(server["mcp"], server["FastMCP"])
    assert await server["mcp"].list_tools()
    assert await server["mcp"].list_prompts()
    assert requests == []
    factory.assert_not_called()
    dotenv.assert_not_called()


def test_sdk_import_server_discovery_is_lazy(load_server, monkeypatch):
    from mcp.cli.cli import _import_server

    monkeypatch.delenv("MEALIE_BASE_URL")
    monkeypatch.delenv("MEALIE_API_KEY")
    _, _, requests, factory = load_server()
    discovered = _import_server(Path("src/server.py").resolve())
    assert discovered.name == "mealie"
    factory.assert_not_called()
    assert requests == []


def test_script_entry_point_uses_main_without_import_time_http(load_server):
    server, client, requests, factory = load_server()
    assert requests == []
    with patch.object(server["FastMCP"], "run", autospec=True) as run:
        runpy.run_path("src/server.py", run_name="__main__")
    run.assert_called_once()
    assert run.call_args.kwargs["transport"] == "stdio"
    assert requests[0].url.path == "/api/app/about"
    assert client.is_closed
    factory.assert_called_once()


@pytest.mark.parametrize("transport", [None, "sse", "streamable-http"])
def test_transport_selection(load_server, monkeypatch, transport):
    if transport:
        monkeypatch.setenv("MCP_TRANSPORT", transport)
        monkeypatch.setenv("MCP_HOST", "0.0.0.0")
        monkeypatch.setenv("MCP_PORT", "8766")

    server, client, requests, factory = load_server()
    with patch.object(server["FastMCP"], "run", autospec=True) as run:
        server["main"]()
    mcp = run.call_args.args[0]
    assert mcp.settings.host == ("0.0.0.0" if transport else "127.0.0.1")
    assert mcp.settings.port == (8766 if transport else 8765)
    run.assert_called_once_with(mcp, transport=transport or "stdio", mount_path=None)
    assert requests[0].url.path == "/api/app/about"
    factory.assert_called_once()
    assert client.is_closed


def server_lifespan(mcp, transport):
    if transport == "stdio":
        return mcp.settings.lifespan(mcp)
    app = mcp.sse_app() if transport == "sse" else mcp.streamable_http_app()
    return app.router.lifespan_context(app)


@pytest.mark.parametrize("transport", ["stdio", "sse", "streamable-http"])
async def test_startup_rejects_failed_health_check_and_closes(load_server, transport):
    server, client, requests, factory = load_server(health_status=503)
    with pytest.raises(httpx.HTTPStatusError):
        async with server_lifespan(server["mcp"], transport):
            pytest.fail("Unhealthy startup must not enter the running lifespan")
    assert requests[0].url.path == "/api/app/about"
    assert client.is_closed
    factory.assert_called_once()


@pytest.mark.parametrize("transport", ["stdio", "sse", "streamable-http"])
async def test_lifespan_closes_on_normal_shutdown(load_server, transport):
    server, client, requests, factory = load_server()
    async with server_lifespan(server["mcp"], transport):
        assert not client.is_closed
        assert requests[0].url.path == "/api/app/about"
    assert client.is_closed
    factory.assert_called_once()


async def test_lifespan_closes_when_running_server_fails(load_server):
    server, client, _, _ = load_server()
    with pytest.raises(RuntimeError, match="synthetic failure"):
        async with server_lifespan(server["mcp"], "stdio"):
            raise RuntimeError("synthetic failure")
    assert client.is_closed


async def test_stdio_eof_runs_health_check_and_closes_client(load_server, monkeypatch):
    server, client, requests, factory = load_server()

    @asynccontextmanager
    async def empty_stdio():
        input_send, input_receive = anyio.create_memory_object_stream()
        output_send, output_receive = anyio.create_memory_object_stream()
        async with input_send, input_receive, output_send, output_receive:
            await input_send.aclose()
            yield input_receive, output_send

    monkeypatch.setattr("mcp.server.fastmcp.server.stdio_server", empty_stdio)
    await server["mcp"].run_stdio_async()
    assert requests[0].url.path == "/api/app/about"
    factory.assert_called_once()
    assert client.is_closed


async def test_http_client_survives_individual_mcp_sessions(load_server):
    server, client, _, factory = load_server()
    mcp = server["mcp"]
    async with server_lifespan(mcp, "streamable-http"):
        for _ in range(2):
            async with mcp.settings.lifespan(mcp):
                assert not client.is_closed
            assert not client.is_closed
        factory.assert_called_once()
    assert client.is_closed


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("MEALIE_BASE_URL", ""),
        ("MEALIE_API_KEY", ""),
        ("MCP_TRANSPORT", "unsupported"),
        ("MCP_PORT", "not-a-port"),
        ("MCP_PORT", "0"),
        ("MCP_PORT", "65536"),
        ("MEALIE_ENABLE_AI_IMPORT", "yes"),
        ("MEALIE_ENABLE_AI_IMPORT", ""),
    ],
)
def test_invalid_configuration_fails_before_http_allocation(load_server, monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    server, _, requests, factory = load_server()
    with pytest.raises(ValueError):
        server["main"]()
    assert requests == []
    factory.assert_not_called()


@pytest.mark.parametrize("value,enabled", [("true", True), ("TRUE", True), ("false", False), ("False", False)])
@pytest.mark.parametrize("transport", ["stdio", "sse", "streamable-http"])
async def test_ai_import_lazy_runtime_registration(load_server, monkeypatch, value, enabled, transport):
    monkeypatch.setenv("MEALIE_ENABLE_AI_IMPORT", value)
    namespace, _, requests, factory = load_server()
    mcp = namespace["mcp"]
    assert len(await mcp.list_tools()) == 75
    factory.assert_not_called()
    assert requests == []
    async with server_lifespan(mcp, transport):
        tools = await mcp.list_tools()
        assert len(tools) == (76 if enabled else 75)
        assert ("import_recipe_with_ai" in {t.name for t in tools}) is enabled
        async with mcp.settings.lifespan(mcp):
            assert len(await mcp.list_tools()) == len(tools)
    factory.assert_called_once()


@pytest.mark.parametrize("enabled", [False, True])
async def test_ai_import_explicit_configuration_discovery(load_server, enabled):
    namespace, _, requests, factory = load_server()
    config = namespace["ServerConfig"]("http://mealie.invalid", "placeholder", enable_ai_import=enabled)
    mcp = namespace["create_server"](config)
    assert len(await mcp.list_tools()) == (76 if enabled else 75)
    factory.assert_not_called()
    assert requests == []


@pytest.mark.parametrize("transport", ["stdio", "sse", "streamable-http"])
async def test_invalid_ai_opt_in_fails_lazy_startup(load_server, monkeypatch, transport):
    monkeypatch.setenv("MEALIE_ENABLE_AI_IMPORT", "invalid")
    namespace, _, requests, factory = load_server()
    with pytest.raises(ValueError, match="MEALIE_ENABLE_AI_IMPORT"):
        async with server_lifespan(namespace["mcp"], transport):
            pytest.fail("Invalid opt-in must fail startup")
    factory.assert_not_called()
    assert requests == []


@pytest.mark.parametrize("transport", ["stdio", "sse", "streamable-http"])
async def test_ai_import_main_registration(load_server, monkeypatch, transport):
    monkeypatch.setenv("MEALIE_ENABLE_AI_IMPORT", "true")
    monkeypatch.setenv("MCP_TRANSPORT", transport)
    namespace, _, _, _ = load_server()
    with patch.object(namespace["FastMCP"], "run", autospec=True) as run:
        namespace["main"]()
    mcp = run.call_args.args[0]
    assert len(await mcp.list_tools()) == 76


@pytest.mark.parametrize(
    ("value", "expected"), [("debug", "DEBUG"), ("WARN", "WARNING"), ("root", "INFO"), ("NOTSET", "INFO")]
)
def test_log_level_is_applied_with_existing_handlers(load_server, monkeypatch, value, expected):
    monkeypatch.setenv("LOG_LEVEL", value)
    server, _, _, _ = load_server()
    with patch.object(server["FastMCP"], "run"):
        server["main"]()
    assert server["logger"].getEffectiveLevel() == getattr(server["logging"], expected)


async def test_debug_configuration_does_not_log_http_urls_or_queries(load_server, monkeypatch, caplog):
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    server, _, requests, _ = load_server()
    mcp = server["mcp"]
    with caplog.at_level(logging.DEBUG):
        async with server_lifespan(mcp, "stdio"):
            mcp.client_provider._handle_request(
                "GET", "/api/recipes", params={"search": "private-query-marker"}
            )
            assert server["logger"].getEffectiveLevel() == logging.DEBUG
            assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
            assert logging.getLogger("httpcore").getEffectiveLevel() >= logging.WARNING
    assert "private-query-marker" in str(requests[-1].url)
    assert "private-query-marker" not in caplog.text
    assert "mealie.invalid" not in caplog.text
    assert "HTTP Request:" not in caplog.text


def test_transport_failure_propagates_without_logging_exception_content(load_server, caplog):
    server, client, _, _ = load_server()
    with patch.object(server["FastMCP"], "run", side_effect=ValueError("Invalid transport")):
        with pytest.raises(ValueError, match="Invalid transport"):
            server["main"]()
    assert "Invalid transport" not in caplog.text
    assert "ValueError" in caplog.text
    assert client.is_closed


def test_main_health_failure_raises_before_http_runner(load_server, monkeypatch):
    monkeypatch.setenv("MCP_TRANSPORT", "streamable-http")
    server, client, _, _ = load_server(health_status=503)
    with patch.object(server["FastMCP"], "run") as run:
        with pytest.raises(httpx.HTTPStatusError):
            server["main"]()
    run.assert_not_called()
    assert client.is_closed


@pytest.mark.parametrize("enable_ai_import", [False, True])
async def test_http_sessions_initialize_list_and_call_tools(load_server, monkeypatch, enable_ai_import):
    # sse-starlette's global event must not retain a previous test's event loop.
    monkeypatch.setattr("sse_starlette.sse.AppStatus.should_exit_event", None)
    monkeypatch.setenv("MEALIE_ENABLE_AI_IMPORT", str(enable_ai_import).lower())
    server, mealie_client, requests, factory = load_server()
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
                assert ('"name":"import_recipe_with_ai"' in response.text) is enable_ai_import

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
    assert sum(req.url.path == "/api/app/about" for req in requests) == 1
    factory.assert_called_once()
    assert mealie_client.is_closed
