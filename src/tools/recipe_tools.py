import logging
import traceback
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from mealie import MealieFetcher
from models.recipe import Recipe, RecipeIngredient, RecipeInstruction

logger = logging.getLogger("mealie-mcp")


def register_recipe_tools(mcp: FastMCP, mealie: MealieFetcher) -> None:
    """Register all recipe-related tools with the MCP server."""

    @mcp.tool()
    def get_recipes(
        search: Optional[str] = None,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        categories: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        require_all_tags: Optional[bool] = None,
        require_all_categories: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Provides a paginated list of recipes with optional filtering.

        IMPORTANT: When filtering by tags or categories, you MUST use slugs or UUIDs, NOT display names!
        - ✅ Correct: tags=["quick-meals", "vegetarian"]
        - ❌ Wrong: tags=["Quick Meals", "Vegetarian"]

        Use get_tags() or get_categories() first to find the correct slugs.

        Args:
            search: Filters recipes by name or description.
            page: Page number for pagination.
            per_page: Number of items per page.
            categories: Filter by category SLUGS (e.g., ["breakfast", "dinner"]).
            tags: Filter by tag SLUGS or UUIDs (e.g., ["quick", "healthy"]).
            require_all_tags: If True, recipe must have ALL specified tags (AND). Default False (OR).
            require_all_categories: If True, recipe must have ALL specified categories (AND).

        Returns:
            Dict[str, Any]: Recipe summaries with details like ID, name, description, and image information.
        """
        try:
            logger.info(
                {
                    "message": "Fetching recipes",
                    "search": search,
                    "page": page,
                    "per_page": per_page,
                    "categories": categories,
                    "tags": tags,
                    "require_all_tags": require_all_tags,
                    "require_all_categories": require_all_categories,
                }
            )
            return mealie.get_recipes(
                search=search,
                page=page,
                per_page=per_page,
                categories=categories,
                tags=tags,
                require_all_tags=require_all_tags,
                require_all_categories=require_all_categories,
            )
        except Exception as e:
            error_msg = f"Error fetching recipes: {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise ToolError(error_msg)

    @mcp.tool()
    def get_recipe_detailed(slug: str) -> Dict[str, Any]:
        """Retrieve a specific recipe by its slug identifier. Use this when to get full recipe
        details for tasks like updating or displaying the recipe.

        Args:
            slug: The unique text identifier for the recipe, typically found in recipe URLs
                or from get_recipes results.

        Returns:
            Dict[str, Any]: Comprehensive recipe details including ingredients, instructions,
                nutrition information, notes, and associated metadata.
        """
        try:
            logger.info({"message": "Fetching recipe", "slug": slug})
            return mealie.get_recipe(slug)
        except Exception as e:
            error_msg = f"Error fetching recipe with slug '{slug}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise ToolError(error_msg)

    @mcp.tool()
    def get_recipe_concise(slug: str) -> Dict[str, Any]:
        """Retrieve a concise version of a specific recipe by its slug identifier. Use this when you only
        need a summary of the recipe, such as for when mealplaning.

        Args:
            slug: The unique text identifier for the recipe, typically found in recipe URLs
                or from get_recipes results.

        Returns:
            Dict[str, Any]: Concise recipe summary with essential fields.
        """
        try:
            logger.info({"message": "Fetching recipe", "slug": slug})
            recipe_json = mealie.get_recipe(slug)
            recipe = Recipe.model_validate(recipe_json)
            return recipe.model_dump(
                include={
                    "name",
                    "slug",
                    "recipeServings",
                    "recipeYieldQuantity",
                    "recipeYield",
                    "totalTime",
                    "rating",
                    "recipeIngredient",
                    "lastMade",
                },
                exclude_none=True,
            )
        except Exception as e:
            error_msg = f"Error fetching recipe with slug '{slug}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise ToolError(error_msg)

    @mcp.tool()
    def create_recipe(
        name: str, ingredients: List[str], instructions: List[str]
    ) -> Dict[str, Any]:
        """Create a new recipe

        Args:
            name: The name of the new recipe to be created.
            ingredients: A list of ingredients for the recipe include quantities and units.
            instructions: A list of instructions for preparing the recipe.

        Returns:
            Dict[str, Any]: The created recipe details.
        """
        try:
            logger.info({"message": "Creating recipe", "name": name})
            slug = mealie.create_recipe(name)
            recipe_json = mealie.get_recipe(slug)
            recipe = Recipe.model_validate(recipe_json)
            recipe.recipeIngredient = [RecipeIngredient(note=i) for i in ingredients]
            recipe.recipeInstructions = [
                RecipeInstruction(text=i) for i in instructions
            ]
            return mealie.update_recipe(slug, recipe.model_dump(exclude_none=True))
        except Exception as e:
            error_msg = f"Error creating recipe '{name}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise ToolError(error_msg)

    @mcp.tool()
    def update_recipe(
        slug: str,
        ingredients: List[str],
        instructions: List[str],
    ) -> Dict[str, Any]:
        """Replaces the ingredients and instructions of an existing recipe.

        Args:
            slug: The unique text identifier for the recipe to be updated.
            ingredients: A list of ingredients for the recipe include quantities and units.
            instructions: A list of instructions for preparing the recipe.

        Returns:
            Dict[str, Any]: The updated recipe details.
        """
        try:
            logger.info({"message": "Updating recipe", "slug": slug})
            recipe_json = mealie.get_recipe(slug)
            recipe = Recipe.model_validate(recipe_json)
            recipe.recipeIngredient = [RecipeIngredient(note=i) for i in ingredients]
            recipe.recipeInstructions = [
                RecipeInstruction(text=i) for i in instructions
            ]
            return mealie.update_recipe(slug, recipe.model_dump(exclude_none=True))
        except Exception as e:
            error_msg = f"Error updating recipe '{slug}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise ToolError(error_msg)

    @mcp.tool()
    def patch_recipe(
        slug: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        recipe_yield: Optional[str] = None,
        total_time: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Partially update a recipe (only updates provided fields).

        Args:
            slug: The unique text identifier for the recipe to be updated.
            name: New name for the recipe (optional)
            description: New description for the recipe (optional)
            recipe_yield: New yield/servings for the recipe (optional)
            total_time: New total time for the recipe (optional)

        Returns:
            Dict[str, Any]: The updated recipe details.
        """
        try:
            logger.info({"message": "Patching recipe", "slug": slug})

            recipe_data = {}
            if name is not None:
                recipe_data["name"] = name
            if description is not None:
                recipe_data["description"] = description
            if recipe_yield is not None:
                recipe_data["recipeYield"] = recipe_yield
            if total_time is not None:
                recipe_data["totalTime"] = total_time

            if not recipe_data:
                raise ValueError("At least one field must be provided to update")

            return mealie.patch_recipe(slug, recipe_data)
        except Exception as e:
            error_msg = f"Error patching recipe '{slug}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug({"message": "Error traceback", "traceback": traceback.format_exc()})
            raise ToolError(error_msg)

    @mcp.tool()
    def duplicate_recipe(slug: str, name: Optional[str] = None) -> Dict[str, Any]:
        """Duplicate an existing recipe, creating a copy with a new slug.

        Args:
            slug: The unique text identifier for the recipe to duplicate.
            name: Optional new name for the duplicate (if not provided, uses original name with copy indicator).

        Returns:
            Dict[str, Any]: The newly created duplicate recipe details.
        """
        try:
            logger.info({"message": "Duplicating recipe", "slug": slug, "name": name})
            return mealie.duplicate_recipe(slug, name)
        except Exception as e:
            error_msg = f"Error duplicating recipe '{slug}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug({"message": "Error traceback", "traceback": traceback.format_exc()})
            raise ToolError(error_msg)

    @mcp.tool()
    def mark_recipe_last_made(slug: str) -> Dict[str, Any]:
        """Mark a recipe as having been made today (updates last made timestamp).

        Args:
            slug: The unique text identifier for the recipe.

        Returns:
            Dict[str, Any]: The updated recipe details.
        """
        try:
            logger.info({"message": "Marking recipe as last made", "slug": slug})
            return mealie.update_recipe_last_made(slug)
        except Exception as e:
            error_msg = f"Error updating recipe last made '{slug}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug({"message": "Error traceback", "traceback": traceback.format_exc()})
            raise ToolError(error_msg)

    @mcp.tool()
    def set_recipe_image_from_url(slug: str, image_url: str) -> Dict[str, Any]:
        """Set a recipe's image by scraping it from a URL.

        Args:
            slug: The unique text identifier for the recipe.
            image_url: URL of the image to scrape and use as the recipe image.

        Returns:
            Dict[str, Any]: Confirmation that the image was set.
        """
        try:
            logger.info({"message": "Setting recipe image from URL", "slug": slug, "url": image_url})
            return mealie.scrape_recipe_image_from_url(slug, image_url)
        except Exception as e:
            error_msg = f"Error setting recipe image from URL '{slug}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug({"message": "Error traceback", "traceback": traceback.format_exc()})
            raise ToolError(error_msg)

    @mcp.tool()
    def upload_recipe_image_file(slug: str, image_path: str) -> Dict[str, Any]:
        """Upload an image file for a recipe.

        Args:
            slug: The unique text identifier for the recipe.
            image_path: Local file path to the image to upload.

        Returns:
            Dict[str, Any]: Confirmation that the image was uploaded.
        """
        try:
            import os

            logger.info({"message": "Uploading recipe image", "slug": slug, "path": image_path})

            if not os.path.exists(image_path):
                raise ValueError(f"Image file not found: {image_path}")

            with open(image_path, "rb") as f:
                image_data = f.read()

            filename = os.path.basename(image_path)
            return mealie.upload_recipe_image(slug, image_data, filename)
        except Exception as e:
            error_msg = f"Error uploading recipe image '{slug}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug({"message": "Error traceback", "traceback": traceback.format_exc()})
            raise ToolError(error_msg)

    @mcp.tool()
    def upload_recipe_asset_file(slug: str, asset_path: str) -> Dict[str, Any]:
        """Upload an asset file (document, PDF, etc.) for a recipe.

        Args:
            slug: The unique text identifier for the recipe.
            asset_path: Local file path to the asset to upload.

        Returns:
            Dict[str, Any]: Details of the uploaded asset.
        """
        try:
            import os

            logger.info({"message": "Uploading recipe asset", "slug": slug, "path": asset_path})

            if not os.path.exists(asset_path):
                raise ValueError(f"Asset file not found: {asset_path}")

            with open(asset_path, "rb") as f:
                asset_data = f.read()

            filename = os.path.basename(asset_path)
            return mealie.upload_recipe_asset(slug, asset_data, filename)
        except Exception as e:
            error_msg = f"Error uploading recipe asset '{slug}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug({"message": "Error traceback", "traceback": traceback.format_exc()})
            raise ToolError(error_msg)

    @mcp.tool()
    def set_recipe_categories(slug: str, category_ids: List[str]) -> Dict[str, Any]:
        """Set the categories for a recipe, replacing any existing categories.
        Use get_categories() first to find valid category IDs.
        Passing an empty list will remove all categories from the recipe.

        Args:
            slug: The unique text identifier for the recipe.
            category_ids: List of category UUIDs to assign.

        Returns:
            Dict[str, Any]: The updated recipe details.
        """
        try:
            logger.info({"message": "Setting recipe categories", "slug": slug, "category_ids": category_ids})
            return mealie.set_recipe_categories(slug, category_ids)
        except Exception as e:
            error_msg = f"Error setting categories on recipe '{slug}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug({"message": "Error traceback", "traceback": traceback.format_exc()})
            raise ToolError(error_msg)

    @mcp.tool()
    def set_recipe_tags(slug: str, tag_ids: List[str]) -> Dict[str, Any]:
        """Set the tags for a recipe, replacing any existing tags.
        Use get_tags() first to find valid tag IDs.
        Passing an empty list will remove all tags from the recipe.

        Args:
            slug: The unique text identifier for the recipe.
            tag_ids: List of tag UUIDs to assign.

        Returns:
            Dict[str, Any]: The updated recipe details.
        """
        try:
            logger.info({"message": "Setting recipe tags", "slug": slug, "tag_ids": tag_ids})
            return mealie.set_recipe_tags(slug, tag_ids)
        except Exception as e:
            error_msg = f"Error setting tags on recipe '{slug}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug({"message": "Error traceback", "traceback": traceback.format_exc()})
            raise ToolError(error_msg)

    @mcp.tool()
    def update_recipe_categories_and_tags(
        slug: str,
        category_ids: Optional[List[str]] = None,
        tag_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Update categories and/or tags for a recipe in a single API call.
        Use get_categories() and get_tags() first to find valid IDs.
        Passing an empty list for either field will clear it; omitting (None) leaves it unchanged.

        Args:
            slug: The unique text identifier for the recipe.
            category_ids: List of category UUIDs to assign (omit to leave unchanged).
            tag_ids: List of tag UUIDs to assign (omit to leave unchanged).

        Returns:
            Dict[str, Any]: The updated recipe details.
        """
        try:
            logger.info({"message": "Updating recipe categories and tags", "slug": slug})
            return mealie.set_recipe_categories_and_tags(slug, category_ids=category_ids, tag_ids=tag_ids)
        except Exception as e:
            error_msg = f"Error updating categories/tags on recipe '{slug}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug({"message": "Error traceback", "traceback": traceback.format_exc()})
            raise ToolError(error_msg)

    @mcp.tool()
    def delete_recipe(slug: str) -> Dict[str, Any]:
        """Delete a recipe permanently.

        Args:
            slug: The unique text identifier for the recipe to delete.

        Returns:
            Dict[str, Any]: Confirmation of deletion.
        """
        try:
            logger.info({"message": "Deleting recipe", "slug": slug})
            return mealie.delete_recipe(slug)
        except Exception as e:
            error_msg = f"Error deleting recipe '{slug}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug({"message": "Error traceback", "traceback": traceback.format_exc()})
            raise ToolError(error_msg)
