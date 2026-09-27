from collections import Counter
from decimal import Decimal

import pytest
from bls4_importer.erratum import apply_erratum, load_erratum
from bls4_importer.source import (
    FIELDS,
    columns_from_headers,
    parse_amount,
    parse_codes,
    parse_food,
    preparation_state,
)


def test_codes_are_explicit_and_unique():
    assert parse_codes("# note\nF110100\n\n") == {"F110100"}
    for text in ("F110100\nF110100\n", "f110100\n", "# no codes\n"):
        with pytest.raises(ValueError):
            parse_codes(text)


def test_markers_are_null_not_zero():
    issues = []
    assert parse_amount("TR", "F110100", "FIBT", issues) is None
    assert parse_amount(0, "F110100", "FAT", issues) == 0
    assert issues == [{"code": "F110100", "field": "FIBT", "marker": "TR"}]


@pytest.mark.parametrize("value", [-1, "mystery", float("nan"), True])
def test_bad_amounts_fail(value):
    with pytest.raises((TypeError, ValueError)):
        parse_amount(value, "F110100", "FAT", [])


def test_missing_or_ambiguous_columns_fail():
    with pytest.raises(ValueError):
        columns_from_headers(("BLS Code", "Food name"))


def bls_row(code: str, german: str, english: str, **values) -> tuple[tuple, dict[str, int]]:
    """A worksheet row and column map; unspecified components are BLS "-" markers."""
    fields = ["code", "german_name", "english_name", *FIELDS]
    row = {"code": code, "german_name": german, "english_name": english} | values
    return tuple(row.get(field, "-") for field in fields), {f: i for i, f in enumerate(fields)}


def test_energy_erratum_recomputes_kj_and_kcal_before_rounding():
    salsify = {
        "energy_kj": 213,
        "energy_kcal": 51,
        "protein_g": 1.3,
        "fat_g": 0.4,
        "carbs_g": 6.6,
        "fiber_g": 5,
        "oligosaccharides": 2.539,
        "alcohol_g": 0,
        "organic_acids": 0.25,
        "polyols_g": 0.066,
    }
    candy = {
        "energy_kj": 1322,
        "energy_kcal": 312,
        "protein_g": 4.8,
        "fat_g": 0.3,
        "carbs_g": 70.7,
        "fiber_g": 1.01,
        "oligosaccharides": 2.4,
        "alcohol_g": 0,
        "organic_acids": 0.271,
        "polyols_g": 0.019,
    }
    food, corrected, missing = parse_food(
        *bls_row("G650132", "Schwarzwurzel gekocht", "Black salsify boiled", **salsify),
        "G650132",
        [],
    )
    assert corrected and missing == []
    assert food.nutrients["energy_kcal"] == Decimal(46)
    assert food.nutrients["energy_kj"] == Decimal(192)
    food, corrected, missing = parse_food(
        *bls_row("S361000", "Fruchtgummi", "Fruit gummy", **candy), "S361000", []
    )
    assert corrected and missing == []
    assert food.nutrients["energy_kcal"] == Decimal(308)
    assert food.nutrients["energy_kj"] == Decimal(1306)

    food, corrected, missing = parse_food(
        *bls_row("G650132", "Schwarzwurzel", "Salsify", **(salsify | {"polyols_g": "-"})),
        "G650132",
        [],
    )
    assert food.nutrients["energy_kcal"] is None and food.nutrients["energy_kj"] is None
    assert not corrected
    assert missing == ["POLYL"]


def test_label_nutrients_are_read_and_markers_stay_null():
    issues = []
    food, corrected, _missing = parse_food(
        *bls_row(
            "M713100",
            "Speisequark Magerstufe",
            "Quark < 10 % fat in dry matter",
            energy_kj=277,
            energy_kcal=66,
            fat_g=0.18,
            saturated_fat_g=0.11,
            carbs_g=3.68,
            sugars_g=3.68,
            protein_g=11.85,
            salt_g=0.1,
            starch_g="<LOD",
        ),
        "M713100",
        issues,
    )
    assert not corrected
    assert food.nutrients["energy_kj"] == Decimal(277)
    assert food.nutrients["saturated_fat_g"] == Decimal("0.11")
    assert food.nutrients["sugars_g"] == Decimal("3.68")
    assert food.nutrients["salt_g"] == Decimal("0.1")
    assert food.nutrients["starch_g"] is None
    assert {"code": "M713100", "field": "STARCH", "marker": "<LOD"} in issues


