"""Research spike: what the USDA CSV bundles contain, and how they fit the catalog.

Reads the unpacked bundles under data/usda/unpacked (git-ignored) and prints one
JSON summary. Read-only; it writes nothing to the database. Run from the repo root:

    python3 importers/usda/spike/survey.py > data/usda/spike-summary.json
"""

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] / "data/usda/unpacked"
BUNDLES = {
    "foundation": (
        ROOT
        / "FoodData_Central_foundation_food_csv_2026-04-30/FoodData_Central_foundation_food_csv_2026-04-30",
        "foundation_food",
    ),
    "sr_legacy": (
        ROOT
        / "FoodData_Central_sr_legacy_food_csv_2018-04/FoodData_Central_sr_legacy_food_csv_2018-04",
        "sr_legacy_food",
    ),
    "survey": (
        ROOT
        / "FoodData_Central_survey_food_csv_2024-10-31/FoodData_Central_survey_food_csv_2024-10-31",
        "survey_fndds_food",
    ),
}

# Catalog label columns -> USDA nutrient ids, in order of preference (fallbacks).
LABEL = {
    "energy_kcal": [1008, 2047],  # 2047 = Atwater General Factors, the label's basis
    "energy_kj": [1062],
    "fat_g": [1004],
    "saturated_fat_g": [1258],
    "monounsaturated_fat_g": [1292],
    "polyunsaturated_fat_g": [1293],
    "carbs_by_difference_g": [1005],
    "sugars_g": [2000, 1063],
    "starch_g": [1009],
    "fiber_g": [1079],
    "protein_g": [1003],
    "sodium_mg": [1093],
    "alcohol_g": [1018],
}
# The other catalog nutrients (food_source_nutrients), USDA ids.
OTHER = {
    "vitamin_a": [1106],
    "vitamin_d": [1114],
    "vitamin_e": [1109],
    "vitamin_k": [1185],
    "vitamin_c": [1162],
    "thiamin": [1165],
    "riboflavin": [1166],
    "niacin": [1167],
    "vitamin_b6": [1175],
    "folate": [1190, 1177],
    "vitamin_b12": [1178],
    "potassium": [1092],
    "calcium": [1087],
    "magnesium": [1090],
    "phosphorus": [1091],
    "iron": [1089],
    "zinc": [1095],
    "iodine": [1100],
    "epa": [1278],
    "dha": [1272],
    "cholesterol": [1253],
    "water": [1051],
    "lactose": [1013],
    "sodium": [1093],
}
STATES = {
    "raw",
    "boiled",
    "stewed",
    "braised",
    "grilled",
    "fried",
    "baked",
    "deep-fried",
    "dried",
    "frozen",
    "canned",
    "smoked",
    "poached",
    "steamed",
    "roasted",
    "gratinated",
    "toasted",
    "blanched",
    "cooked",
}
# Categories that are American-specific: chains, restaurants, baby products, traditional foods.
AMERICAN_CATEGORIES = {
    "Fast Foods",
    "Restaurant Foods",
    "Baby Foods",
    "American Indian/Alaska Native Foods",
}
# A rough signal for brand names in SR Legacy descriptions. It over-matches on purpose.
BRAND = re.compile(
    r"\b(Foods?|Kraft|Pillsbury|Gerber|McDonald|Burger King|Taco Bell|Kellogg|General Mills|"
    r"Nestl[eé]|Heinz|Campbell|Hormel|Tyson|Sara Lee|Pepsi|Coca|Dunkin|Wendy|Subway|"
    r"Kentucky|Pizza Hut|Domino|Starbucks|Nabisco|Keebler|Quaker|Dole|Del Monte|"
    r"Betty Crocker|Jell-O|Oscar Mayer|Bakeries)\b"
)


def rows(path: Path):
    with path.open(encoding="utf-8", newline="") as handle:
        yield from csv.DictReader(handle)


def coverage(foods, amounts, mapping):
    return {
        key: sum(1 for fdc in foods if any(number in amounts[fdc] for number in numbers))
        for key, numbers in mapping.items()
    }


def main() -> None:
    summary: dict = {}
    for bundle, (path, data_type) in BUNDLES.items():
        food_rows = {
            int(r["fdc_id"]): r for r in rows(path / "food.csv") if r["data_type"] == data_type
        }
        foods = set(food_rows)
        summary[bundle] = {"foods": len(foods), "data_type": data_type}
        if not foods:
            continue

        # Nutrient ids: survey files key food_nutrient by nutrient_nbr, not by nutrient id.
        nutrient_by_id = {int(r["id"]): r for r in rows(path / "nutrient.csv")}
        key_column = "nutrient_nbr" if bundle == "survey" else "id"
        if bundle == "survey":
            number_of = {r[key_column]: int(r["id"]) for r in nutrient_by_id.values()}
        amounts: dict[int, set[int]] = defaultdict(set)
        for r in rows(path / "food_nutrient.csv"):
            if not r["fdc_id"] or r["amount"] == "":
                continue
            fdc = int(r["fdc_id"])
            if fdc in foods:
                nutrient = int(r["nutrient_id"])
                amounts[fdc].add(
                    number_of.get(str(nutrient), nutrient) if bundle == "survey" else nutrient
                )

        summary[bundle]["label_coverage"] = coverage(foods, amounts, LABEL)
        summary[bundle]["other_coverage"] = coverage(foods, amounts, OTHER)
        summary[bundle]["core_kcal_fat_carbs_protein"] = sum(
            1
            for fdc in foods
            if all(
                any(n in amounts[fdc] for n in LABEL[k])
                for k in ("energy_kcal", "fat_g", "carbs_by_difference_g", "protein_g")
            )
        )
        summary[bundle]["other_nutrient_rows"] = sum(
            sum(1 for numbers in OTHER.values() if any(n in amounts[fdc] for n in numbers))
            for fdc in foods
        )

        descriptions = Counter(r["description"] for fdc, r in food_rows.items())
        summary[bundle]["descriptions_used_twice"] = sum(1 for n in descriptions.values() if n > 1)
        states = Counter(
            d.rsplit(",", 1)[-1].strip().lower()
            for d in descriptions
            if d.rsplit(",", 1)[-1].strip().lower() in STATES
        )
        summary[bundle]["preparation_state_from_last_word"] = sum(states.values())

        if (path / "food_category.csv").exists():
            names = {int(r["id"]): r["description"] for r in rows(path / "food_category.csv")}
            categories = Counter(
                names.get(int(r["food_category_id"] or 0), "(none)") for fdc, r in food_rows.items()
            )
            summary[bundle]["categories"] = dict(categories.most_common())
            summary[bundle]["american_category_foods"] = sum(
                n for name, n in categories.items() if name in AMERICAN_CATEGORIES
            )
        if bundle == "sr_legacy":
            summary[bundle]["brand_like_names"] = sum(
                1 for r in food_rows.values() if BRAND.search(r["description"])
            )

        portions = Counter()
        for r in rows(path / "food_portion.csv"):
            if r["fdc_id"] and int(r["fdc_id"]) in foods:
                portions[(r["modifier"] or "").strip().lower()[:24] or "(none)"] += 1
        summary[bundle]["portion_rows"] = sum(portions.values())
        summary[bundle]["portion_modifiers_top"] = portions.most_common(8)

    json.dump(summary, sys.stdout, ensure_ascii=False, indent=1)
    print()


if __name__ == "__main__":
    main()
