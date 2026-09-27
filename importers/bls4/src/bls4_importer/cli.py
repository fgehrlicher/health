"""Command-line entry point for the BLS 4.0 importer."""

import argparse
import hashlib
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

import psycopg

from bls4_importer.database import write_foods
from bls4_importer.download import ensure_workbook, sha256_file
from bls4_importer.source import SOURCE_NAME, WORKBOOK_SHA256, parse_codes, read_workbook

REPOSITORY_DIR = Path(__file__).resolve().parents[4]
DATA_DIR = REPOSITORY_DIR / "data/bls4"
DEFAULT_PACKAGE = DATA_DIR / "BLS_4_0_2025_DE.zip"
DEFAULT_WORKBOOK = DATA_DIR / "BLS_4_0_2025_DE/BLS_4_0_Daten_2025_DE.xlsx"
DEFAULT_DATABASE_URL = "postgres://health:health@127.0.0.1:5432/health"


def run(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description="Import the pinned BLS 4.0 workbook")
    parser.add_argument(
        "--workbook",
        type=Path,
        help="local workbook; default downloads the official package if missing",
    )
    parser.add_argument(
        "--codes", type=Path, help="optional subset of BLS codes; default is all foods"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="validate without connecting to PostgreSQL"
    )
    options = parser.parse_args(argv)
    if options.workbook is None:
        options.workbook = DEFAULT_WORKBOOK
        ensure_workbook(DEFAULT_WORKBOOK, DEFAULT_PACKAGE)

    workbook_hash = sha256_file(options.workbook)
    if workbook_hash != WORKBOOK_SHA256:
        raise ValueError(
            f"unexpected BLS workbook checksum: {workbook_hash}; expected {WORKBOOK_SHA256}"
        )
    code_bytes = options.codes.read_bytes() if options.codes else None
    codes = parse_codes(code_bytes.decode("utf-8")) if code_bytes else None
    foods, issues, corrected, energy_unavailable = read_workbook(options.workbook, codes)
    markers = Counter((issue["field"], issue["marker"]) for issue in issues)
    counts = (
        (0, 0, 0)
        if options.dry_run
        else write_foods(os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL), foods)
    )
    return {
        "source": SOURCE_NAME,
        "publisher": "Max Rubner-Institut",
        "citation": "Max Rubner-Institut (2025): Bundeslebensmittelschlüssel (BLS), Version 4.0 — Deutsche Nährstoffdatenbank. Karlsruhe. DOI: 10.25826/Data20251217-134202-0",
        "license": "CC BY 4.0",
        "download_url": "https://blsdb.de/download",
        "workbook_sha256": workbook_hash,
        "selection": "codes" if code_bytes else "all",
        "codes_sha256": hashlib.sha256(code_bytes).hexdigest() if code_bytes else None,
        "run_unix_seconds": int(time.time()),
        "dry_run": options.dry_run,
        "selected": len(foods),
        "created": counts[0],
        "updated": counts[1],
        "skipped": counts[2],
        "energy_corrected": corrected,
        "energy_unavailable": energy_unavailable,
        "nonnumeric_values": [
            {"field": field, "marker": marker, "count": count}
            for (field, marker), count in sorted(markers.items())
        ],
    }


def main() -> int:
    try:
        print(json.dumps(run(), indent=2, ensure_ascii=False))
    except (OSError, TypeError, ValueError, RuntimeError, psycopg.Error) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