def test_sugars_above_carbs_fail():
    with pytest.raises(ValueError, match="sugars_g exceeds carbs_g"):
        parse_food(
            *bls_row(
                "F110100",
                "Apfel",
                "Apple",
                energy_kj=240,
                energy_kcal=58,
                carbs_g=11.7,
                sugars_g=12,
            ),
            "F110100",
            [],
        )


@pytest.mark.parametrize(
    ("name", "state"),
    [
        ("Hühnerei roh", "raw"),
        ("Reis poliert, gekocht, gebraten ohne Fett (Pfanne)", "fried"),
        ("Hähnchen Brustfilet, tiefgefroren", "frozen"),
        ("Tomate Konserve", "canned"),
        ("Karottensalat (gegart) mit warmer Essigmarinade", None),
        ("Rohkost-Salat", None),
        ("Vollkornbrot", None),
    ],
)
def test_preparation_state_is_the_last_named_step(name, state):
    assert preparation_state(name) == state


def test_other_nutrients_convert_to_label_units_and_drop_impossible_values():
    issues = []
    food, _corrected, _missing = parse_food(
        *bls_row(
            "N311000",
            "Limonade mit Süßungsmitteln",
            "Lemonade with sweeteners",
            energy_kj=5,
            energy_kcal=1,
            vitamin_b6=150,
            calcium=12.5,
            water=100.16,
        ),
        "N311000",
        issues,
    )
    assert food.other_nutrients["vitamin_b6"] == Decimal("0.15")  # 150 µg -> mg
    assert food.other_nutrients["calcium"] == Decimal("12.5")
    assert food.other_nutrients["water"] is None
    assert {"code": "N311000", "field": "WATER", "marker": "implausible"} in issues
    assert food.other_nutrients["iodine"] is None


def test_erratum_corrects_only_the_published_value_and_withholds_others():
    erratum = load_erratum()
    almond = parse_food(
        *bls_row(
            "H210100", "Mandel süß", "Sweet almond", energy_kj=2500, energy_kcal=600, calcium=84.864
        ),
        "H210100",
        [],
    )[0]
    assert apply_erratum(almond, erratum["H210100"]).other_nutrients["calcium"] == Decimal(254)

    unexpected = parse_food(
        *bls_row(
            "H210100", "Mandel süß", "Sweet almond", energy_kj=2500, energy_kcal=600, calcium=90
        ),
        "H210100",
        [],
    )[0]
    with pytest.raises(ValueError, match="expects CA 84.9"):
        apply_erratum(unexpected, erratum["H210100"])

    anchovy = parse_food(
        *bls_row(
            "T104100",
            "Sardelle roh",
            "Anchovy raw",
            energy_kj=849,
            energy_kcal=204,
            fat_g=13.7,
            protein_g=20.1,
            omega_3=1.4,
            calcium=147,
        ),
        "T104100",
        [],
    )[0]
    anchovy = apply_erratum(anchovy, erratum["T104100"])
    assert anchovy.nutrients["fat_g"] is None and anchovy.nutrients["energy_kcal"] is None
    assert anchovy.other_nutrients["omega_3"] is None
    assert anchovy.nutrients["protein_g"] == Decimal("20.1")
    assert anchovy.other_nutrients["calcium"] == Decimal(147)


def test_erratum_file_covers_the_documented_entries():
    erratum = load_erratum()
    sections = Counter(c.section for entries in erratum.values() for c in entries)
    assert sections == {
        "1.2": 1,
        "1.3": 3,
        "2.2": 2,
        "6": 1,
        "7.1": 6,
        "7.2": 19,
        "7.3": 132,
        "7.7": 16,
    }
