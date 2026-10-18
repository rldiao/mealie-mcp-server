"""Live-Mealie fixtures for the integration tests.

These tests are opt-in: they run only when MEALIE_INTEGRATION=1. By default a
disposable Mealie is started from docker-compose.yml next to this file and
removed afterwards. To reuse an instance instead, set MEALIE_INTEGRATION_URL
and MEALIE_INTEGRATION_API_KEY. Set MEALIE_INTEGRATION_KEEP=1 to leave the
container running after the session.

The root conftest's ``server`` and ``invoke`` fixtures build on ``fetcher``,
so overriding ``fetcher`` here runs the real MCP tools against live Mealie.
"""

import os
import subprocess
import uuid
from pathlib import Path

import httpx
import pytest

from mealie import MealieFetcher

COMPOSE_FILE = Path(__file__).with_name("docker-compose.yml")
ENABLED = os.getenv("MEALIE_INTEGRATION") == "1"


def pytest_collection_modifyitems(config, items):
    if ENABLED:
        return
    skip = pytest.mark.skip(reason="set MEALIE_INTEGRATION=1 to run live Mealie tests")
    here = Path(__file__).parent
    for item in items:
        if here in Path(item.fspath).parents:
            item.add_marker(skip)


def _compose(*args):
    subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), *args],
        check=True,
        capture_output=True,
    )


def _create_api_key(base_url):
    """Log in as Mealie's default admin and mint an API token."""
    with httpx.Client(base_url=base_url, timeout=30.0) as client:
        login = client.post(
            "/api/auth/token",
            data={
                "username": os.getenv("MEALIE_INTEGRATION_USER", "changeme@example.com"),
                "password": os.getenv("MEALIE_INTEGRATION_PASSWORD", "MyPassword"),
            },
        )
        login.raise_for_status()
        token = client.post(
            "/api/users/api-tokens",
            headers={"Authorization": f"Bearer {login.json()['access_token']}"},
            json={"name": f"mcp-integration-{uuid.uuid4().hex[:8]}"},
        )
        token.raise_for_status()
        return token.json()["token"]


@pytest.fixture(scope="session")
def mealie_instance():
    """(base_url, api_key) of a running Mealie."""
    url = os.getenv("MEALIE_INTEGRATION_URL")
    if url:
        key = os.getenv("MEALIE_INTEGRATION_API_KEY")
        if not key:
            pytest.fail("MEALIE_INTEGRATION_URL needs MEALIE_INTEGRATION_API_KEY")
        yield url.rstrip("/"), key
        return

    port = os.getenv("MEALIE_INTEGRATION_PORT", "9926")
    _compose("up", "-d", "--wait")
    try:
        base_url = f"http://127.0.0.1:{port}"
        yield base_url, _create_api_key(base_url)
    finally:
        if os.getenv("MEALIE_INTEGRATION_KEEP") != "1":
            _compose("down", "-v")


@pytest.fixture(scope="session")
def live_fetcher(mealie_instance):
    client = MealieFetcher(*mealie_instance)
    yield client
    client.close()


@pytest.fixture
def fetcher(live_fetcher):
    return live_fetcher


@pytest.fixture
def unique():
    """Per-test name suffix so tests never collide on a shared instance."""
    suffix = uuid.uuid4().hex[:8]
    return lambda name: f"{name} {suffix}"


@pytest.fixture
def cleanup():
    """Register callables to run after the test, newest first, ignoring errors."""
    actions = []
    yield actions.append
    for action in reversed(actions):
        try:
            action()
        except Exception:
            pass
