# Epic 02 — Rust food-ingestion CLI

**Status:** In progress — BLS 4.0 bulk import implemented; manual and agent input remain.

## Outcome

A Rust CLI provides the supported path for creating and updating foods, whether
the caller is a person, an agent, or a bulk importer.

## Scope

- manual creation of one food and its energy and macro values
- non-interactive, machine-readable input and output for agents
- bulk ingestion through a source-specific adapter
- validation before any database mutation
- a source identity for every accepted food record
- an import report with the source artifact checksum and rejected or nonnumeric
  source values; the source file must remain available for a rebuild
- transactional writes with clear partial-failure behavior
- idempotent re-imports using stable source identity
- dry-run and useful error reporting
- an import summary suitable for both humans and automation

The ingestion path should separate source parsing from the canonical domain
input. Adding another source later should not require rewriting database logic.

## Acceptance criteria

- A person can add a single ingredient without writing SQL.
- An agent can submit the same logical operation without parsing prose output.
- A representative source fixture can be validated and imported in bulk.
- Re-running an unchanged import creates no duplicates or unexplained changes.
- Invalid units, impossible values, and missing required identity are rejected
  before commit.
- A failed import reports what happened and does not leave silent partial data.
- Successful output includes created, updated, skipped, and rejected counts.

## Not in this epic

An agent itself, network APIs, scheduled synchronization, or importers for every
available dataset. Command names, interchange format, Rust libraries, and batch
size are selected during implementation.
