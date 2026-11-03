"""Tests for cookbook, recipe rating, meal plan rule, and random meal tools."""

import logging

import pytest
from mcp.server.fastmcp.exceptions import ToolError

COOKBOOKS = "/api/households/cookbooks"
RULES = "/api/households/mealplans/rules"
CURRENT_COOKBOOK = {
    "id": "cb-1",
    "name": "Quick",
    "slug": "quick",
    "description": "Fast food",
    "position": 2,
    "public": False,
    "queryFilterString": "totalTimeSeconds <= 1800",
    "groupId": "group-1",
    "householdId": "household-1",
    "queryFilter": {"parts": []},
}
CURRENT_RULE = {
    "id": "rule-1",
    "day": "monday",
    "entryType": "dinner",
    "queryFilterString": "totalTimeSeconds <= 1800",
    "groupId": "group-1",
    "householdId": "household-1",
    "queryFilter": {"parts": []},
}


def calls(fetcher):
    return [(r["method"], r["url"], r["json"]) for r in fetcher.requests]


# --- ratings ----------------------------------------------------------------


async def test_rate_recipe_posts_to_current_user(invoke, fetcher):
    fetcher.responses["POST", "/api/users/user-1/ratings/pie"] = {"success": True}
    result = await invoke("rate_recipe", slug="pie", rating=4.5, is_favorite=True)
    assert result == {"success": True, "slug": "pie", "rating": 4.5, "isFavorite": True}
    assert calls(fetcher) == [
        ("GET", "/api/users/self", None),
        ("POST", "/api/users/user-1/ratings/pie", {"rating": 4.5, "isFavorite": True}),
    ]


async def test_rate_recipe_sends_only_given_fields(invoke, fetcher):
    fetcher.responses["POST", "/api/users/user-1/ratings/pie"] = {"success": True}
    await invoke("rate_recipe", slug="pie", is_favorite=False)
    assert fetcher.last("POST")["json"] == {"isFavorite": False}


@pytest.mark.parametrize(
    "arguments",
    [{"slug": "pie"}, {"slug": " ", "rating": 3}, {"slug": "pie", "rating": 5.5},
     {"slug": "pie", "rating": -1}],
)
async def test_rate_recipe_validates_before_request(invoke, fetcher, arguments):
    with pytest.raises(ToolError):
        await invoke("rate_recipe", **arguments)
    assert fetcher.requests == []


async def test_rate_recipe_failure_is_tool_error(invoke, fetcher):
    fetcher.fail_on("/ratings/", status_code=404)
    with pytest.raises(ToolError, match="Error rating recipe"):
        await invoke("rate_recipe", slug="missing", rating=3)


async def test_get_my_recipe_ratings(invoke, fetcher):
    ratings = {"ratings": [{"recipeId": "r1", "rating": 4.0, "isFavorite": True}]}
    fetcher.responses["GET", "/api/users/self/ratings"] = ratings
    assert await invoke("get_my_recipe_ratings") == ratings


async def test_get_recipes_filters_by_cookbook(invoke, fetcher):
    await invoke("get_recipes", cookbook="quick")
    assert fetcher.last("GET", "/api/recipes")["params"]["cookbook"] == "quick"


# --- cookbooks --------------------------------------------------------------


async def test_get_cookbooks_forwards_pagination(invoke, fetcher):
    fetcher.responses["GET", COOKBOOKS] = {"items": [CURRENT_COOKBOOK], "total": 1}
    result = await invoke("get_cookbooks", page=2, per_page=5)
    assert result["items"][0]["slug"] == "quick"
    assert fetcher.last()["params"] == {"page": 2, "perPage": 5}


async def test_create_cookbook_payload(invoke, fetcher):
    fetcher.responses["POST", COOKBOOKS] = CURRENT_COOKBOOK
    await invoke("create_cookbook", name="Quick", query_filter="totalTimeSeconds <= 1800")
    assert calls(fetcher) == [
        (
            "POST",
            COOKBOOKS,
            {
                "name": "Quick",
                "queryFilterString": "totalTimeSeconds <= 1800",
                "description": "",
                "public": False,
            },
        )
    ]


async def test_update_cookbook_merges_and_sends_only_writable_fields(invoke, fetcher):
    fetcher.responses["GET", f"{COOKBOOKS}/quick"] = CURRENT_COOKBOOK
    fetcher.responses["PUT", f"{COOKBOOKS}/cb-1"] = {**CURRENT_COOKBOOK, "public": True}
    await invoke("update_cookbook", cookbook_id="quick", public=True)
    assert calls(fetcher)[-1] == (
        "PUT",
        f"{COOKBOOKS}/cb-1",
        {
            "name": "Quick",
            "description": "Fast food",
            "slug": "quick",
            "position": 2,
            "public": True,
            "queryFilterString": "totalTimeSeconds <= 1800",
        },
    )


