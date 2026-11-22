"""Shared test fixtures.

Tests exercise the MCP tools end-to-end against a fake Mealie client that
records the HTTP requests the mixins would make (method, url, json, params)
and returns canned responses. No network access is required.
"""

import json
import time
from copy import deepcopy

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from mcp.server.fastmcp import FastMCP

from mcp_auth import AuthConfig
from mealie import MealieFetcher
from mealie.client import MealieApiError
from tools import register_all_tools

# A minimal but schema-valid recipe payload (satisfies the required Recipe
# fields), used as the response to GET /api/recipes/<slug>.
BASE_RECIPE = {
    "id": "00000000-0000-0000-0000-000000000000",
    "userId": "11111111-1111-1111-1111-111111111111",
    "householdId": "22222222-2222-2222-2222-222222222222",
    "groupId": "33333333-3333-3333-3333-333333333333",
    "name": "Test Recipe",
    "slug": "test-recipe",
    "dateAdded": "2024-01-01",
    "dateUpdated": "2024-01-01T00:00:00",
    "createdAt": "2024-01-01T00:00:00",
    "updatedAt": "2024-01-01T00:00:00",
    # Mealie seeds these from the household preferences, so a fresh recipe does
    # not necessarily start all-false.
    "settings": {
        "public": False,
        "showNutrition": True,
        "showAssets": True,
        "landscapeView": False,
        "disableComments": False,
        "locked": True,
    },
}


def _parsed(text):
    """A ParsedIngredient shaped like Mealie's, with the full food/unit records.

    Unit is left unmatched so the flattening keeps a null visible.
    """
    return {
        "input": text,
        "confidence": {
            "average": 0.996,
            "comment": 0.993,
            "name": None,
            "unit": 0.999,
            "quantity": 1.0,
            "food": 0.991,
        },
        "ingredient": {
            "quantity": 0.25,
            "unit": None,
            "food": {
                "id": "a0819c33-1a5e-4374-9151-ed85160c0049",
                "name": "onion",
                "pluralName": "onions",
                "description": "",
                "extras": {},
                "labelId": None,
                "aliases": [],
                "householdsWithIngredientFood": [],
                "label": None,
                "createdAt": "2026-08-03T02:15:22.603088Z",
                "updatedAt": "2026-08-03T02:15:22.603092Z",
            },
            "referencedRecipe": None,
            "note": "chopped",
            "display": "¹/₄ cup onion chopped",
            "title": None,
            "originalText": None,
            "referenceId": "75e1853f-3cb1-49b9-b2ca-26ae76da256b",
        },
    }


