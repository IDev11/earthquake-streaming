import json
import os
import time
from datetime import datetime, timezone

import requests
from kafka import KafkaProducer

USGS_URL = os.environ.get(
    "USGS_FEED_URL",
    "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson",
)
KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
TOPIC = "raw.earthquakes"
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL_SECONDS", "60"))

# In-memory dedup: tracks event IDs seen this session so we don't re-publish
# events that are still in the USGS hourly window on the next poll.
seen_ids: set[str] = set()


def make_producer() -> KafkaProducer:
    for attempt in range(1, 13):
        try:
            return KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )
        except Exception as exc:
            print(f"[{attempt}/12] Kafka not ready: {exc}. Retrying in 5s...")
            time.sleep(5)
    raise RuntimeError("Could not connect to Kafka after 12 attempts.")


def parse_feature(feature: dict) -> dict:
    p = feature["properties"]
    lon, lat, depth = feature["geometry"]["coordinates"]
    return {
        "event_id":   feature["id"],
        "magnitude":  p.get("mag"),
        "place":      p.get("place"),
        "event_time": datetime.fromtimestamp(
            p["time"] / 1000, tz=timezone.utc
        ).isoformat(),
        "latitude":   lat,
        "longitude":  lon,
        "depth_km":   depth,
        "alert":      p.get("alert"),
        "tsunami":    bool(p.get("tsunami", 0)),
        "sig":        p.get("sig"),
        "mag_type":   p.get("magType"),
        "title":      p.get("title"),
    }


def main() -> None:
    producer = make_producer()
    print(f"Producer ready. Polling USGS every {POLL_INTERVAL}s → Kafka topic '{TOPIC}'")

    while True:
        try:
            resp = requests.get(USGS_URL, timeout=30)
            resp.raise_for_status()
            features = resp.json()["features"]

            new = 0
            for feature in features:
                eid = feature["id"]
                if eid in seen_ids:
                    continue
                seen_ids.add(eid)
                producer.send(TOPIC, value=parse_feature(feature))
                new += 1

            producer.flush()
            ts = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
            print(f"[{ts}] +{new} new events published. Session cache: {len(seen_ids)} IDs.")

        except requests.RequestException as exc:
            print(f"USGS fetch failed: {exc}")
        except Exception as exc:
            print(f"Unexpected error: {exc}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
