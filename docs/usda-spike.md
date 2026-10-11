# USDA FoodData Central: research spike

Question: can the whole USDA bulk download go into our catalog, and what would
have to change? This spike downloaded the CSV bundles, measured them against
the database and the BLS import, and decided nothing has been imported yet.
It wrote no data anywhere except the git-ignored `data/usda/` folder.

Reproduce the numbers:

```sh
python3 importers/usda/spike/survey.py > data/usda/spike-summary.json
```

The bundles come from <https://fdc.nal.usda.gov/download-datasets>. Checksums
(SHA-256, first 16 characters) recorded at download:

| Bundle | Release | Size | SHA-256 |
| --- | --- | --- | --- |
| Foundation Foods, CSV | 2026-04-30 | 3.8 MB | `70457ee9d9342f43` |
| SR Legacy, CSV | 2018-04 | 6.1 MB | `b80817294b885053` |
| Survey (FNDDS), CSV | 2024-10-31 | 3.3 MB | `5ccc25ec2777a898` |
| Supporting data, CSV | 2022-10-28 | 0.95 MB | `03f5cb6d5ec76fc5` |

Branded Food (large, American retail products) was not downloaded. You said
you do not need it.

## What is in the bundles

| Dataset | Foods | What it is | Verdict |
| --- | --- | --- | --- |
| SR Legacy | 7,793 | USDA's reference database, generic foods, last release 2018 | import |
| Foundation Foods | 469 (402 distinct descriptions) | Newer analytical data for generic foods | import |
| Survey (FNDDS) | 5,432 | Foods and dishes as eaten in the US survey, many mixed dishes | later, if at all |
| Branded | not downloaded | US retail products | out of scope |

The Foundation bundle also holds about 88,000 rows of samples, acquisitions and
sub-samples. These are raw lab records, not foods, and the importer ignores them.

## Coverage

Counts are foods that have a value. Mapping uses the fallbacks listed under
"Mapping" below.

| Column | SR Legacy (7,793) | Foundation (469) | Survey (5,432) |
| --- | --- | --- | --- |
| energy kcal | 7,793 | 378 | 5,431 |
| energy kJ | 7,793 | 135 | 0 |
| fat | 7,793 | 413 | 5,431 |
| saturated fat | 7,450 | 152 | 5,431 |
| carbohydrate (by difference) | 7,793 | 377 | 5,431 |
| sugars | 6,007 | 185 | 5,431 |
| fiber | 7,231 | 241 | 5,431 |
| protein | 7,793 | 425 | 5,431 |
| sodium | 7,709 | 403 | 5,431 |
| core four (kcal, fat, carbs, protein) | 7,793 | 377 | 5,431 |
| other catalog nutrients, rows | 154,935 | 5,713 | 119,482 |

Reading this: SR Legacy is nearly complete. Foundation is patchy: many of its
foods have no fiber, sugars or kJ. Survey is complete, but it is American
survey data.

## Compatibility with the catalog

**Fits as it is**

- `foods`: `slug`, `name` (English), `aliases`, `kind = 'generic'`. Nothing in
  the schema is USDA-specific.
- `food_sources`: `source_name = 'USDA FoodData Central'`, `external_id` = FDC
  ID, `reference_quantity = 100`, `reference_unit = 'g'`. Both foundational
  bundles are per 100 g.
- `food_source_nutrients`: 24 of the 26 catalog nutrients have a USDA source.
  Vitamin A, D, E, K, C, B1, B2, niacin, B6, B12, folate, sodium, potassium,
  calcium, magnesium, phosphorus, iron, zinc, iodine, EPA, DHA, cholesterol,
  water and lactose. Omega-3 and omega-6 totals are not single USDA values, so
  they stay unknown.
- `food_portions`: SR Legacy has 14,449 portion rows with a gram weight, for
  example 1 cup = 240 g. Foundation has 187.

**Needs a decision or a rule**

- **kJ.** Foundation has kJ for 135 of 469 foods, and survey has none. The
  catalog stores kJ next to kcal, and both come from the same energy value. A
  rule would derive kJ = kcal × 4.184. This is a conversion, not an estimate.
  Our rules say do not guess, so we need your approval of this rule.
- **Duplicates.** 65 Foundation descriptions appear more than once, 67 extra
  records in all, and two of them three times. The copies come from the 2019
  release and the 2019-12 release. For example "Broccoli, raw" is 321900 and
  747447. The importer must pick one. Proposal: keep the record with the newer
  publication date and report the others.
