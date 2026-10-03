import json
import logging
from itertools import product

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from tools import register_all_tools


@pytest.fixture
def server(fetcher):
    mcp = FastMCP("ai-import-test")
    register_all_tools(mcp, fetcher, enable_ai_import=True)
    fetcher.responses["GET", "/api/groups/self"] = {
        "aiProviderSettings": {
            "aiEnabled": True,
            "imageProviderEnabled": True,
            "audioProviderEnabled": False,
        }
    }
    return mcp, fetcher


async def test_ai_import_discovery(server):
    mcp, fetcher = server
    tools = await mcp.list_tools()
    assert len(tools) == 62
    tool = next(tool for tool in tools if tool.name == "import_recipe_with_ai")
    assert all(
        "import_recipe_with_ai" not in (other.description or "")
        for other in tools if other.name != tool.name
    )
    assert not tool.inputSchema.get("required")
    assert len(tool.description.split()) <= 80
    assert set(tool.inputSchema["properties"]) == {
        "content", "url", "image_paths", "translate_language", "create_new_organizers"
    }
    for name in ("import_recipe_from_url", "create_recipe", "upload_recipe_image_file"):
        assert name in tool.description
    assert tool.annotations.readOnlyHint is False
    assert tool.annotations.idempotentHint is False
    assert fetcher.requests == []


@pytest.mark.parametrize(
    ("has_content", "has_url", "has_images"),
    [combo for combo in product((False, True), repeat=3) if any(combo)],
)
async def test_source_combinations(
    invoke, fetcher, tmp_path, has_content, has_url, has_images
):
    image = tmp_path / "recipe.jpg"
    image.write_bytes(b"image-data")
    arguments = {}
    if has_content:
        arguments["content"] = "  Private source material\n"
    if has_url:
        arguments["url"] = "https://example.com/recipe"
    if has_images:
        arguments["image_paths"] = [str(image)]
    result = await invoke("import_recipe_with_ai", **arguments)
    assert result == fetcher.recipe
    assert [(r["method"], r["url"]) for r in fetcher.requests] == [
        ("GET", "/api/groups/self"),
        ("POST", "/api/recipes/create/ai"),
        ("GET", "/api/recipes/test-recipe"),
    ]
    request = fetcher.requests[1]
    assert request["json"] is None
    assert request["params"] is None
    assert request["data"] == {
        "createNewOrganizers": "false",
        **({"content": arguments["content"]} if has_content else {}),
        **({"url": arguments["url"]} if has_url else {}),
    }
    assert request["files"] == (
        [("images", ("0-recipe.jpg", b"image-data"))] if has_images else None
    )


@pytest.mark.parametrize("content", [
    "plain recipe", "<html>recipe</html>", '{"@type":"Recipe"}', "{}", "[]", "null"
])
async def test_content_preserved_with_options(invoke, fetcher, content):
    await invoke(
        "import_recipe_with_ai", content=content,
        translate_language="French", create_new_organizers=True,
    )
    assert fetcher.requests[1]["data"] == {
        "content": content, "translateLanguage": "French", "createNewOrganizers": "true"
    }


async def test_multiple_images_preserve_order_and_avoid_name_collisions(invoke, fetcher, tmp_path):
    paths = []
    for index in range(2):
        directory = tmp_path / str(index)
        directory.mkdir()
        image = directory / "recipe.jpg"
        image.write_bytes(bytes([index]))
        paths.append(str(image))
    await invoke("import_recipe_with_ai", image_paths=paths)
    assert fetcher.requests[1]["files"] == [
        ("images", ("0-recipe.jpg", b"\x00")),
        ("images", ("1-recipe.jpg", b"\x01")),
    ]


@pytest.mark.parametrize("arguments", [
    {}, {"content": " "}, {"url": ""}, {"image_paths": []},
    {"content": "recipe", "translate_language": " "},
    {"url": "ftp://example.com/recipe"}, {"url": "not a url"},
    {"image_paths": [" "]}, {"image_paths": [None]}, {"content": 123}, {"content": None},
])
async def test_invalid_sources_do_not_issue_requests(invoke, fetcher, arguments):
    with pytest.raises(ToolError):
        await invoke("import_recipe_with_ai", **arguments)
    assert fetcher.requests == []


