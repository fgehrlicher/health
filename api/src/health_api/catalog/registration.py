"""Validate and register branded foods submitted by agents, e.g. from label photos."""

import re
import unicodedata
from decimal import Decimal

from psycopg import Connection

from health_api.catalog.models import FoodInput, NutritionInput, SourceTextUpdate
from health_api.catalog.repository import NUTRIENTS, get_food

MANDATORY_LABEL_ROWS = ("energy_kj", "saturated_fat_g", "sugars_g", "salt_g")


class RegistrationError(Exception):
    """The submission contradicts itself or the catalog; nothing was written."""

    def __init__(self, issues: list[dict]):
        super().__init__("; ".join(f"{issue['field']}: {issue['message']}" for issue in issues))
        self.issues = issues


class BarcodeConflict(Exception):
    def __init__(self, slug: str):
        super().__init__(f"barcode already registered as {slug}")
        self.slug = slug


def barcode_problem(barcode: str) -> str | None:
    """Why a barcode cannot identify a product, or None for a valid GTIN."""
    if not barcode.isascii() or not barcode.isdigit() or len(barcode) not in (8, 12, 13):
        return "must be 8, 12, or 13 digits (EAN-8, UPC-A, EAN-13)"
    digits = [int(digit) for digit in barcode]
    # GS1 check digit: weights 3, 1, 3, ... from the right, excluding the check digit.
    total = sum(digit * (3 if index % 2 == 0 else 1) for index, digit in enumerate(digits[-2::-1]))
    if (10 - total % 10) % 10 != digits[-1]:
        return "check digit does not match; the barcode was probably misread"
    restricted = (
        (len(barcode) == 13 and barcode[0] == "2")
        or (len(barcode) == 12 and barcode[0] == "2")
        or (len(barcode) == 8 and barcode[0] in "02")
    )
    if restricted:
        return "store-internal code (e.g. weighed goods), not a product identity"
    return None


def energy_from_macros(nutrition: NutritionInput) -> Decimal:
    """kcal from EU conversion factors; missing optional components count as 0."""
    polyols = nutrition.polyols_g or 0
    return (
        nutrition.protein_g * 4
        + nutrition.fat_g * 9
        + (nutrition.carbs_g - polyols) * 4
        + polyols * Decimal("2.4")
        + (nutrition.fiber_g or 0) * 2
        + (nutrition.alcohol_g or 0) * 7
    )


def check_food(food: FoodInput) -> tuple[list[dict], list[dict]]:
    """Errors block registration; warnings ask the agent to double-check."""
    errors: list[dict] = []
    warnings: list[dict] = []

    def error(field: str, message: str) -> None:
        errors.append({"field": field, "message": message})

    def warning(field: str, message: str) -> None:
        warnings.append({"field": field, "message": message})

    if not food.name.strip():
        error("name", "must not be blank")
    if food.barcode is not None and (problem := barcode_problem(food.barcode)):
        error("barcode", problem)
    if food.barcode is None:
        warning("barcode", "no barcode; the food cannot be found by scanning later")

    n = food.nutrition
    per_100 = Decimal(100) / n.reference_quantity
    for field in NUTRIENTS:
        value = getattr(n, field)
        if field.endswith("_g") and value is not None and value > n.reference_quantity:
            error(f"nutrition.{field}", f"exceeds the reference quantity {n.reference_quantity}")
    if n.energy_kcal * per_100 > 900:
        error("nutrition.energy_kcal", "above 900 kcal per 100, more than pure fat")
    for field in n.upper_bounds:
        if getattr(n, field) is None:
            error("nutrition.upper_bounds", f"{field} is listed but has no value")

    # "davon" rows are parts of their parent row; allow for rounding of each row.
    fats = (n.saturated_fat_g, n.monounsaturated_fat_g, n.polyunsaturated_fat_g)
    if sum(value or 0 for value in fats) > n.fat_g + Decimal("0.2"):
        error("nutrition.saturated_fat_g", "fatty acids add up to more than fat")
    carbs = (n.sugars_g, n.polyols_g, n.starch_g)
    if sum(value or 0 for value in carbs) > n.carbs_g + Decimal("0.2"):
        error("nutrition.sugars_g", "sugars, polyols, and starch add up to more than carbs")

    if n.energy_kj is not None:
        expected_kj = n.energy_kcal * Decimal("4.184")
        if abs(n.energy_kj - expected_kj) > max(expected_kj * Decimal("0.05"), Decimal(6)):
            error("nutrition.energy_kj", f"{n.energy_kj} kJ does not match {n.energy_kcal} kcal")

    # Labels calculate energy from the same rows, so a misread digit shows here.
    calculated = energy_from_macros(n)
    difference = abs(calculated - n.energy_kcal)
    message = f"macros give {calculated:.0f} kcal but the label says {n.energy_kcal} kcal"
    if difference > max(n.energy_kcal * Decimal("0.2"), Decimal(10)):
        error("nutrition.energy_kcal", message)
    elif difference > max(n.energy_kcal * Decimal("0.08"), Decimal(5)):
        warning("nutrition.energy_kcal", message)

    for field in MANDATORY_LABEL_ROWS:
        if getattr(n, field) is None:
            warning(f"nutrition.{field}", "mandatory on EU labels; check the photo")
    if food.ingredients_text is None:
        warning("ingredients_text", "mandatory on most EU labels; send the full list if visible")
    elif not food.ingredients_text.strip():
        error("ingredients_text", "must not be blank")

    names = [portion.name.casefold() for portion in food.portions]
    if len(set(names)) != len(names):
        error("portions", "portion names must be unique")
    if sum(portion.kind == "package" for portion in food.portions) > 1:
        error("portions", "at most one package portion")
    for index, portion in enumerate(food.portions):
        if portion.unit != n.reference_unit:
            error(f"portions.{index}.unit", f"must match the nutrition unit {n.reference_unit}")
    return errors, warnings


