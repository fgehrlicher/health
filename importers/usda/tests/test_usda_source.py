from decimal import Decimal

import pytest
from test_usda_bundle import UNITS
from usda_importer.source import Rejected, build_food, preparation_state

AMOUNTS = {
    1008: Decimal(23),
    1004: Decimal("0.52"),
    1005: Decimal("3.67"),
    1079: Decimal("2.8"),
    2000: Decimal("0.87"),
    1003: Decimal("2.13"),
    1093: Decimal(46),
}


def food(amounts=None, description="Coriander (cilantro) leaves, raw", **kwargs):
    return build_food(
        fdc_id=169997,
        description=description,
        data_type="sr_legacy_food",
        publication_date="2019-04-01",
        amounts=dict(AMOUNTS if amounts is None else amounts),
        units=dict(UNITS),
        portion_rows=kwargs.get("portion_rows", []),
        german_name=None,
    )


def test_label_columns_follow_the_usda_values():
    n = food().nutrients
    assert n["energy_kcal"] == Decimal(23)
    assert n["fat_g"] == Decimal("0.52")
    assert n["carbs_g"] == Decimal("0.87")  # 3.67 by difference less 2.8 fiber
    assert n["sugars_g"] == Decimal("0.87")
    assert n["salt_g"] == Decimal("0.115")  # 46 mg sodium x 2.5
    assert n["polyols_g"] is None and n["starch_g"] is None and n["alcohol_g"] is None


def test_kj_is_derived_from_kcal_when_usda_has_none():
    result = food()
    assert result.nutrients["energy_kj"] == Decimal("96.2")  # 23 x 4.184
    assert result.derived == ["energy_kj"]


def test_kj_stays_as_given_when_usda_has_it():
    result = food({**AMOUNTS, 1062: Decimal(95)})
    assert result.nutrients["energy_kj"] == Decimal(95)
    assert result.derived == []


def test_energy_falls_back_to_atwater_general_factors():
    result = food({**AMOUNTS, 2047: Decimal(24)})
    assert result.nutrients["energy_kcal"] == Decimal(23)  # 1008 wins when present
    without = food({k: v for k, v in AMOUNTS.items() if k != 1008} | {2047: Decimal(24)})
    assert without.nutrients["energy_kcal"] == Decimal(24)


def test_sugars_fall_back_to_the_other_usda_total():
    result = food({k: v for k, v in AMOUNTS.items() if k != 2000} | {1063: Decimal("0.5")})
    assert result.nutrients["sugars_g"] == Decimal("0.5")


def test_folate_falls_back_to_total_folate_and_lactose_is_not_sucrose():
    result = food({**AMOUNTS, 1177: Decimal(9), 1010: Decimal(40), 1013: Decimal("1.2")})
    assert result.other["folate"] == Decimal(9)
    assert result.other["lactose"] == Decimal("1.2")  # 1013, not sucrose (1010)
    only_sucrose = food({**AMOUNTS, 1010: Decimal(40)})
    assert "lactose" not in only_sucrose.other


def test_carbs_stay_unknown_without_fiber():
    result = food({k: v for k, v in AMOUNTS.items() if k != 1079})
    assert result.nutrients["carbs_g"] is None


def test_a_unit_the_mapping_does_not_expect_is_rejected():
    units = dict(UNITS, **{"1093": "G"})  # sodium in grams, not milligrams
    with pytest.raises(Rejected, match="expected MG"):
        build_food(
            fdc_id=1,
            description="Egg",
            data_type="sr_legacy_food",
            publication_date="2019-04-01",
            amounts=dict(AMOUNTS),
            units=units,
            portion_rows=[],
            german_name=None,
        )


def test_sugars_far_above_available_carbohydrate_become_unknown_and_are_noted():
    result = food({**AMOUNTS, 2000: Decimal(9)})
    assert result.nutrients["sugars_g"] is None
    assert result.nutrients["carbs_g"] == Decimal("0.87")
    assert result.notes[0].startswith("sugars_unknown:")


def test_a_small_sugar_excess_is_rounding_and_kept():
    result = food({**AMOUNTS, 2000: Decimal("1.2")})  # available carbohydrate is 0.87 g
    assert result.nutrients["sugars_g"] == Decimal("1.2")
    assert result.notes[0].startswith("rounding:")


def test_a_small_negative_carbohydrate_becomes_zero_and_is_noted():
    result = food({**AMOUNTS, 1005: Decimal("-0.5"), 1079: Decimal(0), 2000: Decimal(0)})
    assert result.nutrients["carbs_g"] == Decimal(0)
    assert result.notes[0].startswith("carbs_clamped:")


def test_a_large_negative_carbohydrate_is_rejected():
    with pytest.raises(Rejected, match="carbohydrate by difference is"):
        food({**AMOUNTS, 1005: Decimal(-3)})


def test_negative_values_are_rejected():
    with pytest.raises(Rejected, match="negative"):
        food({**AMOUNTS, 1004: Decimal(-1)})


def test_portions_take_their_name_from_the_measure_and_their_grams():
    rows = [
        {"amount": "1", "modifier": "cup", "gram_weight": "240"},
        {"amount": "2.0", "modifier": "tbsp", "gram_weight": "30"},
        {"amount": "1", "modifier": "serving", "gram_weight": "34"},
        {"amount": "1", "modifier": "cup", "gram_weight": "250"},  # same name: first one wins
        {"amount": "1", "modifier": "", "gram_weight": "10"},  # no measure: skipped
        {"amount": "1", "modifier": "slice", "gram_weight": ""},  # no grams: skipped
    ]
    portions = food(portion_rows=rows).portions
    assert [(p.name, p.kind, p.quantity, p.unit) for p in portions] == [
        ("1 cup", "household", Decimal(240), "g"),
        ("2 tbsp", "household", Decimal(30), "g"),
        ("1 serving", "serving", Decimal(34), "g"),
    ]


@pytest.mark.parametrize(
    ("description", "state"),
    [
        ("Coriander (cilantro) leaves, raw", "raw"),
        ("Spices, oregano, dried", "dried"),
        ("Spices, paprika", None),
        ("Beef, ground, cooked, pan-broiled", None),
        ("Chicken, roasting, meat only, roasted", "roasted"),
    ],
)
def test_preparation_state_is_the_last_word_when_it_names_a_state(description, state):
    assert preparation_state(description) == state
