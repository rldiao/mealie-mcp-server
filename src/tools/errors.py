"""Safe error translation shared by explicitly registered MCP tools."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager

import httpx
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import ValidationError

from mealie.client import MealieApiError

logger = logging.getLogger("mealie-mcp")


@contextmanager
def tool_error_boundary(operation: str) -> Iterator[None]:
    """Translate expected failures without logging exception text or tool input.

    ``operation`` must be a fixed description, never formatted with user data.
    Explicit ToolError messages, including partial-progress recovery, pass through.
    """
    try:
        yield
    except ToolError:
        raise
    except (
        MealieApiError,
        httpx.HTTPError,
        TimeoutError,
        ConnectionError,
        ValueError,
        FileNotFoundError,
        PermissionError,
        IsADirectoryError,
        NotADirectoryError,
    ) as error:
        metadata = {"operation": operation, "error_type": type(error).__name__}
        if isinstance(error, MealieApiError):
            metadata["status_code"] = error.status_code
            detail = f"Mealie API request failed (HTTP {error.status_code})"
        elif isinstance(error, httpx.HTTPStatusError):
            metadata["status_code"] = error.response.status_code
            detail = f"Mealie API request failed (HTTP {error.response.status_code})"
        elif isinstance(error, (TimeoutError, httpx.TimeoutException)):
            detail = "Mealie API request timed out"
        elif isinstance(error, (ConnectionError, httpx.RequestError)):
            detail = "Could not communicate with the Mealie API"
        elif isinstance(error, ValidationError):
            # Custom validator messages can embed input even when include_input=False.
            kinds = sorted({
                item["type"]
                for item in error.errors(
                    include_input=False, include_context=False, include_url=False
                )
            })
            detail = f"Invalid input ({', '.join(kinds)})"
        elif isinstance(error, ValueError):
            detail = str(error)
        else:
            detail = "Could not access the requested file"
        logger.error(metadata)
        raise ToolError(f"{operation}: {detail}") from None
