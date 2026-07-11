from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class IngredientUnit(BaseModel):
    id: Optional[str] = None
    name: str
    pluralName: Optional[str] = None
    description: str = ""
    extras: Optional[Dict[str, Any]] = None
    fraction: bool = True
    abbreviation: str = ""
    pluralAbbreviation: Optional[str] = ""
    useAbbreviation: bool = False
    aliases: List[Any] = Field(default_factory=list)
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None


class IngredientFood(BaseModel):
    id: Optional[str] = None
    name: str
    pluralName: Optional[str] = None
    description: str = ""
    extras: Optional[Dict[str, Any]] = None
    labelId: Optional[str] = None
    label: Optional[Any] = None
    aliases: List[Any] = Field(default_factory=list)
    householdsWithIngredientFood: List[str] = Field(default_factory=list)
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None


class RecipeIngredient(BaseModel):
    quantity: Optional[float] = None
    unit: Optional[IngredientUnit] = None
    food: Optional[IngredientFood] = None
    note: Optional[str] = None
    isFood: Optional[bool] = True
    disableAmount: Optional[bool] = False
    display: Optional[str] = None
    title: Optional[str] = None
    originalText: Optional[str] = None
    referenceId: Optional[str] = None


class IngredientReference(BaseModel):
    referenceId: Optional[str] = None


class RecipeInstruction(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    text: str
    ingredientReferences: List[IngredientReference] = Field(default_factory=list)


class RecipeNutrition(BaseModel):
    calories: Optional[str] = None
    carbohydrateContent: Optional[str] = None
    cholesterolContent: Optional[str] = None
    fatContent: Optional[str] = None
    fiberContent: Optional[str] = None
    proteinContent: Optional[str] = None
    saturatedFatContent: Optional[str] = None
    sodiumContent: Optional[str] = None
    sugarContent: Optional[str] = None
    transFatContent: Optional[str] = None
    unsaturatedFatContent: Optional[str] = None


class RecipeSettings(BaseModel):
    public: bool = False
    showNutrition: bool = False
    showAssets: bool = False
    landscapeView: bool = False
    disableComments: bool = False
    disableAmount: bool = False
    locked: bool = False


class RecipeCategory(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    slug: Optional[str] = None


class RecipeTag(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    slug: Optional[str] = None


class RecipeTool(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    slug: Optional[str] = None
    householdsWithTool: List[str] = Field(default_factory=list)


class Recipe(BaseModel):
    id: str
    userId: str
    householdId: str
    groupId: str
    name: str
    slug: str
    image: Optional[str] = None
    recipeServings: Optional[int] = None
    recipeYieldQuantity: Optional[int] = 0
    recipeYield: Optional[str] = None
    totalTime: Optional[str] = None
    prepTime: Optional[str] = None
    cookTime: Optional[str] = None
    performTime: Optional[str] = None
    description: Optional[str] = None
    recipeCategory: List[RecipeCategory] = Field(default_factory=list)
    tags: List[RecipeTag] = Field(default_factory=list)
    tools: List[RecipeTool] = Field(default_factory=list)
    rating: Optional[float] = None
    orgURL: Optional[str] = None
    dateAdded: str
    dateUpdated: str
    createdAt: str
    updatedAt: str
    lastMade: Optional[str] = None
    recipeIngredient: List[RecipeIngredient] = Field(default_factory=list)
    recipeInstructions: List[RecipeInstruction] = Field(default_factory=list)
    nutrition: RecipeNutrition = Field(default_factory=RecipeNutrition)
    settings: RecipeSettings = Field(default_factory=RecipeSettings)
    assets: List[Any] = Field(default_factory=list)
    notes: List[Any] = Field(default_factory=list)
    extras: Dict[str, Any] = Field(default_factory=dict)
    comments: List[Any] = Field(default_factory=list)


class RecipeIngredientInput(BaseModel):
    """Structured ingredient accepted by the create/update recipe tools.

    Pass a plain string instead of this object to let Mealie's
    natural-language parser resolve the quantity, unit, and food.
    """

    referenceId: Optional[str] = Field(
        default=None,
        description=(
            "Id used to link instruction steps to this ingredient. Mealie stores "
            "it as a UUID v4; any string is accepted and non-v4 values are "
            "converted to a stable UUID v4 server-side. Reuse the same value on "
            "the step's ingredientReferences to keep the link."
        ),
    )
    quantity: Optional[float] = Field(
        default=None, description="Numeric amount, e.g. 200."
    )
    unit: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Existing Mealie unit object. Mealie requires both the id and the "
            'name, e.g. {"id": "<uuid>", "name": "gram"}.'
        ),
    )
    food: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Existing Mealie food object. Mealie requires both the id and the "
            'name, e.g. {"id": "<uuid>", "name": "rice"}.'
        ),
    )
    note: Optional[str] = Field(
        default=None,
        description='Free-text qualifier shown after the food, e.g. "Basmati".',
    )
    title: Optional[str] = Field(
        default=None, description="Section heading rendered above this ingredient."
    )


class RecipeInstructionInput(BaseModel):
    """Structured preparation step accepted by the create/update recipe tools.

    Pass a plain string instead of this object for a step that has no title
    and no ingredient links.
    """

    text: str = Field(description="The instruction text for this step.")
    title: Optional[str] = Field(
        default=None, description="Optional heading for this step or section."
    )
    ingredientReferences: Optional[List[IngredientReference]] = Field(
        default=None,
        description=(
            "referenceIds of the ingredients used in this step; must match the "
            "referenceId set on those ingredients (Mealie requires UUID v4 here; "
            "non-v4 values are converted to a stable UUID v4 server-side). "
            "Enables Mealie's cook-mode highlighting."
        ),
    )


class OrganizerRef(BaseModel):
    """Reference to an existing Mealie tag, category, or tool.

    Look up ids with get_tags / get_categories / get_tools. Mealie requires
    both the id and the name.
    """

    id: str = Field(description="UUID of the existing organizer.")
    name: str = Field(description="Display name of the existing organizer.")
    slug: Optional[str] = Field(
        default=None, description="Optional slug; Mealie derives it when omitted."
    )
