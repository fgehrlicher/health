import os
from decimal import Decimal

import psycopg
import pytest
from health_api.ingredients import changes
from health_api.log.meals import ItemInput
from health_api.recipes.cooks import CookInput
from pydantic import ValidationError
from test_catalog import request
from test_registration import request_json

RICE = "bls4-c352032"
BROCCOLI = "bls4-g312132"
COCONUT_MILK = "bls4-h154000"
CHICKEN = "bls4-v4a6100"


@pytest.mark.parametrize(
    "item",
    [
        {"cook": 1},
        {"cook": 1, "food": RICE, "amount": 1},
        {"cook": 1, "amount": 1, "portion": "Becher"},
        {"cook": 1, "amount": 1, "source_id": 3},
        {"amount": 1},
    ],
)
def test_meal_items_are_a_food_or_portions_of_a_cook(item):
    with pytest.raises(ValidationError):
        ItemInput.model_validate(item)


def test_meal_items_accept_portions_of_a_cook():
    item = ItemInput.model_validate({"cook": 7, "amount": "1.5", "estimated": True})
    assert item.cook == 7 and item.amount == Decimal("1.5")


def test_cooks_split_into_at_most_100_portions():
    assert CookInput.model_validate({"recipe": "curry", "portions": 4}).portions == 4
    for portions in (0, 101):
        with pytest.raises(ValidationError):
            CookInput.model_validate({"recipe": "curry", "portions": portions})


def amount(grams, food, unit="g", variant_of=None):
    return {
        "amount": Decimal(grams),
        "food": food,
        "food_name": food,
        "unit": unit,
        "variant_of": variant_of,
    }


def short(change):
    side = lambda parts: [(p["food"], p["amount"]) for p in parts]
    return side(change["planned"]), side(change["actual"])


def test_changes_list_only_ingredients_whose_amount_differs():
    planned = [amount(250, "coconut"), amount(400, "chicken"), amount(5, "salt")]
    actual = [amount(400, "coconut"), amount(400, "chicken"), amount(10, "chili")]
    assert [short(c) for c in changes(planned, actual)] == [
        ([("coconut", "250")], [("coconut", "400")]),
        ([("salt", "5")], []),
        ([], [("chili", "10")]),
    ]


def test_a_branded_variant_replaces_its_generic_food_as_one_change():
    planned = [amount(500, "soy-drink"), amount(5, "salt")]
    actual = [amount(500, "alpro-soy", "ml", variant_of="soy-drink"), amount(5, "salt")]
    assert [short(c) for c in changes(planned, actual)] == [
        ([("soy-drink", "500")], [("alpro-soy", "500")])
    ]
    # The same variant in both lists is no change.
    assert changes(actual, actual) == []


def total(totals: dict, column: str) -> Decimal:
    return Decimal(totals[column]["measured"]) + Decimal(totals[column]["estimated"])


