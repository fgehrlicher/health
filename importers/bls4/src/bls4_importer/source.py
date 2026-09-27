"""Read and validate the pinned BLS 4.0 workbook without touching the database."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from openpyxl import load_workbook

WORKBOOK_SHA256 = "524bbefe25b691f5cb3de7a9f3e27fa2967aebfeabf217d99414ba7806e78c60"
SOURCE_NAME = "BLS 4.0"
FIELDS = {
    "energy": ("ENERCC ", "[kcal/100g]"),
    "protein": ("PROT625 ", "[g/100g]"),
    "fat": ("FAT ", "[g/100g]"),
    "carbs": ("CHO ", "[g/100g]"),
    "fiber": ("FIBT ", "[g/100g]"),
    "oligosaccharides": ("OLSAC ", "[g/100g]"),
    "alcohol": ("ALC ", "[g/100g]"),
    "organic_acids": ("OA ", "[g/100g]"),
    "polyols": ("POLYL ", "[g/100g]"),
}
MARKERS = {"", "TR", "<LOD", "<LOQ", "<LOD or <LOQ", "-"}


@dataclass(frozen=True)
class Food:
    code: str
    german_name: str
    english_name: str
    energy: Decimal
    protein: Decimal | None
    fat: Decimal | None
    carbs: Decimal | None
    fiber: Decimal | None


def parse_codes(contents: str) -> set[str]:
    codes = set()
    for line_number, line in enumerate(contents.splitlines(), 1):
        code = line.strip()
        if not code or code.startswith("#"):
            continue
        if len(code) != 7 or not code.isascii() or not code.isalnum() or code != code.upper():
            raise ValueError(f"invalid BLS code {code!r} at line {line_number}")
        if code in codes:
            raise ValueError(f"duplicate BLS code {code} at line {line_number}")
        codes.add(code)
    if not codes:
        raise ValueError("codes file does not select any foods")
    return codes


def columns_from_headers(headers: tuple) -> dict[str, int]:
    def find(name: str, unit: str | None = None) -> int:
        matches = [
            index
            for index, header in enumerate(headers)
            if isinstance(header, str)
            and (header == name if unit is None else header.startswith(name) and unit in header)
        ]
        if len(matches) != 1:
            raise ValueError(
                f"expected one BLS column {name!r} with unit {unit!r}; got {len(matches)}"
            )
        return matches[0]

    columns = {
        "code": find("BLS Code"),
        "german_name": find("Lebensmittelbezeichnung"),
        "english_name": find("Food name"),
    }
    columns.update({field: find(*header) for field, header in FIELDS.items()})
    return columns


def required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be nonempty text")
    return value.strip()


def parse_amount(value: object, code: str, field: str, issues: list[dict]) -> Decimal | None:
    if value is None or isinstance(value, str) and value.strip() in MARKERS:
        marker = "blank" if value is None or not value.strip() else value.strip()
        issues.append({"code": code, "field": field, "marker": marker})
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise TypeError(f"unsupported {field} value {value!r}")
    try:
        amount = Decimal(str(value).strip())
    except Exception as error:
        raise ValueError(f"invalid {field} value {value!r}") from error
    if not amount.is_finite() or amount < 0:
        raise ValueError(f"invalid {field} value {value!r}")
    return amount


def parse_food(
    row: tuple, columns: dict[str, int], code: str, issues: list[dict]
) -> tuple[Food, bool]:
    def amount(field: str) -> Decimal | None:
        return parse_amount(row[columns[field]], code, FIELDS[field][0].strip(), issues)

    german_name = required_text(row[columns["german_name"]], "German food name")
    english_name = required_text(row[columns["english_name"]], "English food name")
    energy = amount("energy")
    if energy is None:
        raise ValueError("energy must be numeric")
    protein, fat, carbs, fiber = (amount(field) for field in ("protein", "fat", "carbs", "fiber"))
    oligosaccharides = amount("oligosaccharides")
    for field, value in zip(
        ("protein", "fat", "carbs", "fiber", "oligosaccharides"),
        (protein, fat, carbs, fiber, oligosaccharides),
        strict=True,
    ):
        if value is not None and value > 100:
            raise ValueError(f"{field} exceeds 100 g per 100 g")
    if energy > 1000:
        raise ValueError("energy exceeds 1000 kcal per 100 g")

    corrected = oligosaccharides is not None and oligosaccharides > 0
    if corrected:
        alcohol, organic_acids, polyols = (
            amount(field) for field in ("alcohol", "organic_acids", "polyols")
        )
        components = (protein, fat, carbs, fiber, alcohol, organic_acids, polyols)
        if any(value is None for value in components):
            raise ValueError("nonnumeric component needed for corrected energy")
        if any(value > 100 for value in (alcohol, organic_acids, polyols)):
            raise ValueError("corrected-energy component exceeds 100 g per 100 g")
        # BLS 4.0 erratum: OLSAC was counted twice. Recalculate before rounding.
        energy = (
            protein * 4
            + fat * 9
            + (carbs - polyols) * 4
            + fiber * 2
            + alcohol * 7
            + organic_acids * 3
            + polyols * Decimal("2.4")
        ).quantize(Decimal(1), rounding=ROUND_HALF_UP)
        if energy < 0 or energy > 1000:
            raise ValueError("corrected energy is outside 0–1000 kcal per 100 g")
    return Food(code, german_name, english_name, energy, protein, fat, carbs, fiber), corrected


def read_workbook(path: Path, selected: set[str]) -> tuple[list[Food], list[dict], int]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        rows = workbook.worksheets[0].iter_rows(values_only=True)
        columns = columns_from_headers(next(rows))
        found: dict[str, Food] = {}
        issues: list[dict] = []
        corrected = 0
        for line_number, row in enumerate(rows, 2):
            code = row[columns["code"]]
            if code not in selected:
                continue
            if code in found:
                raise ValueError(f"duplicate selected BLS code {code} in worksheet")
            try:
                food, was_corrected = parse_food(row, columns, code, issues)
            except ValueError as error:
                raise ValueError(f"BLS row {line_number} ({code}): {error}") from error
            found[code] = food
            corrected += was_corrected
        missing = sorted(selected - found.keys())
        if missing:
            raise ValueError(f"selected BLS codes not found in workbook: {missing}")
        return [found[code] for code in sorted(found)], issues, corrected
    finally:
        workbook.close()
