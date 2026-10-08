import logging
from typing import Any, Dict, List, Optional

from utils import format_api_params

logger = logging.getLogger("mealie-mcp")


class CategoriesMixin:
    """Mixin class for recipe category-related API endpoints"""

    def get_categories(
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
        """Get all recipe categories.

        Args:
            page: Page number to retrieve
            per_page: Number of items per page
            order_by: Field to order results by
            order_direction: Direction to order results ('asc' or 'desc')
            search: Search term to filter categories
            query_filter: Advanced query filter
            order_by_null_position: How to handle nulls in ordering ('first' or 'last')
            pagination_seed: Seed for consistent pagination

        Returns:
            JSON response containing category items and pagination information
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

        logger.info({"message": "Retrieving categories"})
        return self._handle_request("GET", "/api/organizers/categories", params=params)

    def get_empty_categories(self) -> List[Dict[str, Any]]:
        """Get all categories that have no recipes assigned.

        Returns:
            List of empty categories
        """
        logger.info({"message": "Retrieving empty categories"})
        return self._handle_request("GET", "/api/organizers/categories/empty")

    def create_category(self, name: str) -> Dict[str, Any]:
        """Create a new recipe category.

        Args:
            name: Name of the category

        Returns:
            JSON response containing the created category
        """
        if not name:
            raise ValueError("Category name cannot be empty")

        payload = {"name": name}

        logger.info({"message": "Creating category"})
        return self._handle_request("POST", "/api/organizers/categories", json=payload)

    def get_category(self, category_id: str) -> Dict[str, Any]:
        """Get a specific category by ID.

        Args:
            category_id: The UUID of the category

        Returns:
            JSON response containing the category details
        """
        if not category_id:
            raise ValueError("Category ID cannot be empty")

        logger.info({"message": "Retrieving category"})
        return self._handle_request("GET", f"/api/organizers/categories/{category_id}")

    def get_category_by_slug(self, category_slug: str) -> Dict[str, Any]:
        """Get a specific category by its slug.

        Args:
            category_slug: The slug of the category

        Returns:
            JSON response containing the category details
        """
        if not category_slug:
            raise ValueError("Category slug cannot be empty")

        logger.info({"message": "Retrieving category by slug"})
        return self._handle_request("GET", f"/api/organizers/categories/slug/{category_slug}")

    def update_category(self, category_id: str, category_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a specific category.

        Args:
            category_id: The UUID of the category to update
            category_data: Dictionary containing the category properties to update

        Returns:
            JSON response containing the updated category
        """
        if not category_id:
            raise ValueError("Category ID cannot be empty")
        if not category_data:
            raise ValueError("Category data cannot be empty")

        logger.info({"message": "Updating category"})
        return self._handle_request("PUT", f"/api/organizers/categories/{category_id}", json=category_data)

    def delete_category(self, category_id: str) -> Dict[str, Any]:
        """Delete a specific category.

        Args:
            category_id: The UUID of the category to delete

        Returns:
            JSON response confirming deletion
        """
        if not category_id:
            raise ValueError("Category ID cannot be empty")

        logger.info({"message": "Deleting category"})
        return self._handle_request("DELETE", f"/api/organizers/categories/{category_id}")
