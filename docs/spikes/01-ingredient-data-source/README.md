# Research spike — Ingredient nutrition data source

**Status:** Recommendation complete

## Decision

Use the **Bundeslebensmittelschlüssel (BLS) 4.x** as the primary source for the
initial ingredient catalog.

BLS is the maintained German national nutrient database, covers the intended
ingredient groups well, distinguishes preparation states, provides German and
English food names, and carries provenance for every nutrient value. Its CC BY
4.0 license permits use in this project with attribution.

No major blocker was found. There is one release-management condition: BLS 4.0
has a current erratum whose corrections are planned for BLS 4.1. Before a
production seed, review any newer release. The initial importer pins
4.0 and handles the relevant energy erratum described in the assessment.

## Spike artifacts

- [BLS 4.0 assessment](bls4-assessment.md)
- [Inspected source release and checksums](source-lock.md)
- [Representative ingredient values](representative-foods.md)

## Why BLS over the alternatives

USDA FoodData Central remains a useful cross-check and fallback when BLS has a
documented gap. The Swiss Food Composition Database is another credible regional
reference. Neither offers a stronger default than the maintained German source
for this project's locale.

Do not merge several databases merely to increase row count. A secondary source
should be added only for a named missing food or nutrient, with its own identity
and provenance.

## Decisions made by this spike

- Primary source family: BLS 4.x.
- Source food identity: BLS code plus the chosen source version, not the food name.
- Reference basis: nutrient values per 100 g edible portion.
- The importer must understand original BLS values, markers, and provenance.
  A retained, checksum-identified source file and import report support
  reproduction; V1 stores only selected numeric energy and macro values.
- Raw, dried, and cooked forms remain distinct foods.
- The importer must be version-aware and idempotent.
- The original 11-code sample is retained for testing; the local catalog now
  imports all 7,140 generic BLS 4.0 foods, including prepared dishes.
- The BLS 4.0 importer recomputes affected kcal from the erratum's corrected
  formula when `OLSAC` is positive; see the [import guide](../../bls4-import.md).

## Decisions still open

- whether a narrower ingredient-only view is useful alongside the full catalog
- the canonical machine input accepted by future manual/agent entry tooling

## Primary sources

- [BLS download and license](https://blsdb.de/download)
- [BLS 4.0 documentation and current errata](https://www.blsdb.de/bls)
- [BLS FAQ](https://www.blsdb.de/faq)
- [USDA FoodData Central documentation](https://fdc.nal.usda.gov/data-documentation/)
- [Swiss Food Composition Database](https://naehrwertdaten.ch/en/)
