"""Maps USDA FoodData Central foods to catalog columns, per 100 g.

Only SR Legacy and Foundation foods are mapped. Every USDA unit is checked
against the unit the catalog expects. A food that breaks a rule is rejected
with its reason, and the rest of the import goes on, as the BLS importer rejects
its rows.
"""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

SOURCE_NAME = "USDA FoodData Central"
KJ_PER_KCAL = Decimal("4.184")
SALT_PER_SODIUM = Decimal("2.5")  # salt = sodium x 2.5, the EU labelling convention

# The label columns of the catalog (docs/database.md#import-contract).
# Polyols are not in USDA data, so they are always unknown.
LABEL_COLUMNS = (
    "energy_kj",
    "energy_kcal",
    "fat_g",
    "saturated_fat_g",
    "monounsaturated_fat_g",
    "polyunsaturated_fat_g",
    "carbs_g",
    "sugars_g",
    "polyols_g",
    "starch_g",
    "fiber_g",
    "protein_g",
    "salt_g",
    "alcohol_g",
)

# catalog column -> (USDA nutrient ids in order of preference, USDA unit).
DIRECT = {
    "energy_kcal": ([1008, 2047], "KCAL"),  # 2047: Atwater General Factors, the label's basis
    "energy_kj": ([1062], "KJ"),
    "fat_g": ([1004], "G"),
    "saturated_fat_g": ([1258], "G"),
    "monounsaturated_fat_g": ([1292], "G"),
    "polyunsaturated_fat_g": ([1293], "G"),
    "sugars_g": ([2000, 1063], "G"),
    "starch_g": ([1009], "G"),
    "fiber_g": ([1079], "G"),
    "protein_g": ([1003], "G"),
    "alcohol_g": ([1018], "G"),
}
TOTAL_CARBOHYDRATE = 1005  # "by difference": includes fiber, the label's carbs do not
FIBER = 1079
SODIUM = 1093  # mg

# catalog key -> (USDA ids in order of preference, USDA unit, the catalog's unit).
# The catalog unit is checked against catalog.nutrients before anything is written.
OTHER = {
    "vitamin_a": ([1106], "UG", "µg"),
    "vitamin_d": ([1114], "UG", "µg"),
    "vitamin_e": ([1109], "MG", "mg"),
    "vitamin_k": ([1185], "UG", "µg"),
    "vitamin_c": ([1162], "MG", "mg"),
    "thiamin": ([1165], "MG", "mg"),
    "riboflavin": ([1166], "MG", "mg"),
    "niacin": ([1167], "MG", "mg"),
    "vitamin_b6": ([1175], "MG", "mg"),
    "folate": ([1190, 1177], "UG", "µg"),
    "vitamin_b12": ([1178], "UG", "µg"),
    "sodium": ([SODIUM], "MG", "mg"),
    "potassium": ([1092], "MG", "mg"),
    "calcium": ([1087], "MG", "mg"),
    "magnesium": ([1090], "MG", "mg"),
    "phosphorus": ([1091], "MG", "mg"),
    "iron": ([1089], "MG", "mg"),
    "zinc": ([1095], "MG", "mg"),
    "iodine": ([1100], "UG", "µg"),
    "epa": ([1278], "G", "g"),
    "dha": ([1272], "G", "g"),
    "cholesterol": ([1253], "MG", "mg"),
    "water": ([1051], "G", "g"),
    "lactose": ([1013], "G", "g"),
}

