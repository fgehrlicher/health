# Epic 01 — PostgreSQL food-data foundation

**Status:** Complete

Implemented by the base schema and tooling documented in
[Food catalog database](../database.md).

## Outcome

A developer can start PostgreSQL, initialize an empty database from one
pre-deployment base schema, and store sourced ingredient energy and macros.

## Scope

- reproducible local PostgreSQL startup and configuration
- a mutable base schema while no deployed database exists
- a documented boundary after which schema changes become migrations
- foods and their names or aliases
- energy and macro values with fixed units and a declared reference quantity
- source identities and references, including the chosen BLS version in a
  readable source name
- a nullable amount so unavailable values are not silently stored as zero
- database identities and the direct food/source link; content validation
  belongs to the ingestion CLI
- a very small fixture used to exercise the schema and queries

## Acceptance criteria

- An empty database can be initialized to the current schema with one
  documented command.
- Bootstrapping an initialized database is safe, and schema status is
  inspectable.
- A representative fruit, grain, and legume can be stored with energy and
  macros per 100 g.
- Each value can be traced to a source record identified as BLS 4.0.
- Source identifiers are retained so the ingestion CLI can detect duplicates
  before writing.
- Missing numeric data is observably different from zero.
- A simple query returns energy and macros for a food.

## Not in this epic

The production dataset import, recipe data, consumption tracking, and agent
integration. A migration history starts only after the first deployment.
