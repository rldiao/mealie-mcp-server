"""End-to-end checks of the OAuth-protected streamable HTTP endpoint.

The real server runs in-process behind `httpx.ASGITransport`; the identity
provider is `FakeOidc` and Mealie is `FakeMealie`, both over `MockTransport`.
"""

import asyncio
import itertools
import json
import logging
import runpy
from contextlib import asynccontextmanager
from types import SimpleNamespace

import httpx
import pytest
from mcp.server.fastmcp.exceptions import ToolError

from conftest import AUTH_VARIABLES, FakeMealie

PUBLIC_URL = "https://miam-mcp.example"
# Concurrent requests in one MCP session need distinct JSON-RPC ids: the
# transport routes each response to the stream registered under its id.
_REQUEST_IDS = itertools.count(2)
RP = {"MEALIE_AUTH_MODE": "reverse-proxy", "MEALIE_REVERSE_PROXY_SECRET": "proxy-secret-marker"}
INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1"},
    },
}


@pytest.fixture
def http_app(monkeypatch, oidc):
    @asynccontextmanager
    async def start(*, mealie_health: int = 200, **env):
        values = {
            "MEALIE_BASE_URL": "http://mealie.invalid",
            "MEALIE_API_KEY": FakeMealie.API_KEY,
            "MCP_TRANSPORT": "streamable-http",
            "MCP_HOST": "0.0.0.0",
            "MCP_AUTH_ISSUER": oidc.issuer,
            "MCP_AUTH_AUDIENCE": oidc.audience,
            "MCP_AUTH_REQUIRED_GROUP": "miam-contributors",
            "MCP_PUBLIC_URL": PUBLIC_URL,
            **env,
        }
        for name in ("MCP_PORT", "MEALIE_ENABLE_AI_IMPORT", "LOG_LEVEL", *AUTH_VARIABLES):
            monkeypatch.delenv(name, raising=False)
        for name, value in values.items():
            if value is None:
                monkeypatch.delenv(name, raising=False)
            else:
                monkeypatch.setenv(name, value)

        mealie = FakeMealie()
        mealie.health_status = mealie_health
        mealie.install(monkeypatch)

        original_async_client = httpx.AsyncClient

        class OidcAsyncClient(original_async_client):
            def __init__(self, *args, **kwargs):
                if kwargs.get("transport") is None:
                    kwargs["transport"] = oidc.transport
                super().__init__(*args, **kwargs)

        monkeypatch.setattr(httpx, "AsyncClient", OidcAsyncClient)
        monkeypatch.setattr("dotenv.load_dotenv", lambda: None)
        # sse-starlette's global event must not retain a previous test's event loop.
        monkeypatch.setattr("sse_starlette.sse.AppStatus.should_exit_event", None)

        namespace = runpy.run_module("server", run_name="auth_http_server")
        server = namespace["create_server"](namespace["ServerConfig"].from_environment())
        app = server.streamable_http_app()
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url=PUBLIC_URL
            ) as client:
                yield SimpleNamespace(client=client, oidc=oidc, mealie=mealie, server=server)

    return start


async def initialize(client, token) -> dict[str, str]:
    headers = {
        "Accept": "application/json, text/event-stream",
        "Authorization": f"Bearer {token}",
    }
    response = await client.post("/mcp", headers=headers, json=INITIALIZE)
    assert response.status_code == 200
    headers["Mcp-Session-Id"] = response.headers["mcp-session-id"]
    response = await client.post(
        "/mcp", headers=headers, json={"jsonrpc": "2.0", "method": "notifications/initialized"}
    )
    assert response.status_code == 202
    return headers


async def call_tool(client, headers, name, arguments=None, *, token=None) -> tuple[int, dict | None]:
    headers = dict(headers)
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    response = await client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": next(_REQUEST_IDS),
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        },
    )
    if response.status_code != 200:
        return response.status_code, None
    event = next(
        line[6:] for line in response.text.splitlines() if line.startswith("data: ")
    )
    return response.status_code, json.loads(event).get("result")


async def test_missing_token_is_challenged_with_resource_metadata(http_app):
    async with http_app() as app:
        response = await app.client.post("/mcp", json={})
        assert response.status_code == 401
        assert (
            'resource_metadata="https://miam-mcp.example/.well-known/oauth-protected-resource/mcp"'
            in response.headers["www-authenticate"]
        )
        metadata = await app.client.get("/.well-known/oauth-protected-resource/mcp")
        assert metadata.status_code == 200
        assert metadata.json()["resource"] == "https://miam-mcp.example/mcp"
        assert metadata.json()["authorization_servers"] == [app.oidc.issuer]


@pytest.mark.parametrize("claims", [{"aud": "other"}, {"groups": ["other"]}, {"exp": 1}])
async def test_rejected_tokens_get_401(http_app, claims):
    async with http_app() as app:  # oidc.userinfo stays None: no group from userinfo either
        response = await app.client.post(
            "/mcp",
            json=INITIALIZE,
            headers={
                "Accept": "application/json, text/event-stream",
                "Authorization": f"Bearer {app.oidc.token(**claims)}",
            },
        )
        assert response.status_code == 401


async def test_valid_token_calls_mealie_with_api_key(http_app):
    async with http_app() as app:
        # Host is miam-mcp.example with MCP_HOST=0.0.0.0: pins the § 10.3 finding
        headers = await initialize(app.client, app.oidc.token())
        status, result = await call_tool(app.client, headers, "get_recipes")
        assert status == 200 and result.get("isError") is not True
        assert "shared recipe" in json.dumps(result)
        assert app.mealie.requests[-1].headers["authorization"] == "Bearer api-key-marker"


