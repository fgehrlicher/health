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
has a current erratum whose corrections are planned for BLS 4.1. Before the
first production seed, use 4.1 if it has been released. Otherwise, ingest 4.0
with the errata handling described in the assessment.

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
- Source food identity: BLS code plus source release, not the food name.
- Reference basis: nutrient values per 100 g edible portion.
- Original BLS value, status, provenance category, and reference must survive
  normalization.
- Raw, dried, and cooked forms remain distinct foods.
- The importer must be version-aware and idempotent.
- The initial seed is a curated ingredient subset, not all 7,140 rows.

## Decisions still open

- the exact first nutrient shortlist
- the exact ingredient inclusion rules within the relevant BLS groups
- whether corrected energy is stored as a derived value or calculated on read
- the canonical machine input accepted by the Rust CLI

## Primary sources

- [BLS download and license](https://blsdb.de/download)
- [BLS 4.0 documentation and current errata](https://www.blsdb.de/bls)
- [BLS FAQ](https://www.blsdb.de/faq)
- [USDA FoodData Central documentation](https://fdc.nal.usda.gov/data-documentation/)
- [Swiss Food Composition Database](https://naehrwertdaten.ch/en/)
