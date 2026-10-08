from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

from mealie import MealieFetcher
from tools.errors import tool_error_boundary


def register_labels_tools(mcp: FastMCP, mealie: MealieFetcher) -> None:
    """Register all label-related tools with the MCP server."""

    @mcp.tool()
    def get_labels(
        search: Optional[str] = None,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
    ) -> Dict[str, Any]:
        """List the group's labels, optionally filtered by a search term.

        Labels are the colored, group-wide organizers Mealie uses on foods
        and shopping-list items (e.g. "Produce", "Dairy"). Use this to
        resolve an existing label id+name before assigning it to a food.

        Args:
            search: Search term to filter labels by name.
            page: Page number to retrieve.
            per_page: Number of items per page.

        Returns:
            Dict[str, Any]: Labels (under "items") with pagination information.
        """
        with tool_error_boundary("Error fetching labels"):
            return mealie.get_labels(search=search, page=page, per_page=per_page)

    @mcp.tool()
    def create_label(name: str, color: Optional[str] = None) -> Dict[str, Any]:
        """Create a new group label.

        Args:
            name: Name of the label (e.g. "Produce").
            color: Optional hex color for the label (e.g. "#4CAF50").

        Returns:
            Dict[str, Any]: The created label.
        """
        with tool_error_boundary("Error creating label"):
            return mealie.create_label(name, color=color)

    @mcp.tool()
    def get_label(label_id: str) -> Dict[str, Any]:
        """Get a specific label by ID.

        Args:
            label_id: The UUID of the label.

        Returns:
            Dict[str, Any]: The label details.
        """
        with tool_error_boundary("Error fetching label"):
            return mealie.get_label(label_id)

    @mcp.tool()
    def update_label(
        label_id: str,
        name: Optional[str] = None,
        color: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a label's details (only provided fields are changed).

        Args:
            label_id: The UUID of the label to update.
            name: New name for the label.
            color: New hex color for the label.

        Returns:
            Dict[str, Any]: The updated label.
        """
        with tool_error_boundary("Error updating label"):
            label_data: Dict[str, Any] = {}
            if name is not None:
                label_data["name"] = name
            if color is not None:
                label_data["color"] = color

            if not label_data:
                raise ValueError("At least one field must be provided to update")

            return mealie.update_label(label_id, label_data)

    @mcp.tool()
    def delete_label(label_id: str) -> Dict[str, Any]:
        """Delete a specific label.

        Args:
            label_id: The UUID of the label to delete.

        Returns:
            Dict[str, Any]: Confirmation of deletion.
        """
        with tool_error_boundary("Error deleting label"):
            return mealie.delete_label(label_id)
