import asyncio
import os
from decimal import Decimal

import httpx
import pytest
from health_catalog.app import app
from health_catalog.repository import FoodFilters, source_from_row


def request(path: str) -> httpx.Response:
    async def get() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.get(path)

    return asyncio.run(get())


def test_frontend_and_assets_are_served():
    page = request("/")
    assert page.status_code == 200
    assert "Food Atlas" in page.text
    assert request("/assets/app.js").status_code == 200
    assert request("/assets/styles.css").status_code == 200


def test_api_rejects_invalid_filters_before_querying_database():
    for path in (
        "/api/foods?limit=0",
        "/api/foods?limit=101",
        "/api/foods?offset=-1",
        "/api/foods?sort=DROP%20TABLE%20foods",
        "/api/foods?min_protein=-1",
    ):
        assert request(path).status_code == 422


def test_openapi_describes_catalog_response():
    schema = request("/openapi.json").json()
    response = schema["paths"]["/api/foods"]["get"]["responses"]["200"]
    assert response["content"]["application/json"]["schema"]["$ref"].endswith("FoodPage")


def test_filter_params_normalize_search_and_keep_numeric_values():
    filters = FoodFilters(q="  Lentil  ", min_protein=Decimal("10.5"))
    assert filters.sql_params()["q"] == "lentil"
    assert filters.sql_params()["min_protein"] == Decimal("10.5")


def test_source_values_preserve_unknown_and_exact_decimal_text():
    row = {
        "source_id": 7,
        "source_name": "BLS 4.0",
        "external_id": "F110100",
        "food_name": "Apfel roh",
        "reference_quantity": Decimal(100),
        "reference_unit": "g",
        "energy_kcal": Decimal(58),
        "protein_g": Decimal("0.424"),
        "fat_g": None,
        "carbs_g": Decimal("11.7"),
        "fiber_g": Decimal("2.275"),
    }
    source = source_from_row(row)
    assert source["protein_g"] == "0.424"
    assert source["fat_g"] is None


def test_catalog_queries_against_postgres(monkeypatch):
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("set TEST_DATABASE_URL for PostgreSQL integration coverage")
    monkeypatch.setenv("DATABASE_URL", database_url)

    all_foods = request("/api/foods?limit=2")
    assert all_foods.status_code == 200
    assert all_foods.json()["total"] >= 3
    assert len(all_foods.json()["items"]) == 2

    apple = request("/api/foods?q=F110100")
    assert apple.status_code == 200
    assert [food["slug"] for food in apple.json()["items"]] == ["apple-raw"]

    high_protein = request("/api/foods?min_protein=20&sort=protein_desc")
    assert high_protein.status_code == 200
    proteins = [Decimal(food["source"]["protein_g"]) for food in high_protein.json()["items"]]
    assert proteins and all(value >= 20 for value in proteins)
    assert proteins == sorted(proteins, reverse=True)

    sources = request("/api/foods?source_name=BLS%204.0&max_energy=100")
    assert sources.status_code == 200
    assert all(food["source"]["source_name"] == "BLS 4.0" for food in sources.json()["items"])
    assert all(Decimal(food["source"]["energy_kcal"]) <= 100 for food in sources.json()["items"])

    detail = request("/api/foods/bls4-g650132")
    assert detail.status_code == 200
    assert detail.json()["sources"][0]["energy_kcal"] == "46"
    assert request("/api/foods/not-a-food").status_code == 404
