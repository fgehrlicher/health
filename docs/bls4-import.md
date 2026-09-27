# BLS 4.0 importer

The dedicated importer in [`importers/bls4/`](../importers/bls4/) reads the
checksum-pinned official BLS 4.0 workbook. By default it imports all 7,140
generic foods, including prepared dishes. It does not import branded labels;
those will come from your own scans. The earlier 11-code sample remains in
[`selected.codes`](../importers/bls4/selected.codes) for small test runs.

## Source file

If `data/bls4/BLS_4_0_2025_DE/BLS_4_0_Daten_2025_DE.xlsx` is missing, the
importer downloads the official package from
<https://blsdb.de/assets/uploads/BLS_4_0_2025_DE.zip> (linked from the
[BLS download page](https://blsdb.de/download)) into `data/bls4/` and extracts
the workbook. The package must match SHA-256
`12b7a6ba62807ec9b301eb276f897dc85f99b2292311618dec3749a12d984c91` and the
workbook `524bbefe25b691f5cb3de7a9f3e27fa2967aebfeabf217d99414ba7806e78c60`;
the importer refuses other bytes. `data/` is ignored by Git. An explicit
`--workbook` path is never downloaded.

## Commands

```sh
uv run --locked bls4-import --dry-run
make db-up
uv run --locked bls4-import
uv run --locked bls4-import --codes importers/bls4/selected.codes --dry-run
```

`--workbook` uses a local workbook instead; `DATABASE_URL` selects a different
PostgreSQL database. A dry run validates without connecting to PostgreSQL.
The JSON report includes selected/created/updated/skipped counts, checksum,
corrected-energy count, rows with unavailable energy, and aggregate counts of
nonnumeric markers. Database writes are transactional and reruns are idempotent.

Each BLS code maps to one `generic` food and one `BLS 4.0` nutrition source.
English names are displayed initially; German names are aliases. BLS codes
stay searchable, their group prefix is stored in `food_sources.group_code`,
and preparation variants stay separate. Existing catalog
names and aliases are not overwritten by reruns.

## Values and limits

Nutrition is per 100 g. The importer reads the 14 components that match the
EU nutrition label, listed in the [database guide](database.md#import-contract):
energy in kJ and kcal, fat with saturated, mono- and polyunsaturated fatty
acids, available carbohydrate with sugars, polyols, and starch, fiber,
protein, salt, and alcohol. Source markers such as `TR`, `<LOD`, `<LOQ`, and
`-` become `NULL`, never zero. Sugars or polyols above available carbohydrate
reject the row; this holds for every BLS 4.0 row.

BLS is not always internally consistent, so these are not validated: 42 rows
have more saturated fatty acids than fat (e.g. `F545100` plantain), 446 have
sugars plus starch above available carbohydrate, and salt does not always
equal sodium × 2.5.

The [BLS 4.0 erratum](https://www.blsdb.de/bls) identifies double-counted
oligosaccharides in published energy, both kJ and kcal. The importer
recalculates both with EU factors for the 387 rows where all required inputs
are present; the same kJ formula reproduces the published kJ of 6,724 of the
6,729 unaffected rows. For 24 further affected rows, one or more inputs are
missing: those foods are imported, but energy is `NULL` instead of the
suspect published number. When `OLSAC` itself is nonnumeric, the published
energy is retained; its marker appears in the report. The other published
errata (zinc, almond calcium, amino acids) do not affect the imported fields.

## Other BLS fields

The workbook has 138 components, each with a data-origin and reference column,
plus a free-text note. Worth knowing when extending the import:

- **Vitamins and minerals** (A, D, E, B-vitamins, folate, C; sodium,
  potassium, calcium, magnesium, iron, zinc, iodide, …) are 93–100% numeric.
  They would suit a long-format nutrient table rather than more columns.
  Before adding them, apply the zinc and almond-calcium errata.
- **Omega-3 and omega-6** totals (`FAPUN3`, `FAPUN6`), **cholesterol**
  (`CHORL`), and **water** are well populated.
- **Amino acids** are affected by the erratum; wait for BLS 4.1.
- **Data origin**: about 77% of protein and fat values are recipe
  calculations, about 5% laboratory analyses; the rest come from other
  databases, literature, or rescaling. Useful as a quality hint, not stored.
- The **note** column is set for only 4 rows (sweeteners such as maltitol).

Each future source should have its own importer. Do not edit an importer while
it is writing to PostgreSQL.
