"""The cooking log: what was cooked when, with what actually went into the pot.

A cook usually starts from a recipe version and records the real ingredient
list, which often differs (the whole can of coconut milk). The pot is split
into equal portions; meals log portions of it, and their nutrition is the
cook's total divided by its portions.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from psycopg import Connection
from pydantic import BaseModel, ConfigDict, Field

from health_api.clock import day_bounds, local_time, timezone
from health_api.ingredients import (
    FoodAmount,
    InputError,
    changes,
    insert_amounts,
    load_amounts,
    public_amount,
    resolve_amounts,
)
from health_api.nutrition import public_sums, status, sums

MAX_ITEMS = 100
Portions = Annotated[Decimal, Field(gt=0, le=100, max_digits=6, decimal_places=3)]
Note = Annotated[str | None, Field(max_length=2000)]


class CookInput(BaseModel):
    """A cook from a recipe version, or an improvised one with a name and items."""

    model_config = ConfigDict(extra="forbid")

    # Recipe slug; without it the cook is improvised and needs name, portions, and items.
    recipe: Annotated[str | None, Field(min_length=1, max_length=200)] = None
    # Version number; default the recipe's latest version.
    version: Annotated[int | None, Field(gt=0)] = None
    # Default: the recipe's name.
    name: Annotated[str | None, Field(min_length=1, max_length=200)] = None
    # Without an offset, the time is local (HEALTH_TIMEZONE). Default: now.
    cooked_at: datetime | None = None
    # Equal parts the pot was split into. Default: the version's portions.
    portions: Portions | None = None
    weight_g: Annotated[Decimal | None, Field(gt=0, le=50000, max_digits=8, decimal_places=1)] = (
        None
    )
    note: Note = None
    # What actually went in, all of it. Default: the version's ingredients.
    items: Annotated[list[FoodAmount] | None, Field(min_length=1, max_length=MAX_ITEMS)] = None


class CookUpdate(BaseModel):
    """Only the given fields change; `items` replaces all ingredients."""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str | None, Field(min_length=1, max_length=200)] = None
    cooked_at: datetime | None = None
    portions: Portions | None = None
    weight_g: Annotated[Decimal | None, Field(gt=0, le=50000, max_digits=8, decimal_places=1)] = (
        None
    )
    note: Note = None
    items: Annotated[list[FoodAmount] | None, Field(min_length=1, max_length=MAX_ITEMS)] = None


class CookNotFound(Exception):
    pass


class CookInUse(Exception):
    pass


def clean_text(text: str | None) -> str | None:
    """Trimmed text; blank means none."""
    return text.strip() or None if text is not None else None


def find_version(connection: Connection, recipe: str, number: int | None, field: str) -> dict:
    """A recipe's version by number, or its latest; fail with an issue."""
    found = connection.execute(
        """SELECT v.id, v.number, v.portions, r.name AS recipe_name
           FROM recipe.versions v JOIN recipe.recipes r ON r.id = v.recipe_id
           WHERE r.slug = %(recipe)s AND (%(number)s::int IS NULL OR v.number = %(number)s)
           ORDER BY v.number DESC LIMIT 1""",
        {"recipe": recipe, "number": number},
    ).fetchone()
    if found is None:
        exists = connection.execute(
            "SELECT 1 FROM recipe.recipes WHERE slug = %s", (recipe,)
        ).fetchone()
        message = f"{recipe!r} has no version {number}" if exists else f"unknown recipe {recipe!r}"
        raise InputError([{"field": field, "message": message}])
    return found


def version_rows(connection: Connection, version_id: int) -> list[dict]:
    return [
        {"source_id": row["source_id"], "amount": row["amount"], "estimated": row["estimated"]}
        for row in connection.execute(
            """SELECT source_id, amount, estimated FROM recipe.version_items
               WHERE version_id = %s ORDER BY id""",
            (version_id,),
        )
    ]


