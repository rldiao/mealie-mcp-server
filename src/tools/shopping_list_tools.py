import logging
import traceback
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from mealie import MealieFetcher

logger = logging.getLogger("mealie-mcp")


def register_shopping_list_tools(mcp: FastMCP, mealie: MealieFetcher) -> None:
    """Register all shopping list-related tools with the MCP server."""

    # Shopping List Operations

    @mcp.tool()
    def get_shopping_lists(
        page: Optional[int] = None,
        per_page: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get all shopping lists for the current household with pagination.

        Args:
            page: Page number to retrieve
            per_page: Number of items per page

        Returns:
            Dict[str, Any]: Shopping lists with pagination information
        """
        try:
            logger.info({"message": "Fetching shopping lists", "page": page, "per_page": per_page})
            return mealie.get_shopping_lists(page=page, per_page=per_page)
        except Exception as e:
            error_msg = f"Error fetching shopping lists: {str(e)}"
            logger.error({"message": error_msg})
            logger.debug({"message": "Error traceback", "traceback": traceback.format_exc()})
            raise ToolError(error_msg)

    @mcp.tool()
    def create_shopping_list(name: str) -> Dict[str, Any]:
        """Create a new shopping list.

        Args:
            name: Name of the shopping list

        Returns:
            Dict[str, Any]: The created shopping list details
        """
        try:
            logger.info({"message": "Creating shopping list", "name": name})
            return mealie.create_shopping_list(name)
        except Exception as e:
            error_msg = f"Error creating shopping list '{name}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug({"message": "Error traceback", "traceback": traceback.format_exc()})
            raise ToolError(error_msg)

    @mcp.tool()
    def get_shopping_list(list_id: str) -> Dict[str, Any]:
        """Get a specific shopping list by ID.

        Args:
            list_id: The UUID of the shopping list

        Returns:
            Dict[str, Any]: The shopping list details including all items
        """
        try:
            logger.info({"message": "Fetching shopping list", "list_id": list_id})
            return mealie.get_shopping_list(list_id)
        except Exception as e:
            error_msg = f"Error fetching shopping list '{list_id}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug({"message": "Error traceback", "traceback": traceback.format_exc()})
            raise ToolError(error_msg)

    @mcp.tool()
    def update_shopping_list(list_id: str, name: str) -> Dict[str, Any]:
        """Update a shopping list's properties (e.g. rename it).

        Args:
            list_id: The UUID of the shopping list to update.
            name: The new name for the shopping list.

        Returns:
            Dict[str, Any]: The updated shopping list details.
        """
        try:
            logger.info({"message": "Updating shopping list", "list_id": list_id, "name": name})
            return mealie.update_shopping_list(list_id, {"name": name})
        except Exception as e:
            error_msg = f"Error updating shopping list '{list_id}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug({"message": "Error traceback", "traceback": traceback.format_exc()})
            raise ToolError(error_msg)

    @mcp.tool()
    def delete_shopping_list(list_id: str) -> Dict[str, Any]:
        """Delete a specific shopping list.

        Args:
            list_id: The UUID of the shopping list to delete

        Returns:
            Dict[str, Any]: Confirmation of deletion
        """
        try:
            logger.info({"message": "Deleting shopping list", "list_id": list_id})
            return mealie.delete_shopping_list(list_id)
        except Exception as e:
            error_msg = f"Error deleting shopping list '{list_id}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug({"message": "Error traceback", "traceback": traceback.format_exc()})
            raise ToolError(error_msg)

    @mcp.tool()
    def add_recipe_to_shopping_list(
        list_id: str,
        recipe_id: str,
        recipe_increment_quantity: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Add a recipe's ingredients to a shopping list.

        Args:
            list_id: The UUID of the shopping list
            recipe_id: The UUID of the recipe to add
            recipe_increment_quantity: Multiplier for recipe quantities (e.g., 2.0 for double)

        Returns:
            Dict[str, Any]: The updated shopping list
        """
        try:
            logger.info({
                "message": "Adding recipe to shopping list",
                "list_id": list_id,
                "recipe_id": recipe_id,
            })
            return mealie.add_recipe_to_shopping_list(
                list_id, recipe_id, recipe_increment_quantity
            )
        except Exception as e:
            error_msg = f"Error adding recipe to shopping list: {str(e)}"
            logger.error({"message": error_msg})
            logger.debug({"message": "Error traceback", "traceback": traceback.format_exc()})
            raise ToolError(error_msg)

    @mcp.tool()
    def remove_recipe_from_shopping_list(
        list_id: str,
        recipe_id: str,
    ) -> Dict[str, Any]:
        """Remove a recipe's ingredients from a shopping list.

        Args:
            list_id: The UUID of the shopping list
            recipe_id: The UUID of the recipe to remove

        Returns:
            Dict[str, Any]: The updated shopping list
        """
        try:
            logger.info({
                "message": "Removing recipe from shopping list",
                "list_id": list_id,
                "recipe_id": recipe_id,
            })
            return mealie.remove_recipe_from_shopping_list(list_id, recipe_id)
        except Exception as e:
            error_msg = f"Error removing recipe from shopping list: {str(e)}"
            logger.error({"message": error_msg})
            logger.debug({"message": "Error traceback", "traceback": traceback.format_exc()})
            raise ToolError(error_msg)

    # Shopping List Item Operations

    @mcp.tool()
    def get_shopping_list_items(
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get all shopping list items with pagination and search.

        Args:
            page: Page number to retrieve
            per_page: Number of items per page
            search: Search term to filter items

        Returns:
            Dict[str, Any]: Shopping list items with pagination information
        """
        try:
            logger.info({
                "message": "Fetching shopping list items",
                "page": page,
                "per_page": per_page,
                "search": search,
            })
            return mealie.get_shopping_list_items(
                page=page, per_page=per_page, search=search
            )
        except Exception as e:
            error_msg = f"Error fetching shopping list items: {str(e)}"
            logger.error({"message": error_msg})
            logger.debug({"message": "Error traceback", "traceback": traceback.format_exc()})
            raise ToolError(error_msg)

    @mcp.tool()
    def get_shopping_list_item(item_id: str) -> Dict[str, Any]:
        """Get a specific shopping list item by ID.

        Args:
            item_id: The UUID of the shopping list item

        Returns:
            Dict[str, Any]: The shopping list item details
        """
        try:
            logger.info({"message": "Fetching shopping list item", "item_id": item_id})
            return mealie.get_shopping_list_item(item_id)
        except Exception as e:
            error_msg = f"Error fetching shopping list item '{item_id}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug({"message": "Error traceback", "traceback": traceback.format_exc()})
            raise ToolError(error_msg)

    @mcp.tool()
    def create_shopping_list_item(
        shopping_list_id: str,
        note: str,
        quantity: Optional[float] = None,
        unit_id: Optional[str] = None,
        food_id: Optional[str] = None,
        label_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new item in a shopping list.

        Args:
            shopping_list_id: UUID of the shopping list
            note: Item description (e.g., "2 lbs chicken breast")
            quantity: Item quantity
            unit_id: UUID of the unit (optional)
            food_id: UUID of the food (optional)
            label_id: UUID of the label (optional)

        Returns:
            Dict[str, Any]: The created shopping list item
        """
        try:
            logger.info({
                "message": "Creating shopping list item",
                "shopping_list_id": shopping_list_id,
                "note": note,
            })
            return mealie.create_shopping_list_item(
                shopping_list_id, note, quantity, unit_id, food_id, label_id
            )
        except Exception as e:
            error_msg = f"Error creating shopping list item: {str(e)}"
            logger.error({"message": error_msg})
            logger.debug({"message": "Error traceback", "traceback": traceback.format_exc()})
            raise ToolError(error_msg)

    @mcp.tool()
    def create_shopping_list_items_bulk(
        items: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Create multiple shopping list items at once.

        Args:
            items: List of item dictionaries, each containing:
                - shopping_list_id (str): UUID of the shopping list
                - note (str): Item description
                - quantity (float, optional): Item quantity
                - unit_id (str, optional): UUID of the unit
                - food_id (str, optional): UUID of the food

        Returns:
            Dict[str, Any]: Results of the bulk creation operation
        """
        try:
            logger.info({"message": "Creating bulk shopping list items", "count": len(items)})
            return mealie.create_shopping_list_items_bulk(items)
        except Exception as e:
            error_msg = f"Error creating bulk shopping list items: {str(e)}"
            logger.error({"message": error_msg})
            logger.debug({"message": "Error traceback", "traceback": traceback.format_exc()})
            raise ToolError(error_msg)

    @mcp.tool()
    def update_shopping_list_item(
        item_id: str,
        note: Optional[str] = None,
        quantity: Optional[float] = None,
        checked: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Update a shopping list item. Use this to check/uncheck items or modify their details.

        Args:
            item_id: The UUID of the shopping list item to update
            note: Updated item description
            quantity: Updated quantity
            checked: Whether the item is checked off

        Returns:
            Dict[str, Any]: The updated shopping list item
        """
        try:
            logger.info({"message": "Updating shopping list item", "item_id": item_id})

            item_data = {}
            if note is not None:
                item_data["note"] = note
            if quantity is not None:
                item_data["quantity"] = quantity
            if checked is not None:
                item_data["checked"] = checked

            if not item_data:
                raise ValueError("At least one field must be provided to update")

            return mealie.update_shopping_list_item(item_id, item_data)
        except Exception as e:
            error_msg = f"Error updating shopping list item '{item_id}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug({"message": "Error traceback", "traceback": traceback.format_exc()})
            raise ToolError(error_msg)

    @mcp.tool()
    def delete_shopping_list_item(item_id: str) -> Dict[str, Any]:
        """Delete a specific shopping list item.

        Args:
            item_id: The UUID of the shopping list item to delete

        Returns:
            Dict[str, Any]: Confirmation of deletion
        """
        try:
            logger.info({"message": "Deleting shopping list item", "item_id": item_id})
            return mealie.delete_shopping_list_item(item_id)
        except Exception as e:
            error_msg = f"Error deleting shopping list item '{item_id}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug({"message": "Error traceback", "traceback": traceback.format_exc()})
            raise ToolError(error_msg)

    @mcp.tool()
    def update_shopping_list_items_bulk(
        items: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Update multiple shopping list items at once.

        IMPORTANT: Each item dictionary must include:
        - id: The item UUID
        - shoppingListId: The shopping list UUID
        - Any other fields you want to update (note, quantity, checked, etc.)

        Args:
            items: List of item dictionaries with IDs, shoppingListId, and fields to update

        Returns:
            Dict[str, Any]: Results of the bulk update operation
        """
        try:
            logger.info({"message": "Updating bulk shopping list items", "count": len(items)})
            return mealie.update_shopping_list_items_bulk(items)
        except Exception as e:
            error_msg = f"Error updating bulk shopping list items: {str(e)}"
            logger.error({"message": error_msg})
            logger.debug({"message": "Error traceback", "traceback": traceback.format_exc()})
            raise ToolError(error_msg)

    @mcp.tool()
    def delete_shopping_list_items_bulk(
        item_ids: List[str],
    ) -> Dict[str, Any]:
        """Delete multiple shopping list items at once.

        Args:
            item_ids: List of shopping list item UUIDs to delete

        Returns:
            Dict[str, Any]: Results of the bulk deletion operation
        """
        try:
            logger.info({"message": "Deleting bulk shopping list items", "count": len(item_ids)})
            return mealie.delete_shopping_list_items_bulk(item_ids)
        except Exception as e:
            error_msg = f"Error deleting bulk shopping list items: {str(e)}"
            logger.error({"message": error_msg})
            logger.debug({"message": "Error traceback", "traceback": traceback.format_exc()})
            raise ToolError(error_msg)
