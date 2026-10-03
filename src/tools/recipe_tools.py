import json
import math
import re
import uuid
from contextlib import contextmanager
from copy import deepcopy
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
    RecipeNutrition,
    RecipeSettingsInput,
)
from tools.errors import tool_error_boundary


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


def _normalize_references(
    ingredients: List[RecipeIngredient], instructions: List[RecipeInstruction]
) -> None:
    """Coerce every ingredient referenceId and instruction link to a UUID."""
    for ingredient in ingredients:
        if ingredient.referenceId:
            ingredient.referenceId = _coerce_reference_id(ingredient.referenceId)
    for step in instructions:
        for ref in step.ingredientReferences:
            if ref.referenceId:
                ref.referenceId = _coerce_reference_id(ref.referenceId)


def _require_text(value: str, label: str) -> None:
    if not value.strip():
        raise ValueError(f"{label} cannot be empty")


def _recipe_changes(
    *,
    ingredients: Optional[List[Union[str, RecipeIngredientInput]]] = None,
    instructions: Optional[List[Union[str, RecipeInstructionInput]]] = None,
    tags: Optional[List[OrganizerRef]] = None,
    tools: Optional[List[OrganizerRef]] = None,
    nutrition: Optional[RecipeNutrition] = None,
    settings: Optional[RecipeSettingsInput] = None,
    **fields: Any,
) -> Dict[str, Any]:
    """Validate and serialize caller content before any creation request."""
    field_names = {
        "name": "name",
        "description": "description",
        "org_url": "orgURL",
        "total_time": "totalTime",
        "prep_time": "prepTime",
        "cook_time": "cookTime",
        "perform_time": "performTime",
        "recipe_yield": "recipeYield",
        "servings": "recipeServings",
    }
    changes = {
        field_names[key]: value for key, value in fields.items() if value is not None
    }
    if "name" in changes:
        _require_text(changes["name"], "Recipe name")
    if "recipeServings" in changes and not math.isfinite(changes["recipeServings"]):
        raise ValueError("Servings must be finite")
    built_ingredients = [_build_ingredient(i) for i in ingredients or []]
    built_instructions = [_build_instruction(i) for i in instructions or []]
    _normalize_references(built_ingredients, built_instructions)
    if ingredients is not None:
        changes["recipeIngredient"] = [
            i.model_dump(exclude_none=True) for i in built_ingredients
        ]
    if instructions is not None:
        changes["recipeInstructions"] = [
            i.model_dump(exclude_none=True) for i in built_instructions
        ]
    if tags is not None:
        changes["tags"] = [_organizer_payload(t) for t in tags]
    if tools is not None:
        changes["tools"] = [_organizer_payload(t) for t in tools]
    if nutrition is not None:
        changes["nutrition"] = nutrition.model_dump(exclude_none=True)
    if settings is not None:
        changes["settings"] = settings.model_dump(exclude_none=True)
    return changes


def _compose_recipe(
    current: Dict[str, Any], changes: Dict[str, Any]
) -> Dict[str, Any]:
    """Preserve fetched fields, replacing content but merging settings toggles."""
    recipe = deepcopy(current)
    recipe.setdefault("nutrition", {})
    recipe.update(deepcopy(changes))
    if "settings" in changes:
        recipe["settings"] = {
            **deepcopy(current.get("settings") or {}),
            **changes["settings"],
        }
    return recipe


@contextmanager
def _created_recipe_stage(slug: str, stage: str):
    """Expose recovery information only to the caller, never to logs."""
    try:
        with tool_error_boundary("Error completing created recipe"):
            yield
    except ToolError:
        raise ToolError(
            json.dumps(
                {
                    "message": (
                        "Recipe was created; inspect it and resume using its slug "
                        "instead of creating it again."
                    ),
                    "created_slug": slug,
                    "stage": stage,
                }
            )
        ) from None


