import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app.db import get_db
from app.models import EnergyReading, Building
from app.redis_client import get_redis

router = APIRouter(prefix="/ingest", tags=["ingest"])

@router.post("/csv")
async def ingest_csv(
    building_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    building = db.get(Building, building_id)
    if not building:
        raise HTTPException(status_code=404, detail="Building not found")

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    content = await file.read()
    reader = csv.DictReader(io.StringIO(content.decode("utf-8")))

    if "timestamp" not in reader.fieldnames or "kwh" not in reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV must contain timestamp,kwh columns")

    redis = get_redis()
    inserted = 0

    for row in reader:
        try:
            ts_raw = row["timestamp"].strip()
            if ts_raw.endswith("Z"):
                ts_raw = ts_raw[:-1] + "+00:00"
            ts = datetime.fromisoformat(ts_raw)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)

            kwh = float(row["kwh"])
        except Exception:
            raise HTTPException(status_code=400, detail=f"Invalid row: {row}")

        stmt = (
            insert(EnergyReading)
            .values(
                building_id=building_id,
                ts=ts,
                kwh=kwh,
                source="csv",
            )
            .on_conflict_do_nothing(index_elements=["building_id", "ts"])
        )

        result = db.execute(stmt)
        db.commit()

        if result.rowcount == 1:
            inserted += 1
            redis.xadd(
                "energy_events",
                {"building_id": building_id, "timestamp": ts.isoformat()},
            )

    return {"inserted": inserted}
