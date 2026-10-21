"""Authenticate the configured credential without dictating administrator policy."""

from unittest.mock import patch
import httpx
import pytest
from mealie import MealieFetcher


@pytest.mark.parametrize(
    ("status", "payload"),
    [(401, {}), (403, {}), (200, {}), (200, []), (200, {"admin": "false"})],
)
@pytest.mark.parametrize("version", ["v3.28.0", "v3.29.0"])
def test_startup_rejects_invalid_or_malformed_identity(status, payload, version):
    client = httpx.Client(
        base_url="http://mealie.invalid",
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                status if r.url.path == "/api/users/self" else 200,
                json=(
                    payload
                    if r.url.path == "/api/users/self"
                    else {"version": version}
                ),
            )
        ),
    )
    with patch("mealie.client.httpx.Client", return_value=client):
        with pytest.raises((ValueError, httpx.HTTPStatusError)):
            MealieFetcher("http://mealie.invalid", "synthetic")
    assert client.is_closed


@pytest.mark.parametrize("admin", [False, True])
@pytest.mark.parametrize("version", ["v3.28.0", "v3.29.0"])
def test_valid_identity_keeps_existing_user_role_policy(admin, version):
    client = httpx.Client(
        base_url="http://mealie.invalid",
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json={"admin": admin} if r.url.path == "/api/users/self" else {"version": version})
        ),
    )
    with patch("mealie.client.httpx.Client", return_value=client):
        backend = MealieFetcher("http://mealie.invalid", "synthetic")
    assert not client.is_closed
    backend.close()
