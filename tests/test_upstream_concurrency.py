"""Focused upstream regressions; no live service or credentials required."""

import asyncio
import json
import threading
from contextlib import contextmanager
from unittest.mock import patch
import httpx
from mealie import MealieFetcher
from server import ServerConfig, create_server


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


async def test_sync_tools_overlap_without_blocking_loop_and_limit_workers():
    # A blocking implementation cannot start two workers or run the ticker.
    import anyio
    from server import _MealieServer

    mcp = _MealieServer(None)
    release = threading.Event()
    four_started = threading.Event()
    lock = threading.Lock()
    active = peak = 0

    @mcp.tool()
    def slow(value: int) -> int:
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
            if active == 4:
                four_started.set()
        assert release.wait(3)
        with lock:
            active -= 1
        return value

    progress = []

    async def ticker():
        await anyio.sleep(0.02)
        progress.append(not release.is_set())

    # Timer bounds failure even if the event loop is blocked by the broken code.
    timer = threading.Timer(0.4, release.set)
    timer.start()
    try:
        await asyncio.gather(
            *(mcp.call_tool("slow", {"value": n}) for n in range(6)), ticker()
        )
    finally:
        release.set()
        timer.join()
    assert peak == 4
    assert four_started.is_set()
    assert progress == [True]


async def test_wrapper_preserves_tool_catalogue_and_returns_original_function(fetcher):
    from mcp.server.fastmcp import FastMCP
    from server import _MealieServer
    from tools import register_all_tools

    plain, wrapped = FastMCP("plain"), _MealieServer(None)
    for mcp in (plain, wrapped):
        register_all_tools(mcp, fetcher, enable_ai_import=True)
    assert [t.model_dump_json() for t in await plain.list_tools()] == [
        t.model_dump_json() for t in await wrapped.list_tools()
    ]

    def original(value: int) -> int:
        return value

    assert wrapped.tool()(original) is original


async def test_cancelled_scope_waits_for_worker_before_client_close():
    import anyio
    from server import _MealieServer

    mcp = _MealieServer(None)
    entered, release = threading.Event(), threading.Event()
    events = []

    @mcp.tool()
    def slow() -> str:
        entered.set()
        assert release.wait(3)
        events.append("worker-finished")
        return "done"

    async def caller():
        await mcp.call_tool("slow", {})

    timer = threading.Timer(0.3, release.set)
    timer.start()
    try:
        async with anyio.create_task_group() as tg:
            tg.start_soon(caller)
            with anyio.fail_after(2):
                while not entered.is_set():
                    await anyio.sleep(0.01)
            tg.cancel_scope.cancel()
        events.append("client-close-safe")
    finally:
        release.set()
        timer.join()
    assert events == ["worker-finished", "client-close-safe"]


async def test_http_initialize_progresses_while_sync_tool_is_waiting():
    import anyio

    entered, release = threading.Event(), threading.Event()

    def respond(request):
        if request.url.path == "/api/app/about":
            return httpx.Response(200, json={"version": "v3.28.0"})
        if request.url.path == "/api/users/self":
            return httpx.Response(200, json={"admin": False})
        entered.set()
        assert release.wait(3)
        return httpx.Response(200, json={"items": [], "total": 0})

    api = httpx.Client(
        base_url="http://mealie.invalid", transport=httpx.MockTransport(respond)
    )
    mcp = create_server(ServerConfig("http://mealie.invalid", "synthetic"))
    app = mcp.streamable_http_app()
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1"},
        },
    }
    headers = {"Accept": "application/json, text/event-stream"}
    timer = threading.Timer(0.8, release.set)
    timer.start()
    try:
        with patch("mealie.client.httpx.Client", return_value=api):
            async with app.router.lifespan_context(app):
                async with httpx.AsyncClient(
                    base_url="http://127.0.0.1:8765", transport=httpx.ASGITransport(app)
                ) as http:
                    first = await http.post("/mcp", json=body, headers=headers)
                    session = dict(
                        headers, **{"Mcp-Session-Id": first.headers["Mcp-Session-Id"]}
                    )
                    await http.post(
                        "/mcp",
                        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                        headers=session,
                    )
                    call = asyncio.create_task(
                        http.post(
                            "/mcp",
                            json={
                                "jsonrpc": "2.0",
                                "id": 2,
                                "method": "tools/call",
                                "params": {"name": "get_recipes", "arguments": {}},
                            },
                            headers=session,
                        )
                    )
                    try:
                        with anyio.fail_after(2):
                            while not entered.is_set():
                                await anyio.sleep(0.01)
                        assert not release.is_set()
                        health = await http.post("/mcp", json=body, headers=headers)
                        assert health.status_code == 200
                        assert not release.is_set()
                        await http.delete(
                            "/mcp",
                            headers=dict(
                                headers,
                                **{"Mcp-Session-Id": health.headers["Mcp-Session-Id"]}
                            ),
                        )
                    finally:
                        release.set()
                        assert (await call).status_code == 200
                    await http.delete("/mcp", headers=session)
        assert api.is_closed
    finally:
        release.set()
        timer.join()


