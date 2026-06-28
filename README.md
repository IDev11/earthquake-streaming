# Earthquake Streaming Pipeline

A real-time earthquake monitoring system that ingests live seismic data from USGS, streams it through Kafka and Spark, stores it in PostgreSQL, and visualises it on an interactive 3D globe dashboard.

## Architecture

```
USGS Feed (M2.5+)
      │
      ▼
┌─────────────┐     ┌───────────────┐     ┌─────────────┐     ┌─────────────┐
│  Producer   │────▶│     Kafka     │────▶│    Spark    │────▶│  PostgreSQL │
│  (Python)   │     │  (KRaft)      │     │  Streaming  │     │             │
└─────────────┘     └───────────────┘     └─────────────┘     └──────┬──────┘
                                                                       │
                                                               ┌───────▼──────┐
                                                               │   Streamlit  │
                                                               │  3D Dashboard│
                                                               └──────────────┘
```

## Stack

| Layer | Technology |
|---|---|
| Data source | USGS Earthquake Hazards Program (GeoJSON feed, M2.5+) |
| Message broker | Apache Kafka 3.7 (KRaft — no ZooKeeper) |
| Stream processing | Apache Spark 3.5.1 Structured Streaming |
| Storage | PostgreSQL 15 |
| Dashboard | Streamlit + pydeck (3D GlobeView) + Plotly |
| Orchestration | Docker Compose |

## Features

- **Live ingestion** — polls the USGS M2.5+ daily feed every 60 s, deduplicates by event ID
- **Streaming pipeline** — Kafka → Spark micro-batches (30 s trigger) → PostgreSQL with `ON CONFLICT DO NOTHING`
- **3D globe** — pydeck GlobeView with magnitude-scaled, colour-coded dots and a glow effect
- **Swarm detection** — configurable sidebar sliders: min events, cluster radius (km), time window (h)
- **KPI tiles** — total events, strongest magnitude, average magnitude, average depth, active swarms
- **Magnitude histogram** — Plotly chart showing the event distribution
- **Recent events table** — last 100 events with sortable columns
- **Auto-refresh** — configurable interval (30 s – 5 min)

## Magnitude colour scale

| Colour | Range |
|---|---|
| Green | M < 4 |
| Yellow | M 4–5 |
| Orange | M 5–6 |
| Red | M 6–7 |
| Purple | M 7+ |

## Project Structure

```
earthquake-streaming/
├── docker-compose.yml          # Full stack orchestration
├── sql/
│   └── init.sql                # raw.earthquakes schema + indexes
├── postgres/
│   └── Dockerfile              # Postgres image with init.sql baked in
├── producer/
│   ├── usgs_producer.py        # USGS poll → Kafka publisher
│   ├── requirements.txt
│   └── Dockerfile
├── spark/
│   ├── streaming_job.py        # Kafka consumer → Postgres writer
│   └── Dockerfile              # Spark 3.5.1 + Kafka/PG JARs pre-installed
└── streamlit/
    ├── app.py                  # Dashboard (globe, swarms, charts)
    ├── requirements.txt
    ├── Dockerfile
    └── .streamlit/
        └── config.toml         # Dark theme
```

## Getting Started

**Prerequisites:** Docker Desktop with at least 4 GB RAM allocated.

```bash
git clone https://github.com/IDev11/earthquake-streaming.git
cd earthquake-streaming
docker compose up -d
```

The first start downloads Spark's JAR dependencies — allow ~2 minutes before events appear.

Open **http://localhost:8501** to view the dashboard.

### Startup sequence

| Service | Depends on | Ready when |
|---|---|---|
| `postgres` | — | health check passes |
| `kafka` | — | health check passes |
| `kafka-init` | kafka healthy | topic `raw.earthquakes` created (exits 0) |
| `producer` | kafka-init done | starts polling USGS |
| `spark-job` | kafka-init done + postgres healthy | starts consuming |
| `streamlit` | postgres healthy | http://localhost:8501 |

### Stopping

```bash
docker compose down          # keep data volumes
docker compose down -v       # also wipe Postgres and Spark checkpoint
```

## Configuration

All tuneable parameters are exposed as environment variables in `docker-compose.yml`.

| Variable | Service | Default | Description |
|---|---|---|---|
| `POLL_INTERVAL_SECONDS` | producer | `60` | USGS poll frequency |
| `USGS_FEED_URL` | producer | daily M2.5+ feed | Override to hourly or weekly |
| `PG_HOST / PG_USER / PG_PASSWORD / PG_DB` | spark, streamlit | `quake` | Database connection |

## Data Model

```sql
CREATE TABLE raw.earthquakes (
    event_id    VARCHAR PRIMARY KEY,
    magnitude   FLOAT NOT NULL,
    place       VARCHAR,
    event_time  TIMESTAMPTZ NOT NULL,
    latitude    FLOAT NOT NULL,
    longitude   FLOAT NOT NULL,
    depth_km    FLOAT,
    alert       VARCHAR,
    tsunami     BOOLEAN DEFAULT FALSE,
    sig         INTEGER,
    mag_type    VARCHAR,
    title       VARCHAR,
    ingested_at TIMESTAMPTZ DEFAULT NOW()
);
```
