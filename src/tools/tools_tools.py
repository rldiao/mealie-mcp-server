import logging
import traceback
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from mealie import MealieFetcher

logger = logging.getLogger("mealie-mcp")


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
        create_recipe_full or patch_recipe. Each item includes
        ``householdsWithTool``: a non-empty value means the household owns the
        tool, an empty list means it only exists in the database.

        Args:
            search: Search term to filter tools by name.
            page: Page number to retrieve.
            per_page: Number of items per page.

        Returns:
            Dict[str, Any]: Tools (under "items") with pagination information.
        """
        try:
            logger.info(
                {"message": "Fetching tools", "search": search, "per_page": per_page}
            )
            return mealie.get_tools(search=search, page=page, per_page=per_page)
        except Exception as e:
            error_msg = f"Error fetching tools: {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise ToolError(error_msg)

    @mcp.tool()
    def create_tool(name: str) -> Dict[str, Any]:
        """Create a new recipe tool.

        Args:
            name: Name of the tool (e.g. "Kochtopf", "Backofen").

        Returns:
            Dict[str, Any]: The created tool.
        """
        try:
            logger.info({"message": "Creating tool", "name": name})
            return mealie.create_tool(name)
        except Exception as e:
            error_msg = f"Error creating tool '{name}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise ToolError(error_msg)

    @mcp.tool()
    def get_tool(tool_id: str) -> Dict[str, Any]:
        """Get a specific tool by ID.

        Args:
            tool_id: The UUID of the tool.

        Returns:
            Dict[str, Any]: The tool details.
        """
        try:
            logger.info({"message": "Fetching tool", "tool_id": tool_id})
            return mealie.get_tool(tool_id)
        except Exception as e:
            error_msg = f"Error fetching tool '{tool_id}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise ToolError(error_msg)

    @mcp.tool()
    def get_tool_by_slug(tool_slug: str) -> Dict[str, Any]:
        """Get a specific tool by its slug.

        Args:
            tool_slug: The slug of the tool (e.g. "kochtopf").

        Returns:
            Dict[str, Any]: The tool details.
        """
        try:
            logger.info({"message": "Fetching tool by slug", "tool_slug": tool_slug})
            return mealie.get_tool_by_slug(tool_slug)
        except Exception as e:
            error_msg = f"Error fetching tool by slug '{tool_slug}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise ToolError(error_msg)

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
        try:
            logger.info({"message": "Updating tool", "tool_id": tool_id})

            tool_data: Dict[str, Any] = {}
            if name is not None:
                tool_data["name"] = name

            if not tool_data:
                raise ValueError("At least one field must be provided to update")

            return mealie.update_tool(tool_id, tool_data)
        except Exception as e:
            error_msg = f"Error updating tool '{tool_id}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise ToolError(error_msg)

    @mcp.tool()
    def delete_tool(tool_id: str) -> Dict[str, Any]:
        """Delete a specific tool.

        Args:
            tool_id: The UUID of the tool to delete.

        Returns:
            Dict[str, Any]: Confirmation of deletion.
        """
        try:
            logger.info({"message": "Deleting tool", "tool_id": tool_id})
            return mealie.delete_tool(tool_id)
        except Exception as e:
            error_msg = f"Error deleting tool '{tool_id}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise ToolError(error_msg)
