from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from mealie import MealieFetcher
from models.shopping_list import ShoppingListItemCreate, ShoppingListItemUpdate
from tools.errors import tool_error_boundary


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
        with tool_error_boundary("Error fetching shopping lists"):
            return mealie.get_shopping_lists(page=page, per_page=per_page)

    @mcp.tool()
    def create_shopping_list(name: str) -> Dict[str, Any]:
        """Create a new shopping list.

        Args:
            name: Name of the shopping list

        Returns:
            Dict[str, Any]: The created shopping list details
        """
        with tool_error_boundary("Error creating shopping list"):
            return mealie.create_shopping_list(name)

    @mcp.tool()
    def get_shopping_list(list_id: str) -> Dict[str, Any]:
        """Get a specific shopping list by ID.

        Args:
            list_id: The UUID of the shopping list

        Returns:
            Dict[str, Any]: The shopping list details including all items
        """
        with tool_error_boundary("Error fetching shopping list"):
            return mealie.get_shopping_list(list_id)

    @mcp.tool()
    def update_shopping_list(list_id: str, name: str) -> Dict[str, Any]:
        """Update a shopping list's properties (e.g. rename it).

        Args:
            list_id: The UUID of the shopping list to update.
            name: The new name for the shopping list.

        Returns:
            Dict[str, Any]: The updated shopping list details.
        """
        with tool_error_boundary("Error updating shopping list"):
            return mealie.update_shopping_list(list_id, {"name": name})

    @mcp.tool()
    def delete_shopping_list(list_id: str) -> Dict[str, Any]:
        """Delete a specific shopping list.

        Args:
            list_id: The UUID of the shopping list to delete

        Returns:
            Dict[str, Any]: Confirmation of deletion
        """
        with tool_error_boundary("Error deleting shopping list"):
            return mealie.delete_shopping_list(list_id)

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
        with tool_error_boundary("Error adding recipe to shopping list"):
            return mealie.add_recipe_to_shopping_list(
                list_id, recipe_id, recipe_increment_quantity
            )

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
        with tool_error_boundary("Error removing recipe from shopping list"):
            return mealie.remove_recipe_from_shopping_list(list_id, recipe_id)

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
        with tool_error_boundary("Error fetching shopping list items"):
            return mealie.get_shopping_list_items(
                page=page, per_page=per_page, search=search
            )

    @mcp.tool()
    def get_shopping_list_item(item_id: str) -> Dict[str, Any]:
        """Get a specific shopping list item by ID.

        Args:
            item_id: The UUID of the shopping list item

        Returns:
            Dict[str, Any]: The shopping list item details
        """
        with tool_error_boundary("Error fetching shopping list item"):
            return mealie.get_shopping_list_item(item_id)

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
        with tool_error_boundary("Error creating shopping list item"):
            return mealie.create_shopping_list_item(
                shopping_list_id, note, quantity, unit_id, food_id, label_id
            )

    @mcp.tool()
    def create_shopping_list_items_bulk(
        items: List[ShoppingListItemCreate],
    ) -> Dict[str, Any]:
        """Create multiple shopping list items at once.

        Args:
            items: List of item dictionaries, each containing:
                - shopping_list_id (str): UUID of the shopping list
                - note (str): Item description
                - quantity (float, optional): Item quantity
                - unit_id (str, optional): UUID of the unit
                - food_id (str, optional): UUID of the food
                - label_id (str, optional): UUID of the label

            API camelCase aliases are also accepted.

        Returns:
            Dict[str, Any]: Results of the bulk creation operation
        """
        with tool_error_boundary("Error creating bulk shopping list items"):
            return mealie.create_shopping_list_items_bulk(items)

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
        with tool_error_boundary("Error updating shopping list item"):
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

    @mcp.tool()
    def delete_shopping_list_item(item_id: str) -> Dict[str, Any]:
        """Delete a specific shopping list item.

        Args:
            item_id: The UUID of the shopping list item to delete

        Returns:
            Dict[str, Any]: Confirmation of deletion
        """
        with tool_error_boundary("Error deleting shopping list item"):
            return mealie.delete_shopping_list_item(item_id)

    @mcp.tool()
    def update_shopping_list_items_bulk(
        items: List[ShoppingListItemUpdate],
    ) -> Dict[str, Any]:
        """Update multiple shopping list items at once.

        Each item dictionary must include:
        - id: The item UUID
        - At least one field to update (note, quantity, checked, etc.)

        Missing fields are preserved from the current item. Explicit null clears
        nullable fields. Snake_case and API camelCase aliases are accepted.

        Args:
            items: List of item dictionaries with IDs and fields to update

        Returns:
            Dict[str, Any]: Results of the bulk update operation
        """
        with tool_error_boundary("Error updating bulk shopping list items"):
            return mealie.update_shopping_list_items_bulk(items)

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
        with tool_error_boundary("Error deleting bulk shopping list items"):
            return mealie.delete_shopping_list_items_bulk(item_ids)
