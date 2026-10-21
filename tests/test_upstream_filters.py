"""Focused upstream regressions; no live service or credentials required."""

from contextlib import contextmanager
from unittest.mock import patch
import httpx
import pytest
from mealie import MealieFetcher


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


@pytest.mark.parametrize("tags", [["quick", "vegan"], []])
def test_filter_arrays_use_repeated_query_parameters(tags):
    with real_backend() as (backend, requests):
        backend.get_recipes(tags=tags)
        assert requests[-1].url.params.get_list("tags") == tags
