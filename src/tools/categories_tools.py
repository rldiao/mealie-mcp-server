from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from mealie import MealieFetcher
from tools.errors import tool_error_boundary


def register_categories_tools(mcp: FastMCP, mealie: MealieFetcher) -> None:
    """Register all category-related tools with the MCP server."""

    @mcp.tool()
    def get_categories(
        page: Optional[int] = None,
        per_page: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get all recipe categories with pagination.

        Args:
            page: Page number to retrieve
            per_page: Number of items per page

        Returns:
            Dict[str, Any]: Categories with pagination information
        """
        with tool_error_boundary("Error fetching categories"):
            return mealie.get_categories(page=page, per_page=per_page)

    @mcp.tool()
    def get_empty_categories() -> List[Dict[str, Any]]:
        """Get all categories that have no recipes assigned.

        Returns:
            List[Dict[str, Any]]: List of empty categories
        """
        with tool_error_boundary("Error fetching empty categories"):
            return mealie.get_empty_categories()

    @mcp.tool()
    def create_category(name: str) -> Dict[str, Any]:
        """Create a new recipe category.

        Args:
            name: Name of the category (e.g., "Breakfast", "Desserts", "Vegetarian")

        Returns:
            Dict[str, Any]: The created category details
        """
        with tool_error_boundary("Error creating category"):
            return mealie.create_category(name)

    @mcp.tool()
    def get_category(category_id: str) -> Dict[str, Any]:
        """Get a specific category by ID.

        Args:
            category_id: The UUID of the category

        Returns:
            Dict[str, Any]: The category ID, slug, and name
        """
        with tool_error_boundary("Error fetching category"):
            return mealie.get_category(category_id)

    @mcp.tool()
    def get_category_by_slug(category_slug: str) -> Dict[str, Any]:
        """Get a specific category by its slug.

        Args:
            category_slug: The slug of the category (e.g., "breakfast", "desserts")

        Returns:
            Dict[str, Any]: The category details
        """
        with tool_error_boundary("Error fetching category by slug"):
            return mealie.get_category_by_slug(category_slug)

    @mcp.tool()
    def update_category(
        category_id: str,
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a category's details.

        Args:
            category_id: The UUID of the category to update
            name: New name for the category

        Returns:
            Dict[str, Any]: The updated category details
        """
        with tool_error_boundary("Error updating category"):
            category_data = {}
            if name is not None:
                category_data["name"] = name

            if not category_data:
                raise ValueError("At least one field must be provided to update")

            return mealie.update_category(category_id, category_data)

    @mcp.tool()
    def delete_category(category_id: str) -> Dict[str, Any]:
        """Delete a specific category.

        Args:
            category_id: The UUID of the category to delete

        Returns:
            Dict[str, Any]: Confirmation of deletion
        """
        with tool_error_boundary("Error deleting category"):
            return mealie.delete_category(category_id)
