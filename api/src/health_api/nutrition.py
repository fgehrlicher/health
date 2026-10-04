"""Nutrition of amounts of catalog sources: per item and summed, never stored.

An item is a dict with `amount`, `reference_quantity`, `estimated`, and one
value per NUTRIENTS column for that reference quantity (None when unknown).
Meal items, recipe ingredients, and cooked dishes all use this shape.
"""

from decimal import Decimal
from typing import Literal

from health_api.catalog.repository import NUTRIENTS


def rounded(column: str, value: Decimal) -> str:
    places = Decimal(1) if column.startswith("energy") else Decimal("0.01")
    return str(value.quantize(places))


def item_values(item: dict) -> dict[str, Decimal | None]:
    """Each nutrient for the item's amount; None where the source has no value."""
    factor = item["amount"] / item["reference_quantity"]
    return {column: None if item[column] is None else item[column] * factor for column in NUTRIENTS}


def rounded_values(values: dict[str, Decimal | None]) -> dict[str, str | None]:
    return {
        column: None if value is None else rounded(column, value)
        for column, value in values.items()
    }


def status(items: list[dict]) -> Literal["measured", "estimated", "unknown"]:
    if not items:
        return "unknown"
    return "estimated" if any(item["estimated"] for item in items) else "measured"


def sums(items: list[dict]) -> dict[str, dict]:
    """Exact per-nutrient sums of measured and estimated items, and items lacking a value."""
    result = {}
    for column in NUTRIENTS:
        measured = estimated = Decimal(0)
        missing = 0
        for item in items:
            value = item_values(item)[column]
            if value is None:
                missing += 1
            elif item["estimated"]:
                estimated += value
            else:
                measured += value
        result[column] = {"measured": measured, "estimated": estimated, "missing": missing}
    return result


def public_sums(exact: dict[str, dict], divisor: Decimal = Decimal(1)) -> dict:
    """Sums as API totals, optionally divided, e.g. by a dish's portions."""
    return {
        column: {
            "measured": rounded(column, part["measured"] / divisor),
            "estimated": rounded(column, part["estimated"] / divisor),
            "items_without_value": part["missing"],
        }
        for column, part in exact.items()
    }


def totals(items: list[dict]) -> dict:
    """Per nutrient: sums of measured and estimated items, and items lacking a value."""
    return public_sums(sums(items))
