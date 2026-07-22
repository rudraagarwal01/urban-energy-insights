from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator


class BuildingCreate(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    type: str | None = Field(default=None, max_length=100)
    timezone: str = Field(default="UTC", min_length=1, max_length=64)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Invalid IANA timezone") from exc
        return value


class BuildingResponse(BuildingCreate):
    created_at: datetime

    model_config = {"from_attributes": True}


class IngestionResponse(BaseModel):
    inserted: int
    duplicates: int
    published_events: int
    publish_failures: int


class InsightResponse(BaseModel):
    id: int
    building_id: str
    start_ts: datetime
    end_ts: datetime
    category: str
    severity: float
    explanation: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class InsightStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        allowed = {"open", "ack", "resolved"}
        if value not in allowed:
            raise ValueError(f"status must be one of: {', '.join(sorted(allowed))}")
        return value


class ProcessEventRequest(BaseModel):
    building_id: str = Field(min_length=1, max_length=64)
    timestamp: datetime


class ProcessEventResponse(BaseModel):
    insights_created: int
