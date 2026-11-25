"""Reverse-proxy sign-in exchange and per-user client pool, against FakeMealie."""

import logging

import httpx
import pytest

from conftest import FakeMealie
from mealie.client import MealieApiError
from mealie.reverse_proxy import (
    MealieAccountUnavailable,
    MealieToken,
    ReverseProxyClientPool,
    ReverseProxyConfig,
)

URL = "http://mealie.invalid"
EXCHANGE_ROUTE = ("GET", "/api/auth/reverse-proxy")


@pytest.fixture
def mealie(monkeypatch):
    fake = FakeMealie()
    fake.install(monkeypatch)
    return fake


@pytest.fixture
def now():
    return [0.0]


@pytest.fixture
def make_pool(mealie, now, request):
    def make(config=None, **kwargs):
        pool = ReverseProxyClientPool(
            URL, config or ReverseProxyConfig(mealie.secret), clock=lambda: now[0], **kwargs
        )
        request.addfinalizer(pool.close)
        return pool

    return make


@pytest.fixture
def pool(make_pool):
    return make_pool()


def test_exchange_sends_user_and_secret_headers(mealie, pool):
    pool.get("alice")
    request = mealie.exchanges[0]
    assert (request.method, request.url.path) == ("GET", "/api/auth/reverse-proxy")
    assert request.headers["x-forwarded-user"] == "alice"
    assert request.headers["x-mealie-reverse-proxy-secret"] == mealie.secret


def test_exchange_uses_configured_header_names(mealie, make_pool):
    mealie.user_header, mealie.secret_header = "X-User", "X-Secret"
    pool = make_pool(ReverseProxyConfig(mealie.secret, "X-User", "X-Secret"))
    pool.get("alice")
    headers = mealie.exchanges[0].headers
    assert headers["x-user"] == "alice" and headers["x-secret"] == mealie.secret
    assert "x-forwarded-user" not in headers
    assert "x-mealie-reverse-proxy-secret" not in headers


def test_unknown_account_raises_readable_error_and_is_not_cached(mealie, pool):
    with pytest.raises(MealieAccountUnavailable, match="sign in to Mealie once"):
        pool.get("carol")
    with pytest.raises(MealieAccountUnavailable):
        pool.get("carol")
    assert len(mealie.exchanges) == 2


def test_non_ascii_username_fails_readably_without_exchange(mealie, pool):
    with pytest.raises(ValueError, match="requires an ASCII username") as error:
        pool.get("hélène")
    assert "hél" not in str(error.value)
    assert mealie.exchanges == []


def test_account_unavailable_is_a_value_error():
    assert issubclass(MealieAccountUnavailable, ValueError)


def test_exchange_server_error_has_status_without_body(mealie, pool):
    mealie.exchange_status = 503
    with pytest.raises(MealieApiError) as error:
        pool.get("alice")
    assert error.value.status_code == 503 and error.value.response_text is None


@pytest.mark.parametrize(
    "body",
    [
        {"access_token": "", "expires_in": 10},
        {"access_token": "t"},
        {"access_token": "t", "expires_in": 0},
        {"access_token": "t", "expires_in": "10"},
        ["x"],
    ],
)
def test_unexpected_exchange_body_is_rejected(mealie, pool, body):
    mealie.routes[EXCHANGE_ROUTE] = lambda request: httpx.Response(200, json=body)
    with pytest.raises(ValueError, match="unexpected response"):
        pool.get("alice")


@pytest.mark.parametrize(
    "failure,expected",
    [
        (httpx.ReadTimeout("slow"), TimeoutError),
        (httpx.ConnectError("down"), ConnectionError),
    ],
)
def test_exchange_transport_failures_are_normalized(mealie, pool, failure, expected):
    def fail(request):
        raise failure

    mealie.routes[EXCHANGE_ROUTE] = fail
    with pytest.raises(expected):
        pool.get("alice")


def test_client_is_reused_case_insensitively(mealie, pool):
    assert pool.get("alice") is pool.get("Alice ")
    assert len(mealie.exchanges) == 1


def test_expired_client_is_replaced_and_closed(mealie, pool, now):
    first = pool.get("alice")
    now[0] += 172800 - 299
    second = pool.get("alice")
    assert second is not first and first._client.is_closed and len(mealie.exchanges) == 2


def test_unauthorized_call_reexchanges_once(mealie, pool):
    fetcher = pool.get("alice")
    mealie.revoke("alice")
    assert fetcher.get_recipes()["items"][0]["name"] == "alice recipe"
    assert len(mealie.exchanges) == 2
    mealie.reject_all("alice")
    with pytest.raises(MealieApiError) as error:
        fetcher.get_recipes()
    assert error.value.status_code == 401 and len(mealie.exchanges) == 3


def test_non_401_errors_do_not_reexchange(mealie, pool):
    fetcher = pool.get("alice")
    mealie.routes[("GET", "/api/recipes")] = lambda request: httpx.Response(500)
    with pytest.raises(MealieApiError) as error:
        fetcher.get_recipes()
    assert error.value.status_code == 500 and len(mealie.exchanges) == 1


def test_two_users_never_share_tokens(mealie, pool):
    alice, bob = pool.get("alice"), pool.get("bob")
    for fetcher in (alice, bob, alice, bob):
        fetcher.get_recipes()
    recipe_requests = [r for r in mealie.requests if r.url.path == "/api/recipes"]
    assert len(recipe_requests) == 4
    for request in recipe_requests:
        user = mealie.user_of(request)
        assert request.headers["authorization"].startswith(f"Bearer mealie-{user}-")


def test_exchange_does_not_forward_cookies(mealie, pool):
    pool.get("alice")
    pool.get("bob")
    assert "cookie" not in mealie.exchanges[1].headers


def test_least_recently_used_client_is_evicted_and_closed(mealie, make_pool):
    pool = make_pool(max_clients=1)
    alice = pool.get("alice")
    pool.get("bob")
    assert alice._client.is_closed
    assert pool.get("alice") is not alice
    assert len(mealie.exchanges) == 3


def test_close_closes_every_client(mealie, pool):
    pool.get("alice")
    pool.get("bob")
    pool.close()
    assert all(client.is_closed for client in mealie.clients)
    with pytest.raises(RuntimeError):
        pool.get("alice")


def test_pool_startup_fails_on_unhealthy_mealie(mealie):
    mealie.health_status = 503
    with pytest.raises(httpx.HTTPStatusError):
        ReverseProxyClientPool(URL, ReverseProxyConfig(mealie.secret))
    assert mealie.exchanges == [] and all(client.is_closed for client in mealie.clients)


def test_failures_log_no_username_secret_or_token(mealie, pool, caplog):
    caplog.set_level(logging.DEBUG)
    with pytest.raises(MealieAccountUnavailable):
        pool.get("carol")
    mealie.exchange_status = 503
    with pytest.raises(MealieApiError):
        pool.get("alice")
    logged = "\n".join(
        f"{record.getMessage()} {record.exc_text or ''}" for record in caplog.records
    )
    assert "Exchanging Mealie reverse-proxy token" in logged
    for forbidden in ("carol", "alice", mealie.secret, "mealie-"):
        assert forbidden not in logged


def test_config_and_token_hide_secrets():
    assert "s3cret" not in repr(ReverseProxyConfig("s3cret"))
    assert "tok" not in repr(MealieToken("tok", 1.0))