async def test_parallel_recipe_writes_preserve_both_successful_changes():
    from copy import deepcopy

    state = {
        "slug": "r",
        "name": "r",
        "recipeServings": 2,
        "recipeIngredient": [],
        "recipeInstructions": [],
        "settings": {},
    }
    patched = threading.Event()

    def respond(request):
        if request.method == "GET":
            snapshot = deepcopy(state)
            patched.wait(0.2)  # Force the old implementation to read stale state.
            return httpx.Response(200, json=snapshot)
        body = json.loads(request.content)
        if request.method == "PATCH":
            state.update(body)
            patched.set()
        else:
            state.clear()
            state.update(body)
        return httpx.Response(200, json=state)

    with real_backend(respond) as (backend, requests):
        mcp = create_server(ServerConfig("http://mealie.invalid", "synthetic"))
        mcp.client_provider._client = backend
        await asyncio.gather(
            mcp.call_tool(
                "update_recipe", {"slug": "r", "ingredients": ["synthetic rice"]}
            ),
            mcp.call_tool("update_recipe", {"slug": "r", "servings": 4}),
        )
        assert state["recipeServings"] == 4
        assert state["recipeIngredient"][0]["note"] == "synthetic rice"


async def test_reads_progress_while_short_write_holds_its_lock():
    import anyio

    entered, release = threading.Event(), threading.Event()

    def respond(request):
        if request.url.path.endswith("/writing") and request.method == "GET":
            entered.set()
            assert release.wait(3)
        return httpx.Response(200, json={"name": "synthetic", "slug": "writing"})

    with real_backend(respond) as (backend, requests):
        mcp = create_server(ServerConfig("http://mealie.invalid", "synthetic"))
        mcp.client_provider._client = backend
        timer = threading.Timer(0.8, release.set)
        timer.start()
        try:
            write = asyncio.create_task(
                mcp.call_tool(
                    "update_recipe", {"slug": "writing", "ingredients": ["synthetic"]}
                )
            )
            with anyio.fail_after(2):
                while not entered.is_set():
                    await anyio.sleep(0.01)
            await mcp.call_tool("get_recipe", {"slug": "reading"})
            assert not release.is_set()
            release.set()
            await write
        finally:
            release.set()
            timer.join()


async def test_all_registered_tools_have_action_annotations(fetcher):
    from server import _MealieServer
    from tools import register_all_tools

    mcp = _MealieServer(None)
    register_all_tools(mcp, fetcher, enable_ai_import=True)
    tools = {t.name: t for t in await mcp.list_tools()}
    assert all(t.annotations is not None for t in tools.values())
    assert tools["get_recipe"].annotations.readOnlyHint is True
    assert tools["update_recipe"].annotations.destructiveHint is True
    assert tools["create_recipe"].annotations.openWorldHint is True
    assert tools["set_recipe_image_from_url"].annotations.destructiveHint is True
    assert tools["upload_recipe_image_file"].annotations.readOnlyHint is False
    assert tools["upload_recipe_asset_file"].annotations.readOnlyHint is False
