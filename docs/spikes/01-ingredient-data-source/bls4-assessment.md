# BLS 4.0 assessment

## Verdict

BLS 4.x is a good fit and should be the project's primary ingredient source.
The 4.0 dataset is usable, but its published errata must be part of the import
contract. Prefer BLS 4.1 if it is available when the first seed is built.

This assessment inspected the actual official BLS 4.0 package, not only the web
interface. The package was downloaded on 2026-09-25 from the
[official download page](https://blsdb.de/download).

## Dataset shape

The main workbook contains:

- 7,140 food rows
- 418 columns
- 3 identity columns: BLS code, German name, and English name
- 138 nutrient components, each represented by a value, provenance category,
  and reference column
- one trailing free-text `Hinweis` column

The separate component workbook defines all 138 nutrient codes, German and
English names, units, groups, and formulas. Of those components, 16 are always
calculated and 8 are calculated when their required inputs are available.

All values use 100 g of edible food as their reference basis. The workbook has
no duplicate BLS codes and no missing German or English food names.

## Food identity and classification

A BLS code is a seven-character hierarchical source identifier. Its first
character identifies the broad food group. Preparation and weight context are
also encoded in later positions. Codes removed from BLS are not reused, and MRI
publishes mappings when codes change between major versions.

Treat the code as an opaque external identifier in the canonical model. Parsing
its hierarchy may help select the initial catalog, but internal food identity
must not depend on the current encoding remaining unchanged.

The most relevant groups for the first plant-focused seed are:

| Prefix | Group | Rows in BLS 4.0 |
| --- | --- | ---: |
| C | Cereals, grains, grain products, rice | 231 |
| F | Fruit and fruit products | 275 |
| G | Vegetables and vegetable products | 560 |
| H | Mature legumes, nuts, oilseeds, other seeds | 142 |
| K | Potatoes, starchy plant parts, mushrooms | 157 |

Some useful ingredients also appear in other groups, such as oils under `Q` and
spices under `R`. Conversely, every relevant group contains processed products
that should not automatically enter the first seed. Prefix filtering is only a
first pass.

BLS has useful preparation-specific records. Examples include separate entries
for raw and boiled white rice, dry and boiled lentils, and dry and boiled
chickpeas. Those must remain distinct rather than being aliases of one food.

## Nutrient representation

Nutrient cells are not purely numeric. The importer must recognize:

| Source value | Meaning | Canonical handling |
| --- | --- | --- |
| number | reported content per 100 g | store the numeric value and provenance |
| `TR` | detected trace; exact amount unknown | non-zero trace status, no invented number |
| `<LOD` | below detection limit | censored value with detection-limit status |
| `<LOQ` | below quantification limit | censored value with quantification-limit status |
| `<LOD or <LOQ` | source does not distinguish the limit | censored value with the raw marker retained |
| `-` | no reliable value | missing, never zero |
| blank | currently an upstream defect in known cases | missing plus an import warning |

This is a strong match for the project's uncertainty principles, but it rules
out a simple nullable numeric column as the complete representation. Preserve
the raw marker even if the product initially exposes only a numeric value.

The source also retains significant figures dynamically. Do not round all
nutrients to a fixed number of decimal places during import.

## Coverage of likely first nutrients

This table reports numeric cells across all 7,140 foods. Non-numeric source
markers remain meaningful data rather than failed parsing.

| Component | Unit | Numeric rows | Numeric coverage | Notable non-numeric values |
| --- | --- | ---: | ---: | --- |
| Energy (`ENERCC`) | kcal | 7,140 | 100.00% | none; see known energy erratum |
| Protein (`PROT625`) | g | 7,117 | 99.68% | 23 `TR` |
| Fat (`FAT`) | g | 7,112 | 99.61% | LOD/LOQ, traces, missing |
| Available carbohydrate (`CHO`) | g | 7,140 | 100.00% | none |
| Total sugar (`SUGAR`) | g | 7,140 | 100.00% | none |
| Total fiber (`FIBT`) | g | 7,087 | 99.26% | 25 `<LOD`, 14 missing, 13 `TR`, 1 combined limit |
| Saturated fatty acids (`FASAT`) | g | 7,117 | 99.68% | 23 missing |
| Sodium (`NA`) | mg | 7,097 | 99.40% | 26 missing plus LOD/LOQ markers |
| Potassium (`K`) | mg | 7,121 | 99.73% | 16 missing plus limit markers |
| Magnesium (`MG`) | mg | 7,113 | 99.62% | 18 missing plus limit markers |
| Calcium (`CA`) | mg | 7,121 | 99.73% | 14 missing plus limit markers |
| Iron (`FE`) | mg | 7,113 | 99.62% | 22 missing plus limit markers |
| Zinc (`ZN`) | mg | 7,081 | 99.17% | 59 blank cells covered by the erratum |

The high coverage does not mean every value was directly measured. Every value
has one of 13 provenance categories, including analysis, literature,
aggregation, another nutrient database, transferred value, rescaling, recipe
calculation, logical zero, trace, and formula calculation. That category and the
raw reference are part of the value, not optional metadata.

References can contain several source citations separated by `#`. Preserve the
raw reference first. Splitting and normalizing citations can wait until there is
a concrete query that needs it.

## Known BLS 4.0 errata

The [current BLS page](https://www.blsdb.de/bls) links an August 2026 erratum.
The corrections are planned for BLS 4.1, which was not available at the time of
this assessment.

Material items are:

- Energy is too high for 411 foods because available oligosaccharides (`OLSAC`)
  were counted twice by the generating software. The mean error across affected
  records is 1.2%, with a documented maximum of 23.1%.
- The inspected workbook confirms all 411 affected rows. Seventy-nine are in
  groups C, F, G, H, or K. Examples relevant to the initial catalog include raw
  chicory, black salsify, mature beans, and cooked kidney beans.
- Fifty-nine zinc cells are blank even though blank nutrient cells are not part
  of the intended format. The erratum classifies 53 as missing and 6 as below a
  detection or quantification limit.
- Calcium for two almond records is scheduled for correction. The raw sweet
  almond value changes from 84.9 to 254 mg/100 g in BLS 4.1.
- Vitamin A and iodine corrections affect selected milk records and derived
  recipes.
- Phenylalanine and other amino-acid values are under review because some
  apparent zeros are not biologically plausible.
- Raw anchovy and derived records have a known fat and energy error.

These are not blockers for selecting BLS. They are blockers for importing 4.0
without versioning and validation.

## Required import policy

1. Check the official download page for BLS 4.1 before pinning the production
   seed.
2. Record the release name, retrieval time, file checksum, citation, and license
   with every import run.
3. Preserve every source value, marker, provenance category, and reference.
4. If 4.0 is used, calculate energy with the corrected documented formula or
   apply an explicit errata overlay. Never silently replace the source value.
5. Treat the 59 blank zinc cells as import warnings and missing values unless the
   erratum provides the corrected limit marker.
6. Apply or explicitly exclude the affected almond calcium values if calcium is
   in the first nutrient set.
7. Keep amino acids out of the first health-focused set unless the 4.1 fixes are
   available and validated.
8. Generate a post-import report for numeric values, missing values, trace/limit
   markers, unknown provenance categories, duplicates, and rejected rows.

## Suggested first nutrient set

The smallest useful set is:

- energy in kcal
- protein
- fat
- available carbohydrate
- total fiber

A still compact health-oriented set adds:

- total sugar
- saturated fatty acids
- sodium, with salt derived when needed
- potassium
- magnesium
- calcium
- iron

The schema can remain nutrient-generic even if only this subset is imported and
shown initially. Importing all 138 components should be a separate decision: it
would add nearly one million nutrient observations and many repeated reference
strings without immediate product value.

## Conclusion

Adopt BLS 4.x. The data model and importer must treat provenance, censored
values, preparation state, source version, and errata as first-class concerns.
With those conditions, the current issues are manageable and do not justify a
different primary source.
