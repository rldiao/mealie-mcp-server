import logging
import re
import traceback
import uuid
from typing import Any, Dict, List, Optional, Union

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from mealie import MealieFetcher
from models.recipe import (
    OrganizerRef,
    Recipe,
    RecipeIngredient,
    RecipeIngredientInput,
    RecipeInstruction,
    RecipeInstructionInput,
    RecipeTag,
    RecipeTool,
)

logger = logging.getLogger("mealie-mcp")


def _build_ingredient(
    ingredient: Union[str, RecipeIngredientInput, Dict[str, Any]],
) -> RecipeIngredient:
    """Coerce a flat string or structured ingredient into a RecipeIngredient.

    A plain string becomes a note for Mealie's natural-language parser to
    resolve; a structured object maps its fields straight onto the Mealie
    RecipeIngredient model.
    """
    if isinstance(ingredient, str):
        return RecipeIngredient(note=ingredient)
    if isinstance(ingredient, RecipeIngredientInput):
        ingredient = ingredient.model_dump(exclude_none=True)
    return RecipeIngredient(**ingredient)


def _build_instruction(
    instruction: Union[str, RecipeInstructionInput, Dict[str, Any]],
) -> RecipeInstruction:
    """Coerce a flat string or structured step into a RecipeInstruction."""
    if isinstance(instruction, str):
        return RecipeInstruction(text=instruction)
    if isinstance(instruction, RecipeInstructionInput):
        instruction = instruction.model_dump(exclude_none=True)
    return RecipeInstruction(**instruction)


_REF_NAMESPACE = uuid.uuid5(
    uuid.NAMESPACE_URL, "mealie-mcp/recipe-ingredient-reference"
)


def _slugify(name: str) -> str:
    """Best-effort Mealie-style slug, used to fill an omitted organizer slug."""
    slug = name.strip().lower()
    for umlaut, ascii_ in (("ä", "a"), ("ö", "o"), ("ü", "u"), ("ß", "ss")):
        slug = slug.replace(umlaut, ascii_)
    return re.sub(r"[^a-z0-9]+", "-", slug).strip("-")


def _organizer_payload(org: OrganizerRef) -> Dict[str, Any]:
    """Map an OrganizerRef to the {id, name, slug} Mealie requires for tags/tools.

    Mealie requires a slug on every tag/tool reference; derive one from the name
    when the caller omits it (Mealie links the organizer by its id, so the exact
    slug only needs to be present).
    """
    return {"id": org.id, "name": org.name, "slug": org.slug or _slugify(org.name)}


def _coerce_reference_id(value: Optional[str]) -> Optional[str]:
    """Return a UUID v4 string for an ingredient referenceId.

    Mealie validates instruction ingredientReferences as UUID **v4**. An
    existing v4 UUID passes through unchanged; anything else (a non-UUID, or a
    UUID of another version) is mapped to a stable v4 UUID derived from it — a
    uuid5 hash with the version/variant bits forced to 4/RFC-4122. It is
    deterministic, so the same caller-supplied id used on an ingredient and on
    an instruction step resolves to the same v4 UUID and keeps the link intact.
    """
    if not value:
        return value
    try:
        existing = uuid.UUID(str(value))
        if existing.version == 4:
            return str(existing)
    except (ValueError, AttributeError, TypeError):
        pass
    return str(uuid.UUID(int=uuid.uuid5(_REF_NAMESPACE, str(value)).int, version=4))


