CREATE TABLE IF NOT EXISTS workout_intervals (
    interval_id TEXT PRIMARY KEY,
    workout_id TEXT,
    interval_index INTEGER,
    work_duration_sec INTEGER,
    rest_duration_sec INTEGER,
    distance_m INTEGER,
    split_sec REAL,
    spm REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);