"""Contract tests for category, tag, food, unit, and equipment tools."""

import copy
import logging

import pytest
from mcp.server.fastmcp.exceptions import ToolError


ORGANIZERS = [
    ("category", "categories", "/api/organizers/categories"),
    ("tag", "tags", "/api/organizers/tags"),
    ("food", "foods", "/api/foods"),
    ("unit", "units", "/api/units"),
    ("tool", "tools", "/api/organizers/tools"),
]
REPLACEMENT_ORGANIZERS = ORGANIZERS[2:]


@pytest.fixture(params=ORGANIZERS, ids=[case[0] for case in ORGANIZERS])
def organizer(request):
    return request.param


async def test_list_forwards_pagination(invoke, fetcher, organizer):
    _, plural, endpoint = organizer
    result = await invoke(f"get_{plural}", page=2, per_page=10)
    assert fetcher.last("GET", endpoint)["params"] == {"page": 2, "perPage": 10}
    assert "items" in result


async def test_list_omits_unset_parameters(invoke, fetcher, organizer):
    _, plural, endpoint = organizer
    await invoke(f"get_{plural}")
    assert fetcher.last("GET", endpoint)["params"] == {}


def test_mixin_forwards_search_and_filter(fetcher, organizer):
    _, plural, endpoint = organizer
    getattr(fetcher, f"get_{plural}")(
        search="synthetic-search", query_filter="synthetic-filter", per_page=10
    )
    assert fetcher.last("GET", endpoint)["params"] == {
        "search": "synthetic-search",
        "queryFilter": "synthetic-filter",
        "perPage": 10,
    }


@pytest.mark.parametrize("plural", ["foods", "units", "tools"])
async def test_search_argument_is_forwarded(invoke, fetcher, plural):
    await invoke(f"get_{plural}", search="synthetic-search")
    assert fetcher.last("GET")["params"] == {"search": "synthetic-search"}


async def test_create(invoke, fetcher, organizer):
    singular, _, endpoint = organizer
    result = await invoke(f"create_{singular}", name="Synthetic")
    assert fetcher.last("POST", endpoint)["json"] == {"name": "Synthetic"}
    assert result["name"] == "Synthetic"


async def test_get_by_id(invoke, fetcher, organizer):
    singular, _, endpoint = organizer
    result = await invoke(f"get_{singular}", **{f"{singular}_id": "record-1"})
    assert fetcher.last("GET")["url"] == f"{endpoint}/record-1"
    assert result["id"] == "record-1"


async def test_update_preserves_resource_specific_request_flow(
    invoke, fetcher, organizer
):
    singular, _, endpoint = organizer
    result = await invoke(
        f"update_{singular}", **{f"{singular}_id": "record-1", "name": "Renamed"}
    )
    assert result["name"] == "Renamed"
    put = fetcher.last("PUT", endpoint)
    assert put["url"] == f"{endpoint}/record-1"
    if singular in ("category", "tag"):
        assert [request["method"] for request in fetcher.requests] == ["PUT"]
        assert put["json"] == {"name": "Renamed"}
    else:
        assert [request["method"] for request in fetcher.requests] == ["GET", "PUT"]
        assert put["json"]["id"] == "record-1"
        assert put["json"]["description"] == "old"


async def test_delete_returns_structured_success(invoke, fetcher, organizer):
    singular, _, endpoint = organizer
    result = await invoke(f"delete_{singular}", **{f"{singular}_id": "record-1"})
    assert fetcher.last("DELETE")["url"] == f"{endpoint}/record-1"
    assert result["success"] is True


@pytest.mark.parametrize(
    ("singular", "plural", "endpoint"), ORGANIZERS[:2] + ORGANIZERS[4:]
)
async def test_slug_lookup(invoke, fetcher, singular, plural, endpoint):
    url = f"{endpoint}/slug/synthetic-slug"
    fetcher.responses["GET", url] = {
        "id": "record-1", "name": "Synthetic", "slug": "synthetic-slug"
    }
    await invoke(f"get_{singular}_by_slug", **{f"{singular}_slug": "synthetic-slug"})
    assert fetcher.last("GET")["url"] == url


@pytest.mark.parametrize("plural", ["categories", "tags"])
async def test_empty_lookup(invoke, fetcher, plural):
    fetcher.responses["GET", f"/api/organizers/{plural}/empty"] = []
    assert await invoke(f"get_empty_{plural}") == []
    assert fetcher.last("GET")["url"] == f"/api/organizers/{plural}/empty"


