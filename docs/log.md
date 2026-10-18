# Consumption log

Records what was eaten, when, and how much. It is part of the health API
(`make api`, <http://127.0.0.1:8000/docs>) and stores its tables in the `log`
database schema.

## Model: meals of "this much of this"

A **meal** is one sitting: a time, an optional kind (`breakfast`, `lunch`,
`dinner`, or `snack`), an optional **note**, and **items**. The note holds raw
thoughts about the meal ("too salty, hungry again by 4 pm"), up to 2,000
characters, stored as written and never interpreted. An item is a catalog food and the amount
eaten, e.g. 400 g of the peach quark, portions of a cooked dish, or a stated
item (see [Items](#items)). A single snack is a meal with one item.

For catalog foods and cooked dishes, callers send no nutrition values and the
log stores none. Every such value is calculated when read: the referenced source's value times the amount, or for a
cooked dish its ingredients' total per portion. A
corrected catalog value therefore also corrects past days. A new recipe of a
product must be registered as a new source, not by changing the old one, so
meals keep pointing at what was actually eaten. Sources referenced by a meal
cannot be deleted. The one exception is a stated item: something without a
catalog product, whose values the person or the agent gives and the log
stores as given.

A meal's status follows from its items:

| Status | Items | Example |
| --- | --- | --- |
| `measured` | all read from a package or weighed | the whole 400 g cup |
| `estimated` | at least one with `estimated: true` | about 200 g of rice, guessed |
| `unknown` | none | "ate at the Italian place", no details yet |

Estimates still name catalog foods; BLS includes many prepared dishes such as
pizza, lasagne, and curries. If no catalog food fits, the person can state the
values they know, or the agent estimates them; an estimate is always marked
estimated, and a value nobody gives stays unknown.

## Items

An item is either portions of a cook from the
[cooking log](recipes.md#eating-from-a-cook), `{"cook": 12, "amount": 1}`, or a
food named by `food` (its slug) with either:

- `amount`: in the source's unit (g or ml), or
- `portion` and optional `count` (default 1): a named portion of that food,
  e.g. `{"portion": "Becher"}` for the 400 g cup or
  `{"portion": "Becher", "count": 0.5}` for half of it. Names are
  case-insensitive; unknown ones are rejected with the list of known portions.
  `count` without `portion` is rejected.

`estimated: true` marks a guessed amount. `source_id` picks a specific source;
by default the food's BLS 4.0 source is used, otherwise its newest one (the
current label version), the same source the catalog shows. A portion must be in
the source's unit; otherwise give an `amount` or pick a matching `source_id`.
One item may be at most 5,000 g or ml, and a meal at most 100 items.

A **stated item** is something without a catalog product, e.g. a canteen dish
or a bar whose wrapper is gone: `{"stated": {"name": "Protein bar",
"energy_kcal": 300, "protein_g": 30}}`. It takes a name, its kcal, and any of
`protein_g`, `fat_g`, `carbs_g` and `fiber_g`, plus `estimated` when the values
are rough, as they are when the food agent estimates them. Only the values given are stored; one left out is unknown, never
zero, and counts in `items_without_value`. It comes back as one `item` with the
`source_name` "Without product".

## Time and days

`eaten_at` defaults to now. A time without an offset is local time in
`HEALTH_TIMEZONE` (default `Europe/Berlin`). Times more than ten minutes in the
future are rejected. A day runs from local midnight to local midnight, including
23- and 25-hour days at daylight-saving changes.

## Endpoints

- `POST /api/log/meals`: log a meal; `?dry_run=true` returns it without storing.
- `GET /api/log/meals/{id}`: one meal with items and totals.
- `PATCH /api/log/meals/{id}`: change `eaten_at`, `kind`, `note` (`null` or
  blank clears them), or `items` (replaces all items, e.g. to fill in an
  unknown meal).
- `DELETE /api/log/meals/{id}`: delete a meal and its items.
- `GET /api/log/days/{YYYY-MM-DD}`: a day's meals and totals, whether it is
  marked incomplete, and the goals it is judged by (`daily_kcal_limit`,
  `kcal_tolerance`).
- `PUT /api/log/days/{YYYY-MM-DD}/incomplete` with `{"incomplete": true}`: mark
  a day as incomplete, or complete again with `false`.
- `GET /api/log/calendar?start=…&end=…`: kcal, the energy-split nutrients and
  meal counts per day, for every day with meals or marked incomplete, at most
  400 days, with the goals.
- `PUT /api/log/goals` with `{"daily_kcal_limit": 2200, "kcal_tolerance": 300}`.

Invalid requests return `422` with `field`/`message` issues and write nothing.
Changes and deletions are not versioned; `make db-backup` is the safety net.

```json
POST /api/log/meals
{
  "eaten_at": "2026-09-28T16:50:00",
  "kind": "snack",
  "note": "Straight from the fridge after the gym",
  "items": [{"food": "milbona-high-protein-quark-creme-pfirsich-maracuja", "portion": "Becher"}]
}
```

## Totals

Each meal and each day have, per nutrient column (the 14 label fields):

- `measured`: the sum over items not marked estimated;
- `estimated`: the sum over estimated items;
- `items_without_value`: items whose source lacks that nutrient, so a total is
  a lower bound when this is not 0.

A day also has `counts` of measured, estimated, and unknown meals. Together they
read as "1,840 kcal measured, 450 kcal estimated, 1 meal unknown" instead of one
number that hides how much is known.

## Goals and incomplete days

The goals are one row: a daily kcal limit (default 2,000) and a tolerance above
it (default 300). A day's kcal are its measured plus estimated energy. At or
under the limit it is within it; over it by no more than the tolerance it is
slightly over (yellow in the web app); beyond that it is over (red). The API
returns the numbers, and the web app and the food agent judge with this rule.

A day marked **incomplete** is missing meals. Its meals and totals stay as
they are, but it is not judged against the limit, and the stats leave it out.

## Not included

Totals cover the 14 label fields, not vitamins and minerals. There are no
"same as yesterday" copies. Recipes and meal prep are in the
[cooking log](recipes.md); agents use this API through the `health` CLI
([Agents](agents.md)).