@pytest.mark.parametrize("kind", ["missing", "empty", "directory", "permission"])
async def test_invalid_files_fail_before_requests(
    invoke, fetcher, tmp_path, monkeypatch, kind, caplog
):
    path = tmp_path / "private-filename.jpg"
    if kind == "empty":
        path.touch()
    elif kind == "directory":
        path.mkdir()
    elif kind == "permission":
        from pathlib import Path

        def denied(self):
            raise PermissionError("private-filename.jpg")

        monkeypatch.setattr(Path, "read_bytes", denied)
    with pytest.raises(ToolError) as caught:
        await invoke("import_recipe_with_ai", image_paths=[str(path)])
    assert "private-filename" not in str(caught.value)
    assert "private-filename" not in caplog.text
    assert fetcher.requests == []


@pytest.mark.parametrize("group", [
    {}, {"aiProviderSettings": None}, [], {"aiProviderSettings": {}},
    {"aiProviderSettings": {
        "aiEnabled": "true", "imageProviderEnabled": True, "audioProviderEnabled": True
    }},
])
async def test_unknown_capabilities_are_not_treated_as_disabled(invoke, fetcher, group):
    fetcher.responses["GET", "/api/groups/self"] = group
    with pytest.raises(ToolError, match="Unable to determine"):
        await invoke("import_recipe_with_ai", content="recipe")
    assert len(fetcher.requests) == 1


@pytest.mark.parametrize("status", [401, 403, 404, 503])
async def test_capability_request_errors(invoke, fetcher, status):
    fetcher.fail_on("/api/groups/self", status)
    with pytest.raises(ToolError, match="Unable to determine"):
        await invoke("import_recipe_with_ai", content="recipe")
    assert len(fetcher.requests) == 1


async def test_provider_changes_are_checked_each_time(invoke, fetcher):
    settings = fetcher.responses["GET", "/api/groups/self"]["aiProviderSettings"]
    settings["aiEnabled"] = False
    with pytest.raises(ToolError, match="default AI provider"):
        await invoke("import_recipe_with_ai", content="recipe")
    assert len(fetcher.requests) == 1
    settings["aiEnabled"] = True
    await invoke("import_recipe_with_ai", content="recipe")
    assert len(fetcher.requests) == 4


async def test_image_provider_required_only_for_photos(invoke, fetcher, tmp_path):
    fetcher.responses["GET", "/api/groups/self"]["aiProviderSettings"]["imageProviderEnabled"] = False
    image = tmp_path / "recipe.jpg"
    image.write_bytes(b"image")
    with pytest.raises(ToolError, match="image AI provider"):
        await invoke("import_recipe_with_ai", image_paths=[str(image)])
    assert len(fetcher.requests) == 1
    await invoke("import_recipe_with_ai", content="recipe")


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422, 500])
async def test_import_errors_do_not_fetch_or_retry(invoke, fetcher, status, caplog):
    fetcher.fail_on("/create/ai", status, "private-response")
    with pytest.raises(ToolError) as caught:
        await invoke("import_recipe_with_ai", content="private-content")
    assert ("3.23.0" if status == 404 else f"HTTP {status}") in str(caught.value)
    assert len(fetcher.requests) == 2
    assert "private-response" not in str(caught.value)
    assert "private-content" not in caplog.text


@pytest.mark.parametrize("failure", [TimeoutError, ConnectionError])
async def test_uncertain_creation_warns_before_retry(invoke, fetcher, monkeypatch, failure):
    original = fetcher._handle_request

    def request(method, url, **kwargs):
        result = original(method, url, **kwargs)
        if url.endswith("/create/ai"):
            raise failure("private-transport")
        return result

    monkeypatch.setattr(fetcher, "_handle_request", request)
    with pytest.raises(ToolError, match="outcome is unknown") as caught:
        await invoke("import_recipe_with_ai", content="recipe")
    assert "private-transport" not in str(caught.value)
    assert len(fetcher.requests) == 2


@pytest.mark.parametrize("slug", [None, {}, [], True, 42, "", " ", "../private", "bad?query"])
async def test_invalid_slug_does_not_fetch_or_retry(invoke, fetcher, slug):
    fetcher.responses["POST", "/api/recipes/create/ai"] = slug
    with pytest.raises(ToolError, match="invalid AI import slug"):
        await invoke("import_recipe_with_ai", content="recipe")
    assert len(fetcher.requests) == 2


async def test_fetch_failure_returns_recovery_details(invoke, fetcher, caplog):
    fetcher.fail_on("/api/recipes/test-recipe", 503)
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(ToolError) as caught:
            await invoke("import_recipe_with_ai", content="private-content")
    message = str(caught.value)
    error = json.loads(message[message.index("{"):])
    assert error["created_slug"] == "test-recipe"
    assert error["stage"] == "fetch"
    assert len(fetcher.requests) == 3
    assert "test-recipe" not in caplog.text
    assert "private-content" not in caplog.text
