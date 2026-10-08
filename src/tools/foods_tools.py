from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from mealie import MealieFetcher
from tools.errors import tool_error_boundary


def register_foods_tools(mcp: FastMCP, mealie: MealieFetcher) -> None:
    """Register all food-related tools with the MCP server."""

    @mcp.tool()
    def get_foods(
        search: Optional[str] = None,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
    ) -> Dict[str, Any]:
        """List the household's foods, optionally filtered by a search term.

        Use this to resolve an existing Mealie food id+name before building a
        structured ingredient, instead of hardcoding UUIDs. The Mealie search is
        token-based; do client-side matching against the returned items if you
        need fuzzy matching (e.g. "Basmatireis" -> "Reis").

        Args:
            search: Search term to filter foods by name/alias.
            page: Page number to retrieve.
            per_page: Number of items per page.

        Returns:
            Dict[str, Any]: Foods (under "items") with pagination information.
        """
        with tool_error_boundary("Error fetching foods"):
            return mealie.get_foods(search=search, page=page, per_page=per_page)

    @mcp.tool()
    def create_food(
        name: str,
        plural_name: Optional[str] = None,
        description: Optional[str] = None,
        extras: Optional[Dict[str, Any]] = None,
        label_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new food.

        Args:
            name: Name of the food (e.g. "Reis").
            plural_name: Optional plural name.
            description: Optional description.
            extras: Optional arbitrary key-value metadata dict stored on the food
                (Mealie's ``extras`` field) — e.g. external identifiers.
            label_id: Optional UUID of a Multi Purpose Label to assign (used for
                aisle/section grouping on shopping lists).

        Returns:
            Dict[str, Any]: The created food.
        """
        with tool_error_boundary("Error creating food"):
            return mealie.create_food(
                name,
                plural_name=plural_name,
                description=description,
                extras=extras,
                label_id=label_id,
            )

    @mcp.tool()
    def get_food(food_id: str) -> Dict[str, Any]:
        """Get a specific food by ID.

        Args:
            food_id: The UUID of the food.

        Returns:
            Dict[str, Any]: The food details.
        """
        with tool_error_boundary("Error fetching food"):
            return mealie.get_food(food_id)

    @mcp.tool()
    def update_food(
        food_id: str,
        name: Optional[str] = None,
        plural_name: Optional[str] = None,
        description: Optional[str] = None,
        extras: Optional[Dict[str, Any]] = None,
        label_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a food's details (only provided fields are changed).

        Args:
            food_id: The UUID of the food to update.
            name: New name for the food.
            plural_name: New plural name.
            description: New description.
            extras: Arbitrary key-value metadata dict to store on the food
                (Mealie's ``extras`` field). Replaces the food's existing extras.
            label_id: UUID of a Multi Purpose Label to assign (aisle/section
                grouping). Pass an empty string to clear the label.

        Returns:
            Dict[str, Any]: The updated food.
        """
        with tool_error_boundary("Error updating food"):
            food_data: Dict[str, Any] = {}
            if name is not None:
                food_data["name"] = name
            if plural_name is not None:
                food_data["pluralName"] = plural_name
            if description is not None:
                food_data["description"] = description
            if extras is not None:
                food_data["extras"] = extras
            if label_id is not None:
                # "" is the caller's "clear the label" sentinel; Mealie's API
                # rejects an empty string for a UUID field and wants null instead.
                food_data["labelId"] = label_id or None

            if not food_data:
                raise ValueError("At least one field must be provided to update")

            return mealie.update_food(food_id, food_data)

    @mcp.tool()
    def delete_food(food_id: str) -> Dict[str, Any]:
        """Delete a specific food.

        Args:
            food_id: The UUID of the food to delete.

        Returns:
            Dict[str, Any]: Confirmation of deletion.
        """
        with tool_error_boundary("Error deleting food"):
            return mealie.delete_food(food_id)

    @mcp.tool()
    def set_food_on_hand(food_id: str, on_hand: bool = True) -> Dict[str, Any]:
        """Mark or unmark a food as on-hand for the current household.

        Args:
            food_id: The UUID of the food.
            on_hand: True to mark on-hand, False to clear it. Defaults to True.

        Returns:
            Dict[str, Any]: The updated food.
        """
        with tool_error_boundary("Error setting food on-hand status"):
            return mealie.set_food_on_hand(food_id, on_hand=on_hand)

    @mcp.tool()
    def mark_foods_on_hand(names: List[str], on_hand: bool = True) -> Dict[str, Any]:
        """Mark or unmark common ingredients as on-hand, by name.

        Use this instead of set_food_on_hand when you know ingredient names
        (e.g. pantry staples like "Salt", "Flour", "Olive Oil") but not their
        Mealie food IDs. Names are matched case-insensitively against
        existing foods; a name with no match is created as a new food.

        Args:
            names: Food names to update.
            on_hand: True to mark on-hand, False to clear it. Defaults to True.

        Returns:
            Dict[str, Any]: {"updated": [...updated foods], "created": [...names of foods that were created]}.
        """
        with tool_error_boundary("Error marking foods on-hand"):
            return mealie.set_foods_on_hand_by_name(names, on_hand=on_hand)

    @mcp.tool()
    def set_food_aliases(food_id: str, aliases: List[str]) -> Dict[str, Any]:
        """Replace a food's aliases with the given list.

        Aliases let Mealie match alternate names for a food (e.g. "Scallion"
        as an alias for "Green Onion") when parsing ingredients. This
        replaces the whole list; pass an empty list to clear all aliases, or
        use add_food_alias/remove_food_alias to change one at a time.

        Args:
            food_id: The UUID of the food.
            aliases: Alias names to set, e.g. ["Scallion", "Spring Onion"].

        Returns:
            Dict[str, Any]: The updated food.
        """
        with tool_error_boundary("Error setting food aliases"):
            return mealie.set_food_aliases(food_id, aliases)

    @mcp.tool()
    def add_food_alias(food_id: str, alias: str) -> Dict[str, Any]:
        """Add an alias to a food, keeping any aliases it already has.

        Args:
            food_id: The UUID of the food.
            alias: Alias name to add, e.g. "Scallion".

        Returns:
            Dict[str, Any]: The updated food.
        """
        with tool_error_boundary("Error adding food alias"):
            return mealie.add_food_alias(food_id, alias)

    @mcp.tool()
    def set_food_label(food_id: str, label_id: Optional[str] = None) -> Dict[str, Any]:
        """Set or clear a food's label.

        Args:
            food_id: The UUID of the food.
            label_id: The UUID of the label to assign. Omit or pass None to
                clear the food's label.

        Returns:
            Dict[str, Any]: The updated food.
        """
        with tool_error_boundary("Error setting food label"):
            return mealie.set_food_label(food_id, label_id)

    @mcp.tool()
    def set_food_label_by_name(food_name: str, label_name: str) -> Dict[str, Any]:
        """Set a food's label, resolving both the food and label by name.

        Use this instead of set_food_label when you know the food and label
        names but not their Mealie IDs. Both are matched case-insensitively;
        the food must already exist, but the label is created if no label
        with that name exists yet.

        Args:
            food_name: Name of the food to update, e.g. "Carrot".
            label_name: Name of the label to assign, e.g. "Produce".

        Returns:
            Dict[str, Any]: The updated food.
        """
        with tool_error_boundary("Error setting food label by name"):
            return mealie.set_food_label_by_name(food_name, label_name)

    @mcp.tool()
    def set_foods_label_by_name(
        food_names: List[str], label_name: str
    ) -> Dict[str, Any]:
        """Set one label on multiple foods at once, by name.

        Use this instead of calling set_food_label_by_name repeatedly when
        applying the same label to a batch of foods (e.g. tagging a set of
        ingredients as "Produce"). The label is resolved once (created if it
        doesn't exist) and applied to every matching food; food names are
        matched case-insensitively and are NOT auto-created, so a typo is
        reported instead of silently creating a new food.

        Args:
            food_names: Names of the foods to update, e.g. ["Carrot", "Onion"].
            label_name: Name of the label to assign to all of them, e.g. "Produce".

        Returns:
            Dict[str, Any]: {"updated": [...updated foods], "not_found": [...names with no matching food]}.
        """
        with tool_error_boundary("Error setting label on foods"):
            return mealie.set_foods_label_by_name(food_names, label_name)

    @mcp.tool()
    def remove_food_alias(food_id: str, alias: str) -> Dict[str, Any]:
        """Remove an alias from a food.

        Args:
            food_id: The UUID of the food.
            alias: Alias name to remove (matched case-insensitively).

        Returns:
            Dict[str, Any]: The updated food.
        """
        with tool_error_boundary("Error removing food alias"):
            return mealie.remove_food_alias(food_id, alias)
