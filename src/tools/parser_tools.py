from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from mealie import MealieFetcher
from tools.errors import tool_error_boundary

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
    def parse_ingredients(
        ingredients: List[str], parser: str = "nlp", verbose: bool = False
    ) -> List[Dict[str, Any]]:
        """Resolve one or more ingredient lines in a single call.

        Mealie's server-side parser turns "1/4 cup chopped onion" into
        quantity 0.25, the existing "cup" unit, the existing "onion" food, and
        the note "chopped" — in one call, instead of searching get_foods and
        get_units per ingredient. Pass a one-element list for a single line.
        Results always come back as a list in input order, one per line.

        The returned unit and food carry the ids create_recipe needs, so a
        result can be passed straight through as a structured ingredient.
        A null unit or food means Mealie has no matching entry; create one with
        create_food or create_unit, or leave the text in the note.

        Confidence is Mealie's own 0-1 score; low values are worth checking
        against the source text before writing the recipe.

        Args:
            ingredients: Nonempty ingredient lines to parse, in recipe order.
            parser: Parser backend — "nlp" (default, trained model), "brute"
                (regex splitting, better for terse or unusual formats), or
                "openai" (only if the Mealie server is configured for it).
            verbose: If True, return Mealie's untouched responses, including the
                full food/unit records and the per-field confidence breakdown.

        Returns:
            List[Dict[str, Any]]: One result per input line, in the same order,
            each with input, confidence, quantity, unit, food, and note.
        """
        with tool_error_boundary("Error parsing ingredients"):
            _validate_parser(parser)
            if any(not ingredient.strip() for ingredient in ingredients):
                raise ValueError("Ingredient cannot be empty")
            parsed = mealie.parse_ingredients(ingredients, parser=parser)
            return parsed if verbose else [_flatten(p) for p in parsed]
