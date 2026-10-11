import csv
import hashlib
import io
import zipfile
from pathlib import Path

import pytest
from usda_importer.bundle import PINNED, read_dataset

SR_NAME = "FoodData_Central_sr_legacy_food_csv_2018-04.zip"
FOUNDATION_NAME = "FoodData_Central_foundation_food_csv_2026-04-30.zip"
REAL_DIR = Path(__file__).resolve().parents[3] / "data/usda/raw"

# The units the archive's nutrient.csv gives, as the real bundles do.
UNITS = {
    "1008": "KCAL",
    "2047": "KCAL",
    "1062": "kJ",
    "1004": "G",
    "1258": "G",
    "1292": "G",
    "1293": "G",
    "2000": "G",
    "1063": "G",
    "1009": "G",
    "1079": "G",
    "1003": "G",
    "1093": "MG",
    "1018": "G",
    "1005": "G",
    "1106": "UG",
    "1114": "UG",
    "1109": "MG",
    "1185": "UG",
    "1162": "MG",
    "1165": "MG",
    "1166": "MG",
    "1167": "MG",
    "1175": "MG",
    "1190": "UG",
    "1177": "UG",
    "1178": "UG",
    "1092": "MG",
    "1087": "MG",
    "1090": "MG",
    "1091": "MG",
    "1089": "MG",
    "1095": "MG",
    "1100": "UG",
    "1278": "G",
    "1272": "G",
    "1253": "MG",
    "1051": "G",
    "1013": "G",
    "1010": "G",
}


def nutrient_table():
    return [{"id": number, "name": number, "unit_name": unit} for number, unit in UNITS.items()]


def food(fdc, description, *, category="1", published="2019-04-01", data_type="sr_legacy_food"):
    return {
        "fdc_id": str(fdc),
        "data_type": data_type,
        "description": description,
        "food_category_id": category,
        "publication_date": published,
    }


def amount(fdc, nutrient, value):
    return {"fdc_id": str(fdc), "nutrient_id": str(nutrient), "amount": str(value)}


def portion(fdc, amount_value, modifier, grams):
    return {
        "fdc_id": str(fdc),
        "amount": str(amount_value),
        "modifier": modifier,
        "gram_weight": str(grams),
    }


def label_values(fdc, overrides=None):
    """Energy, fat, carbs, protein, fiber, sugars and sodium for one food."""
    values = {1008: 100, 1004: 2, 1005: 20, 1079: 3, 2000: 5, 1003: 4, 1093: 40}
    values.update(overrides or {})
    return [amount(fdc, number, value) for number, value in values.items() if value is not None]


def make_archive(
    directory: Path, name: str, *, foods, amounts, portions=(), categories=None
) -> Path:
    tables = {
        "food.csv": (
            ["fdc_id", "data_type", "description", "food_category_id", "publication_date"],
            list(foods),
        ),
        "food_nutrient.csv": (["fdc_id", "nutrient_id", "amount"], list(amounts)),
        "nutrient.csv": (["id", "name", "unit_name"], nutrient_table()),
        "food_portion.csv": (
            ["fdc_id", "amount", "modifier", "gram_weight"],
            list(portions) or [{"fdc_id": "", "amount": "", "modifier": "", "gram_weight": ""}],
        ),
        "food_category.csv": (
            ["id", "description"],
            categories
            or [
                {"id": "1", "description": "Dairy and Egg Products"},
                {"id": "2", "description": "Fast Foods"},
            ],
        ),
    }
    path = directory / name
    with zipfile.ZipFile(path, "w") as archive:
        for table, (fields, rows) in tables.items():
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
            archive.writestr(f"{name[:-4]}/{table}", buffer.getvalue())
    return path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_archive_with_the_wrong_checksum_is_refused(tmp_path):
    path = make_archive(tmp_path, SR_NAME, foods=[food(1, "Egg")], amounts=label_values(1))
    with pytest.raises(ValueError, match="unexpected checksum"):
        read_dataset(path, expected_sha256="0" * 64)


def test_unknown_archive_name_is_refused(tmp_path):
    path = make_archive(tmp_path, "other.zip", foods=[food(1, "Egg")], amounts=label_values(1))
    with pytest.raises(ValueError, match="not a pinned USDA archive"):
        read_dataset(path)


def test_american_categories_are_excluded(tmp_path):
    foods = [food(1, "Egg, whole, raw", category="1"), food(2, "Burger, fast food", category="2")]
    amounts = label_values(1) + label_values(2)
    path = make_archive(tmp_path, SR_NAME, foods=foods, amounts=amounts)
    report = read_dataset(path, expected_sha256=sha256(path))
    assert [f.fdc_id for f in report.foods] == [1]
    assert report.excluded_american == 1


def test_duplicate_descriptions_keep_the_newest(tmp_path):
    foods = [
        food(10, "Broccoli, raw", published="2019-04-01", data_type="foundation_food"),
        food(11, "Broccoli, raw", published="2019-12-16", data_type="foundation_food"),
    ]
    amounts = label_values(10) + label_values(11)
    path = make_archive(tmp_path, FOUNDATION_NAME, foods=foods, amounts=amounts)
    report = read_dataset(path, expected_sha256=sha256(path))
    assert [f.fdc_id for f in report.foods] == [11]
    assert report.duplicates_dropped == [{"fdc_id": 10, "kept": 11, "description": "Broccoli, raw"}]


def test_a_rule_breaking_food_is_reported_and_the_rest_imports(tmp_path):
    bad = label_values(20, {1004: -1})  # negative fat: a broken value, not rounding
    good = label_values(21)
    path = make_archive(
        tmp_path, SR_NAME, foods=[food(20, "Butter"), food(21, "Egg")], amounts=bad + good
    )
    report = read_dataset(path, expected_sha256=sha256(path))
    assert [f.fdc_id for f in report.foods] == [21]
    assert report.rejected[0]["fdc_id"] == 20
    assert "negative" in report.rejected[0]["reason"]


def test_a_sugar_conflict_keeps_the_food_and_notes_it(tmp_path):
    conflict = label_values(22, {2000: 50})  # sugars 50 g, available carbohydrate 17 g
    path = make_archive(tmp_path, SR_NAME, foods=[food(22, "Syrup")], amounts=conflict)
    report = read_dataset(path, expected_sha256=sha256(path))
    [syrup] = report.foods
    assert syrup.nutrients["sugars_g"] is None
    assert syrup.notes and syrup.notes[0].startswith("sugars_unknown:")
    assert report.rejected == []


@pytest.mark.skipif(
    not all((REAL_DIR / name).exists() for name in PINNED),
    reason="real USDA archives not downloaded",
)
def test_the_real_archives_pass_their_checksums_and_map():
    for name in PINNED:
        report = read_dataset(REAL_DIR / name)
        assert report.foods, name
        assert not [item for item in report.rejected if "unit" in item["reason"]], name
