# Current delivery plan

The first milestone is a trustworthy catalog of unbranded ingredients in
PostgreSQL. Work outside that foundation is intentionally deferred.

## Current state

Completed:

1. [PostgreSQL food-data foundation](01-postgres-food-data-foundation.md)
2. [Research spike: ingredient data source](../spikes/01-ingredient-data-source/README.md)

In progress:

3. [Rust food-ingestion CLI](02-rust-food-ingestion-cli.md)

After the CLI:

4. [Initial ingredient catalog](03-initial-ingredient-catalog.md)

The BLS 4.0 importer now handles a reviewed code list, including the known
energy erratum. Manual and agent ingestion are still open. V1 stores energy
and macros; expanding the ingredient catalog requires its own inclusion review.

## Milestone complete when

- PostgreSQL can be started locally and built from an empty database using the
  base schema. After the first deployment, changes use versioned migrations.
- The Rust CLI is the supported write path for manual, agent, and bulk input.
- A useful set of vegetables, fruit, grains, beans, and similar ingredients has
  been imported from a documented source.
- Every imported value is traceable to its named source (such as BLS 4.0).
- Missing energy or macro values remain null rather than silently becoming zero.

Implementation details that are not necessary for this milestone should be
chosen during the relevant epic, not fixed here.
