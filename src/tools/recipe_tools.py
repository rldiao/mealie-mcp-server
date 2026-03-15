import logging
import re
import subprocess
import json
import traceback
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from mealie import MealieFetcher
from models.recipe import (
    Recipe,
    RecipeIngredient,
    RecipeInstruction,
    IngredientUnit,
    IngredientFood,
)

logger = logging.getLogger("mealie-mcp")

KNOWN_UNITS = {
    # Metric weight
    'kg', 'g', 'gram', 'grams', 'mg', 'oz', 'ounce', 'ounces', 'lb', 'lbs', 'pound', 'pounds',
    # Metric volume
    'l', 'liter', 'liters', 'litre', 'litres', 'dl', 'cl', 'ml',
    'cup', 'cups', 'fl', 'gallon', 'gallons', 'gal', 'quart', 'quarts', 'qt', 'pint', 'pints', 'pt',
    # Spoon measures (Dutch)
    'el', 'eetlepel', 'eetlepels',
    'tl', 'theelepel', 'theelepels',
    # Spoon measures (English)
    'tbsp', 'tablespoon', 'tablespoons',
    'tsp', 'teaspoon', 'teaspoons',
    # Pinch / dash
    'snuf', 'snufje', 'snufjes',
    'pinch', 'pinches', 'dash', 'dashes',
    # Piece / unit
    'stuk', 'stuks',
    'piece', 'pieces', 'whole',
    # Slice
    'plak', 'plakje', 'plakjes', 'plakken',
    'slice', 'slices',
    # Disc / round
    'schijf', 'schijfje', 'schijfjes', 'schijven',
    # Sprig / branch
    'tak', 'takje', 'takjes', 'takken',
    'sprig', 'sprigs', 'branch', 'branches',
    # Clove
    'teen', 'tenen', 'teentje', 'teentjes',
    'clove', 'cloves',
    # Can / tin
    'blik', 'blikje', 'blikjes', 'blikken',
    'can', 'cans', 'tin', 'tins',
    # Jar / pot
    'pot', 'potje', 'potjes', 'potten',
    'jar', 'jars',
    # Bag
    'zak', 'zakje', 'zakjes', 'zakken',
    'bag', 'bags',
    # Pack / package
    'pak', 'pakje', 'pakjes', 'pakken',
    'pack', 'packs', 'package', 'packages',
    # Bunch
    'bos', 'bosje', 'bosjes', 'bossen',
    'bus', 'busje', 'busjes', 'bussen',
    'bunch', 'bunches',
    # Leaf
    'blad', 'blaadje', 'blaadjes', 'bladeren',
    'leaf', 'leaves',
    # Drop
    'druppel', 'druppels',
    'drop', 'drops',
    # Handful
    'hand', 'handvol', 'handje', 'handjes',
    'handful', 'handfuls',
    # Splash
    'scheut', 'scheutje', 'scheutjes',
    'splash',
    # Knife tip
    'mespunt', 'mespuntje', 'mespuntjes',
    # Cup (Dutch)
    'kopje', 'kopjes', 'kop',
    # Ball / bulb
    'bol', 'bollen', 'bolletje', 'bolletjes',
    'bulb', 'bulbs',
    # Sheet
    'vel', 'vellen', 'velletje', 'velletjes',
    'sheet', 'sheets',
    # Ring
    'ring', 'ringen', 'ringetje', 'ringetjes',
    # Strip / bar
    'reep', 'repen', 'reepje', 'reepjes',
    'strip', 'strips',
    # Tuft
    'pluk', 'plukje', 'plukjes',
    # Stalk / stem
    'stengel', 'stengels',
    'stalk', 'stalks', 'stem', 'stems',
    # Cluster
    'tros', 'trosje', 'trosjes', 'trossen',
    # Bottle
    'fles', 'flesje', 'flesjes', 'flessen',
    'bottle', 'bottles',
    # Container / tray
    'bakje', 'bakjes',
    'container', 'containers',
    # Portion / serving
    'portie', 'porties',
    'portion', 'portions', 'serving', 'servings',
    # Wedge / point
    'punt', 'puntje', 'puntjes',
    'wedge', 'wedges',
    # Cube / block
    'blokje', 'blokjes',
    'cube', 'cubes', 'block', 'blocks',
    # Crown
    'kroontje', 'kroontjes',
    'head', 'heads',
}


def parse_ingredient(text: str) -> RecipeIngredient:
    """Parse an ingredient string like '300 g bloem' into structured data."""
    match = re.match(r'^(\d+[.,/]?\d*)\s+(.+)$', text)

    if not match:
        return RecipeIngredient(note=text, originalText=text, isFood=True)

    qty_str = match.group(1).replace(',', '.')
    if '/' in qty_str:
        num, den = qty_str.split('/')
        quantity = float(num) / float(den)
    else:
        quantity = float(qty_str)

    rest = match.group(2)
    words = rest.split()
    first_word = words[0].lower()

    if first_word in KNOWN_UNITS:
        unit = IngredientUnit(name=words[0])
        food_name = ' '.join(words[1:])
    else:
        unit = None
        food_name = rest

    food = IngredientFood(name=food_name) if food_name else None

    return RecipeIngredient(
        quantity=quantity,
        unit=unit,
        food=food,
        note=text,
        originalText=text,
        isFood=True,
    )


