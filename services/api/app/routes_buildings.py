from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Building
from app.schemas import BuildingCreate, BuildingOut

router = APIRouter(prefix="/buildings", tags=["buildings"])

@router.post("", response_model=BuildingOut)
def create_building(payload: BuildingCreate, db: Session = Depends(get_db)):
    existing = db.get(Building, payload.id)
    if existing:
        raise HTTPException(status_code=409, detail="Building already exists")

    b = Building(
        id=payload.id,
        name=payload.name,
        type=payload.type,
        timezone=payload.timezone,
    )
    db.add(b)
    db.commit()
    db.refresh(b)

    return BuildingOut(id=b.id, name=b.name, type=b.type, timezone=b.timezone)
