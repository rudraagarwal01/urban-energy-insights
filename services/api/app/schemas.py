from pydantic import BaseModel

class BuildingCreate(BaseModel):
    id: str
    name: str
    type: str | None = None
    timezone: str = "UTC"

class BuildingOut(BuildingCreate):
    pass
