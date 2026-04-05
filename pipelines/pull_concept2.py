"""
ERGBootCamp — pull_concept2.py
Syncs workouts from the Concept2 logbook API into DuckDB.
Re-uses original logic; updated to use config_loader.
"""

import os
from datetime import datetime, timedelta, UTC
import requests
import duckdb

from pipelines.config_loader import C2_API_TOKEN, C2_API_URL, C2_REPLAY_DAYS, DB_PATH


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return duckdb.connect(DB_PATH)


def ensure_tables(con):
    con.execute("""
    CREATE TABLE IF NOT EXISTS workout_sessions (
        workout_id    TEXT PRIMARY KEY,
        workout_date  TIMESTAMP,
        distance_m    INTEGER,
        duration_sec  INTEGER,
        avg_split_sec REAL,
        created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at    TIMESTAMP
    )
    """)
    con.execute("""
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
    )
    """)
    con.execute("""
    CREATE TABLE IF NOT EXISTS sync_state (
        source_name  TEXT PRIMARY KEY,
        last_sync_ts TIMESTAMP
    )
    """)


def get_last_sync(con):
    row = con.execute("""
        SELECT last_sync_ts FROM sync_state WHERE source_name = 'concept2'
    """).fetchone()
    return row[0] if row else None


def compute_fetch_start(last_sync):
    if not last_sync:
        return None
    if last_sync.tzinfo is None:
        last_sync = last_sync.replace(tzinfo=UTC)
    return last_sync - timedelta(days=C2_REPLAY_DAYS)


def fetch_workouts():
    if not C2_API_TOKEN:
        raise ValueError("Missing C2_API_TOKEN in config/.env")
    headers = {"Authorization": f"Bearer {C2_API_TOKEN}"}
    r = requests.get(C2_API_URL, headers=headers)
    r.raise_for_status()
    data = r.json().get("data", [])
    print(f"Fetched {len(data)} workouts from Concept2 API")
    return data


def parse_date(date_str):
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.astimezone(UTC)
    except Exception:
        return None


def filter_by_incremental(rows, fetch_start):
    if not fetch_start:
        return rows
    filtered = [r for r in rows if (dt := parse_date(r.get("date"))) and dt >= fetch_start]
    print(f"Filtered to {len(filtered)} workouts (incremental window)")
    return filtered


def transform(row):
    workout_id = str(row.get("id"))
    date = parse_date(row.get("date"))
    distance = row.get("distance")
    duration = row.get("time") / 10  # tenths of seconds → seconds
    avg_split = (duration / (distance / 500)) if distance and duration and distance > 0 else None
    return (workout_id, date, distance, int(duration), avg_split, datetime.now(UTC))


def upsert_workouts(con, records):
    if not records:
        return
    con.executemany("""
    INSERT OR REPLACE INTO workout_sessions
        (workout_id, workout_date, distance_m, duration_sec, avg_split_sec, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
    """, records)
    print(f"Upserted {len(records)} workouts")


def extract_intervals(workout_id, row):
    records = []
    for i, interval in enumerate(row.get("intervals", [])):
        distance = interval.get("distance")
        duration = interval.get("time")
        spm = interval.get("spm")
        split = (duration / (distance / 500)) if distance and duration and distance > 0 else None
        records.append((f"{workout_id}_{i}", workout_id, i, duration, None, distance, split, spm))
    return records


def upsert_intervals(con, records):
    if not records:
        return
    con.executemany("""
    INSERT OR REPLACE INTO workout_intervals
        (interval_id, workout_id, interval_index, work_duration_sec,
         rest_duration_sec, distance_m, split_sec, spm, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, records)


def update_sync_state(con):
    now = datetime.now(UTC)
    con.execute("""
    INSERT INTO sync_state (source_name, last_sync_ts) VALUES ('concept2', ?)
    ON CONFLICT (source_name) DO UPDATE SET last_sync_ts = excluded.last_sync_ts
    """, (now,))
    print(f"Sync state updated → {now}")


def main():
    print("ERGBootCamp — syncing Concept2 workouts...")
    con = get_connection()
    ensure_tables(con)

    last_sync = get_last_sync(con)
    fetch_start = compute_fetch_start(last_sync)
    print(f"Last sync: {last_sync} | Fetch start: {fetch_start}")

    raw = fetch_workouts()
    filtered = filter_by_incremental(raw, fetch_start)

    records, all_intervals = [], []
    for r in filtered:
        rec = transform(r)
        records.append(rec)
        all_intervals.extend(extract_intervals(rec[0], r))

    upsert_workouts(con, records)
    upsert_intervals(con, all_intervals)
    update_sync_state(con)
    con.close()
    print("Sync complete ✅")


if __name__ == "__main__":
    main()
