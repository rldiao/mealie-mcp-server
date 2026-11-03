import logging
from typing import Any, Dict, List, Optional

from pydantic import TypeAdapter

from models.mealplan import (
    EntryType,
    ISODate,
    MealPlanDateRange,
    MealPlanEntry,
    MealPlanUpdate,
)
from utils import format_api_params

logger = logging.getLogger("mealie-mcp")


MEALPLAN_ICAL = "/api/households/mealplans/ical"
MEALPLAN_RULES = "/api/households/mealplans/rules"
RULE_FIELDS = ("day", "entryType", "queryFilterString")


class MealplanMixin:
    """Mixin class for mealplan-related API endpoints"""

    def _ical_feed(self, response: Dict[str, Any]) -> Dict[str, Any]:
        token = response.get("mealplanIcalToken") if isinstance(response, dict) else None
        return {
            "enabled": bool(token),
            "feedUrl": f"{self.base_url}{MEALPLAN_ICAL}/{token}" if token else None,
        }

    def create_random_mealplan(self, date: str, entry_type: str = "dinner") -> Dict[str, Any]:
        """Let Mealie pick a recipe for a date, honouring the household's rules.

        Returns:
            The created meal plan entry, including the chosen recipe
        """
        payload = {
            "date": TypeAdapter(ISODate).validate_python(date),
            "entryType": TypeAdapter(EntryType).validate_python(entry_type),
        }
        logger.info({"message": "Creating random mealplan entry"})
        return self._handle_request(
            "POST", "/api/households/mealplans/random", json=payload
        )

    def get_mealplan_rules(
        self, page: Optional[int] = None, per_page: Optional[int] = None
    ) -> Dict[str, Any]:
        """List the household's meal plan rules."""
        params = format_api_params({"page": page, "perPage": per_page})
        logger.info({"message": "Retrieving mealplan rules"})
        return self._handle_request("GET", MEALPLAN_RULES, params=params)

    def create_mealplan_rule(self, rule: Dict[str, Any]) -> Dict[str, Any]:
        """Create a rule from Mealie-cased fields (day, entryType, queryFilterString)."""
        logger.info({"message": "Creating mealplan rule"})
        return self._handle_request("POST", MEALPLAN_RULES, json=rule)

    def update_mealplan_rule(self, rule_id: str, changes: Dict[str, Any]) -> Dict[str, Any]:
        """Change some fields of a rule, keeping the rest."""
        if not rule_id or not rule_id.strip():
            raise ValueError("Rule ID cannot be empty")
        if not changes:
            raise ValueError("At least one field must be provided to update")
        current = self._handle_request("GET", f"{MEALPLAN_RULES}/{rule_id}")
        merged = {key: current.get(key) for key in RULE_FIELDS if key in current}
        merged.update(changes)
        logger.info({"message": "Updating mealplan rule"})
        return self._handle_request("PUT", f"{MEALPLAN_RULES}/{rule_id}", json=merged)

    def delete_mealplan_rule(self, rule_id: str) -> Dict[str, Any]:
        """Delete a meal plan rule."""
        if not rule_id or not rule_id.strip():
            raise ValueError("Rule ID cannot be empty")
        logger.info({"message": "Deleting mealplan rule"})
        return self._handle_request("DELETE", f"{MEALPLAN_RULES}/{rule_id}")

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
        include_week_entries: Optional[bool] = None,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get all mealplans for the current household with pagination.

        Args:
            start_date: Start date for filtering meal plans (ISO format YYYY-MM-DD)
            end_date: End date for filtering meal plans (ISO format YYYY-MM-DD)
            include_week_entries: Also return entries that span a week
                (Mealie 3.30+); Mealie leaves them out by default
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
            "include_week_entries": include_week_entries,
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
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new mealplan entry.

        Args:
            date: Date for the mealplan in ISO format (YYYY-MM-DD)
            recipe_id: UUID of the recipe to add to the mealplan (optional)
            title: Title for the mealplan entry if not using a recipe (optional)
            entry_type: Meal type (breakfast, lunch, dinner, side, snack, drink, dessert)
            recipe_scale: Serving multiplier for the recipe (Mealie defaults to 1)
            end_date: Last day of a multi-day or week-long entry (Mealie 3.30+)

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
            end_date=end_date,
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
        if entry.end_date:
            payload["endDate"] = entry.end_date

        logger.info({"message": "Creating mealplan entry"})
        return self._handle_request("POST", "/api/households/mealplans", json=payload)

    def update_mealplan(
        self, entry_id: int | str, entry_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an entry while preserving fields required by Mealie's PUT."""
        entry_id = "" if entry_id is None else str(entry_id).strip()
        if not entry_id:
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
            end_date=merged_data.get("endDate"),
        )
        return self._handle_request(
            "PUT", f"/api/households/mealplans/{entry_id}", json=merged_data
        )

    def delete_mealplan(self, item_id: int | str) -> Dict[str, Any]:
        """Delete a specific mealplan entry.

        Args:
            item_id: The ID of the mealplan entry to delete

        Returns:
            JSON response confirming deletion

        Raises:
            ValueError: If item_id is empty
            MealieApiError: If the API request fails
        """
        item_id = "" if item_id is None else str(item_id).strip()
        if not item_id:
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
