# Epic 03 — Initial ingredient catalog

**Status:** Blocked by the ingestion CLI

## Outcome

PostgreSQL contains a useful, reproducible baseline of unbranded ingredients
and the small set of health-focused nutrients selected by the research spike.

## Scope

- pin the selected upstream dataset version and record its checksum
- define repeatable inclusion rules for unbranded, unprocessed, or lightly
  processed foods
- keep preparation states such as raw, dried, boiled, and cooked distinct
- import vegetables, fruit, grains, legumes, nuts, seeds, and other agreed
  ingredient groups
- retain source names, identifiers, provenance, and relevant quality markers
- generate a report covering counts, gaps, duplicates, and rejected records
- document the exact command needed to reproduce the catalog

## Acceptance criteria

- The catalog contains representative foods from every agreed initial group.
- Branded products and composite meals are excluded by documented rules.
- Rebuilding from an empty database produces the same logical catalog.
- Re-running the pinned import is idempotent.
- Sampled nutrient values can be traced back to the exact upstream record.
- Raw and cooked forms are not merged when their nutritional meaning differs.
- Missing-value rates for each selected nutrient are visible in the report.
- A small manual review finds no unexplained zeros or obvious unit errors.

## Not in this epic

Branded food, automatic upstream updates, translations beyond what is needed for
useful search, or a comprehensive cleanup of every upstream food description.
