from __future__ import annotations

import json
import os
import time
from urllib import error, request

import redis

STREAM = "energy_events"
GROUP = "energy_workers"
CONSUMER = os.getenv("CONSUMER_NAME", "worker-1")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
API_BASE_URL = os.getenv("API_BASE_URL", "http://api:8000")
INTERNAL_API_TOKEN = os.getenv("INTERNAL_API_TOKEN")


def ensure_group(client: redis.Redis) -> None:
    try:
        client.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
        print(f"created consumer group {GROUP} on {STREAM}")
    except redis.exceptions.ResponseError as exc:
        if "BUSYGROUP" in str(exc):
            print(f"consumer group {GROUP} already exists")
            return
        raise


def process_event(building_id: str, timestamp: str) -> None:
    payload = json.dumps({"building_id": building_id, "timestamp": timestamp}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if INTERNAL_API_TOKEN:
        headers["x-internal-token"] = INTERNAL_API_TOKEN

    req = request.Request(
        url=f"{API_BASE_URL}/internal/process-event",
        data=payload,
        headers=headers,
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=15) as response:
            if response.status >= 300:
                raise RuntimeError(f"API returned status={response.status}")
    except error.URLError as exc:
        raise RuntimeError("Failed to call API for event processing") from exc


def main() -> None:
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    ensure_group(redis_client)
    print("worker consuming...")

    while True:
        events = redis_client.xreadgroup(
            groupname=GROUP,
            consumername=CONSUMER,
            streams={STREAM: ">"},
            count=10,
            block=5000,
        )
        if not events:
            continue

        for _, messages in events:
            for msg_id, fields in messages:
                building_id = fields.get("building_id")
                timestamp = fields.get("timestamp")
                if not building_id or not timestamp:
                    print(f"skipping malformed event id={msg_id} fields={fields}")
                    redis_client.xack(STREAM, GROUP, msg_id)
                    continue

                try:
                    process_event(building_id, timestamp)
                    redis_client.xack(STREAM, GROUP, msg_id)
                    print(f"processed event id={msg_id} building_id={building_id} timestamp={timestamp}")
                except Exception as exc:
                    # Keep message pending for redelivery and operator visibility.
                    print(f"failed processing id={msg_id}: {exc}")

        time.sleep(0.05)


if __name__ == "__main__":
    main()