def test_recipes_cooks_and_eating_from_a_cook(monkeypatch):
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("set TEST_DATABASE_URL for PostgreSQL integration coverage")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("HEALTH_TIMEZONE", "Europe/Berlin")
    slugs, cook_ids, meal_ids = [], [], []
    try:
        created = request_json(
            "POST",
            "/api/recipes",
            {
                "name": "Test curry",
                "portions": 4,
                "instructions": "Fry, add coconut milk, simmer.",
                "items": [
                    {"food": CHICKEN, "amount": 400},
                    {"food": COCONUT_MILK, "amount": 250},
                    {"food": RICE, "amount": 600},
                ],
            },
        )
        assert created.status_code == 201, created.text
        curry = created.json()
        slugs.append(curry["slug"])
        assert curry["slug"] == "test-curry"
        v1 = curry["versions"][0]
        assert v1["number"] == 1 and v1["parent"] is None and v1["status"] == "measured"
        assert total(v1["per_portion"], "energy_kcal") == pytest.approx(
            total(v1["totals"], "energy_kcal") / 4, abs=1
        )

        # A new version keeps the steps and records why it changed.
        v2 = request_json(
            "POST",
            f"/api/recipes/{curry['slug']}/versions",
            {
                "note": "more vegetables",
                "items": [
                    {"food": CHICKEN, "amount": 400},
                    {"food": COCONUT_MILK, "amount": 250},
                    {"food": RICE, "amount": 600},
                    {"food": BROCCOLI, "amount": 300},
                ],
            },
        )
        assert v2.status_code == 201, v2.text
        assert v2.json()["number"] == 2 and v2.json()["parent"]["number"] == 1
        assert v2.json()["instructions"] == "Fry, add coconut milk, simmer."
        assert v2.json()["portions"] == "4"
        assert [short(c) for c in v2.json()["changes"]] == [([], [(BROCCOLI, "300")])]

        # The cook uses the whole can and splits the pot into 5 portions.
        cooked = request_json(
            "POST",
            "/api/cooks",
            {
                "recipe": curry["slug"],
                "cooked_at": "2026-01-19T19:00",
                "portions": 5,
                "note": "too watery",
                "items": [
                    {"food": CHICKEN, "amount": 400},
                    {"food": COCONUT_MILK, "amount": 400},
                    {"food": RICE, "amount": 600},
                    {"food": BROCCOLI, "amount": 300},
                ],
            },
        )
        assert cooked.status_code == 201, cooked.text
        cook = cooked.json()
        cook_ids.append(cook["id"])
        assert cook["version"] == 2 and cook["name"] == "Test curry"
        assert [short(c) for c in cook["changes"]] == [
            ([(COCONUT_MILK, "250")], [(COCONUT_MILK, "400")])
        ]
        assert cook["portions_left"] == "5"

        # Without items, a cook uses the version's ingredients.
        plain = request_json("POST", "/api/cooks", {"recipe": curry["slug"], "version": 1})
        assert plain.status_code == 201, plain.text
        cook_ids.append(plain.json()["id"])
        assert plain.json()["changes"] == [] and plain.json()["portions"] == "4"

        lunch = request_json(
            "POST",
            "/api/log/meals",
            {
                "eaten_at": "2026-01-20T12:30",
                "kind": "lunch",
                "items": [{"cook": cook["id"], "amount": 1}, {"food": BROCCOLI, "amount": 100}],
            },
        )
        assert lunch.status_code == 201, lunch.text
        meal_ids.append(lunch.json()["id"])
        item = lunch.json()["items"][0]
        assert item["unit"] == "portion" and item["food"] is None
        assert item["recipe"] == {"slug": curry["slug"], "name": "Test curry"}
        assert item["cooked_at"].startswith("2026-01-19T19:00")
        per_portion = total(cook["per_portion"], "energy_kcal")
        assert Decimal(item["nutrition"]["energy_kcal"]) == pytest.approx(per_portion, abs=1)
        assert request(f"/api/cooks/{cook['id']}").json()["portions_left"] == "4"

        # Correcting the cook corrects what was eaten from it.
        corrected = request_json("PATCH", f"/api/cooks/{cook['id']}", {"portions": 4})
        assert corrected.status_code == 200, corrected.text
        meal = request(f"/api/log/meals/{lunch.json()['id']}").json()
        assert Decimal(meal["items"][0]["nutrition"]["energy_kcal"]) == pytest.approx(
            total(corrected.json()["totals"], "energy_kcal") / 4, abs=1
        )

        found = request("/api/cooks?q=curry&since=2026-01-19&until=2026-01-19").json()
        assert [c["id"] for c in found] == [cook["id"]]
        assert cook["id"] not in [c["id"] for c in request("/api/cooks?until=2026-01-18").json()]

        # A cook that turned out well becomes the next version.
        v3 = request_json(
            "POST",
            f"/api/recipes/{curry['slug']}/versions",
            {"from_cook": cook["id"], "note": "the whole can works"},
        )
        assert v3.status_code == 201, v3.text
        assert v3.json()["parent"]["number"] == 2 and v3.json()["from_cook_id"] == cook["id"]
        assert v3.json()["portions"] == "4"
        assert {i["food"]: i["amount"] for i in v3.json()["items"]}[COCONUT_MILK] == "400"

        # A fork develops another recipe from a version.
        fork = request_json(
            "POST",
            "/api/recipes",
            {
                "name": "Test curry with tofu",
                "forked_from": {"recipe": curry["slug"], "version": 2},
            },
        )
        assert fork.status_code == 201, fork.text
        slugs.insert(0, fork.json()["slug"])
        assert fork.json()["versions"][0]["parent"] == {
            "recipe": curry["slug"],
            "recipe_name": "Test curry",
            "number": 2,
        }
        assert len(fork.json()["versions"][0]["items"]) == 4
        detail = request(f"/api/recipes/{curry['slug']}").json()
        assert [v["number"] for v in detail["versions"]] == [3, 2, 1]
        assert detail["forks"] == [
            {"slug": fork.json()["slug"], "name": "Test curry with tofu", "from_version": 2}
        ]
        assert len(detail["cooks"]) == 2
        listed = {r["slug"]: r for r in request("/api/recipes?q=test%20curry").json()}
        assert listed[curry["slug"]]["latest_version"] == 3 and listed[curry["slug"]]["cooks"] == 2

        # An improvised cook needs everything a recipe would give.
        missing = request_json("POST", "/api/cooks", {"note": "fridge leftovers"})
        assert missing.status_code == 422
        assert [i["field"] for i in missing.json()["detail"]] == ["name", "portions", "items"]
        improvised = request_json(
            "POST",
            "/api/cooks",
            {
                "name": "Test fried rice",
                "portions": 2,
                "items": [{"food": RICE, "amount": 400, "estimated": True}],
            },
        )
        assert improvised.status_code == 201, improvised.text
        cook_ids.append(improvised.json()["id"])
        assert improvised.json()["recipe"] is None and improvised.json()["status"] == "estimated"
        saved = request_json(
            "POST",
            "/api/recipes",
            {"name": "Test fried rice", "from_cook": improvised.json()["id"]},
        )
        assert saved.status_code == 201, saved.text
        slugs.insert(0, saved.json()["slug"])
        linked = request(f"/api/cooks/{improvised.json()['id']}").json()
        assert linked["recipe"]["slug"] == saved.json()["slug"] and linked["version"] == 1

        errors = request_json(
            "POST",
            "/api/log/meals",
            {"items": [{"cook": 0, "amount": 1}, {"cook": cook["id"], "amount": 21}]},
        )
        assert [i["field"] for i in errors.json()["detail"]] == ["items.0.cook", "items.1"]
        assert request_json("DELETE", f"/api/cooks/{cook['id']}", None).status_code == 409
        assert request_json("DELETE", f"/api/recipes/{curry['slug']}", None).status_code == 409
        assert (
            request_json(
                "PATCH", f"/api/recipes/{curry['slug']}/versions/1", {"note": "first"}
            ).json()["note"]
            == "first"
        )
        dry = request_json("POST", "/api/recipes?dry_run=true", {"name": "Dry", "items": []})
        assert dry.status_code == 422
    finally:
        with psycopg.connect(database_url) as connection:
            connection.execute(
                """DELETE FROM log.meals WHERE id = ANY(%s)
                   OR id IN (SELECT meal_id FROM log.meal_items WHERE cook_id = ANY(%s))""",
                (meal_ids, cook_ids),
            )
            connection.execute("DELETE FROM recipe.cooks WHERE id = ANY(%s)", (cook_ids,))
            connection.execute("DELETE FROM recipe.recipes WHERE slug = ANY(%s)", (slugs,))


