import logging
from typing import Any, Dict, List, Optional

from utils import format_api_params

logger = logging.getLogger("mealie-mcp")


class RecipeMixin:
    """Mixin class for recipe-related API endpoints"""

    def get_recipes(
        self,
        search: Optional[str] = None,
        order_by: Optional[str] = None,
        order_by_null_position: Optional[str] = None,
        order_direction: Optional[str] = "desc",
        query_filter: Optional[str] = None,
        pagination_seed: Optional[str] = None,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        categories: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        tools: Optional[List[str]] = None,
        require_all_tags: Optional[bool] = None,
        require_all_categories: Optional[bool] = None,
        require_all_tools: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Provides paginated list of recipes

        Args:
            search: Search term to filter recipes by name, description, etc.
            order_by: Field to order results by
            order_by_null_position: How to handle nulls in ordering ('first' or 'last')
            order_direction: Direction to order results ('asc' or 'desc')
            query_filter: Advanced query filter
            pagination_seed: Seed for consistent pagination
            page: Page number to retrieve
            per_page: Number of items per page
            categories: List of category slugs (NOT names) to filter by
            tags: List of tag slugs or UUIDs (NOT display names) to filter by
            tools: List of tool slugs to filter by
            require_all_tags: If True, recipe must have ALL specified tags (AND logic). Default False (OR logic)
            require_all_categories: If True, recipe must have ALL specified categories (AND logic)
            require_all_tools: If True, recipe must have ALL specified tools (AND logic)

        Returns:
            JSON response containing recipe items and pagination information
        """

        param_dict = {
            "search": search,
            "orderBy": order_by,
            "orderByNullPosition": order_by_null_position,
            "orderDirection": order_direction,
            "queryFilter": query_filter,
            "paginationSeed": pagination_seed,
            "page": page,
            "perPage": per_page,
            "categories": categories,
            "tags": tags,
            "tools": tools,
            "requireAllTags": require_all_tags,
            "requireAllCategories": require_all_categories,
            "requireAllTools": require_all_tools,
        }

        params = format_api_params(param_dict)

        logger.info({"message": "Retrieving recipes", "parameters": params})
        return self._handle_request("GET", "/api/recipes", params=params)

    def get_recipe(self, slug: str) -> Dict[str, Any]:
        """Retrieve a specific recipe by its slug

        Args:
            slug: The slug identifier of the recipe to retrieve

        Returns:
            JSON response containing all recipe details
        """
        if not slug:
            raise ValueError("Recipe slug cannot be empty")

        logger.info({"message": "Retrieving recipe", "slug": slug})
        return self._handle_request("GET", f"/api/recipes/{slug}")

    def update_recipe(self, slug: str, recipe_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a specific recipe by its slug

        Args:
            slug: The slug identifier of the recipe to update
            recipe_data: Dictionary containing the recipe properties to update

        Returns:
            JSON response containing the updated recipe details
        """
        if not slug:
            raise ValueError("Recipe slug cannot be empty")
        if not recipe_data:
            raise ValueError("Recipe data cannot be empty")

        logger.info({"message": "Updating recipe", "slug": slug})
        return self._handle_request("PUT", f"/api/recipes/{slug}", json=recipe_data)

    def create_recipe(self, name: str) -> str:
        """Create a new recipe

        Args:
            name: The name of the new recipe

        Returns:
            Slug of the newly created recipe
        """
        logger.info({"message": "Creating new recipe", "name": name})
        return self._handle_request("POST", "/api/recipes", json={"name": name})

    def import_recipe_from_url(
        self, url: str, include_tags: bool = False
    ) -> str:
        """Create a recipe by scraping a URL using Mealie's built-in scraper

        Mealie's server uses the `recipe-scrapers` library, which has built-in
        adapters for major recipe sites and falls back to JSON-LD/Schema.org
        parsing for other sites.

        Args:
            url: Source URL of the recipe to import
            include_tags: If True, import tags Mealie extracts from the source

        Returns:
            Slug of the newly created recipe
        """
        if not url:
            raise ValueError("URL cannot be empty")

        logger.info({"message": "Importing recipe from URL", "url": url})
        return self._handle_request(
            "POST",
            "/api/recipes/create/url",
            json={"url": url, "includeTags": include_tags},
        )

    def patch_recipe(self, slug: str, recipe_data: Dict[str, Any]) -> Dict[str, Any]:
        """Partially update a recipe (only updates provided fields)

        Args:
            slug: The slug identifier of the recipe to patch
            recipe_data: Dictionary containing only the fields to update

        Returns:
            JSON response containing the updated recipe details
        """
        if not slug:
            raise ValueError("Recipe slug cannot be empty")
        if not recipe_data:
            raise ValueError("Recipe data cannot be empty")

        logger.info({"message": "Patching recipe", "slug": slug})
        return self._handle_request("PATCH", f"/api/recipes/{slug}", json=recipe_data)

    def duplicate_recipe(self, slug: str, name: Optional[str] = None) -> Dict[str, Any]:
        """Duplicate an existing recipe

        Args:
            slug: The slug identifier of the recipe to duplicate
            name: Optional new name for the duplicate (defaults to original name + copy indicator)

        Returns:
            JSON response containing the newly created duplicate recipe
        """
        if not slug:
            raise ValueError("Recipe slug cannot be empty")

        payload = {}
        if name:
            payload["name"] = name

        logger.info({"message": "Duplicating recipe", "slug": slug})
        return self._handle_request("POST", f"/api/recipes/{slug}/duplicate", json=payload)

    def update_recipe_last_made(self, slug: str, timestamp: Optional[str] = None) -> Dict[str, Any]:
        """Update the last made timestamp for a recipe

        Args:
            slug: The slug identifier of the recipe
            timestamp: ISO format timestamp (if None, uses current time)

        Returns:
            JSON response containing the updated recipe
        """
        if not slug:
            raise ValueError("Recipe slug cannot be empty")

        # If no timestamp provided, use current time
        if not timestamp:
            from datetime import datetime
            timestamp = datetime.utcnow().isoformat() + "Z"

        payload = {"timestamp": timestamp}

        logger.info({"message": "Updating recipe last made", "slug": slug})
        return self._handle_request("PATCH", f"/api/recipes/{slug}/last-made", json=payload)

    def scrape_recipe_image_from_url(self, slug: str, image_url: str) -> Dict[str, Any]:
        """Scrape and set a recipe's image from a URL (JSON payload)

        Args:
            slug: The slug identifier of the recipe
            image_url: URL of the image to scrape

        Returns:
            JSON response confirming the image was set
        """
        if not slug:
            raise ValueError("Recipe slug cannot be empty")
        if not image_url:
            raise ValueError("Image URL cannot be empty")

        payload = {"url": image_url}

        logger.info({"message": "Scraping recipe image from URL", "slug": slug, "url": image_url})
        return self._handle_request("POST", f"/api/recipes/{slug}/image", json=payload)

    def upload_recipe_image(self, slug: str, image_data: bytes, filename: str) -> Dict[str, Any]:
        """Upload a recipe image file (multipart upload)

        Args:
            slug: The slug identifier of the recipe
            image_data: Binary image data
            filename: Name of the image file

        Returns:
            JSON response confirming the image was uploaded
        """
        if not slug:
            raise ValueError("Recipe slug cannot be empty")
        if not image_data:
            raise ValueError("Image data cannot be empty")
        if not filename:
            raise ValueError("Filename cannot be empty")

        files = {"image": (filename, image_data)}

        logger.info({"message": "Uploading recipe image", "slug": slug, "filename": filename})
        return self._handle_request("PUT", f"/api/recipes/{slug}/image", files=files)

    def upload_recipe_asset(self, slug: str, asset_data: bytes, filename: str) -> Dict[str, Any]:
        """Upload a recipe asset file (multipart upload)

        Args:
            slug: The slug identifier of the recipe
            asset_data: Binary asset data
            filename: Name of the asset file

        Returns:
            JSON response containing the uploaded asset details
        """
        if not slug:
            raise ValueError("Recipe slug cannot be empty")
        if not asset_data:
            raise ValueError("Asset data cannot be empty")
        if not filename:
            raise ValueError("Filename cannot be empty")

        files = {"file": (filename, asset_data)}

        logger.info({"message": "Uploading recipe asset", "slug": slug, "filename": filename})
        return self._handle_request("POST", f"/api/recipes/{slug}/assets", files=files)

    def delete_recipe(self, slug: str) -> Dict[str, Any]:
        """Delete a recipe

        Args:
            slug: The slug identifier of the recipe to delete

        Returns:
            JSON response confirming deletion
        """
        if not slug:
            raise ValueError("Recipe slug cannot be empty")

        logger.info({"message": "Deleting recipe", "slug": slug})
        return self._handle_request("DELETE", f"/api/recipes/{slug}")
