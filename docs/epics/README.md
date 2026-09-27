# Current delivery plan

The first milestone is a trustworthy catalog of unbranded ingredients in
PostgreSQL. Work outside that foundation is intentionally deferred.

## Current state

Completed:

1. [PostgreSQL food-data foundation](01-postgres-food-data-foundation.md)
2. [Research spike: ingredient data source](../spikes/01-ingredient-data-source/README.md)

In progress:

3. [Food ingestion](02-food-ingestion.md)

Next:

4. [Initial ingredient catalog](03-initial-ingredient-catalog.md) (BLS import complete; selection review open)

The BLS 4.0 importer now loads the full dataset, including generic prepared
dishes, and handles the known energy erratum. The local browser supports BLS
group filtering. Manual and agent ingestion are still open. Sources store the
EU nutrition-label fields and foods can have named portions, ready for label
photos; a narrower ingredient view can be decided later.

## Milestone complete when

- PostgreSQL can be started locally and built from an empty database using the
  base schema. After the first deployment, changes use versioned migrations.
- Source-specific importers and a future manual/agent entry path handle writes.
- A useful set of vegetables, fruit, grains, beans, and similar ingredients has
  been imported from a documented source.
- Every imported value is traceable to its named source (such as BLS 4.0).
- Missing energy or macro values remain null rather than silently becoming zero.

Implementation details that are not necessary for this milestone should be
chosen during the relevant epic, not fixed here.
