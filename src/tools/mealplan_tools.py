import json
from typing import Any, Dict, List, Optional

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from mealie import MealieFetcher
from mealie.client import MealieApiError
from models.mealplan import MealPlanEntry
from tools.errors import tool_error_boundary


def register_mealplan_tools(mcp: FastMCP, mealie: MealieFetcher) -> None:
    """Register all mealplan-related tools with the MCP server."""

    @mcp.tool()
    def get_all_mealplans(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get all meal plans for the current household with pagination.

        Args:
            start_date: Start date for filtering meal plans (ISO format YYYY-MM-DD)
            end_date: End date for filtering meal plans (ISO format YYYY-MM-DD)
            page: Page number to retrieve
            per_page: Number of items per page

        Returns:
            Dict[str, Any]: JSON response containing mealplan items and pagination information
        """
        with tool_error_boundary("Error fetching mealplans"):
            return mealie.get_mealplans(
                start_date=start_date,
                end_date=end_date,
                page=page,
                per_page=per_page,
            )

    @mcp.tool()
    def create_mealplan(
        date: str,
        recipe_id: Optional[str] = None,
        title: Optional[str] = None,
        entry_type: str = "breakfast",
        recipe_scale: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Create a new meal plan entry.

        Args:
            date: Date for the mealplan in ISO format (YYYY-MM-DD)
            recipe_id: UUID of the recipe to add to the mealplan (optional)
            title: Title for the mealplan entry if not using a recipe (optional)
            entry_type: Type of mealplan entry (breakfast, lunch, dinner, side)
            recipe_scale: Serving multiplier for the recipe, e.g. 2 to cook a
                double batch (optional; Mealie defaults to 1)

        Returns:
            Dict[str, Any]: JSON response containing the created mealplan entry
        """
        with tool_error_boundary("Error creating mealplan entry"):
            return mealie.create_mealplan(
                date=date,
                recipe_id=recipe_id,
                title=title,
                entry_type=entry_type,
                recipe_scale=recipe_scale,
            )

    @mcp.tool()
    def create_mealplan_bulk(
        entries: List[MealPlanEntry],
    ) -> Dict[str, Any]:
        """Create multiple meal plan entries after validating the entire batch.

        Writes are sequential, not atomic. A failure reports completed entries
        using zero-based indexes and returned IDs; do not retry those entries.

        Args:
            entries: List of mealplan entries, each containing:
                - date (str): Date in ISO format (YYYY-MM-DD)
                - recipe_id (str, optional): UUID of the recipe
                - title (str, optional): Title for the entry
                - entry_type (str, optional): Type of entry (breakfast, lunch, dinner, side)
                - recipe_scale (float, optional): Serving multiplier for the recipe

        Returns:
            Dict[str, Any]: JSON response with success message
        """
        with tool_error_boundary("Error creating bulk mealplan entries"):
            validated = [MealPlanEntry.model_validate(entry) for entry in entries]
            completed = []
            for index, entry in enumerate(validated):
                try:
                    result = mealie.create_mealplan(**entry.model_dump())
                except (MealieApiError, httpx.HTTPError, TimeoutError, ConnectionError):
                    progress = {"completed": completed, "failed_index": index}
                    raise ToolError(
                        "Error creating bulk mealplan entries; "
                        "completed entries must not be retried. Check the failed "
                        "entry before retrying; its remote outcome may be unknown. Progress: "
                        + json.dumps(progress)
                    ) from None
                completed.append({"index": index, "id": result.get("id")})
            return {"message": f"Successfully created {len(entries)} mealplan entries"}

    @mcp.tool()
    def update_mealplan(
        entry_id: int | str,
        date: Optional[str] = None,
        recipe_id: Optional[str] = None,
        title: Optional[str] = None,
        entry_type: Optional[str] = None,
        recipe_scale: Optional[float] = None,
        clear_recipe: bool = False,
    ) -> Dict[str, Any]:
        """Update selected fields; clear_recipe removes the linked recipe.

        Omitted or null arguments leave fields unchanged. clear_recipe cannot
        be combined with a replacement recipe_id. recipe_scale is the serving
        multiplier for the recipe, e.g. 2 for a double batch.
        """
        with tool_error_boundary("Error updating mealplan entry"):
            if clear_recipe and recipe_id is not None:
                raise ValueError("Cannot clear and replace a recipe in one update")
            entry_data = {}
            if date is not None:
                entry_data["date"] = date
            if recipe_id is not None:
                entry_data["recipeId"] = recipe_id
            if clear_recipe:
                entry_data["recipeId"] = None
            if title is not None:
                entry_data["title"] = title
            if entry_type is not None:
                entry_data["entryType"] = entry_type
            if recipe_scale is not None:
                entry_data["recipeScale"] = recipe_scale
            if not entry_data:
                raise ValueError("At least one field must be provided to update")
            return mealie.update_mealplan(entry_id, entry_data)

    @mcp.tool()
    def delete_mealplan(item_id: int | str) -> Dict[str, Any]:
        """Delete a specific meal plan entry.

        Args:
            item_id: The ID of the mealplan entry to delete

        Returns:
            Dict[str, Any]: Confirmation of deletion
        """
        with tool_error_boundary("Error deleting mealplan entry"):
            return mealie.delete_mealplan(item_id)

    @mcp.tool()
    def get_mealplan_ical_feed() -> Dict[str, Any]:
        """Get the household's meal plan calendar (iCal) subscription URL.

        The URL needs no login: anyone who has it can read the household's
        meal plan, so share it only with the people it is meant for.

        Returns:
            Dict[str, Any]: {"enabled": bool, "feedUrl": str or null}.
        """
        with tool_error_boundary("Error fetching mealplan iCal feed"):
            return mealie.get_mealplan_ical_feed()

    @mcp.tool()
    def set_mealplan_ical_feed(enabled: bool) -> Dict[str, Any]:
        """Turn the meal plan calendar (iCal) feed on or off (Mealie 3.29+).

        Turning it on issues a new URL that calendar apps (Google, Apple, Home
        Assistant, ...) can subscribe to without logging in, and any previous
        URL stops working. Only enable it, or re-enable it to rotate a leaked
        URL, when the user asks. Turning it off revokes the URL. Requires
        permission to manage the household.

        Args:
            enabled: True to issue a new feed URL, False to disable the feed.

        Returns:
            Dict[str, Any]: {"enabled": bool, "feedUrl": str or null}.
        """
        with tool_error_boundary("Error changing mealplan iCal feed"):
            return mealie.set_mealplan_ical_feed(enabled)

    @mcp.tool()
    def get_todays_mealplan() -> List[Dict[str, Any]]:
        """Get the mealplan entries for today.

        Returns:
            List[Dict[str, Any]]: List of today's mealplan entries
        """
        with tool_error_boundary("Error fetching today's mealplan"):
            return mealie.get_todays_mealplan()
