# Health

A personal health observability system focused first on low-friction food,
nutrition, recipe, and meal-prep tracking.

- [Current state](docs/current-state.md): what exists today
- [Food catalog database](docs/database.md)
- [BLS 4.0 importer](docs/bls4-import.md)
- [Food catalog browser and API](docs/catalog.md)
- [Consumption log](docs/log.md)
- [Product and technical vision](docs/VISION.md)

Python packages share the root [`pyproject.toml`](pyproject.toml) and `uv.lock`:
[`api/`](api/) is the single backend (catalog, consumption log, browser UI), and
each data source has its own importer under `importers/`. Run the BLS importer
from the repository root with `uv run --locked bls4-import --dry-run`.

To run everything locally, use `make db-up` and `make api`, then open
<http://127.0.0.1:8000>.
