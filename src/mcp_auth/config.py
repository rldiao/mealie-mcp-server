"""Configuration for OAuth resource-server authentication."""

import os
from dataclasses import dataclass
from urllib.parse import urlsplit

# Settings that only make sense with MCP_AUTH_ISSUER: when one is set without
# the issuer, refuse to start rather than serve without authentication.
_DEPENDENT_VARIABLES = (
    "MCP_AUTH_AUDIENCE",
    "MCP_AUTH_REQUIRED_GROUP",
    "MCP_AUTH_USERNAME_CLAIM",
    "MCP_PUBLIC_URL",
)


@dataclass(frozen=True)
class AuthConfig:
    """Settings the token verifier and the MCP auth wiring share."""

    issuer: str
    audience: str
    public_url: str
    required_group: str | None = None
    username_claim: str = "preferred_username"

    def __post_init__(self) -> None:
        object.__setattr__(self, "public_url", self.public_url.rstrip("/"))

    @property
    def resource_url(self) -> str:
        return f"{self.public_url}/mcp"

    @classmethod
    def from_environment(cls) -> "AuthConfig | None":
        """Read authentication settings; None when MCP_AUTH_ISSUER is unset.

        Error messages name the variable, never its value.
        """
        issuer = os.getenv("MCP_AUTH_ISSUER", "").strip()
        audience = os.getenv("MCP_AUTH_AUDIENCE", "").strip()
        required_group = os.getenv("MCP_AUTH_REQUIRED_GROUP", "").strip()
        username_claim = os.getenv("MCP_AUTH_USERNAME_CLAIM")
        public_url = os.getenv("MCP_PUBLIC_URL", "").strip()

        if not issuer:
            dependent = {
                "MCP_AUTH_AUDIENCE": audience,
                "MCP_AUTH_REQUIRED_GROUP": required_group,
                "MCP_AUTH_USERNAME_CLAIM": (username_claim or "").strip(),
                "MCP_PUBLIC_URL": public_url,
            }
            orphans = [name for name in _DEPENDENT_VARIABLES if dependent[name]]
            if orphans:
                raise ValueError(f"{', '.join(orphans)} requires MCP_AUTH_ISSUER to be set")
            return None

        if not _is_http_url(issuer):
            raise ValueError("MCP_AUTH_ISSUER must be an http or https URL with a host")
        if not audience:
            raise ValueError("MCP_AUTH_AUDIENCE must be set when MCP_AUTH_ISSUER is set")
        if not public_url:
            raise ValueError("MCP_PUBLIC_URL must be set when MCP_AUTH_ISSUER is set")
        if not _is_public_base_url(public_url):
            raise ValueError(
                "MCP_PUBLIC_URL must be an http or https URL with a host and no path, "
                "query, or fragment"
            )
        if username_claim is None:
            username_claim = "preferred_username"
        username_claim = username_claim.strip()
        if not username_claim:
            raise ValueError("MCP_AUTH_USERNAME_CLAIM must not be empty")

        return cls(
            issuer=issuer,
            audience=audience,
            public_url=public_url,
            required_group=required_group or None,
            username_claim=username_claim,
        )


def _is_http_url(value: str) -> bool:
    try:
        parts = urlsplit(value)
        _ = parts.port  # raises ValueError on an invalid port
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and bool(parts.hostname)


def _is_public_base_url(value: str) -> bool:
    if not _is_http_url(value):
        return False
    # Reject even an empty query or fragment ("https://host?"): urlsplit drops it.
    if "?" in value or "#" in value:
        return False
    return urlsplit(value).path in ("", "/")
