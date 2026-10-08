from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

from mealie import MealieFetcher
from tools.errors import tool_error_boundary


def register_units_tools(mcp: FastMCP, mealie: MealieFetcher) -> None:
    """Register all unit-related tools with the MCP server."""

    @mcp.tool()
    def get_units(
        search: Optional[str] = None,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
    ) -> Dict[str, Any]:
        """List the household's units, optionally filtered by a search term.

        Use this to resolve an existing Mealie unit id+name before building a
        structured ingredient.

        Args:
            search: Search term to filter units by name/abbreviation.
            page: Page number to retrieve.
            per_page: Number of items per page.

        Returns:
            Dict[str, Any]: Units (under "items") with pagination information.
        """
        with tool_error_boundary("Error fetching units"):
            return mealie.get_units(search=search, page=page, per_page=per_page)

    @mcp.tool()
    def create_unit(
        name: str,
        abbreviation: Optional[str] = None,
        plural_name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new unit.

        Args:
            name: Name of the unit (e.g. "Gramm").
            abbreviation: Optional short form (e.g. "g", "ml").
            plural_name: Optional plural name.
            description: Optional description.

        Returns:
            Dict[str, Any]: The created unit.
        """
        with tool_error_boundary("Error creating unit"):
            return mealie.create_unit(
                name,
                abbreviation=abbreviation,
                plural_name=plural_name,
                description=description,
            )

    @mcp.tool()
    def get_unit(unit_id: str) -> Dict[str, Any]:
        """Get a specific unit by ID.

        Args:
            unit_id: The UUID of the unit.

        Returns:
            Dict[str, Any]: The unit details.
        """
        with tool_error_boundary("Error fetching unit"):
            return mealie.get_unit(unit_id)

    @mcp.tool()
    def update_unit(
        unit_id: str,
        name: Optional[str] = None,
        abbreviation: Optional[str] = None,
        plural_name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a unit's details (only provided fields are changed).

        Args:
            unit_id: The UUID of the unit to update.
            name: New name for the unit.
            abbreviation: New abbreviation.
            plural_name: New plural name.
            description: New description.

        Returns:
            Dict[str, Any]: The updated unit.
        """
        with tool_error_boundary("Error updating unit"):
            unit_data: Dict[str, Any] = {}
            if name is not None:
                unit_data["name"] = name
            if abbreviation is not None:
                unit_data["abbreviation"] = abbreviation
            if plural_name is not None:
                unit_data["pluralName"] = plural_name
            if description is not None:
                unit_data["description"] = description

            if not unit_data:
                raise ValueError("At least one field must be provided to update")

            return mealie.update_unit(unit_id, unit_data)

    @mcp.tool()
    def delete_unit(unit_id: str) -> Dict[str, Any]:
        """Delete a specific unit.

        Args:
            unit_id: The UUID of the unit to delete.

        Returns:
            Dict[str, Any]: Confirmation of deletion.
        """
        with tool_error_boundary("Error deleting unit"):
            return mealie.delete_unit(unit_id)
