# Recipes and cooking log

What I cook, how the recipes evolve, and what went into each pot. Part of the
health API (`make api`, <http://127.0.0.1:8000/docs>), with its tables in the
`recipe` database schema.

## Model

| Concept | What it is | Example |
| --- | --- | --- |
| **Recipe** | A named line of versions | "Chicken curry" |
| **Version** | A fixed ingredient list, portions, steps as free text, a note on what changed, and a parent | "v3: less salt, v2 was too salty" |
| **Cook** | One time something was cooked: when, what actually went in, how many equal portions, how it turned out | "Mon 19:00, from v3, whole can of coconut milk, 5 portions, too watery" |

Ingredients are "this much of this", as in the log: a catalog source and an
amount in its unit (g or ml), optionally marked estimated. Nutrition is never
stored; it is the sources' values times the amounts, calculated when read.

**Versions never change their ingredients or portions.** An improvement is a
new version whose `parent` is the version it came from. Only the note and the
steps can be edited. Cooks and old meals therefore keep pointing at exactly
what was cooked.

**A cook records what really went into the pot**, which often differs from the
version: the whole can, both chicken breasts. Its nutrition comes from that
list, and `changes` lists every food whose amount differs from the version. The
cook's note says how it turned out. When a cook worked out, `from_cook` saves
it as the next version, so the history of versions holds deliberate
improvements and the cooking log holds reality.

**Forks**: a version whose parent belongs to another recipe, e.g. "Mango ice
cream" v1 from "Ice cream" v2. A recipe lists the recipes forked from it.

**Improvised cooks** have no recipe: a name, portions, and ingredients. Saving
one as a new recipe (`from_cook`) links the cook to that recipe's version 1.

## Portions

The pot is split into equal portions; one portion is 1/`portions` of every
ingredient, so water lost while cooking does not matter. A version's portions
are the default for its cooks. `weight_g` stores the finished dish's weight
when weighed; it is informational for now.

Per portion, nutrition is the cook's (or version's) total divided by its
portions. A cook shows `portions_eaten` from the log and `portions_left`.

## Eating from a cook

A meal item names a cook instead of a food: `{"cook": 12, "amount": 1}` is one
portion. Its nutrition is the cook's current total per portion, so correcting
the cook (ingredients or portions) also corrects the meals eaten from it. If
any ingredient lacks a nutrient, the item's value for it is unknown rather than
too low. An estimated ingredient makes the eaten portion count as estimated.

A cook that meals were logged from cannot be deleted; a recipe with cooks or
forks neither.

## Endpoints

Recipes:

- `GET /api/recipes?q=`: recipes, recently cooked or created first, with the
  latest version's nutrition per portion.
- `POST /api/recipes`: a recipe and its version 1. Ingredients and portions
  come from `items` and `portions`, otherwise from `from_cook`, otherwise from
  `forked_from: {"recipe": slug, "version": n}`. `?dry_run=true` stores nothing.
- `GET /api/recipes/{slug}`: every version (newest first) with ingredients,
  totals, and per-portion nutrition; forks; cooks.
- `PATCH /api/recipes/{slug}`: `name`, `note`. `DELETE` if never cooked or
  forked.
- `POST /api/recipes/{slug}/versions`: a new version with a `note`. Missing
  `items` and `portions` come from `from_cook`, then from the parent; missing
  `instructions` from the parent. `parent` (a version number) defaults to the
  cook's version, else the latest.
- `PATCH /api/recipes/{slug}/versions/{n}`: `note`, `instructions`.

Cooking log:

- `GET /api/cooks?recipe=&q=&since=&until=`: cooks newest first, by recipe,
  name words, or local days (inclusive). "The curry from Monday" is
  `?q=curry&since=2026-09-28&until=2026-09-28`.
- `POST /api/cooks`: `recipe` and optional `version` (default latest),
  `cooked_at` (default now, local time without an offset), `portions` (default
  the version's), `weight_g`, `note`, and `items` for what actually went in
  (default the version's ingredients; give the complete list when anything
  differs). Without a recipe, `name`, `portions`, and `items` are required.
- `GET /api/cooks/{id}`: ingredients, totals, per portion, `changes`, portions
  eaten and left.
- `PATCH /api/cooks/{id}`: any field; `items` replaces all ingredients.
  `DELETE` if nothing was eaten from it.

Invalid input returns `422` with `field`/`message` issues and writes nothing.

```json
POST /api/cooks
{
  "recipe": "chicken-curry",
  "cooked_at": "2026-09-28T19:00",
  "portions": 4,
  "note": "a bit watery, more coconut next time",
  "items": [
    {"food": "bls4-v4a6100", "amount": 520},
    {"food": "bls4-h154000", "amount": 400},
    {"food": "bls4-c352000", "amount": 250}
  ]
}
```

## Not built

- Recipes as ingredients of other recipes (an ice cream base shared by all
  flavors); for now a flavor is a fork of the base.
- Logging grams of a cook by its weight; meals log portions.
- Comparing two arbitrary versions; a cook compares with its version.
