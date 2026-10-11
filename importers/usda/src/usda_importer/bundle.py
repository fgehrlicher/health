"""Reads the USDA FoodData Central zip archives that the importer is pointed at.

Each archive is checked against its pinned SHA-256 before it is read. The tables
are read straight from the zip, so nothing is unpacked to disk.
"""

import csv
import hashlib
import io
import zipfile
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from usda_importer.source import Rejected, build_food

# Pinned archives: file name -> (dataset, SHA-256). The importer refuses other bytes.
PINNED = {
    "FoodData_Central_sr_legacy_food_csv_2018-04.zip": (
        "sr_legacy",
        "b80817294b8850530aaedf2e515c02593b1824f763a0ff356e5c2081643e6fd0",
    ),
    "FoodData_Central_foundation_food_csv_2026-04-30.zip": (
        "foundation",
        "70457ee9d9342f43bda2010318c85f04210c689fdeb9cd2da4c513b0e8dbc655",
    ),
}
DATA_TYPES = {"sr_legacy": "sr_legacy_food", "foundation": "foundation_food"}

# Categories that are American-specific: chains, restaurants, baby foods, traditional foods.
AMERICAN_CATEGORIES = frozenset(
    {"Fast Foods", "Restaurant Foods", "Baby Foods", "American Indian/Alaska Native Foods"}
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Archive:
    """One zip archive, with its tables read by file name."""

    def __init__(self, path: Path):
        self.path = path
        self.zip = zipfile.ZipFile(path)

    def rows(self, table: str):
        member = next(
            (name for name in self.zip.namelist() if name.rsplit("/", 1)[-1] == table), None
        )
        if member is None:
            return
        with self.zip.open(member) as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8", newline="")
            yield from csv.DictReader(text)

    def has(self, table: str) -> bool:
        return any(name.rsplit("/", 1)[-1] == table for name in self.zip.namelist())


@dataclass
class Report:
    """What one dataset gave: the foods, and what was left out and why."""

    dataset: str
    sha256: str
    foods: list  # validated Food objects
    rejected: list[dict]
    excluded_american: int
    duplicates_dropped: list[dict]


def read_dataset(path: Path, expected_sha256: str | None = None) -> Report:
    """Validate and map one archive. expected_sha256 defaults to the pinned value."""
    if path.name not in PINNED:
        raise ValueError(f"not a pinned USDA archive: {path.name}")
    dataset, pinned_sha = PINNED[path.name]
    digest = sha256_file(path)
    expected = expected_sha256 or pinned_sha
    if digest != expected:
        raise ValueError(f"unexpected checksum for {path.name}: {digest}; expected {expected}")

    archive = Archive(path)
    data_type = DATA_TYPES[dataset]
    categories = {r["id"]: r["description"] for r in archive.rows("food_category.csv")}
    food_rows = {
        int(r["fdc_id"]): r for r in archive.rows("food.csv") if r["data_type"] == data_type
    }

    # Units by nutrient id, as the archive names them.
    units = {r["id"]: r["unit_name"] for r in archive.rows("nutrient.csv")}
    wanted = set(food_rows)
    amounts: dict[int, dict[int, Decimal]] = {}
    for row in archive.rows("food_nutrient.csv"):
        if not row["fdc_id"] or row["amount"] == "":
            continue
        fdc = int(row["fdc_id"])
        if fdc in wanted:
            amounts.setdefault(fdc, {})[int(row["nutrient_id"])] = Decimal(row["amount"])

    portions: dict[int, list[dict]] = {}
    for row in archive.rows("food_portion.csv"):
        if row["fdc_id"] and int(row["fdc_id"]) in wanted:
            portions.setdefault(int(row["fdc_id"]), []).append(row)

    excluded = 0
    duplicates: list[dict] = []
    keep: dict[int, dict] = {}
    for fdc, row in food_rows.items():
        category = categories.get(row.get("food_category_id") or "", "")
        if category in AMERICAN_CATEGORIES:
            excluded += 1
            continue
        keep[fdc] = row

    # One record per description: the newest publication, the others are reported.
    by_description: dict[str, list[int]] = {}
    for fdc, row in keep.items():
        by_description.setdefault(row["description"].strip(), []).append(fdc)
    dropped: set[int] = set()
    for description, ids in by_description.items():
        if len(ids) < 2:
            continue
        newest = max(ids, key=lambda i: (keep[i]["publication_date"], i))
        for fdc in ids:
            if fdc != newest:
                dropped.add(fdc)
                duplicates.append({"fdc_id": fdc, "kept": newest, "description": description})

    foods = []
    rejected: list[dict] = []
    for fdc, row in sorted(keep.items()):
        if fdc in dropped:
            continue
        try:
            foods.append(
                build_food(
                    fdc_id=fdc,
                    description=row["description"],
                    data_type=row["data_type"],
                    publication_date=row["publication_date"],
                    amounts=amounts.get(fdc, {}),
                    units=units,
                    portion_rows=portions.get(fdc, []),
                    german_name=None,
                )
            )
        except Rejected as error:
            rejected.append(
                {"fdc_id": fdc, "description": row["description"], "reason": str(error)}
            )

    return Report(
        dataset=dataset,
        sha256=digest,
        foods=foods,
        rejected=rejected,
        excluded_american=excluded,
        duplicates_dropped=duplicates,
    )
