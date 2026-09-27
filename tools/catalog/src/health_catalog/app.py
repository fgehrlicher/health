"""The read-only catalog HTTP API and same-origin frontend."""

import os
from decimal import Decimal
from pathlib import Path
from typing import Annotated

import psycopg
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from psycopg.rows import dict_row

from health_catalog.models import (
    CatalogFacets,
    FoodDetail,
    FoodInput,
    FoodPage,
    FoodRegistration,
    SourceTextUpdate,
)
from health_catalog.registration import (
    BarcodeConflict,
    RegistrationError,
    SourceNotFound,
    barcode_problem,
    check_food,
    register_food,
    update_source_text,
)
from health_catalog.repository import FoodFilters, Sort, get_facets, get_food, list_foods

STATIC_DIR = Path(__file__).parent / "static"
DEFAULT_DATABASE_URL = "postgres://health:health@127.0.0.1:5432/health"

app = FastAPI(title="Health Food Catalog", version="0.1.0")
app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")


@app.exception_handler(psycopg.OperationalError)
def database_unavailable(_request, _error):
    return JSONResponse(status_code=503, content={"detail": "Food database is unavailable"})


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/foods", response_model=FoodPage)
def foods(
    q: Annotated[str | None, Query(max_length=100)] = None,
    kind: Annotated[str | None, Query(max_length=60)] = None,
    group: Annotated[str | None, Query(pattern="^[BCDEFGHKMNPQRSTUVWXY]$")] = None,
    source_name: Annotated[str | None, Query(max_length=100)] = None,
    preparation_state: Annotated[str | None, Query(max_length=60)] = None,
    min_protein: Annotated[Decimal | None, Query(ge=0)] = None,
    min_protein_density: Annotated[Decimal | None, Query(ge=0)] = None,
    min_fiber: Annotated[Decimal | None, Query(ge=0)] = None,
    max_energy: Annotated[Decimal | None, Query(ge=0)] = None,
    sort: Sort = "relevance",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    filters = FoodFilters(
        q=q,
        kind=kind,
        group=group,
        source_name=source_name,
        preparation_state=preparation_state,
        min_protein=min_protein,
        min_protein_density=min_protein_density,
        min_fiber=min_fiber,
        max_energy=max_energy,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    with psycopg.connect(database_url(), row_factory=dict_row) as connection:
        return list_foods(connection, filters)


@app.get("/api/foods/facets", response_model=CatalogFacets)
def facets():
    with psycopg.connect(database_url(), row_factory=dict_row) as connection:
        return get_facets(connection)


@app.get("/api/foods/barcode/{barcode}", response_model=FoodDetail)
def food_by_barcode(barcode: str):
    """Exact lookup of a scanned or photographed EAN/UPC barcode."""
    if problem := barcode_problem(barcode):
        raise HTTPException(status_code=422, detail=f"barcode {problem}")
    with psycopg.connect(database_url(), row_factory=dict_row) as connection:
        row = connection.execute("SELECT slug FROM foods WHERE barcode = %s", (barcode,)).fetchone()
        food = get_food(connection, row["slug"]) if row else None
    if food is None:
        raise HTTPException(status_code=404, detail="No food with this barcode")
    return food


@app.post(
    "/api/foods",
    response_model=FoodRegistration,
    status_code=201,
    responses={
        409: {"description": "Barcode already registered; `slug` names the food"},
        422: {"description": "Invalid or self-contradicting values; nothing written"},
    },
)
def create_food(food: FoodInput, response: Response, dry_run: bool = False):
    """Register a branded food with its label nutrition and portions.

    Validates the barcode check digit, "davon" rows, kJ against kcal, and kcal
    against the macros. Use `dry_run=true` first; warnings do not block writing.
    """
    errors, _warnings = check_food(food)
    if errors:
        return JSONResponse(status_code=422, content={"detail": errors})
    try:
        with psycopg.connect(database_url(), row_factory=dict_row) as connection:
            result = register_food(connection, food, dry_run)
    except RegistrationError as error:
        return JSONResponse(status_code=422, content={"detail": error.issues})
    except BarcodeConflict as conflict:
        return JSONResponse(
            status_code=409, content={"detail": str(conflict), "slug": conflict.slug}
        )
    if dry_run:
        response.status_code = 200
    return result


@app.patch(
    "/api/foods/{slug}/sources/{source_id}",
    response_model=FoodDetail,
    responses={404: {"description": "No such food or source"}, 422: {"description": "Invalid"}},
)
def patch_source_text(slug: str, source_id: int, update: SourceTextUpdate):
    """Add a label's legal name or ingredients read from a later photo.

    Only text fields; a label with different nutrition is a new source. BLS
    sources cannot be edited.
    """
    try:
        with psycopg.connect(database_url(), row_factory=dict_row) as connection:
            return update_source_text(connection, slug, source_id, update)
    except RegistrationError as error:
        return JSONResponse(status_code=422, content={"detail": error.issues})
    except SourceNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/foods/{slug}", response_model=FoodDetail)
def food_detail(slug: str):
    with psycopg.connect(database_url(), row_factory=dict_row) as connection:
        food = get_food(connection, slug)
    if food is None:
        raise HTTPException(status_code=404, detail="Food not found")
    return food
