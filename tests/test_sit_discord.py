"""
SIT (System Integration Test) for Discord webhook delivery.

Sends a real embed to the Discord channel to verify end-to-end delivery.
Skips gracefully if DISCORD_WEBHOOK_URL is not set.

Run:
    pytest tests/test_sit_discord.py -v -s
"""

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Load .env so DISCORD_WEBHOOK_URL is available
from dotenv import load_dotenv
load_dotenv(ROOT / "config" / ".env")

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

pytestmark = pytest.mark.skipif(
    not DISCORD_WEBHOOK_URL,
    reason="DISCORD_WEBHOOK_URL not set — skipping SIT",
)


def test_discord_webhook_url_is_set():
    assert DISCORD_WEBHOOK_URL, "DISCORD_WEBHOOK_URL must be set for SIT"


def test_send_real_embed_to_discord():
    from pipelines.config_loader import ATHLETE
    from pipelines.send_discord import build_embed, send_discord

    mock_brief = (
        "**Good morning Em!** 🚣\n\n"
        "**Yesterday:** You rowed 5000m at a solid 2:15/500m — "
        "1.2s faster than the session before.\n\n"
        "**Today's session:** Easy 6000m at 2:20-2:22/500m, rate 20.\n\n"
        "**Focus cue:** Drive with the legs first, keep the hands relaxed.\n\n"
        "**Motivation:** You're building a strong base — trust the process!"
    )

    mock_coaching = {
        "model": "SIT-test",
        "summary": {
            "split_raw_sec": 135.0,
            "split_formatted": "2:15.0/500m",
            "prev_split_formatted": "2:16.2/500m",
            "delta_sec": -1.2,
            "delta_direction": "improving",
            "distance_m": 5000,
            "duration_min": 22.5,
            "weekly_load_min": 120,
            "fatigue": "normal",
            "trend": "improving",
        },
    }

    mock_garmin = {
        "body_battery": 72,
        "hrv_status": "Balanced",
        "sleep_score": 81,
        "resting_hr": 52,
        "stress": 28,
        "readiness": 85,
    }

    payload = build_embed(mock_brief, mock_coaching, mock_garmin)

    # Tag embed as SIT test
    payload["embeds"][0]["title"] = "🧪 SIT Test — " + payload["embeds"][0]["title"]

    result = send_discord(payload)
    print(f"Discord response: {result}")
    assert result["status"] == 204, f"Expected 204, got {result['status']}"
