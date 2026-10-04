"""Recipe and cooking log endpoints."""

from datetime import date
from typing import Annotated

import psycopg
from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import JSONResponse

from health_api.db import connect
from health_api.ingredients import InputError
from health_api.recipes.cooks import (
    CookInput,
    CookInUse,
    CookNotFound,
    CookUpdate,
    add_cook,
    delete_cook,
    get_cook,
    list_cooks,
    update_cook,
)
from health_api.recipes.models import Cook, CookSummary, Recipe, RecipeSummary, Version
from health_api.recipes.recipes import (
    RecipeInput,
    RecipeInUse,
    RecipeNotFound,
    RecipeUpdate,
    VersionInput,
    VersionUpdate,
    add_version,
    create_recipe,
    delete_recipe,
    get_recipe,
    list_recipes,
    update_recipe,
    update_version,
)

router = APIRouter(prefix="/api", tags=["recipes"])

INVALID = {422: {"description": "Invalid input; nothing written"}}


def issues_response(error: InputError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": error.issues})


@router.get("/recipes", response_model=list[RecipeSummary])
def read_recipes(q: Annotated[str | None, Query(max_length=200)] = None):
    """Recipes, most recently cooked or created first; `q` matches name words."""
    with connect() as connection:
        return list_recipes(connection, q)


@router.post("/recipes", status_code=201, response_model=Recipe, responses=INVALID)
def post_recipe(recipe: RecipeInput, response: Response, dry_run: bool = False):
    """Create a recipe with version 1, from ingredients, a cook, or another recipe's version.

    `forked_from` develops it from another recipe's version; `from_cook` saves
    what went into a cook. `dry_run=true` returns it without storing.
    """
    try:
        with connect() as connection, connection.transaction() as transaction:
            slug = create_recipe(connection, recipe)
            result = get_recipe(connection, slug)
            if dry_run:
                raise psycopg.Rollback(transaction)
    except InputError as error:
        return issues_response(error)
    if dry_run:
        response.status_code = 200
    return result


@router.get("/recipes/{slug}", response_model=Recipe)
def read_recipe(slug: str):
    """A recipe with every version (newest first), forks, and its cooks."""
    with connect() as connection:
        recipe = get_recipe(connection, slug)
    if recipe is None:
        raise HTTPException(status_code=404, detail="No such recipe")
    return recipe


@router.patch("/recipes/{slug}", response_model=Recipe, responses=INVALID)
def patch_recipe(slug: str, update: RecipeUpdate):
    """Rename a recipe or change its note."""
    try:
        with connect() as connection, connection.transaction():
            update_recipe(connection, slug, update)
            return get_recipe(connection, slug)
    except InputError as error:
        return issues_response(error)
    except RecipeNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.delete("/recipes/{slug}", status_code=204)
def remove_recipe(slug: str):
    """Delete a recipe that was never cooked or forked."""
    try:
        with connect() as connection:
            delete_recipe(connection, slug)
    except RecipeNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RecipeInUse as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return Response(status_code=204)


@router.post("/recipes/{slug}/versions", status_code=201, response_model=Version, responses=INVALID)
def post_version(slug: str, version: VersionInput, response: Response, dry_run: bool = False):
    """Add a version: changed ingredients or portions, with a note on what and why.

    Missing fields come from `from_cook` (ingredients, portions) and the parent
    version (ingredients, portions, steps). The parent defaults to the cook's
    version, else the latest.
    """
    try:
        with connect() as connection, connection.transaction() as transaction:
            number = add_version(connection, slug, version)
            recipe = get_recipe(connection, slug)
            if dry_run:
                raise psycopg.Rollback(transaction)
    except InputError as error:
        return issues_response(error)
    except RecipeNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    if dry_run:
        response.status_code = 200
    return next(v for v in recipe["versions"] if v["number"] == number)


@router.patch("/recipes/{slug}/versions/{number}", response_model=Version)
def patch_version(slug: str, number: int, update: VersionUpdate):
    """Change a version's note or steps; ingredients and portions are fixed."""
    try:
        with connect() as connection, connection.transaction():
            update_version(connection, slug, number, update)
            recipe = get_recipe(connection, slug)
    except RecipeNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return next(v for v in recipe["versions"] if v["number"] == number)


@router.get("/cooks", response_model=list[CookSummary])
def read_cooks(
    recipe: Annotated[str | None, Query(max_length=200)] = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    since: date | None = None,
    until: date | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    """The cooking log, newest first: by recipe slug, name words, or local days."""
    with connect() as connection:
        return list_cooks(connection, recipe, q, since, until, limit)


@router.post("/cooks", status_code=201, response_model=Cook, responses=INVALID)
def post_cook(cook: CookInput, response: Response, dry_run: bool = False):
    """Log a cook: a recipe version and what actually went in, split into portions.

    Without `items`, the version's ingredients are used. Without a recipe, the
    cook is improvised and needs `name`, `portions`, and `items`.
    """
    try:
        with connect() as connection, connection.transaction() as transaction:
            result = get_cook(connection, add_cook(connection, cook))
            if dry_run:
                raise psycopg.Rollback(transaction)
    except InputError as error:
        return issues_response(error)
    if dry_run:
        response.status_code = 200
    return result


@router.get("/cooks/{cook_id}", response_model=Cook)
def read_cook(cook_id: int):
    """A cook with its ingredients, nutrition per portion, and changes to its version."""
    with connect() as connection:
        cook = get_cook(connection, cook_id)
    if cook is None:
        raise HTTPException(status_code=404, detail="No such cook")
    return cook


@router.patch("/cooks/{cook_id}", response_model=Cook, responses=INVALID)
def patch_cook(cook_id: int, update: CookUpdate):
    """Correct a cook; meals eaten from it follow. `items` replaces all ingredients."""
    try:
        with connect() as connection, connection.transaction():
            update_cook(connection, cook_id, update)
            return get_cook(connection, cook_id)
    except InputError as error:
        return issues_response(error)
    except CookNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.delete("/cooks/{cook_id}", status_code=204)
def remove_cook(cook_id: int):
    """Delete a cook nothing was logged from."""
    try:
        with connect() as connection, connection.transaction():
            delete_cook(connection, cook_id)
    except CookNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except CookInUse as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return Response(status_code=204)
