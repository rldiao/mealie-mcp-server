import logging
from typing import Any, Dict, List, Optional

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

        Each tool includes ``householdsWithTool``, a list of household slugs.
        Ownership requires membership of the relevant household slug in that list.

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

    def get_empty_tools(self) -> List[Dict[str, Any]]:
        """Get all tools that no recipe uses.

        Returns:
            List of unused tools
        """
        logger.info({"message": "Retrieving empty tools"})
        return self._handle_request("GET", "/api/organizers/tools/empty")

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

    def set_tool_on_hand(self, tool_id: str, on_hand: bool = True) -> Dict[str, Any]:
        """Mark or unmark a tool as owned (on hand) by the current household.

        Mealie tracks ownership per household via the ``householdsWithTool``
        list on the tool record rather than a single global boolean, so this
        fetches the current household slug, then fetch-merges the tool
        (Mealie's PUT replaces the whole record).

        Args:
            tool_id: The UUID of the tool
            on_hand: True to mark owned by the current household, False to clear it

        Returns:
            JSON response containing the updated tool
        """
        if not tool_id:
            raise ValueError("Tool ID cannot be empty")

        existing = self.get_tool(tool_id)
        household_slug = self._current_household_slug()

        logger.info({"message": "Setting tool on-hand status"})
        return self._put_tool_households(existing, household_slug, on_hand)

    def set_tools_on_hand_by_name(
        self, names: List[str], on_hand: bool = True
    ) -> Dict[str, Any]:
        """Mark or unmark tools as owned by name, creating missing tools.

        Names are matched case-insensitively against existing tools; a name
        with no match is created as a new tool before being marked owned.

        Args:
            names: Tool names to update (created in Mealie if they don't exist)
            on_hand: True to mark owned by the current household, False to clear it

        Returns:
            Dict with "updated" (the updated tool records) and "created"
            (names of tools that had to be created)
        """
        if not names:
            raise ValueError("Tool names cannot be empty")

        logger.info({"message": "Marking tools on-hand"})

        household_slug = self._current_household_slug()
        updated = []
        created = []

        for raw_name in names:
            name = raw_name.strip()
            if not name:
                continue

            matches = self.get_tools(search=name).get("items", [])
            tool = next(
                (t for t in matches if (t.get("name") or "").lower() == name.lower()),
                None,
            )
            if tool is None:
                tool = self.create_tool(name)
                created.append(name)

            updated.append(self._put_tool_households(tool, household_slug, on_hand))

        return {"updated": updated, "created": created}

    def _put_tool_households(
        self, tool: Dict[str, Any], household_slug: str, on_hand: bool
    ) -> Dict[str, Any]:
        households = [h for h in tool.get("householdsWithTool") or [] if h != household_slug]
        if on_hand:
            households.append(household_slug)

        merged = {**tool, "householdsWithTool": households}
        return self._handle_request(
            "PUT", f"/api/organizers/tools/{tool['id']}", json=merged
        )
