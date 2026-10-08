"""Tests for the Pydantic recipe models, including the typing fixes."""

import pytest
from conftest import BASE_RECIPE
from pydantic import ValidationError

from models.recipe import (
    OrganizerRef,
    Recipe,
    RecipeIngredientInput,
    RecipeIngredientSubstitutionInput,
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


def test_recipe_ingredient_input_accepts_substitutions():
    ing = RecipeIngredientInput(
        note="buttermilk",
        substitutions=[
            {"substituteFoodId": "a1000001-0000-4000-8000-000000000009"},
            {"note": "milk with a squeeze of lemon"},
        ],
    )
    assert ing.model_dump(exclude_none=True)["substitutions"] == [
        {"substituteFoodId": "a1000001-0000-4000-8000-000000000009"},
        {"note": "milk with a squeeze of lemon"},
    ]


def test_substitution_input_requires_food_or_note():
    with pytest.raises(ValidationError):
        RecipeIngredientSubstitutionInput()
    with pytest.raises(ValidationError):
        RecipeIngredientSubstitutionInput(note="   ")


def test_recipe_round_trip_keeps_unmodelled_mealie_fields():
    recipe = Recipe.model_validate(
        {
            **BASE_RECIPE,
            "someFutureField": {"keep": True},
            "recipeIngredient": [
                {
                    "note": "Cos",
                    "referenceId": "a1000001-0000-4000-8000-000000000001",
                    "substitutions": [
                        {
                            "substituteFoodId": "a1000001-0000-4000-8000-000000000002",
                            "note": None,
                            "substituteFood": {"id": "x", "name": "Romaine"},
                        }
                    ],
                    "referencedRecipe": {"id": "r", "slug": "dressing"},
                    "anotherNewField": 1,
                }
            ],
        }
    )
    dumped = recipe.model_dump(exclude_none=True)
    ing = dumped["recipeIngredient"][0]
    assert dumped["someFutureField"] == {"keep": True}
    assert ing["substitutions"][0]["substituteFoodId"] == (
        "a1000001-0000-4000-8000-000000000002"
    )
    assert ing["referencedRecipe"] == {"id": "r", "slug": "dressing"}
    assert ing["anotherNewField"] == 1