def _create_populated_recipe(
    mealie: MealieFetcher,
    name: str,
    changes: Dict[str, Any],
    image_url: Optional[str] = None,
) -> Dict[str, Any]:
    _require_text(name, "Recipe name")
    if image_url is not None:
        _require_text(image_url, "Image URL")
    slug = mealie.create_recipe(name)
    with _created_recipe_stage(slug, "fetch"):
        current = mealie.get_recipe(slug)
    with _created_recipe_stage(slug, "populate"):
        updated = mealie.update_recipe(slug, _compose_recipe(current, changes))
    if image_url is not None:
        with _created_recipe_stage(slug, "image"):
            mealie.scrape_recipe_image_from_url(slug, image_url)
        with _created_recipe_stage(slug, "fetch_image"):
            updated = mealie.get_recipe(slug)
    return updated


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
        with tool_error_boundary("Error fetching recipes"):
            return mealie.get_recipes(
                search=search,
                page=page,
                per_page=per_page,
                categories=categories,
                tags=tags,
                require_all_tags=require_all_tags,
                require_all_categories=require_all_categories,
            )

    @mcp.tool()
    def get_recipe(slug: str, concise: bool = False) -> Dict[str, Any]:
        """Retrieve a recipe, optionally returning only a concise summary.

        Args:
            slug: The unique text identifier for the recipe, typically found in recipe URLs
                or from get_recipes results.
            concise: Return essential fields for meal planning instead of full
                ingredients, instructions, nutrition, notes, and metadata.

        Returns:
            Dict[str, Any]: Full recipe details by default, or a concise summary.
        """
        with tool_error_boundary("Error fetching recipe"):
            recipe_json = mealie.get_recipe(slug)
            if not concise:
                return recipe_json
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

    @mcp.tool()
    def import_recipe_from_url(
        url: str, include_tags: bool = False
    ) -> Dict[str, Any]:
        """Import a recipe into Mealie by scraping a URL.

        Prefer this for ordinary recipe webpages.

        Uses Mealie's server-side scraper (the `recipe-scrapers` library), which
        has built-in adapters for many recipe sites and falls back to
        JSON-LD/Schema.org parsing for sites without a dedicated adapter.
        Mealie may fall back to AI when configured. Coverage varies by Mealie
        version; URLs Mealie cannot parse return an error.

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

        If fetching the imported recipe fails, the error includes created_slug
        and stage so the recipe can be retrieved without importing it again.
        """
        with tool_error_boundary("Error importing recipe from URL"):
            slug = mealie.import_recipe_from_url(url, include_tags=include_tags)
            with _created_recipe_stage(slug, "fetch"):
                return mealie.get_recipe(slug)

    @mcp.tool()
    def create_recipe(
        name: str,
        description: Optional[str] = None,
        org_url: Optional[str] = None,
        total_time: Optional[str] = None,
        prep_time: Optional[str] = None,
        cook_time: Optional[str] = None,
        perform_time: Optional[str] = None,
        recipe_yield: Optional[str] = None,
        servings: Optional[float] = None,
        image_url: Optional[str] = None,
        ingredients: Optional[List[Union[str, RecipeIngredientInput]]] = None,
        instructions: Optional[List[Union[str, RecipeInstructionInput]]] = None,
        tags: Optional[List[OrganizerRef]] = None,
        tools: Optional[List[OrganizerRef]] = None,
        nutrition: Optional[RecipeNutrition] = None,
        settings: Optional[RecipeSettingsInput] = None,
    ) -> Dict[str, Any]:
        """Create a recipe and populate all of its content in one call.

        Use when the recipe is already composed into ingredients and instructions.
        Only name is required. Provide ingredients and instructions for a basic
        recipe, or include metadata, nutrition, and display settings for a
        complete recipe. Omitted or null fields keep Mealie's defaults; empty
        lists clear those fields. An image_url is scraped after content is saved.

        Ingredients and instructions each accept either a plain string or a
        structured object:

        - An ingredient string (e.g. "200 g basmati rice") is resolved by
          Mealie's natural-language parser into quantity/unit/food.
        - An ingredient object can set quantity, note, title, an existing
          Mealie unit/food (by id and name), and a referenceId for step links.
        - An instruction string is the step text; an instruction object can
          also carry a summary (heading shown in place of "Step N"), a title
          (section banner above the step), and ingredientReferences for
          cook-mode highlights.

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
            nutrition: Per-serving nutrition values (calories in kcal, sodium and
                cholesterol in mg, the rest in grams). Omitted keys stay empty.
            settings: Display toggles to override on the new recipe. Only the
                toggles you pass are changed; the rest keep the defaults Mealie
                seeds from the household preferences. Set showAssets here when
                you know you are about to attach a file.

        Returns:
            Dict[str, Any]: The created recipe details.

        If a later API step fails, the error includes created_slug and stage.
        Inspect that recipe and resume the failed step instead of creating again.
        """
        with tool_error_boundary("Error creating recipe"):
            changes = _recipe_changes(
                description=description,
                org_url=org_url,
                total_time=total_time,
                prep_time=prep_time,
                cook_time=cook_time,
                perform_time=perform_time,
                recipe_yield=recipe_yield,
                servings=servings,
                ingredients=ingredients,
                instructions=instructions,
                tags=tags,
                tools=tools,
                nutrition=nutrition,
                settings=settings,
            )
            return _create_populated_recipe(mealie, name, changes, image_url)

    @mcp.tool()
    def update_recipe(
        slug: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        recipe_yield: Optional[str] = None,
        servings: Optional[float] = None,
        total_time: Optional[str] = None,
        prep_time: Optional[str] = None,
        cook_time: Optional[str] = None,
        perform_time: Optional[str] = None,
        org_url: Optional[str] = None,
        tags: Optional[List[OrganizerRef]] = None,
        tools: Optional[List[OrganizerRef]] = None,
        nutrition: Optional[RecipeNutrition] = None,
        settings: Optional[RecipeSettingsInput] = None,
        ingredients: Optional[List[Union[str, RecipeIngredientInput]]] = None,
        instructions: Optional[List[Union[str, RecipeInstructionInput]]] = None,
    ) -> Dict[str, Any]:
        """Partially update a recipe (only updates provided fields).

        Omitted or null fields are unchanged. Provided ingredient/instruction
        lists replace those fields; empty lists clear them. Content changes use
        a read-merge-write to preserve other recipe fields; metadata-only changes
        use PATCH.

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
            nutrition: Per-serving nutrition values (calories in kcal, sodium and
                cholesterol in mg, the rest in grams). Mealie replaces the whole
                nutrition object, so pass every value you want to keep — omitted
                keys are cleared, not preserved.
            settings: Display toggles to change, e.g. showAssets to make an
                uploaded asset visible in the UI, or showNutrition to reveal
                stored nutrition. Only the toggles you pass are changed: the
                current settings are read first and merged, because Mealie does
                not reliably preserve toggles left out of a settings PATCH.
            ingredients: Ingredient strings and/or structured objects, as in
                create_recipe. Replaces the ingredient list when provided.
            instructions: Step strings and/or structured objects, as in
                create_recipe. Replaces the instruction list when provided.

        Returns:
            Dict[str, Any]: The updated recipe details.
        """
        with tool_error_boundary("Error updating recipe"):
            recipe_data = _recipe_changes(
                name=name,
                description=description,
                recipe_yield=recipe_yield,
                servings=servings,
                total_time=total_time,
                prep_time=prep_time,
                cook_time=cook_time,
                perform_time=perform_time,
                org_url=org_url,
                tags=tags,
                tools=tools,
                nutrition=nutrition,
                settings=settings,
                ingredients=ingredients,
                instructions=instructions,
            )
            if not recipe_data:
                raise ValueError("At least one field must be provided to update")
            if ingredients is not None or instructions is not None:
                current = mealie.get_recipe(slug)
                return mealie.update_recipe(
                    slug, _compose_recipe(current, recipe_data)
                )
            if settings is not None:
                # Mealie drops some toggles omitted from a settings PATCH, so
                # send the complete object built from the recipe's current one
                current = mealie.get_recipe(slug).get("settings") or {}
                recipe_data["settings"] = {
                    **current,
                    **settings.model_dump(exclude_none=True),
                }

            return mealie.patch_recipe(slug, recipe_data)

    @mcp.tool()
    def duplicate_recipe(slug: str, name: Optional[str] = None) -> Dict[str, Any]:
        """Duplicate an existing recipe, creating a copy with a new slug.

        Args:
            slug: The unique text identifier for the recipe to duplicate.
            name: Optional new name for the duplicate (if not provided, uses original name with copy indicator).

        Returns:
            Dict[str, Any]: The newly created duplicate recipe details.
        """
        with tool_error_boundary("Error duplicating recipe"):
            return mealie.duplicate_recipe(slug, name)

    @mcp.tool()
    def mark_recipe_last_made(slug: str) -> Dict[str, Any]:
        """Mark a recipe as having been made today (updates last made timestamp).

        Args:
            slug: The unique text identifier for the recipe.

        Returns:
            Dict[str, Any]: The updated recipe details.
        """
        with tool_error_boundary("Error updating recipe last made"):
            return mealie.update_recipe_last_made(slug)

    @mcp.tool()
    def set_recipe_image_from_url(slug: str, image_url: str) -> Dict[str, Any]:
        """Set a recipe's image by scraping it from a URL.

        Args:
            slug: The unique text identifier for the recipe.
            image_url: URL of the image to scrape and use as the recipe image.

        Returns:
            Dict[str, Any]: Confirmation that the image was set.
        """
        with tool_error_boundary("Error setting recipe image from URL"):
            return mealie.scrape_recipe_image_from_url(slug, image_url)

    @mcp.tool()
    def upload_recipe_image_file(
        slug: str, image_path: str, extension: Optional[str] = None
    ) -> Dict[str, Any]:
        """Upload an image file for a recipe.

        Attach a photo to an existing recipe; this does not extract recipe text
        from the image or create a new recipe.
        Args:
            slug: The unique text identifier for the recipe.
            image_path: Local file path to the image to upload.
            extension: Image extension such as "jpg". Derived from image_path when omitted.

        Returns:
            Dict[str, Any]: Confirmation that the image was uploaded.
        """
        with tool_error_boundary("Error uploading recipe image"):
            import os

            if not os.path.exists(image_path):
                raise ValueError("Image file not found")

            with open(image_path, "rb") as f:
                image_data = f.read()

            filename = os.path.basename(image_path)
            return mealie.upload_recipe_image(slug, image_data, filename, extension)

    @mcp.tool()
    def upload_recipe_asset_file(
        slug: str,
        asset_path: str,
        name: Optional[str] = None,
        icon: Optional[str] = None,
        extension: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Upload an asset file (document, PDF, etc.) for a recipe.

        Args:
            slug: The unique text identifier for the recipe.
            asset_path: Local file path to the asset to upload.
            name: Display name for the asset. Derived from the file name when omitted.
            icon: Material Design icon name, for example "mdi-file-pdf-box".
            extension: Asset extension such as "pdf". Derived from asset_path when omitted.

        Returns:
            Dict[str, Any]: Details of the uploaded asset.
        """
        with tool_error_boundary("Error uploading recipe asset"):
            import os

            if not os.path.exists(asset_path):
                raise ValueError("Asset file not found")

            with open(asset_path, "rb") as f:
                asset_data = f.read()

            filename = os.path.basename(asset_path)
            return mealie.upload_recipe_asset(
                slug, asset_data, filename, name=name, icon=icon, extension=extension
            )

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
        with tool_error_boundary("Error updating recipe categories and tags"):
            return mealie.set_recipe_categories_and_tags(slug, category_ids=category_ids, tag_ids=tag_ids)

    @mcp.tool()
    def delete_recipe(slug: str) -> Dict[str, Any]:
        """Delete a recipe permanently.

        Args:
            slug: The unique text identifier for the recipe to delete.

        Returns:
            Dict[str, Any]: Confirmation of deletion.
        """
        with tool_error_boundary("Error deleting recipe"):
            return mealie.delete_recipe(slug)
