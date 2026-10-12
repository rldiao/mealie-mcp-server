from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from mealie import MealieFetcher
from tools.errors import tool_error_boundary


def register_tools_tools(mcp: FastMCP, mealie: MealieFetcher) -> None:
    """Register all recipe-tool (kitchen equipment) tools with the MCP server."""

    @mcp.tool()
    def get_tools(
        search: Optional[str] = None,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
    ) -> Dict[str, Any]:
        """List the household's recipe tools, optionally filtered by a search term.

        Use this to resolve a tool id+name before assigning it to a recipe via
        create_recipe or update_recipe. Each item includes
        ``householdsWithTool``, a list of household IDs. A household owns the
        tool only if its ID appears in that list; a non-empty list alone does
        not establish ownership by the current household.

        Args:
            search: Search term to filter tools by name.
            page: Page number to retrieve.
            per_page: Number of items per page.

        Returns:
            Dict[str, Any]: Tools (under "items") with pagination information.
        """
        with tool_error_boundary("Error fetching tools"):
            return mealie.get_tools(search=search, page=page, per_page=per_page)

    @mcp.tool()
    def create_tool(name: str) -> Dict[str, Any]:
        """Create a new recipe tool.

        Args:
            name: Name of the tool (e.g. "Kochtopf", "Backofen").

        Returns:
            Dict[str, Any]: The created tool.
        """
        with tool_error_boundary("Error creating tool"):
            return mealie.create_tool(name)

    @mcp.tool()
    def get_tool(
        tool_id: Optional[str] = None,
        tool_slug: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get a specific tool by ID or slug. Provide exactly one nonempty identifier.

        Args:
            tool_id: The UUID of the tool.
            tool_slug: The slug of the tool (e.g. "kochtopf").

        Returns:
            Dict[str, Any]: The tool details.
        """
        with tool_error_boundary("Error fetching tool"):
            if (
                (tool_id is None) == (tool_slug is None)
                or (tool_id is not None and not tool_id.strip())
                or (tool_slug is not None and not tool_slug.strip())
            ):
                raise ValueError("Provide exactly one nonempty tool_id or tool_slug")
            if tool_id is not None:
                return mealie.get_tool(tool_id)
            return mealie.get_tool_by_slug(tool_slug)

    @mcp.tool()
    def update_tool(
        tool_id: str,
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a tool's details (only provided fields are changed).

        Args:
            tool_id: The UUID of the tool to update.
            name: New name for the tool.

        Returns:
            Dict[str, Any]: The updated tool.
        """
        with tool_error_boundary("Error updating tool"):
            tool_data: Dict[str, Any] = {}
            if name is not None:
                tool_data["name"] = name

            if not tool_data:
                raise ValueError("At least one field must be provided to update")

            return mealie.update_tool(tool_id, tool_data)

    @mcp.tool()
    def set_tool_on_hand(tool_id: str, on_hand: bool = True) -> Dict[str, Any]:
        """Mark or unmark a tool as owned (on hand) by the current household.

        Args:
            tool_id: The UUID of the tool.
            on_hand: True to mark owned, False to clear it. Defaults to True.

        Returns:
            Dict[str, Any]: The updated tool.
        """
        with tool_error_boundary("Error setting tool on-hand status"):
            return mealie.set_tool_on_hand(tool_id, on_hand=on_hand)

    @mcp.tool()
    def mark_tools_on_hand(names: List[str], on_hand: bool = True) -> Dict[str, Any]:
        """Mark or unmark kitchen tools the household owns, by name.

        Use this instead of set_tool_on_hand when you know tool names (e.g.
        "Stand Mixer", "Dutch Oven", "Food Processor") but not their Mealie
        tool IDs. Names are matched case-insensitively against existing
        tools; a name with no match is created as a new tool.

        Args:
            names: Tool names to update.
            on_hand: True to mark owned, False to clear it. Defaults to True.

        Returns:
            Dict[str, Any]: {"updated": [...updated tools], "created": [...names of tools that were created]}.
        """
        with tool_error_boundary("Error marking tools on-hand"):
            return mealie.set_tools_on_hand_by_name(names, on_hand=on_hand)

    @mcp.tool()
    def delete_tool(tool_id: str) -> Dict[str, Any]:
        """Delete a specific tool.

        Args:
            tool_id: The UUID of the tool to delete.

        Returns:
            Dict[str, Any]: Confirmation of deletion.
        """
        with tool_error_boundary("Error deleting tool"):
            return mealie.delete_tool(tool_id)
