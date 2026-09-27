# BLS 4.0 importer

The dedicated importer in [`importers/bls4/`](../importers/bls4/) reads the
checksum-pinned official BLS 4.0 workbook. By default it imports all 7,140
generic foods, including prepared dishes. It does not import branded labels;
those will come from your own scans. The earlier 11-code sample remains in
[`selected.codes`](../importers/bls4/selected.codes) for small test runs.

## Source file

Download `BLS_4_0_2025_DE.zip` from the [official BLS download](https://blsdb.de/download)
and extract it under `data/bls4/`. The expected workbook is
`data/bls4/BLS_4_0_2025_DE/BLS_4_0_Daten_2025_DE.xlsx`, SHA-256
`524bbefe25b691f5cb3de7a9f3e27fa2967aebfeabf217d99414ba7806e78c60`.
`data/` is ignored by Git. The importer refuses changed workbook bytes.

## Commands

```sh
uv run --locked bls4-import --dry-run
make db-up
uv run --locked bls4-import
uv run --locked bls4-import --codes importers/bls4/selected.codes --dry-run
```

`--workbook` overrides the source path; `DATABASE_URL` selects a different
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

Nutrition is per 100 g. `ENERCC`, `PROT625`, `FAT`, `CHO`, and `FIBT` map to
kcal, protein, fat, carbs, and fiber. Source markers such as `TR`, `<LOD`,
`<LOQ`, and `-` become `NULL`, never zero.

The [BLS 4.0 erratum](https://www.blsdb.de/bls) identifies double-counted
oligosaccharides in published energy. The importer recalculates kcal for the
387 rows where all required inputs are present. For 24 further affected rows,
one or more inputs are missing: those foods are imported, but kcal is `NULL`
instead of using the suspect published number. When `OLSAC` itself is
nonnumeric, the published energy is retained; its marker appears in the report.
Other published errata were not applied to these five V1 nutrients.

Each future source should have its own importer. Do not edit an importer while
it is writing to PostgreSQL.
