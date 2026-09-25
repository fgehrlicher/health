# Epic 01 — PostgreSQL food-data foundation

**Status:** Complete

Implemented by the base schema and tooling documented in
[Food catalog database](../database.md).

## Outcome

A developer can start PostgreSQL, initialize an empty database from one
pre-deployment base schema, and store sourced ingredient nutrition without
losing uncertainty or provenance.

## Scope

- reproducible local PostgreSQL startup and configuration
- a mutable base schema while no deployed database exists
- a documented boundary after which schema changes become migrations
- foods and their names or aliases
- nutrient definitions, units, and values based on a declared quantity
- external dataset identities, versions, and source references
- a distinction between missing, zero, measured, and calculated values where
  the source provides it
- database constraints for the invariants already known
- a very small fixture used to exercise the schema and queries

## Acceptance criteria

- An empty database can be initialized to the current schema with one
  documented command.
- Bootstrapping an initialized database is safe, and schema status is
  inspectable.
- A representative raw fruit, grain, and legume can be stored with selected
  nutrients per 100 g.
- Each value can be traced to a source record and dataset version.
- The same external source record cannot be accidentally imported twice.
- Missing nutrient data is observably different from a measured or logical
  zero.
- A simple query returns the selected health-focused nutrients for a food.

## Not in this epic

The production dataset import, recipe data, consumption tracking, and agent
integration. A migration history starts only after the first deployment.
