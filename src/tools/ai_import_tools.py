from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from mealie import MealieFetcher
from tools.errors import tool_error_boundary
from tools.recipe_tools import _created_recipe_stage


def register_ai_import_tools(mcp: FastMCP, mealie: MealieFetcher) -> None:
    """Register the explicitly enabled AI recipe importer."""

    @mcp.tool(annotations=ToolAnnotations(
        readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True
    ))
    def import_recipe_with_ai(
        content: str = "",
        url: str | None = None,
        image_paths: list[str] | None = None,
        translate_language: str | None = None,
        create_new_organizers: bool = False,
    ) -> dict[str, Any]:
        """Create one recipe from text, HTML/JSON, photos, or web/video links using AI.
        Supports combined sources and translation.

        Prefer import_recipe_from_url for ordinary webpages, create_recipe for
        structured recipes, and upload_recipe_image_file for attaching photos.

        Provide at least one source. Image paths must be accessible to the server.

        Saves immediately and returns the recipe for review. AI charges may apply.
        """
        with tool_error_boundary("Error importing recipe with AI"):
            images = []
            for image_path in image_paths or []:
                if not image_path.strip():
                    raise ValueError("Image path cannot be empty")
                path = Path(image_path)
                images.append((path.name, path.read_bytes()))
            # A plain str annotation prevents FastMCP from pre-parsing recipe JSON.
            slug = mealie.import_recipe_with_ai(
                content=content or None, url=url, images=images,
                translate_language=translate_language,
                create_new_organizers=create_new_organizers,
            )
            with _created_recipe_stage(slug, "fetch"):
                return mealie.get_recipe(slug)
