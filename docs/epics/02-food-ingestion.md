# Epic 02 — Food ingestion

**Status:** In progress — BLS 4.0 importer implemented; manual and agent input remain.

## Outcome

Source-specific importers and, later, a manual/agent entry path create and
update foods with validation before database writes.

## Scope

- manual creation of one food and its energy and macro values
- non-interactive, machine-readable input and output for agents
- bulk ingestion through a dedicated importer for each source
- validation before any database mutation
- a source identity for every accepted food record
- an import report with the source artifact checksum and rejected or nonnumeric
  source values; the source file must remain available for a rebuild
- transactional writes with clear partial-failure behavior
- idempotent re-imports using stable source identity
- dry-run and useful error reporting
- an import summary suitable for both humans and automation

The BLS 4.0 importer is a Python/uv project. Further sources should have their
own importers; shared code can be extracted when actual duplication appears.

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
available dataset. The manual/agent entry interface is selected when built.
