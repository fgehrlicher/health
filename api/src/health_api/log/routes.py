"""Consumption log endpoints: meals and day totals."""

from datetime import date

import psycopg
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import JSONResponse

from health_api.db import connect
from health_api.log.meals import (
    LogError,
    MealInput,
    MealUpdate,
    day_summary,
    get_meal,
    insert_items,
    local_time,
    resolve_items,
)

router = APIRouter(prefix="/api/log", tags=["log"])


def issues_response(error: LogError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": error.issues})


@router.post("/meals", status_code=201)
def create_meal(meal: MealInput, response: Response, dry_run: bool = False):
    """Log a meal: catalog foods and amounts. Nutrition is calculated, never sent.

    A meal without items is logged with unknown nutrition. `dry_run=true`
    returns the meal as it would be stored, without storing it.
    """
    try:
        eaten_at = local_time(meal.eaten_at)
        with connect() as connection, connection.transaction() as transaction:
            rows = resolve_items(connection, meal.items)
            meal_id = connection.execute(
                "INSERT INTO log.meals (eaten_at, kind) VALUES (%s, %s) RETURNING id",
                (eaten_at, meal.kind),
            ).fetchone()["id"]
            insert_items(connection, meal_id, rows)
            result = get_meal(connection, meal_id)
            if dry_run:
                raise psycopg.Rollback(transaction)
    except LogError as error:
        return issues_response(error)
    if dry_run:
        response.status_code = 200
    return result


@router.get("/meals/{meal_id}")
def read_meal(meal_id: int):
    with connect() as connection:
        meal = get_meal(connection, meal_id)
    if meal is None:
        raise HTTPException(status_code=404, detail="No such meal")
    return meal


@router.patch("/meals/{meal_id}")
def update_meal(meal_id: int, update: MealUpdate):
    """Change time, kind, or items; `items` replaces all of the meal's items.

    Send `"kind": null` to clear the kind. Filling in an unknown meal is an
    update with items.
    """
    given = update.model_fields_set
    try:
        eaten_at = local_time(update.eaten_at) if "eaten_at" in given else None
        with connect() as connection, connection.transaction():
            found = connection.execute(
                "SELECT 1 FROM log.meals WHERE id = %s FOR UPDATE", (meal_id,)
            ).fetchone()
            if found is None:
                raise HTTPException(status_code=404, detail="No such meal")
            if "eaten_at" in given and update.eaten_at is None:
                raise LogError([{"field": "eaten_at", "message": "cannot be cleared"}])
            if update.items is not None:
                rows = resolve_items(connection, update.items)
                connection.execute("DELETE FROM log.meal_items WHERE meal_id = %s", (meal_id,))
                insert_items(connection, meal_id, rows)
            connection.execute(
                """UPDATE log.meals SET updated_at = now(),
                       eaten_at = CASE WHEN %(set_time)s THEN %(eaten_at)s ELSE eaten_at END,
                       kind = CASE WHEN %(set_kind)s THEN %(kind)s ELSE kind END
                   WHERE id = %(id)s""",
                {
                    "id": meal_id,
                    "set_time": "eaten_at" in given,
                    "eaten_at": eaten_at,
                    "set_kind": "kind" in given,
                    "kind": update.kind,
                },
            )
            return get_meal(connection, meal_id)
    except LogError as error:
        return issues_response(error)


@router.delete("/meals/{meal_id}", status_code=204)
def delete_meal(meal_id: int):
    with connect() as connection:
        deleted = connection.execute(
            "DELETE FROM log.meals WHERE id = %s RETURNING id", (meal_id,)
        ).fetchone()
    if deleted is None:
        raise HTTPException(status_code=404, detail="No such meal")
    return Response(status_code=204)


@router.get("/days/{day}")
def read_day(day: date):
    """A local day's meals and totals, keeping measured, estimated, and unknown apart."""
    with connect() as connection:
        return day_summary(connection, day)
