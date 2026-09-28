"""Consumption log: record what was eaten; nutrition always comes from the catalog.

Callers send an observation, a time, and components (catalog food + amount).
They cannot send nutrition values: every number is a catalog source's value
times the amount, snapshotted when logged. An entry without components is valid
and has unknown nutrition.
"""

import os
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

import psycopg
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import JSONResponse
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field, model_validator

from health_catalog.repository import NUTRIENTS

DEFAULT_DATABASE_URL = "postgres://health:health@127.0.0.1:5432/health"
MAX_AMOUNT = Decimal(5000)
# Accept slightly future times from clock skew, not planned meals.
FUTURE_TOLERANCE = timedelta(minutes=10)

Positive = Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=3)]


def timezone() -> ZoneInfo:
    """The person's local zone; days in the log start at local midnight."""
    return ZoneInfo(os.environ.get("HEALTH_TIMEZONE", "Europe/Berlin"))


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


class ItemInput(BaseModel):
    """One component: a catalog food and how much of it, exact or as a range."""

    model_config = ConfigDict(extra="forbid")

    food: Annotated[str, Field(min_length=1, max_length=200, description="catalog slug")]
    # Default: the food's BLS 4.0 source, otherwise its newest source.
    source_id: int | None = None
    # What this component stands for, e.g. "Fladenbrot".
    label: Annotated[str | None, Field(max_length=200)] = None
    # Exactly one of: amount; amount_min and amount_max; portion (with count).
    amount: Positive | None = None
    amount_min: Positive | None = None
    amount_max: Positive | None = None
    portion: Annotated[str | None, Field(max_length=60)] = None
    count: Positive = Decimal(1)

    @model_validator(mode="after")
    def one_amount(self):
        ways = [
            self.amount is not None,
            self.amount_min is not None or self.amount_max is not None,
            self.portion is not None,
        ]
        if sum(ways) != 1:
            raise ValueError("give exactly one of amount, amount_min+amount_max, or portion")
        if ways[1] and (self.amount_min is None or self.amount_max is None):
            raise ValueError("an estimate needs both amount_min and amount_max")
        if ways[1] and self.amount_min > self.amount_max:
            raise ValueError("amount_min exceeds amount_max")
        return self


class EntryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # The person's own words, kept as the original observation.
    observation: Annotated[str, Field(min_length=1, max_length=2000)]
    # Without an offset, the time is local (HEALTH_TIMEZONE). Default: now.
    eaten_at: datetime | None = None
    # Empty means "logged, nutrition unknown".
    items: list[ItemInput] = []


class ItemsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ItemInput]


class EntryTimeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    eaten_at: datetime


class LogError(Exception):
    def __init__(self, issues: list[dict]):
        super().__init__("; ".join(issue["message"] for issue in issues))
        self.issues = issues


def local_time(value: datetime | None) -> datetime:
    zone = timezone()
    if value is None:
        return datetime.now(zone)
    value = value.replace(tzinfo=zone) if value.tzinfo is None else value
    if value > datetime.now(UTC) + FUTURE_TOLERANCE:
        raise LogError([{"field": "eaten_at", "message": "lies in the future"}])
    return value


