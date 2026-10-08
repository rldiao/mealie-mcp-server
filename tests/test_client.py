"""HTTP transport behavior, privacy, and ownership without network access."""

import logging
from unittest.mock import Mock

import httpx
import pytest

from mealie.client import MealieApiError, MealieClient


@pytest.fixture
def make_client(monkeypatch, request):
    def make(response=None, failure=None, health_failure=None):
        requests = []

        def respond(api_request):
            requests.append(api_request)
            if api_request.url.path == "/api/app/about":
                if health_failure:
                    if isinstance(health_failure, Exception):
                        raise health_failure
                    return httpx.Response(health_failure)
                return httpx.Response(200, json={})
            if failure:
                raise failure
            return response if response is not None else httpx.Response(200, json={})

        http_client = httpx.Client(
            base_url="https://private-host.invalid",
            transport=httpx.MockTransport(respond),
        )
        request.addfinalizer(http_client.close)
        factory = Mock(return_value=http_client)
        monkeypatch.setattr("mealie.client.httpx.Client", factory)
        return http_client, factory, requests

    return make


def test_initialization_sets_authentication_and_timeout(make_client):
    _, factory, requests = make_client()
    client = MealieClient("https://private-host.invalid", "synthetic-key")
    assert factory.call_args.kwargs["headers"] == {
        "Authorization": "Bearer synthetic-key"
    }
    assert factory.call_args.kwargs["timeout"] == 30.0
    assert requests[0].url.path == "/api/app/about"
    client.close()


@pytest.mark.parametrize("payload", [{"detail": "private-response"}, "private-response"])
def test_http_errors_never_log_content_or_include_it_in_message(make_client, caplog, payload):
    response = (
        httpx.Response(422, json=payload)
        if isinstance(payload, dict)
        else httpx.Response(422, text=payload)
    )
    make_client(response=response)
    with caplog.at_level(logging.DEBUG):
        client = MealieClient("https://private-host.invalid", "synthetic-key")
        with pytest.raises(MealieApiError) as caught:
            client._handle_request(
                "POST",
                "/api/private-path",
                params={"search": "private-query"},
                json={"name": "private-request"},
            )
    assert caught.value.status_code == 422
    assert "private-response" in caught.value.response_text
    assert "private-response" not in str(caught.value)
    assert "/api/private-path" not in str(caught.value)
    for marker in (
        "private-host", "synthetic-key", "private-path", "private-query",
        "private-request", "private-response",
    ):
        assert marker not in caplog.text
    assert "422" in caplog.text
    assert all(record.exc_info is None for record in caplog.records)


@pytest.mark.parametrize(
    "error_type",
    [httpx.ReadTimeout, httpx.ConnectTimeout, httpx.WriteTimeout, httpx.PoolTimeout],
)
def test_all_timeouts_are_normalized(make_client, caplog, error_type):
    make_client(failure=error_type("private-transport-message"))
    client = MealieClient("https://private-host.invalid", "synthetic-key")
    with pytest.raises(TimeoutError, match="Mealie API request timed out") as caught:
        client._handle_request("GET", "/api/private-path")
    assert caught.value.__suppress_context__
    assert "private-transport-message" not in caplog.text
    assert "private-path" not in caplog.text


@pytest.mark.parametrize("error_type", [httpx.ConnectError, httpx.RemoteProtocolError])
def test_request_failures_are_normalized(make_client, caplog, error_type):
    make_client(failure=error_type("private-transport-message"))
    client = MealieClient("https://private-host.invalid", "synthetic-key")
    with pytest.raises(ConnectionError, match="Could not communicate"):
        client._handle_request("GET", "/api/private-path")
    assert "private-transport-message" not in caplog.text


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (503, httpx.HTTPStatusError),
        (httpx.ConnectTimeout("private-health-failure"), TimeoutError),
        (httpx.ConnectError("private-health-failure"), ConnectionError),
        (RuntimeError("private-health-failure"), RuntimeError),
    ],
)
def test_failed_health_checks_close_client(make_client, caplog, failure, expected):
    http_client, _, _ = make_client(health_failure=failure)
    with pytest.raises(expected):
        MealieClient("https://private-host.invalid", "synthetic-key")
    assert http_client.is_closed
    assert "private-health-failure" not in caplog.text
    assert "private-host" not in caplog.text


