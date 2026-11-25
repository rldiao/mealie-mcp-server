"""The authenticated user behind the MCP request being handled."""

from collections.abc import Mapping

from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
from mcp.server.fastmcp import FastMCP

from .verifier import USERNAME_KEY


def current_username(server: FastMCP) -> str | None:
    """Return the Mealie username of the current HTTP request, or None.

    Read from the current request's ASGI scope, never from the SDK's auth context
    variable: that one holds the token of the request that opened the MCP session,
    which goes stale once the client refreshes its token.
    """
    try:
        request = server.get_context().request_context.request
    except ValueError:  # outside of any MCP request
        return None
    if request is None:
        return None
    scope = getattr(request, "scope", None)
    user = scope.get("user") if isinstance(scope, Mapping) else None
    if not isinstance(user, AuthenticatedUser):
        return None
    username = (user.access_token.claims or {}).get(USERNAME_KEY)
    if isinstance(username, str) and username:
        return username
    return None
