# Health

A personal health observability system focused first on low-friction food,
nutrition, recipe, and meal-prep tracking.

- [Current state](docs/current-state.md): what exists today
- [Food catalog database](docs/database.md)
- [BLS 4.0 importer](docs/bls4-import.md)
- [Food catalog browser and API](docs/catalog.md)
- [Consumption log](docs/log.md)
- [Product and technical vision](docs/VISION.md)

Python tools share the root [`pyproject.toml`](pyproject.toml) and `uv.lock`.
Run the current importer from the repository root with
`uv run --locked bls4-import --dry-run`. Future importers and CLIs can be added
as workspace packages under `importers/` or `tools/` and declared as root
dependencies to make their commands available the same way.

To explore the catalog locally, run `make db-up` and `make catalog`, then open
<http://127.0.0.1:8000>.
