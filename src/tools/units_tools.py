import logging
import traceback
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from mealie import MealieFetcher

logger = logging.getLogger("mealie-mcp")


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
        try:
            logger.info(
                {"message": "Fetching units", "search": search, "per_page": per_page}
            )
            return mealie.get_units(search=search, page=page, per_page=per_page)
        except Exception as e:
            error_msg = f"Error fetching units: {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise ToolError(error_msg)

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
        try:
            logger.info({"message": "Creating unit", "name": name})
            return mealie.create_unit(
                name,
                abbreviation=abbreviation,
                plural_name=plural_name,
                description=description,
            )
        except Exception as e:
            error_msg = f"Error creating unit '{name}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise ToolError(error_msg)

    @mcp.tool()
    def get_unit(unit_id: str) -> Dict[str, Any]:
        """Get a specific unit by ID.

        Args:
            unit_id: The UUID of the unit.

        Returns:
            Dict[str, Any]: The unit details.
        """
        try:
            logger.info({"message": "Fetching unit", "unit_id": unit_id})
            return mealie.get_unit(unit_id)
        except Exception as e:
            error_msg = f"Error fetching unit '{unit_id}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise ToolError(error_msg)

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
        try:
            logger.info({"message": "Updating unit", "unit_id": unit_id})

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
        except Exception as e:
            error_msg = f"Error updating unit '{unit_id}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise ToolError(error_msg)

    @mcp.tool()
    def delete_unit(unit_id: str) -> Dict[str, Any]:
        """Delete a specific unit.

        Args:
            unit_id: The UUID of the unit to delete.

        Returns:
            Dict[str, Any]: Confirmation of deletion.
        """
        try:
            logger.info({"message": "Deleting unit", "unit_id": unit_id})
            return mealie.delete_unit(unit_id)
        except Exception as e:
            error_msg = f"Error deleting unit '{unit_id}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise ToolError(error_msg)
