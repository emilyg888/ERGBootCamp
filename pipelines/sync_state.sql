CREATE TABLE IF NOT EXISTS sync_state (
    source_name TEXT PRIMARY KEY,
    last_sync_ts TIMESTAMP
);