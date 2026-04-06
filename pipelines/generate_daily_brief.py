"""
ERGBootCamp — generate_daily_brief.py

Generates the daily brief text and saves it as a dated file
in coaching/briefs/daily/. Called by the pipeline and by the launchd job.
"""

import json
import os
from datetime import datetime, UTC, date

from pipelines.config_loader import (
    DB_PATH, LM_MODEL, LM_MAX_TOKENS, ATHLETE, COACHING, BRIEFS_DIR,
    ROOT, get_lm_client,
)
from pipelines.coaching_memory import get_recent_tips, build_context_block, last_taper_flag
import duckdb


def get_yesterday_summary():
    con = duckdb.connect(DB_PATH)
    df = con.execute("""
    SELECT *
    FROM daily_metrics
    ORDER BY workout_date DESC
    LIMIT 1
    """).fetchdf()
    con.close()

    if df.empty:
        return None

    latest = df.iloc[-1]
    delta = latest["delta"]
    return {
        "date": str(latest["workout_date"]),
        "split": round(float(latest["avg_split_sec"]), 1),
        "delta": float(delta) if delta is not None else None,
        "rolling_split": round(float(latest["rolling_avg_split"]), 1),
        "duration_min": round(float(latest["duration_sec"]) / 60, 1),
        "distance_m": int(latest["distance_m"]),
        "weekly_load_min": round(float(latest["weekly_load_min"]), 1) if latest["weekly_load_min"] is not None else None,
        "fatigue_flag": latest["fatigue_flag"],
        "session_type": latest["session_type"],
        "trend": "improving" if delta is not None and delta < 0 else "declining",
    }


def load_garmin():
    try:
        with open(ROOT / "data" / "garmin_latest.json") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def format_split(sec):
    if sec is None:
        return "N/A"
    m = int(sec // 60)
    s = sec % 60
    return f"{m}:{s:04.1f}"


def generate_brief(summary, garmin=None):
    client = get_lm_client()
    recent_tips = get_recent_tips(5)
    context_block = build_context_block(recent_tips)
    taper_active = last_taper_flag()

    garmin_section = ""
    if garmin:
        garmin_section = f"""
Recovery signals (Garmin):
- Body Battery: {garmin.get('body_battery', '?')}/100
- HRV: {garmin.get('hrv_status', '?')}
- Sleep: {garmin.get('sleep_score', '?')}
- Resting HR: {garmin.get('resting_hr', '?')} bpm"""

    taper_note = (
        "NOTE: Yesterday was a planned RECOVERY row. "
        "Slower split is expected and should be praised, not flagged.\n"
        if taper_active else ""
    )

    prompt = f"""You are a supportive Concept2 rowing coach sending a morning brief.

Athlete: {ATHLETE['name']} | Competition in 7 months | Goal: {ATHLETE['goal']}
- Appropriate stroke rate for steady state: 18-22 spm (never recommend above 24 for easy rows)
- Never recommend a target split slower than 2:30/500m — athlete is capable of 2:20 at threshold
{taper_note}
Recent coaching context:
{context_block}

Yesterday's session:
- Split: {format_split(summary['split'])} /500m (delta: {summary['delta']:+.1f}s)
- Distance: {summary['distance_m']}m in {summary['duration_min']} min
- Session type: {summary['session_type']} | Fatigue: {summary['fatigue_flag']}
- Weekly load: {summary['weekly_load_min']} min | Trend: {summary['trend']}
{garmin_section}

Write a morning brief (200 words max). Format:
*Good morning [name]!* (emoji)

*Yesterday:* 1-2 sentences on what happened

*Today's session:* specific prescription (distance, split, rate)

*Focus cue:* one technical reminder

*Motivation:* one short encouraging line related to their 7-month journey

Use bold (*text*) sparingly. Friendly, coach tone. Be specific."""

    response = client.chat.completions.create(
        model=LM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300,
        temperature=0.75,
    )

    return response.choices[0].message.content.strip()


def save_brief(brief_text: str) -> str:
    today = date.today().isoformat()
    path = BRIEFS_DIR / f"{today}.txt"
    path.write_text(brief_text)

    # also write latest.txt for easy access
    latest = BRIEFS_DIR / "latest.txt"
    latest.write_text(brief_text)

    return str(path)


def main():
    print("ERGBootCamp - generating daily brief...")

    summary = get_yesterday_summary()
    if summary is None:
        print("No data available")
        return

    garmin = load_garmin()

    brief = generate_brief(summary, garmin)
    path = save_brief(brief)

    print(f"Brief saved -> {path}")
    print("\n=== DAILY BRIEF ===")
    print(brief)
    return brief


if __name__ == "__main__":
    main()