@pytest.mark.parametrize(
    ("status", "content"), [(204, b""), (200, b""), (200, b"null"), (200, b" \n")]
)
def test_empty_delete_responses_remain_successful(make_client, status, content):
    make_client(response=httpx.Response(status, content=content))
    client = MealieClient("https://private-host.invalid", "synthetic-key")
    assert client._handle_request("DELETE", "/api/items/1") == {
        "success": True, "message": "Operation completed successfully"
    }


@pytest.mark.parametrize("payload", [{"items": []}, ["one"], "slug", True, 3])
def test_successful_json_is_preserved(make_client, payload):
    make_client(response=httpx.Response(200, json=payload))
    client = MealieClient("https://private-host.invalid", "synthetic-key")
    assert client._handle_request("GET", "/api/items") == payload


def test_json_and_multipart_headers_are_safe(make_client):
    _, _, requests = make_client()
    client = MealieClient("https://private-host.invalid", "synthetic-key")
    headers = {"X-Test": "value"}
    client._handle_request("POST", "/api/items", json={"value": 1}, headers=headers)
    assert headers == {"X-Test": "value"}
    assert requests[-1].headers["content-type"] == "application/json"
    client._handle_request("POST", "/api/items", files={"file": ("test.txt", b"test")})
    assert requests[-1].headers["content-type"].startswith("multipart/form-data; boundary=")


def test_unexpected_failures_propagate_without_logging_content(make_client, caplog):
    failure = RuntimeError("private-programming-failure")
    make_client(failure=failure)
    client = MealieClient("https://private-host.invalid", "synthetic-key")
    with pytest.raises(RuntimeError) as caught:
        client._handle_request("GET", "/api/items")
    assert caught.value is failure
    assert "private-programming-failure" not in caplog.text


@pytest.mark.parametrize("with_images", [False, True])
def test_ai_import_wire_encoding_and_timeout(make_client, monkeypatch, with_images):
    from email.parser import BytesParser
    from urllib.parse import parse_qs

    from mealie import MealieFetcher

    http_client, _, requests = make_client(response=httpx.Response(201, json="recipe"))
    http_client.timeout = httpx.Timeout(30.0)
    client = MealieFetcher("https://private-host.invalid", "synthetic-key")
    monkeypatch.setattr(client, "get_current_group", lambda: {
        "aiProviderSettings": {
            "aiEnabled": True, "imageProviderEnabled": True, "audioProviderEnabled": False
        }
    })
    images = [("same.jpg", b"first"), ("same.jpg", b"second")] if with_images else None
    assert client.import_recipe_with_ai(
        content="source", url="https://example.com/recipe", images=images,
        translate_language="French", create_new_organizers=True,
    ) == "recipe"
    request = requests[-1]
    assert request.method == "POST"
    assert request.url.path == "/api/recipes/create/ai"
    assert request.extensions["timeout"] == {
        "connect": 30.0, "read": 300.0, "write": 30.0, "pool": 30.0
    }
    expected = {
        "content": "source", "url": "https://example.com/recipe",
        "translateLanguage": "French", "createNewOrganizers": "true",
    }
    if with_images:
        content_type = request.headers["content-type"]
        assert content_type.startswith("multipart/form-data; boundary=")
        message = BytesParser().parsebytes(
            f"Content-Type: {content_type}\r\n\r\n".encode() + request.content
        )
        parts = message.get_payload()
        assert {
            part.get_param("name", header="content-disposition"): part.get_payload(decode=True).decode()
            for part in parts if not part.get_filename()
        } == expected
        files = [part for part in parts if part.get_filename()]
        assert [part.get_param("name", header="content-disposition") for part in files] == ["images", "images"]
        assert [part.get_filename() for part in files] == ["0-same.jpg", "1-same.jpg"]
        assert [part.get_payload(decode=True) for part in files] == [b"first", b"second"]
    else:
        assert request.headers["content-type"] == "application/x-www-form-urlencoded"
        assert parse_qs(request.content.decode()) == {key: [value] for key, value in expected.items()}
    client.get_recipes()
    assert requests[-1].extensions["timeout"]["read"] == 30.0
