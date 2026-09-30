"""Export and apply mock data: registered products and one logged day.

The mock file holds what BLS cannot rebuild: branded foods (as registration
input) and a day of meals (with times of day, not dates). `apply` goes through
the same validation and code as the API, so it works on any database that has
the schema and the BLS import, and repeated runs add nothing twice.
"""

import argparse
import json
import sys
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

import psycopg

from health_api.catalog.models import FoodInput
from health_api.catalog.registration import BarcodeConflict, RegistrationError, register_food
from health_api.catalog.repository import NUTRIENTS
from health_api.db import connect
from health_api.log.meals import LogError, MealInput, add_meal, day_bounds, timezone

MOCK_FILE = Path(__file__).resolve().parents[3] / "db/fixtures/mock.json"


def plain(value: object) -> object:
    """Decimals as exact text, keeping the printed precision ("3.0", not 3)."""
    return str(value) if isinstance(value, Decimal) else value


def export_mock(connection: psycopg.Connection, day: date) -> dict:
    foods = []
    for food in connection.execute(
        """SELECT id, slug, name, aliases, brand, barcode, food_group FROM catalog.foods
           WHERE kind = 'branded' ORDER BY id"""
    ).fetchall():
        # The newest source is the current label.
        source = connection.execute(
            f"""SELECT source_name, food_name, ingredients_text, reference_quantity,
                       reference_unit, upper_bounds, {", ".join(NUTRIENTS)}
                FROM catalog.food_sources WHERE food_id = %s ORDER BY id DESC LIMIT 1""",
            (food["id"],),
        ).fetchone()
        portions = connection.execute(
            """SELECT name, kind, quantity, unit FROM catalog.food_portions
               WHERE food_id = %s ORDER BY quantity, name""",
            (food["id"],),
        ).fetchall()
        nutrition = {
            "reference_quantity": plain(source["reference_quantity"]),
            "reference_unit": source["reference_unit"],
            **{column: plain(source[column]) for column in NUTRIENTS if source[column] is not None},
        }
        if source["upper_bounds"]:
            nutrition["upper_bounds"] = source["upper_bounds"]
        foods.append(
            {
                "slug": food["slug"],
                "name": food["name"],
                "brand": food["brand"],
                "barcode": food["barcode"],
                "food_group": food["food_group"],
                "aliases": food["aliases"],
                "source_name": source["source_name"],
                "source_food_name": source["food_name"],
                "ingredients_text": source["ingredients_text"],
                "nutrition": nutrition,
                "portions": [
                    {**portion, "quantity": plain(portion["quantity"])} for portion in portions
                ],
            }
        )

    start, end = day_bounds(day)
    meals = []
    for meal in connection.execute(
        """SELECT id, eaten_at, kind, note FROM log.meals
           WHERE eaten_at >= %s AND eaten_at < %s ORDER BY eaten_at, id""",
        (start, end),
    ).fetchall():
        items = connection.execute(
            """SELECT f.slug AS food, i.amount, i.estimated
               FROM log.meal_items i
               JOIN catalog.food_sources s ON s.id = i.source_id
               JOIN catalog.foods f ON f.id = s.food_id
               WHERE i.meal_id = %s ORDER BY i.id""",
            (meal["id"],),
        ).fetchall()
        meals.append(
            {
                "time": meal["eaten_at"].astimezone(timezone()).strftime("%H:%M"),
                "kind": meal["kind"],
                "note": meal["note"],
                "items": [
                    {"food": item["food"], "amount": plain(item["amount"])}
                    | ({"estimated": True} if item["estimated"] else {})
                    for item in items
                ],
            }
        )
    return {"foods": foods, "meals": meals}


def apply_mock(connection: psycopg.Connection, mock: dict, day: date, replace: bool) -> list[str]:
    """Register the foods, then log the meals on `day`; returns what happened."""
    report = []
    if connection.execute("SELECT count(*) AS n FROM catalog.foods").fetchone()["n"] == 0:
        raise SystemExit("the catalog is empty: run `uv run --locked bls4-import` first")

    # Exported slug -> slug in this database (the same unless one was taken).
    slugs: dict[str, str] = {}
    for food in mock["foods"]:
        exported_slug = food["slug"]
        food_input = FoodInput.model_validate({k: v for k, v in food.items() if k != "slug"})
        try:
            result = register_food(connection, food_input, dry_run=False)
            slugs[exported_slug] = result["slug"]
            report.append(f"registered {result['slug']}")
        except BarcodeConflict as conflict:
            slugs[exported_slug] = conflict.slug
            report.append(f"kept {conflict.slug} (barcode already registered)")

    start, end = day_bounds(day)
    existing = connection.execute(
        "SELECT count(*) AS n FROM log.meals WHERE eaten_at >= %s AND eaten_at < %s",
        (start, end),
    ).fetchone()["n"]
    if existing and not replace:
        report.append(f"{day} already has {existing} meals; left unchanged (use --replace)")
        return report
    with connection.transaction():
        if existing:
            connection.execute(
                "DELETE FROM log.meals WHERE eaten_at >= %s AND eaten_at < %s", (start, end)
            )
            report.append(f"deleted {existing} meals on {day}")
        for meal in mock["meals"]:
            # Local time of day in the app's zone, on the target day.
            eaten_at = datetime.combine(day, time.fromisoformat(meal["time"]), timezone())
            meal_input = MealInput.model_validate(
                {
                    "eaten_at": eaten_at.isoformat(),
                    "kind": meal["kind"],
                    "note": meal["note"],
                    "items": [
                        {**item, "food": slugs.get(item["food"], item["food"])}
                        for item in meal["items"]
                    ],
                }
            )
            add_meal(connection, meal_input)
        report.append(f"logged {len(mock['meals'])} meals on {day}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Export or apply the development mock data")
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export", help="write branded foods and one day to the file")
    export.add_argument("--date", type=date.fromisoformat, help="day to export; default today")
    apply = commands.add_parser("apply", help="register the foods and log the day")
    apply.add_argument("--date", type=date.fromisoformat, help="day to log on; default today")
    apply.add_argument("--replace", action="store_true", help="replace that day's meals")
    for command in (export, apply):
        command.add_argument("--file", type=Path, default=MOCK_FILE)
    options = parser.parse_args()
    day = options.date or datetime.now(timezone()).date()

    try:
        with connect() as connection:
            if options.command == "export":
                mock = export_mock(connection, day)
                options.file.write_text(
                    json.dumps(mock, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
                )
                print(
                    f"wrote {len(mock['foods'])} foods and {len(mock['meals'])} meals "
                    f"from {day} to {options.file}"
                )
            else:
                mock = json.loads(options.file.read_text(encoding="utf-8"))
                print("\n".join(apply_mock(connection, mock, day, options.replace)))
    except (RegistrationError, LogError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except psycopg.OperationalError as error:
        print(f"error: database unavailable: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