@pytest.mark.parametrize(
    "tool, arguments",
    [
        ("create_cookbook", {"name": "  "}),
        ("update_cookbook", {"cookbook_id": "cb-1"}),
        ("update_cookbook", {"cookbook_id": "cb-1", "name": ""}),
        ("update_cookbook", {"cookbook_id": " ", "public": True}),
        ("delete_cookbook", {"cookbook_id": ""}),
    ],
)
async def test_cookbook_validation_before_request(invoke, fetcher, tool, arguments):
    with pytest.raises(ToolError):
        await invoke(tool, **arguments)
    assert fetcher.requests == []


async def test_delete_cookbook(invoke, fetcher):
    fetcher.responses["DELETE", f"{COOKBOOKS}/cb-1"] = CURRENT_COOKBOOK
    await invoke("delete_cookbook", cookbook_id="cb-1")
    assert calls(fetcher) == [("DELETE", f"{COOKBOOKS}/cb-1", None)]


async def test_invalid_cookbook_filter_is_tool_error_without_content(
    invoke, fetcher, caplog
):
    caplog.set_level(logging.DEBUG, logger="mealie-mcp")
    fetcher.fail_on(COOKBOOKS, status_code=422, message="private-filter invalid")
    with pytest.raises(ToolError, match="Error creating cookbook") as error:
        await invoke("create_cookbook", name="private-name", query_filter="private-filter")
    assert "private" not in str(error.value)
    assert "private" not in caplog.text


# --- meal plan rules --------------------------------------------------------


async def test_create_rule_defaults_to_any_day_and_meal(invoke, fetcher):
    fetcher.responses["POST", RULES] = CURRENT_RULE
    await invoke("create_mealplan_rule", query_filter="rating >= 4")
    assert calls(fetcher) == [
        ("POST", RULES, {"day": "unset", "entryType": "unset", "queryFilterString": "rating >= 4"})
    ]


async def test_update_rule_keeps_omitted_fields(invoke, fetcher):
    fetcher.responses["GET", f"{RULES}/rule-1"] = CURRENT_RULE
    fetcher.responses["PUT", f"{RULES}/rule-1"] = CURRENT_RULE
    await invoke("update_mealplan_rule", rule_id="rule-1", day="friday")
    assert calls(fetcher)[-1] == (
        "PUT",
        f"{RULES}/rule-1",
        {"day": "friday", "entryType": "dinner", "queryFilterString": "totalTimeSeconds <= 1800"},
    )


async def test_update_rule_can_clear_the_filter(invoke, fetcher):
    fetcher.responses["GET", f"{RULES}/rule-1"] = CURRENT_RULE
    fetcher.responses["PUT", f"{RULES}/rule-1"] = CURRENT_RULE
    await invoke("update_mealplan_rule", rule_id="rule-1", query_filter="")
    assert fetcher.last("PUT")["json"]["queryFilterString"] == ""


@pytest.mark.parametrize(
    "tool, arguments",
    [
        ("create_mealplan_rule", {"day": "someday"}),
        ("create_mealplan_rule", {"entry_type": "brunch"}),
        ("update_mealplan_rule", {"rule_id": "rule-1"}),
        ("update_mealplan_rule", {"rule_id": " ", "day": "monday"}),
        ("delete_mealplan_rule", {"rule_id": ""}),
    ],
)
async def test_rule_validation_before_request(invoke, fetcher, tool, arguments):
    with pytest.raises(ToolError):
        await invoke(tool, **arguments)
    assert fetcher.requests == []


async def test_get_and_delete_rules(invoke, fetcher):
    fetcher.responses["GET", RULES] = {"items": [CURRENT_RULE]}
    fetcher.responses["DELETE", f"{RULES}/rule-1"] = CURRENT_RULE
    assert (await invoke("get_mealplan_rules"))["items"][0]["id"] == "rule-1"
    await invoke("delete_mealplan_rule", rule_id="rule-1")
    assert calls(fetcher)[-1] == ("DELETE", f"{RULES}/rule-1", None)


# --- random meal ------------------------------------------------------------


async def test_random_mealplan_payload(invoke, fetcher):
    entry = {"id": 3, "date": "2030-03-02", "entryType": "snack", "recipeId": "r1"}
    fetcher.responses["POST", "/api/households/mealplans/random"] = entry
    assert await invoke("create_random_mealplan", date="2030-03-02", entry_type="snack") == entry
    assert calls(fetcher) == [
        ("POST", "/api/households/mealplans/random", {"date": "2030-03-02", "entryType": "snack"})
    ]


@pytest.mark.parametrize(
    "arguments", [{"date": "2030-02-30"}, {"date": "2030-03-02", "entry_type": "brunch"}]
)
async def test_random_mealplan_validates_before_request(invoke, fetcher, arguments):
    with pytest.raises(ToolError):
        await invoke("create_random_mealplan", **arguments)
    assert fetcher.requests == []


async def test_random_mealplan_without_recipes_is_tool_error(invoke, fetcher):
    fetcher.fail_on("/random", status_code=404)
    with pytest.raises(ToolError, match="Error creating random mealplan entry"):
        await invoke("create_random_mealplan", date="2030-03-02")


async def test_mealplan_accepts_new_meal_types(invoke, fetcher):
    await invoke("create_mealplan", date="2030-03-02", title="Cake", entry_type="dessert")
    assert fetcher.last("POST")["json"]["entryType"] == "dessert"