@pytest.mark.parametrize("operation", ["create", "get", "update", "delete", "noop"])
async def test_validation_fails_before_request(invoke, fetcher, organizer, operation):
    singular, _, _ = organizer
    if operation == "create":
        arguments = {"name": ""}
    elif operation == "noop":
        operation = "update"
        arguments = {f"{singular}_id": "record-1"}
    else:
        arguments = {f"{singular}_id": ""}
        if operation == "update":
            arguments["name"] = "Renamed"
    with pytest.raises(ToolError):
        await invoke(f"{operation}_{singular}", **arguments)
    assert fetcher.requests == []


@pytest.mark.parametrize("singular", ["category", "tag", "tool"])
async def test_empty_slug_fails_before_request(invoke, fetcher, singular):
    with pytest.raises(ToolError):
        await invoke(f"get_{singular}_by_slug", **{f"{singular}_slug": ""})
    assert fetcher.requests == []


@pytest.mark.parametrize("operation", ["list", "create", "get", "update", "delete"])
@pytest.mark.parametrize("failure", ["client", "validation", "unexpected"])
async def test_failures_are_tool_errors_without_content_logs(
    invoke, fetcher, organizer, operation, failure, monkeypatch, caplog
):
    singular, plural, endpoint = organizer
    secret = "synthetic-private-error"
    if failure == "client":
        fetcher.fail_on(endpoint, message=secret)
    else:
        def fail(*args, **kwargs):
            error_type = ValueError if failure == "validation" else RuntimeError
            raise error_type(secret)

        monkeypatch.setattr(fetcher, "_handle_request", fail)
    if operation == "list":
        tool_name, arguments = f"get_{plural}", {}
    elif operation == "create":
        tool_name, arguments = f"create_{singular}", {"name": secret}
    else:
        tool_name = f"{operation}_{singular}"
        arguments = {f"{singular}_id": secret}
        if operation == "update":
            arguments["name"] = secret
    with caplog.at_level(logging.DEBUG, logger="mealie-mcp"):
        with pytest.raises(ToolError) as error:
            await invoke(tool_name, **arguments)
    if failure == "client":
        assert secret not in str(error.value)
    assert secret not in caplog.text
    assert "Traceback" not in caplog.text
    if singular in ("food", "unit", "tool"):
        assert fetcher.last("PUT") is None


async def test_success_logs_exclude_content(invoke, fetcher, organizer, caplog):
    singular, plural, endpoint = organizer
    secret = "synthetic-private-content"
    if singular in ("category", "tag", "tool"):
        fetcher.responses["GET", f"{endpoint}/slug/{secret}"] = {
            "id": secret, "name": secret, "slug": secret
        }
    with caplog.at_level(logging.DEBUG, logger="mealie-mcp"):
        getattr(fetcher, f"get_{plural}")(search=secret, query_filter=secret)
        await invoke(f"create_{singular}", name=secret)
        await invoke(f"get_{singular}", **{f"{singular}_id": secret})
        await invoke(
            f"update_{singular}", **{f"{singular}_id": secret, "name": secret}
        )
        if singular in ("category", "tag", "tool"):
            await invoke(
                f"get_{singular}_by_slug", **{f"{singular}_slug": secret}
            )
        await invoke(f"delete_{singular}", **{f"{singular}_id": secret})
    assert caplog.records
    assert secret not in caplog.text


@pytest.mark.parametrize(("singular", "plural", "endpoint"), REPLACEMENT_ORGANIZERS)
@pytest.mark.parametrize(
    "existing",
    [
        None,
        [],
        "invalid",
        {},
        {"id": "record-1"},
        {"name": "Existing"},
        {"id": None, "name": "Existing"},
        {"id": "record-1", "name": None},
        {"id": "record-1", "name": 42},
        {"id": "record-1", "name": "  "},
    ],
)
async def test_malformed_read_prevents_replacement(
    invoke, fetcher, singular, plural, endpoint, existing
):
    fetcher.responses["GET", f"{endpoint}/record-1"] = existing
    with pytest.raises(ToolError):
        await invoke(
            f"update_{singular}", **{f"{singular}_id": "record-1", "name": "Renamed"}
        )
    assert [request["method"] for request in fetcher.requests] == ["GET"]


async def test_equipment_read_requires_slug(invoke, fetcher):
    fetcher.responses["GET", "/api/organizers/tools/record-1"] = {
        "id": "record-1", "name": "Existing"
    }
    with pytest.raises(ToolError):
        await invoke("update_tool", tool_id="record-1", name="Renamed")
    assert fetcher.last("PUT") is None