def resolve_items(connection: Connection, items: list[ItemInput]) -> list[dict]:
    """Turn inputs into rows: source, amount range in its unit, and a value snapshot."""
    rows, issues = [], []
    for index, item in enumerate(items):
        field = f"items.{index}"
        food = connection.execute("SELECT id FROM foods WHERE slug = %s", (item.food,)).fetchone()
        if food is None:
            issues.append({"field": f"{field}.food", "message": f"unknown food {item.food!r}"})
            continue
        source = connection.execute(
            f"""SELECT id, reference_quantity, reference_unit, {", ".join(NUTRIENTS)}
                FROM food_sources
                WHERE food_id = %(food_id)s AND (%(source_id)s::bigint IS NULL OR id = %(source_id)s)
                ORDER BY (source_name = 'BLS 4.0') DESC, id DESC
                LIMIT 1""",
            {"food_id": food["id"], "source_id": item.source_id},
        ).fetchone()
        if source is None:
            message = f"source {item.source_id} is not a source of {item.food!r}"
            issues.append({"field": f"{field}.source_id", "message": message})
            continue
        unit = source["reference_unit"]
        portion_name = portion_count = None
        if item.portion is not None:
            portion = connection.execute(
                """SELECT name, quantity, unit FROM food_portions
                   WHERE food_id = %s AND lower(name) = lower(%s)""",
                (food["id"], item.portion),
            ).fetchone()
            if portion is None or portion["unit"] != unit:
                names = [
                    row["name"]
                    for row in connection.execute(
                        "SELECT name FROM food_portions WHERE food_id = %s ORDER BY name",
                        (food["id"],),
                    )
                ]
                message = f"{item.food!r} has no portion {item.portion!r}; known: {names}"
                issues.append({"field": f"{field}.portion", "message": message})
                continue
            amount_min = amount_max = portion["quantity"] * item.count
            portion_name, portion_count = portion["name"], item.count
        elif item.amount is not None:
            amount_min = amount_max = item.amount
        else:
            amount_min, amount_max = item.amount_min, item.amount_max
        if amount_max > MAX_AMOUNT:
            message = f"more than {MAX_AMOUNT} {unit} in one component"
            issues.append({"field": field, "message": message})
            continue
        rows.append(
            {
                "source_id": source["id"],
                "label": item.label,
                "amount_min": amount_min,
                "amount_max": amount_max,
                "unit": unit,
                "portion_name": portion_name,
                "portion_count": portion_count,
                "reference_quantity": source["reference_quantity"],
                "nutrition": {
                    column: None if source[column] is None else str(source[column])
                    for column in NUTRIENTS
                },
            }
        )
    if issues:
        raise LogError(issues)
    return rows


def insert_items(connection: Connection, entry_id: int, rows: list[dict]) -> None:
    for row in rows:
        connection.execute(
            """INSERT INTO log.entry_items
                   (entry_id, source_id, label, amount_min, amount_max, unit,
                    portion_name, portion_count, reference_quantity, nutrition)
               VALUES (%(entry_id)s, %(source_id)s, %(label)s, %(amount_min)s, %(amount_max)s,
                       %(unit)s, %(portion_name)s, %(portion_count)s, %(reference_quantity)s,
                       %(nutrition)s)""",
            {**row, "entry_id": entry_id, "nutrition": Jsonb(row["nutrition"])},
        )


def rounded(column: str, value: Decimal) -> str:
    places = Decimal(1) if column.startswith("energy") else Decimal("0.01")
    return str(value.quantize(places))


def item_values(item: dict) -> dict[str, tuple[Decimal, Decimal] | None]:
    """Min and max of each nutrient for this item; None where the source has no value."""
    values = {}
    for column in NUTRIENTS:
        per_reference = item["nutrition"].get(column)
        if per_reference is None:
            values[column] = None
            continue
        factor = Decimal(per_reference) / item["reference_quantity"]
        values[column] = (factor * item["amount_min"], factor * item["amount_max"])
    return values


def status(items: list[dict]) -> Literal["measured", "estimated", "unknown"]:
    if not items:
        return "unknown"
    exact = all(item["amount_min"] == item["amount_max"] for item in items)
    return "measured" if exact else "estimated"


def summarize(items: list[dict]) -> dict:
    """Per nutrient: min and max summed over items, and how many items lack a value."""
    totals = {}
    for column in NUTRIENTS:
        low = high = Decimal(0)
        missing = 0
        for item in items:
            value = item_values(item)[column]
            if value is None:
                missing += 1
                continue
            low, high = low + value[0], high + value[1]
        totals[column] = {
            "min": rounded(column, low),
            "max": rounded(column, high),
            "items_without_value": missing,
        }
    return totals


