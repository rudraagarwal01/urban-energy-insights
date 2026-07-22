from __future__ import annotations

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from app import routes_ingest


class FakeRedis:
    def __init__(self) -> None:
        self.published = 0

    def xadd(self, name: str, fields: dict[str, str]) -> str:
        self.published += 1
        return "1-0"


def test_ingest_csv_and_skip_duplicates(client: TestClient, monkeypatch: MonkeyPatch) -> None:
    assert client.post("/buildings", json={"id": "b1", "name": "HQ Tower", "timezone": "UTC"}).status_code == 201

    fake_redis = FakeRedis()
    monkeypatch.setattr(routes_ingest, "get_redis", lambda: fake_redis)

    csv_content = "timestamp,kwh\n2026-02-01T00:00:00Z,10.5\n2026-02-01T00:00:00Z,10.5\n"
    response = client.post(
        "/ingest/csv?building_id=b1",
        files={"file": ("readings.csv", csv_content, "text/csv")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["inserted"] == 1
    assert data["duplicates"] == 1
    assert data["published_events"] == 1
    assert data["publish_failures"] == 0


def test_ingest_invalid_csv_rejected(client: TestClient) -> None:
    assert client.post("/buildings", json={"id": "b2", "name": "Annex", "timezone": "UTC"}).status_code == 201
    invalid = "time,value\n2026-02-01T00:00:00Z,10\n"
    response = client.post(
        "/ingest/csv?building_id=b2",
        files={"file": ("readings.csv", invalid, "text/csv")},
    )
    assert response.status_code == 400
