import logging
from typing import Any, Dict

logger = logging.getLogger("mealie-mcp")


class UserMixin:
    """Mixin class for user-related API endpoints"""

    def get_current_user(self) -> Dict[str, Any]:
        """Get information about the currently logged in user.

        Returns:
            Dictionary containing user details such as id, username, email, and other profile information.
        """
        logger.info({"message": "Retrieving current user information"})
        return self._handle_request("GET", "/api/users/self")

    def _current_household_slug(self) -> str:
        """Slug of the API user's household.

        Mealie's householdsWithIngredientFood and householdsWithTool lists hold
        household slugs; it silently drops household IDs written there.
        """
        slug = self.get_current_user().get("householdSlug")
        if not slug:
            raise ValueError("Could not determine the current household")
        return slug
