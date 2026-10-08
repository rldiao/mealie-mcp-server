import logging
from typing import Any, Dict, Optional

from utils import format_api_params

logger = logging.getLogger("mealie-mcp")


class LabelsMixin:
    """Mixin class for multi-purpose label-related API endpoints (/api/groups/labels)."""

    def get_labels(
        self,
        search: Optional[str] = None,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get all group labels.

        Args:
            search: Search term to filter labels by name
            page: Page number to retrieve
            per_page: Number of items per page

        Returns:
            JSON response containing label items and pagination information
        """
        param_dict = {
            "search": search,
            "page": page,
            "perPage": per_page,
        }
        params = format_api_params(param_dict)

        logger.info({"message": "Retrieving labels"})
        return self._handle_request("GET", "/api/groups/labels", params=params)

    def create_label(self, name: str, color: Optional[str] = None) -> Dict[str, Any]:
        """Create a new group label.

        Args:
            name: Name of the label
            color: Optional hex color for the label (e.g. "#959595")

        Returns:
            JSON response containing the created label
        """
        if not name:
            raise ValueError("Label name cannot be empty")

        payload: Dict[str, Any] = {"name": name}
        if color is not None:
            payload["color"] = color

        logger.info({"message": "Creating label"})
        return self._handle_request("POST", "/api/groups/labels", json=payload)

    def get_label(self, label_id: str) -> Dict[str, Any]:
        """Get a specific label by ID.

        Args:
            label_id: The UUID of the label

        Returns:
            JSON response containing the label details
        """
        if not label_id:
            raise ValueError("Label ID cannot be empty")

        logger.info({"message": "Retrieving label"})
        return self._handle_request("GET", f"/api/groups/labels/{label_id}")

    def update_label(self, label_id: str, label_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a specific label.

        Args:
            label_id: The UUID of the label to update
            label_data: Dictionary containing the label properties to update

        Returns:
            JSON response containing the updated label
        """
        if not label_id:
            raise ValueError("Label ID cannot be empty")
        if not label_data:
            raise ValueError("Label data cannot be empty")

        logger.info({"message": "Updating label"})
        return self._handle_request(
            "PUT", f"/api/groups/labels/{label_id}", json=label_data
        )

    def delete_label(self, label_id: str) -> Dict[str, Any]:
        """Delete a specific label.

        Args:
            label_id: The UUID of the label to delete

        Returns:
            JSON response confirming deletion
        """
        if not label_id:
            raise ValueError("Label ID cannot be empty")

        logger.info({"message": "Deleting label"})
        return self._handle_request("DELETE", f"/api/groups/labels/{label_id}")
