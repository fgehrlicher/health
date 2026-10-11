import os
from decimal import Decimal

import psycopg
import pytest
from test_usda_bundle import food, label_values, make_archive, portion, sha256
from usda_importer.bundle import read_dataset
from usda_importer.database import slug_for, write_foods


def foods_from_archive(tmp_path, monkeypatch):
    archive = make_archive(
        tmp_path,
        "FoodData_Central_sr_legacy_food_csv_2018-04.zip",
        foods=[food(170923, "Spices, cumin seed")],
        amounts=label_values(170923)
        + [{"fdc_id": "170923", "nutrient_id": "1013", "amount": "1.5"}],
        portions=[portion(170923, 1, "tsp", 2)],
    )
    report = read_dataset(archive, expected_sha256=sha256(archive))
    for item in report.foods:
        item.german_name = "Kreuzkümmel, Samen"
    return report.foods


def test_import_creates_the_food_and_then_updates_it(tmp_path, monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("set TEST_DATABASE_URL for PostgreSQL integration coverage")
    foods = foods_from_archive(tmp_path, monkeypatch)

    first = write_foods(url, foods)
    assert first in ((1, 0), (0, 1))
    assert write_foods(url, foods) == (0, 1)

    with psycopg.connect(url) as connection:
        row = connection.execute(
            """SELECT f.name, f.aliases, f.kind, f.preparation_state, s.source_name,
                      s.external_id, s.energy_kcal, s.salt_g
               FROM catalog.foods f JOIN catalog.food_sources s ON s.food_id = f.id
               WHERE f.slug = %s""",
            (slug_for(170923),),
        ).fetchone()
        lactose = connection.execute(
            """SELECT n.amount FROM catalog.food_source_nutrients n
               JOIN catalog.food_sources s ON s.id = n.source_id
               JOIN catalog.foods f ON f.id = s.food_id
               WHERE f.slug = %s AND n.nutrient_key = 'lactose'""",
            (slug_for(170923),),
        ).fetchone()
        portions = connection.execute(
            """SELECT p.name, p.kind, p.quantity, p.unit FROM catalog.food_portions p
               JOIN catalog.foods f ON f.id = p.food_id WHERE f.slug = %s""",
            (slug_for(170923),),
        ).fetchall()
    assert row[0] == "Spices, cumin seed"
    assert row[1] == ["Kreuzkümmel, Samen"]
    assert row[2] == "generic"
    assert row[3] is None
    assert row[4] == "USDA FoodData Central"
    assert row[5] == "170923"
    assert row[6] == Decimal(100)  # the synthetic energy from label_values
    assert row[7] == Decimal("0.1")  # 40 mg sodium x 2.5
    assert lactose[0] == Decimal("1.5")
    assert portions == [("1 tsp", "household", Decimal(2), "g")]


def test_a_catalog_unit_that_differs_stops_the_import(tmp_path, monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("set TEST_DATABASE_URL for PostgreSQL integration coverage")
    foods = foods_from_archive(tmp_path, monkeypatch)
    with psycopg.connect(url) as connection:
        connection.execute("UPDATE catalog.nutrients SET unit = 'mg' WHERE key = 'lactose'")
        connection.commit()
    try:
        with pytest.raises(ValueError, match="catalog nutrient lactose"):
            write_foods(url, foods)
    finally:
        with psycopg.connect(url) as connection:
            connection.execute("UPDATE catalog.nutrients SET unit = 'g' WHERE key = 'lactose'")
            connection.commit()
