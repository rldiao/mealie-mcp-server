from typing import Any, Dict

from mcp.server.fastmcp import FastMCP

from mealie import MealieFetcher
from mealie.organizers import OrganizerKind
from tools.errors import tool_error_boundary


def register_organizers_tools(mcp: FastMCP, mealie: MealieFetcher) -> None:
    """Register tools that work across every organizer type."""

    @mcp.tool()
    def merge_organizers(kind: OrganizerKind, from_id: str, to_id: str) -> Dict[str, Any]:
        """Merge a duplicate tag, category, tool, label, food, or unit into another.

        Every recipe (and, for foods and units, every shopping list item) that
        uses from_id is moved to to_id, then from_id is deleted. This cannot be
        undone. Look up both IDs first with the matching get_* tool, and use
        the get_empty_* tools to find organizers that no recipe uses.

        Args:
            kind: The organizer type both IDs belong to.
            from_id: ID of the duplicate to merge away; it is deleted.
            to_id: ID of the organizer to keep.

        Returns:
            Dict[str, Any]: The surviving organizer, or a success message for
            foods and units.
        """
        with tool_error_boundary("Error merging organizers"):
            return mealie.merge_organizers(kind, from_id, to_id)
