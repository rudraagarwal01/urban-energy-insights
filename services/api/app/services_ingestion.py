from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Building, EnergyReading
from app.redis_client import StreamPublisher
from app.schemas import IngestionResponse


class CsvValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedReading:
    ts: datetime
    kwh: float


def _parse_iso_ts(raw: str) -> datetime:
    value = raw.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    ts = datetime.fromisoformat(value)
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


def parse_csv_readings(content: bytes) -> list[ParsedReading]:
    try:
        decoded = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CsvValidationError("CSV must be utf-8 encoded") from exc

    reader = csv.DictReader(io.StringIO(decoded))
    if not reader.fieldnames:
        raise CsvValidationError("CSV is empty")
    if "timestamp" not in reader.fieldnames or "kwh" not in reader.fieldnames:
        raise CsvValidationError("CSV must contain timestamp,kwh columns")

    readings: list[ParsedReading] = []
    for row_idx, row in enumerate(reader, start=2):
        try:
            ts = _parse_iso_ts(row["timestamp"])
            kwh = float(row["kwh"])
        except Exception as exc:
            raise CsvValidationError(f"Invalid row at line {row_idx}: {row}") from exc
        if kwh < 0:
            raise CsvValidationError(f"Invalid row at line {row_idx}: kwh must be >= 0")
        readings.append(ParsedReading(ts=ts, kwh=kwh))
    return readings


def ingest_readings(
    db: Session,
    publisher: StreamPublisher,
    building_id: str,
    readings: list[ParsedReading],
) -> IngestionResult:
) -> IngestionResponse:
    building = db.execute(select(Building).where(Building.id == building_id)).scalar_one_or_none()
    if not building:
        raise LookupError("Building not found")

    inserted_ts: list[datetime] = []
    duplicates = 0

    for reading in readings:
        try:
            with db.begin_nested():
                db.add(
                    EnergyReading(
                        building_id=building_id,
                        ts=reading.ts,
                        kwh=reading.kwh,
                        source="csv",
                    )
                )
            inserted_ts.append(reading.ts)
        except IntegrityError:
            duplicates += 1

    db.commit()

    published_events = 0
    publish_failures = 0
    for ts in inserted_ts:
        try:
            publisher.xadd(
                "energy_events",
                {"building_id": building_id, "timestamp": ts.isoformat()},
            )
            published_events += 1
        except Exception:
            publish_failures += 1

    return IngestionResponse(
        inserted=len(inserted_ts),
        duplicates=duplicates,
        published_events=published_events,
        publish_failures=publish_failures,
    )
