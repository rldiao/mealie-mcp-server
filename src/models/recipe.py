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


class RecipeInstruction(BaseModel):
    id: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    text: str
    ingredientReferences: List[str] = Field(default_factory=list)


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


class RecipeOrganizer(BaseModel):
    id: str
    name: str
    slug: str


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
    totalTime: Optional[int] = None
    prepTime: Optional[int] = None
    cookTime: Optional[int] = None
    performTime: Optional[int] = None
    description: Optional[str] = None
    recipeCategory: List[RecipeOrganizer] = Field(default_factory=list)
    tags: List[RecipeOrganizer] = Field(default_factory=list)
    tools: List[RecipeOrganizer] = Field(default_factory=list)
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
