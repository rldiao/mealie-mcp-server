import logging
from typing import Any, Dict, Optional

from utils import format_api_params

logger = logging.getLogger("mealie-mcp")


class UnitsMixin:
    """Mixin class for unit-related API endpoints (/api/units)."""

    def get_units(
        self,
        search: Optional[str] = None,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        query_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List the household's units (optionally filtered by search term).

        Args:
            search: Search term to filter units by name/abbreviation
            page: Page number to retrieve
            per_page: Number of items per page
            query_filter: Advanced query filter

        Returns:
            JSON response containing unit items and pagination information
        """
        param_dict = {
            "search": search,
            "page": page,
            "perPage": per_page,
            "queryFilter": query_filter,
        }
        params = format_api_params(param_dict)

        logger.info({"message": "Retrieving units", "parameters": params})
        return self._handle_request("GET", "/api/units", params=params)

    def create_unit(
        self,
        name: str,
        abbreviation: Optional[str] = None,
        plural_name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new unit.

        Args:
            name: Name of the unit
            abbreviation: Optional short form (e.g. "g", "ml")
            plural_name: Optional plural name
            description: Optional description

        Returns:
            JSON response containing the created unit
        """
        if not name:
            raise ValueError("Unit name cannot be empty")

        payload: Dict[str, Any] = {"name": name}
        if abbreviation is not None:
            payload["abbreviation"] = abbreviation
        if plural_name is not None:
            payload["pluralName"] = plural_name
        if description is not None:
            payload["description"] = description

        logger.info({"message": "Creating unit", "name": name})
        return self._handle_request("POST", "/api/units", json=payload)

    def get_unit(self, unit_id: str) -> Dict[str, Any]:
        """Get a specific unit by ID.

        Args:
            unit_id: The UUID of the unit

        Returns:
            JSON response containing the unit details
        """
        if not unit_id:
            raise ValueError("Unit ID cannot be empty")

        logger.info({"message": "Retrieving unit", "unit_id": unit_id})
        return self._handle_request("GET", f"/api/units/{unit_id}")

    def update_unit(self, unit_id: str, unit_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a specific unit.

        Mealie's PUT replaces the whole record, so we fetch the existing unit
        and merge the provided fields over it (preserving unset fields and
        keeping the required ``id``/``name`` in the body).

        Args:
            unit_id: The UUID of the unit to update
            unit_data: Dictionary containing the unit properties to update

        Returns:
            JSON response containing the updated unit
        """
        if not unit_id:
            raise ValueError("Unit ID cannot be empty")
        if not unit_data:
            raise ValueError("Unit data cannot be empty")

        existing = self.get_unit(unit_id)
        merged = {**existing, **unit_data} if isinstance(existing, dict) else unit_data

        logger.info({"message": "Updating unit", "unit_id": unit_id})
        return self._handle_request("PUT", f"/api/units/{unit_id}", json=merged)

    def delete_unit(self, unit_id: str) -> Dict[str, Any]:
        """Delete a specific unit.

        Args:
            unit_id: The UUID of the unit to delete

        Returns:
            JSON response confirming deletion
        """
        if not unit_id:
            raise ValueError("Unit ID cannot be empty")

        logger.info({"message": "Deleting unit", "unit_id": unit_id})
        return self._handle_request("DELETE", f"/api/units/{unit_id}")