class FakeFetcher(MealieFetcher):
    """MealieFetcher with the network layer replaced by a recorder.

    Skips MealieClient.__init__ (no connection) and overrides _handle_request
    so the real mixin methods run and we can assert on the requests they build.
    """

    def __init__(self):
        self.requests = []
        self.created_slug = "test-recipe"
        self.recipe = deepcopy(BASE_RECIPE)
        self.responses = {}
        # url fragment -> MealieApiError to raise, for client-failure tests
        self.failures = {}

    def fail_on(self, url_contains, status_code=422, message="Mealie rejected it"):
        """Make any request whose url contains this fragment raise."""
        self.failures[url_contains] = MealieApiError(status_code, message)

    def _handle_request(self, method, url, **kwargs):
        self.requests.append(
            {
                "method": method,
                "url": url,
                "json": deepcopy(kwargs.get("json")),
                "params": deepcopy(kwargs.get("params")),
                "files": kwargs.get("files"),
                "data": deepcopy(kwargs.get("data")),
            }
        )
        for fragment, error in self.failures.items():
            if fragment in url:
                raise error
        if (method, url) in self.responses:
            return deepcopy(self.responses[method, url])
        resource_url, _, resource_id = url.rpartition("/")
        if method == "POST" and url == "/api/recipes/create/ai":
            return self.created_slug
        if method == "POST" and url == "/api/recipes":
            name = (kwargs.get("json") or {}).get("name")
            if name:
                # reflect the created name on subsequent GET (like the real API)
                self.recipe = {**self.recipe, "name": name, "slug": self.created_slug}
            return self.created_slug
        if method == "GET" and url.startswith("/api/recipes/") and url.count("/") == 3:
            return deepcopy(self.recipe)
        if (
            method in ("POST", "PUT")
            and url.startswith("/api/recipes/")
            and url.count("/") == 4
            and url.endswith("/image")
        ):
            return {"image": "1"}
        if method == "POST" and url.startswith("/api/recipes/") and url.endswith("/assets"):
            data = kwargs.get("data") or {}
            return {
                "name": data.get("name"),
                "icon": data.get("icon"),
                "fileName": f"{data.get('name')}.{data.get('extension')}",
            }
        if method == "POST" and url == "/api/parser/ingredient":
            return _parsed((kwargs.get("json") or {}).get("ingredient"))
        if method == "POST" and url == "/api/parser/ingredients":
            return [
                _parsed(text) for text in (kwargs.get("json") or {}).get("ingredients", [])
            ]
        if method in ("PUT", "PATCH") and resource_url == "/api/recipes":
            return deepcopy(kwargs.get("json", {}))
        # single-record GET (the fetch-merge update path reads the existing record)
        if method == "GET" and resource_url in (
            "/api/foods",
            "/api/units",
            "/api/organizers/tools",
        ):
            return {
                "id": url.rsplit("/", 1)[-1],
                "name": "Existing",
                "pluralName": "Existings",
                "description": "old",
                **({"slug": "existing"} if resource_url == "/api/organizers/tools" else {}),
            }
        if method == "GET" and resource_url == "/api/organizers/categories":
            item_id = url.rsplit("/", 1)[-1]
            return {"id": item_id, "name": "Category", "slug": "category"}
        if method == "GET" and resource_url == "/api/organizers/tags":
            item_id = url.rsplit("/", 1)[-1]
            return {"id": item_id, "name": "Tag", "slug": "tag"}
        if method == "GET" and resource_url == "/api/households/mealplans":
            return {
                "id": url.rsplit("/", 1)[-1],
                "groupId": "group-1",
                "userId": "user-1",
                "date": "2026-07-12",
                "entryType": "dinner",
                "title": "Existing meal",
            }
        if method == "GET" and resource_url == "/api/households/shopping/lists":
            return {
                "id": url.rsplit("/", 1)[-1],
                "groupId": "group-1",
                "userId": "user-1",
                "name": "Existing list",
            }
        # list endpoints
        if method == "GET" and url in (
            "/api/foods",
            "/api/units",
            "/api/organizers/tools",
            "/api/organizers/categories",
            "/api/organizers/tags",
            "/api/recipes",
            "/api/households/mealplans",
            "/api/households/shopping/lists",
        ):
            return {
                "items": [{"id": "x1", "name": "Sample"}],
                "page": 1,
                "perPage": 50,
                "total": 1,
            }
        # create echoes the body with a generated id
        if method == "POST" and url in (
            "/api/foods",
            "/api/units",
            "/api/organizers/tools",
            "/api/organizers/categories",
            "/api/organizers/tags",
            "/api/households/mealplans",
            "/api/households/shopping/lists",
        ):
            return {**deepcopy(kwargs.get("json") or {}), "id": "generated-0001"}
        # full-replace update echoes the merged body
        if method == "PUT" and resource_url in (
            "/api/foods",
            "/api/units",
            "/api/organizers/tools",
            "/api/organizers/categories",
            "/api/organizers/tags",
            "/api/households/mealplans",
            "/api/households/shopping/lists",
        ):
            return deepcopy(kwargs.get("json", {}))
        # delete (Mealie normalizes the empty body to a success payload)
        if method == "DELETE" and resource_id and resource_url in (
            "/api/recipes",
            "/api/foods",
            "/api/units",
            "/api/organizers/tools",
            "/api/organizers/categories",
            "/api/organizers/tags",
            "/api/households/mealplans",
            "/api/households/shopping/lists",
        ):
            return {"success": True, "message": "Operation completed successfully"}
        raise AssertionError(f"Unhandled fake request: {method} {url}")

    def last(self, method=None, url_contains=None):
        """Return the most recent recorded request matching method/url filter."""
        for req in reversed(self.requests):
            if method is not None and req["method"] != method:
                continue
            if url_contains is not None and url_contains not in req["url"]:
                continue
            return req
        return None


@pytest.fixture
def fetcher():
    return FakeFetcher()


@pytest.fixture
def server(fetcher):
    mcp = FastMCP("test")
    register_all_tools(mcp, fetcher)
    return mcp, fetcher


@pytest.fixture
def invoke(server):
    """Async helper: call a tool by name with kwargs, return its parsed result."""
    import json

    mcp, _ = server

    async def _invoke(tool_name, /, **arguments):
        result = await mcp.call_tool(tool_name, arguments)
        content, structured = result if isinstance(result, tuple) else (result, None)
        if isinstance(structured, dict) and set(structured.keys()) == {"result"}:
            return structured["result"]
        if structured is not None:
            return structured
        if content and getattr(content[0], "text", None):
            return json.loads(content[0].text)
        return content

    return _invoke


