"""Verify OIDC access tokens (JWTs) against the issuer's published keys.

Never log tokens, subjects, usernames or response bodies: a rejection logs only
a short reason code.
"""

import logging
import math
import time
from collections.abc import Callable
from typing import Any

import anyio
import httpx
import jwt
from mcp.server.auth.provider import AccessToken

from .config import AuthConfig

logger = logging.getLogger("mealie-mcp")

USERNAME_KEY = "mealie_username"

_ALLOWED_ALGORITHMS = (
    "RS256",
    "RS384",
    "RS512",
    "PS256",
    "PS384",
    "PS512",
    "ES256",
    "ES384",
    "ES512",
)


class _Rejected(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class OidcTokenVerifier:
    def __init__(
        self,
        config: AuthConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
        jwks_ttl: float = 3600.0,
        jwks_refresh_cooldown: float = 60.0,
    ):
        self._config = config
        self._transport = transport
        self._clock = clock
        self._jwks_ttl = jwks_ttl
        self._cooldown = jwks_refresh_cooldown
        self._lock = anyio.Lock()
        self._discovery: dict[str, Any] | None = None
        self._keys: dict[str, jwt.PyJWK] = {}
        self._keys_fetched_at: float | None = None
        # Cooldown applies to reloads triggered by an unknown kid only.
        self._last_kid_reload = -math.inf

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=self._transport, timeout=10.0)

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            return await self._verify(token)
        except _Rejected as rejection:
            logger.warning(
                {"operation": "mcp token rejected", "reason": rejection.reason}
            )
            return None

    async def _verify(self, token: str) -> AccessToken:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError:
            raise _Rejected("malformed") from None
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            raise _Rejected("malformed")

        jwk = await self._key_for(kid)
        if jwk.algorithm_name not in _ALLOWED_ALGORITHMS:
            raise _Rejected("invalid_token")
        try:
            payload = jwt.decode(
                token,
                jwk.key,
                algorithms=[jwk.algorithm_name],
                audience=self._config.audience,
                issuer=self._config.issuer,
                leeway=30,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except jwt.PyJWTError:
            raise _Rejected("invalid_token") from None

        subject = payload["sub"]
        if not isinstance(subject, str) or not subject:
            raise _Rejected("invalid_token")

        # The userinfo request is lazy and shared by the group and name checks.
        userinfo_cache: list[dict[str, Any]] = []

        async def userinfo() -> dict[str, Any]:
            if not userinfo_cache:
                userinfo_cache.append(await self._fetch_userinfo(token, subject))
            return userinfo_cache[0]

        required_group = self._config.required_group
        if required_group is not None and not _has_group(payload, required_group):
            if not _has_group(await userinfo(), required_group):
                raise _Rejected("group_missing")

        claim = self._config.username_claim
        username = _clean_name(payload.get(claim))
        if username is None:
            username = _clean_name((await userinfo()).get(claim))
        if username is None:
            raise _Rejected("username_missing")

        scope = payload.get("scope")
        azp = payload.get("azp")
        return AccessToken(
            token=token,
            client_id=azp if isinstance(azp, str) and azp else self._config.audience,
            scopes=scope.split() if isinstance(scope, str) else [],
            expires_at=int(payload["exp"]),
            subject=subject,
            claims={"iss": payload["iss"], USERNAME_KEY: username},
        )

    async def _key_for(self, kid: str) -> jwt.PyJWK:
        async with self._lock:
            now = self._clock()
            if (
                self._keys_fetched_at is None
                or now - self._keys_fetched_at >= self._jwks_ttl
            ):
                await self._load_keys()
            if kid not in self._keys and now - self._last_kid_reload >= self._cooldown:
                self._last_kid_reload = now
                await self._load_keys()
            jwk = self._keys.get(kid)
        if jwk is None:
            raise _Rejected("unknown_key")
        return jwk

    async def _load_keys(self) -> None:
        discovery = await self._discover()
        jwks_uri = discovery.get("jwks_uri")
        if not isinstance(jwks_uri, str):
            raise _Rejected("jwks_failed")
        try:
            async with self._client() as client:
                response = await client.get(jwks_uri)
                response.raise_for_status()
                raw_keys = response.json()["keys"]
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise _Rejected("jwks_failed") from None
        keys: dict[str, jwt.PyJWK] = {}
        if isinstance(raw_keys, list):
            for raw in raw_keys:
                try:
                    keys[raw["kid"]] = jwt.PyJWK.from_dict(raw)
                except (jwt.PyJWTError, KeyError, TypeError):
                    continue  # skip keys we cannot use
        self._keys = keys
        self._keys_fetched_at = self._clock()

    async def _discover(self) -> dict[str, Any]:
        if self._discovery is not None:
            return self._discovery
        url = self._config.issuer.rstrip("/") + "/.well-known/openid-configuration"
        try:
            async with self._client() as client:
                response = await client.get(url)
                response.raise_for_status()
                document = response.json()
        except (httpx.HTTPError, ValueError):
            raise _Rejected("discovery_failed") from None
        if (
            not isinstance(document, dict)
            or document.get("issuer") != self._config.issuer
        ):
            raise _Rejected("discovery_failed")
        self._discovery = document
        return document

    async def _fetch_userinfo(self, token: str, subject: str) -> dict[str, Any]:
        # Discovery is already cached here: _key_for ran before any userinfo call.
        endpoint = (self._discovery or {}).get("userinfo_endpoint")
        if not isinstance(endpoint, str):
            raise _Rejected("userinfo_failed")
        try:
            async with self._client() as client:
                response = await client.get(
                    endpoint, headers={"Authorization": f"Bearer {token}"}
                )
                response.raise_for_status()
                document = response.json()
        except (httpx.HTTPError, ValueError):
            raise _Rejected("userinfo_failed") from None
        if not isinstance(document, dict) or document.get("sub") != subject:
            raise _Rejected("userinfo_failed")
        return document


def _has_group(claims: dict[str, Any], group: str) -> bool:
    groups = claims.get("groups")
    return isinstance(groups, list) and group in groups


def _clean_name(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