def load_entries(connection: Connection, where: str, params: dict) -> list[dict]:
    entries = connection.execute(
        f"""SELECT id, eaten_at, observation, created_at FROM log.entries
            WHERE deleted_at IS NULL AND {where} ORDER BY eaten_at, id""",
        params,
    ).fetchall()
    if not entries:
        return []
    items: dict[int, list] = {}
    for item in connection.execute(
        """SELECT i.id, i.entry_id, f.slug AS food, f.name AS food_name, i.source_id,
                  s.source_name, i.label, i.amount_min, i.amount_max, i.unit,
                  i.portion_name, i.portion_count, i.reference_quantity, i.nutrition
           FROM log.entry_items i
           JOIN food_sources s ON s.id = i.source_id
           JOIN foods f ON f.id = s.food_id
           WHERE i.superseded_at IS NULL AND i.entry_id = ANY(%s)
           ORDER BY i.id""",
        ([entry["id"] for entry in entries],),
    ):
        items.setdefault(item["entry_id"], []).append(item)
    zone = timezone()
    return [
        {
            "id": entry["id"],
            "eaten_at": entry["eaten_at"].astimezone(zone).isoformat(),
            "observation": entry["observation"],
            "status": status(items.get(entry["id"], [])),
            "items": [public_item(item) for item in items.get(entry["id"], [])],
            "totals": summarize(items.get(entry["id"], [])),
        }
        for entry in entries
    ]


def public_item(item: dict) -> dict:
    return {
        "id": item["id"],
        "food": item["food"],
        "food_name": item["food_name"],
        "source_id": item["source_id"],
        "source_name": item["source_name"],
        "label": item["label"],
        "amount_min": str(item["amount_min"]),
        "amount_max": str(item["amount_max"]),
        "unit": item["unit"],
        "portion": item["portion_name"],
        "portion_count": None if item["portion_count"] is None else str(item["portion_count"]),
        "nutrition": {
            column: None
            if value is None
            else {
                "min": rounded(column, value[0]),
                "max": rounded(column, value[1]),
            }
            for column, value in item_values(item).items()
        },
    }


def get_entry(connection: Connection, entry_id: int) -> dict | None:
    entries = load_entries(connection, "id = %(id)s", {"id": entry_id})
    return entries[0] if entries else None


def create_entry(connection: Connection, entry: EntryInput, dry_run: bool) -> dict:
    eaten_at = local_time(entry.eaten_at)
    with connection.transaction() as transaction:
        rows = resolve_items(connection, entry.items)
        entry_id = connection.execute(
            "INSERT INTO log.entries (eaten_at, observation) VALUES (%s, %s) RETURNING id",
            (eaten_at, entry.observation.strip()),
        ).fetchone()["id"]
        insert_items(connection, entry_id, rows)
        result = get_entry(connection, entry_id)
        if dry_run:
            # Same path as a real write, so the preview shows exactly what would be stored.
            raise psycopg.Rollback(transaction)
    return result


def replace_items(connection: Connection, entry_id: int, items: list[ItemInput]) -> dict | None:
    with connection.transaction():
        found = connection.execute(
            "SELECT 1 FROM log.entries WHERE id = %s AND deleted_at IS NULL FOR UPDATE",
            (entry_id,),
        ).fetchone()
        if found is None:
            return None
        rows = resolve_items(connection, items)
        connection.execute(
            """UPDATE log.entry_items SET superseded_at = now()
               WHERE entry_id = %s AND superseded_at IS NULL""",
            (entry_id,),
        )
        insert_items(connection, entry_id, rows)
        return get_entry(connection, entry_id)


def day_bounds(day: date) -> tuple[datetime, datetime]:
    zone = timezone()
    start = datetime.combine(day, time(), zone)
    return start, datetime.combine(day + timedelta(days=1), time(), zone)