def add_cook(connection: Connection, cook: CookInput) -> int:
    """Store a cook; the caller owns the transaction."""
    cooked_at = local_time(cook.cooked_at, "cooked_at")
    version = None
    if cook.recipe is not None:
        version = find_version(connection, cook.recipe, cook.version, "version")
    else:
        issues = [
            {"field": field, "message": "required for a cook without a recipe"}
            for field in ("name", "portions", "items")
            if getattr(cook, field) is None
        ]
        if cook.version is not None:
            issues.append({"field": "version", "message": "needs a recipe"})
        if issues:
            raise InputError(issues)
    if cook.items is not None:
        rows = resolve_amounts(connection, cook.items)
    else:
        rows = version_rows(connection, version["id"])
    name = clean_text(cook.name) or version["recipe_name"]
    cook_id = connection.execute(
        """INSERT INTO recipe.cooks (version_id, name, cooked_at, portions, weight_g, note)
           VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
        (
            version and version["id"],
            name,
            cooked_at,
            cook.portions or version["portions"],
            cook.weight_g,
            clean_text(cook.note),
        ),
    ).fetchone()["id"]
    insert_amounts(connection, "recipe.cook_items", cook_id, rows)
    return cook_id


def update_cook(connection: Connection, cook_id: int, update: CookUpdate) -> None:
    given = update.model_fields_set
    for field in ("name", "cooked_at", "portions"):
        if field in given and getattr(update, field) is None:
            raise InputError([{"field": field, "message": "cannot be cleared"}])
    found = connection.execute(
        "SELECT 1 FROM recipe.cooks WHERE id = %s FOR UPDATE", (cook_id,)
    ).fetchone()
    if found is None:
        raise CookNotFound(f"no cook {cook_id}")
    cooked_at = local_time(update.cooked_at, "cooked_at") if "cooked_at" in given else None
    if update.items is not None:
        rows = resolve_amounts(connection, update.items)
        connection.execute("DELETE FROM recipe.cook_items WHERE cook_id = %s", (cook_id,))
        insert_amounts(connection, "recipe.cook_items", cook_id, rows)
    values = {
        "name": clean_text(update.name),
        "cooked_at": cooked_at,
        "portions": update.portions,
        "weight_g": update.weight_g,
        "note": clean_text(update.note),
    }
    changed = [field for field in values if field in given]
    if changed:
        assignments = ", ".join(f"{field} = %({field})s" for field in changed)
        connection.execute(
            f"UPDATE recipe.cooks SET {assignments} WHERE id = %(id)s", values | {"id": cook_id}
        )


def delete_cook(connection: Connection, cook_id: int) -> None:
    eaten = connection.execute(
        "SELECT count(*) AS n FROM log.meal_items WHERE cook_id = %s", (cook_id,)
    ).fetchone()["n"]
    if eaten:
        raise CookInUse(f"cook {cook_id} is in {eaten} logged meal items; remove those first")
    deleted = connection.execute(
        "DELETE FROM recipe.cooks WHERE id = %s RETURNING id", (cook_id,)
    ).fetchone()
    if deleted is None:
        raise CookNotFound(f"no cook {cook_id}")


def dish_values(items: list[dict]) -> dict[str, Decimal | None]:
    """A dish's exact total per nutrient; None when any ingredient lacks it."""
    return {
        column: None if part["missing"] else part["measured"] + part["estimated"]
        for column, part in sums(items).items()
    }


def cook_sources(connection: Connection, cook_ids: list[int]) -> dict[int, dict]:
    """Cooks as sources for meal items: totals per `portions` portions."""
    if not cook_ids:
        return {}
    items = load_amounts(connection, "recipe.cook_items", cook_ids)
    result = {}
    for cook in connection.execute(
        """SELECT c.id, c.name, c.cooked_at, c.portions, r.slug AS recipe_slug,
                  r.name AS recipe_name
           FROM recipe.cooks c
           LEFT JOIN recipe.versions v ON v.id = c.version_id
           LEFT JOIN recipe.recipes r ON r.id = v.recipe_id
           WHERE c.id = ANY(%s)""",
        (cook_ids,),
    ):
        ingredients = items.get(cook["id"], [])
        result[cook["id"]] = {
            **cook,
            "recipe": {"slug": cook["recipe_slug"], "name": cook["recipe_name"]}
            if cook["recipe_slug"]
            else None,
            # Any guessed ingredient makes what is eaten from the pot an estimate.
            "estimated": any(item["estimated"] for item in ingredients),
            "values": dish_values(ingredients),
        }
    return result


def load_cooks(
    connection: Connection, where: str, params: dict, details: bool = True, limit: int = 1000
) -> list[dict]:
    """Cooks as the API shows them, newest first; details adds items and changes."""
    cooks = connection.execute(
        f"""SELECT c.id, c.name, c.cooked_at, c.portions, c.weight_g, c.note, c.version_id,
                   v.number AS version, r.slug AS recipe_slug, r.name AS recipe_name,
                   (SELECT coalesce(sum(amount), 0) FROM log.meal_items m
                    WHERE m.cook_id = c.id) AS portions_eaten
            FROM recipe.cooks c
            LEFT JOIN recipe.versions v ON v.id = c.version_id
            LEFT JOIN recipe.recipes r ON r.id = v.recipe_id
            WHERE {where}
            ORDER BY c.cooked_at DESC, c.id DESC
            LIMIT %(limit)s""",
        params | {"limit": limit},
    ).fetchall()
    ids = [cook["id"] for cook in cooks]
    items = load_amounts(connection, "recipe.cook_items", ids)
    planned = load_amounts(
        connection, "recipe.version_items", [c["version_id"] for c in cooks if c["version_id"]]
    )
    zone = timezone()
    result = []
    for cook in cooks:
        ingredients = items.get(cook["id"], [])
        exact = sums(ingredients)
        public = {
            "id": cook["id"],
            "name": cook["name"],
            "recipe": {"slug": cook["recipe_slug"], "name": cook["recipe_name"]}
            if cook["recipe_slug"]
            else None,
            "version": cook["version"],
            "cooked_at": cook["cooked_at"].astimezone(zone).isoformat(),
            "portions": str(cook["portions"]),
            "weight_g": None if cook["weight_g"] is None else str(cook["weight_g"]),
            "note": cook["note"],
            "portions_eaten": str(cook["portions_eaten"]),
            "portions_left": str(max(cook["portions"] - cook["portions_eaten"], Decimal(0))),
            "status": status(ingredients),
            "totals": public_sums(exact),
            "per_portion": public_sums(exact, cook["portions"]),
        }
        if details:
            public["items"] = [public_amount(item) for item in ingredients]
            public["changes"] = (
                changes(planned.get(cook["version_id"], []), ingredients)
                if cook["version_id"]
                else []
            )
        result.append(public)
    return result


def get_cook(connection: Connection, cook_id: int) -> dict | None:
    cooks = load_cooks(connection, "c.id = %(id)s", {"id": cook_id})
    return cooks[0] if cooks else None


def list_cooks(
    connection: Connection,
    recipe: str | None,
    q: str | None,
    since: date | None,
    until: date | None,
    limit: int,
) -> list[dict]:
    """Cooks newest first, by recipe, name words, or local days (inclusive)."""
    words = (q or "").split()
    where = ["(%(recipe)s::text IS NULL OR r.slug = %(recipe)s)"]
    params: dict = {"recipe": recipe}
    for index, word in enumerate(words):
        where.append(f"(c.name ILIKE %(w{index})s OR r.name ILIKE %(w{index})s)")
        params[f"w{index}"] = f"%{word}%"
    if since:
        where.append("c.cooked_at >= %(since)s")
        params["since"] = day_bounds(since)[0]
    if until:
        where.append("c.cooked_at < %(until)s")
        params["until"] = day_bounds(until)[1]
    return load_cooks(connection, " AND ".join(where), params, details=False, limit=limit)