@pytest.mark.parametrize(
    ("singular", "fields", "arguments", "changes"),
    [
        (
            "food",
            {
                "labelId": "label-1",
                "extras": {"keep": "value"},
                "pluralName": "Existing foods",
                "aliases": [{"name": "Alias"}],
                "householdsWithIngredientFood": ["household-1"],
            },
            {"description": "new"},
            {"description": "new"},
        ),
        (
            "food",
            {
                "labelId": "label-1",
                "extras": {"old": "value"},
                "aliases": [{"name": "Alias"}],
                "householdsWithIngredientFood": ["household-1"],
            },
            {"label_id": "", "extras": {}},
            {"labelId": None, "extras": {}},
        ),
        (
            "unit",
            {
                "fraction": False,
                "useAbbreviation": True,
                "pluralAbbreviation": "gs",
                "extras": {"keep": "value"},
                "aliases": [{"name": "Alias"}],
            },
            {"abbreviation": "g", "plural_name": ""},
            {"abbreviation": "g", "pluralName": ""},
        ),
        (
            "tool",
            {"slug": "existing", "householdsWithTool": ["household-1"]},
            {"name": "Renamed"},
            {"name": "Renamed"},
        ),
    ],
)
async def test_replacement_preserves_omitted_fields_without_mutation(
    invoke, fetcher, monkeypatch, singular, fields, arguments, changes
):
    existing = {"id": "record-1", "name": "Existing", "description": "old", **fields}
    original = copy.deepcopy(existing)
    monkeypatch.setattr(fetcher, f"get_{singular}", lambda _: existing)
    await invoke(
        f"update_{singular}", **{f"{singular}_id": "record-1", **arguments}
    )
    assert fetcher.last("PUT")["json"] == {**original, **changes}
    assert existing == original


async def test_create_food_preserves_optional_fields_and_label_clear(invoke, fetcher):
    await invoke(
        "create_food",
        name="Food",
        plural_name="Foods",
        description="",
        extras={},
        label_id="",
    )
    assert fetcher.last("POST")["json"] == {
        "name": "Food",
        "pluralName": "Foods",
        "description": "",
        "extras": {},
        "labelId": None,
    }


async def test_create_unit_preserves_optional_fields(invoke, fetcher):
    await invoke(
        "create_unit", name="Gram", abbreviation="g", plural_name="Grams", description=""
    )
    assert fetcher.last("POST")["json"] == {
        "name": "Gram",
        "abbreviation": "g",
        "pluralName": "Grams",
        "description": "",
    }


async def test_registered_schemas_remain_explicit(server, organizer):
    singular, plural, _ = organizer
    mcp, _ = server
    tools = {tool.name: tool for tool in await mcp.list_tools()}
    extra_fields = {
        "food": {"plural_name", "description", "extras", "label_id"},
        "unit": {"abbreviation", "plural_name", "description"},
    }.get(singular, set())
    expected = {
        f"get_{plural}": (
            {"page", "per_page"}
            | ({"search"} if singular in ("food", "unit", "tool") else set()),
            set(),
        ),
        f"create_{singular}": ({"name"} | extra_fields, {"name"}),
        f"get_{singular}": ({f"{singular}_id"}, {f"{singular}_id"}),
        f"update_{singular}": (
            {f"{singular}_id", "name"} | extra_fields,
            {f"{singular}_id"},
        ),
        f"delete_{singular}": ({f"{singular}_id"}, {f"{singular}_id"}),
    }
    if singular in ("category", "tag"):
        expected[f"get_empty_{plural}"] = (set(), set())
    if singular in ("category", "tag", "tool"):
        expected[f"get_{singular}_by_slug"] = (
            {f"{singular}_slug"}, {f"{singular}_slug"}
        )
    for name, (properties, required) in expected.items():
        schema = tools[name].inputSchema
        assert set(schema["properties"]) == properties
        assert set(schema.get("required", [])) == required
        for field in required:
            assert schema["properties"][field]["type"] == "string"
        for field in properties - required:
            assert schema["properties"][field]["default"] is None


async def test_lookup_descriptions_match_resource_contracts(server):
    mcp, _ = server
    tools = {tool.name: tool for tool in await mcp.list_tools()}
    assert "associated recipes" not in tools["get_category"].description
    assert "ID, slug, and name" in tools["get_category"].description
    assert "only if its ID appears" in tools["get_tools"].description
