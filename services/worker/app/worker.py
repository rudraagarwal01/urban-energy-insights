import os
import time
import redis

STREAM = "energy_events"
GROUP = "energy_workers"
CONSUMER = os.getenv("CONSUMER_NAME", "worker-1")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

def ensure_group(r: redis.Redis):
    try:
        # mkstream=True creates the stream if it doesn't exist
        r.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
        print(f"created consumer group {GROUP} on {STREAM}")
    except redis.exceptions.ResponseError as e:
        # BUSYGROUP means it already exists
        if "BUSYGROUP" in str(e):
            print(f"consumer group {GROUP} already exists")
        else:
            raise

def main():
    r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    ensure_group(r)
    print("worker consuming...")

    while True:
        # Read 10 messages, block up to 5 seconds
        resp = r.xreadgroup(
            groupname=GROUP,
            consumername=CONSUMER,
            streams={STREAM: ">"},
            count=10,
            block=5000,
        )

        if not resp:
            continue

        for stream_name, messages in resp:
            for msg_id, fields in messages:
                building_id = fields.get("building_id")
                ts = fields.get("timestamp")

                print(f"processed event id={msg_id} building_id={building_id} timestamp={ts}")

                # ACK so it won’t be re-delivered
                r.xack(STREAM, GROUP, msg_id)

        time.sleep(0.1)

if __name__ == "__main__":
    main()
