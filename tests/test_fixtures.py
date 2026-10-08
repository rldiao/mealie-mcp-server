from copy import deepcopy

import pytest

from conftest import BASE_RECIPE, FakeFetcher


@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "PATCH", "DELETE"])
def test_fake_rejects_unhandled_requests(fetcher, method):
    with pytest.raises(AssertionError, match="Unhandled fake request"):
        fetcher._handle_request(method, "/api/unknown")


def test_recipe_fixtures_are_isolated(fetcher):
    original = deepcopy(BASE_RECIPE)
    second = FakeFetcher()
    fetcher.recipe["settings"]["showAssets"] = False
    response = second._handle_request("GET", "/api/recipes/test-recipe")
    response["settings"]["showNutrition"] = False
    assert second.recipe == original
    assert BASE_RECIPE == original


def test_fake_records_independent_payloads(fetcher):
    payload = {"settings": {"showAssets": False}}
    response = fetcher._handle_request("PATCH", "/api/recipes/test-recipe", json=payload)
    payload["settings"]["showAssets"] = True
    response["settings"]["showAssets"] = True
    assert fetcher.last()["json"] == {"settings": {"showAssets": False}}


def test_fake_response_overrides_are_isolated(fetcher):
    response = {"name": "Original", "extras": {"source": "test"}}
    fetcher.responses["GET", "/api/foods/f1"] = response
    fetched = fetcher._handle_request("GET", "/api/foods/f1")
    fetched["extras"]["source"] = "changed"
    assert response["extras"]["source"] == "test"
