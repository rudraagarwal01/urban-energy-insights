from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db import get_db
from app.redis_client import get_redis
from app.schemas import IngestionResult
from app.services_ingestion import CsvValidationError, ingest_readings, parse_csv_readings

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/csv", response_model=IngestionResult)
async def ingest_csv(
    building_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> IngestionResult:
    filename = file.filename or ""
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    content = await file.read()
    try:
        readings = parse_csv_readings(content)
    except CsvValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        return ingest_readings(
            db=db,
            publisher=get_redis(),
            building_id=building_id,
            readings=readings,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
