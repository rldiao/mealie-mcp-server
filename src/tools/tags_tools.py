from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from mealie import MealieFetcher
from tools.errors import tool_error_boundary


def register_tags_tools(mcp: FastMCP, mealie: MealieFetcher) -> None:
    """Register all tag-related tools with the MCP server."""

    @mcp.tool()
    def get_tags(
        page: Optional[int] = None,
        per_page: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get all recipe tags with pagination.

        Args:
            page: Page number to retrieve
            per_page: Number of items per page

        Returns:
            Dict[str, Any]: Tags with pagination information
        """
        with tool_error_boundary("Error fetching tags"):
            return mealie.get_tags(page=page, per_page=per_page)

    @mcp.tool()
    def get_empty_tags() -> List[Dict[str, Any]]:
        """Get all tags that have no recipes assigned.

        Returns:
            List[Dict[str, Any]]: List of empty tags
        """
        with tool_error_boundary("Error fetching empty tags"):
            return mealie.get_empty_tags()

    @mcp.tool()
    def create_tag(name: str) -> Dict[str, Any]:
        """Create a new recipe tag.

        Args:
            name: Name of the tag (e.g., "Quick", "Healthy", "Family Favorite")

        Returns:
            Dict[str, Any]: The created tag details
        """
        with tool_error_boundary("Error creating tag"):
            return mealie.create_tag(name)

    @mcp.tool()
    def get_tag(
        tag_id: Optional[str] = None,
        tag_slug: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get a specific tag by ID or slug. Provide exactly one nonempty identifier.

        Args:
            tag_id: The UUID of the tag
            tag_slug: The slug of the tag (e.g., "quick", "healthy")

        Returns:
            Dict[str, Any]: The tag details including associated recipes
        """
        with tool_error_boundary("Error fetching tag"):
            if (
                (tag_id is None) == (tag_slug is None)
                or (tag_id is not None and not tag_id.strip())
                or (tag_slug is not None and not tag_slug.strip())
            ):
                raise ValueError("Provide exactly one nonempty tag_id or tag_slug")
            if tag_id is not None:
                return mealie.get_tag(tag_id)
            return mealie.get_tag_by_slug(tag_slug)

    @mcp.tool()
    def update_tag(
        tag_id: str,
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a tag's details.

        Args:
            tag_id: The UUID of the tag to update
            name: New name for the tag

        Returns:
            Dict[str, Any]: The updated tag details
        """
        with tool_error_boundary("Error updating tag"):
            tag_data = {}
            if name is not None:
                tag_data["name"] = name

            if not tag_data:
                raise ValueError("At least one field must be provided to update")

            return mealie.update_tag(tag_id, tag_data)

    @mcp.tool()
    def delete_tag(tag_id: str) -> Dict[str, Any]:
        """Delete a specific tag.

        Args:
            tag_id: The UUID of the tag to delete

        Returns:
            Dict[str, Any]: Confirmation of deletion
        """
        with tool_error_boundary("Error deleting tag"):
            return mealie.delete_tag(tag_id)
