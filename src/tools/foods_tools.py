import logging
import traceback
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from mealie import MealieFetcher

logger = logging.getLogger("mealie-mcp")


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
        try:
            logger.info(
                {"message": "Fetching foods", "search": search, "per_page": per_page}
            )
            return mealie.get_foods(search=search, page=page, per_page=per_page)
        except Exception as e:
            error_msg = f"Error fetching foods: {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise ToolError(error_msg)

    @mcp.tool()
    def create_food(
        name: str,
        plural_name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new food.

        Args:
            name: Name of the food (e.g. "Reis").
            plural_name: Optional plural name.
            description: Optional description.

        Returns:
            Dict[str, Any]: The created food.
        """
        try:
            logger.info({"message": "Creating food", "name": name})
            return mealie.create_food(
                name, plural_name=plural_name, description=description
            )
        except Exception as e:
            error_msg = f"Error creating food '{name}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise ToolError(error_msg)

    @mcp.tool()
    def get_food(food_id: str) -> Dict[str, Any]:
        """Get a specific food by ID.

        Args:
            food_id: The UUID of the food.

        Returns:
            Dict[str, Any]: The food details.
        """
        try:
            logger.info({"message": "Fetching food", "food_id": food_id})
            return mealie.get_food(food_id)
        except Exception as e:
            error_msg = f"Error fetching food '{food_id}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise ToolError(error_msg)

    @mcp.tool()
    def update_food(
        food_id: str,
        name: Optional[str] = None,
        plural_name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a food's details (only provided fields are changed).

        Args:
            food_id: The UUID of the food to update.
            name: New name for the food.
            plural_name: New plural name.
            description: New description.

        Returns:
            Dict[str, Any]: The updated food.
        """
        try:
            logger.info({"message": "Updating food", "food_id": food_id})

            food_data: Dict[str, Any] = {}
            if name is not None:
                food_data["name"] = name
            if plural_name is not None:
                food_data["pluralName"] = plural_name
            if description is not None:
                food_data["description"] = description

            if not food_data:
                raise ValueError("At least one field must be provided to update")

            return mealie.update_food(food_id, food_data)
        except Exception as e:
            error_msg = f"Error updating food '{food_id}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise ToolError(error_msg)

    @mcp.tool()
    def delete_food(food_id: str) -> Dict[str, Any]:
        """Delete a specific food.

        Args:
            food_id: The UUID of the food to delete.

        Returns:
            Dict[str, Any]: Confirmation of deletion.
        """
        try:
            logger.info({"message": "Deleting food", "food_id": food_id})
            return mealie.delete_food(food_id)
        except Exception as e:
            error_msg = f"Error deleting food '{food_id}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise ToolError(error_msg)
