"""Deleting a registered product, after another food takes its place.

Meals, recipe versions and cooks point at a product's sources, and the database
refuses to drop a source that is still referenced. So a product in use is only
deleted together with a replacement: every meal item and ingredient that used it
moves to the replacement's source in the same unit (g or ml), with the same
amount, and then the product is gone. Generic foods belong to their importers
(BLS, USDA) and are never deleted here.
"""

import psycopg
from psycopg import Connection
from pydantic import BaseModel

from health_api.catalog.registration import FoodNotFound, RegistrationError

# Each table that holds an amount of a catalog source, with the thing it belongs to.
USERS = {
    "meals": ("log.meal_items", "meal_id"),
    "recipes": ("recipe.version_items", "version_id"),
    "cooks": ("recipe.cook_items", "cook_id"),
}


class FoodUses(BaseModel):
    meals: int
    # Recipes with at least one version that uses the product.
    recipes: int
    cooks: int


class FoodDeletion(BaseModel):
    slug: str
    # The food that takes its place in meals, recipes and cooks, if one was given.
    replaced_with: str | None
    uses: FoodUses
    # True when it is still in use and nothing replaces it: then it cannot be deleted.
    blocked: bool


class FoodInUse(Exception):
    def __init__(self, uses: dict):
        super().__init__("the product is still used; give replace_with to move its uses first")
        self.uses = uses


def count_uses(connection: Connection, source_ids: list[int]) -> dict:
    uses = {}
    for name, (table, owner) in USERS.items():
        if name == "recipes":
            query = f"""SELECT count(DISTINCT v.recipe_id) AS n FROM {table} i
                        JOIN recipe.versions v ON v.id = i.{owner}
                        WHERE i.source_id = ANY(%s)"""
        else:
            query = f"SELECT count(DISTINCT {owner}) AS n FROM {table} WHERE source_id = ANY(%s)"
        uses[name] = connection.execute(query, (source_ids,)).fetchone()["n"]
    return uses


def move_uses(connection: Connection, sources: list[dict], replace_with: str) -> None:
    """Point every use of these sources at the replacement's source in the same unit."""
    target = connection.execute(
        "SELECT id FROM catalog.foods WHERE slug = %s", (replace_with,)
    ).fetchone()
    if target is None:
        raise RegistrationError(
            [{"field": "replace_with", "message": f"unknown food {replace_with!r}"}]
        )
    for source in sources:
        if not any(count_uses(connection, [source["id"]]).values()):
            continue
        # The same choice as when logging a food: BLS 4.0 first, otherwise the newest.
        new = connection.execute(
            """SELECT id FROM catalog.food_sources
               WHERE food_id = %s AND reference_unit = %s
               ORDER BY (source_name = 'BLS 4.0') DESC, id DESC LIMIT 1""",
            (target["id"], source["reference_unit"]),
        ).fetchone()
        if new is None:
            unit = source["reference_unit"]
            raise RegistrationError(
                [
                    {
                        "field": "replace_with",
                        "message": f"{replace_with} has no values per {unit}, "
                        f"but the amounts to move are in {unit}",
                    }
                ]
            )
        for table, _owner in USERS.values():
            connection.execute(
                f"UPDATE {table} SET source_id = %s WHERE source_id = %s",
                (new["id"], source["id"]),
            )


def delete_food(
    connection: Connection, slug: str, replace_with: str | None = None, dry_run: bool = False
) -> dict:
    """Delete a registered product, moving its uses to `replace_with` first.

    A dry run reports the uses and whether the deletion would go through, and
    changes nothing. A real run on a product in use without a replacement raises
    FoodInUse.
    """
    with connection.transaction() as transaction:
        food = connection.execute(
            "SELECT id, kind FROM catalog.foods WHERE slug = %s FOR UPDATE", (slug,)
        ).fetchone()
        if food is None:
            raise FoodNotFound(f"no food {slug}")
        if food["kind"] != "branded":
            raise RegistrationError(
                [
                    {
                        "field": "slug",
                        "message": "only registered products can be deleted; "
                        "BLS and USDA foods belong to their importers",
                    }
                ]
            )
        if replace_with == slug:
            raise RegistrationError(
                [{"field": "replace_with", "message": "a product cannot replace itself"}]
            )
        sources = connection.execute(
            "SELECT id, reference_unit FROM catalog.food_sources WHERE food_id = %s",
            (food["id"],),
        ).fetchall()
        uses = count_uses(connection, [source["id"] for source in sources])
        blocked = any(uses.values()) and replace_with is None
        if blocked and not dry_run:
            raise FoodInUse(uses)
        if replace_with is not None:
            move_uses(connection, sources, replace_with)
        if not blocked:
            # Sources, portions and nutrients go with it; its variants lose the link.
            connection.execute("DELETE FROM catalog.foods WHERE id = %s", (food["id"],))
            connection.execute("SELECT catalog.refresh_search()")
        result = {"slug": slug, "replaced_with": replace_with, "uses": uses, "blocked": blocked}
        if dry_run:
            raise psycopg.Rollback(transaction)
    return result
