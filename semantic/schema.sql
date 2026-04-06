-- ERGBootCamp — Semantic Layer: Schema Definitions
-- Single source of truth for all raw table DDL.
-- Python pipelines also contain these DDL statements for runtime bootstrapping;
-- keep both in sync when making changes.

-- Source: pipelines/pull_concept2.py
CREATE TABLE IF NOT EXISTS workout_sessions (
    workout_id    TEXT PRIMARY KEY,
    workout_date  TIMESTAMP,
    distance_m    INTEGER,
    duration_sec  INTEGER,
    avg_split_sec REAL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP
);

-- Source: pipelines/pull_concept2.py
CREATE TABLE IF NOT EXISTS workout_intervals (
    interval_id       TEXT PRIMARY KEY,
    workout_id        TEXT,
    interval_index    INTEGER,
    work_duration_sec REAL,
    rest_duration_sec REAL,
    distance_m        INTEGER,
    split_sec         REAL,
    spm               INTEGER,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Source: pipelines/pull_concept2.py
CREATE TABLE IF NOT EXISTS sync_state (
    source_name  TEXT PRIMARY KEY,
    last_sync_ts TIMESTAMP
);

-- Source: pipelines/import_garmin.py
CREATE TABLE IF NOT EXISTS garmin_daily (
    record_date   DATE PRIMARY KEY,
    body_battery  INTEGER,
    hrv_status    TEXT,
    sleep_score   INTEGER,
    resting_hr    INTEGER,
    stress        INTEGER,
    readiness     INTEGER,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Source: pipelines/coaching_memory.py
CREATE TABLE IF NOT EXISTS coaching_tips (
    tip_id       TEXT PRIMARY KEY,
    created_at   TIMESTAMP NOT NULL,
    session_date TEXT,
    author       TEXT NOT NULL,          -- 'coach' | 'athlete'
    tip_text     TEXT NOT NULL,
    tag          TEXT,                   -- recovery|hard|race|technical|nutrition|performance
    session_type TEXT,                   -- declared intent for NEXT session
    expect_taper BOOLEAN DEFAULT FALSE   -- TRUE when next session is flagged as recovery
);
