"""Live checks of the long-standing tools that unit tests only cover with fakes."""

import struct
import zlib
from datetime import UTC, date, datetime

import pytest
from mcp.server.fastmcp.exceptions import ToolError


def _png_bytes():
    """A valid 1x1 PNG."""

    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    pixels = zlib.compress(b"\x00\xff\x00\x00")
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", pixels)
        + chunk(b"IEND", b"")
    )


# --- recipes ----------------------------------------------------------------


async def test_full_recipe_round_trip(invoke, recipe):
    created = await recipe(
        "Pancakes",
        description="Fluffy",
        servings=4,
        recipe_yield="8 pancakes",
        ingredients=["200 g flour", {"note": "2 eggs", "referenceId": "eggs"}],
        instructions=[
            "Whisk the flour.",
            {"text": "Beat in the eggs.", "ingredientReferences": [{"referenceId": "eggs"}]},
        ],
        nutrition={"calories": 250, "proteinContent": 8},
        settings={"showNutrition": True},
    )
    stored = await invoke("get_recipe", slug=created["slug"])
    assert stored["description"] == "Fluffy"
    assert stored["recipeServings"] == 4
    assert [i.get("note") for i in stored["recipeIngredient"]] == ["200 g flour", "2 eggs"]
    egg_ref = stored["recipeIngredient"][1]["referenceId"]
    assert stored["recipeInstructions"][1]["ingredientReferences"] == [{"referenceId": egg_ref}]
    assert stored["nutrition"]["calories"] == "250"
    assert stored["settings"]["showNutrition"] is True

    renamed = await invoke("update_recipe", slug=created["slug"], name=created["name"] + " II")
    assert renamed["slug"] != created["slug"]
    refetched = await invoke("get_recipe", slug=renamed["slug"])
    # metadata-only updates keep the content
    assert len(refetched["recipeIngredient"]) == 2
    await invoke("update_recipe", slug=renamed["slug"], name=created["name"])


async def test_duplicate_and_last_made(invoke, live_fetcher, recipe, cleanup):
    created = await recipe("Original", instructions=["Cook."])
    copy = await invoke("duplicate_recipe", slug=created["slug"], name=created["name"] + " Copy")
    cleanup(lambda: live_fetcher.delete_recipe(copy["slug"]))
    assert copy["slug"] != created["slug"]
    assert [s["text"] for s in copy["recipeInstructions"]] == ["Cook."]

    assert "lastMade" not in await invoke("get_recipe", slug=created["slug"], concise=True)
    await invoke("mark_recipe_last_made", slug=created["slug"])
    concise = await invoke("get_recipe", slug=created["slug"], concise=True)
    assert concise["lastMade"].startswith(datetime.now(UTC).date().isoformat())


async def test_recipe_tags_and_categories(invoke, recipe, organizer, unique):
    category = await organizer("category", "Mains")
    created = await recipe("Organized")

    summary = await invoke("add_recipe_tags", slug=created["slug"], tags=[unique("Weeknight")])
    tag_names = summary["tags"]
    assert len(tag_names) == 1
    await invoke(
        "update_recipe_categories_and_tags",
        slug=created["slug"],
        category_ids=[category["id"]],
    )
    stored = await invoke("get_recipe", slug=created["slug"])
    assert [c["id"] for c in stored["recipeCategory"]] == [category["id"]]
    assert [t["name"] for t in stored["tags"]] == tag_names

    tag = await invoke("get_tag", tag_slug=stored["tags"][0]["slug"])
    await invoke("update_recipe_categories_and_tags", slug=created["slug"], tag_ids=[])
    await invoke("delete_tag", tag_id=tag["id"])


async def test_image_and_asset_uploads(invoke, recipe, tmp_path):
    created = await recipe("Pictured")
    image = tmp_path / "photo.png"
    image.write_bytes(_png_bytes())
    await invoke("upload_recipe_image_file", slug=created["slug"], image_path=str(image))
    assert (await invoke("get_recipe", slug=created["slug"]))["image"]

    notes = tmp_path / "notes.txt"
    notes.write_text("Serve warm.")
    asset = await invoke(
        "upload_recipe_asset_file", slug=created["slug"], asset_path=str(notes), name="Notes"
    )
    assert asset["fileName"].endswith(".txt")
    stored = await invoke("get_recipe", slug=created["slug"])
    assert [a["name"] for a in stored["assets"]] == ["Notes"]


async def test_missing_recipe_is_tool_error(invoke):
    with pytest.raises(ToolError, match="HTTP 404"):
        await invoke("get_recipe", slug="does-not-exist-anywhere")


# --- parser -----------------------------------------------------------------


async def test_parse_ingredients(invoke):
    parsed = await invoke("parse_ingredients", ingredients=["2 cups flour", "1 tsp salt"])
    assert len(parsed) == 2
    assert parsed[0]["quantity"] == 2


# --- foods, labels, units, tools --------------------------------------------


async def test_food_aliases_labels_and_on_hand(invoke, organizer):
    food = await organizer("food", "Scallion")
    label = await organizer("label", "Produce")

    await invoke("set_food_aliases", food_id=food["id"], aliases=["Green Onion"])
    await invoke("add_food_alias", food_id=food["id"], alias="Spring Onion")
    await invoke("remove_food_alias", food_id=food["id"], alias="Green Onion")
    await invoke("set_food_label_by_name", food_name=food["name"], label_name=label["name"])
    await invoke("set_food_on_hand", food_id=food["id"], on_hand=True)

    stored = await invoke("get_food", food_id=food["id"])
    assert [a["name"] for a in stored["aliases"]] == ["Spring Onion"]
    assert stored["labelId"] == label["id"]
    assert stored["householdsWithIngredientFood"]

    await invoke("set_food_label", food_id=food["id"], label_id=None)
    await invoke("set_food_on_hand", food_id=food["id"], on_hand=False)
    stored = await invoke("get_food", food_id=food["id"])
    assert stored["labelId"] is None
    assert not stored["householdsWithIngredientFood"]