async def test_other_user_cannot_use_session(http_app):
    async with http_app() as app:
        headers = await initialize(app.client, app.oidc.token())
        bob = app.oidc.token(sub="sub-bob", preferred_username="bob")
        before = len(app.mealie.requests)
        status, _ = await call_tool(app.client, headers, "get_recipes", token=bob)
        assert status == 404
        assert len(app.mealie.requests) == before


async def test_auth_logs_contain_no_tokens(http_app, caplog):
    with caplog.at_level(logging.DEBUG):
        async with http_app(LOG_LEVEL="DEBUG") as app:
            rejected, accepted = app.oidc.token(aud="other"), app.oidc.token()
            await app.client.post(
                "/mcp", json=INITIALIZE, headers={"Authorization": f"Bearer {rejected}"}
            )
            await call_tool(app.client, await initialize(app.client, accepted), "get_recipes")
    for secret in (rejected, accepted, "api-key-marker", "shared recipe", "sub-alice"):
        assert secret not in caplog.text


async def test_each_user_reaches_mealie_as_themselves(http_app):
    async with http_app(**RP) as app:
        alice = await initialize(app.client, app.oidc.token())
        bob = await initialize(app.client, app.oidc.token(sub="sub-bob", preferred_username="bob"))
        calls = [
            call_tool(app.client, alice if i % 2 == 0 else bob, "get_recipes") for i in range(20)
        ]
        results = await asyncio.gather(*calls)
        for i, (status, result) in enumerate(results):
            assert status == 200
            assert ("alice recipe" if i % 2 == 0 else "bob recipe") in json.dumps(result)
        assert len(app.mealie.exchanges) == 2


async def test_refreshed_token_keeps_session_and_identity(http_app):
    async with http_app(**RP) as app:
        headers = await initialize(app.client, app.oidc.token(jti="first"))
        status, result = await call_tool(
            app.client, headers, "get_recipes", token=app.oidc.token(jti="second")
        )
        assert status == 200 and "alice recipe" in json.dumps(result)


async def test_refreshed_token_uses_current_request_identity(http_app):
    async with http_app(**RP) as app:
        headers = await initialize(app.client, app.oidc.token())
        # Same sub keeps the SDK session; only the current request names bob.
        status, result = await call_tool(
            app.client,
            headers,
            "get_recipes",
            token=app.oidc.token(preferred_username="bob"),
        )
        assert status == 200 and "bob recipe" in json.dumps(result)
        recipes = [r for r in app.mealie.requests if r.url.path == "/api/recipes"]
        assert recipes and app.mealie.user_of(recipes[-1]) == "bob"


async def test_unknown_mealie_account_gets_readable_tool_error(http_app):
    async with http_app(**RP) as app:
        headers = await initialize(
            app.client, app.oidc.token(sub="sub-carol", preferred_username="carol")
        )
        status, result = await call_tool(app.client, headers, "get_recipes")
        assert status == 200 and result["isError"] is True
        assert "sign in to Mealie once" in result["content"][0]["text"]


async def test_tools_refuse_without_authenticated_user(http_app):
    async with http_app(**RP) as app:  # call outside any HTTP request: no user
        with pytest.raises(ToolError, match="authenticated user"):
            await app.server.call_tool("get_recipes", {})
        assert app.mealie.exchanges == []


async def test_reverse_proxy_startup_rejects_failed_health_check(http_app):
    with pytest.raises(httpx.HTTPStatusError):
        async with http_app(mealie_health=503, **RP):
            pytest.fail("Unhealthy startup must not enter the running lifespan")


async def test_reverse_proxy_checks_health_once_and_closes_clients(http_app):
    async with http_app(**RP) as app:
        for token in (app.oidc.token(), app.oidc.token(sub="sub-bob", preferred_username="bob")):
            status, result = await call_tool(
                app.client, await initialize(app.client, token), "get_recipes"
            )
            assert status == 200 and result.get("isError") is not True
        health = [r for r in app.mealie.requests if r.url.path == "/api/app/about"]
        assert len(health) == 1
        assert all(
            r.headers["authorization"] != "Bearer api-key-marker"
            for r in app.mealie.requests
            if "authorization" in r.headers
        )
    assert app.mealie.clients and all(client.is_closed for client in app.mealie.clients)


async def test_reverse_proxy_logs_contain_no_identity_or_secret(http_app, caplog):
    issued_oidc_tokens = []
    with caplog.at_level(logging.DEBUG):
        async with http_app(LOG_LEVEL="DEBUG", **RP) as app:
            alice_token = app.oidc.token()
            carol_token = app.oidc.token(sub="sub-carol", preferred_username="carol")
            issued_oidc_tokens += [alice_token, carol_token]
            status, result = await call_tool(
                app.client, await initialize(app.client, alice_token), "get_recipes"
            )
            assert status == 200 and "alice recipe" in json.dumps(result)
            status, result = await call_tool(
                app.client, await initialize(app.client, carol_token), "get_recipes"
            )
            assert status == 200 and result["isError"] is True
    for secret in (
        "proxy-secret-marker",
        "mealie-alice",
        "alice recipe",
        "alice",
        "carol",
        *issued_oidc_tokens,
    ):
        assert secret not in caplog.text
