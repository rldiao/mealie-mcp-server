from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.prompts.base import AssistantMessage, Message, UserMessage


def register_prompts(mcp: FastMCP) -> None:
    """Register all prompt-related tools with the MCP server."""

    @mcp.prompt()
    def weekly_meal_plan(preferences: str = "") -> list[Message]:
        """Generates a weekly meal plan template.

        Args:
            preferences: Additional dietary preferences or constraints
        """
        # System message with detailed instructions for the AI assistant
        system_content = """
<context>
You have access to a Mealie recipe database with various recipes. You can search for recipes and create meal plans that can be saved directly to the Mealie system.

## Tool Usage Guidelines

### Recipe Tools
- get_recipes: Search and list recipes (always set per_page=50. Use null if empty values)
- get_recipe_concise: Get basic recipe details (use by default)
- get_recipe_detailed: Get full recipe information (do not use unless user asks for it)

### Meal Plan Tools
- get_all_mealplans: View existing meal plans
- create_mealplan_bulk: Add multiple recipes to a meal plan at once (requires a list of entries with date in YYYY-MM-DD format, recipe_id if available, and entry_type)
- get_todays_mealplan: View today's planned meals
</context>

<instructions>
# Meal Planning Guidelines
- Include breakfast, lunch, and dinner for all 7 days
- Create a variety of meals using different proteins, grains, and vegetables
- Consider seasonal ingredients and balance nutrition throughout the week
- Use recipes from the Mealie database when available
- Plan for leftovers where appropriate and suggest how they can be repurposed

# User Interaction
- Present the meal plan in table format
- Ask for feedback about meal swaps, leftover utilization, and dietary needs
- When suggesting recipes, include the recipe ID or slug
- Before saving to Mealie, display the complete meal plan in concise summary for final user confirmation
- After confirmation, save the plan to Mealie without showing an additional summary
</instructions>
"""

        # User message that initiates the conversation
        user_content = "I need help creating a balanced meal plan for the next week that includes breakfast, lunch, and dinner."

        if preferences:
            user_content += f" My preferences are: {preferences}"

        # Create and return a list of Message objects
        return [
            AssistantMessage(system_content),
            UserMessage(user_content),
        ]
