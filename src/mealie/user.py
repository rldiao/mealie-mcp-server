import logging
from typing import Any, Dict, Optional

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

    def get_my_ratings(self) -> Dict[str, Any]:
        """Get the current user's recipe ratings and favorites.

        Returns:
            {"ratings": [{"recipeId", "rating", "isFavorite"}, ...]}
        """
        logger.info({"message": "Retrieving recipe ratings"})
        return self._handle_request("GET", "/api/users/self/ratings")

    def rate_recipe(
        self,
        slug: str,
        rating: Optional[float] = None,
        is_favorite: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Set the current user's rating and/or favorite flag on a recipe.

        Fields left as None keep their current value.

        Returns:
            The values that were set, with the recipe slug
        """
        if not slug or not slug.strip():
            raise ValueError("Recipe slug cannot be empty")
        if rating is None and is_favorite is None:
            raise ValueError("Provide a rating, is_favorite, or both")
        payload: Dict[str, Any] = {}
        if rating is not None:
            payload["rating"] = rating
        if is_favorite is not None:
            payload["isFavorite"] = is_favorite
        user_id = self.get_current_user().get("id")
        if not user_id:
            raise ValueError("Could not determine the current user")

        logger.info({"message": "Rating recipe"})
        self._handle_request("POST", f"/api/users/{user_id}/ratings/{slug}", json=payload)
        return {"success": True, "slug": slug, **payload}
