import json
import os

import psycopg
import pytest
from test_usda_bundle import food, label_values, make_archive, sha256
from usda_importer.bundle import read_dataset
from usda_importer.database import slug_for, write_foods
from usda_importer.postprocess import GROUPS_PATH, apply, check_decisions, load_groups

KNOWN_CODES = {
    "B",
    "C",
    "D",
    "E",
    "F",
    "G",
    "H",
    "K",
    "M",
    "N",
    "P",
    "Q",
    "R",
    "S",
    "T",
    "U",
    "V",
    "W",
    "X",
    "Y",
}


def test_check_accepts_a_complete_set():
    decisions = [{"slug": "usda-1", "food_group": "G", "name_de": "Koriander, frisch"}]
    assert check_decisions(decisions, {"usda-1"}, {"G", "R"}) == []


def test_check_reports_each_kind_of_problem():
    decisions = [
        {"slug": "usda-1", "food_group": "G", "name_de": "A"},
        {"slug": "usda-1", "food_group": "G", "name_de": "A"},
        {"slug": "usda-9", "food_group": "Z", "name_de": " "},
    ]
    text = "\n".join(check_decisions(decisions, {"usda-1", "usda-2"}, {"G"}))
    assert "decided more than once" in text
    assert "not an imported USDA food" in text
    assert "is not a catalog group" in text
    assert "German name is missing or malformed" in text
    assert "1 foods have no decision" in text and "usda-2" in text


def test_the_group_names_cover_every_catalog_group():
    groups = load_groups(GROUPS_PATH)
    assert set(groups) == KNOWN_CODES
    assert all(name and name == name.strip() for name in groups.values())


def test_apply_refuses_decisions_that_do_not_cover_the_database(tmp_path):
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("set TEST_DATABASE_URL for PostgreSQL integration coverage")
    decisions = tmp_path / "decisions"
    decisions.mkdir()
    (decisions / "batch-01.json").write_text(
        json.dumps([{"slug": "usda-000", "food_group": "G", "name_de": "Test"}]), encoding="utf-8"
    )
    with pytest.raises(ValueError):
        apply(url, decisions, GROUPS_PATH, commit=False)


def test_apply_writes_group_and_german_name_once(tmp_path):
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("set TEST_DATABASE_URL for PostgreSQL integration coverage")
    archive = make_archive(
        tmp_path,
        "FoodData_Central_sr_legacy_food_csv_2018-04.zip",
        foods=[food(170924, "Spices, cumin seed")],
        amounts=label_values(170924),
    )
    report = read_dataset(archive, expected_sha256=sha256(archive))
    write_foods(url, report.foods)

    # One decision for every USDA food the database holds.
    with psycopg.connect(url) as connection:
        slugs = [
            row[0]
            for row in connection.execute(
                """SELECT f.slug FROM catalog.foods f
                   JOIN catalog.food_sources s ON s.food_id = f.id
                   WHERE s.source_name = 'USDA FoodData Central'"""
            )
        ]
    decisions = tmp_path / "decisions"
    decisions.mkdir()
    items = [{"slug": slug, "food_group": "R", "name_de": "Kreuzkümmel, Samen"} for slug in slugs]
    (decisions / "batch-01.json").write_text(json.dumps(items), encoding="utf-8")

    apply(url, decisions, GROUPS_PATH, commit=True)
    apply(url, decisions, GROUPS_PATH, commit=True)  # a rerun changes nothing

    with psycopg.connect(url) as connection:
        row = connection.execute(
            """SELECT f.food_group, f.name_de, f.aliases, g.name_de
               FROM catalog.foods f JOIN catalog.food_groups g ON g.code = f.food_group
               WHERE f.slug = %s""",
            (slug_for(170924),),
        ).fetchone()
    assert row[0] == "R"
    assert row[1] == "Kreuzkümmel, Samen"
    assert row[2].count("Kreuzkümmel, Samen") == 1
    assert row[3] == "Gewürze und Soßen"
