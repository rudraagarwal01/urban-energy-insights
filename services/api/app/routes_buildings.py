from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Building
from app.schemas import BuildingCreate, BuildingResponse

router = APIRouter(prefix="/buildings", tags=["buildings"])


@router.post("", response_model=BuildingResponse, status_code=status.HTTP_201_CREATED)
def create_building(payload: BuildingCreate, db: Session = Depends(get_db)) -> BuildingResponse:
    existing = db.get(Building, payload.id)
    if existing:
        raise HTTPException(status_code=409, detail="Building already exists")

    building = Building(
        id=payload.id,
        name=payload.name,
        type=payload.type,
        timezone=payload.timezone,
    )
    db.add(building)
    db.commit()
    db.refresh(building)
    return BuildingResponse.model_validate(building)


@router.get("", response_model=list[BuildingResponse])
def list_buildings(db: Session = Depends(get_db)) -> list[BuildingResponse]:
    buildings = db.execute(select(Building).order_by(Building.id)).scalars().all()
    return [BuildingResponse.model_validate(building) for building in buildings]


@router.get("/{building_id}", response_model=BuildingResponse)
def get_building(building_id: str, db: Session = Depends(get_db)) -> BuildingResponse:
    building = db.get(Building, building_id)
    if not building:
        raise HTTPException(status_code=404, detail="Building not found")
    return BuildingResponse.model_validate(building)