# The states allowed in foods.preparation_state (docs/database.md#import-contract).
PREPARATION_STATES = frozenset(
    {
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
)


class Rejected(ValueError):
    """A food that breaks a rule. The message says which rule."""


# USDA rounds to one decimal place, and carbohydrate is calculated by difference, so
# small inconsistencies are rounding. Larger ones are kept as notes, not stored.
CARB_TOLERANCE = Decimal(1)  # a negative carbohydrate down to this many grams is set to 0
SUGAR_TOLERANCE = Decimal("0.5")  # sugars this far above available carbohydrate are rounding


@dataclass(frozen=True)
class Portion:
    name: str
    kind: str  # serving or household
    quantity: Decimal  # grams
    unit: str


@dataclass
class Food:
    fdc_id: int
    description: str
    data_type: str
    publication_date: str
    german_name: str | None
    preparation_state: str | None
    nutrients: dict[str, Decimal | None]  # label columns
    other: dict[str, Decimal]  # catalog nutrient key -> amount, only the known ones
    portions: list[Portion] = field(default_factory=list)
    derived: list[str] = field(default_factory=list)  # columns computed by a rule
    notes: list[str] = field(default_factory=list)  # adjustments and conflicts, for the report


def unit_amount(
    amounts: dict[int, Decimal], units: dict[str, str], number: int, unit: str
) -> Decimal | None:
    """One nutrient's amount in the expected unit, or None when the record lacks it."""
    if number not in amounts:
        return None
    found = units.get(str(number), "")
    if found.casefold() != unit.casefold():
        raise Rejected(f"nutrient {number} is in {found!r}, expected {unit}")
    return amounts[number]


def amount_of(
    amounts: dict[int, Decimal], units: dict[str, str], number: int, unit: str
) -> Decimal | None:
    """One nutrient's amount, or None when the record does not give it. Never negative."""
    value = unit_amount(amounts, units, number, unit)
    if value is not None and value < 0:
        raise Rejected(f"nutrient {number} is negative")
    return value


def first_amount(
    amounts: dict[int, Decimal], units: dict[str, str], numbers: list[int], unit: str
) -> Decimal | None:
    for number in numbers:
        value = amount_of(amounts, units, number, unit)
        if value is not None:
            return value
    return None


def preparation_state(description: str) -> str | None:
    """The last comma-separated word of the description, when it names a state."""
    last = description.rsplit(",", 1)[-1].strip().lower()
    return last if last in PREPARATION_STATES else None


def format_amount(value: Decimal) -> str:
    return format(value.normalize(), "f")


def portions_of(rows: list[dict]) -> list[Portion]:
    """Gram portions from SR Legacy/Foundation rows; the modifier names the measure."""
    portions: list[Portion] = []
    seen: set[str] = set()
    for row in rows:
        modifier = (row.get("modifier") or "").strip()
        amount = row.get("amount") or ""
        grams = row.get("gram_weight") or ""
        if not modifier or not amount or not grams:
            continue
        quantity = Decimal(grams)
        if quantity <= 0:
            continue
        name = f"{format_amount(Decimal(amount))} {modifier}"
        if name in seen:
            continue
        seen.add(name)
        kind = "serving" if modifier.lower().startswith("serving") else "household"
        portions.append(Portion(name=name, kind=kind, quantity=quantity, unit="g"))
    return portions


def nutrition(
    amounts: dict[int, Decimal], units: dict[str, str], derived: list[str], notes: list[str]
) -> dict[str, Decimal | None]:
    """The label columns for one food. Missing stays None, never zero."""
    values: dict[str, Decimal | None] = {column: None for column in LABEL_COLUMNS}
    for column, (numbers, unit) in DIRECT.items():
        values[column] = first_amount(amounts, units, numbers, unit)

    if values["energy_kj"] is None and values["energy_kcal"] is not None:
        values["energy_kj"] = (values["energy_kcal"] * KJ_PER_KCAL).quantize(
            Decimal("0.1"), rounding=ROUND_HALF_UP
        )
        derived.append("energy_kj")

    total = unit_amount(amounts, units, TOTAL_CARBOHYDRATE, "G")
    if total is not None and total < 0:
        if total < -CARB_TOLERANCE:
            raise Rejected(f"carbohydrate by difference is {total} g")
        notes.append(f"carbs_clamped: carbohydrate by difference {total} g set to 0")
        total = Decimal(0)
    fiber = values["fiber_g"]
    if total is not None and fiber is not None:
        if fiber > total:
            raise Rejected("fiber is above total carbohydrate")
        values["carbs_g"] = total - fiber  # the label's available carbohydrate

    sodium = amount_of(amounts, units, SODIUM, "MG")
    if sodium is not None:
        values["salt_g"] = sodium * SALT_PER_SODIUM / 1000

    sugars, carbs = values["sugars_g"], values["carbs_g"]
    if sugars is not None and carbs is not None and sugars > carbs:
        if sugars - carbs <= SUGAR_TOLERANCE:
            notes.append(f"rounding: sugars {sugars} g above available carbohydrate {carbs} g")
        else:
            notes.append(
                f"sugars_unknown: sugars {sugars} g above available carbohydrate {carbs} g; "
                "sugars left unknown"
            )
            values["sugars_g"] = None
    return values


def other_nutrients(amounts: dict[int, Decimal], units: dict[str, str]) -> dict[str, Decimal]:
    result: dict[str, Decimal] = {}
    for key, (numbers, unit, _catalog_unit) in OTHER.items():
        value = first_amount(amounts, units, numbers, unit)
        if value is not None:
            result[key] = value
    return result


def build_food(
    *,
    fdc_id: int,
    description: str,
    data_type: str,
    publication_date: str,
    amounts: dict[int, Decimal],
    units: dict[str, str],
    portion_rows: list[dict],
    german_name: str | None,
) -> Food:
    """One validated food. Raises Rejected with the reason when a rule is broken."""
    if not description.strip():
        raise Rejected("no description")
    if not amounts:
        raise Rejected("no nutrient values")
    derived: list[str] = []
    notes: list[str] = []
    nutrients = nutrition(amounts, units, derived, notes)
    return Food(
        fdc_id=fdc_id,
        description=description.strip(),
        data_type=data_type,
        publication_date=publication_date,
        german_name=german_name,
        preparation_state=preparation_state(description),
        nutrients=nutrients,
        other=other_nutrients(amounts, units),
        portions=portions_of(portion_rows),
        derived=derived,
        notes=notes,
    )
