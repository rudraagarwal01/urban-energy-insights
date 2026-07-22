from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Insight
from app.schemas import InsightOut, InsightStatusUpdate, ProcessEventRequest
from app.services_insights import process_energy_event

router = APIRouter(tags=["insights"])


@router.patch("/insights/{insight_id}", response_model=InsightOut)
def update_insight_status(
    insight_id: int,
    payload: InsightStatusUpdate,
    db: Session = Depends(get_db),
) -> InsightOut:
    insight = db.get(Insight, insight_id)
    if insight is None:
        raise HTTPException(status_code=404, detail="Insight not found")
    insight.status = payload.status
    db.commit()
    db.refresh(insight)
    return InsightOut.model_validate(insight)


@router.post("/internal/process-event")
def process_event(
    payload: ProcessEventRequest,
    db: Session = Depends(get_db),
    x_internal_token: str | None = Header(default=None),
) -> dict[str, int]:
    settings = get_settings()
    if settings.internal_api_token and x_internal_token != settings.internal_api_token:
        raise HTTPException(status_code=401, detail="Unauthorized internal caller")
    try:
        created = process_energy_event(db, payload.building_id, payload.timestamp)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"insights_created": created}


@router.get("/insights", response_model=list[InsightOut])
def list_insights(
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[InsightOut]:
    insights = db.execute(select(Insight).limit(limit)).scalars().all()
    return [InsightOut.model_validate(item) for item in insights]
