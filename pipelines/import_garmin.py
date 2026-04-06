"""
ERGBootCamp — import_garmin.py

Pulls recovery signals from Garmin Connect and writes them to:
  data/garmin_latest.json   (for coaching pipeline)
  db/rowing.duckdb          (garmin_daily table for dashboard charts)

Requires: pip install garminconnect
"""

import json
import os
import sys
from datetime import date, datetime, UTC
import duckdb

from pipelines.config_loader import DB_PATH, GARMIN_EMAIL, GARMIN_PASSWORD, ROOT

GARMIN_CACHE = ROOT / "data" / "garmin_latest.json"

# DDL also defined in semantic/schema.sql — keep in sync
DDL_GARMIN = """
CREATE TABLE IF NOT EXISTS garmin_daily (
    record_date   DATE PRIMARY KEY,
    body_battery  INTEGER,
    hrv_status    TEXT,
    sleep_score   INTEGER,
    resting_hr    INTEGER,
    stress        INTEGER,
    readiness     INTEGER,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""


GARMIN_TOKEN_STORE = str(ROOT / ".garminconnect")


def fetch_garmin() -> dict:
    from garminconnect import Garmin

    if not GARMIN_EMAIL or not GARMIN_PASSWORD:
        raise ValueError("Missing GARMIN_EMAIL or GARMIN_PASSWORD in config/.env")

    api = Garmin(GARMIN_EMAIL, GARMIN_PASSWORD)
    try:
        api.login(GARMIN_TOKEN_STORE)
    except Exception:
        api.login()
        api.garth.save(GARMIN_TOKEN_STORE)

    today = date.today().isoformat()

    body_battery = None
    try:
        bb_data = api.get_body_battery(today)
        if bb_data:
            body_battery = bb_data[-1].get("charged", None)
    except Exception:
        pass

    hrv_status = None
    try:
        hrv_data = api.get_hrv_data(today)
        hrv_status = hrv_data.get("hrvSummary", {}).get("status", None)
    except Exception:
        pass

    sleep_score = None
    try:
        sleep = api.get_sleep_data(today)
        sleep_score = sleep.get("dailySleepDTO", {}).get("sleepScores", {}).get("overall", {}).get("value", None)
    except Exception:
        pass

    resting_hr = None
    try:
        hr_data = api.get_rhr_day(today)
        resting_hr = hr_data.get("allMetrics", {}).get("metricsMap", {}).get(
            "WELLNESS_RESTING_HEART_RATE", [{}]
        )[0].get("value", None)
    except Exception:
        pass

    stress = None
    try:
        stress_data = api.get_stress_data(today)
        stress = stress_data.get("overallStressLevel", None)
    except Exception:
        pass

    readiness = None
    try:
        ready = api.get_training_readiness(today)
        if ready:
            readiness = ready[0].get("score", None)
    except Exception:
        pass

    return {
        "date": today,
        "body_battery": body_battery,
        "hrv_status": hrv_status,
        "sleep_score": sleep_score,
        "resting_hr": resting_hr,
        "stress": stress,
        "readiness": readiness,
        "fetched_at": datetime.now(UTC).isoformat(),
    }


def save_to_db(data: dict):
    con = duckdb.connect(DB_PATH)
    con.execute(DDL_GARMIN)
    con.execute("""
    INSERT OR REPLACE INTO garmin_daily
        (record_date, body_battery, hrv_status, sleep_score, resting_hr, stress, readiness)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        data["date"],
        data.get("body_battery"),
        data.get("hrv_status"),
        data.get("sleep_score"),
        data.get("resting_hr"),
        data.get("stress"),
        data.get("readiness"),
    ))
    con.close()


def main():
    print("ERGBootCamp - importing Garmin data...")

    data = fetch_garmin()

    os.makedirs(ROOT / "data", exist_ok=True)
    with open(GARMIN_CACHE, "w") as f:
        json.dump(data, f, indent=2)

    save_to_db(data)

    print(f"Garmin data saved -> {GARMIN_CACHE}")
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Garmin sync skipped: {e}")
        sys.exit(0)  # exit clean so pipeline continues
