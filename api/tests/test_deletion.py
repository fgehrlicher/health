"""Deleting a registered product: its uses move to a replacement first."""

import os

import psycopg
import pytest
from test_registration import QUARK, request_json

PRODUCT = "4000000000082"  # valid check digits, not real products
DRINK = "4000000000099"


def test_a_used_product_is_deleted_only_with_a_replacement(monkeypatch):
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("set TEST_DATABASE_URL for PostgreSQL integration coverage")
    monkeypatch.setenv("DATABASE_URL", database_url)
    with psycopg.connect(database_url) as connection:
        [generic] = connection.execute(
            """SELECT f.slug FROM catalog.foods f JOIN catalog.food_sources s ON s.food_id = f.id
               WHERE s.source_name = 'BLS 4.0' AND s.reference_unit = 'g'
               ORDER BY f.id LIMIT 1"""
        ).fetchone()
    product = QUARK | {"name": "Deletion test quark", "brand": None, "barcode": PRODUCT}
    drink = QUARK | {
        "name": "Deletion test drink",
        "brand": None,
        "barcode": DRINK,
        "nutrition": QUARK["nutrition"] | {"reference_unit": "ml"},
        "portions": [],
    }
    created = {}
    try:
        slug = request_json("POST", "/api/foods", product).json()["food"]["slug"]
        drink_slug = request_json("POST", "/api/foods", drink).json()["food"]["slug"]
        meal = request_json("POST", "/api/log/meals", {"items": [{"food": slug, "amount": 200}]})
        created["meal"] = meal.json()["id"]
        recipe = request_json(
            "POST",
            "/api/recipes",
            {"name": "Deletion test bowl", "portions": 2, "items": [{"food": slug, "amount": 300}]},
        )
        created["recipe"] = recipe.json()["slug"]
        cook = request_json("POST", "/api/cooks", {"recipe": created["recipe"]})
        created["cook"] = cook.json()["id"]

        # A dry run reports the uses and changes nothing.
        dry = request_json("DELETE", f"/api/foods/{slug}?dry_run=true", None)
        assert dry.status_code == 200, dry.text
        assert dry.json()["uses"] == {"meals": 1, "recipes": 1, "cooks": 1}
        assert dry.json()["blocked"] is True

        refused = request_json("DELETE", f"/api/foods/{slug}", None)
        assert refused.status_code == 409
        assert refused.json()["uses"] == {"meals": 1, "recipes": 1, "cooks": 1}

        # The amounts are in g; a food per ml cannot take them.
        wrong_unit = request_json("DELETE", f"/api/foods/{slug}?replace_with={drink_slug}", None)
        assert wrong_unit.status_code == 422
        assert "per g" in wrong_unit.json()["detail"][0]["message"]
        itself = request_json("DELETE", f"/api/foods/{slug}?replace_with={slug}", None)
        assert itself.status_code == 422
        assert request_json("GET", f"/api/foods/{slug}", None).status_code == 200

        deleted = request_json("DELETE", f"/api/foods/{slug}?replace_with={generic}", None)
        assert deleted.status_code == 200, deleted.text
        assert deleted.json() == {
            "slug": slug,
            "replaced_with": generic,
            "uses": {"meals": 1, "recipes": 1, "cooks": 1},
            "blocked": False,
        }
        assert request_json("GET", f"/api/foods/{slug}", None).status_code == 404

        # Every use now points at the replacement, with the same amount.
        [item] = request_json("GET", f"/api/log/meals/{created['meal']}", None).json()["items"]
        assert (item["food"], item["amount"]) == (generic, "200")
        [ingredient] = request_json("GET", f"/api/recipes/{created['recipe']}", None).json()[
            "versions"
        ][0]["items"]
        assert ingredient["food"] == generic
        [cooked] = request_json("GET", f"/api/cooks/{created['cook']}", None).json()["items"]
        assert cooked["food"] == generic

        # An unused product goes without a replacement; generic foods never go.
        assert request_json("DELETE", f"/api/foods/{drink_slug}", None).status_code == 200
        assert request_json("DELETE", f"/api/foods/{generic}", None).status_code == 422
        assert request_json("DELETE", "/api/foods/no-such-food", None).status_code == 404
    finally:
        if "meal" in created:
            request_json("DELETE", f"/api/log/meals/{created['meal']}", None)
        if "cook" in created:
            request_json("DELETE", f"/api/cooks/{created['cook']}", None)
        if "recipe" in created:
            request_json("DELETE", f"/api/recipes/{created['recipe']}", None)
        with psycopg.connect(database_url) as connection:
            connection.execute(
                "DELETE FROM catalog.foods WHERE barcode = ANY(%s)", ([PRODUCT, DRINK],)
            )
            connection.execute("SELECT catalog.refresh_search()")
