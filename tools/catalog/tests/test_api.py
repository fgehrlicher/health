import asyncio
import os
from decimal import Decimal

import httpx
import psycopg
import pytest
from health_catalog.app import app
from health_catalog.repository import (
    NUTRIENTS,
    FoodFilters,
    search_tokens,
    source_from_row,
)
from health_catalog.search_eval import evaluate, hit_rate, read_cases
from psycopg.rows import dict_row


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
    assert "<title>Foods</title>" in page.text
    assert 'id="food-table"' in page.text
    assert request("/assets/app.js").status_code == 200
    assert request("/assets/styles.css").status_code == 200
    assert request("/assets/vendor/tabulator-6.5.3/tabulator.min.js").status_code == 200


def test_api_rejects_invalid_filters_before_querying_database():
    for path in (
        "/api/foods?limit=0",
        "/api/foods?limit=101",
        "/api/foods?offset=-1",
        "/api/foods?sort=DROP%20TABLE%20foods",
        "/api/foods?min_protein=-1",
        "/api/foods?min_protein_density=-1",
        "/api/foods?group=Z",
    ):
        assert request(path).status_code == 422


def test_openapi_describes_catalog_response():
    schema = request("/openapi.json").json()
    response = schema["paths"]["/api/foods"]["get"]["responses"]["200"]
    assert response["content"]["application/json"]["schema"]["$ref"].endswith("FoodPage")


def test_filter_params_normalize_search_and_keep_numeric_values():
    filters = FoodFilters(q="  Lentil  ", min_protein=Decimal("10.5"))
    assert filters.sql_params()["tokens"] == ["lentil"]
    assert filters.sql_params()["min_protein"] == Decimal("10.5")


def test_source_values_preserve_unknown_and_exact_decimal_text():
    row = {
        "source_id": 7,
        "source_name": "BLS 4.0",
        "external_id": "F110100",
        "food_name": "Apfel roh",
        "group_code": "F",
        "reference_quantity": Decimal(100),
        "reference_unit": "g",
        "energy_kcal": Decimal(58),
        "protein_g": Decimal("0.424"),
        "protein_per_100_kcal": Decimal("0.73103448275862068966"),
        "fat_g": None,
        "carbs_g": Decimal("11.7"),
        "fiber_g": Decimal("2.275"),
        "upper_bounds": ["fat_g"],
        "ingredients_text": None,
    }
    row |= {field: row.get(field) for field in NUTRIENTS}
    source = source_from_row(row)
    assert source["protein_g"] == "0.424"
    assert source["fat_g"] is None
    assert source["group_code"] == "F"
    assert source["protein_per_100_kcal"] == "0.73103448275862068966"
    assert source["sugars_g"] is None
    assert source["upper_bounds"] == ["fat_g"]


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
    assert len(apple.json()["items"]) == 1
    assert apple.json()["items"][0]["source"]["external_id"] == "F110100"
    assert apple.json()["items"][0]["source"]["group_code"] == "F"
    apple_source = apple.json()["items"][0]["source"]
    assert abs(
        Decimal(apple_source["protein_per_100_kcal"])
        - Decimal(apple_source["protein_g"]) * 100 / Decimal(apple_source["energy_kcal"])
    ) < Decimal("0.0000000001")

    high_protein = request("/api/foods?min_protein=20&sort=protein_desc")
    assert high_protein.status_code == 200
    proteins = [Decimal(food["source"]["protein_g"]) for food in high_protein.json()["items"]]
    assert proteins and all(value >= 20 for value in proteins)
    assert proteins == sorted(proteins, reverse=True)

    sources = request("/api/foods?source_name=BLS%204.0&max_energy=100")
    assert sources.status_code == 200
    assert all(food["source"]["source_name"] == "BLS 4.0" for food in sources.json()["items"])
    assert all(Decimal(food["source"]["energy_kcal"]) <= 100 for food in sources.json()["items"])

    fruit = request("/api/foods?group=F")
    assert fruit.status_code == 200
    assert fruit.json()["total"] >= 1
    assert all(food["source"]["external_id"].startswith("F") for food in fruit.json()["items"])
    facets = request("/api/foods/facets")
    assert any(group["code"] == "F" for group in facets.json()["groups"])

    fat_sorted = request("/api/foods?sort=fat_desc&limit=20")
    assert fat_sorted.status_code == 200
    fats = [Decimal(food["source"]["fat_g"]) for food in fat_sorted.json()["items"]]
    assert fats == sorted(fats, reverse=True)
    code_sorted = request("/api/foods?sort=code_desc&limit=20")
    assert code_sorted.status_code == 200
    codes = [food["source"]["external_id"] for food in code_sorted.json()["items"]]
    assert codes == sorted(codes, reverse=True)

    density_sorted = request("/api/foods?sort=protein_density_desc&limit=20")
    assert density_sorted.status_code == 200
    densities = [
        Decimal(food["source"]["protein_per_100_kcal"]) for food in density_sorted.json()["items"]
    ]
    assert densities == sorted(densities, reverse=True)
    dense = request("/api/foods?min_protein_density=20")
    assert dense.status_code == 200
    assert dense.json()["total"] >= 1
    assert all(
        Decimal(food["source"]["protein_per_100_kcal"]) >= 20 for food in dense.json()["items"]
    )

    detail = request("/api/foods/bls4-g650132")
    assert detail.status_code == 200
    assert detail.json()["sources"][0]["energy_kcal"] == "46"
    assert detail.json()["sources"][0]["energy_kj"] == "192"
    assert detail.json()["sources"][0]["sugars_g"] is not None
    assert detail.json()["portions"] == []
    assert request("/api/foods/not-a-food").status_code == 404


def test_search_tokens_are_distinct_lowercase_words():
    assert search_tokens(None) is None
    assert search_tokens(" ,; ") is None
    assert search_tokens("Chicken  breast, chicken_Breast") == ["chicken", "breast"]
    assert search_tokens("a b c d e f g h i j") == list("abcdefgh")


def test_search_ranks_typos_word_order_and_german_names(monkeypatch):
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("set TEST_DATABASE_URL for PostgreSQL integration coverage")
    monkeypatch.setenv("DATABASE_URL", database_url)

    def first_codes(q: str, count: int = 1) -> list[str]:
        response = request(f"/api/foods?q={q}&limit={count}")
        assert response.status_code == 200
        return [food["source"]["external_id"] for food in response.json()["items"]]

    assert first_codes("brocoli") == ["G312100"]
    assert first_codes("rice%20white") == ["C352000"]
    assert first_codes("kichererbse%20gekocht") == ["G770432"]
    assert first_codes("apfel") == ["F110100"]
    assert first_codes("F110100", 5) == ["F110100"]


def test_search_quality_on_full_bls_catalog():
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("set TEST_DATABASE_URL for PostgreSQL integration coverage")
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        count = connection.execute("SELECT count(*) AS n FROM food_sources").fetchone()["n"]
        if count < 7000:
            pytest.skip("search evaluation needs the full BLS 4.0 import")
        results = evaluate(connection, read_cases())
    # Guards against ranking regressions; raise these as search improves.
    assert hit_rate(results, 1) >= 0.55
    assert hit_rate(results, 5) >= 0.75
