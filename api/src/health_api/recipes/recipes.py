"""Recipes as lines of versions.

A version is a fixed ingredient list with portions, free-text steps, and a
note on what changed. Ingredients never change in place: an improvement is a
new version whose parent is the version it came from. A parent in another
recipe makes a fork, e.g. a mango ice cream developed from the plain one. A
cook that turned out well can be saved as a new version.
"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated

import psycopg
from psycopg import Connection
from pydantic import BaseModel, ConfigDict, Field

from health_api.catalog.registration import slugify
from health_api.clock import timezone
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
from health_api.recipes.cooks import MAX_ITEMS, Note, Portions, clean_text, list_cooks

Name = Annotated[str, Field(min_length=1, max_length=200)]
Instructions = Annotated[str | None, Field(max_length=20000)]
Items = Annotated[list[FoodAmount] | None, Field(min_length=1, max_length=MAX_ITEMS)]


class VersionRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipe: Name
    # Default: the recipe's latest version.
    version: Annotated[int | None, Field(gt=0)] = None


class RecipeInput(BaseModel):
    """A new recipe and its first version.

    Ingredients and portions come from `items` and `portions`, otherwise from
    `from_cook`, otherwise from the `forked_from` version.
    """

    model_config = ConfigDict(extra="forbid")

    name: Name
    note: Note = None
    items: Items = None
    portions: Portions | None = None
    instructions: Instructions = None
    # Develop from another recipe's version.
    forked_from: VersionRef | None = None
    # Save what went into this cook as the first version.
    from_cook: int | None = None


class VersionInput(BaseModel):
    """A new version; anything not given comes from `from_cook` or the parent."""

    model_config = ConfigDict(extra="forbid")

    # What changed and why, e.g. "less salt: v3 was too salty".
    note: Note = None
    items: Items = None
    portions: Portions | None = None
    # Default: the parent's steps.
    instructions: Instructions = None
    # Version number in this recipe. Default: the cook's version, else the latest.
    parent: Annotated[int | None, Field(gt=0)] = None
    from_cook: int | None = None


class RecipeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name | None = None
    note: Note = None


class VersionUpdate(BaseModel):
    """Only text changes; different ingredients or portions are a new version."""

    model_config = ConfigDict(extra="forbid")

    note: Note = None
    instructions: Instructions = None


def local_iso(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(timezone()).isoformat()


class RecipeNotFound(Exception):
    pass


class RecipeInUse(Exception):
    pass


def recipe_id(connection: Connection, slug: str) -> int:
    found = connection.execute("SELECT id FROM recipe.recipes WHERE slug = %s", (slug,)).fetchone()
    if found is None:
        raise RecipeNotFound(f"no recipe {slug}")
    return found["id"]


def version_by_number(connection: Connection, recipe: int, number: int | None) -> dict | None:
    return connection.execute(
        """SELECT id, portions, instructions FROM recipe.versions
           WHERE recipe_id = %(recipe)s AND (%(number)s::int IS NULL OR number = %(number)s)
           ORDER BY number DESC LIMIT 1""",
        {"recipe": recipe, "number": number},
    ).fetchone()


def cook_for_version(connection: Connection, cook_id: int) -> dict:
    cook = connection.execute(
        """SELECT c.id, c.portions, c.version_id, v.recipe_id
           FROM recipe.cooks c LEFT JOIN recipe.versions v ON v.id = c.version_id
           WHERE c.id = %s""",
        (cook_id,),
    ).fetchone()
    if cook is None:
        raise InputError([{"field": "from_cook", "message": f"unknown cook {cook_id}"}])
    return cook


def item_rows(connection: Connection, table: str, owner_id: int) -> list[dict]:
    return [
        {"source_id": item["source_id"], "amount": item["amount"], "estimated": item["estimated"]}
        for item in load_amounts(connection, table, [owner_id]).get(owner_id, [])
    ]


def insert_version(
    connection: Connection,
    recipe: int,
    given: VersionInput | RecipeInput,
    base: dict | None,
    cook: dict | None,
) -> int:
    """Store a version from what was given, then the cook, then the base version."""
    if given.items is not None:
        rows = resolve_amounts(connection, given.items)
    elif cook:
        rows = item_rows(connection, "recipe.cook_items", cook["id"])
    elif base:
        rows = item_rows(connection, "recipe.version_items", base["id"])
    else:
        raise InputError([{"field": "items", "message": "required without from_cook or a parent"}])
    portions = given.portions or (cook and cook["portions"]) or (base and base["portions"])
    if portions is None:
        raise InputError([{"field": "portions", "message": "required"}])
    instructions = (
        given.instructions
        if "instructions" in given.model_fields_set
        else (base and base["instructions"])
    )
    version_note = given.note if isinstance(given, VersionInput) else None
    version_id = connection.execute(
        """INSERT INTO recipe.versions
               (recipe_id, number, parent_id, from_cook_id, note, instructions, portions)
           VALUES (%(recipe)s,
                   (SELECT coalesce(max(number), 0) + 1 FROM recipe.versions
                    WHERE recipe_id = %(recipe)s),
                   %(parent)s, %(cook)s, %(note)s, %(instructions)s, %(portions)s)
           RETURNING id""",
        {
            "recipe": recipe,
            "parent": base and base["id"],
            "cook": cook and cook["id"],
            "note": clean_text(version_note),
            "instructions": clean_text(instructions),
            "portions": portions,
        },
    ).fetchone()["id"]
    insert_amounts(connection, "recipe.version_items", version_id, rows)
    # An improvised cook saved unchanged is now a cook of this version.
    if cook and cook["version_id"] is None and given.items is None:
        connection.execute(
            "UPDATE recipe.cooks SET version_id = %s WHERE id = %s", (version_id, cook["id"])
        )
    return version_id


def create_recipe(connection: Connection, recipe: RecipeInput) -> str:
    """Store a recipe with its first version; returns the slug. The caller owns the transaction."""
    cook = cook_for_version(connection, recipe.from_cook) if recipe.from_cook else None
    base = None
    if recipe.forked_from:
        try:
            source = recipe_id(connection, recipe.forked_from.recipe)
        except RecipeNotFound as error:
            raise InputError([{"field": "forked_from.recipe", "message": str(error)}]) from error
        base = version_by_number(connection, source, recipe.forked_from.version)
        if base is None:
            message = f"{recipe.forked_from.recipe!r} has no version {recipe.forked_from.version}"
            raise InputError([{"field": "forked_from.version", "message": message}])
    elif cook and cook["version_id"]:
        # A cook of another recipe saved as a new one is a fork of its version.
        base = connection.execute(
            "SELECT id, portions, instructions FROM recipe.versions WHERE id = %s",
            (cook["version_id"],),
        ).fetchone()
    name = recipe.name.strip()
    slug, suffix = slugify(name), 1
    while connection.execute("SELECT 1 FROM recipe.recipes WHERE slug = %s", (slug,)).fetchone():
        suffix += 1
        slug = f"{slugify(name)}-{suffix}"
    new_id = connection.execute(
        "INSERT INTO recipe.recipes (slug, name, note) VALUES (%s, %s, %s) RETURNING id",
        (slug, name, clean_text(recipe.note)),
    ).fetchone()["id"]
    insert_version(connection, new_id, recipe, base, cook)
    return slug


def add_version(connection: Connection, slug: str, version: VersionInput) -> int:
    """Store a new version of a recipe; returns its number."""
    recipe = recipe_id(connection, slug)
    # Serialize numbering per recipe.
    connection.execute("SELECT 1 FROM recipe.recipes WHERE id = %s FOR UPDATE", (recipe,))
    cook = cook_for_version(connection, version.from_cook) if version.from_cook else None
    if version.parent is not None:
        base = version_by_number(connection, recipe, version.parent)
        if base is None:
            raise InputError([{"field": "parent", "message": f"no version {version.parent}"}])
    elif cook and cook["recipe_id"] == recipe:
        base = connection.execute(
            "SELECT id, portions, instructions FROM recipe.versions WHERE id = %s",
            (cook["version_id"],),
        ).fetchone()
    else:
        base = version_by_number(connection, recipe, None)
    version_id = insert_version(connection, recipe, version, base, cook)
    return connection.execute(
        "SELECT number FROM recipe.versions WHERE id = %s", (version_id,)
    ).fetchone()["number"]


def update_recipe(connection: Connection, slug: str, update: RecipeUpdate) -> None:
    given = update.model_fields_set
    if "name" in given and update.name is None:
        raise InputError([{"field": "name", "message": "cannot be cleared"}])
    recipe = recipe_id(connection, slug)
    connection.execute(
        """UPDATE recipe.recipes SET
               name = CASE WHEN %(set_name)s THEN %(name)s ELSE name END,
               note = CASE WHEN %(set_note)s THEN %(note)s ELSE note END
           WHERE id = %(id)s""",
        {
            "id": recipe,
            "set_name": "name" in given,
            "name": update.name and update.name.strip(),
            "set_note": "note" in given,
            "note": clean_text(update.note),
        },
    )


def update_version(connection: Connection, slug: str, number: int, update: VersionUpdate) -> None:
    given = update.model_fields_set
    recipe = recipe_id(connection, slug)
    updated = connection.execute(
        """UPDATE recipe.versions SET
               note = CASE WHEN %(set_note)s THEN %(note)s ELSE note END,
               instructions = CASE WHEN %(set_steps)s THEN %(steps)s ELSE instructions END
           WHERE recipe_id = %(recipe)s AND number = %(number)s RETURNING id""",
        {
            "recipe": recipe,
            "number": number,
            "set_note": "note" in given,
            "note": clean_text(update.note),
            "set_steps": "instructions" in given,
            "steps": clean_text(update.instructions),
        },
    ).fetchone()
    if updated is None:
        raise RecipeNotFound(f"{slug} has no version {number}")


def delete_recipe(connection: Connection, slug: str) -> None:
    recipe = recipe_id(connection, slug)
    try:
        with connection.transaction():
            connection.execute("DELETE FROM recipe.recipes WHERE id = %s", (recipe,))
    except psycopg.errors.ForeignKeyViolation as error:
        raise RecipeInUse(
            f"{slug} has cooks or forks; delete those first or keep the recipe"
        ) from error


def load_versions(connection: Connection, recipe: int) -> list[dict]:
    """A recipe's versions, newest first, with ingredients and nutrition."""
    versions = connection.execute(
        """SELECT v.id, v.number, v.from_cook_id, v.note, v.instructions, v.portions,
                  v.created_at, v.parent_id, p.number AS parent_number, pr.slug AS parent_recipe,
                  pr.name AS parent_recipe_name,
                  (SELECT count(*) FROM recipe.cooks c WHERE c.version_id = v.id) AS cooks
           FROM recipe.versions v
           LEFT JOIN recipe.versions p ON p.id = v.parent_id
           LEFT JOIN recipe.recipes pr ON pr.id = p.recipe_id
           WHERE v.recipe_id = %s
           ORDER BY v.number DESC""",
        (recipe,),
    ).fetchall()
    ids = {v["id"] for v in versions} | {v["parent_id"] for v in versions if v["parent_id"]}
    items = load_amounts(connection, "recipe.version_items", sorted(ids))
    result = []
    for version in versions:
        ingredients = items.get(version["id"], [])
        exact = sums(ingredients)
        result.append(
            {
                "id": version["id"],
                "number": version["number"],
                "parent": {
                    "recipe": version["parent_recipe"],
                    "recipe_name": version["parent_recipe_name"],
                    "number": version["parent_number"],
                }
                if version["parent_recipe"]
                else None,
                "changes": changes(items.get(version["parent_id"], []), ingredients)
                if version["parent_id"]
                else [],
                "from_cook_id": version["from_cook_id"],
                "note": version["note"],
                "instructions": version["instructions"],
                "portions": str(version["portions"]),
                "created_at": local_iso(version["created_at"]),
                "cooks": version["cooks"],
                "status": status(ingredients),
                "items": [public_amount(item) for item in ingredients],
                "totals": public_sums(exact),
                "per_portion": public_sums(exact, version["portions"]),
            }
        )
    return result


