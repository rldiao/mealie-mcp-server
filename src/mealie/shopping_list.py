import logging
from typing import Any, Dict, List, Optional

from utils import format_api_params

logger = logging.getLogger("mealie-mcp")


class ShoppingListMixin:
    """Mixin class for shopping list-related API endpoints"""

    # Shopping List Operations

    def get_shopping_lists(
        self,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        order_by: Optional[str] = None,
        order_direction: Optional[str] = None,
        search: Optional[str] = None,
        query_filter: Optional[str] = None,
        order_by_null_position: Optional[str] = None,
        pagination_seed: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get all shopping lists for the current household.

        Args:
            page: Page number to retrieve
            per_page: Number of items per page
            order_by: Field to order results by
            order_direction: Direction to order results ('asc' or 'desc')
            search: Search term to filter lists
            query_filter: Advanced query filter
            order_by_null_position: How to handle nulls in ordering ('first' or 'last')
            pagination_seed: Seed for consistent pagination

        Returns:
            JSON response containing shopping list items and pagination information
        """
        param_dict = {
            "page": page,
            "perPage": per_page,
            "orderBy": order_by,
            "orderDirection": order_direction,
            "search": search,
            "queryFilter": query_filter,
            "orderByNullPosition": order_by_null_position,
            "paginationSeed": pagination_seed,
        }

        params = format_api_params(param_dict)

        logger.info({"message": "Retrieving shopping lists", "parameters": params})
        return self._handle_request("GET", "/api/households/shopping/lists", params=params)

    def create_shopping_list(self, name: str) -> Dict[str, Any]:
        """Create a new shopping list.

        Args:
            name: Name of the shopping list

        Returns:
            JSON response containing the created shopping list
        """
        if not name:
            raise ValueError("Shopping list name cannot be empty")

        payload = {"name": name}

        logger.info({"message": "Creating shopping list", "name": name})
        return self._handle_request("POST", "/api/households/shopping/lists", json=payload)

    def get_shopping_list(self, list_id: str) -> Dict[str, Any]:
        """Get a specific shopping list by ID.

        Args:
            list_id: The UUID of the shopping list

        Returns:
            JSON response containing the shopping list details
        """
        if not list_id:
            raise ValueError("Shopping list ID cannot be empty")

        logger.info({"message": "Retrieving shopping list", "list_id": list_id})
        return self._handle_request("GET", f"/api/households/shopping/lists/{list_id}")

    def update_shopping_list(self, list_id: str, list_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a specific shopping list.

        Args:
            list_id: The UUID of the shopping list to update
            list_data: Dictionary containing the shopping list properties to update

        Returns:
            JSON response containing the updated shopping list
        """
        if not list_id:
            raise ValueError("Shopping list ID cannot be empty")
        if not list_data:
            raise ValueError("Shopping list data cannot be empty")

        logger.info({"message": "Updating shopping list", "list_id": list_id})

        # Fetch current list to preserve required fields (id, groupId, userId, etc.)
        current_list = self._handle_request("GET", f"/api/households/shopping/lists/{list_id}")

        # Merge caller's changes into the full list object
        merged_data = {**current_list, **list_data}

        return self._handle_request("PUT", f"/api/households/shopping/lists/{list_id}", json=merged_data)

    def delete_shopping_list(self, list_id: str) -> Dict[str, Any]:
        """Delete a specific shopping list.

        Args:
            list_id: The UUID of the shopping list to delete

        Returns:
            JSON response confirming deletion
        """
        if not list_id:
            raise ValueError("Shopping list ID cannot be empty")

        logger.info({"message": "Deleting shopping list", "list_id": list_id})
        return self._handle_request("DELETE", f"/api/households/shopping/lists/{list_id}")

    def add_recipe_to_shopping_list(
        self,
        list_id: str,
        recipe_id: str,
        recipe_increment_quantity: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Add a single recipe's ingredients to a shopping list.

        Args:
            list_id: The UUID of the shopping list
            recipe_id: The UUID of the recipe to add
            recipe_increment_quantity: Multiplier for recipe quantities

        Returns:
            JSON response containing the updated shopping list
        """
        if not list_id:
            raise ValueError("Shopping list ID cannot be empty")
        if not recipe_id:
            raise ValueError("Recipe ID cannot be empty")

        payload = {}
        if recipe_increment_quantity is not None:
            payload["recipeIncrementQuantity"] = recipe_increment_quantity

        logger.info({
            "message": "Adding recipe to shopping list",
            "list_id": list_id,
            "recipe_id": recipe_id,
        })
        return self._handle_request(
            "POST",
            f"/api/households/shopping/lists/{list_id}/recipe/{recipe_id}",
            json=payload,
        )

    def remove_recipe_from_shopping_list(
        self,
        list_id: str,
        recipe_id: str,
    ) -> Dict[str, Any]:
        """Remove a recipe's ingredients from a shopping list.

        Args:
            list_id: The UUID of the shopping list
            recipe_id: The UUID of the recipe to remove

        Returns:
            JSON response containing the updated shopping list
        """
        if not list_id:
            raise ValueError("Shopping list ID cannot be empty")
        if not recipe_id:
            raise ValueError("Recipe ID cannot be empty")

        logger.info({
            "message": "Removing recipe from shopping list",
            "list_id": list_id,
            "recipe_id": recipe_id,
        })
        return self._handle_request(
            "POST",
            f"/api/households/shopping/lists/{list_id}/recipe/{recipe_id}/delete",
        )

    # Shopping List Item Operations

    def get_shopping_list_items(
        self,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        order_by: Optional[str] = None,
        order_direction: Optional[str] = None,
        query_filter: Optional[str] = None,
        search: Optional[str] = None,
        order_by_null_position: Optional[str] = None,
        pagination_seed: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get all shopping list items.

        Args:
            page: Page number to retrieve
            per_page: Number of items per page
            order_by: Field to order results by
            order_direction: Direction to order results ('asc' or 'desc')
            query_filter: Advanced query filter
            search: Search term to filter items
            order_by_null_position: How to handle nulls in ordering ('first' or 'last')
            pagination_seed: Seed for consistent pagination

        Returns:
            JSON response containing shopping list items and pagination information
        """
        param_dict = {
            "page": page,
            "perPage": per_page,
            "orderBy": order_by,
            "orderDirection": order_direction,
            "queryFilter": query_filter,
            "search": search,
            "orderByNullPosition": order_by_null_position,
            "paginationSeed": pagination_seed,
        }

        params = format_api_params(param_dict)

        logger.info({"message": "Retrieving shopping list items", "parameters": params})
        return self._handle_request("GET", "/api/households/shopping/items", params=params)

    def create_shopping_list_item(
        self,
        shopping_list_id: str,
        note: str,
        quantity: Optional[float] = None,
        unit_id: Optional[str] = None,
        food_id: Optional[str] = None,
        label_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new shopping list item.

        Args:
            shopping_list_id: UUID of the shopping list
            note: Item description/note
            quantity: Item quantity
            unit_id: UUID of the unit
            food_id: UUID of the food
            label_id: UUID of the label

        Returns:
            JSON response containing the created shopping list item
        """
        if not shopping_list_id:
            raise ValueError("Shopping list ID cannot be empty")
        if not note:
            raise ValueError("Item note cannot be empty")

        payload = {
            "shoppingListId": shopping_list_id,
            "note": note,
        }

        if quantity is not None:
            payload["quantity"] = quantity
        if unit_id:
            payload["unitId"] = unit_id
        if food_id:
            payload["foodId"] = food_id
        if label_id:
            payload["labelId"] = label_id

        logger.info({"message": "Creating shopping list item", "note": note})
        return self._handle_request("POST", "/api/households/shopping/items", json=payload)

    def create_shopping_list_items_bulk(
        self,
        items: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Create multiple shopping list items in bulk.

        Args:
            items: List of shopping list item dictionaries

        Returns:
            JSON response with creation results (may include per-item status)
        """
        if not items:
            raise ValueError("Items list cannot be empty")

        logger.info({"message": "Creating bulk shopping list items", "count": len(items)})
        return self._handle_request("POST", "/api/households/shopping/items/create-bulk", json=items)

    def get_shopping_list_item(self, item_id: str) -> Dict[str, Any]:
        """Get a specific shopping list item by ID.

        Args:
            item_id: The UUID of the shopping list item

        Returns:
            JSON response containing the shopping list item details
        """
        if not item_id:
            raise ValueError("Shopping list item ID cannot be empty")

        logger.info({"message": "Retrieving shopping list item", "item_id": item_id})
        return self._handle_request("GET", f"/api/households/shopping/items/{item_id}")

    def update_shopping_list_item(
        self,
        item_id: str,
        item_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update a specific shopping list item.

        Uses fetch-merge-update pattern to preserve existing fields.

        Args:
            item_id: The UUID of the shopping list item to update
            item_data: Dictionary containing the item properties to update

        Returns:
            JSON response containing the updated shopping list item
        """
        if not item_id:
            raise ValueError("Shopping list item ID cannot be empty")
        if not item_data:
            raise ValueError("Item data cannot be empty")

        logger.info({"message": "Updating shopping list item", "item_id": item_id})

        # Fetch current item to preserve existing fields
        current_item = self._handle_request("GET", f"/api/households/shopping/items/{item_id}")

        # Merge updates into current item
        merged_data = {**current_item, **item_data}

        return self._handle_request("PUT", f"/api/households/shopping/items/{item_id}", json=merged_data)

    def update_shopping_list_items_bulk(
        self,
        items: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Update multiple shopping list items in bulk.

        Args:
            items: List of shopping list item dictionaries with IDs

        Returns:
            JSON response with update results (may include per-item status)
        """
        if not items:
            raise ValueError("Items list cannot be empty")

        logger.info({"message": "Updating bulk shopping list items", "count": len(items)})
        return self._handle_request("PUT", "/api/households/shopping/items", json=items)

    def delete_shopping_list_item(self, item_id: str) -> Dict[str, Any]:
        """Delete a specific shopping list item.

        Args:
            item_id: The UUID of the shopping list item to delete

        Returns:
            JSON response confirming deletion
        """
        if not item_id:
            raise ValueError("Shopping list item ID cannot be empty")

        logger.info({"message": "Deleting shopping list item", "item_id": item_id})
        return self._handle_request("DELETE", f"/api/households/shopping/items/{item_id}")

    def delete_shopping_list_items_bulk(
        self,
        item_ids: List[str],
    ) -> Dict[str, Any]:
        """Delete multiple shopping list items in bulk.

        Args:
            item_ids: List of shopping list item UUIDs to delete

        Returns:
            JSON response with deletion results
        """
        if not item_ids:
            raise ValueError("Item IDs list cannot be empty")

        params = {"ids": item_ids}

        logger.info({"message": "Deleting bulk shopping list items", "count": len(item_ids)})
        return self._handle_request("DELETE", "/api/households/shopping/items", params=params)
