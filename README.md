# Health

A personal health observability system focused first on low-friction food,
nutrition, recipe, and meal-prep tracking.

- [Current state](docs/current-state.md): what exists today
- [Food catalog database](docs/database.md)
- [BLS 4.0 importer](docs/bls4-import.md)
- [Web frontend](docs/web.md)
- [Food catalog API](docs/catalog.md)
- [Consumption log](docs/log.md)
- [Product and technical vision](docs/VISION.md)

Python packages share the root [`pyproject.toml`](pyproject.toml) and `uv.lock`:
[`api/`](api/) is the single backend (catalog and consumption log), and each
data source has its own importer under `importers/`. The web frontend in
[`web/`](web/) is TypeScript with TanStack Start and shadcn/ui, managed with pnpm. Run the BLS importer
from the repository root with `uv run --locked bls4-import --dry-run`.

To run everything locally, use `make db-up`, `make api`, and `make web`, then
open <http://localhost:3000>.