- **Preparation state.** The last-word rule finds a state for 2,454 of 7,793
  SR Legacy foods (31%) and for 170 of the 402 distinct Foundation
  descriptions. Other foods stay without a state. That is allowed by the schema.
- **Portions.** SR Legacy portion text is in the `modifier` column, not
  `portion_description`: "oz", "cup", "tbsp", "slice", "serving". Survey uses
  numeric codes instead of text, so its portions need a lookup we do not have.

**Does not fit, or is risky**

- **Names.** Every USDA name is English. Our UI puts German first, and only
  the BLS source supplies `name_de`. A USDA-only food would show English only.
  This is the main product decision. See below.
- **Food groups.** `foods.food_group` takes BLS letters. USDA has 28 food
  categories and no letters, so USDA foods would have no group. Storing the
  category would need a new column.
- **Survey nutrient numbers.** The survey file keys nutrients by
  `nutrient_nbr`, while the other bundles use the nutrient `id`. Read with the
  wrong key, survey shows zero coverage. This is handled in the spike script,
  and it matters only if survey is imported.
- **American content.** 931 SR Legacy foods are in the categories Fast Foods (312),
  Restaurant Foods (109), Baby Foods (345) and American Indian/Alaska Native
  Foods (165). A name pattern for brands finds 112 SR names. That pattern also
  matches some generic names, such as "Pears ... (Includes foods for USDA's Food
  Distribution Program)", so it can only flag names for review.
- **Overlap.** Some USDA foods will describe the same food as a BLS food, for
  example raw broccoli, and some SR Legacy foods will also appear in Foundation.
  The spike did not measure either overlap. Today every import creates a
  separate food. Merging them would need a decision and a matching step.

## Mapping

Label columns use the EU label definitions, as the BLS importer does:

- `energy_kcal`: USDA 1008, falling back to 2047 (Atwater General Factors,
  the basis of the EU label).
- `energy_kj`: USDA 1062, or the kcal rule above.
- `carbs_g`: USDA 1005 minus fiber 1079. The label's available carbohydrate
  leaves fiber out. Without a fiber value, carbs stay unknown.
- `sugars_g`: 2000, falling back to 1063.
- `salt_g`: sodium 1093 mg × 2.5 / 1000.
- `polyols_g`: not in USDA data, unknown.
- Other nutrients: the 24 mapped nutrients above, with folate 1190 falling back
  to 1177. Units are checked before any value is written.

Missing values stay unknown, never zero, as in the rest of the catalog.

## Scale

The first dry run and a trial import into a scratch database, with the decisions
above applied, gave: 7,259 foods (6,862 SR Legacy and 397 Foundation), 7,259
sources, 141,510 `food_source_nutrients` rows and 12,944 portions. Rerunning the
import updates the same foods and creates none. That is about the size of the
BLS import (7,140 foods), so the existing write pattern held.

## Decisions needed

1. **Scope.** Import SR Legacy and Foundation, and leave out Survey and Branded?
   Proposal: yes. Also leave out the four American categories (931 foods)?
   Proposal: yes.
2. **Names.** English names for USDA foods, with a German alias only where a
   name is curated? Or should the UI show German for these foods too, which
   needs a translation source? The API currently takes `name_de` from BLS only.
3. **kJ.** Derive from kcal with 4.184 for the 334 Foundation foods that lack
   kJ? Proposal: yes, with the rule written into the importer.
4. **Duplicates.** Keep the newer publication per description? Proposal: yes.
5. **BLS overlap.** Keep USDA foods as separate foods for now? Proposal: yes,
   and measure the overlap before deciding on merging.

## Status

The decisions were taken as proposed above. The importer now reads the pinned
zip archives directly, with the scope and duplicate rules, and dry-runs by
default. The on-demand API path was removed. The import was run against a
scratch database only, not the box. The catalog's search lists the source,
with a filter.

## Corrections

- **Lactose.** The first version of the survey mapped lactose to USDA id 1010,
  which is sucrose. Lactose is id 1013. The numbers in the table above for
  lactose were from the wrong id, and the importer uses 1013.
- **Rules found in the first dry run.** 10 Foundation foods had a carbohydrate
  by difference of −0.1 g to −0.5 g, which is rounding, so they are set to 0.
  136 foods had sugars slightly above the available carbohydrate. Up to 0.5 g is
  rounding and kept. Above that, only the sugars are left unknown, and the food
  is kept. These foods are noted in the import report.
- **Unit check.** The importer checks each USDA unit and the catalog's unit for
  every nutrient, and it stops if they differ.
