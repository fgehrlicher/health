"""Catalog endpoints: search, details, barcode lookup, and branded food registration."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import JSONResponse

from health_api.catalog.models import (
    CatalogFacets,
    FoodDetail,
    FoodInput,
    FoodPage,
    FoodRegistration,
    FoodUpdate,
    SourceTextUpdate,
)
from health_api.catalog.registration import (
    BarcodeConflict,
    FoodNotFound,
    RegistrationError,
    SourceNotFound,
    barcode_problem,
    check_food,
    register_food,
    update_food,
    update_source_text,
)
from health_api.catalog.repository import FoodFilters, Sort, get_facets, get_food, list_foods
from health_api.db import connect

router = APIRouter(tags=["catalog"])


@router.get("/api/foods", response_model=FoodPage)
def foods(
    q: Annotated[str | None, Query(max_length=100)] = None,
    kind: Annotated[str | None, Query(max_length=60)] = None,
    group: Annotated[str | None, Query(pattern="^[A-Z]$")] = None,
    brand: Annotated[str | None, Query(max_length=100)] = None,
    source_name: Annotated[str | None, Query(max_length=100)] = None,
    preparation_state: Annotated[str | None, Query(max_length=60)] = None,
    min_protein: Annotated[Decimal | None, Query(ge=0)] = None,
    min_protein_density: Annotated[Decimal | None, Query(ge=0)] = None,
    min_fiber: Annotated[Decimal | None, Query(ge=0)] = None,
    max_energy: Annotated[Decimal | None, Query(ge=0)] = None,
    incomplete: Annotated[
        bool, Query(description="only products whose label still lacks something")
    ] = False,
    sort: Sort = "relevance",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    filters = FoodFilters(
        q=q,
        kind=kind,
        group=group,
        brand=brand,
        source_name=source_name,
        preparation_state=preparation_state,
        min_protein=min_protein,
        min_protein_density=min_protein_density,
        min_fiber=min_fiber,
        max_energy=max_energy,
        incomplete=incomplete,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    with connect() as connection:
        return list_foods(connection, filters)


@router.get("/api/foods/facets", response_model=CatalogFacets)
def facets(
    q: Annotated[str | None, Query(max_length=100)] = None,
    kind: Annotated[str | None, Query(max_length=60)] = None,
    group: Annotated[str | None, Query(pattern="^[A-Z]$")] = None,
    brand: Annotated[str | None, Query(max_length=100)] = None,
    preparation_state: Annotated[str | None, Query(max_length=60)] = None,
    incomplete: bool = False,
):
    """Filter values with counts for the same filters as `GET /api/foods`.

    Each dimension is counted under the other filters, so the counts show what
    selecting a value would yield.
    """
    filters = FoodFilters(
        q=q,
        kind=kind,
        group=group,
        brand=brand,
        preparation_state=preparation_state,
        incomplete=incomplete,
    )
    with connect() as connection:
        return get_facets(connection, filters)


@router.get("/api/foods/barcode/{barcode}", response_model=FoodDetail)
def food_by_barcode(barcode: str):
    """Exact lookup of a scanned or photographed EAN/UPC barcode."""
    if problem := barcode_problem(barcode):
        raise HTTPException(status_code=422, detail=f"barcode {problem}")
    with connect() as connection:
        row = connection.execute(
            "SELECT slug FROM catalog.foods WHERE barcode = %s", (barcode,)
        ).fetchone()
        food = get_food(connection, row["slug"]) if row else None
    if food is None:
        raise HTTPException(status_code=404, detail="No food with this barcode")
    return food


@router.post(
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
        with connect() as connection:
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


@router.patch(
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
        with connect() as connection:
            return update_source_text(connection, slug, source_id, update)
    except RegistrationError as error:
        return JSONResponse(status_code=422, content={"detail": error.issues})
    except SourceNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.patch(
    "/api/foods/{slug}",
    response_model=FoodDetail,
    responses={404: {"description": "No such food"}, 422: {"description": "Invalid"}},
)
def patch_food(slug: str, update: FoodUpdate):
    """Set a food's group or brand, e.g. to categorize a registered product.

    Only the given fields change; `null` clears one.
    """
    try:
        with connect() as connection:
            return update_food(connection, slug, update)
    except RegistrationError as error:
        return JSONResponse(status_code=422, content={"detail": error.issues})
    except FoodNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/api/foods/{slug}", response_model=FoodDetail)
def food_detail(slug: str):
    with connect() as connection:
        food = get_food(connection, slug)
    if food is None:
        raise HTTPException(status_code=404, detail="Food not found")
    return food
