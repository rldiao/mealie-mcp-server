import logging
from typing import Any, Dict, Optional

from utils import format_api_params

logger = logging.getLogger("mealie-mcp")


class FoodsMixin:
    """Mixin class for food-related API endpoints (/api/foods)."""

    def get_foods(
        self,
        search: Optional[str] = None,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        query_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List the household's foods (optionally filtered by search term).

        Args:
            search: Search term to filter foods by name/alias
            page: Page number to retrieve
            per_page: Number of items per page
            query_filter: Advanced query filter

        Returns:
            JSON response containing food items and pagination information
        """
        param_dict = {
            "search": search,
            "page": page,
            "perPage": per_page,
            "queryFilter": query_filter,
        }
        params = format_api_params(param_dict)

        logger.info({"message": "Retrieving foods", "parameters": params})
        return self._handle_request("GET", "/api/foods", params=params)

    def create_food(
        self,
        name: str,
        plural_name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new food.

        Args:
            name: Name of the food
            plural_name: Optional plural name
            description: Optional description

        Returns:
            JSON response containing the created food
        """
        if not name:
            raise ValueError("Food name cannot be empty")

        payload: Dict[str, Any] = {"name": name}
        if plural_name is not None:
            payload["pluralName"] = plural_name
        if description is not None:
            payload["description"] = description

        logger.info({"message": "Creating food", "name": name})
        return self._handle_request("POST", "/api/foods", json=payload)

    def get_food(self, food_id: str) -> Dict[str, Any]:
        """Get a specific food by ID.

        Args:
            food_id: The UUID of the food

        Returns:
            JSON response containing the food details
        """
        if not food_id:
            raise ValueError("Food ID cannot be empty")

        logger.info({"message": "Retrieving food", "food_id": food_id})
        return self._handle_request("GET", f"/api/foods/{food_id}")

    def update_food(self, food_id: str, food_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a specific food.

        Mealie's PUT replaces the whole record, so we fetch the existing food
        and merge the provided fields over it. This both preserves fields the
        caller did not set and keeps the required ``id``/``name`` in the body
        (a partial body would null them and fail).

        Args:
            food_id: The UUID of the food to update
            food_data: Dictionary containing the food properties to update

        Returns:
            JSON response containing the updated food
        """
        if not food_id:
            raise ValueError("Food ID cannot be empty")
        if not food_data:
            raise ValueError("Food data cannot be empty")

        existing = self.get_food(food_id)
        merged = {**existing, **food_data} if isinstance(existing, dict) else food_data

        logger.info({"message": "Updating food", "food_id": food_id})
        return self._handle_request("PUT", f"/api/foods/{food_id}", json=merged)

    def delete_food(self, food_id: str) -> Dict[str, Any]:
        """Delete a specific food.

        Args:
            food_id: The UUID of the food to delete

        Returns:
            JSON response confirming deletion
        """
        if not food_id:
            raise ValueError("Food ID cannot be empty")

        logger.info({"message": "Deleting food", "food_id": food_id})
        return self._handle_request("DELETE", f"/api/foods/{food_id}")