class FakeOidc:
    """In-memory OIDC provider: discovery, JWKS and userinfo over MockTransport."""

    issuer = "https://auth.example/application/o/mealie-mcp/"
    audience = "mealie-mcp-client"

    def __init__(self, key):
        self.discovery_url = (
            self.issuer.rstrip("/") + "/.well-known/openid-configuration"
        )
        self.jwks_uri = "https://auth.example/application/o/mealie-mcp/jwks/"
        self.userinfo_endpoint = "https://auth.example/application/o/userinfo/"
        self.discovery_status = 200
        self.userinfo = None
        self.requests = []
        self.keys = {}
        self.current_kid = None
        self.publish_key("k1", key)
        self.transport = httpx.MockTransport(self._handle)

    def publish_key(self, kid, key=None):
        self.keys[kid] = key or rsa.generate_private_key(
            public_exponent=65537, key_size=2048
        )
        self.current_kid = kid

    def _jwks(self):
        keys = []
        for kid, key in self.keys.items():
            jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
            keys.append({**jwk, "kid": kid, "use": "sig", "alg": "RS256"})
        return {"keys": keys}

    def _handle(self, request):
        self.requests.append(request)
        url = str(request.url)
        if url == self.discovery_url:
            if self.discovery_status != 200:
                return httpx.Response(self.discovery_status)
            return httpx.Response(
                200,
                json={
                    "issuer": self.issuer,
                    "jwks_uri": self.jwks_uri,
                    "userinfo_endpoint": self.userinfo_endpoint,
                },
            )
        if url == self.jwks_uri:
            return httpx.Response(200, json=self._jwks())
        if url == self.userinfo_endpoint:
            if self.userinfo is None:
                return httpx.Response(401)
            return httpx.Response(200, json=self.userinfo)
        return httpx.Response(404)

    def claims(self, **overrides):
        now = int(time.time())
        claims = {
            "iss": self.issuer,
            "aud": self.audience,
            "sub": "sub-alice",
            "iat": now,
            "exp": now + 600,
            "preferred_username": "alice",
            "groups": ["miam-contributors"],
            **overrides,
        }
        return {k: v for k, v in claims.items() if v is not None}

    def token(self, *, kid="k1", key=None, algorithm="RS256", **overrides):
        headers = {"kid": kid} if kid is not None else {}
        return jwt.encode(
            self.claims(**overrides),
            key or self.keys[self.current_kid],
            algorithm=algorithm,
            headers=headers,
        )

    def config(self, **overrides):
        values = {
            "issuer": self.issuer,
            "audience": self.audience,
            "public_url": "https://miam-mcp.example",
            "required_group": "miam-contributors",
            **overrides,
        }
        return AuthConfig(**values)

    def count(self, url):
        return sum(1 for r in self.requests if str(r.url) == url)


@pytest.fixture(scope="session")
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def oidc(rsa_key):
    return FakeOidc(rsa_key)


class FakeMealie:
    """In-memory Mealie HTTP API for tests that run the real `MealieFetcher`.

    `install()` makes every `httpx.Client` use `transport`, so no request leaves
    the process. Bearer values map to Mealie users through `tokens`; routes map
    `(method, path)` to handlers. Unknown routes fail the test.
    """

    API_KEY = "api-key-marker"

    def __init__(self):
        self.health_status = 200
        self.requests: list[httpx.Request] = []
        self.clients: list[httpx.Client] = []
        self.tokens = {self.API_KEY: "shared"}
        self.routes = {
            ("GET", "/api/app/about"): self._about,
            ("GET", "/api/recipes"): self._recipes,
        }
        self.transport = httpx.MockTransport(self._handle)

    def install(self, monkeypatch):
        original = httpx.Client
        fake = self

        class RecordingClient(original):
            def __init__(self, *args, **kwargs):
                kwargs["transport"] = fake.transport
                super().__init__(*args, **kwargs)
                fake.clients.append(self)

        monkeypatch.setattr(httpx, "Client", RecordingClient)

    def user(self, request):
        """The Mealie user a request authenticates as, or None."""
        scheme, _, credentials = request.headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer":
            return None
        return self.tokens.get(credentials)

    def _handle(self, request):
        self.requests.append(request)
        handler = self.routes.get((request.method, request.url.path))
        if handler is None:
            raise AssertionError(
                f"Unexpected Mealie request: {request.method} {request.url.path}"
            )
        return handler(request)

    def _about(self, request):
        return httpx.Response(self.health_status, json={"version": "v3.0.0"})

    def _recipes(self, request):
        user = self.user(request)
        if user is None:
            return httpx.Response(401, json={"detail": "Not authenticated"})
        return httpx.Response(
            200,
            json={
                "items": [{"id": "r1", "name": f"{user} recipe"}],
                "page": 1,
                "perPage": 50,
                "total": 1,
            },
        )
