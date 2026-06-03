from .categories_tools import register_categories_tools
from .foods_tools import register_foods_tools
from .mealplan_tools import register_mealplan_tools
from .recipe_tools import register_recipe_tools
from .shopping_list_tools import register_shopping_list_tools
from .tags_tools import register_tags_tools
from .tools_tools import register_tools_tools
from .units_tools import register_units_tools


def register_all_tools(mcp, mealie):
    """Register all tools with the MCP server."""
    register_recipe_tools(mcp, mealie)
    register_categories_tools(mcp, mealie)
    register_tags_tools(mcp, mealie)
    register_foods_tools(mcp, mealie)
    register_units_tools(mcp, mealie)
    register_tools_tools(mcp, mealie)
    register_shopping_list_tools(mcp, mealie)
    register_mealplan_tools(mcp, mealie)


__all__ = [
    "register_all_tools",
    "register_recipe_tools",
    "register_categories_tools",
    "register_tags_tools",
    "register_foods_tools",
    "register_units_tools",
    "register_tools_tools",
    "register_shopping_list_tools",
    "register_mealplan_tools",
]
