import asyncio
import io
import os

import httpx
import psycopg
import pytest
import zxingcpp
from health_api.app import app
from health_api.scan import decode, product_number
from PIL import Image
from test_registration import QUARK, request_json

REGISTERED = "4000000000051"  # valid check digits, not real products
UNKNOWN = "4000000000068"
IN_STORE = "2012345678903"  # prefix 2: a shop's own code for weighed goods
WRONG_CHECK = "4000000000052"


def png(text: str, fmt: zxingcpp.BarcodeFormat) -> bytes:
    """A generated code on a white margin, as a PNG."""
    code = Image.fromarray(zxingcpp.create_barcode(text, fmt).to_image(scale=4))
    canvas = Image.new("L", (code.width + 80, code.height + 80), 255)
    canvas.paste(code, (40, 40))
    out = io.BytesIO()
    canvas.save(out, "PNG")
    return out.getvalue()


def blank_png() -> bytes:
    out = io.BytesIO()
    Image.new("L", (200, 200), 255).save(out, "PNG")
    return out.getvalue()


def post_image(data: bytes, content_type: str = "image/png") -> httpx.Response:
    async def send():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/api/scan", content=data, headers={"Content-Type": content_type}
            )

    return asyncio.run(send())


@pytest.mark.parametrize(
    ("fmt", "text", "expected"),
    [
        ("EAN-13", REGISTERED, REGISTERED),
        ("EAN-8", "40084015", "40084015"),
        ("QR Code", f"https://id.gs1.org/01/0{REGISTERED}", REGISTERED),
        ("QR Code", f"https://www.lidl.de/fischtracking/s4306?01=0{REGISTERED}", REGISTERED),
        ("QR Code", "https://www.oetker.de/rezepte", None),
        ("Code 128", "LOT-4711", None),
    ],
)
def test_product_numbers_come_from_linear_codes_and_gs1_links(fmt, text, expected):
    assert product_number(fmt, text) == expected


def test_decode_reads_generated_codes_and_refuses_non_images():
    assert decode(png(REGISTERED, zxingcpp.BarcodeFormat.EAN13)) == [("EAN-13", REGISTERED)]
    assert decode(blank_png()) == []
    with pytest.raises(ValueError):
        decode(b"not an image")


def test_scan_refuses_other_content_and_unreadable_images():
    assert post_image(blank_png(), "text/plain").status_code == 415
    assert post_image(b"\x89PNG broken", "image/png").status_code == 422


def test_scan_reports_what_the_catalog_knows_against_postgres(monkeypatch):
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("set TEST_DATABASE_URL for PostgreSQL integration coverage")
    monkeypatch.setenv("DATABASE_URL", database_url)
    product = QUARK | {"name": "Scan test quark", "brand": None, "barcode": REGISTERED}
    try:
        created = request_json("POST", "/api/foods", product)
        assert created.status_code == 201, created.text
        slug = created.json()["food"]["slug"]

        def only_code(data: bytes) -> dict:
            response = post_image(data)
            assert response.status_code == 200, response.text
            [code] = response.json()["codes"]
            return code

        known = only_code(png(REGISTERED, zxingcpp.BarcodeFormat.EAN13))
        assert known["status"] == "known" and known["product_number"] == REGISTERED
        assert known["food"] == {"slug": slug, "name": "Scan test quark"}

        link = f"https://id.gs1.org/01/0{REGISTERED}"
        from_qr = only_code(png(link, zxingcpp.BarcodeFormat.QRCode))
        assert from_qr["format"] == "QR Code" and from_qr["text"] == link
        assert from_qr["status"] == "known" and from_qr["food"]["slug"] == slug

        unknown = only_code(png(UNKNOWN, zxingcpp.BarcodeFormat.EAN13))
        assert unknown["status"] == "not_in_catalog" and unknown["food"] is None

        in_store = only_code(png(IN_STORE, zxingcpp.BarcodeFormat.EAN13))
        assert in_store["status"] == "in_store_code"

        # A barcode reader rejects a wrong check digit itself; a QR link can still carry one.
        misread = only_code(
            png(f"https://id.gs1.org/01/0{WRONG_CHECK}", zxingcpp.BarcodeFormat.QRCode)
        )
        assert misread["status"] == "misread" and misread["product_number"] == WRONG_CHECK

        plain = only_code(png("https://www.oetker.de/rezepte", zxingcpp.BarcodeFormat.QRCode))
        assert plain["status"] == "no_product_number" and plain["product_number"] is None

        empty = post_image(blank_png())
        assert empty.status_code == 200 and empty.json() == {"codes": []}
    finally:
        with psycopg.connect(database_url) as connection:
            connection.execute("DELETE FROM catalog.foods WHERE barcode = %s", (REGISTERED,))
            connection.execute("SELECT catalog.refresh_search()")
