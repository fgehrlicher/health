"""The health API: one backend for the catalog, recipes, and the consumption log.

The web frontend in web/ and agents use it over HTTP; it serves no pages.
"""

import psycopg
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from health_api.catalog.routes import router as catalog_router
from health_api.log.routes import router as log_router
from health_api.recipes.routes import router as recipes_router

app = FastAPI(title="Health API", version="0.1.0")
app.include_router(catalog_router)
app.include_router(log_router)
app.include_router(recipes_router)


@app.exception_handler(psycopg.OperationalError)
def database_unavailable(_request, _error):
    return JSONResponse(status_code=503, content={"detail": "Database is unavailable"})
