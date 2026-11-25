"""OAuth resource-server authentication for the MCP endpoint."""

from .config import AuthConfig
from .identity import current_username
from .verifier import USERNAME_KEY, OidcTokenVerifier

__all__ = ["USERNAME_KEY", "AuthConfig", "OidcTokenVerifier", "current_username"]
