"""
ERGBootCamp — send_discord.py

Sends the daily coaching brief to Discord via webhook embed.
Called by the launchd job at 06:30, or manually.

Usage:
    python pipelines/send_discord.py             # generate + send
    python pipelines/send_discord.py --brief-only # send latest saved brief
"""

import sys
import os
import json
import requests
from datetime import date, datetime
from pathlib import Path

from pipelines.config_loader import BRIEFS_DIR, ATHLETE, fmt_split

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# colour codes (decimal) — mapped to fatigue state
COLOURS = {
    "normal":  0x00e5b4,   # teal  — good to train
    "caution": 0xf59e0b,   # amber — watch load
    "fatigue": 0xef4444,   # red   — back off
}

FATIGUE_EMOJI = {
    "normal":  "🟢",
    "caution": "🟡",
    "fatigue": "🔴",
}


def load_brief() -> str | None:
    today_path = BRIEFS_DIR / f"{date.today().isoformat()}.txt"
    latest_path = BRIEFS_DIR / "latest.txt"
    for p in [today_path, latest_path]:
        if p.exists():
            return p.read_text().strip()
    return None


def load_coaching_output() -> dict:
    p = Path("data/coaching_output.json")
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return {}


def load_garmin() -> dict:
    p = Path("data/garmin_latest.json")
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return {}



def build_embed(brief_text: str, coaching: dict, garmin: dict) -> dict:
    summary = coaching.get("summary", {})
    model = coaching.get("model", "Qwen2.5-14B")
    fatigue = summary.get("fatigue", "normal")
    colour = COLOURS.get(fatigue, COLOURS["normal"])
    f_emoji = FATIGUE_EMOJI.get(fatigue, "🟢")

    # competition countdown
    comp = datetime.strptime(ATHLETE["competition_date"], "%Y-%m-%d").date()
    days_left = max((comp - date.today()).days, 0)

    # split info
    split_fmt = summary.get("split_formatted", fmt_split(summary.get("split_raw_sec")))
    prev_fmt   = summary.get("prev_split_formatted", "—")
    delta_sec  = summary.get("delta_sec")
    delta_dir  = summary.get("delta_direction", "—")
    delta_str  = f"{delta_sec:+.1f}s — {delta_dir}" if delta_sec is not None else "—"

    # garmin fields
    garmin_val = (
        f"🔋 **Body Battery:** {garmin.get('body_battery', '—')}/100\n"
        f"📊 **HRV Status:** {garmin.get('hrv_status', '—')}\n"
        f"😴 **Sleep Score:** {garmin.get('sleep_score', '—')}\n"
        f"❤️ **Resting HR:** {garmin.get('resting_hr', '—')} bpm\n"
        f"😤 **Stress Level:** {garmin.get('stress', '—')}\n"
        f"⚡ **Readiness:** {garmin.get('readiness', '—')}%"
        if garmin else "_Run `import_garmin.py` to sync recovery data_"
    )

    # convert single-asterisk bold (*text*) to Discord double-asterisk (**text**)
    clean_brief = brief_text.replace("*", "**")

    fields = [
        {
            "name": "📍 Last Session",
            "value": (
                f"**Split:** {split_fmt}\n"
                f"**vs Prev:** {delta_str}\n"
                f"**Distance:** {summary.get('distance_m', '—')}m  "
                f"**Duration:** {summary.get('duration_min', '—')} min"
            ),
            "inline": True,
        },
        {
            "name": f"{f_emoji} Readiness",
            "value": (
                f"**Fatigue:** {fatigue.title()}\n"
                f"**Weekly load:** {summary.get('weekly_load_min', '—')} min\n"
                f"**Trend:** {summary.get('trend', '—')}"
            ),
            "inline": True,
        },
        {
            "name": "💚 Garmin Recovery",
            "value": garmin_val,
            "inline": False,
        },
        {
            "name": "🧠 Today's Brief",
            "value": clean_brief[:1000] + ("..." if len(clean_brief) > 1000 else ""),
            "inline": False,
        },
        {
            "name": "🏁 Competition Countdown",
            "value": f"**{days_left} days** until your first race — {ATHLETE['competition_date']}",
            "inline": False,
        },
    ]

    return {
        "embeds": [
            {
                "title": f"🚣 ERGBootCamp — Morning Brief {date.today().strftime('%a %d %b')}",
                "color": colour,
                "fields": fields,
                "footer": {
                    "text": f"Powered by {model} via LMStudio  •  ERGBootCamp"
                },
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
        ]
    }


def send_discord(payload: dict) -> dict:
    if not DISCORD_WEBHOOK_URL:
        raise ValueError("Missing DISCORD_WEBHOOK_URL in config/.env")

    r = requests.post(
        DISCORD_WEBHOOK_URL,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=10,
    )
    r.raise_for_status()
    return {"status": r.status_code, "ok": r.ok}


def main():
    brief_only = "--brief-only" in sys.argv

    if not brief_only:
        from pipelines.generate_daily_brief import main as gen_brief
        gen_brief()

    brief = load_brief()
    if not brief:
        print("No brief found. Run generate_daily_brief.py first.")
        sys.exit(1)

    coaching = load_coaching_output()
    garmin   = load_garmin()

    payload = build_embed(brief, coaching, garmin)

    print(f"Sending Discord embed to webhook...")
    result = send_discord(payload)
    print(f"Sent! Status: {result['status']}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Discord send failed: {e}")
        sys.exit(1)