def day_summary(connection: Connection, day: date) -> dict:
    start, end = day_bounds(day)
    entries = load_entries(
        connection, "eaten_at >= %(start)s AND eaten_at < %(end)s", {"start": start, "end": end}
    )
    measured = [entry for entry in entries if entry["status"] == "measured"]
    estimated = [entry for entry in entries if entry["status"] == "estimated"]
    totals = {}
    for column in NUTRIENTS:
        known = sum(Decimal(entry["totals"][column]["min"]) for entry in measured)
        low = sum(Decimal(entry["totals"][column]["min"]) for entry in estimated)
        high = sum(Decimal(entry["totals"][column]["max"]) for entry in estimated)
        missing = sum(entry["totals"][column]["items_without_value"] for entry in entries)
        totals[column] = {
            "measured": rounded(column, Decimal(known)),
            "estimated_min": rounded(column, Decimal(low)),
            "estimated_max": rounded(column, Decimal(high)),
            "items_without_value": missing,
        }
    return {
        "date": day.isoformat(),
        "timezone": timezone().key,
        "entries": entries,
        "counts": {
            "measured": len(measured),
            "estimated": len(estimated),
            "unknown": sum(entry["status"] == "unknown" for entry in entries),
        },
        "totals": totals,
    }


router = APIRouter(prefix="/api/log", tags=["log"])


def issues_response(error: LogError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": error.issues})


@router.post("/entries", status_code=201)
def post_entry(entry: EntryInput, response: Response, dry_run: bool = False):
    """Log something eaten. Nutrition is calculated from the catalog, never sent.

    Items with an exact amount make a measured entry, amount ranges an estimated
    one, no items an unknown one. `dry_run=true` returns the entry without storing it.
    """
    try:
        with psycopg.connect(database_url(), row_factory=dict_row) as connection:
            result = create_entry(connection, entry, dry_run)
    except LogError as error:
        return issues_response(error)
    if dry_run:
        response.status_code = 200
    return result


@router.get("/entries/{entry_id}")
def read_entry(entry_id: int):
    with psycopg.connect(database_url(), row_factory=dict_row) as connection:
        entry = get_entry(connection, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="No such log entry")
    return entry


@router.put("/entries/{entry_id}/items")
def put_items(entry_id: int, body: ItemsInput):
    """Replace an entry's components, e.g. to fill in an unknown meal or correct one.

    The previous components stay stored as superseded.
    """
    try:
        with psycopg.connect(database_url(), row_factory=dict_row) as connection:
            entry = replace_items(connection, entry_id, body.items)
    except LogError as error:
        return issues_response(error)
    if entry is None:
        raise HTTPException(status_code=404, detail="No such log entry")
    return entry


@router.patch("/entries/{entry_id}")
def patch_entry_time(entry_id: int, body: EntryTimeInput):
    """Correct when something was eaten, e.g. "that was yesterday evening"."""
    try:
        eaten_at = local_time(body.eaten_at)
    except LogError as error:
        return issues_response(error)
    with psycopg.connect(database_url(), row_factory=dict_row) as connection:
        updated = connection.execute(
            """UPDATE log.entries SET eaten_at = %s
               WHERE id = %s AND deleted_at IS NULL RETURNING id""",
            (eaten_at, entry_id),
        ).fetchone()
        entry = get_entry(connection, entry_id) if updated else None
    if entry is None:
        raise HTTPException(status_code=404, detail="No such log entry")
    return entry


@router.delete("/entries/{entry_id}", status_code=204)
def delete_entry(entry_id: int):
    """Remove an entry from totals; it stays stored as deleted."""
    with psycopg.connect(database_url(), row_factory=dict_row) as connection:
        deleted = connection.execute(
            """UPDATE log.entries SET deleted_at = now()
               WHERE id = %s AND deleted_at IS NULL RETURNING id""",
            (entry_id,),
        ).fetchone()
    if deleted is None:
        raise HTTPException(status_code=404, detail="No such log entry")
    return Response(status_code=204)


@router.get("/days/{day}")
def read_day(day: date):
    """A local day's entries and totals, keeping measured, estimated, and unknown apart."""
    with psycopg.connect(database_url(), row_factory=dict_row) as connection:
        return day_summary(connection, day)
