"""Command-line entry point for the USDA post-processing.

    usda-postprocess export --out data/usda/batches   # the foods, in batches for the LLM
    usda-postprocess apply                            # check the decisions (dry run)
    usda-postprocess apply --commit                   # write them to the database

`export` only reads. `apply` checks every decision first and writes nothing
unless every USDA food has one and --commit is given.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import psycopg

from usda_importer.postprocess import BATCH_SIZE, DECISIONS_DIR, GROUPS_PATH, apply, export_batches

REPOSITORY_DIR = Path(__file__).resolve().parents[4]
DEFAULT_DATA_DIR = REPOSITORY_DIR / "data/usda/raw"
DEFAULT_BATCHES = REPOSITORY_DIR / "data/usda/batches"
DEFAULT_DATABASE_URL = "postgres://health:health@127.0.0.1:5432/health"


def run(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(
        description="Give the imported USDA foods a food group and a German name"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    export = commands.add_parser("export", help="write the USDA foods in batches for the LLM")
    export.add_argument("--out", type=Path, default=DEFAULT_BATCHES)
    export.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    export.add_argument("--batch-size", type=int, default=BATCH_SIZE)

    decide = commands.add_parser("apply", help="check the decisions and write them")
    decide.add_argument("--decisions", type=Path, default=DECISIONS_DIR)
    decide.add_argument("--groups", type=Path, default=GROUPS_PATH)
    decide.add_argument(
        "--commit", action="store_true", help="write to the database; otherwise a dry run"
    )

    options = parser.parse_args(argv)
    database_url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    if options.command == "export":
        count = export_batches(database_url, options.data_dir, options.out, options.batch_size)
        return {"exported": count, "batches_in": str(options.out)}
    return apply(database_url, options.decisions, options.groups, options.commit)


def main() -> int:
    try:
        print(json.dumps(run(), indent=2, ensure_ascii=False))
    except (OSError, TypeError, ValueError, RuntimeError, psycopg.Error) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