def test_branded_variants_of_a_generic_food(monkeypatch):
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("set TEST_DATABASE_URL for PostgreSQL integration coverage")
    monkeypatch.setenv("DATABASE_URL", database_url)
    soy = "bls4-h841100"  # Soya drink unsweetened
    barcode = "4000000000037"  # valid check digit, not a real product
    product = {
        "name": "Test soy drink",
        "brand": "Test",
        "barcode": barcode,
        "food_group": "H",
        "variant_of": soy,
        "nutrition": {
            "reference_unit": "ml",
            "energy_kcal": 33,
            "fat_g": 1.8,
            "carbs_g": 0.2,
            "protein_g": 3.3,
        },
    }
    slugs, cook_ids = [], []
    try:
        created = request_json("POST", "/api/foods", product)
        assert created.status_code == 201, created.text
        branded = created.json()["food"]
        assert branded["variant_of"] == {"slug": soy, "name": "Soya drink unsweetened"}
        generic = request(f"/api/foods/{soy}").json()
        assert [v["slug"] for v in generic["variants"]] == [branded["slug"]]
        assert generic["variants"][0]["reference_unit"] == "ml"
        assert generic["variant_of"] is None

        # Only a branded product points at a generic food.
        for slug, target in ((soy, soy), (branded["slug"], branded["slug"])):
            wrong = request_json("PATCH", f"/api/foods/{slug}", {"variant_of": target})
            assert wrong.status_code == 422, wrong.text
        cleared = request_json("PATCH", f"/api/foods/{branded['slug']}", {"variant_of": None})
        assert cleared.json()["variant_of"] is None
        request_json("PATCH", f"/api/foods/{branded['slug']}", {"variant_of": soy})

        # The recipe names soy drink; the pot got the product: one swap.
        recipe = request_json(
            "POST",
            "/api/recipes",
            {"name": "Test porridge", "portions": 1, "items": [{"food": soy, "amount": 300}]},
        ).json()
        slugs.append(recipe["slug"])
        assert recipe["versions"][0]["items"][0]["variants"] == 1
        cook = request_json(
            "POST",
            "/api/cooks",
            {"recipe": recipe["slug"], "items": [{"food": branded["slug"], "amount": 300}]},
        ).json()
        cook_ids.append(cook["id"])
        assert cook["items"][0]["variant_of"] == soy
        assert [short(c) for c in cook["changes"]] == [([(soy, "300")], [(branded["slug"], "300")])]
        assert total(cook["per_portion"], "energy_kcal") == 99
    finally:
        with psycopg.connect(database_url) as connection:
            connection.execute("DELETE FROM recipe.cooks WHERE id = ANY(%s)", (cook_ids,))
            connection.execute("DELETE FROM recipe.recipes WHERE slug = ANY(%s)", (slugs,))
            connection.execute("DELETE FROM catalog.foods WHERE barcode = %s", (barcode,))
            connection.execute("SELECT catalog.refresh_search()")
