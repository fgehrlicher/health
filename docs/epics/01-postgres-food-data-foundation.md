# Epic 01 — PostgreSQL food-data foundation

**Status:** Ready

## Outcome

A developer can start PostgreSQL, apply versioned migrations to an empty
database, and store sourced ingredient nutrition without losing uncertainty or
provenance.

## Scope

- reproducible local PostgreSQL startup and configuration
- a migration workflow for creating and evolving the schema
- foods and their names or aliases
- nutrient definitions, units, and values based on a declared quantity
- external dataset identities, versions, and source references
- a distinction between missing, zero, measured, and calculated values where
  the source provides it
- database constraints for the invariants already known
- a very small fixture used to exercise migrations and queries

## Acceptance criteria

- An empty database can be migrated to the current schema with one documented
  command.
- Applying migrations again is safe, and migration state is inspectable.
- A representative raw fruit, grain, and legume can be stored with selected
  nutrients per 100 g.
- Each value can be traced to a source record and dataset version.
- The same external source record cannot be accidentally imported twice.
- Missing nutrient data is observably different from a measured or logical
  zero.
- A simple query returns the selected health-focused nutrients for a food.

## Not in this epic

The production dataset import, recipe data, consumption tracking, and agent
integration. The migration library, exact table layout, and naming conventions
are decisions for implementation.
