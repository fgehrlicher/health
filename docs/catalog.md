# Local food browser and API

The read-only browser is a sortable table of foods with energy, four macros,
and protein per 100 kcal. This last value is calculated as
`protein_g × 100 / energy_kcal`, not stored in the database. It is unknown
when protein or energy is missing or energy is zero.
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

Open <http://127.0.0.1:8000>. The server binds to `127.0.0.1` by default;
it has no login, so do not expose it to a public network. `DATABASE_URL`
overrides the local Compose database.

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
- `GET /api/foods/{slug}`: food details with all nutrition sources.
- `GET /docs`: interactive API documentation.

List results show one source per food: the requested source, otherwise BLS
4.0 if present, otherwise the first record. Values are never merged across
sources. Nutrition filters compare the displayed source's stated reference
basis. Unknown values do not match numeric filters. API decimals are strings
to preserve source precision.
The source response includes `group_code`; it is populated by the BLS importer
and can be `null` for a future non-BLS source.