def fetch_ah_recipe(url: str) -> Dict[str, Any]:
    """Fetch and parse a recipe from ah.nl using JSON-LD structured data."""
    safe_url = re.sub(r'[^a-zA-Z0-9/:._\-?&=%+]', '', url)
    html = subprocess.check_output(
        [
            'curl', '-sL',
            '-H', 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            '-H', 'Accept: text/html',
            '-H', 'Accept-Language: nl-NL,nl',
            safe_url,
        ],
        encoding='utf-8',
        timeout=15,
    )

    # Extract JSON-LD blocks
    for match in re.finditer(r'<script type="application/ld\+json">(.+?)</script>', html):
        try:
            data = json.loads(match.group(1))
            if data.get('@type') == 'Recipe':
                return data
        except json.JSONDecodeError:
            continue

    raise ValueError("Geen receptdata gevonden op deze pagina")


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
        name: str,
        ingredients: List[str],
        instructions: List[str],
        description: Optional[str] = None,
        recipe_yield: Optional[str] = None,
        total_time: Optional[str] = None,
        org_url: Optional[str] = None,
        image_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new recipe with parsed ingredients (quantity, unit, food).

        Args:
            name: The name of the new recipe to be created.
            ingredients: A list of ingredients like "300 g bloem" or "2 tenen knoflook". Quantities and units are automatically parsed.
            instructions: A list of instructions for preparing the recipe.
            description: Optional description of the recipe.
            recipe_yield: Optional yield/servings (e.g. "4 porties").
            total_time: Optional total preparation time (e.g. "15 minuten").
            org_url: Optional original source URL of the recipe.
            image_url: Optional URL of an image for the recipe.

        Returns:
            Dict[str, Any]: The created recipe details.
        """
        try:
            logger.info({"message": "Creating recipe", "name": name})
            slug = mealie.create_recipe(name)
            recipe_json = mealie.get_recipe(slug)
            recipe = Recipe.model_validate(recipe_json)
            recipe.recipeIngredient = [parse_ingredient(i) for i in ingredients]
            recipe.recipeInstructions = [
                RecipeInstruction(text=i) for i in instructions
            ]
            if description is not None:
                recipe.description = description
            if recipe_yield is not None:
                recipe.recipeYield = recipe_yield
            if total_time is not None:
                recipe.totalTime = total_time
            if org_url is not None:
                recipe.orgURL = org_url
            result = mealie.update_recipe(slug, recipe.model_dump(exclude_none=True))

            if image_url:
                try:
                    mealie.scrape_recipe_image_from_url(slug, image_url)
                except Exception as img_err:
                    logger.warning({"message": "Failed to set image", "error": str(img_err)})

            return result
        except Exception as e:
            error_msg = f"Error creating recipe '{name}': {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise ToolError(error_msg)

    @mcp.tool()
    def import_recipe_from_url(url: str) -> Dict[str, Any]:
        """Import a recipe from a URL (currently supports ah.nl/allerhande).

        Fetches the recipe page, extracts structured data (JSON-LD), and creates
        the recipe in Mealie with parsed ingredients (quantity, unit, food),
        instructions, description, servings, cooking time, and image.

        Args:
            url: The URL of the recipe page (e.g. https://www.ah.nl/allerhande/recept/R-R.../...)

        Returns:
            Dict[str, Any]: The created recipe details in Mealie.
        """
        try:
            logger.info({"message": "Importing recipe from URL", "url": url})

            if not re.match(r'https?://(www\.)?ah\.nl/allerhande/recept/', url):
                raise ValueError("Alleen ah.nl/allerhande URLs worden ondersteund")

            data = fetch_ah_recipe(url)

            name = data.get('name', 'Onbekend recept')
            ingredients = data.get('recipeIngredient', [])
            raw_instructions = data.get('recipeInstructions', [])
            instructions = [
                step.get('text', '') if isinstance(step, dict) else str(step)
                for step in raw_instructions
            ]
            description = data.get('description', '')
            recipe_yield = data.get('recipeYield')
            if recipe_yield:
                recipe_yield = f"{recipe_yield} porties"
            total_time = data.get('totalTime', '')
            # Convert ISO 8601 duration to readable format
            time_match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?', total_time)
            if time_match:
                hours = f"{time_match.group(1)} uur " if time_match.group(1) else ""
                mins = f"{time_match.group(2)} minuten" if time_match.group(2) else ""
                total_time = (hours + mins).strip() or None
            else:
                total_time = None

            # Find best image
            image_url = None
            images = data.get('image', [])
            if isinstance(images, str):
                images = [images]
            for img in images:
                if img and len(img) > 0:
                    image_url = img
                    break

            # Create the recipe
            slug = mealie.create_recipe(name)
            recipe_json = mealie.get_recipe(slug)
            recipe = Recipe.model_validate(recipe_json)
            recipe.recipeIngredient = [parse_ingredient(i) for i in ingredients]
            recipe.recipeInstructions = [RecipeInstruction(text=i) for i in instructions]
            recipe.description = description
            recipe.orgURL = url
            if recipe_yield:
                recipe.recipeYield = recipe_yield
            if total_time:
                recipe.totalTime = total_time

            result = mealie.update_recipe(slug, recipe.model_dump(exclude_none=True))

            if image_url:
                try:
                    mealie.scrape_recipe_image_from_url(slug, image_url)
                except Exception as img_err:
                    logger.warning({"message": "Failed to set image", "error": str(img_err)})

            return result
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
        ingredients: List[str],
        instructions: List[str],
    ) -> Dict[str, Any]:
        """Replaces the ingredients and instructions of an existing recipe.
        Ingredients are automatically parsed into quantity, unit, and food.

        Args:
            slug: The unique text identifier for the recipe to be updated.
            ingredients: A list of ingredients like "300 g bloem". Quantities and units are automatically parsed.
            instructions: A list of instructions for preparing the recipe.

        Returns:
            Dict[str, Any]: The updated recipe details.
        """
        try:
            logger.info({"message": "Updating recipe", "slug": slug})
            recipe_json = mealie.get_recipe(slug)
            recipe = Recipe.model_validate(recipe_json)
            recipe.recipeIngredient = [parse_ingredient(i) for i in ingredients]
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
