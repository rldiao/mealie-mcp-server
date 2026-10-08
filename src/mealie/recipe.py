import logging
import re
from typing import Any, Dict, List, Optional

import httpx
from pydantic import HttpUrl, TypeAdapter, ValidationError

from mealie.client import MealieApiError
from models.ai_import import AIProviderCapabilities
from utils import format_api_params

logger = logging.getLogger("mealie-mcp")


def _upload_extension(filename: str, extension: Optional[str] = None) -> str:
    """Resolve the bare extension (no dot, lowercase) for a Mealie upload.

    Mealie takes the extension as a separate form field on the image and asset
    upload endpoints instead of deriving it from the uploaded file name.
    """
    if extension:
        resolved = extension.strip().lstrip(".")
    else:
        stem, dot, suffix = filename.strip().rpartition(".")
        resolved = suffix if dot and stem else ""

    resolved = resolved.strip().lower()
    if not resolved:
        raise ValueError(
            "Could not determine a file extension; pass the extension explicitly"
        )
    return resolved


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

        logger.info({"message": "Retrieving recipes"})
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

        logger.info({"message": "Retrieving recipe"})
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

        logger.info({"message": "Updating recipe"})
        return self._handle_request("PUT", f"/api/recipes/{slug}", json=recipe_data)

    def create_recipe(self, name: str) -> str:
        """Create a new recipe

        Args:
            name: The name of the new recipe

        Returns:
            Slug of the newly created recipe
        """
        if not name.strip():
            raise ValueError("Recipe name cannot be empty")
        logger.info({"message": "Creating new recipe"})
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
        if not url.strip():
            raise ValueError("URL cannot be empty")

        logger.info({"message": "Importing recipe from URL"})
        return self._handle_request(
            "POST",
            "/api/recipes/create/url",
            json={"url": url, "includeTags": include_tags},
        )

    def import_recipe_with_ai(
        self,
        content: str | None = None,
        url: str | None = None,
        images: list[tuple[str, bytes]] | None = None,
        translate_language: str | None = None,
        create_new_organizers: bool = False,
    ) -> str:
        """Import combined sources using Mealie's configured AI providers."""
        for value, label in (
            (content, "Content"), (url, "URL"), (translate_language, "Translation language")
        ):
            if value is not None and not value.strip():
                raise ValueError(f"{label} cannot be empty")
        if not (content or url or images):
            raise ValueError("Provide content, a URL, or at least one image")
        if url is not None:
            TypeAdapter(HttpUrl).validate_python(url)
        for filename, image in images or []:
            if not filename.strip() or not image:
                raise ValueError("Image filename and data cannot be empty")

        try:
            group = self.get_current_group()
        except (MealieApiError, TimeoutError, ConnectionError):
            raise ValueError("Unable to determine Mealie AI capabilities") from None
        try:
            capabilities = AIProviderCapabilities.model_validate(
                group.get("aiProviderSettings") if isinstance(group, dict) else None
            )
        except ValidationError:
            raise ValueError("Unable to determine Mealie AI capabilities") from None
        if not capabilities.aiEnabled:
            raise ValueError("Configure a default AI provider in Mealie before importing")
        if images and not capabilities.imageProviderEnabled:
            raise ValueError("Configure an image AI provider in Mealie before importing photos")

        data = {"createNewOrganizers": str(create_new_organizers).lower()}
        for key, value in (
            ("content", content), ("url", url), ("translateLanguage", translate_language)
        ):
            if value is not None:
                data[key] = value
        # Mealie stores uploads by basename; prefix every name to avoid collisions.
        files = [
            ("images", (f"{index}-{filename}", image))
            for index, (filename, image) in enumerate(images or [])
        ]
        logger.info({"message": "Importing recipe with AI"})
        try:
            slug = self._handle_request(
                "POST", "/api/recipes/create/ai", data=data, files=files or None,
                timeout=httpx.Timeout(30.0, read=300.0),
            )
        except MealieApiError as error:
            if error.status_code == 404:
                raise ValueError(
                    "AI import endpoint unavailable; Mealie 3.23.0 or newer is required"
                ) from None
            raise
        except (TimeoutError, ConnectionError):
            raise ValueError(
                "AI import connection failed or timed out; creation outcome is unknown. "
                "Check Mealie for the recipe before retrying or using another import tool."
            ) from None
        if not isinstance(slug, str) or not re.fullmatch(r"[\w-]+", slug):
            raise ValueError(
                "Mealie returned an invalid AI import slug; creation outcome is unknown. "
                "Check Mealie before retrying."
            )
        return slug

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

        logger.info({"message": "Patching recipe"})
        return self._handle_request("PATCH", f"/api/recipes/{slug}", json=recipe_data)

    def set_recipe_categories(self, slug: str, category_ids: List[str]) -> Dict[str, Any]:
        """Set the categories for a recipe, replacing any existing categories.

        Args:
            slug: The slug identifier of the recipe
            category_ids: List of category UUIDs to assign

        Returns:
            JSON response containing the updated recipe details
        """
        if not slug:
            raise ValueError("Recipe slug cannot be empty")

        logger.info({"message": "Setting recipe categories"})
        categories = [self.get_category(cid) for cid in category_ids]
        return self._handle_request("PATCH", f"/api/recipes/{slug}", json={"recipeCategory": categories})

    def set_recipe_tags(self, slug: str, tag_ids: List[str]) -> Dict[str, Any]:
        """Set the tags for a recipe, replacing any existing tags.

        Args:
            slug: The slug identifier of the recipe
            tag_ids: List of tag UUIDs to assign

        Returns:
            JSON response containing the updated recipe details
        """
        if not slug:
            raise ValueError("Recipe slug cannot be empty")

        logger.info({"message": "Setting recipe tags"})
        tags = [self.get_tag(tid) for tid in tag_ids]
        return self._handle_request("PATCH", f"/api/recipes/{slug}", json={"tags": tags})

    def add_recipe_tags(self, slug: str, tag_names: List[str]) -> Dict[str, Any]:
        """Add one or more tags to a recipe without removing existing tags.

        Tag names are matched case-insensitively against the recipe's current
        tags and against Mealie's existing tags; a name with no match is
        created as a new tag.

        Args:
            slug: The slug identifier of the recipe
            tag_names: Tag names to add (created in Mealie if they don't exist)

        Returns:
            JSON response containing the updated recipe details
        """
        if not slug:
            raise ValueError("Recipe slug cannot be empty")
        if not tag_names:
            raise ValueError("Tag names cannot be empty")

        logger.info({"message": "Adding recipe tags"})

        recipe = self.get_recipe(slug)
        merged_tags = list(recipe.get("tags", []))
        known_names = {(t.get("name") or "").lower() for t in merged_tags}

        for raw_name in tag_names:
            name = raw_name.strip()
            if not name or name.lower() in known_names:
                continue

            matches = self.get_tags(search=name).get("items", [])
            tag = next(
                (t for t in matches if (t.get("name") or "").lower() == name.lower()),
                None,
            )
            if tag is None:
                tag = self.create_tag(name)

            merged_tags.append(tag)
            known_names.add(name.lower())

        return self._handle_request(
            "PATCH", f"/api/recipes/{slug}", json={"tags": merged_tags}
        )

    def set_recipe_categories_and_tags(
        self,
        slug: str,
        category_ids: Optional[List[str]] = None,
        tag_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Update categories and/or tags for a recipe in a single API call.

        Args:
            slug: The slug identifier of the recipe
            category_ids: List of category UUIDs to assign (None = leave unchanged)
            tag_ids: List of tag UUIDs to assign (None = leave unchanged)

        Returns:
            JSON response containing the updated recipe details
        """
        if not slug:
            raise ValueError("Recipe slug cannot be empty")
        if category_ids is None and tag_ids is None:
            raise ValueError("At least one of category_ids or tag_ids must be provided")

        logger.info({"message": "Setting recipe categories and tags"})
        recipe_data = {}
        if category_ids is not None:
            recipe_data["recipeCategory"] = [self.get_category(cid) for cid in category_ids]
        if tag_ids is not None:
            recipe_data["tags"] = [self.get_tag(tid) for tid in tag_ids]
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

        logger.info({"message": "Duplicating recipe"})
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

        logger.info({"message": "Updating recipe last made"})
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

        logger.info({"message": "Scraping recipe image from URL"})
        return self._handle_request("POST", f"/api/recipes/{slug}/image", json=payload)

    def upload_recipe_image(
        self,
        slug: str,
        image_data: bytes,
        filename: str,
        extension: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Upload a recipe image file (multipart upload)

        Args:
            slug: The slug identifier of the recipe
            image_data: Binary image data
            filename: Name of the image file
            extension: Image extension such as "jpg"; derived from filename when omitted

        Returns:
            JSON response confirming the image was uploaded
        """
        if not slug:
            raise ValueError("Recipe slug cannot be empty")
        if not image_data:
            raise ValueError("Image data cannot be empty")
        if not filename:
            raise ValueError("Filename cannot be empty")

        extension = _upload_extension(filename, extension)

        files = {"image": (filename, image_data)}
        # Mealie requires the extension as a separate form field
        data = {"extension": extension}

        logger.info({"message": "Uploading recipe image"})
        return self._handle_request("PUT", f"/api/recipes/{slug}/image", files=files, data=data)

    def upload_recipe_asset(
        self,
        slug: str,
        asset_data: bytes,
        filename: str,
        name: Optional[str] = None,
        icon: Optional[str] = None,
        extension: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Upload a recipe asset file (multipart upload)

        Args:
            slug: The slug identifier of the recipe
            asset_data: Binary asset data
            filename: Name of the asset file
            name: Display name of the asset; derived from filename when omitted
            icon: Material Design icon name; defaults to "mdi-file"
            extension: Asset extension such as "pdf"; derived from filename when omitted

        Returns:
            JSON response containing the uploaded asset details
        """
        if not slug:
            raise ValueError("Recipe slug cannot be empty")
        if not asset_data:
            raise ValueError("Asset data cannot be empty")
        if not filename:
            raise ValueError("Filename cannot be empty")

        extension = _upload_extension(filename, extension)
        name = name or filename.rsplit(".", 1)[0] or filename

        files = {"file": (filename, asset_data)}
        # Mealie requires name, icon and extension as separate form fields
        data = {"name": name, "icon": icon or "mdi-file", "extension": extension}

        logger.info({"message": "Uploading recipe asset"})
        return self._handle_request("POST", f"/api/recipes/{slug}/assets", files=files, data=data)

    def delete_recipe(self, slug: str) -> Dict[str, Any]:
        """Delete a recipe

        Args:
            slug: The slug identifier of the recipe to delete

        Returns:
            JSON response confirming deletion
        """
        if not slug:
            raise ValueError("Recipe slug cannot be empty")

        logger.info({"message": "Deleting recipe"})
        return self._handle_request("DELETE", f"/api/recipes/{slug}")
