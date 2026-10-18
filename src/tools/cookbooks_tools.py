from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

from mealie import MealieFetcher
from tools.errors import tool_error_boundary

def _cookbook_fields(
    name: Optional[str],
    query_filter: Optional[str],
    description: Optional[str],
    public: Optional[bool],
    position: Optional[int],
) -> Dict[str, Any]:
    fields = {
        "name": name,
        "queryFilterString": query_filter,
        "description": description,
        "public": public,
        "position": position,
    }
    return {key: value for key, value in fields.items() if value is not None}


def register_cookbooks_tools(mcp: FastMCP, mealie: MealieFetcher) -> None:
    """Register household cookbook tools with the MCP server."""

    @mcp.tool()
    def get_cookbooks(
        page: Optional[int] = None, per_page: Optional[int] = None
    ) -> Dict[str, Any]:
        """List the household's cookbooks: named, saved recipe filters.

        To list a cookbook's recipes, call get_recipes with cookbook=<slug>.

        Returns:
            Dict[str, Any]: Cookbooks (under "items") with their
            queryFilterString, plus pagination information.
        """
        with tool_error_boundary("Error fetching cookbooks"):
            return mealie.get_cookbooks(page=page, per_page=per_page)

    @mcp.tool()
    def create_cookbook(
        name: str,
        query_filter: str = "",
        description: str = "",
        public: bool = False,
        position: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create a cookbook, a named recipe filter shown in Mealie's sidebar.

        Args:
            name: Cookbook name, e.g. "Weeknight Dinners".
            query_filter: Mealie query filter choosing the recipes, e.g.
                "totalTimeSeconds <= 1800 AND rating >= 4" or
                'tags.name CONTAINS ALL ["Vegan"]'. Mealie rejects invalid
                filters. Empty includes every recipe.
            description: Optional description.
            public: Show the cookbook to people who are not logged in.
            position: Sidebar order (Mealie defaults to 1).

        Returns:
            Dict[str, Any]: The created cookbook.
        """
        with tool_error_boundary("Error creating cookbook"):
            return mealie.create_cookbook(
                _cookbook_fields(name, query_filter, description, public, position)
            )

    @mcp.tool()
    def update_cookbook(
        cookbook_id: str,
        name: Optional[str] = None,
        query_filter: Optional[str] = None,
        description: Optional[str] = None,
        public: Optional[bool] = None,
        position: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Change some fields of a cookbook; omitted fields are kept.

        Args:
            cookbook_id: Cookbook ID or slug.
            name: New name.
            query_filter: New recipe filter; "" includes every recipe.
            description: New description.
            public: Whether people who are not logged in can see it.
            position: Sidebar order.

        Returns:
            Dict[str, Any]: The updated cookbook.
        """
        with tool_error_boundary("Error updating cookbook"):
            return mealie.update_cookbook(
                cookbook_id,
                _cookbook_fields(name, query_filter, description, public, position),
            )

    @mcp.tool()
    def delete_cookbook(cookbook_id: str) -> Dict[str, Any]:
        """Delete a cookbook. The recipes it listed are not affected.

        Args:
            cookbook_id: Cookbook ID.

        Returns:
            Dict[str, Any]: Confirmation of deletion.
        """
        with tool_error_boundary("Error deleting cookbook"):
            return mealie.delete_cookbook(cookbook_id)
