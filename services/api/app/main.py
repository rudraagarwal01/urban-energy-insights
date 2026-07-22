from __future__ import annotations

from fastapi import FastAPI

from app.routes_buildings import router as buildings_router
from app.routes_ingest import router as ingest_router
from app.routes_insights import router as insights_router

app = FastAPI(title="Urban Energy Insights API", version="1.0.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(buildings_router)
app.include_router(ingest_router)
app.include_router(insights_router)
