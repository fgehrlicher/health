"""Command-line entry point for the USDA FoodData Central importer.

Reads the pinned SR Legacy and Foundation archives from a local folder. A dry
run is the default: it validates everything and prints the report. --commit
stores the foods.
"""

import argparse
import csv
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

import psycopg

from usda_importer.bundle import PINNED, read_dataset
from usda_importer.database import slug_for, write_foods
from usda_importer.source import LABEL_COLUMNS, OTHER, SOURCE_NAME, Food

REPOSITORY_DIR = Path(__file__).resolve().parents[4]
DEFAULT_DATA_DIR = REPOSITORY_DIR / "data/usda/raw"
NAMES_PATH = Path(__file__).resolve().parents[2] / "names-de.tsv"
DEFAULT_DATABASE_URL = "postgres://health:health@127.0.0.1:5432/health"


def load_german_names(path: Path) -> dict[int, str]:
    """Curated German aliases, by FDC ID. Only the listed foods get one."""
    names: dict[int, str] = {}
    with path.open(encoding="utf-8") as handle:
        for row in csv.reader(
            (line for line in handle if not line.startswith("#")), delimiter="\t"
        ):
            if row:
                names[int(row[0])] = row[1].strip()
    return names


def food_report(food: Food) -> dict:
    return {
        "fdc_id": food.fdc_id,
        "slug": slug_for(food.fdc_id),
        "name": food.description,
        "name_de": food.german_name,
        "data_type": food.data_type,
        "preparation_state": food.preparation_state,
        "derived": food.derived,
        "notes": food.notes,
        "portions": len(food.portions),
        "nutrition": {
            column: None if food.nutrients[column] is None else str(food.nutrients[column])
            for column in LABEL_COLUMNS
        },
    }


def run(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(
        description="Import the pinned USDA SR Legacy and Foundation foods"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="folder with the downloaded zip archives (default: data/usda/raw)",
    )
    parser.add_argument(
        "--commit", action="store_true", help="store the foods; without this, only a dry run"
    )
    parser.add_argument(
        "--report", type=Path, help="write the full report (every food, rejection and drop) here"
    )
    options = parser.parse_args(argv)

    names = load_german_names(NAMES_PATH)
    datasets = []
    foods: list[Food] = []
    for file_name in PINNED:
        path = options.data_dir / file_name
        if not path.exists():
            raise ValueError(f"missing archive: {path}")
        report = read_dataset(path)
        datasets.append(report)
        foods.extend(food for food in report.foods)
    for food in foods:
        food.german_name = names.get(food.fdc_id)

    counts = (
        (0, 0)
        if not options.commit
        else write_foods(os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL), foods)
    )
    derived = {}
    for food in foods:
        for column in food.derived:
            derived[column] = derived.get(column, 0) + 1
    summary = {
        "source": SOURCE_NAME,
        "citation": "U.S. Department of Agriculture, Agricultural Research Service. FoodData Central, https://fdc.nal.usda.gov",
        "license": "public domain (U.S. government data)",
        "datasets": [
            {
                "dataset": report.dataset,
                "archive_sha256": report.sha256,
                "foods": len(report.foods),
                "rejected": len(report.rejected),
                "excluded_american_categories": report.excluded_american,
                "duplicates_dropped": len(report.duplicates_dropped),
            }
            for report in datasets
        ],
        "dry_run": not options.commit,
        "selected": len(foods),
        "created": counts[0],
        "updated": counts[1],
        "derived_values": derived,
        "notes": dict(Counter(note.split(":", 1)[0] for food in foods for note in food.notes)),
        "other_nutrients_mapped": len(OTHER),
        "run_unix_seconds": int(time.time()),
    }
    if options.report:
        full = {
            **summary,
            "rejected": [item for report in datasets for item in report.rejected],
            "duplicates_dropped": [
                item for report in datasets for item in report.duplicates_dropped
            ],
            "foods": [food_report(food) for food in foods],
        }
        options.report.write_text(json.dumps(full, ensure_ascii=False, indent=1), encoding="utf-8")
        summary["report_file"] = str(options.report)
    summary["rejected_count"] = sum(len(report.rejected) for report in datasets)
    return summary


def main() -> int:
    try:
        print(json.dumps(run(), indent=2, ensure_ascii=False))
    except (OSError, TypeError, ValueError, RuntimeError, psycopg.Error) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
