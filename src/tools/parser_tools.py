import logging
import traceback
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from mealie import MealieFetcher

logger = logging.getLogger("mealie-mcp")

_PARSERS = ("nlp", "brute", "openai")


def _organizer_ref(value: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Reduce a parsed food/unit to the {id, name} pair the recipe tools need."""
    if not value:
        return None
    return {"id": value.get("id"), "name": value.get("name")}


def _flatten(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Reduce a Mealie ParsedIngredient to a RecipeIngredientInput-shaped dict.

    Mealie returns the full food and unit records plus a per-field confidence
    breakdown. Only the ids and names are needed to build a recipe, so the rest
    is dropped and the confidences collapse to their average; pass verbose=True
    to the tool to get the untouched response instead.
    """
    ingredient = parsed.get("ingredient") or {}
    return {
        "input": parsed.get("input"),
        "confidence": (parsed.get("confidence") or {}).get("average"),
        "quantity": ingredient.get("quantity"),
        "unit": _organizer_ref(ingredient.get("unit")),
        "food": _organizer_ref(ingredient.get("food")),
        "note": ingredient.get("note"),
    }


def _validate_parser(parser: str) -> None:
    if parser not in _PARSERS:
        raise ValueError(f"parser must be one of {', '.join(_PARSERS)}, got '{parser}'")


def register_parser_tools(mcp: FastMCP, mealie: MealieFetcher) -> None:
    """Register the ingredient-parser tools with the MCP server."""

    @mcp.tool()
    def parse_ingredient(
        ingredient: str, parser: str = "nlp", verbose: bool = False
    ) -> Dict[str, Any]:
        """Resolve one free-text ingredient line against Mealie's vocabulary.

        Mealie's server-side parser turns "1/4 cup chopped onion" into
        quantity 0.25, the existing "cup" unit, the existing "onion" food, and
        the note "chopped" — in one call, instead of searching get_foods and
        get_units per ingredient. Use parse_ingredients for a whole recipe.

        The returned unit and food carry the ids create_recipe_full needs, so a
        result can be passed straight through as a structured ingredient.
        A null unit or food means Mealie has no matching entry; create one with
        create_food or create_unit, or leave the text in the note.

        Confidence is Mealie's own 0-1 score; low values are worth checking
        against the source text before writing the recipe.

        Args:
            ingredient: The ingredient line to parse, e.g. "1/4 cup chopped onion".
            parser: Parser backend — "nlp" (default, trained model), "brute"
                (regex splitting, better for terse or unusual formats), or
                "openai" (only if the Mealie server is configured for it).
            verbose: If True, return Mealie's untouched response, including the
                full food/unit records and the per-field confidence breakdown.

        Returns:
            Dict[str, Any]: input, confidence, quantity, unit, food, and note.
        """
        try:
            _validate_parser(parser)
            logger.info({"message": "Parsing ingredient", "parser": parser})
            parsed = mealie.parse_ingredient(ingredient, parser=parser)
            return parsed if verbose else _flatten(parsed)
        except Exception as e:
            error_msg = f"Error parsing ingredient: {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise ToolError(error_msg)

    @mcp.tool()
    def parse_ingredients(
        ingredients: List[str], parser: str = "nlp", verbose: bool = False
    ) -> List[Dict[str, Any]]:
        """Resolve a whole recipe's ingredient lines in a single call.

        Same parser as parse_ingredient, batched — the efficient way to prepare
        ingredients before create_recipe_full or update_recipe. Results come
        back in input order, one per line.

        Args:
            ingredients: The ingredient lines to parse, in recipe order.
            parser: Parser backend — "nlp" (default, trained model), "brute"
                (regex splitting, better for terse or unusual formats), or
                "openai" (only if the Mealie server is configured for it).
            verbose: If True, return Mealie's untouched responses, including the
                full food/unit records and the per-field confidence breakdown.

        Returns:
            List[Dict[str, Any]]: One result per input line, in the same order,
            each with input, confidence, quantity, unit, food, and note.
        """
        try:
            _validate_parser(parser)
            logger.info(
                {
                    "message": "Parsing ingredients",
                    "parser": parser,
                    "count": len(ingredients),
                }
            )
            parsed = mealie.parse_ingredients(ingredients, parser=parser)
            return parsed if verbose else [_flatten(p) for p in parsed]
        except Exception as e:
            error_msg = f"Error parsing ingredients: {str(e)}"
            logger.error({"message": error_msg})
            logger.debug(
                {"message": "Error traceback", "traceback": traceback.format_exc()}
            )
            raise ToolError(error_msg)
