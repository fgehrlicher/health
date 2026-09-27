# BLS 4.0 ingredient importer

The Rust CLI reads the exact official BLS 4.0 workbook inspected in the
[source lock](spikes/01-ingredient-data-source/source-lock.md). It imports only
codes listed in a text file. The [starter list](../db/imports/bls4-v1.codes)
contains 11 reviewed foods across fruit, vegetables, rice, legumes, nuts, and
seeds, including raw and boiled variants. It is a working sample, not the full
ingredient catalog.

## Get the source file

Download `BLS_4_0_2025_DE.zip` from the
[official BLS page](https://blsdb.de/download), save it under `data/bls4/`,
and extract it there. `data/` is ignored by Git, so keep your copy of the
official package if you want to rebuild without downloading it again.

The expected SHA-256 of `BLS_4_0_Daten_2025_DE.xlsx` is
`524bbefe25b691f5cb3de7a9f3e27fa2967aebfeabf217d99414ba7806e78c60`.
The CLI refuses other workbook bytes instead of silently accepting another
release or edited data.

## Validate and import

From the repository root, with PostgreSQL running:

```sh
make db-up
cargo run --bin health-import -- bls4 \
  --workbook data/bls4/BLS_4_0_2025_DE/BLS_4_0_Daten_2025_DE.xlsx \
  --codes db/imports/bls4-v1.codes --dry-run
cargo run --bin health-import -- bls4 \
  --workbook data/bls4/BLS_4_0_2025_DE/BLS_4_0_Daten_2025_DE.xlsx \
  --codes db/imports/bls4-v1.codes
```

Set `DATABASE_URL` to target a different PostgreSQL database. The dry run
needs no database. Success prints a JSON report with attribution, the workbook
and code-list checksums, timestamp, counts, nonnumeric source markers, and
number of energy values corrected. Save that output if you need a durable
import record. An
invalid workbook, selected code, required value, or database conflict fails
without a partial write.

Each selected BLS code becomes one ingredient food and one `BLS 4.0` source.
The English BLS name is the initial display name; the German name is an alias.
New foods get a stable `bls4-<code>` slug. Existing BLS sources, including the
three development-fixture foods, are reused. Reruns update changed source
values but leave manually edited food names and aliases alone. Preparation
variants remain separate because their BLS codes differ.

## Value handling

Values are per 100 g edible food. The importer maps `ENERCC`, `PROT625`,
`FAT`, `CHO`, and `FIBT` to the fixed database columns. Known nonnumeric
markers such as `TR`, `<LOD`, `<LOQ`, and `-` become SQL `NULL`, never zero.
The report names each marker; unknown markers and impossible amounts fail
validation before writing.

The [August 2026 BLS erratum](https://www.blsdb.de/bls) says 4.0's published
energy double-counts available oligosaccharides. When `OLSAC` is positive,
the importer recalculates whole-number kcal from the erratum's corrected
formula, using protein, fat, available carbohydrate, fiber, alcohol, organic
acids, and polyols. If any required input is nonnumeric, the selected food is
rejected. When `OLSAC` itself is nonnumeric, the published energy is retained
and its marker appears in the report; it is not treated as a known zero.

Only the starter list and BLS 4.0's relevant energy erratum have been reviewed
for this import. Expand the code list deliberately: group prefixes include
processed products, and other published errata may affect future selections.
