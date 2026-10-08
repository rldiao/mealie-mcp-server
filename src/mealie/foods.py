import logging
from typing import Any, Dict, List, Optional

from utils import format_api_params

from .updates import merge_replacement_record

logger = logging.getLogger("mealie-mcp")


class FoodsMixin:
    """Mixin class for food-related API endpoints (/api/foods)."""

    def get_foods(
        self,
        search: Optional[str] = None,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        query_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List the household's foods (optionally filtered by search term).

        Args:
            search: Search term to filter foods by name/alias
            page: Page number to retrieve
            per_page: Number of items per page
            query_filter: Advanced query filter

        Returns:
            JSON response containing food items and pagination information
        """
        param_dict = {
            "search": search,
            "page": page,
            "perPage": per_page,
            "queryFilter": query_filter,
        }
        params = format_api_params(param_dict)

        logger.info({"message": "Retrieving foods"})
        return self._handle_request("GET", "/api/foods", params=params)

    def create_food(
        self,
        name: str,
        plural_name: Optional[str] = None,
        description: Optional[str] = None,
        extras: Optional[Dict[str, Any]] = None,
        label_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new food.

        Args:
            name: Name of the food
            plural_name: Optional plural name
            description: Optional description
            extras: Optional arbitrary key-value metadata dict (Mealie ``extras``)
            label_id: Optional Multi Purpose Label UUID (aisle/section grouping)

        Returns:
            JSON response containing the created food
        """
        if not name:
            raise ValueError("Food name cannot be empty")

        payload: Dict[str, Any] = {"name": name}
        if plural_name is not None:
            payload["pluralName"] = plural_name
        if description is not None:
            payload["description"] = description
        if extras is not None:
            payload["extras"] = extras
        if label_id is not None:
            # "" clears the label; Mealie wants null, not an empty UUID string.
            payload["labelId"] = label_id or None

        logger.info({"message": "Creating food"})
        return self._handle_request("POST", "/api/foods", json=payload)

    def get_food(self, food_id: str) -> Dict[str, Any]:
        """Get a specific food by ID.

        Args:
            food_id: The UUID of the food

        Returns:
            JSON response containing the food details
        """
        if not food_id:
            raise ValueError("Food ID cannot be empty")

        logger.info({"message": "Retrieving food"})
        return self._handle_request("GET", f"/api/foods/{food_id}")

    def update_food(self, food_id: str, food_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a specific food.

        Mealie's PUT replaces the whole record, so we fetch the existing food
        and merge the provided fields over it. This both preserves fields the
        caller did not set and keeps the required ``name`` and existing ``id``.
        An invalid or incomplete read is rejected before issuing the PUT.

        Args:
            food_id: The UUID of the food to update
            food_data: Dictionary containing the food properties to update

        Returns:
            JSON response containing the updated food
        """
        if not food_id:
            raise ValueError("Food ID cannot be empty")
        if not food_data:
            raise ValueError("Food data cannot be empty")

        existing = self.get_food(food_id)
        merged = merge_replacement_record(existing, food_data)

        logger.info({"message": "Updating food"})
        return self._handle_request("PUT", f"/api/foods/{food_id}", json=merged)

    def delete_food(self, food_id: str) -> Dict[str, Any]:
        """Delete a specific food.

        Args:
            food_id: The UUID of the food to delete

        Returns:
            JSON response confirming deletion
        """
        if not food_id:
            raise ValueError("Food ID cannot be empty")

        logger.info({"message": "Deleting food"})
        return self._handle_request("DELETE", f"/api/foods/{food_id}")

    def set_food_on_hand(self, food_id: str, on_hand: bool = True) -> Dict[str, Any]:
        """Mark or unmark a food as on-hand for the current household.

        Mealie tracks on-hand status per household via the
        ``householdsWithIngredientFood`` list on the food record rather than
        a single global boolean, so this fetches the current household id,
        then fetch-merges the food (Mealie's PUT replaces the whole record).

        Args:
            food_id: The UUID of the food
            on_hand: True to mark on-hand for the current household, False to clear it

        Returns:
            JSON response containing the updated food
        """
        if not food_id:
            raise ValueError("Food ID cannot be empty")

        existing = self.get_food(food_id)
        household_id = self.get_current_user().get("householdId")
        households = list(existing.get("householdsWithIngredientFood", []))

        if on_hand:
            if household_id not in households:
                households.append(household_id)
        else:
            households = [h for h in households if h != household_id]

        merged = {**existing, "householdsWithIngredientFood": households}

        logger.info({"message": "Setting food on-hand status"})
        return self._handle_request("PUT", f"/api/foods/{food_id}", json=merged)

    def set_foods_on_hand_by_name(
        self, names: List[str], on_hand: bool = True
    ) -> Dict[str, Any]:
        """Mark or unmark foods as on-hand by name, creating missing foods.

        Names are matched case-insensitively against existing foods (the
        same approach ``add_recipe_tags`` uses for tag names); a name with
        no match is created as a new food before being marked on-hand.

        Args:
            names: Food names to update (created in Mealie if they don't exist)
            on_hand: True to mark on-hand for the current household, False to clear it

        Returns:
            Dict with "updated" (the updated food records) and "created"
            (names of foods that had to be created)
        """
        if not names:
            raise ValueError("Food names cannot be empty")

        logger.info({"message": "Marking foods on-hand"})

        household_id = self.get_current_user().get("householdId")
        updated = []
        created = []

        for raw_name in names:
            name = raw_name.strip()
            if not name:
                continue

            matches = self.get_foods(search=name).get("items", [])
            food = next(
                (f for f in matches if (f.get("name") or "").lower() == name.lower()),
                None,
            )
            if food is None:
                food = self.create_food(name)
                created.append(name)

            households = list(food.get("householdsWithIngredientFood", []))
            if on_hand:
                if household_id not in households:
                    households.append(household_id)
            else:
                households = [h for h in households if h != household_id]

            merged = {**food, "householdsWithIngredientFood": households}
            updated.append(
                self._handle_request("PUT", f"/api/foods/{food['id']}", json=merged)
            )

        return {"updated": updated, "created": created}

    def set_food_aliases(self, food_id: str, aliases: List[str]) -> Dict[str, Any]:
        """Replace a food's aliases with the given list.

        Args:
            food_id: The UUID of the food
            aliases: Alias names to set (replaces any existing aliases; pass
                an empty list to clear all aliases)

        Returns:
            JSON response containing the updated food
        """
        if not food_id:
            raise ValueError("Food ID cannot be empty")
        if aliases is None:
            raise ValueError("Aliases cannot be None")

        existing = self.get_food(food_id)

        seen = set()
        alias_dicts = []
        for raw_alias in aliases:
            name = raw_alias.strip()
            if not name or name.lower() in seen:
                continue
            alias_dicts.append({"name": name})
            seen.add(name.lower())

        merged = {**existing, "aliases": alias_dicts}

        logger.info({"message": "Setting food aliases"})
        return self._handle_request("PUT", f"/api/foods/{food_id}", json=merged)

    def add_food_alias(self, food_id: str, alias: str) -> Dict[str, Any]:
        """Add an alias to a food, keeping any aliases it already has.

        Args:
            food_id: The UUID of the food
            alias: Alias name to add

        Returns:
            JSON response containing the updated food
        """
        if not food_id:
            raise ValueError("Food ID cannot be empty")
        if not alias:
            raise ValueError("Alias cannot be empty")

        existing = self.get_food(food_id)
        aliases = list(existing.get("aliases", []))
        known = {(a.get("name") or "").lower() for a in aliases}

        name = alias.strip()
        if name and name.lower() not in known:
            aliases.append({"name": name})

        merged = {**existing, "aliases": aliases}

        logger.info({"message": "Adding food alias"})
        return self._handle_request("PUT", f"/api/foods/{food_id}", json=merged)

    def set_food_label(self, food_id: str, label_id: Optional[str]) -> Dict[str, Any]:
        """Set or clear a food's label.

        Args:
            food_id: The UUID of the food
            label_id: The UUID of the label to assign, or None to clear the
                food's label

        Returns:
            JSON response containing the updated food
        """
        if not food_id:
            raise ValueError("Food ID cannot be empty")

        existing = self.get_food(food_id)
        merged = {**existing, "labelId": label_id}

        logger.info({"message": "Setting food label"})
        return self._handle_request("PUT", f"/api/foods/{food_id}", json=merged)

    def _resolve_or_create_label(self, label_name: str) -> Dict[str, Any]:
        """Look up a label by name (case-insensitive), creating it if missing."""
        label_matches = self.get_labels(search=label_name).get("items", [])
        label = next(
            (
                label
                for label in label_matches
                if (label.get("name") or "").lower() == label_name.lower()
            ),
            None,
        )
        if label is None:
            label = self.create_label(label_name)
        return label

    def set_food_label_by_name(self, food_name: str, label_name: str) -> Dict[str, Any]:
        """Set a food's label, resolving both by name.

        The food must already exist (matched case-insensitively). The label
        is matched case-insensitively too, and created if no label with that
        name exists yet, mirroring the auto-create behaviour of
        ``set_foods_on_hand_by_name``.

        Args:
            food_name: Name of the food to update
            label_name: Name of the label to assign

        Returns:
            JSON response containing the updated food
        """
        if not food_name:
            raise ValueError("Food name cannot be empty")
        if not label_name:
            raise ValueError("Label name cannot be empty")

        food_matches = self.get_foods(search=food_name).get("items", [])
        food = next(
            (
                f
                for f in food_matches
                if (f.get("name") or "").lower() == food_name.lower()
            ),
            None,
        )
        if food is None:
            raise ValueError(f"No food found with name '{food_name}'")

        label = self._resolve_or_create_label(label_name)
        merged = {**food, "labelId": label["id"]}

        logger.info({"message": "Setting food label by name"})
        return self._handle_request("PUT", f"/api/foods/{food['id']}", json=merged)

    def set_foods_label_by_name(
        self, food_names: List[str], label_name: str
    ) -> Dict[str, Any]:
        """Set one label on multiple foods at once, resolving all by name.

        The label is resolved once (case-insensitive, created if missing) and
        applied to every matching food. Unlike ``set_foods_on_hand_by_name``,
        this does not create missing foods: a name with no match is reported
        under "not_found" instead, so one typo doesn't abort the whole batch.

        Args:
            food_names: Names of the foods to update
            label_name: Name of the label to assign to all of them

        Returns:
            Dict with "updated" (the updated food records) and "not_found"
            (names that didn't match an existing food)
        """
        if not food_names:
            raise ValueError("Food names cannot be empty")
        if not label_name:
            raise ValueError("Label name cannot be empty")

        label = self._resolve_or_create_label(label_name)
        updated = []
        not_found = []

        for raw_name in food_names:
            name = raw_name.strip()
            if not name:
                continue

            matches = self.get_foods(search=name).get("items", [])
            food = next(
                (f for f in matches if (f.get("name") or "").lower() == name.lower()),
                None,
            )
            if food is None:
                not_found.append(name)
                continue

            merged = {**food, "labelId": label["id"]}
            updated.append(
                self._handle_request("PUT", f"/api/foods/{food['id']}", json=merged)
            )

        logger.info({"message": "Setting label on foods by name"})
        return {"updated": updated, "not_found": not_found}

    def remove_food_alias(self, food_id: str, alias: str) -> Dict[str, Any]:
        """Remove an alias from a food.

        Args:
            food_id: The UUID of the food
            alias: Alias name to remove (matched case-insensitively)

        Returns:
            JSON response containing the updated food
        """
        if not food_id:
            raise ValueError("Food ID cannot be empty")
        if not alias:
            raise ValueError("Alias cannot be empty")

        existing = self.get_food(food_id)
        target = alias.strip().lower()
        aliases = [
            a
            for a in existing.get("aliases", [])
            if (a.get("name") or "").lower() != target
        ]

        merged = {**existing, "aliases": aliases}

        logger.info({"message": "Removing food alias"})
        return self._handle_request("PUT", f"/api/foods/{food_id}", json=merged)
