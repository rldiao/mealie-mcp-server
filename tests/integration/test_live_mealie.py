"""End-to-end checks of the MCP tools against a real Mealie (see conftest.py)."""

import httpx
import pytest
from mcp.server.fastmcp.exceptions import ToolError


async def test_server_is_the_expected_version(live_fetcher):
    about = live_fetcher._handle_request("GET", "/api/app/about")
    assert about["version"].startswith("v3.")


# --- structured recipe times and query filters ------------------------------


async def test_structured_times_round_trip_and_filter(invoke, recipe):
    quick = await recipe(
        "Quick Soup",
        total_time="25 min",
        total_time_seconds=1500,
        prep_time_seconds=600,
        perform_time_seconds=900,
    )
    slow = await recipe("Slow Stew", total_time_seconds=3 * 3600)

    stored = await invoke("get_recipe", slug=quick["slug"])
    assert stored["totalTime"] == "25 min"
    assert stored["totalTimeSeconds"] == 1500
    assert stored["prepTimeSeconds"] == 600
    assert stored["performTimeSeconds"] == 900
    concise = await invoke("get_recipe", slug=quick["slug"], concise=True)
    assert concise["totalTimeSeconds"] == 1500

    found = await invoke(
        "get_recipes",
        query_filter="totalTimeSeconds <= 1800",
        order_by="totalTimeSeconds",
        order_direction="asc",
        per_page=100,
    )
    slugs = [item["slug"] for item in found["items"]]
    assert quick["slug"] in slugs
    assert slow["slug"] not in slugs


async def test_update_recipe_changes_only_structured_time(invoke, recipe):
    created = await recipe("Timed", total_time="1 h", total_time_seconds=3600)
    summary = await invoke("update_recipe", slug=created["slug"], total_time_seconds=2700)
    assert summary["updated_fields"] == ["totalTimeSeconds"]
    stored = await invoke("get_recipe", slug=created["slug"])
    assert stored["totalTimeSeconds"] == 2700
    assert stored["totalTime"] == "1 h"


# --- meal plan recipe scale -------------------------------------------------


async def test_mealplan_recipe_scale(invoke, recipe, mealplan_entry):
    created = await recipe("Planned")
    stored = await invoke("get_recipe", slug=created["slug"])
    entry = await mealplan_entry(
        date="2030-01-15",
        recipe_id=stored["id"],
        entry_type="dinner",
        recipe_scale=2,
    )
    assert entry["recipeScale"] == 2

    updated = await invoke("update_mealplan", entry_id=entry["id"], recipe_scale=1.5)
    assert updated["recipeScale"] == 1.5
    assert updated["entryType"] == "dinner"
    assert updated["recipeId"] == stored["id"]


# --- week-long meal plan entries and step durations (Mealie 3.30) ------------


async def test_week_long_mealplan_entry_needs_include_week_entries(
    invoke, mealplan_entry
):
    entry = await mealplan_entry(
        date="2030-03-04", end_date="2030-03-10", title="Cook sometime this week"
    )
    assert entry["endDate"] == "2030-03-10"

    window = {"start_date": "2030-03-04", "end_date": "2030-03-10"}
    default = await invoke("get_all_mealplans", **window)
    assert entry["id"] not in [item["id"] for item in default["items"]]
    included = await invoke("get_all_mealplans", **window, include_week_entries=True)
    assert entry["id"] in [item["id"] for item in included["items"]]

    renamed = await invoke("update_mealplan", entry_id=entry["id"], title="Renamed")
    assert renamed["endDate"] == "2030-03-10"
    cleared = await invoke("update_mealplan", entry_id=entry["id"], clear_end_date=True)
    assert cleared["endDate"] is None


async def test_recipe_step_duration_round_trip(invoke, recipe):
    created = await recipe(
        "Timed",
        instructions=["Mix.", {"text": "Rest the dough.", "durationSeconds": 600}],
    )
    stored = await invoke("get_recipe", slug=created["slug"])
    steps = stored["recipeInstructions"]
    assert steps[0]["durationSeconds"] is None
    assert steps[1]["durationSeconds"] == 600


# --- organizer merge and unused lookups -------------------------------------


