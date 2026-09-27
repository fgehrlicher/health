from decimal import Decimal

import pytest
from bls4_importer.source import columns_from_headers, parse_amount, parse_codes, parse_food


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


def test_energy_erratum_recomputes_before_rounding():
    columns = dict(
        zip(
            (
                "code",
                "german_name",
                "english_name",
                "energy",
                "protein",
                "fat",
                "carbs",
                "fiber",
                "oligosaccharides",
                "alcohol",
                "organic_acids",
                "polyols",
            ),
            range(12),
            strict=True,
        )
    )
    salsify = (
        "G650132",
        "Schwarzwurzel gekocht",
        "Black salsify boiled",
        51,
        1.3,
        0.4,
        6.6,
        5,
        2.539,
        0,
        0.25,
        0.066,
    )
    candy = (
        "S361000",
        "Fruchtgummi",
        "Fruit gummy",
        312,
        4.8,
        0.3,
        70.7,
        1.01,
        2.4,
        0,
        0.271,
        0.019,
    )
    food, corrected = parse_food(salsify, columns, "G650132", [])
    assert corrected and food.energy == Decimal(46)
    food, corrected = parse_food(candy, columns, "S361000", [])
    assert corrected and food.energy == Decimal(308)
