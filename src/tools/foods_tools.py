from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

from mealie import MealieFetcher
from tools.errors import tool_error_boundary


def register_foods_tools(mcp: FastMCP, mealie: MealieFetcher) -> None:
    """Register all food-related tools with the MCP server."""

    @mcp.tool()
    def get_foods(
        search: Optional[str] = None,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
    ) -> Dict[str, Any]:
        """List the household's foods, optionally filtered by a search term.

        Use this to resolve an existing Mealie food id+name before building a
        structured ingredient, instead of hardcoding UUIDs. The Mealie search is
        token-based; do client-side matching against the returned items if you
        need fuzzy matching (e.g. "Basmatireis" -> "Reis").

        Args:
            search: Search term to filter foods by name/alias.
            page: Page number to retrieve.
            per_page: Number of items per page.

        Returns:
            Dict[str, Any]: Foods (under "items") with pagination information.
        """
        with tool_error_boundary("Error fetching foods"):
            return mealie.get_foods(search=search, page=page, per_page=per_page)

    @mcp.tool()
    def create_food(
        name: str,
        plural_name: Optional[str] = None,
        description: Optional[str] = None,
        extras: Optional[Dict[str, Any]] = None,
        label_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new food.

        Args:
            name: Name of the food (e.g. "Reis").
            plural_name: Optional plural name.
            description: Optional description.
            extras: Optional arbitrary key-value metadata dict stored on the food
                (Mealie's ``extras`` field) — e.g. external identifiers.
            label_id: Optional UUID of a Multi Purpose Label to assign (used for
                aisle/section grouping on shopping lists).

        Returns:
            Dict[str, Any]: The created food.
        """
        with tool_error_boundary("Error creating food"):
            return mealie.create_food(
                name,
                plural_name=plural_name,
                description=description,
                extras=extras,
                label_id=label_id,
            )

    @mcp.tool()
    def get_food(food_id: str) -> Dict[str, Any]:
        """Get a specific food by ID.

        Args:
            food_id: The UUID of the food.

        Returns:
            Dict[str, Any]: The food details.
        """
        with tool_error_boundary("Error fetching food"):
            return mealie.get_food(food_id)

    @mcp.tool()
    def update_food(
        food_id: str,
        name: Optional[str] = None,
        plural_name: Optional[str] = None,
        description: Optional[str] = None,
        extras: Optional[Dict[str, Any]] = None,
        label_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a food's details (only provided fields are changed).

        Args:
            food_id: The UUID of the food to update.
            name: New name for the food.
            plural_name: New plural name.
            description: New description.
            extras: Arbitrary key-value metadata dict to store on the food
                (Mealie's ``extras`` field). Replaces the food's existing extras.
            label_id: UUID of a Multi Purpose Label to assign (aisle/section
                grouping). Pass an empty string to clear the label.

        Returns:
            Dict[str, Any]: The updated food.
        """
        with tool_error_boundary("Error updating food"):
            food_data: Dict[str, Any] = {}
            if name is not None:
                food_data["name"] = name
            if plural_name is not None:
                food_data["pluralName"] = plural_name
            if description is not None:
                food_data["description"] = description
            if extras is not None:
                food_data["extras"] = extras
            if label_id is not None:
                # "" is the caller's "clear the label" sentinel; Mealie's API
                # rejects an empty string for a UUID field and wants null instead.
                food_data["labelId"] = label_id or None

            if not food_data:
                raise ValueError("At least one field must be provided to update")

            return mealie.update_food(food_id, food_data)

    @mcp.tool()
    def delete_food(food_id: str) -> Dict[str, Any]:
        """Delete a specific food.

        Args:
            food_id: The UUID of the food to delete.

        Returns:
            Dict[str, Any]: Confirmation of deletion.
        """
        with tool_error_boundary("Error deleting food"):
            return mealie.delete_food(food_id)
