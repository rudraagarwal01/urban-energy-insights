from fastapi import FastAPI
from app.routes_buildings import router as buildings_router
from app.routes_ingest import router as ingest_router

app = FastAPI(title="Urban Energy Insights API")

@app.get("/health")
def health():
    return {"status": "ok"}

app.include_router(buildings_router)
app.include_router(ingest_router)
