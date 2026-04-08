"""
ERGBootCamp — generate_weekly_plan.py

Runs every Sunday at 19:30 via launchd.
Aggregates the past 7 days of training data, calls the LLM to produce:
  1. A weekly summary insight (plain text)
  2. A 7-day plan for the coming week (structured JSON)

Output: data/snapshots/weekly_plan.json
"""

import json
import duckdb
from datetime import date, datetime, timedelta, UTC

from pipelines.config_loader import (
    DB_PATH, LM_MODEL, LM_MAX_TOKENS, LM_TEMPERATURE, ATHLETE,
    ROOT, get_lm_client, fmt_split,
)
from pipelines.coaching_memory import get_recent_tips, build_context_block


SNAPSHOT_PATH = ROOT / "data" / "snapshots" / "weekly_plan.json"

SESSION_TYPES = ["steady", "recovery", "interval", "threshold", "long", "rest"]


# ── data layer ───────────────────────────────────────────────────────────────

def _get_week_rows(week_start: date, week_end: date) -> list[dict]:
    """Return daily_metrics rows for a given Mon–Sun window."""
    con = duckdb.connect(DB_PATH)
    rows = con.execute("""
        SELECT workout_date, avg_split_sec, distance_m, duration_sec,
               session_type, fatigue_flag, weekly_load_min
        FROM daily_metrics
        WHERE CAST(workout_date AS DATE) >= ? AND CAST(workout_date AS DATE) <= ?
          AND avg_split_sec IS NOT NULL
        ORDER BY workout_date
    """, (str(week_start), str(week_end))).fetchall()
    con.close()
    return [
        {
            "date":            str(r[0]),
            "avg_split_sec":   float(r[1]),
            "distance_m":      int(r[2]),
            "duration_sec":    float(r[3]) if r[3] else 0,
            "session_type":    r[4] or "steady",
            "fatigue_flag":    bool(r[5]),
            "weekly_load_min": float(r[6]) if r[6] else 0,
        }
        for r in rows
    ]


def _aggregate(rows: list[dict]) -> dict:
    if not rows:
        return {}
    total_m        = sum(r["distance_m"] for r in rows)
    total_min      = sum(r["duration_sec"] for r in rows) / 60
    avg_split      = sum(r["avg_split_sec"] for r in rows) / len(rows)
    sessions       = len(rows)
    fatigue_days   = sum(1 for r in rows if r["fatigue_flag"])
    return {
        "sessions_completed":   sessions,
        "total_volume_m":       total_m,
        "total_volume_km":      round(total_m / 1000, 1),
        "total_duration_min":   round(total_min, 1),
        "avg_split_sec":        round(avg_split, 1),
        "avg_split_formatted":  fmt_split(avg_split),
        "fatigue_days":         fatigue_days,
    }


# ── LLM call ─────────────────────────────────────────────────────────────────

PLAN_SCHEMA = """
{
  "insight": "<2-3 sentences: what the week showed, one risk flag, one positive>",
  "next_week": [
    {
      "day":          "Mon",
      "date":         "YYYY-MM-DD",
      "session_type": "steady|recovery|interval|threshold|long|rest",
      "label":        "<short session label, e.g. '8km easy'>",
      "target_split": "<MM:SS or null for rest>",
      "duration_min": <integer or null>,
      "notes":        "<one coaching cue or null>"
    }
    // ... 7 entries Mon–Sun
  ]
}
"""


def generate_weekly_plan(
    this_week: dict,
    prev_week: dict,
    week_start: date,
) -> dict:
    client        = get_lm_client()
    recent_tips   = get_recent_tips(limit=3)
    context_block = build_context_block(recent_tips)
    next_monday   = week_start + timedelta(days=7)
    next_dates    = [(next_monday + timedelta(days=i)).isoformat() for i in range(7)]
    day_labels    = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    prev_block = ""
    if prev_week:
        prev_block = f"""
Previous week (for comparison):
- Volume: {prev_week.get('total_volume_km')} km over {prev_week.get('sessions_completed')} sessions
- Avg split: {prev_week.get('avg_split_formatted')}
- Total duration: {prev_week.get('total_duration_min')} min
"""

    prompt = f"""You are an expert Concept2 indoor rowing coach.
Athlete: height {ATHLETE['height_cm']}cm | goal: {ATHLETE['goal']} | competition: {ATHLETE['competition_date']}

SPLIT FORMAT RULES:
- ALL split targets MUST be in MM:SS/500m format (e.g. "2:45/500m"). Never raw seconds.
- For rest days, set target_split to null.

--- RECENT COACHING CONTEXT ---
{context_block}
--- END CONTEXT ---

This week's training summary:
- Sessions completed: {this_week.get('sessions_completed', 0)}
- Total volume: {this_week.get('total_volume_km', 0)} km
- Avg split: {this_week.get('avg_split_formatted', 'N/A')}
- Total duration: {this_week.get('total_duration_min', 0)} min
- Fatigue days flagged: {this_week.get('fatigue_days', 0)}
{prev_block}
Now produce:
1. A weekly insight (2-3 sentences): what the week showed, one risk, one positive.
2. A 7-day training plan for next week ({next_dates[0]} to {next_dates[6]}).
   - Progress the athlete sensibly from this week's load.
   - Include at least one rest day, one recovery row, one interval or threshold session.
   - All split targets must be achievable (reference avg split {this_week.get('avg_split_formatted', 'N/A')}).

Return ONLY valid JSON matching this exact schema — no prose outside the JSON:
{PLAN_SCHEMA}

Use these exact day/date values in next_week:
{json.dumps([{"day": d, "date": dt} for d, dt in zip(day_labels, next_dates)], indent=2)}
"""

    response = client.chat.completions.create(
        model=LM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000,   # weekly plan JSON needs more room than daily tips
        temperature=LM_TEMPERATURE,
    )
    raw = response.choices[0].message.content.strip()

    # Strip markdown code fences if the model wraps its JSON
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    return json.loads(raw)


# ── snapshot writer ───────────────────────────────────────────────────────────

def save_snapshot(this_week: dict, prev_week: dict, plan: dict, week_start: date):
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at":  datetime.now(UTC).isoformat(),
        "week_start":    str(week_start),
        "week_end":      str(week_start + timedelta(days=6)),
        "this_week":     this_week,
        "prev_week":     prev_week,
        "insight":       plan.get("insight", ""),
        "next_week_plan": plan.get("next_week", []),
        "model":         LM_MODEL,
    }
    with open(SNAPSHOT_PATH, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Weekly plan saved → {SNAPSHOT_PATH}")


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    print(f"ERGBootCamp — generating weekly plan via {LM_MODEL}")

    today      = date.today()
    # On Sunday: review the week just finished (Mon–Sun).
    # Any other day: review the current week Mon–today so the script is
    # always runnable and always has data.
    if today.weekday() == 6:          # Sunday
        week_end   = today
        week_start = today - timedelta(days=6)
    else:
        week_start = today - timedelta(days=today.weekday())   # this Monday
        week_end   = today

    prev_end   = week_start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=6)

    print(f"Aggregating: {week_start} → {week_end}")
    this_rows  = _get_week_rows(week_start, week_end)
    prev_rows  = _get_week_rows(prev_start, prev_end)

    this_week  = _aggregate(this_rows)
    prev_week  = _aggregate(prev_rows)

    if not this_week:
        print("No data for this week — skipping LLM call.")
        return

    plan = generate_weekly_plan(this_week, prev_week, week_start)
    save_snapshot(this_week, prev_week, plan, week_start)
    print("Done.")


if __name__ == "__main__":
    main()
