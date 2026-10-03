import logging

import httpx
import pytest
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import BaseModel, field_validator

from mealie.client import MealieApiError
from tools.errors import tool_error_boundary


@pytest.mark.parametrize(
    "error",
    [
        MealieApiError(503, "private-client-error", "private-body"),
        httpx.ConnectTimeout("private-client-error"),
        httpx.RemoteProtocolError("private-client-error"),
        TimeoutError("private-client-error"),
        ConnectionError("private-client-error"),
        FileNotFoundError("private-file-path"),
        PermissionError("private-file-path"),
        IsADirectoryError("private-file-path"),
        NotADirectoryError("private-file-path"),
    ],
)
def test_expected_failures_preserve_prefix_without_sensitive_content(error, caplog):
    with pytest.raises(ToolError, match="Error fetching foods") as caught:
        with tool_error_boundary("Error fetching foods"):
            raise error
    assert "private-" not in caplog.text
    assert "private-" not in str(caught.value)
    assert type(error).__name__ in caplog.text
    assert all(record.exc_info is None for record in caplog.records)
    assert caught.value.__suppress_context__


@pytest.mark.parametrize(
    "message",
    [
        "parser must be one of nlp, brute",
        "Ingredient cannot be empty",
        "Ingredients cannot be empty",
    ],
)
def test_input_validation_retains_actionable_messages_without_logging_them(message, caplog):
    with pytest.raises(ToolError, match=message):
        with tool_error_boundary("Error parsing ingredient"):
            raise ValueError(message)
    assert message not in caplog.text


def test_pydantic_validation_excludes_input_and_custom_messages(caplog):
    class Input(BaseModel):
        name: str

        @field_validator("name")
        @classmethod
        def reject(cls, value):
            raise ValueError(f"private-value: {value}")

    with pytest.raises(ToolError, match="Invalid input") as caught:
        with tool_error_boundary("Error validating input"):
            Input(name="private-input")
    assert "private-" not in str(caught.value)
    assert "private-" not in caplog.text
    assert "value_error" in str(caught.value)


def test_http_status_error_is_sanitized(caplog):
    request = httpx.Request("GET", "https://private-host.invalid/private-path")
    response = httpx.Response(404, text="private-body", request=request)
    with pytest.raises(ToolError, match="HTTP 404"):
        with tool_error_boundary("Error fetching recipe"):
            response.raise_for_status()
    assert "404" in caplog.text
    assert "private-" not in caplog.text


def test_explicit_partial_progress_tool_error_is_not_masked(caplog):
    error = ToolError("Created recipe synthetic-id; retry the remaining update")
    with pytest.raises(ToolError) as caught:
        with tool_error_boundary("Error creating recipe"):
            raise error
    assert caught.value is error
    assert not caplog.records


@pytest.mark.parametrize("error", [RuntimeError("unexpected"), TypeError("unexpected")])
def test_unexpected_failures_propagate(error, caplog):
    with pytest.raises(type(error)) as caught:
        with tool_error_boundary("Error creating recipe"):
            raise error
    assert caught.value is error
    assert not caplog.records


def test_success_does_not_log(caplog):
    with caplog.at_level(logging.DEBUG, logger="mealie-mcp"):
        with tool_error_boundary("Fetching foods"):
            result = {"items": []}
    assert result == {"items": []}
    assert not caplog.records
