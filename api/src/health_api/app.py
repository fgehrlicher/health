"""The health API: one backend for the catalog, the log, and the browser UI."""

from pathlib import Path

import psycopg
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from health_api.catalog.routes import router as catalog_router
from health_api.log.routes import router as log_router

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Health API", version="0.1.0")
app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")
app.include_router(catalog_router)
app.include_router(log_router)


@app.exception_handler(psycopg.OperationalError)
def database_unavailable(_request, _error):
    return JSONResponse(status_code=503, content={"detail": "Database is unavailable"})


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
