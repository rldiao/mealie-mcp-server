"""End-to-end checks of the OAuth-protected streamable HTTP endpoint.

The real server runs in-process behind `httpx.ASGITransport`; the identity
provider is `FakeOidc` and Mealie is `FakeMealie`, both over `MockTransport`.
"""

import json
import logging
import runpy
from contextlib import asynccontextmanager
from types import SimpleNamespace

import httpx
import pytest

from conftest import FakeMealie

PUBLIC_URL = "https://miam-mcp.example"
AUTH_VARIABLES = (
    "MCP_AUTH_ISSUER",
    "MCP_AUTH_AUDIENCE",
    "MCP_AUTH_REQUIRED_GROUP",
    "MCP_AUTH_USERNAME_CLAIM",
    "MCP_PUBLIC_URL",
    "MEALIE_AUTH_MODE",
    "MEALIE_REVERSE_PROXY_SECRET",
    "MEALIE_REVERSE_PROXY_USER_HEADER",
    "MEALIE_REVERSE_PROXY_SECRET_HEADER",
)
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
            "id": 2,
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
        async with http_app() as app:
            rejected, accepted = app.oidc.token(aud="other"), app.oidc.token()
            await app.client.post(
                "/mcp", json=INITIALIZE, headers={"Authorization": f"Bearer {rejected}"}
            )
            await call_tool(app.client, await initialize(app.client, accepted), "get_recipes")
    for secret in (rejected, accepted, "api-key-marker", "shared recipe", "sub-alice"):
        assert secret not in caplog.text