async def test_merge_tags_moves_recipes_and_deletes_duplicate(invoke, recipe, organizer):
    keep = await organizer("tag", "Keep")
    dup = await organizer("tag", "Dup")
    created = await recipe("Tagged", tags=[{"id": dup["id"], "name": dup["name"]}])

    await invoke("merge_organizers", kind="tag", from_id=dup["id"], to_id=keep["id"])

    stored = await invoke("get_recipe", slug=created["slug"])
    assert [tag["id"] for tag in stored["tags"]] == [keep["id"]]
    with pytest.raises(ToolError):
        await invoke("get_tag", tag_id=dup["id"])


@pytest.mark.parametrize("kind", ["category", "tool", "label", "food", "unit"])
async def test_merge_deletes_the_duplicate(invoke, organizer, kind):
    keep = await organizer(kind, "Keep")
    dup = await organizer(kind, "Dup")

    await invoke("merge_organizers", kind=kind, from_id=dup["id"], to_id=keep["id"])

    getter, key = {
        "category": ("get_category", "category_id"),
        "tool": ("get_tool", "tool_id"),
        "label": ("get_label", "label_id"),
        "food": ("get_food", "food_id"),
        "unit": ("get_unit", "unit_id"),
    }[kind]
    assert (await invoke(getter, **{key: keep["id"]}))["id"] == keep["id"]
    with pytest.raises(ToolError):
        await invoke(getter, **{key: dup["id"]})


@pytest.mark.parametrize("kind, plural", [("tool", "tools"), ("label", "labels"), ("food", "foods")])
async def test_unused_organizers_are_listed(invoke, organizer, kind, plural):
    unused = await organizer(kind, "Unused")
    listed = await invoke(f"get_empty_{plural}")
    assert unused["id"] in [item["id"] for item in listed]


# --- notes linked to steps --------------------------------------------------


async def test_notes_link_to_steps(invoke, recipe):
    created = await recipe(
        "Bread",
        notes=[{"title": "Tip", "text": "Rest the dough.", "referenceId": "tip"}],
        instructions=[
            "Mix.",
            {"text": "Knead.", "noteReferences": [{"referenceId": "tip"}]},
        ],
    )
    stored = await invoke("get_recipe", slug=created["slug"])
    note_id = stored["notes"][0]["referenceId"]
    assert stored["recipeInstructions"][1]["noteReferences"] == [{"referenceId": note_id}]
    assert stored["recipeInstructions"][0].get("noteReferences") in (None, [])


# --- food substitutions -----------------------------------------------------


async def test_food_substitutions_round_trip(invoke, organizer):
    buttermilk = await organizer("food", "Buttermilk")
    milk = await organizer("food", "Milk")

    await invoke(
        "set_food_substitutions",
        food_id=buttermilk["id"],
        substitutions=[
            {"substituteFoodId": milk["id"], "note": "add lemon juice"},
            {"note": "thinned yogurt"},
        ],
    )
    stored = await invoke("get_food", food_id=buttermilk["id"])
    assert [(s.get("substituteFoodId"), s.get("note")) for s in stored["substitutions"]] == [
        (milk["id"], "add lemon juice"),
        (None, "thinned yogurt"),
    ]
    assert stored["name"] == buttermilk["name"]

    await invoke("set_food_substitutions", food_id=buttermilk["id"], substitutions=[])
    assert (await invoke("get_food", food_id=buttermilk["id"]))["substitutions"] == []


# --- iCal feed --------------------------------------------------------------


async def test_ical_feed_enable_rotate_and_disable(
    invoke, live_fetcher, recipe, mealplan_entry, cleanup
):
    created = await recipe("Calendar Dinner")
    stored = await invoke("get_recipe", slug=created["slug"])
    await mealplan_entry(date="2030-02-01", recipe_id=stored["id"], entry_type="dinner")
    cleanup(lambda: live_fetcher.set_mealplan_ical_feed(False))

    first = await invoke("set_mealplan_ical_feed", enabled=True)
    assert first["enabled"] is True
    assert await invoke("get_mealplan_ical_feed") == first

    # the feed is public: no Authorization header
    feed = httpx.get(first["feedUrl"], params={"start_date": "2030-01-01", "end_date": "2030-03-01"})
    assert feed.status_code == 200
    assert feed.headers["content-type"].startswith("text/calendar")
    assert "BEGIN:VCALENDAR" in feed.text
    assert stored["name"] in feed.text

    second = await invoke("set_mealplan_ical_feed", enabled=True)
    assert second["feedUrl"] != first["feedUrl"]
    assert httpx.get(first["feedUrl"]).status_code == 404

    assert await invoke("set_mealplan_ical_feed", enabled=False) == {
        "enabled": False,
        "feedUrl": None,
    }
    assert httpx.get(second["feedUrl"]).status_code == 404


