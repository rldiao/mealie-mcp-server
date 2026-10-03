# Usage Examples

Example requests for Claude Desktop or another MCP client connected to the
Mealie MCP Server. See the [README](README.md#quick-start) for setup and the
[tool inventory](README.md#available-tools) for supported operations.

These are natural-language prompts, not literal tool calls. The assistant should
resolve recipe slugs, organizer IDs, and list IDs before making changes.

## Contents

- [Recipe Management](#recipe-management)
- [Shopping Lists](#shopping-lists)
- [Meal Planning](#meal-planning)
- [Organization](#organization)
- [Advanced Workflows](#advanced-workflows)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)
- [See Also](#see-also)

## Recipe Management

### Finding Recipes

```text
"Search for chicken recipes"
"Find recipes with 'pasta' in the name"
"Find recipes tagged with 'quick' OR 'easy'"
"Show me recipes that have BOTH 'healthy' AND 'quick' tags"
"Get all breakfast recipes"
```

Recipe filters accept slugs or UUIDs, not display names. The assistant should
look up tags and categories first; for example, resolve `Quick Meals` to
`quick-meals` before filtering.

### Creating, Importing, and Duplicating Recipes

```text
"Create a recipe for scrambled eggs with these ingredients:
- 2 eggs
- 1 tbsp butter
- Salt and pepper to taste

And these instructions:
1. Beat eggs in a bowl
2. Melt butter in a pan
3. Pour in the eggs and scramble until cooked"
```

```text
"Import the recipe from this URL: <recipe URL>"
"Make a copy of the chocolate cake recipe called 'Birthday Cake'"
```

After importing, check that the returned name and content match the source.
Scraping support varies by website and Mealie version.

### Updating Recipes

```text
"Replace the pasta recipe's ingredients with:
- 1 lb spaghetti
- 2 cups marinara
- Fresh basil

And replace its instructions with:
1. Boil pasta
2. Heat sauce
3. Combine and serve"
```

```text
"Change the meatloaf recipe's description to 'Family favorite comfort food'"
"Update the yield of the soup recipe to '6 servings'"
```

Both content and metadata changes use `update_recipe`. Omitted fields stay
unchanged; supplied ingredient and instruction lists replace those fields, and
empty lists clear them.

### Nutrition and Display Settings

```text
"Set the chicken curry's per-serving nutrition to: 520 calories,
 31g protein, 18g fat, 42g carbs, and 780mg sodium"
"Show the nutrition card and uploaded assets on the chicken curry recipe"
```

Mealie replaces the whole nutrition object, so include every value you want to
keep. Display settings are merged instead: omitted toggles keep their current
values. See the [nutrition](README.md#nutrition-is-replaced-not-merged) and
[display settings](README.md#uploaded-assets-and-nutrition-can-be-stored-but-hidden)
notes.

### Parsing Ingredients

```text
"Parse these ingredients against my Mealie vocabulary, then create the recipe:
- 1/4 cup chopped onion
- 2 large eggs
- a pinch of salt"
```

`parse_ingredients` resolves all lines in one request and returns quantities,
units, foods, and notes. Check low-confidence results and missing food or unit
matches before creating the recipe.

### Images and Assets

```text
"Set the chocolate cake recipe's image to https://example.com/cake.jpg"
"Upload the image at /Users/me/Pictures/dish.jpg for the pasta recipe"
"Attach /Users/me/Documents/recipe-notes.pdf to the pasta recipe"
```

Replace example URLs and paths with real ones. Files must be accessible to the
server process; a remote or containerized server cannot read your desktop files
unless you make them available there.

### Marking as Made and Deleting

```text
"Mark the chicken parmesan recipe as made today"
"Delete the test recipe I just created"
```

Marking a recipe as made updates its `lastMade` timestamp. It does not provide a
count of how often the recipe was cooked.

## Shopping Lists

### Managing Lists

```text
"Create a shopping list called 'Weekly Groceries'"
"Show me all my shopping lists"
"Rename 'Weekly Groceries' to 'Weekend Groceries'"
```

### Adding Items

```text
"Add these items to my Weekly Groceries list:
- 2 lbs chicken breast
- 1 dozen eggs
- 2 cups rice"
"Add all ingredients from the lasagna recipe to my Weekly Groceries list"
```

The assistant can use bulk creation for manual items and recipe integration for
recipe ingredients.

### Updating and Removing Items

```text
"Check off milk on my Weekly Groceries list"
"Change the quantity of chicken breast to 3 lbs"
"Update the rice item's note to 'Basmati rice'"
"Remove all checked items from my Weekly Groceries list"
```

Single and bulk item updates preserve omitted fields. Be explicit about whether
you want to delete checked items, all items, or the entire list.

## Meal Planning

### Creating and Viewing Plans

```text
"Add the lasagna recipe to tomorrow's dinner"
"Plan chicken soup for lunch on Friday"
"What's for dinner tonight?"
"Show me this week's meal plan"
```

```text
"Plan this week's dinners:
- Monday: Lasagna
- Tuesday: Chicken stir-fry
- Wednesday: Spaghetti
- Thursday: Tacos
- Friday: Pizza"
```

The assistant must resolve relative dates to `YYYY-MM-DD`. Entry types are
`breakfast`, `lunch`, `dinner`, or `side`; each new entry needs a recipe or a
nonblank title.

### Changing Plans

```text
"Move Friday's pizza dinner to Saturday"
"Replace tomorrow's dinner recipe with a title-only entry called 'Leftovers'"
"Delete Sunday's lunch entry"
```

To remove a recipe link, `update_mealplan` accepts `clear_recipe=True`. It cannot
be combined with a replacement `recipe_id`.

## Organization

### Categories and Tags

```text
"Create a category called 'Quick Dinners'"
"Which categories don't have any recipes?"
"Add the pancake recipe to the Breakfast category, keeping its other categories"
"Create a tag called 'Quick Meals'"
"Which tags aren't being used?"
"Add 'healthy' and 'quick' tags to the salad recipe, keeping its existing tags"
```

Search before creating organizers to avoid duplicates.
`update_recipe_categories_and_tags` replaces each supplied ID list; omitted
lists stay unchanged, and empty lists clear them. To add a category or tag, the
assistant must include the recipe's existing IDs in the replacement list.

### Foods, Units, and Kitchen Tools

```text
"Find the food entry for chickpeas"
"Show me the available measurement units"
"Create a kitchen tool called 'Stand mixer'"
```

Foods and units provide references for structured recipe ingredients. Kitchen
tools represent equipment, not MCP operations.

## Advanced Workflows

### Weekly Meal Planning with Shopping

```text
"Help me plan this week's dinners and create a shopping list for those recipes"
```

A typical sequence is:

1. Choose recipes and resolve their IDs.
2. Create meal plan entries for the agreed dates.
3. Create a shopping list.
4. Add each recipe's ingredients.
5. Review the resulting quantities and any duplicate items.

Bulk meal-plan creation and recipe creation use multiple API requests. On a
failure, inspect the reported completed work before retrying; see
[partial-write recovery](README.md#recovering-from-partially-completed-writes).

### Scaling Recipe Ingredients

```text
"I'm cooking for 8, and my lasagna serves 4.
 Add its ingredients to my Dinner Party shopping list at double quantity."
```

After checking the recipe's yield, the assistant can call
`add_recipe_to_shopping_list` with `recipe_increment_quantity=2.0`.

### Reviewing Older Recipes

```text
"Review the last-made dates of my recipes and suggest some I haven't made lately"
"Find recipes with 'test' in the name and show me the matches before deleting any"
```

`lastMade` indicates recency, not cooking frequency. These tools do not expose
purchase history, price estimates, or pantry inventory.

## Best Practices

- Resolve slugs and IDs before filtering or updating.
- Group similar shopping-item and meal-plan writes using the bulk tools.
- Specify which fields should change and whether existing lists should be kept.
- Use recipe-to-shopping-list integration instead of manually copying ingredients.
- Review imports and parsed ingredients before relying on their results.
- Review the target records before destructive operations.
- Inspect the current state after a failed write instead of blindly retrying.

## Troubleshooting

### No Recipes Found When Filtering

Look up the tag or category and use its slug or UUID, not its display name.
Check whether you requested AND or OR matching when using multiple filters.

### Nutrition or Assets Are Missing in Mealie

Check the recipe's `showNutrition` and `showAssets` settings. Content can be
stored successfully while its UI card is hidden.

### Shopping Item Fields Disappear After an Update

Updates preserve omitted fields. Check whether the request explicitly supplied
values for fields you meant to keep. See
[field preservation](README.md#field-preservation) for bulk-input conventions.

### A Delete Returns No Data

A successful empty or JSON-null API response is normalized to a structured
success response. HTTP failures still surface as errors; no response body alone
is not a failure.

### A Tool Name Is No Longer Available

Refresh the client's tool list and update saved calls using the
[migration table](README.md#migrating-consolidated-tools-breaking-change).

## See Also

- [README](README.md) - Installation, configuration, and tool reference
- [Changelog](CHANGELOG.md) - Changes and migration notes
