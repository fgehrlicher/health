import os
from decimal import Decimal

import psycopg
import pytest
from health_api.catalog.models import FoodInput
from health_api.catalog.registration import barcode_problem, check_food, slugify
from test_catalog import request

# Milbona High Protein Quark-Creme, as read from test-data label photos.
QUARK = {
    "name": "High Protein Quark-Creme Pfirsich-Maracuja",
    "brand": "Milbona",
    "barcode": "4335619151215",
    # Placeholder: the photos show only part of the real list.
    "ingredients_text": "50% Speisequark, 40% Joghurterzeugnis, Maracujasaftkonzentrat, Stärke",
    "nutrition": {
        "energy_kj": "287",
        "energy_kcal": "68",
        "fat_g": "0.4",
        "saturated_fat_g": "0.3",
        "carbs_g": "3.5",
        "sugars_g": "3.0",
        "fiber_g": "0.2",
        "protein_g": "12.4",
        "salt_g": "0.13",
    },
    "portions": [
        {"name": "Portion", "kind": "serving", "quantity": "200", "unit": "g"},
        {"name": "Becher", "kind": "package", "quantity": "400", "unit": "g"},
    ],
}


def quark(**nutrition) -> FoodInput:
    return FoodInput.model_validate(QUARK | {"nutrition": QUARK["nutrition"] | nutrition})


def test_barcodes_need_valid_check_digit_and_public_prefix():
    assert barcode_problem("4335619151215") is None
    assert barcode_problem("96385074") is None
    assert "check digit" in barcode_problem("4335619151216")
    assert "store-internal" in barcode_problem("2012345678903")
    assert "digits" in barcode_problem("43356191512")
    assert "digits" in barcode_problem("43356191512１5")


def test_consistent_label_passes_without_warnings():
    assert check_food(quark()) == ([], [])


@pytest.mark.parametrize(
    ("misread", "field"),
    [
        ({"protein_g": "17.4"}, "nutrition.energy_kcal"),
        ({"energy_kj": "827"}, "nutrition.energy_kj"),
        ({"saturated_fat_g": "3"}, "nutrition.saturated_fat_g"),
        ({"sugars_g": "30"}, "nutrition.sugars_g"),
    ],
)
def test_misread_label_values_are_errors(misread, field):
    errors, _warnings = check_food(quark(**misread))
    assert field in [error["field"] for error in errors]


def test_missing_mandatory_rows_warn():
    food = FoodInput.model_validate(
        QUARK
        | {
            "nutrition": {
                key: QUARK["nutrition"][key]
                for key in ("energy_kcal", "fat_g", "carbs_g", "protein_g")
            }
        }
    )
    errors, warnings = check_food(food)
    assert errors == []
    assert {w["field"] for w in warnings} >= {"nutrition.salt_g", "nutrition.sugars_g"}
    food = FoodInput.model_validate({**QUARK, "ingredients_text": None})
    assert [w["field"] for w in check_food(food)[1]] == ["ingredients_text"]
    assert check_food(FoodInput.model_validate({**QUARK, "ingredients_text": "  "}))[0]


def test_slugs_transliterate_german():
    assert (
        slugify("Müller Joghurt mit Früchten, 3,5 % Fett")
        == "mueller-joghurt-mit-fruechten-3-5-fett"
    )
    assert slugify("  ") == "food"


def test_register_and_find_by_barcode(monkeypatch):
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("set TEST_DATABASE_URL for PostgreSQL integration coverage")
    monkeypatch.setenv("DATABASE_URL", database_url)
    barcode = "4000000000006"  # valid check digit, not a real product
    payload = QUARK | {"name": "Registration test food", "brand": None, "barcode": barcode}
    try:
        dry = request_json("POST", "/api/foods?dry_run=true", payload)
        assert dry.status_code == 200 and dry.json()["food"] is None
        assert request(f"/api/foods/barcode/{barcode}").status_code == 404

        created = request_json("POST", "/api/foods", payload)
        assert created.status_code == 201, created.text
        food = created.json()["food"]
        assert food["kind"] == "branded" and food["barcode"] == barcode
        assert food["sources"][0]["source_name"] == "Product label"
        assert food["sources"][0]["energy_kj"] == "287"
        assert food["sources"][0]["ingredients_text"] == QUARK["ingredients_text"]
        assert [p["name"] for p in food["portions"]] == ["Portion", "Becher"]

        assert request(f"/api/foods/barcode/{barcode}").json()["slug"] == food["slug"]
        search = request("/api/foods?q=registration%20test").json()["items"]
        assert search[0]["slug"] == food["slug"]
        source_path = f"/api/foods/{food['slug']}/sources/{food['sources'][0]['id']}"
        patched = request_json(
            "PATCH", source_path, {"food_name": "Test legal name", "ingredients_text": " Quark "}
        )
        assert patched.status_code == 200, patched.text
        assert patched.json()["sources"][0]["food_name"] == "Test legal name"
        assert patched.json()["sources"][0]["ingredients_text"] == "Quark"
        assert patched.json()["sources"][0]["energy_kcal"] == "68"
        assert request_json("PATCH", source_path, {}).status_code == 422
        assert request_json("PATCH", source_path, {"energy_kcal": 1}).status_code == 422
        assert request_json("PATCH", f"{source_path}0", {"food_name": "x"}).status_code == 404
        bls = request("/api/foods/bls4-f110100").json()["sources"][0]["id"]
        bls_patch = request_json(
            "PATCH", f"/api/foods/bls4-f110100/sources/{bls}", {"food_name": "x"}
        )
        assert bls_patch.status_code == 422

        conflict = request_json("POST", "/api/foods", payload)
        assert conflict.status_code == 409 and conflict.json()["slug"] == food["slug"]
    finally:
        with psycopg.connect(database_url) as connection:
            connection.execute("DELETE FROM foods WHERE barcode = %s", (barcode,))
            connection.execute("REFRESH MATERIALIZED VIEW food_search_terms")
            connection.execute("REFRESH MATERIALIZED VIEW food_search_vocabulary")


def test_invalid_submission_is_rejected_with_issues():
    response = request_json("POST", "/api/foods", QUARK | {"barcode": "4335619151216"})
    assert response.status_code == 422
    assert response.json()["detail"][0]["field"] == "barcode"
    assert request("/api/foods/barcode/123").status_code == 422


def request_json(method: str, path: str, payload: dict):
    import asyncio

    import httpx
    from health_api.app import app

    async def send():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.request(method, path, json=payload)

    return asyncio.run(send())


def test_energy_check_uses_eu_factors():
    from health_api.catalog.registration import energy_from_macros

    assert energy_from_macros(quark().nutrition) == Decimal("67.6")