def _normalize_references(recipe: Recipe) -> None:
    """Coerce every ingredient referenceId and instruction link to a UUID."""
    for ingredient in recipe.recipeIngredient:
        if ingredient.referenceId:
            ingredient.referenceId = _coerce_reference_id(ingredient.referenceId)
    for step in recipe.recipeInstructions:
        for ref in step.ingredientReferences:
            if ref.referenceId:
                ref.referenceId = _coerce_reference_id(ref.referenceId)


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
                    "orgURL",
                    "tags",
                    "tools",
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
        name: str,
        ingredients: List[Union[str, RecipeIngredientInput]],
        instructions: List[Union[str, RecipeInstructionInput]],
    ) -> Dict[str, Any]:
        """Create a new recipe.

        Ingredients and instructions each accept either a plain string or a
        structured object:

        - An ingredient string (e.g. "200 g basmati rice") is resolved by
          Mealie's natural-language parser into quantity/unit/food.
        - An ingredient object can set quantity, note, title, an existing
          Mealie unit/food (by id and name), and a referenceId for step links.
        - An instruction string is the step text; an instruction object can
          also carry a title and ingredientReferences for cook-mode highlights.

        Args:
            name: The name of the new recipe to be created.
            ingredients: Ingredient strings and/or structured ingredient objects.
            instructions: Instruction strings and/or structured instruction objects.

        Returns:
            Dict[str, Any]: The created recipe details.
        """
        try:
            logger.info({"message": "Creating recipe", "name": name})
            slug = mealie.create_recipe(name)
            recipe_json = mealie.get_recipe(slug)
            recipe = Recipe.model_validate(recipe_json)
            recipe.recipeIngredient = [_build_ingredient(i) for i in ingredients]
            recipe.recipeInstructions = [_build_instruction(i) for i in instructions]
            _normalize_references(recipe)
            return mealie.update_recipe(slug, recipe.model_dump(exclude_none=True))
        except Exception as e:
            error_msg = f"Error creating recipe '{name}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise ToolError(error_msg)

    @mcp.tool()
    def import_recipe_from_url(
        url: str, include_tags: bool = False
    ) -> Dict[str, Any]:
        """Import a recipe into Mealie by scraping a URL.

        Uses Mealie's server-side scraper (the `recipe-scrapers` library), which
        has built-in adapters for many recipe sites and falls back to
        JSON-LD/Schema.org parsing for sites without a dedicated adapter.
        Coverage varies by Mealie version; URLs the scraper can't parse return
        a 400 from Mealie.

        The created recipe is fetched and returned so the caller can verify the
        scrape result. Some sources (notably paywalled URLs that redirect) can
        cause the scraper to land on the wrong page and silently return the
        wrong recipe — always confirm the returned `name` matches what was
        requested.

        Args:
            url: Source URL of the recipe to import.
            include_tags: If True, import tags Mealie extracts from the source.
                Defaults to False.

        Returns:
            Dict[str, Any]: The created recipe, including slug, name,
            ingredients, and instructions.
        """
        try:
            logger.info({"message": "Importing recipe from URL", "url": url})
            slug = mealie.import_recipe_from_url(url, include_tags=include_tags)
            return mealie.get_recipe(slug)
        except Exception as e:
            error_msg = f"Error importing recipe from URL '{url}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise ToolError(error_msg)

    @mcp.tool()
    def update_recipe(
        slug: str,
        ingredients: List[Union[str, RecipeIngredientInput]],
        instructions: List[Union[str, RecipeInstructionInput]],
    ) -> Dict[str, Any]:
        """Replaces the ingredients and instructions of an existing recipe.

        Ingredients and instructions accept the same flat-string or structured
        forms as create_recipe.

        Args:
            slug: The unique text identifier for the recipe to be updated.
            ingredients: Ingredient strings and/or structured ingredient objects.
            instructions: Instruction strings and/or structured instruction objects.

        Returns:
            Dict[str, Any]: The updated recipe details.
        """
        try:
            logger.info({"message": "Updating recipe", "slug": slug})
            recipe_json = mealie.get_recipe(slug)
            recipe = Recipe.model_validate(recipe_json)
            recipe.recipeIngredient = [_build_ingredient(i) for i in ingredients]
            recipe.recipeInstructions = [_build_instruction(i) for i in instructions]
            _normalize_references(recipe)
            return mealie.update_recipe(slug, recipe.model_dump(exclude_none=True))
        except Exception as e:
            error_msg = f"Error updating recipe '{slug}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise ToolError(error_msg)

    @mcp.tool()
    def create_recipe_full(
        name: str,
        description: Optional[str] = None,
        org_url: Optional[str] = None,
        total_time: Optional[str] = None,
        prep_time: Optional[str] = None,
        cook_time: Optional[str] = None,
        perform_time: Optional[str] = None,
        recipe_yield: Optional[str] = None,
        servings: Optional[int] = None,
        image_url: Optional[str] = None,
        ingredients: Optional[List[Union[str, RecipeIngredientInput]]] = None,
        instructions: Optional[List[Union[str, RecipeInstructionInput]]] = None,
        tags: Optional[List[OrganizerRef]] = None,
        tools: Optional[List[OrganizerRef]] = None,
    ) -> Dict[str, Any]:
        """Create a recipe and populate all of its content in one call.

        Use this instead of create_recipe when you already have complete
        recipe data (description, timing, servings, source URL, ingredients,
        steps, and optionally an image URL). It creates the recipe, fills in
        every provided field, and sets the image by scraping image_url when
        given.

        Ingredients and instructions accept the same flat-string or structured
        forms as create_recipe.

        Args:
            name: The name of the new recipe.
            description: Recipe description.
            org_url: Source URL for the recipe (shown as a link in the Mealie UI).
            total_time: Total time as free text, e.g. "35 min" or ISO-8601 "PT35M".
            prep_time: Preparation time, same format as total_time.
            cook_time: Cooking time, same format as total_time.
            perform_time: Hands-on/active time, same format as total_time.
            recipe_yield: Yield as free text, e.g. "4 Portionen".
            servings: Number of servings (numeric).
            image_url: URL of an image to scrape and set as the recipe image.
            ingredients: Ingredient strings and/or structured ingredient objects.
            instructions: Instruction strings and/or structured instruction objects.
            tags: Existing Mealie tags (id+name) to assign; look up with get_tags.
            tools: Existing Mealie tools (id+name) to assign; look up with get_tools.

        Returns:
            Dict[str, Any]: The created recipe details.
        """
        try:
            logger.info({"message": "Creating full recipe", "name": name})
            slug = mealie.create_recipe(name)
            recipe_json = mealie.get_recipe(slug)
            recipe = Recipe.model_validate(recipe_json)

            if description is not None:
                recipe.description = description
            if org_url is not None:
                recipe.orgURL = org_url
            if total_time is not None:
                recipe.totalTime = total_time
            if prep_time is not None:
                recipe.prepTime = prep_time
            if cook_time is not None:
                recipe.cookTime = cook_time
            if perform_time is not None:
                recipe.performTime = perform_time
            if recipe_yield is not None:
                recipe.recipeYield = recipe_yield
            if servings is not None:
                recipe.recipeServings = servings
            if ingredients is not None:
                recipe.recipeIngredient = [_build_ingredient(i) for i in ingredients]
            if instructions is not None:
                recipe.recipeInstructions = [
                    _build_instruction(i) for i in instructions
                ]
            if tags is not None:
                recipe.tags = [RecipeTag(**_organizer_payload(t)) for t in tags]
            if tools is not None:
                recipe.tools = [RecipeTool(**_organizer_payload(t)) for t in tools]
            _normalize_references(recipe)

            updated = mealie.update_recipe(slug, recipe.model_dump(exclude_none=True))

            if image_url is not None:
                mealie.scrape_recipe_image_from_url(slug, image_url)
                updated = mealie.get_recipe(slug)

            return updated
        except Exception as e:
            error_msg = f"Error creating full recipe '{name}': {str(e)}"
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
        servings: Optional[int] = None,
        total_time: Optional[str] = None,
        prep_time: Optional[str] = None,
        cook_time: Optional[str] = None,
        perform_time: Optional[str] = None,
        org_url: Optional[str] = None,
        tags: Optional[List[OrganizerRef]] = None,
        tools: Optional[List[OrganizerRef]] = None,
    ) -> Dict[str, Any]:
        """Partially update a recipe (only updates provided fields).

        Args:
            slug: The unique text identifier for the recipe to be updated.
            name: New name for the recipe.
            description: New description for the recipe.
            recipe_yield: Yield as free text, e.g. "4 Portionen".
            servings: Number of servings (numeric).
            total_time: Total time as free text, e.g. "35 min" or ISO-8601 "PT35M".
            prep_time: Preparation time, same format as total_time.
            cook_time: Cooking time, same format as total_time.
            perform_time: Hands-on/active time, same format as total_time.
            org_url: Source URL for the recipe (shown as a link in the Mealie UI).
            tags: Existing Mealie tags (id+name) to set; look up with get_tags.
            tools: Existing Mealie tools (id+name) to set; look up with get_tools.

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
            if servings is not None:
                recipe_data["recipeServings"] = servings
            if total_time is not None:
                recipe_data["totalTime"] = total_time
            if prep_time is not None:
                recipe_data["prepTime"] = prep_time
            if cook_time is not None:
                recipe_data["cookTime"] = cook_time
            if perform_time is not None:
                recipe_data["performTime"] = perform_time
            if org_url is not None:
                recipe_data["orgURL"] = org_url
            if tags is not None:
                recipe_data["tags"] = [_organizer_payload(t) for t in tags]
            if tools is not None:
                recipe_data["tools"] = [_organizer_payload(t) for t in tools]

            if not recipe_data:
                raise ValueError("At least one field must be provided to update")

            return mealie.patch_recipe(slug, recipe_data)
        except Exception as e:
            error_msg = f"Error patching recipe '{slug}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
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
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
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
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
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
            logger.info(
                {
                    "message": "Setting recipe image from URL",
                    "slug": slug,
                    "url": image_url,
                }
            )
            return mealie.scrape_recipe_image_from_url(slug, image_url)
        except Exception as e:
            error_msg = f"Error setting recipe image from URL '{slug}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
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

            logger.info(
                {"message": "Uploading recipe image", "slug": slug, "path": image_path}
            )

            if not os.path.exists(image_path):
                raise ValueError(f"Image file not found: {image_path}")

            with open(image_path, "rb") as f:
                image_data = f.read()

            filename = os.path.basename(image_path)
            return mealie.upload_recipe_image(slug, image_data, filename)
        except Exception as e:
            error_msg = f"Error uploading recipe image '{slug}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
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

            logger.info(
                {"message": "Uploading recipe asset", "slug": slug, "path": asset_path}
            )

            if not os.path.exists(asset_path):
                raise ValueError(f"Asset file not found: {asset_path}")

            with open(asset_path, "rb") as f:
                asset_data = f.read()

            filename = os.path.basename(asset_path)
            return mealie.upload_recipe_asset(slug, asset_data, filename)
        except Exception as e:
            error_msg = f"Error uploading recipe asset '{slug}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
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
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise ToolError(error_msg)
