# Local food browser and API

The read-only browser is a sortable table of foods with energy, four macros,
and protein per 100 kcal. This last value is calculated as
`protein_g × 100 / energy_kcal`, not stored in the database. It is unknown
when protein or energy is missing or energy is zero. Food details add the
full label-style breakdown (kJ, saturated fat, sugars, salt, and more) and any
portions.
Search finds names, aliases, German BLS names, and BLS codes (see
[Search](#search)). Filters include BLS group, source, food type, preparation,
protein, fiber, and energy. Click a row
to see all source records and a small diagram of grams in 100 g (where the
source basis is 100 g). A dash means unknown, not zero.
BLS codes remain searchable and appear in food details, but are not a table column.

Click a column header to sort the full filtered result set, not just the
current page. The table uses a locally bundled [Tabulator 6.5.3](https://tabulator.info/)
for sorting, paging, column resizing, and responsive collapsed rows. No CDN or
frontend build is required at runtime. Its MIT license is in the bundled
`static/vendor/tabulator-6.5.3/LICENSE` file.

## Run

```sh
make db-up
uv run --locked bls4-import
make catalog
```

Open <http://127.0.0.1:8000>. The server binds to `127.0.0.1` by default.
It has no login and its API can add foods, so do not expose it to a public
network. `DATABASE_URL` overrides the local Compose database.

## Search

Every query word must match a word in a food's names, BLS code, brand, or
barcode: exactly, as a prefix (`banan`), as a plural or compound part
(`almonds`, `hähnchenbrust`), or, for words without digits, by trigram
similarity (`brocoli`). Adjacent words are also matched joined, so
`haferflocken` finds "Hafer Flocken". Word order does not matter.

Results are sorted by relevance unless you click a column. Ranking favors foods
whose head phrase, the name part before the first comma, the query covers:
BLS names put the food first and qualifiers after it ("Whole milk, fresh,
3.5 % fat"). Unprepared BLS foods (code ending in `00`) rank higher, composite
dishes (groups X and Y) lower.

Search reads two materialized views, `food_search_terms` and
`food_search_vocabulary`, built from `foods` and `food_sources`. The BLS
importer refreshes them; any other write path must too (see
[database](database.md#search-views)).

`make search-eval` measures ranking against
[`tools/catalog/search_eval.tsv`](../tools/catalog/search_eval.tsv): realistic
queries with their acceptable BLS codes. With the full BLS import it finds the
expected food first for 58% of queries and within the top five for 80%
(substring search: 15% and 27%). Most misses are synonyms that do not occur in
BLS names, such as `porridge` or `ground beef`. Add a case before changing the
ranking, and keep the thresholds in `test_search_quality_on_full_bls_catalog`
in step.

## API

- `GET /api/foods`: paginated list. Parameters: `q`, `group`, `kind`,
  `preparation_state`, `source_name`, `min_protein`, `min_protein_density`,
  `min_fiber`, `max_energy`,
  `sort` (default `relevance`; alphabetical without `q`), `limit`, `offset`.
- `GET /api/foods/facets`: counts and available filter values, including BLS
  group names and counts.
- `GET /api/foods/{slug}`: food details with all nutrition sources and portions.
- `GET /api/foods/barcode/{barcode}`: exact barcode lookup; `404` if unknown,
  `422` for an invalid barcode.
- `POST /api/foods`: register a branded food (see below); `?dry_run=true`
  validates without writing.
- `GET /docs`: interactive API documentation, including the request schema.

List results show one source per food: the requested source, otherwise BLS
4.0 if present, otherwise the first record. Values are never merged across
sources. Nutrition filters compare the displayed source's stated reference
basis. Unknown values do not match numeric filters. API decimals are strings
to preserve source precision.
The source response includes `group_code`; it is populated by the BLS importer
and can be `null` for a future non-BLS source.

## Registering branded foods

Agents add products from label photos or product databases. The expected flow:

1. Look up the barcode: `GET /api/foods/barcode/4335619151215`. If found, use
   that food.
2. Otherwise search by name to avoid a duplicate without a barcode.
3. `POST /api/foods?dry_run=true` with the values as printed, per 100 g or
   100 ml as sold. Fix errors by re-reading the photo or asking the person;
   confirm warnings with them.
4. `POST /api/foods` to write. The response contains the new food.

```json
{
  "name": "High Protein Quark-Creme Pfirsich-Maracuja",
  "brand": "Milbona",
  "barcode": "4335619151215",
  "source_name": "Product label",
  "nutrition": {
    "energy_kj": 287, "energy_kcal": 68, "fat_g": 0.4, "saturated_fat_g": 0.3,
    "carbs_g": 3.5, "sugars_g": 3.0, "fiber_g": 0.2, "protein_g": 12.4,
    "salt_g": 0.13
  },
  "portions": [
    {"name": "Portion", "kind": "serving", "quantity": 200, "unit": "g"},
    {"name": "Becher", "kind": "package", "quantity": 400, "unit": "g"}
  ]
}
```

Required are name, energy in kcal, fat, carbs, and protein. `reference_quantity`
and `reference_unit` default to 100 g. Write a label's "<0,5 g" as `0.5` and
list the column in `nutrition.upper_bounds`.

Validation rejects the submission with `422` and a list of `field`/`message`
issues, writing nothing, when:

- the barcode is not 8, 12, or 13 digits, its check digit is wrong, or it is a
  store-internal code starting with 2 (e.g. weighed goods);
- an amount exceeds the reference quantity, or energy exceeds 900 kcal per 100;
- "davon" rows add up to more than their parent row (0.2 g rounding allowed);
- kJ and kcal disagree by more than 5%;
- energy calculated from the macros with EU factors differs from the stated
  kcal by more than 20% (and 10 kcal). A misread digit usually shows here.

Warnings do not block writing: kcal differs from the macros by more than 8%, a
mandatory label row (kJ, saturated fat, sugars, salt) is missing, or there is no
barcode. An existing barcode returns `409` with the existing food's `slug`.
New foods get `kind` `branded` and a slug from brand and name; the source uses
the barcode as `external_id`. Search views are refreshed on every write.
