from typing import Annotated, Any, Optional, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator


def nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("Identifier cannot be blank")
    return value


Identifier = Annotated[str, AfterValidator(nonblank)]


class ShoppingListItemPatch(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True, extra="allow", allow_inf_nan=False
    )

    id: Optional[Identifier] = None
    shopping_list_id: Optional[Identifier] = Field(default=None, alias="shoppingListId")
    note: Optional[str] = ""
    quantity: float = 1
    checked: bool = False
    position: int = 0
    unit_id: Optional[Identifier] = Field(default=None, alias="unitId")
    food_id: Optional[Identifier] = Field(default=None, alias="foodId")
    label_id: Optional[Identifier] = Field(default=None, alias="labelId")
    unit: Optional[dict[str, Any]] = None
    food: Optional[dict[str, Any]] = None
    is_food: bool = Field(default=False, alias="isFood")
    disable_amount: Optional[bool] = Field(default=None, alias="disableAmount")
    display: str = ""
    extras: Optional[dict[str, Any]] = None
    recipe_references: list[dict[str, Any]] = Field(
        default_factory=list, alias="recipeReferences"
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_aliases(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        value = dict(value)
        for name, field in cls.model_fields.items():
            alias = field.alias
            if alias and name in value and alias in value:
                if value[name] != value[alias]:
                    raise ValueError("Conflicting field aliases")
                del value[name]
        return value

    @model_validator(mode="after")
    def reject_null_identifiers(self) -> Self:
        if (
            "shopping_list_id" in self.model_fields_set
            and self.shopping_list_id is None
        ):
            raise ValueError("Shopping list identifier cannot be null")
        return self


class ShoppingListItemCreate(ShoppingListItemPatch):
    shopping_list_id: Identifier = Field(alias="shoppingListId")


class ShoppingListItemUpdate(ShoppingListItemPatch):
    id: Identifier

    @model_validator(mode="after")
    def require_changes(self) -> Self:
        if not self.model_fields_set - {"id"}:
            raise ValueError("At least one field must be provided to update")
        return self
