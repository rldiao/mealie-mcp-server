# Usage Examples

Practical examples for using the Mealie MCP Server with Claude Desktop.

## Table of Contents

- [Recipe Management](#recipe-management)
- [Shopping Lists](#shopping-lists)
- [Meal Planning](#meal-planning)
- [Organization](#organization)
- [Advanced Workflows](#advanced-workflows)

---

## Recipe Management

### Finding Recipes

**Simple search:**
```
"Search for chicken recipes"
"Find recipes with 'pasta' in the name"
"Show me all recipes containing 'garlic'"
```

**Advanced filtering:**
```
"Find recipes tagged with 'quick' OR 'easy'"
"Show me recipes that have BOTH 'healthy' AND 'quick' tags"
"Get all breakfast recipes"
```

**Important:** When filtering by tags/categories, first get the slugs:
```
User: "Show me all quick meal recipes"
Claude: First, let me get the tags to find the right slug...
         [Finds tag slug is "quick-meals"]
         Now filtering recipes by tag slug "quick-meals"...
```

### Creating Recipes

**Simple recipe:**
```
"Create a recipe for scrambled eggs with these ingredients:
- 2 eggs
- 1 tbsp butter
- Salt and pepper to taste

And these instructions:
1. Beat eggs in a bowl
2. Melt butter in pan
3. Pour eggs and scramble until cooked"
```

**From existing recipe (duplicate):**
```
"Duplicate my lasagna recipe"
"Make a copy of the chocolate cake recipe called 'Birthday Cake'"
```

### Updating Recipes

**Full update:**
```
"Update the pasta recipe with these new ingredients:
- 1 lb spaghetti
- 2 cups marinara
- Fresh basil

And these instructions:
1. Boil pasta
2. Heat sauce
3. Combine and serve"
```

**Partial update (PATCH):**
```
"Change the description of the meatloaf recipe to 'Family favorite comfort food'"
"Update the yield of the soup recipe to '6 servings'"
```

### Nutrition

```
"Add nutrition to the chicken curry: 520 calories, 31g protein, 18g fat,
 42g carbs, 780mg sodium"
```

Values are per serving. Mealie replaces the whole nutrition object, so ask for
every value you want to keep in a single request.

### Recipe Images

**From URL:**
```
"Set the recipe image for chocolate cake to https://example.com/cake.jpg"
```

**From local file:**
```
"Upload the image at /Users/me/Pictures/dish.jpg for the pasta recipe"
```

### Recipe Metadata

**Mark as made:**
```
"Mark the chicken parmesan recipe as made today"
"Update the last made date for lasagna"
```

**Delete recipe:**
```
"Delete the test recipe I just created"
```

---

## Shopping Lists

### Creating & Managing Lists

**Create list:**
```
"Create a shopping list called 'Weekly Groceries'"
"Make a new shopping list for Thanksgiving"
```

**View lists:**
```
"Show me all my shopping lists"
"What shopping lists do I have?"
```

### Adding Items

**Manual items:**
```
"Add eggs and milk to my shopping list"
"Add these items to my grocery list:
- 2 lbs chicken breast
- 1 dozen eggs
- 2 cups rice"
```

**From recipes:**
```
"Add all ingredients from the lasagna recipe to my shopping list"
"Add the ingredients from chicken soup to my Weekly Groceries list"
```

**Bulk creation:**
```
"Create 5 items on my shopping list at once:
- Apples
- Oranges
- Bananas
- Grapes
- Strawberries"
```

### Managing Items

**Check off items:**
```
"Mark eggs as checked on my shopping list"
"Check off milk from the grocery list"
```

**Update items:**
```
"Change the quantity of chicken breast to 3 lbs"
"Update the rice item to 'Basmati rice'"
```

**Delete items:**
```
"Delete eggs from my shopping list"
"Remove all checked items from my grocery list"
```

### Shopping List Workflows

**Weekly meal prep:**
```
User: "I'm planning to make lasagna, chicken soup, and pasta this week.
       Create a shopping list with all the ingredients."

Claude: I'll help you create a comprehensive shopping list:
        1. Creating "Weekly Meal Prep" list
        2. Adding ingredients from lasagna recipe
        3. Adding ingredients from chicken soup
        4. Adding ingredients from pasta recipe
        Done! Your list has 15 unique ingredients.
```

**Post-shopping cleanup:**
```
User: "I'm back from the store. Clear my shopping list."

Claude: I'll delete all items from your shopping list.
        [Deletes all checked items]
        All done!
```

---

## Meal Planning

### Creating Meal Plans

**Single meal:**
```
"Add the lasagna recipe to tomorrow's dinner"
"Plan chicken soup for lunch on Friday"
```

**Bulk planning:**
```
"Plan this week's dinners:
- Monday: Lasagna
- Tuesday: Chicken stir-fry
- Wednesday: Spaghetti
- Thursday: Tacos
- Friday: Pizza"
```

### Viewing Plans

**Today's plan:**
```
"What's for dinner tonight?"
"Show me today's meal plan"
```

**Weekly view:**
```
"Show me this week's meal plan"
"What meals do I have planned for next week?"
```

---

## Organization

### Categories

**Create categories:**
```
"Create a category called 'Quick Dinners'"
"Make categories for Breakfast, Lunch, Dinner, and Dessert"
```

**Find unused categories:**
```
"Which categories don't have any recipes?"
"Show me empty categories"
```

**Organize recipes:**
```
"Add the pancake recipe to the Breakfast category"
"Move lasagna to the Dinner category"
```

### Tags

**Create tags:**
```
"Create a tag called 'Quick Meals'"
"Make tags for: Healthy, Family Favorite, Budget Friendly"
```

**Find and filter:**
```
"Show me all recipes tagged 'healthy'"
"Find recipes with both 'quick' and 'easy' tags"
"Which tags aren't being used?"
```

**Tag recipes:**
```
"Add the 'healthy' and 'quick' tags to the salad recipe"
"Tag the lasagna recipe as 'family favorite'"
```

---

## Advanced Workflows

### Weekly Meal Planning with Shopping

```
User: "Help me plan this week's meals and create a shopping list"

Claude: I'll help you plan the week:

        1. What meals would you like? [User provides list]

        2. Creating meal plan entries for Monday-Friday

        3. Creating "Weekly Shopping List"

        4. Adding ingredients from all 5 recipes to the list

        5. Consolidating duplicate ingredients

        Done! You have:
        - 5 meals planned
        - 1 shopping list with 23 items
```

### Recipe Collection Management

**Find and clean up:**
```
User: "Find all recipes I haven't made in over a year"

Claude: Searching for recipes with lastMade dates over 1 year ago...
        Found 12 recipes. Would you like me to:
        - Delete them?
        - Tag them as "Rarely Made"?
        - Create a report?
```

**Organize by usage:**
```
User: "Show me my most-made recipes this year"

Claude: Sorting recipes by lastMade date...
        Your top 10 most-made recipes:
        1. Spaghetti Carbonara (made 15 times)
        2. Chicken Stir-Fry (made 12 times)
        ...
```

### Smart Shopping Lists

**Recipe-based shopping:**
```
User: "I'm making a dinner party for 8. I want to make lasagna (serves 4).
       Add the ingredients to my shopping list with doubled quantities."

Claude: 1. Getting lasagna recipe
        2. Creating shopping list "Dinner Party"
        3. Adding ingredients with 2x multiplier
        Done! List ready with adjusted quantities.
```

**Budget tracking:**
```
User: "Create a shopping list for this week's meals and estimate the cost"

Claude: [Note: Price data would need to be in Mealie]
        Creating shopping list from meal plan...
        Estimated total: $XX.XX based on previous purchases
```

### Batch Operations

**Recipe cleanup:**
```
User: "Delete all test recipes I created today"

Claude: Searching for recipes created today with "test" in the name...
        Found 3 test recipes. Deleting:
        - Test Recipe 1
        - Test Recipe 2
        - Test Recipe 3
        All cleaned up!
```

**Category reorganization:**
```
User: "Find all breakfast recipes and make sure they're in the Breakfast category"

Claude: Searching for breakfast-related recipes...
        Found 15 recipes. Updating categories...
        Done! All breakfast recipes now categorized.
```

### Integration Workflows

**From recipe to table:**
```
1. "Find a chicken recipe for tonight"
2. "Add it to today's dinner plan"
3. "Add the ingredients to my shopping list"
4. [After cooking] "Mark it as made"
5. "Rate it 5 stars" [if rating is implemented]
```

**Weekly meal prep:**
```
1. "Show me quick recipes with chicken"
2. "Plan these 3 recipes for this week"
3. "Create a shopping list from the meal plan"
4. [After shopping] "Check off all items I bought"
5. [After cooking each meal] "Mark as made"
```

---

## Tips & Best Practices

### 1. Use Slugs for Filtering

❌ **Don't:**
```
"Show me recipes tagged 'Quick Meals'"
```

✅ **Do:**
```
"First show me the tags, then filter by the slug"
```

### 2. Batch Similar Operations

❌ **Don't:**
```
"Add eggs to shopping list"
"Add milk to shopping list"
"Add bread to shopping list"
```

✅ **Do:**
```
"Add eggs, milk, and bread to shopping list"
```

### 3. Be Specific with Updates

❌ **Don't:**
```
"Update the recipe" [vague]
```

✅ **Do:**
```
"Change the description to 'Family favorite' and update the yield to 6 servings"
```

### 4. Use Recipe Integration

❌ **Don't:**
```
"Manually add all ingredients from lasagna to shopping list"
```

✅ **Do:**
```
"Add lasagna recipe ingredients to shopping list"
```

### 5. Leverage Search Before Creating

❌ **Don't:**
```
"Create a tag called 'healthy'"
```

✅ **Do:**
```
"Show me all tags first" [check if 'healthy' already exists]
```

---

## Common Patterns

### Morning Routine
```
"What's on the meal plan for today?"
"Add ingredients for tonight's dinner to my shopping list"
```

### After Shopping
```
"Check off all items on my shopping list"
"Delete checked items"
```

### Weekly Planning
```
"Show me recipes I haven't made in a while"
"Plan those for this week"
"Create shopping list from meal plan"
```

### Recipe Discovery
```
"Find recipes with chicken and pasta"
"Show me quick dinner recipes"
"What recipes can I make with the ingredients I have?" [if inventory is tracked]
```

---

## Troubleshooting

### "No recipes found" when filtering

**Problem:** Using display name instead of slug

**Solution:**
```
Step 1: "Show me all tags"
Step 2: Note the slug (e.g., "quick-meals")
Step 3: "Filter recipes by tag slug 'quick-meals'"
```

### Shopping list item updates clearing fields

**Fixed!** The server now preserves all fields automatically.

```
"Update item to checked: true"
[Note, quantity, etc. are preserved]
```

### Delete operations returning errors

**Fixed!** The server now handles empty/null responses correctly.

```
"Delete the category"
[Returns success message even with null response]
```

---

## See Also

- [README.md](README.md) - Installation and setup
- [CHANGELOG.md](CHANGELOG.md) - Version history
- [API_COVERAGE.md](API_COVERAGE.md) - Detailed API coverage
