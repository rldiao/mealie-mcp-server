"""Tests for ingredient parsing (single-line lists, batches, flattening, verbose)."""

import logging

import pytest
from mcp.server.fastmcp.exceptions import ToolError

FOOD_ID = "a0819c33-1a5e-4374-9151-ed85160c0049"


async def test_parse_ingredient_posts_to_parser_endpoint(invoke, fetcher):
    await invoke("parse_ingredients", ingredients=["1/4 cup chopped onion"])

    req = fetcher.last("POST", "/api/parser/ingredients")
    assert req["url"] == "/api/parser/ingredients"
    assert req["json"] == {"ingredients": ["1/4 cup chopped onion"], "parser": "nlp"}


async def test_parse_ingredient_flattens_to_recipe_ingredient_shape(invoke, fetcher):
    results = await invoke("parse_ingredients", ingredients=["1/4 cup chopped onion"])
    assert len(results) == 1
    out = results[0]

    # exactly the fields create_recipe accepts, plus input/confidence
    assert out == {
        "input": "1/4 cup chopped onion",
        "confidence": 0.996,
        "quantity": 0.25,
        "unit": None,  # unmatched vocabulary stays visible as null
        "food": {"id": FOOD_ID, "name": "onion"},
        "note": "chopped",
    }


async def test_parse_ingredient_verbose_returns_untouched_response(invoke, fetcher):
    out = (await invoke(
        "parse_ingredients", ingredients=["1/4 cup chopped onion"], verbose=True
    ))[0]

    assert out["ingredient"]["food"]["pluralName"] == "onions"
    assert out["confidence"]["quantity"] == 1.0


async def test_parse_ingredient_forwards_parser_choice(invoke, fetcher):
    await invoke("parse_ingredients", ingredients=["2 eggs"], parser="brute")

    assert fetcher.last("POST", "/api/parser/ingredients")["json"]["parser"] == "brute"


async def test_parse_ingredient_rejects_unknown_parser(invoke, fetcher):
    with pytest.raises(ToolError, match="parser must be one of"):
        await invoke("parse_ingredients", ingredients=["2 eggs"], parser="magic")

    assert fetcher.requests == []


@pytest.mark.parametrize("ingredients", [[""], [" \t"], ["2 eggs", ""]])
async def test_parse_ingredient_rejects_empty_input(invoke, fetcher, ingredients):
    with pytest.raises(ToolError, match="Ingredient cannot be empty"):
        await invoke("parse_ingredients", ingredients=ingredients)

    assert fetcher.requests == []


async def test_parse_ingredients_batches_in_one_request(invoke, fetcher):
    lines = ["1/4 cup chopped onion", "2 large eggs", "a pinch of salt"]
    out = await invoke("parse_ingredients", ingredients=lines)

    assert len(fetcher.requests) == 1
    assert fetcher.last("POST", "/api/parser/ingredients")["json"] == {
        "ingredients": lines,
        "parser": "nlp",
    }
    # one result per line, in input order
    assert [r["input"] for r in out] == lines
    assert out[0]["food"] == {"id": FOOD_ID, "name": "onion"}


async def test_parse_ingredients_verbose_returns_untouched_responses(invoke, fetcher):
    out = await invoke("parse_ingredients", ingredients=["2 eggs"], verbose=True)

    assert out[0]["ingredient"]["referenceId"] == "75e1853f-3cb1-49b9-b2ca-26ae76da256b"


async def test_parse_ingredients_rejects_empty_list(invoke, fetcher):
    with pytest.raises(ToolError, match="Ingredients cannot be empty"):
        await invoke("parse_ingredients", ingredients=[])

    assert fetcher.last("POST", "/api/parser/ingredients") is None


async def test_parsed_result_feeds_create_recipe(invoke, fetcher):
    """The parser output must be usable as a structured ingredient verbatim."""
    parsed = await invoke("parse_ingredients", ingredients=["1/4 cup chopped onion"])

    await invoke("create_recipe", name="Parsed", ingredients=parsed)

    written = fetcher.last("PUT", "/api/recipes/")["json"]["recipeIngredient"][0]
    assert written["quantity"] == 0.25
    assert written["food"]["id"] == FOOD_ID
    assert written["note"] == "chopped"


async def test_parse_ingredients_surfaces_client_failure(invoke, fetcher):
    fetcher.fail_on("/api/parser/ingredients", 500, "Parser unavailable")

    with pytest.raises(ToolError, match="Error parsing ingredients"):
        await invoke("parse_ingredients", ingredients=["2 eggs"])


async def test_parser_logs_exclude_inputs_and_client_errors(
    invoke, fetcher, caplog
):
    caplog.set_level(logging.DEBUG, logger="mealie-mcp")
    await invoke("parse_ingredients", ingredients=["private-ingredient"])
    fetcher.fail_on("/api/parser/", 500, "private-error-response")
    with pytest.raises(ToolError):
        await invoke("parse_ingredients", ingredients=["private-ingredient"])
    assert "private-ingredient" not in caplog.text
    assert "private-error-response" not in caplog.text


async def test_parser_validation_does_not_log_user_supplied_parser(invoke, caplog):
    caplog.set_level(logging.DEBUG, logger="mealie-mcp")
    with pytest.raises(ToolError, match="parser must be one of"):
        await invoke(
            "parse_ingredients", ingredients=["private-ingredient"], parser="private-parser"
        )
    assert "private-parser" not in caplog.text
    assert "private-ingredient" not in caplog.text
