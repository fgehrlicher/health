"""Apply the published BLS 4.0 erratum to parsed foods, never silently."""

from dataclasses import dataclass, replace
from decimal import Decimal
from pathlib import Path

from bls4_importer.source import COMPONENTS, NUTRIENTS, OTHER_NUTRIENTS, Food, convert

ERRATUM_PATH = Path(__file__).resolve().parents[2] / "erratum-2026-08.tsv"
# Checksum of the erratum PDF the overlay was transcribed from.
ERRATUM_PDF_SHA256 = "ae021760436f1b6af09fd1df46e93b64d94e415f0a3b665e1d901cdee4ddd8c3"


@dataclass(frozen=True)
class Correction:
    code: str
    components: tuple[str, ...]
    # "correct": replace the published value; "withhold": store NULL until BLS 4.1.
    action: str
    published: Decimal | None
    corrected: Decimal | None
    section: str


def load_erratum(path: Path = ERRATUM_PATH) -> dict[str, list[Correction]]:
    corrections: dict[str, list[Correction]] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        code, components, action, published, corrected, section = line.split("\t")
        components = tuple(components.split(","))
        unknown = [c for c in components if c not in COMPONENTS or c in ("OLSAC", "OA")]
        if unknown:
            raise ValueError(f"erratum line {line_number}: components not imported: {unknown}")
        if action == "correct" and (len(components) != 1 or not published or not corrected):
            raise ValueError(f"erratum line {line_number}: a correction needs one component")
        if action not in ("correct", "withhold"):
            raise ValueError(f"erratum line {line_number}: unknown action {action!r}")
        corrections.setdefault(code, []).append(
            Correction(
                code,
                components,
                action,
                Decimal(published) if published else None,
                Decimal(corrected) if corrected else None,
                section,
            )
        )
    return corrections


def to_stored(field: str, value: Decimal) -> Decimal:
    """Convert a value in the BLS unit to the stored unit of `field`."""
    if field in NUTRIENTS:
        return value
    _header, bls_unit, unit = OTHER_NUTRIENTS[field]
    return convert(value, bls_unit.strip("[]").split("/")[0], unit)


def apply_erratum(food: Food, corrections: list[Correction]) -> Food:
    nutrients = dict(food.nutrients)
    other = dict(food.other_nutrients)
    for correction in corrections:
        for component in correction.components:
            field = COMPONENTS[component]
            values = nutrients if field in nutrients else other
            if correction.action == "withhold":
                values[field] = None
                continue
            # Refuse to correct a different value than the erratum describes.
            published = to_stored(field, correction.published)
            current = values[field]
            if current is None or current.quantize(published) != published:
                raise ValueError(
                    f"erratum {correction.section} expects {component} {correction.published} "
                    f"for {food.code}, workbook has {current}"
                )
            values[field] = to_stored(field, correction.corrected)
    return replace(food, nutrients=nutrients, other_nutrients=other)
