"""Barcodes and QR codes in a photo, decoded by code rather than read by a model.

`POST /api/scan` takes the image bytes as the request body (JPEG, PNG or WebP)
and returns every code found, with the product number it carries and what the
catalog knows about it. The food agent's photo-scan plugin calls it for each
photo before the agent sees the message, and `health scan --image` calls it too.
"""

import io
import re
from typing import Literal

import zxingcpp
from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from PIL import Image, ImageOps, UnidentifiedImageError
from psycopg import Connection
from pydantic import BaseModel

from health_api.catalog.registration import barcode_issue
from health_api.db import connect

router = APIRouter(prefix="/api", tags=["scan"])

MAX_BYTES = 10 * 1024 * 1024
IMAGE_TYPES = ("image/jpeg", "image/png", "image/webp")
# Linear codes that carry a product number (GTIN) directly.
PRODUCT_FORMATS = {"EAN-13", "EAN-8", "UPC-A"}
# GS1 Digital Link QR codes carry the GTIN as application identifier 01, in the
# URL path ("/01/<gtin>") or as a query parameter ("?01=<gtin>").
GTIN_IN_URL = re.compile(r"(?:/01/|[?&]01=)(\d{14})(?!\d)")

ScanStatus = Literal["known", "not_in_catalog", "in_store_code", "misread", "no_product_number"]


class ScannedFood(BaseModel):
    slug: str
    name: str


class ScannedCode(BaseModel):
    # As the decoder names it, e.g. "EAN-13", "EAN-8", "QR Code".
    format: str
    # The code's raw content: the digits, or the QR code's text or URL.
    text: str
    # The EAN/UPC, or the GTIN a GS1 QR code carries; null if there is none.
    product_number: str | None
    # known: in the catalog (see food). not_in_catalog: a valid product number the
    # catalog lacks. in_store_code: a shop's own code (weighed goods), not a product.
    # misread: the check digit is wrong. no_product_number: e.g. a plain QR link.
    status: ScanStatus
    food: ScannedFood | None = None


class ScanResult(BaseModel):
    codes: list[ScannedCode]


def product_number(fmt: str, text: str) -> str | None:
    """The product number a code carries, or None."""
    if fmt in PRODUCT_FORMATS:
        return text
    if match := GTIN_IN_URL.search(text):
        # A GTIN-14 with a leading zero is the EAN-13 behind it.
        return match.group(1).removeprefix("0")
    return None


def decode(data: bytes) -> list[tuple[str, str]]:
    """Each distinct (format, text) the decoder finds in the image, in reading order."""
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError) as error:
        raise ValueError("not a readable image") from error
    image = ImageOps.exif_transpose(image).convert("RGB")
    codes: list[tuple[str, str]] = []
    for found in zxingcpp.read_barcodes(image):
        key = (str(found.format), found.text)
        if key not in codes:
            codes.append(key)
    return codes


def scanned(connection: Connection, fmt: str, text: str) -> dict:
    """One decoded code with its product number and the catalog's answer."""
    number = product_number(fmt, text)
    code = {"format": fmt, "text": text, "product_number": number, "food": None}
    if number is None:
        return code | {"status": "no_product_number"}
    issue = barcode_issue(number)
    if issue == "check_digit":
        return code | {"status": "misread"}
    if issue == "store_internal":
        return code | {"status": "in_store_code"}
    if issue == "format":
        # E.g. a GTIN-14 for a case of products: a number, but not a consumer product's.
        return code | {"status": "no_product_number"}
    row = connection.execute(
        "SELECT slug, name FROM catalog.foods WHERE barcode = %s", (number,)
    ).fetchone()
    if row is None:
        return code | {"status": "not_in_catalog"}
    return code | {"status": "known", "food": {"slug": row["slug"], "name": row["name"]}}


def scan_image(data: bytes) -> dict:
    codes = decode(data)
    with connect() as connection:
        return {"codes": [scanned(connection, fmt, text) for fmt, text in codes]}


@router.post(
    "/scan",
    response_model=ScanResult,
    responses={
        413: {"description": f"Image larger than {MAX_BYTES // (1024 * 1024)} MB"},
        415: {"description": "Not a JPEG, PNG or WebP image"},
        422: {"description": "The body is not a readable image"},
    },
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                kind: {"schema": {"type": "string", "format": "binary"}} for kind in IMAGE_TYPES
            },
        }
    },
)
async def scan(request: Request):
    """Barcodes and QR codes in one photo, with what the catalog knows about each.

    Send the image bytes as the body, with Content-Type image/jpeg, image/png or
    image/webp. A photo without a readable code returns an empty list.
    """
    kind = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if kind not in IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="send a JPEG, PNG or WebP image")
    data = await request.body()
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="the image is larger than 10 MB")
    try:
        # Decoding and the catalog lookups block, so they run off the event loop.
        return await run_in_threadpool(scan_image, data)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
