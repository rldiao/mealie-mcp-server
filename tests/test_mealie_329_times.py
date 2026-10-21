"""Mealie 3.29 structured duration compatibility through real MCP tools."""
import pytest


async def test_migrated_recipe_times_survive_concise_read(invoke, fetcher):
    fetcher.recipe.update(totalTime=None, prepTime=None, performTime=None,
                          totalTimeSeconds=2700, prepTimeSeconds=600,
                          performTimeSeconds=2100)
    result = await invoke('get_recipe', slug='test-recipe', concise=True)
    assert result['totalTimeSeconds'] == 2700
    assert result['prepTimeSeconds'] == 600
    assert result['performTimeSeconds'] == 2100


@pytest.mark.parametrize('argument,field', [
    ('total_time', 'totalTime'), ('prep_time', 'prepTime'),
    ('perform_time', 'performTime'),
])
async def test_time_text_replaces_old_structured_duration(invoke, fetcher, argument, field):
    fetcher.recipe.update(totalTimeSeconds=1800, prepTimeSeconds=600,
                          performTimeSeconds=1200)
    await invoke('update_recipe', slug='test-recipe', **{argument: '45 min'})
    body = fetcher.last('PATCH', '/api/recipes/')['json']
    assert body[field] == '45 min'
    assert field + 'Seconds' in body and body[field + 'Seconds'] is None
    assert len(body) == 2


async def test_ingredient_put_retains_structured_durations(invoke, fetcher):
    fetcher.recipe.update(totalTimeSeconds=1800, prepTimeSeconds=600,
                          performTimeSeconds=1200)
    await invoke('update_recipe', slug='test-recipe', ingredients=['synthetic'])
    body = fetcher.last('PUT', '/api/recipes/')['json']
    assert body['totalTimeSeconds'] == 1800
    assert body['prepTimeSeconds'] == 600
    assert body['performTimeSeconds'] == 1200



async def test_legacy_text_times_remain_visible(invoke, fetcher):
    fetcher.recipe.update(totalTime="30 min", prepTime="10 min", performTime="20 min")
    result = await invoke("get_recipe", slug="test-recipe", concise=True)
    assert result["totalTime"] == "30 min"
    assert "totalTimeSeconds" not in result
    assert "prepTimeSeconds" not in result
    assert "performTimeSeconds" not in result


async def test_time_text_and_ingredients_clear_only_selected_duration(invoke, fetcher):
    fetcher.recipe.update(totalTimeSeconds=1800, prepTimeSeconds=600)
    await invoke("update_recipe", slug="test-recipe", total_time="45 min",
                 ingredients=["synthetic"])
    body = fetcher.last("PUT", "/api/recipes/")["json"]
    assert body["totalTime"] == "45 min"
    assert body["totalTimeSeconds"] is None
    assert body["prepTimeSeconds"] == 600


async def test_empty_time_text_clears_structured_duration(invoke, fetcher):
    fetcher.recipe.update(totalTimeSeconds=1800)
    await invoke("update_recipe", slug="test-recipe", total_time="")
    body = fetcher.last("PATCH", "/api/recipes/")["json"]
    assert body == {"totalTime": "", "totalTimeSeconds": None}


async def test_create_recipe_accepts_time_text(invoke, fetcher):
    await invoke("create_recipe", name="Synthetic time", total_time="45 min")
    body = fetcher.last("PUT", "/api/recipes/")["json"]
    assert body["totalTime"] == "45 min"
    assert body["totalTimeSeconds"] is None
