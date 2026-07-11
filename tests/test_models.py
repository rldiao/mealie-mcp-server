"""Tests for the Pydantic recipe models, including the typing fixes."""

from conftest import BASE_RECIPE

from models.recipe import (
    OrganizerRef,
    Recipe,
    RecipeIngredientInput,
    RecipeInstructionInput,
)


def test_time_fields_accept_text():
    # Previously typed as int, which raised on textual times returned by Mealie.
    r = Recipe.model_validate(
        {
            **BASE_RECIPE,
            "totalTime": "35 Minutes",
            "prepTime": "10 min",
            "cookTime": "PT25M",
            "performTime": "20 Minuten",
        }
    )
    assert r.totalTime == "35 Minutes"
    assert r.cookTime == "PT25M"
    assert r.performTime == "20 Minuten"


def test_instruction_ingredient_references_are_objects():
    r = Recipe.model_validate(
        {
            **BASE_RECIPE,
            "recipeInstructions": [
                {"text": "Mix", "ingredientReferences": [{"referenceId": "abc"}]}
            ],
        }
    )
    assert r.recipeInstructions[0].ingredientReferences[0].referenceId == "abc"


def test_tags_tools_categories_are_objects():
    # Previously typed as list[str]; Mealie returns objects.
    r = Recipe.model_validate(
        {
            **BASE_RECIPE,
            "tags": [{"id": "t1", "name": "Quick", "slug": "quick"}],
            "tools": [
                {
                    "id": "k1",
                    "name": "Pfanne",
                    "slug": "pfanne",
                    "householdsWithTool": ["h1"],
                }
            ],
            "recipeCategory": [{"id": "c1", "name": "Dinner", "slug": "dinner"}],
        }
    )
    assert r.tags[0].name == "Quick"
    assert r.tools[0].householdsWithTool == ["h1"]
    assert r.recipeCategory[0].slug == "dinner"


def test_recipe_ingredient_input_serialisation():
    ing = RecipeIngredientInput(
        quantity=2,
        food={"id": "f1", "name": "egg"},
        unit={"id": "u1", "name": "piece"},
        note="large",
        title="Eggs",
        referenceId="r1",
    )
    dumped = ing.model_dump(exclude_none=True)
    assert dumped["food"] == {"id": "f1", "name": "egg"}
    assert dumped["referenceId"] == "r1"


def test_recipe_instruction_input_serialisation():
    step = RecipeInstructionInput(
        text="Do it", title="Step", ingredientReferences=[{"referenceId": "r1"}]
    )
    assert step.ingredientReferences[0].referenceId == "r1"


def test_organizer_ref_requires_id_and_name():
    org = OrganizerRef(id="t1", name="Quick")
    assert org.model_dump(exclude_none=True) == {"id": "t1", "name": "Quick"}
