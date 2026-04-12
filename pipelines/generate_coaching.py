"""
ERGBootCamp — generate_coaching.py

Calls Qwen2.5-14B Instruct via LM Studio's OpenAI-compatible endpoint.
Injects recent coaching tips as context so the model knows whether
slower splits are expected (post-recovery-row) or a genuine concern.
"""

import json
import os
import duckdb
from datetime import datetime, UTC

from pipelines.config_loader import (
    DB_PATH, LM_MODEL, LM_MAX_TOKENS, LM_TEMPERATURE, ATHLETE, COACHING,
    ROOT, get_lm_client, fmt_split,
)
from pipelines.coaching_memory import (
    get_recent_tips, build_context_block, last_taper_flag, add_tip,
)


def safe_float(x):
    try:
        return float(x) if x is not None else None
    except Exception:
        return None



def get_personal_best() -> str:
    """Query the all-time personal best split from workout_sessions."""
    con = duckdb.connect(DB_PATH)
    row = con.execute("""
    SELECT avg_split_sec, workout_date
    FROM workout_sessions
    WHERE avg_split_sec IS NOT NULL AND distance_m >= 1000
    ORDER BY avg_split_sec ASC LIMIT 1
    """).fetchone()
    con.close()

    if row is None or row[0] is None:
        return "N/A"

    best_sec = row[0]
    best_date = row[1]
    split_str = fmt_split(best_sec)
    try:
        date_str = best_date.strftime("%b %d")
    except Exception:
        date_str = str(best_date)
    return f"{split_str} ({best_sec:.1f}s) on {date_str}"


def get_summary():
    con = duckdb.connect(DB_PATH)
    df = con.execute("""
    SELECT * FROM daily_metrics
    WHERE avg_split_sec IS NOT NULL
    ORDER BY workout_date
    """).fetchdf()
    con.close()

    if df.empty:
        return None

    latest = df.iloc[-1]
    delta = latest["delta"]
    return {
        "date": str(latest["workout_date"]),
        "split_formatted": fmt_split(safe_float(latest["avg_split_sec"])),
        "split_raw_sec": round(safe_float(latest["avg_split_sec"]), 1),
        "prev_split_formatted": fmt_split(safe_float(latest.get("prev_split"))),
        "delta_sec": round(safe_float(delta), 1) if delta is not None else None,
        "delta_direction": "FASTER (improved)" if delta is not None and delta < 0 else "SLOWER (regressed)",
        "rolling_split_formatted": fmt_split(safe_float(latest["rolling_avg_split"])),
        "duration_min": round(safe_float(latest["duration_sec"]) / 60, 1),
        "distance_m": int(latest["distance_m"]),
        "fatigue": latest["fatigue_flag"],
        "weekly_load_min": round(safe_float(latest["weekly_load_min"]), 1),
        "session_type": latest["session_type"],
        "trend": "improving (getting faster)" if delta is not None and delta < 0 else "declining (getting slower)",
        "personal_best_split": get_personal_best(),
        "consistency_stddev": round(safe_float(latest.get("consistency")), 2)
            if latest.get("consistency") is not None else None,
    }


def _summary_for_llm(summary: dict) -> dict:
    """Strip raw-seconds fields that the LLM tends to quote verbatim.

    Keeps only the *_formatted fields so the LLM has no numeric split
    values lying around to accidentally regurgitate.
    """
    SPLIT_RAW_FIELDS = {"split_raw_sec"}
    return {k: v for k, v in summary.items() if k not in SPLIT_RAW_FIELDS}


def generate_coaching(summary, garmin=None):
    client = get_lm_client()
    recent_tips = get_recent_tips()
    context_block = build_context_block(recent_tips)
    taper_active = last_taper_flag()

    taper_note = (
        "\n*** IMPORTANT: The previous coaching tip flagged this session as a RECOVERY ROW. "
        "Slower splits are EXPECTED and intentional. Do NOT treat the performance decline as "
        "negative. Acknowledge it as planned adaptation.\n"
        if taper_active else ""
    )

    garmin_block = ""
    if garmin:
        garmin_block = f"""
Garmin Connect Recovery Signals:
- Body Battery: {garmin.get('body_battery', 'N/A')} / 100
- HRV Status: {garmin.get('hrv_status', 'N/A')}
- Sleep Score: {garmin.get('sleep_score', 'N/A')}
- Resting HR: {garmin.get('resting_hr', 'N/A')} bpm
- Stress Level: {garmin.get('stress', 'N/A')}
- Readiness: {garmin.get('readiness', 'N/A')}%
"""

    prompt = f"""You are an expert Concept2 indoor rowing coach for a beginner rower
training for their first indoor rowing competition in 7 months.

Athlete: height {ATHLETE['height_cm']}cm | goal: {ATHLETE['goal']} | competition: {ATHLETE['competition_date']}

SPLIT CONVENTION — READ CAREFULLY:
- All split values MUST be written in MM:SS.t/500m format (e.g. "2:58.9/500m").
- NEVER write splits as raw seconds (e.g. "178.9" or "208.7"). This is forbidden.
- The fields ending in "_formatted" are already in MM:SS.t/500m — quote them verbatim.
- Lower split = faster. delta_formatted is NEGATIVE when faster, POSITIVE when slower.
- Use delta_direction for plain-English direction ("FASTER" / "SLOWER").
{taper_note}
--- PREVIOUS COACHING CONTEXT ---
{context_block}
--- END CONTEXT ---

Latest session data:
{json.dumps(_summary_for_llm(summary), indent=2)}
{garmin_block}
The athlete's personal best is {summary['personal_best_split']} from a hard threshold effort.
Today's 10km at {summary['split_formatted']} was intentional easy volume — not a performance test.

Provide:
1. What changed — reference split_formatted and prev_split_formatted, state faster or slower
2. What this indicates — fitness / fatigue / pacing context
3. Risk level (low / moderate / high) — one sentence
4. Next session — distance, target split in MM:SS that is FASTER than 2:36/500m, stroke rate, structure
5. One technical cue specific to this athlete's data
6. One pacing mistake to avoid

All pace targets must be in MM:SS/500m. Be direct and specific."""

    response = client.chat.completions.create(
        model=LM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=LM_MAX_TOKENS,
        temperature=LM_TEMPERATURE,
    )

    coaching_text = response.choices[0].message.content.strip()

    tag = "recovery" if taper_active else (
        "performance" if summary.get("trend") == "improving" else "caution"
    )
    add_tip(
        tip_text=coaching_text,
        author="coach",
        tag=tag,
        session_date=summary.get("date"),
    )

    return coaching_text


def save_output(summary, coaching, garmin=None):
    output = {
        "summary": summary,
        "coaching": coaching,
        "garmin": garmin,
        "generated_at": datetime.now(UTC).isoformat(),
        "model": LM_MODEL,
    }
    os.makedirs("data", exist_ok=True)
    with open("data/coaching_output.json", "w") as f:
        json.dump(output, f, indent=2)


def main():
    print(f"ERGBootCamp - generating coaching insight via {LM_MODEL}")

    summary = get_summary()
    if summary is None:
        print("No data. Run pull_concept2.py first.")
        return

    garmin = None
    try:
        with open(ROOT / "data" / "garmin_latest.json") as f:
            garmin = json.load(f)
        print("Garmin data loaded")
    except FileNotFoundError:
        print("No Garmin data (skipping)")

    coaching = generate_coaching(summary, garmin)
    save_output(summary, coaching, garmin)
    print("Coaching output saved -> data/coaching_output.json")


if __name__ == "__main__":
    main()
