"""Discovery and migration contracts for the consolidated MCP tool surface."""

import re
from pathlib import Path

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from prompts import register_prompts

REMOVED_TOOLS = (
    "create_recipe_full",
    "get_recipe_detailed",
    "get_recipe_concise",
    "patch_recipe",
    "set_recipe_categories",
    "set_recipe_tags",
    "get_category_by_slug",
    "get_tag_by_slug",
    "get_tool_by_slug",
    "parse_ingredient",
)


async def test_consolidated_inventory_matches_documentation(server):
    mcp, _ = server
    tools = await mcp.list_tools()
    names = {tool.name for tool in tools}
    assert len(names) == len(tools) == 61
    assert names.isdisjoint(REMOVED_TOOLS)
    assert "import_recipe_with_ai" not in names
    assert all("import_recipe_with_ai" not in (tool.description or "") for tool in tools)
    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text()
    inventory = readme.split("### Recipe Tools", 1)[1].split(
        "### Migrating consolidated tools", 1
    )[0]
    documented = re.findall(r"^- `(\w+)`", inventory, re.MULTILINE)
    assert len(documented) == len(names)
    assert set(documented) == names
    assert "**Total: 61 tools**" in inventory
    for tool in tools:
        for removed in REMOVED_TOOLS:
            assert not re.search(rf"\b{removed}\b", tool.description or "")


@pytest.mark.parametrize("name", REMOVED_TOOLS)
async def test_removed_tool_names_are_rejected(invoke, fetcher, name):
    with pytest.raises(ToolError, match="Unknown tool"):
        await invoke(name)
    assert fetcher.requests == []


async def test_ai_import_is_not_callable_by_default(invoke, fetcher):
    with pytest.raises(ToolError, match="Unknown tool"):
        await invoke("import_recipe_with_ai", content="recipe")
    assert fetcher.requests == []


async def test_meal_planning_prompt_uses_consolidated_recipe_read(server):
    mcp, _ = server
    register_prompts(mcp)
    result = await mcp.get_prompt("weekly_meal_plan")
    content = "\n".join(message.content.text for message in result.messages)
    assert "get_recipe:" in content
    assert "concise=true" in content
    assert "concise=false" in content
    assert all(removed not in content for removed in REMOVED_TOOLS)