async def test_mark_foods_and_tools_on_hand_by_name(invoke, live_fetcher, unique, cleanup):
    food_name, tool_name = unique("Saffron"), unique("Wok")
    foods = await invoke("mark_foods_on_hand", names=[food_name])
    tools = await invoke("mark_tools_on_hand", names=[tool_name])
    assert foods["created"] == [food_name]
    assert tools["created"] == [tool_name]
    food_id = foods["updated"][0]["id"]
    tool_id = tools["updated"][0]["id"]
    cleanup(lambda: live_fetcher.delete_food(food_id))
    cleanup(lambda: live_fetcher.delete_tool(tool_id))
    assert (await invoke("get_food", food_id=food_id))["householdsWithIngredientFood"]
    assert (await invoke("get_tool", tool_id=tool_id))["householdsWithTool"]


async def test_update_unit_and_label_keep_other_fields(invoke, organizer):
    unit = await organizer("unit", "Tablespoon")
    await invoke("update_unit", unit_id=unit["id"], abbreviation="tbsp")
    stored = await invoke("get_unit", unit_id=unit["id"])
    assert (stored["name"], stored["abbreviation"]) == (unit["name"], "tbsp")

    label = await organizer("label", "Dairy")
    await invoke("update_label", label_id=label["id"], color="#4CAF50")
    stored = await invoke("get_label", label_id=label["id"])
    assert (stored["name"], stored["color"]) == (label["name"], "#4CAF50")


# --- shopping lists ---------------------------------------------------------


async def test_shopping_list_items_lifecycle(invoke, shopping_list):
    groceries = await shopping_list("Groceries")
    await invoke("update_shopping_list", list_id=groceries["id"], name=groceries["name"] + "!")
    assert (await invoke("get_shopping_list", list_id=groceries["id"]))["name"].endswith("!")

    await invoke(
        "create_shopping_list_items_bulk",
        items=[
            {"shopping_list_id": groceries["id"], "note": "Apples", "quantity": 3},
            {"shopping_list_id": groceries["id"], "note": "Bread"},
        ],
    )
    single = await invoke(
        "create_shopping_list_item", shopping_list_id=groceries["id"], note="Milk"
    )
    assert single

    items = {i["note"]: i for i in (await invoke("get_shopping_list", list_id=groceries["id"]))["listItems"]}
    assert set(items) == {"Apples", "Bread", "Milk"}
    assert items["Apples"]["quantity"] == 3

    await invoke("update_shopping_list_item", item_id=items["Milk"]["id"], checked=True)
    await invoke(
        "update_shopping_list_items_bulk",
        items=[{"id": items["Bread"]["id"], "quantity": 2}],
    )
    milk = await invoke("get_shopping_list_item", item_id=items["Milk"]["id"])
    bread = await invoke("get_shopping_list_item", item_id=items["Bread"]["id"])
    assert milk["checked"] is True
    assert (bread["quantity"], bread["note"]) == (2, "Bread")

    await invoke("delete_shopping_list_item", item_id=items["Milk"]["id"])
    await invoke(
        "delete_shopping_list_items_bulk",
        item_ids=[items["Apples"]["id"], items["Bread"]["id"]],
    )
    assert (await invoke("get_shopping_list", list_id=groceries["id"]))["listItems"] == []


async def test_add_and_remove_recipe_on_shopping_list(invoke, recipe, shopping_list):
    created = await recipe("Listed", ingredients=["1 onion", "2 carrots"])
    stored = await invoke("get_recipe", slug=created["slug"])
    groceries = await shopping_list("Recipe List")

    await invoke("add_recipe_to_shopping_list", list_id=groceries["id"], recipe_id=stored["id"])
    listed = await invoke("get_shopping_list", list_id=groceries["id"])
    assert len(listed["listItems"]) == 2
    assert [r["recipeId"] for r in listed["recipeReferences"]] == [stored["id"]]

    await invoke("remove_recipe_from_shopping_list", list_id=groceries["id"], recipe_id=stored["id"])
    assert (await invoke("get_shopping_list", list_id=groceries["id"]))["listItems"] == []


# --- meal plans -------------------------------------------------------------


async def test_bulk_mealplans_and_date_filter(invoke, live_fetcher, cleanup):
    result = await invoke(
        "create_mealplan_bulk",
        entries=[
            {"date": "2031-05-01", "title": "Soup", "entry_type": "lunch"},
            {"date": "2031-05-02", "title": "Curry", "entry_type": "dinner"},
        ],
    )
    assert result["message"] == "Successfully created 2 mealplan entries"
    plans = await invoke("get_all_mealplans", start_date="2031-05-01", end_date="2031-05-02")
    titles = {p["title"]: p for p in plans["items"]}
    for entry in titles.values():
        cleanup(lambda entry=entry: live_fetcher.delete_mealplan(entry["id"]))
    assert set(titles) == {"Soup", "Curry"}

    await invoke("update_mealplan", entry_id=titles["Soup"]["id"], title="Stew")
    after = await invoke("get_all_mealplans", start_date="2031-05-01", end_date="2031-05-01")
    assert [p["title"] for p in after["items"]] == ["Stew"]


async def test_todays_mealplan(invoke, mealplan_entry):
    entry = await mealplan_entry(date=date.today().isoformat(), title="Today's Lunch", entry_type="lunch")
    today = await invoke("get_todays_mealplan")
    assert entry["id"] in [e["id"] for e in today]