# --- ratings and favorites --------------------------------------------------


async def test_rating_and_favorite_round_trip(invoke, recipe):
    created = await recipe("Rated Pie")
    stored = await invoke("get_recipe", slug=created["slug"])

    await invoke("rate_recipe", slug=created["slug"], rating=4.5, is_favorite=True)
    await invoke("rate_recipe", slug=created["slug"], is_favorite=False)

    mine = {r["recipeId"]: r for r in (await invoke("get_my_recipe_ratings"))["ratings"]}
    assert mine[stored["id"]]["rating"] == 4.5
    assert mine[stored["id"]]["isFavorite"] is False
    assert (await invoke("get_recipe", slug=created["slug"]))["rating"] == 4.5

    found = await invoke("get_recipes", query_filter="rating >= 4", per_page=100)
    assert created["slug"] in [item["slug"] for item in found["items"]]


# --- cookbooks --------------------------------------------------------------


async def test_cookbook_filters_recipes(invoke, live_fetcher, recipe, unique, cleanup):
    quick = await recipe("Quick Salad", total_time_seconds=600)
    slow = await recipe("Slow Roast", total_time_seconds=4 * 3600)

    cookbook = await invoke(
        "create_cookbook", name=unique("Quick"), query_filter="totalTimeSeconds <= 1800"
    )
    cleanup(lambda: live_fetcher.delete_cookbook(cookbook["id"]))
    assert cookbook["id"] in [c["id"] for c in (await invoke("get_cookbooks"))["items"]]

    listed = await invoke("get_recipes", cookbook=cookbook["slug"], per_page=100)
    slugs = [item["slug"] for item in listed["items"]]
    assert quick["slug"] in slugs
    assert slow["slug"] not in slugs

    updated = await invoke("update_cookbook", cookbook_id=cookbook["id"], public=True)
    assert updated["public"] is True
    assert updated["queryFilterString"] == "totalTimeSeconds <= 1800"
    assert updated["name"] == cookbook["name"]


async def test_cookbook_rejects_invalid_filter(invoke, unique):
    with pytest.raises(ToolError, match="HTTP 422"):
        await invoke("create_cookbook", name=unique("Bad"), query_filter="nonsense >= 4")


# --- meal plan rules and random meals ---------------------------------------


async def test_rule_steers_random_meal(invoke, live_fetcher, recipe, unique, cleanup):
    tag = await invoke("create_tag", name=unique("Rule Tag"))
    cleanup(lambda: live_fetcher.delete_tag(tag["id"]))
    target = await recipe("Rule Pick", tags=[{"id": tag["id"], "name": tag["name"]}])
    await recipe("Not Picked")

    rule = await invoke(
        "create_mealplan_rule",
        day="unset",
        entry_type="dessert",
        query_filter=f'tags.id IN ["{tag["id"]}"]',
    )
    cleanup(lambda: live_fetcher.delete_mealplan_rule(rule["id"]))
    assert rule["id"] in [r["id"] for r in (await invoke("get_mealplan_rules"))["items"]]

    for _ in range(3):
        entry = await invoke("create_random_mealplan", date="2030-04-01", entry_type="dessert")
        cleanup(lambda entry=entry: live_fetcher.delete_mealplan(entry["id"]))
        assert entry["entryType"] == "dessert"
        assert entry["recipe"]["slug"] == target["slug"]

    updated = await invoke("update_mealplan_rule", rule_id=rule["id"], day="friday")
    assert updated["day"] == "friday"
    assert updated["entryType"] == "dessert"
    assert updated["queryFilterString"] == rule["queryFilterString"]
