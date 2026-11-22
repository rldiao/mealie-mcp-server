import logging
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from mcp_auth import OidcTokenVerifier
from mcp_auth.verifier import USERNAME_KEY


@pytest.fixture
def verifier(oidc):
    return OidcTokenVerifier(oidc.config(), transport=oidc.transport)


async def test_valid_token_returns_access_token(oidc, verifier):
    token = oidc.token()
    result = await verifier.verify_token(token)
    assert result.token == token
    assert result.subject == "sub-alice"
    assert result.client_id == oidc.audience
    assert result.claims == {"iss": oidc.issuer, USERNAME_KEY: "alice"}
    assert result.expires_at > time.time()


@pytest.mark.parametrize(
    "claims",
    [
        {"iss": "https://evil.example/"},
        {"aud": "other-client"},
        {"exp": int(time.time()) - 120},
        {"exp": None},
        {"sub": None},
    ],
)
async def test_rejects_invalid_claims(oidc, verifier, claims):
    assert await verifier.verify_token(oidc.token(**claims)) is None


async def test_rejects_foreign_signature(oidc, verifier):
    # same kid "k1", signed by a key the JWKS does not publish
    foreign = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert await verifier.verify_token(oidc.token(key=foreign)) is None


async def test_rejects_unsigned_and_malformed_tokens(oidc, verifier):
    unsigned = jwt.encode(oidc.claims(), None, algorithm="none", headers={"kid": "k1"})
    assert await verifier.verify_token(unsigned) is None
    assert await verifier.verify_token("not-a-jwt") is None
    assert await verifier.verify_token(oidc.token(kid=None)) is None


async def test_group_found_in_userinfo_when_missing_from_token(oidc, verifier):
    oidc.userinfo = {"sub": "sub-alice", "groups": ["miam-contributors"]}
    assert await verifier.verify_token(oidc.token(groups=None)) is not None
    userinfo = [r for r in oidc.requests if str(r.url) == oidc.userinfo_endpoint]
    assert len(userinfo) == 1
    assert userinfo[0].headers["authorization"].startswith("Bearer ")


async def test_group_missing_everywhere_is_rejected(oidc, verifier, caplog):
    oidc.userinfo = {"sub": "sub-alice", "groups": ["someone-else"]}
    assert await verifier.verify_token(oidc.token(groups=["other"])) is None
    assert "group_missing" in caplog.text


async def test_userinfo_for_another_subject_is_rejected(oidc, verifier):
    oidc.userinfo = {"sub": "sub-bob", "groups": ["miam-contributors"]}
    assert await verifier.verify_token(oidc.token(groups=None)) is None


async def test_userinfo_failure_is_rejected(oidc, verifier, caplog):
    assert await verifier.verify_token(oidc.token(groups=None)) is None
    assert "userinfo_failed" in caplog.text


async def test_username_from_userinfo_then_missing(oidc, verifier):
    oidc.userinfo = {"sub": "sub-alice", "preferred_username": "alice"}
    result = await verifier.verify_token(oidc.token(preferred_username=None))
    assert result.claims[USERNAME_KEY] == "alice"
    oidc.userinfo = {"sub": "sub-alice"}
    assert await verifier.verify_token(oidc.token(preferred_username="  ")) is None


async def test_userinfo_requested_once_for_group_and_username(oidc, verifier):
    oidc.userinfo = {
        "sub": "sub-alice",
        "groups": ["miam-contributors"],
        "preferred_username": "alice",
    }
    token = oidc.token(groups=None, preferred_username=None)
    assert await verifier.verify_token(token) is not None
    assert oidc.count(oidc.userinfo_endpoint) == 1


async def test_without_required_group_no_group_check(oidc):
    verifier = OidcTokenVerifier(
        oidc.config(required_group=None), transport=oidc.transport
    )
    assert await verifier.verify_token(oidc.token(groups=None)) is not None
    assert oidc.count(oidc.userinfo_endpoint) == 0


async def test_discovery_failure_is_retried_then_cached(oidc, verifier):
    oidc.discovery_status = 503
    assert await verifier.verify_token(oidc.token()) is None
    oidc.discovery_status = 200
    assert await verifier.verify_token(oidc.token()) is not None
    assert await verifier.verify_token(oidc.token()) is not None
    assert oidc.count(oidc.discovery_url) == 2
    assert oidc.count(oidc.jwks_uri) == 1


async def test_discovery_with_another_issuer_is_rejected(oidc):
    verifier = OidcTokenVerifier(
        oidc.config(issuer=oidc.issuer.rstrip("/")), transport=oidc.transport
    )
    token = oidc.token(iss=oidc.issuer.rstrip("/"))
    assert await verifier.verify_token(token) is None


async def test_unknown_kid_reloads_jwks_at_most_once_per_cooldown(oidc):
    now = [1000.0]
    verifier = OidcTokenVerifier(
        oidc.config(), transport=oidc.transport, clock=lambda: now[0]
    )
    assert await verifier.verify_token(oidc.token()) is not None
    oidc.publish_key("k2")
    assert await verifier.verify_token(oidc.token(kid="k2")) is not None  # reload
    for i in range(5):
        assert await verifier.verify_token(oidc.token(kid=f"random-{i}")) is None
    assert oidc.count(oidc.jwks_uri) == 2
    now[0] += 61
    assert await verifier.verify_token(oidc.token(kid="random-x")) is None
    assert oidc.count(oidc.jwks_uri) == 3


async def test_jwks_reloaded_after_ttl(oidc):
    now = [1000.0]
    verifier = OidcTokenVerifier(
        oidc.config(), transport=oidc.transport, clock=lambda: now[0]
    )
    assert await verifier.verify_token(oidc.token()) is not None
    now[0] += 3601
    assert await verifier.verify_token(oidc.token()) is not None
    assert oidc.count(oidc.jwks_uri) == 2


async def test_rejection_logs_reason_only(oidc, verifier, caplog):
    token = oidc.token(aud="other-client")
    with caplog.at_level(logging.DEBUG):
        assert await verifier.verify_token(token) is None
    assert "mcp token rejected" in caplog.text and "invalid_token" in caplog.text
    assert token not in caplog.text and "sub-alice" not in caplog.text
    assert "alice" not in caplog.text
