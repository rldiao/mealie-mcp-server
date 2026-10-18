import logging
from typing import Any, Dict, List, Optional

from models.mealplan import MealPlanDateRange, MealPlanEntry, MealPlanUpdate
from utils import format_api_params

logger = logging.getLogger("mealie-mcp")


MEALPLAN_ICAL = "/api/households/mealplans/ical"


class MealplanMixin:
    """Mixin class for mealplan-related API endpoints"""

    def _ical_feed(self, response: Dict[str, Any]) -> Dict[str, Any]:
        token = response.get("mealplanIcalToken") if isinstance(response, dict) else None
        return {
            "enabled": bool(token),
            "feedUrl": f"{self.base_url}{MEALPLAN_ICAL}/{token}" if token else None,
        }

    def get_mealplan_ical_feed(self) -> Dict[str, Any]:
        """Get the household's meal plan iCal subscription URL, if enabled.

        Returns:
            {"enabled": bool, "feedUrl": str | None}
        """
        logger.info({"message": "Retrieving mealplan iCal feed"})
        return self._ical_feed(self._handle_request("GET", MEALPLAN_ICAL))

    def set_mealplan_ical_feed(self, enabled: bool) -> Dict[str, Any]:
        """Enable the feed with a new token, or disable it.

        Enabling always issues a new token, so any previous feed URL stops
        working.

        Returns:
            {"enabled": bool, "feedUrl": str | None}
        """
        method = "POST" if enabled else "DELETE"
        logger.info({"message": "Changing mealplan iCal feed", "enabled": enabled})
        return self._ical_feed(self._handle_request(method, MEALPLAN_ICAL))

    def get_mealplans(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get all mealplans for the current household with pagination.

        Args:
            start_date: Start date for filtering meal plans (ISO format YYYY-MM-DD)
            end_date: End date for filtering meal plans (ISO format YYYY-MM-DD)
            page: Page number to retrieve
            per_page: Number of items per page

        Returns:
            JSON response containing mealplan items and pagination information

        Raises:
            MealieApiError: If the API request fails
        """
        dates = MealPlanDateRange(start_date=start_date, end_date=end_date)
        param_dict = {
            "start_date": dates.start_date,
            "end_date": dates.end_date,
            "page": page,
            "perPage": per_page,
        }

        params = format_api_params(param_dict)

        logger.info({"message": "Retrieving mealplans"})
        response = self._handle_request(
            "GET", "/api/households/mealplans", params=params
        )
        return response

    def create_mealplan(
        self,
        date: str,
        recipe_id: Optional[str] = None,
        title: Optional[str] = None,
        entry_type: str = "breakfast",
        recipe_scale: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Create a new mealplan entry.

        Args:
            date: Date for the mealplan in ISO format (YYYY-MM-DD)
            recipe_id: UUID of the recipe to add to the mealplan (optional)
            title: Title for the mealplan entry if not using a recipe (optional)
            entry_type: Type of mealplan entry (breakfast, lunch, dinner, etc.)
            recipe_scale: Serving multiplier for the recipe (Mealie defaults to 1)

        Returns:
            JSON response containing the created mealplan entry

        Raises:
            ValueError: If neither recipe_id nor title is provided
            MealieApiError: If the API request fails
        """
        entry = MealPlanEntry(
            date=date,
            recipe_id=recipe_id,
            title=title,
            entry_type=entry_type,
            recipe_scale=recipe_scale,
        )

        # Build the request payload
        payload = {
            "date": entry.date,
            "entryType": entry.entry_type,
        }

        if entry.recipe_id:
            payload["recipeId"] = entry.recipe_id
        if entry.title:
            payload["title"] = entry.title
        if entry.recipe_scale is not None:
            payload["recipeScale"] = entry.recipe_scale

        logger.info({"message": "Creating mealplan entry"})
        return self._handle_request("POST", "/api/households/mealplans", json=payload)

    def update_mealplan(
        self, entry_id: str, entry_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an entry while preserving fields required by Mealie's PUT."""
        if not entry_id or not entry_id.strip():
            raise ValueError("Mealplan entry ID cannot be empty")
        patch = MealPlanUpdate.model_validate(entry_data).model_dump(
            by_alias=True, exclude_unset=True
        )

        logger.info({"message": "Updating mealplan entry"})
        current_entry = self._handle_request(
            "GET", f"/api/households/mealplans/{entry_id}"
        )
        merged_data = {**current_entry, **patch}
        MealPlanEntry(
            date=merged_data.get("date"),
            recipe_id=merged_data.get("recipeId"),
            title=merged_data.get("title"),
            entry_type=merged_data.get("entryType", "breakfast"),
        )
        return self._handle_request(
            "PUT", f"/api/households/mealplans/{entry_id}", json=merged_data
        )

    def delete_mealplan(self, item_id: str) -> Dict[str, Any]:
        """Delete a specific mealplan entry.

        Args:
            item_id: The ID of the mealplan entry to delete

        Returns:
            JSON response confirming deletion

        Raises:
            ValueError: If item_id is empty
            MealieApiError: If the API request fails
        """
        if not item_id or not item_id.strip():
            raise ValueError("Mealplan entry ID cannot be empty")

        logger.info({"message": "Deleting mealplan entry"})
        return self._handle_request("DELETE", f"/api/households/mealplans/{item_id}")

    def get_todays_mealplan(self) -> List[Dict[str, Any]]:
        """Get the mealplan entries for today.

        Returns:
            List of today's mealplan entries

        Raises:
            MealieApiError: If the API request fails
        """
        logger.info({"message": "Retrieving today's mealplan"})
        return self._handle_request("GET", "/api/households/mealplans/today")
