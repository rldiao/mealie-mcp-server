from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class MealieResponseModel(BaseModel):
    """Model for data read back from Mealie.

    Unknown fields are kept so a fetch-modify-PUT round-trip never drops data
    from newer Mealie versions.
    """

    model_config = ConfigDict(extra="allow")


class IngredientUnit(MealieResponseModel):
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


class IngredientFood(MealieResponseModel):
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


class RecipeIngredient(MealieResponseModel):
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
    substitutions: Optional[List[Dict[str, Any]]] = None
    referencedRecipe: Optional[Dict[str, Any]] = None


class IngredientReference(MealieResponseModel):
    referenceId: Optional[str] = None


class RecipeInstruction(MealieResponseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    text: str
    ingredientReferences: List[IngredientReference] = Field(default_factory=list)


class RecipeNutrition(MealieResponseModel):
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


class RecipeSettings(MealieResponseModel):
    public: bool = False
    showNutrition: bool = False
    showAssets: bool = False
    landscapeView: bool = False
    disableComments: bool = False
    disableAmount: bool = False
    locked: bool = False


class RecipeCategory(MealieResponseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    slug: Optional[str] = None


class RecipeTag(MealieResponseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    slug: Optional[str] = None


class RecipeTool(MealieResponseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    slug: Optional[str] = None
    householdsWithTool: List[str] = Field(default_factory=list)


class Recipe(MealieResponseModel):
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


class RecipeIngredientSubstitutionInput(BaseModel):
    """One "may be replaced by" option for a recipe ingredient.

    Set a substitute food, a note, or both, e.g. a food plus "use half".
    """

    substituteFoodId: Optional[str] = Field(
        default=None,
        description="UUID of an existing Mealie food to substitute; look up with get_foods.",
    )
    note: Optional[str] = Field(
        default=None,
        description='Free-text substitute or caveat, e.g. "milk with lemon juice".',
    )

    @field_validator("note")
    @classmethod
    def _blank_note_to_none(cls, value: Optional[str]) -> Optional[str]:
        return (value.strip() or None) if isinstance(value, str) else value

    @model_validator(mode="after")
    def _require_food_or_note(self) -> "RecipeIngredientSubstitutionInput":
        if not self.substituteFoodId and not self.note:
            raise ValueError("a substitution needs a substituteFoodId, a note, or both")
        return self


NUTRITION_FIELDS = (
    "calories",
    "proteinContent",
    "carbohydrateContent",
    "fatContent",
    "saturatedFatContent",
    "unsaturatedFatContent",
    "transFatContent",
    "fiberContent",
    "sugarContent",
    "sodiumContent",
    "cholesterolContent",
)


class RecipeNutritionInput(BaseModel):
    """Per-serving macros and nutrients for a recipe.

    Give numbers without units; Mealie labels them when displaying
    (calories as kcal, sodium and cholesterol in mg, the rest in g).
    Fields left out keep their current value; null clears one.
    """

    model_config = ConfigDict(extra="forbid")

    calories: Optional[Union[str, float]] = Field(default=None, description="Energy, e.g. 450.")
    proteinContent: Optional[Union[str, float]] = Field(default=None, description="Protein in g.")
    carbohydrateContent: Optional[Union[str, float]] = Field(default=None, description="Carbohydrate in g.")
    fatContent: Optional[Union[str, float]] = Field(default=None, description="Total fat in g.")
    saturatedFatContent: Optional[Union[str, float]] = Field(default=None, description="Saturated fat in g.")
    unsaturatedFatContent: Optional[Union[str, float]] = Field(default=None, description="Unsaturated fat in g.")
    transFatContent: Optional[Union[str, float]] = Field(default=None, description="Trans fat in g.")
    fiberContent: Optional[Union[str, float]] = Field(default=None, description="Fibre in g.")
    sugarContent: Optional[Union[str, float]] = Field(default=None, description="Sugar in g.")
    sodiumContent: Optional[Union[str, float]] = Field(default=None, description="Sodium in mg.")
    cholesterolContent: Optional[Union[str, float]] = Field(default=None, description="Cholesterol in mg.")

    @field_validator(*NUTRITION_FIELDS)
    @classmethod
    def _to_mealie_string(cls, value: Optional[Union[str, float]]) -> Optional[str]:
        """Mealie stores nutrition values as strings; 32.0 becomes "32"."""
        if value is None:
            return None
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return format(value, "g")
        return value.strip() or None

    @model_validator(mode="after")
    def _require_a_field(self) -> "RecipeNutritionInput":
        if not self.model_fields_set:
            raise ValueError("nutrition needs at least one field")
        return self

    def merged_into(self, existing: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Return existing nutrition with only the fields set here replaced."""
        merged = dict(existing or {})
        for field in self.model_fields_set:
            merged[field] = getattr(self, field)
        return merged


class RecipeNoteInput(BaseModel):
    """One entry in a recipe's Notes panel."""

    title: str = Field(default="", description="Heading for the note; may be empty.")
    text: str = Field(description="Body of the note.")

    @model_validator(mode="after")
    def _require_content(self) -> "RecipeNoteInput":
        if not self.title.strip() and not self.text.strip():
            raise ValueError("a note needs a title or text")
        return self


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
    substitutions: Optional[List[RecipeIngredientSubstitutionInput]] = Field(
        default=None,
        description=(
            "Substitutes Mealie shows for this ingredient. Omit to keep the "
            "existing substitutions of the ingredient with the same referenceId "
            "on update; pass [] to remove them."
        ),
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
