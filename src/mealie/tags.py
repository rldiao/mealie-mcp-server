import logging
from typing import Any, Dict, List, Optional

from utils import format_api_params

logger = logging.getLogger("mealie-mcp")


class TagsMixin:
    """Mixin class for recipe tag-related API endpoints"""

    def get_tags(
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
        """Get all recipe tags.

        Args:
            page: Page number to retrieve
            per_page: Number of items per page
            order_by: Field to order results by
            order_direction: Direction to order results ('asc' or 'desc')
            search: Search term to filter tags
            query_filter: Advanced query filter
            order_by_null_position: How to handle nulls in ordering ('first' or 'last')
            pagination_seed: Seed for consistent pagination

        Returns:
            JSON response containing tag items and pagination information
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

        logger.info({"message": "Retrieving tags"})
        return self._handle_request("GET", "/api/organizers/tags", params=params)

    def get_empty_tags(self) -> List[Dict[str, Any]]:
        """Get all tags that have no recipes assigned.

        Returns:
            List of empty tags
        """
        logger.info({"message": "Retrieving empty tags"})
        return self._handle_request("GET", "/api/organizers/tags/empty")

    def create_tag(self, name: str) -> Dict[str, Any]:
        """Create a new recipe tag.

        Args:
            name: Name of the tag

        Returns:
            JSON response containing the created tag
        """
        if not name:
            raise ValueError("Tag name cannot be empty")

        payload = {"name": name}

        logger.info({"message": "Creating tag"})
        return self._handle_request("POST", "/api/organizers/tags", json=payload)

    def get_tag(self, tag_id: str) -> Dict[str, Any]:
        """Get a specific tag by ID.

        Args:
            tag_id: The UUID of the tag

        Returns:
            JSON response containing the tag details
        """
        if not tag_id:
            raise ValueError("Tag ID cannot be empty")

        logger.info({"message": "Retrieving tag"})
        return self._handle_request("GET", f"/api/organizers/tags/{tag_id}")

    def get_tag_by_slug(self, tag_slug: str) -> Dict[str, Any]:
        """Get a specific tag by its slug.

        Args:
            tag_slug: The slug of the tag

        Returns:
            JSON response containing the tag details
        """
        if not tag_slug:
            raise ValueError("Tag slug cannot be empty")

        logger.info({"message": "Retrieving tag by slug"})
        return self._handle_request("GET", f"/api/organizers/tags/slug/{tag_slug}")

    def update_tag(self, tag_id: str, tag_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a specific tag.

        Args:
            tag_id: The UUID of the tag to update
            tag_data: Dictionary containing the tag properties to update

        Returns:
            JSON response containing the updated tag
        """
        if not tag_id:
            raise ValueError("Tag ID cannot be empty")
        if not tag_data:
            raise ValueError("Tag data cannot be empty")

        logger.info({"message": "Updating tag"})
        return self._handle_request("PUT", f"/api/organizers/tags/{tag_id}", json=tag_data)

    def delete_tag(self, tag_id: str) -> Dict[str, Any]:
        """Delete a specific tag.

        Args:
            tag_id: The UUID of the tag to delete

        Returns:
            JSON response confirming deletion
        """
        if not tag_id:
            raise ValueError("Tag ID cannot be empty")

        logger.info({"message": "Deleting tag"})
        return self._handle_request("DELETE", f"/api/organizers/tags/{tag_id}")