def get_recipe(connection: Connection, slug: str) -> dict | None:
    recipe = connection.execute(
        "SELECT id, slug, name, note, created_at FROM recipe.recipes WHERE slug = %s", (slug,)
    ).fetchone()
    if recipe is None:
        return None
    forks = connection.execute(
        """SELECT DISTINCT r.slug, r.name, p.number AS from_version
           FROM recipe.versions v
           JOIN recipe.recipes r ON r.id = v.recipe_id
           JOIN recipe.versions p ON p.id = v.parent_id
           WHERE p.recipe_id = %(id)s AND v.recipe_id <> %(id)s
           ORDER BY r.name""",
        {"id": recipe["id"]},
    ).fetchall()
    return {
        "slug": recipe["slug"],
        "name": recipe["name"],
        "note": recipe["note"],
        "created_at": local_iso(recipe["created_at"]),
        "versions": load_versions(connection, recipe["id"]),
        "forks": forks,
        "cooks": list_cooks(connection, slug, None, None, None, 1000),
    }


def list_recipes(connection: Connection, q: str | None) -> list[dict]:
    """Recipes by name words, most recently cooked or created first."""
    words = (q or "").split()
    where = " AND ".join(f"r.name ILIKE %(w{index})s" for index in range(len(words))) or "true"
    recipes = connection.execute(
        f"""SELECT r.id, r.slug, r.name, r.note, latest.id AS version_id,
                   latest.number AS latest_version, latest.portions, cooked.cooks,
                   cooked.last_cooked_at
            FROM recipe.recipes r
            CROSS JOIN LATERAL (
                SELECT id, number, portions FROM recipe.versions
                WHERE recipe_id = r.id ORDER BY number DESC LIMIT 1
            ) latest
            CROSS JOIN LATERAL (
                SELECT count(*) AS cooks, max(c.cooked_at) AS last_cooked_at
                FROM recipe.cooks c JOIN recipe.versions v ON v.id = c.version_id
                WHERE v.recipe_id = r.id
            ) cooked
            WHERE {where}
            ORDER BY greatest(cooked.last_cooked_at, r.created_at) DESC, r.id DESC""",
        {f"w{index}": f"%{word}%" for index, word in enumerate(words)},
    ).fetchall()
    items = load_amounts(connection, "recipe.version_items", [r["version_id"] for r in recipes])
    return [
        {
            "slug": recipe["slug"],
            "name": recipe["name"],
            "note": recipe["note"],
            "latest_version": recipe["latest_version"],
            "cooks": recipe["cooks"],
            "last_cooked_at": local_iso(recipe["last_cooked_at"]),
            "portions": str(recipe["portions"]),
            "per_portion": public_sums(
                sums(items.get(recipe["version_id"], [])), Decimal(recipe["portions"])
            ),
        }
        for recipe in recipes
    ]
