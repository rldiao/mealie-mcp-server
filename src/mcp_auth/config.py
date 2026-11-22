"""Configuration for OAuth resource-server authentication."""

from dataclasses import dataclass


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
