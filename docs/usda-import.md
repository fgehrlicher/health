# USDA FoodData Central importer

The importer in [`importers/usda/`](../importers/usda/) reads the USDA bulk
downloads that you keep locally, and imports the generic foods from them. It
makes no network calls. The research behind these rules is in
[usda-spike.md](usda-spike.md).

## Source files

Download the two archives from
<https://fdc.nal.usda.gov/download-datasets> into `data/usda/raw/` (git-ignored):

- Foundation Foods, CSV, release 2026-04-30 (`FoodData_Central_foundation_food_csv_2026-04-30.zip`)
- SR Legacy, CSV, release 2018-04 (`FoodData_Central_sr_legacy_food_csv_2018-04.zip`)

The importer reads the tables straight from the zips. It refuses any file whose
SHA-256 differs from the pinned value, as the BLS importer does. The survey
(FNDDS) and branded archives are not read.

## Commands

```sh
uv run --locked usda-import                                 # dry run: validates, stores nothing
uv run --locked usda-import --report data/usda/report.json  # the same, with every food listed
uv run --locked usda-import --commit                        # stores the foods
```

A dry run is the default. It validates every food and prints a summary. The
full report (every food, rejection, note and dropped duplicate) goes to the
`--report` file. `--commit` stores the foods. `DATABASE_URL` selects the
database, as for the BLS importer. A rerun updates the same foods and creates
none.

Before a run on the production box, do a dry run, review the report, and do a
trial run against a scratch database.

## What is stored

- One `generic` food per USDA record, slug `usda-<fdcId>`, with the USDA
  description as its English name.
- One source, `USDA FoodData Central`, with the FDC ID as its external ID, and
  nutrition per 100 g.
- Nutrients for the 24 catalog nutrients that USDA gives. Omega-3 and omega-6
  totals are not single USDA values, so they stay unknown.
- Portions from the SR Legacy and Foundation gram weights, such as `1 cup` = 240 g.
- `preparation_state` only when the description ends in a state word such as
  `raw` or `dried`.
- The German name from [`names-de.tsv`](../importers/usda/names-de.tsv), when
  one is listed for that FDC ID. It is stored as an alias, as the BLS importer
  does. Review these names before you commit.

## Scope

- SR Legacy and Foundation only. Survey (FNDDS) and branded records are not
  read.
- Foods in the American categories are left out: Fast Foods, Restaurant Foods,
  Baby Foods, and American Indian/Alaska Native Foods. The report counts them.
- Foundation has several records for one description, from different releases.
  The one with the newest publication date is kept, and the others are listed
  in the report as dropped.

## How the values map

| Column | From USDA | Note |
| --- | --- | --- |
| `energy_kcal` | 1008, falling back to 2047 | 2047 is the Atwater General Factors basis of the label |
| `energy_kj` | 1062, or derived | when USDA has no kJ, it is kcal × 4.184, rounded to 0.1, and listed as derived |
| `fat_g`, `saturated_fat_g`, `monounsaturated_fat_g`, `polyunsaturated_fat_g` | 1004, 1258, 1292, 1293 | as given |
| `carbs_g` | 1005 − 1079 | total carbohydrate less fiber, the label's available carbohydrate |
| `sugars_g` | 2000, falling back to 1063 | total sugars |
| `fiber_g`, `protein_g`, `alcohol_g`, `starch_g` | 1079, 1003, 1018, 1009 | as given |
| `salt_g` | 1093 × 2.5 / 1000 | sodium converted to salt, the EU convention |
| `polyols_g` | — | not in USDA data, always unknown |

Other nutrients use these USDA ids: vitamins A (1106), D (1114), E (1109), K
(1185), C (1162), B1 (1165), B2 (1166), niacin (1167), B6 (1175), folate (1190,
falling back to 1177), B12 (1178); sodium (1093), potassium (1092), calcium
(1087), magnesium (1090), phosphorus (1091), iron (1089), zinc (1095), iodine
(1100); EPA (1278), DHA (1272), cholesterol (1253), water (1051), and lactose
(1013, not sucrose, which is 1010).

Every USDA unit is checked against the unit the catalog expects, and the
catalog's own units are checked before anything is written.

A missing USDA value stays unknown (`NULL`), never zero. If fiber is unknown,
`carbs_g` is unknown too.

## Rounding rules and notes

USDA rounds to one decimal place, and carbohydrate is calculated by difference,
so some values disagree slightly. The importer keeps the food and records what
it did in the report:

- **`carbs_clamped`**: a negative carbohydrate by difference down to −1 g is
  set to 0.
- **`rounding`**: sugars up to 0.5 g above the available carbohydrate are kept.
- **`sugars_unknown`**: a larger sugar conflict leaves only the sugars unknown.

A value that is wrong for other reasons rejects its food, and the rest of the
run goes on. Rejections are listed in the report with their reason. A negative
value below −1 g, or fiber above total carbohydrate, is one of these.

## Limits

- SR Legacy is USDA's 2018 release, its last. Foundation is newer, but covers
  only about 400 foods.
- Generic entries are not the same as a named product. For example, "Spices,
  paprika" is not specifically sweet (edelsüß) paprika, and "Spices, cumin seed"
  is the seed, not ground cumin.
- A food can be the same as a BLS food, for example raw broccoli. The importer
  keeps USDA foods as separate foods. Merging them is a separate decision.
- Names are English only, except for the curated German aliases. The web app
  shows German names only for BLS foods today.
