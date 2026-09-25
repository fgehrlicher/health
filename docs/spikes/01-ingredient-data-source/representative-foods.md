# Representative BLS ingredient values

This sample was extracted from the inspected BLS 4.0 workbook. Values are per
100 g edible portion and retain the source precision. It is research evidence,
not yet an ingestion fixture or a product nutrient shortlist.

| BLS code | Food | kcal | Protein g | Fat g | Carbohydrate g | Fiber g | Sugar g | Sodium mg | Potassium mg | Iron mg |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `F110100` | Apfel roh | 58 | 0.424 | 0.5 | 11.7 | 2.275 | 10.487 | 1 | 111 | 0.1 |
| `G312100` | Broccoli roh | 35 | 3.622 | 0.5967 | 2.3 | 3 | 1.38 | 26 | 396 | 0.978 |
| `C352000` | Reis poliert, roh | 351 | 7.931 | 0.62 | 77.1 | 2.5 | 0.28 | 15.77 | 106.62 | 0.29149 |
| `C352032` | Reis poliert, gekocht | 117 | 3.3 | 0.35 | 24.8 | 0.61 | 0.1 | 9.77 | 31.63 | 0.14088 |
| `H725100` | Linse reif | 323 | 23.357 | 1.7 | 44.8 | 17.6 | 1.3 | 7 | 837 | 8.03 |
| `H730132` | Linse reif, gekocht | 119 | 9.083 | 0.7 | 15.5 | 7.23 | 0.5 | `<LOQ` | 211 | 2.12 |
| `G770400` | Kichererbse reif | 317 | 18.583 | 5.915 | 39.6 | 15.51 | 2.411 | 23 | 800 | 4.9 |
| `G770432` | Kichererbse reif, gekocht | 151 | 8.4 | 3 | 17.4 | 10.6 | 1.4 | 1 | 281 | 1.9 |
| `H480100` | Chia-Samen | 479 | 22.11 | 32.79 | 3.66 | 40.23 | 0.4732 | 0.3 | 716.6 | 7.5825 |
| `H120100` | Walnuss | 721 | 16.07 | 70.6 | 3 | 4.6 | 2.68 | `<LOD` | 444 | 2.78 |

The sample illustrates three important import requirements:

- preparation state materially changes the nutritional record
- source precision varies by food and nutrient
- non-numeric limit markers occur in otherwise numeric nutrient columns

Provenance also varies within a single food. For example, raw white rice uses
database-derived protein and fat but analyzed fiber, sodium, potassium, and iron.
Chia values in this sample are analytical. Several apple values aggregate
multiple literature sources.

Source and attribution: Max Rubner-Institut (2025),
*Bundeslebensmittelschlüssel (BLS), Version 4.0 — Deutsche Nährstoffdatenbank*,
DOI [10.25826/Data20251217-134202-0](https://doi.org/10.25826/Data20251217-134202-0),
licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
