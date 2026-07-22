from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from app import routes_ingest


class FakeRedis:
    def xadd(self, name: str, fields: dict[str, str]) -> str:
        return "1-0"


def test_process_event_creates_spike_insight(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    assert client.post("/buildings", json={"id": "b3", "name": "Campus", "timezone": "UTC"}).status_code == 201
    monkeypatch.setattr(routes_ingest, "get_redis", lambda: FakeRedis())

    base_ts = datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc)
    rows = ["timestamp,kwh"]
    for i in range(6):
        rows.append(f"{(base_ts + timedelta(minutes=i * 10)).isoformat()},10.0")
    spike_ts = base_ts + timedelta(minutes=60)
    rows.append(f"{spike_ts.isoformat()},35.0")
    csv_content = "\n".join(rows) + "\n"

    ingest = client.post(
        "/ingest/csv?building_id=b3",
        files={"file": ("readings.csv", csv_content, "text/csv")},
    )
    assert ingest.status_code == 200

    process = client.post(
        "/internal/process-event",
        json={"building_id": "b3", "timestamp": spike_ts.isoformat()},
    )
    assert process.status_code == 200
    assert process.json()["insights_created"] >= 1

    insights = client.get("/buildings/b3/insights")
    assert insights.status_code == 200
    assert len(insights.json()) >= 1
