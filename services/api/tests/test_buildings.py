from __future__ import annotations

from fastapi.testclient import TestClient


def test_create_and_get_building(client: TestClient) -> None:
    payload = {"id": "b1", "name": "HQ Tower", "type": "office", "timezone": "UTC"}
    create_response = client.post("/buildings", json=payload)
    assert create_response.status_code == 201
    assert create_response.json()["id"] == "b1"

    get_response = client.get("/buildings/b1")
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "HQ Tower"


def test_duplicate_building_rejected(client: TestClient) -> None:
    payload = {"id": "b1", "name": "HQ Tower", "timezone": "UTC"}
    assert client.post("/buildings", json=payload).status_code == 201
    duplicate = client.post("/buildings", json=payload)
    assert duplicate.status_code == 409
