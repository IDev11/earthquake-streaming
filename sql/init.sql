CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS analytics;

CREATE TABLE IF NOT EXISTS raw.earthquakes (
    event_id     VARCHAR PRIMARY KEY,
    magnitude    FLOAT    NOT NULL,
    place        VARCHAR,
    event_time   TIMESTAMPTZ NOT NULL,
    latitude     FLOAT    NOT NULL,
    longitude    FLOAT    NOT NULL,
    depth_km     FLOAT,
    alert        VARCHAR,
    tsunami      BOOLEAN  DEFAULT FALSE,
    sig          INTEGER,
    mag_type     VARCHAR,
    title        VARCHAR,
    ingested_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_eq_time ON raw.earthquakes (event_time DESC);
CREATE INDEX IF NOT EXISTS idx_eq_mag  ON raw.earthquakes (magnitude DESC);
CREATE INDEX IF NOT EXISTS idx_eq_loc  ON raw.earthquakes (latitude, longitude);