def slugify(text: str) -> str:
    text = text.casefold()
    for letter, replacement in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(letter, replacement)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:80].strip("-") or "food"


def register_food(connection: Connection, food: FoodInput, dry_run: bool) -> dict:
    errors, warnings = check_food(food)
    if errors:
        raise RegistrationError(errors)
    with connection.transaction():
        connection.execute(
            "SELECT pg_advisory_xact_lock(hashtext('health:food-registration')::bigint)"
        )
        if food.barcode is not None:
            existing = connection.execute(
                "SELECT slug FROM foods WHERE barcode = %s", (food.barcode,)
            ).fetchone()
            if existing:
                raise BarcodeConflict(existing["slug"])
        base = slugify(" ".join(filter(None, (food.brand, food.name))))
        slug, suffix = base, 1
        while connection.execute("SELECT 1 FROM foods WHERE slug = %s", (slug,)).fetchone():
            suffix += 1
            slug = f"{base}-{suffix}"
        if dry_run:
            return {"dry_run": True, "slug": slug, "warnings": warnings, "food": None}

        food_id = connection.execute(
            """INSERT INTO foods (slug, name, aliases, kind, brand, barcode)
               VALUES (%s, %s, %s, 'branded', %s, %s) RETURNING id""",
            (slug, food.name.strip(), food.aliases, food.brand, food.barcode),
        ).fetchone()["id"]
        n = food.nutrition
        columns = ", ".join(NUTRIENTS)
        placeholders = ", ".join(f"%({column})s" for column in NUTRIENTS)
        connection.execute(
            f"""INSERT INTO food_sources
                   (food_id, source_name, external_id, food_name, reference_quantity,
                    reference_unit, upper_bounds, ingredients_text, {columns})
               VALUES (%(food_id)s, %(source_name)s, %(external_id)s, %(food_name)s,
                       %(reference_quantity)s, %(reference_unit)s, %(upper_bounds)s,
                       %(ingredients_text)s, {placeholders})""",
            {
                "food_id": food_id,
                "source_name": food.source_name,
                "external_id": food.barcode,
                "food_name": food.source_food_name or food.name.strip(),
                "reference_quantity": n.reference_quantity,
                "reference_unit": n.reference_unit,
                "upper_bounds": n.upper_bounds,
                "ingredients_text": food.ingredients_text.strip()
                if food.ingredients_text
                else None,
                **{column: getattr(n, column) for column in NUTRIENTS},
            },
        )
        for portion in food.portions:
            connection.execute(
                """INSERT INTO food_portions (food_id, name, kind, quantity, unit)
                   VALUES (%s, %s, %s, %s, %s)""",
                (food_id, portion.name, portion.kind, portion.quantity, portion.unit),
            )
        connection.execute("REFRESH MATERIALIZED VIEW food_search_terms")
        connection.execute("REFRESH MATERIALIZED VIEW food_search_vocabulary")
        return {
            "dry_run": False,
            "slug": slug,
            "warnings": warnings,
            "food": get_food(connection, slug),
        }


class SourceNotFound(Exception):
    pass


def update_source_text(
    connection: Connection, slug: str, source_id: int, update: SourceTextUpdate
) -> dict:
    """Set a registered source's legal name or ingredients; nutrition stays unchanged.

    Changed nutrition means a new label version, not an edit. BLS sources belong
    to the importer.
    """
    fields = {name: value.strip() for name, value in update.model_dump(exclude_none=True).items()}
    if not fields:
        raise RegistrationError([{"field": "body", "message": "nothing to update"}])
    blank = [name for name, value in fields.items() if not value]
    if blank:
        raise RegistrationError([{"field": name, "message": "must not be blank"} for name in blank])
    with connection.transaction():
        source = connection.execute(
            """SELECT s.id, s.source_name FROM food_sources s JOIN foods f ON f.id = s.food_id
               WHERE f.slug = %s AND s.id = %s FOR UPDATE""",
            (slug, source_id),
        ).fetchone()
        if source is None:
            raise SourceNotFound(f"food {slug} has no source {source_id}")
        if source["source_name"] == "BLS 4.0":
            raise RegistrationError(
                [{"field": "source", "message": "BLS sources are maintained by the importer"}]
            )
        assignments = ", ".join(f"{name} = %({name})s" for name in fields)
        connection.execute(
            f"UPDATE food_sources SET {assignments} WHERE id = %(id)s", {**fields, "id": source_id}
        )
        if "food_name" in fields:
            connection.execute("REFRESH MATERIALIZED VIEW food_search_terms")
            connection.execute("REFRESH MATERIALIZED VIEW food_search_vocabulary")
        return get_food(connection, slug)
