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
stay searchable, their first letter sets `foods.food_group` (filled in when
empty, never overwritten), and preparation variants stay separate. Existing catalog
names and aliases are not overwritten by reruns.

## Values and limits

Nutrition is per 100 g. The importer reads the 14 components that match the
EU nutrition label, listed in the [database guide](database.md#import-contract):
energy in kJ and kcal, fat with saturated, mono- and polyunsaturated fatty
acids, available carbohydrate with sugars, polyols, and starch, fiber,
protein, salt, and alcohol. Source markers such as `TR`, `<LOD`, `<LOQ`, and
`-` become `NULL`, never zero. Sugars or polyols above available carbohydrate
reject the row; this holds for every BLS 4.0 row.

The importer also stores 26 further nutrients in `food_source_nutrients`:
vitamins A, D, E, K, C, B1, B2, niacin, B6, folate, and B12; sodium,
potassium, calcium, magnesium, phosphorus, iron, zinc, and iodine; omega-3,
EPA, DHA, omega-6, and cholesterol; water and lactose. They are stored in EU
label units, so vitamin B6 converts from µg to mg. An unknown value has no row.
Four diet drinks list slightly more than 100 g water per 100 g; those water
values are dropped and reported as `implausible`.

Each food's `preparation_state` comes from the last preparation word in its
German name outside parentheses: "Reis poliert, gekocht, gebraten ohne Fett"
is `fried`, "Karottensalat (gegart) mit Marinade" has none. 3,699 foods get
one of: raw, boiled, stewed, braised, grilled, fried, baked, deep-fried,
dried, frozen, canned, smoked, poached, steamed, roasted, gratinated, toasted,
blanched, or cooked. The sixth code digit mostly agrees but is undocumented,
so it is not used. Reruns fill a missing state but never overwrite one.

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
energy is retained; its marker appears in the report.

The erratum's other items are applied from
[`erratum-2026-08.tsv`](../importers/bls4/erratum-2026-08.tsv), transcribed
from the erratum PDF (SHA-256 recorded in the file and the report):

- **Corrected** where the erratum gives a new value: vitamin A of skimmed milk
  (`M111100`), iodine of three low-fat milks, and calcium of sweet and
  blanched almonds. The importer fails if the published value differs from the
  one the erratum names, so a changed workbook cannot be silently overwritten.
- **Withheld** (`NULL`) where BLS 4.1 will recalculate: vitamin A, iodine, and
  calcium of the 6, 19, and 132 recipes using those ingredients, and fat,
  fatty acids, and energy of raw anchovy (`T104100`, fat 13.7 g instead of
  2.3–6.3 g) and its 16 derived foods.

The 59 blank zinc cells import as unknown, as the erratum prescribes. Amino
acids are not imported. The report lists the applied erratum sections.

## Other BLS fields

The workbook has 138 components; the importer stores 40. Not imported:

- **Data origin** per value: about 77% of protein and fat values are recipe
  calculations, about 5% laboratory analyses; the rest come from other
  databases, literature, or rescaling. A quality hint for later.
- **Amino acids**: affected by the erratum; wait for BLS 4.1.
- Single fatty acids, sugars other than lactose, fiber fractions, and organic
  acids: too detailed for tracking.
- The **note** column is set for only 4 rows (sweeteners such as maltitol).

Each future source should have its own importer. Do not edit an importer while
it is writing to PostgreSQL.
