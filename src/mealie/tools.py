import logging
from typing import Any, Dict, Optional

from utils import format_api_params

from .updates import merge_replacement_record

logger = logging.getLogger("mealie-mcp")


class ToolsMixin:
    """Mixin class for recipe-tool API endpoints (/api/organizers/tools)."""

    def get_tools(
        self,
        search: Optional[str] = None,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        query_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List the household's recipe tools (optionally filtered by search term).

        Each tool includes ``householdsWithTool``, a list of household IDs.
        Ownership requires membership of the relevant household ID in that list.

        Args:
            search: Search term to filter tools by name
            page: Page number to retrieve
            per_page: Number of items per page
            query_filter: Advanced query filter

        Returns:
            JSON response containing tool items and pagination information
        """
        param_dict = {
            "search": search,
            "page": page,
            "perPage": per_page,
            "queryFilter": query_filter,
        }
        params = format_api_params(param_dict)

        logger.info({"message": "Retrieving tools"})
        return self._handle_request("GET", "/api/organizers/tools", params=params)

    def create_tool(self, name: str) -> Dict[str, Any]:
        """Create a new recipe tool.

        Args:
            name: Name of the tool (e.g. "Kochtopf", "Backofen")

        Returns:
            JSON response containing the created tool
        """
        if not name:
            raise ValueError("Tool name cannot be empty")

        payload = {"name": name}

        logger.info({"message": "Creating tool"})
        return self._handle_request("POST", "/api/organizers/tools", json=payload)

    def get_tool(self, tool_id: str) -> Dict[str, Any]:
        """Get a specific tool by ID.

        Args:
            tool_id: The UUID of the tool

        Returns:
            JSON response containing the tool details
        """
        if not tool_id:
            raise ValueError("Tool ID cannot be empty")

        logger.info({"message": "Retrieving tool"})
        return self._handle_request("GET", f"/api/organizers/tools/{tool_id}")

    def get_tool_by_slug(self, tool_slug: str) -> Dict[str, Any]:
        """Get a specific tool by its slug.

        Args:
            tool_slug: The slug of the tool

        Returns:
            JSON response containing the tool details
        """
        if not tool_slug:
            raise ValueError("Tool slug cannot be empty")

        logger.info({"message": "Retrieving tool by slug"})
        return self._handle_request("GET", f"/api/organizers/tools/slug/{tool_slug}")

    def update_tool(self, tool_id: str, tool_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a specific tool.

        Mealie's PUT replaces the whole record, so we fetch the existing tool
        and merge the provided fields over it, preserving household ownership
        and the required ``name``. An invalid or incomplete read is rejected
        before issuing the PUT.

        Args:
            tool_id: The UUID of the tool to update
            tool_data: Dictionary containing the tool properties to update

        Returns:
            JSON response containing the updated tool
        """
        if not tool_id:
            raise ValueError("Tool ID cannot be empty")
        if not tool_data:
            raise ValueError("Tool data cannot be empty")

        existing = self.get_tool(tool_id)
        merged = merge_replacement_record(
            existing, tool_data, required_fields=("id", "name", "slug")
        )

        logger.info({"message": "Updating tool"})
        return self._handle_request(
            "PUT", f"/api/organizers/tools/{tool_id}", json=merged
        )

    def delete_tool(self, tool_id: str) -> Dict[str, Any]:
        """Delete a specific tool.

        Args:
            tool_id: The UUID of the tool to delete

        Returns:
            JSON response confirming deletion
        """
        if not tool_id:
            raise ValueError("Tool ID cannot be empty")

        logger.info({"message": "Deleting tool"})
        return self._handle_request("DELETE", f"/api/organizers/tools/{tool_id}")
