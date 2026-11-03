import logging
from typing import Any, Dict, Optional

from utils import format_api_params

logger = logging.getLogger("mealie-mcp")

COOKBOOKS = "/api/households/cookbooks"
# Fields Mealie's cookbook PUT accepts; it replaces the whole record.
COOKBOOK_FIELDS = ("name", "description", "slug", "position", "public", "queryFilterString")


class CookbooksMixin:
    """Mixin class for household cookbook endpoints"""

    def get_cookbooks(
        self, page: Optional[int] = None, per_page: Optional[int] = None
    ) -> Dict[str, Any]:
        """List the household's cookbooks (saved recipe filters).

        Returns:
            JSON response containing cookbook items and pagination information
        """
        params = format_api_params({"page": page, "perPage": per_page})
        logger.info({"message": "Retrieving cookbooks"})
        return self._handle_request("GET", COOKBOOKS, params=params)

    def get_cookbook(self, cookbook_id: str) -> Dict[str, Any]:
        """Get a cookbook by ID or slug."""
        if not cookbook_id or not cookbook_id.strip():
            raise ValueError("Cookbook ID cannot be empty")
        logger.info({"message": "Retrieving cookbook"})
        return self._handle_request("GET", f"{COOKBOOKS}/{cookbook_id}")

    def create_cookbook(self, cookbook: Dict[str, Any]) -> Dict[str, Any]:
        """Create a cookbook from Mealie-cased fields (name is required)."""
        if not (cookbook.get("name") or "").strip():
            raise ValueError("Cookbook name cannot be empty")
        logger.info({"message": "Creating cookbook"})
        return self._handle_request("POST", COOKBOOKS, json=cookbook)

    def update_cookbook(self, cookbook_id: str, changes: Dict[str, Any]) -> Dict[str, Any]:
        """Change some fields of a cookbook, keeping the rest."""
        if not changes:
            raise ValueError("At least one field must be provided to update")
        if "name" in changes and not (changes["name"] or "").strip():
            raise ValueError("Cookbook name cannot be empty")
        current = self.get_cookbook(cookbook_id)
        merged = {key: current.get(key) for key in COOKBOOK_FIELDS if key in current}
        merged.update(changes)
        logger.info({"message": "Updating cookbook"})
        return self._handle_request("PUT", f"{COOKBOOKS}/{current['id']}", json=merged)

    def delete_cookbook(self, cookbook_id: str) -> Dict[str, Any]:
        """Delete a cookbook by ID. Recipes are not affected."""
        if not cookbook_id or not cookbook_id.strip():
            raise ValueError("Cookbook ID cannot be empty")
        logger.info({"message": "Deleting cookbook"})
        return self._handle_request("DELETE", f"{COOKBOOKS}/{cookbook_id}")
