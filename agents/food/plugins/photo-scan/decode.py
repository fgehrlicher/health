"""Decodes the barcodes and QR codes in one photo and prints them as JSON.

The photo-scan plugin runs this with a Python that has zxing-cpp and Pillow,
so the Hermes runtime itself needs no extra packages.

Usage: python decode.py <image path>
"""

import json
import re
import sys

import zxingcpp
from PIL import Image

# GS1 Digital Link QR codes carry the GTIN as application identifier 01, in the
# URL path ("/01/<gtin>") or as a query parameter ("?01=<gtin>").
GTIN_IN_URL = re.compile(r"(?:/01/|[?&]01=)(\d{14})(?!\d)")


def ean_checksum_ok(digits: str) -> bool | None:
    """True if an EAN-8 or EAN-13 check digit is right; None for anything else."""
    if not digits.isdigit() or len(digits) not in (8, 13):
        return None
    body, check = digits[:-1], int(digits[-1])
    total = sum(int(d) * (3 if (len(body) - i) % 2 else 1) for i, d in enumerate(body))
    return (10 - total % 10) % 10 == check


def main(path: str) -> None:
    image = Image.open(path).convert("RGB")
    codes = []
    for found in zxingcpp.read_barcodes(image):
        fmt = str(found.format)
        entry = {"format": fmt, "text": found.text, "gtin": None, "checksum_ok": None}
        if fmt.startswith("EAN"):
            entry["checksum_ok"] = ean_checksum_ok(found.text)
        elif match := GTIN_IN_URL.search(found.text):
            gtin14 = match.group(1)
            # A GTIN-14 with a leading zero is an EAN-13 with the zero in front.
            entry["gtin"] = gtin14.removeprefix("0")
            entry["checksum_ok"] = ean_checksum_ok(entry["gtin"])
        codes.append(entry)
    print(json.dumps({"codes": codes}))


if __name__ == "__main__":
    main(sys.argv[1])
