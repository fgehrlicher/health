"""Command-line entry point for the BLS 4.0 importer."""

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import psycopg

from bls4_importer.database import write_foods
from bls4_importer.source import SOURCE_NAME, WORKBOOK_SHA256, parse_codes, read_workbook

PROJECT_DIR = Path(__file__).resolve().parents[2]
REPOSITORY_DIR = Path(__file__).resolve().parents[4]
DEFAULT_WORKBOOK = REPOSITORY_DIR / "data/bls4/BLS_4_0_2025_DE/BLS_4_0_Daten_2025_DE.xlsx"
DEFAULT_CODES = PROJECT_DIR / "selected.codes"
DEFAULT_DATABASE_URL = "postgres://health:health@127.0.0.1:5432/health"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description="Import selected BLS 4.0 ingredients")
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK)
    parser.add_argument("--codes", type=Path, default=DEFAULT_CODES)
    parser.add_argument(
        "--dry-run", action="store_true", help="validate without connecting to PostgreSQL"
    )
    options = parser.parse_args(argv)

    workbook_hash = sha256_file(options.workbook)
    if workbook_hash != WORKBOOK_SHA256:
        raise ValueError(
            f"unexpected BLS workbook checksum: {workbook_hash}; expected {WORKBOOK_SHA256}"
        )
    code_bytes = options.codes.read_bytes()
    codes = parse_codes(code_bytes.decode("utf-8"))
    foods, issues, corrected = read_workbook(options.workbook, codes)
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
        "codes_sha256": hashlib.sha256(code_bytes).hexdigest(),
        "run_unix_seconds": int(time.time()),
        "dry_run": options.dry_run,
        "selected": len(foods),
        "created": counts[0],
        "updated": counts[1],
        "skipped": counts[2],
        "energy_corrected": corrected,
        "nonnumeric_values": issues,
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
