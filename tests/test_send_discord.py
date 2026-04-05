"""
Unit tests for pipelines/send_discord.py
"""

import os
import sys
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure project root is on path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipelines.send_discord import (
    build_embed,
    load_brief,
    send_discord,
    COLOURS,
    FATIGUE_EMOJI,
    fmt_split,
)
from pipelines.config_loader import BRIEFS_DIR, ATHLETE


# ── fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_BRIEF = "Good morning Em! Yesterday you rowed 5000m at 2:15/500m. Great work!"

SAMPLE_COACHING = {
    "model": "Qwen2.5-14B",
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

SAMPLE_GARMIN = {
    "body_battery": 72,
    "hrv_status": "Balanced",
    "sleep_score": 81,
    "resting_hr": 52,
    "stress": 28,
    "readiness": 85,
}


# ── build_embed tests ────────────────────────────────────────────────────────


def test_build_embed_returns_valid_structure():
    payload = build_embed(SAMPLE_BRIEF, SAMPLE_COACHING, SAMPLE_GARMIN)
    assert "embeds" in payload
    assert len(payload["embeds"]) == 1
    embed = payload["embeds"][0]
    assert "title" in embed
    assert "color" in embed
    assert "fields" in embed


def test_embed_has_correct_fields():
    payload = build_embed(SAMPLE_BRIEF, SAMPLE_COACHING, SAMPLE_GARMIN)
    embed = payload["embeds"][0]
    field_names = [f["name"] for f in embed["fields"]]
    assert any("Last Session" in n for n in field_names)
    assert any("Readiness" in n for n in field_names)
    assert any("Garmin Recovery" in n for n in field_names)
    assert any("Brief" in n for n in field_names)
    assert any("Competition Countdown" in n for n in field_names)


def test_garmin_populated_renders_values():
    payload = build_embed(SAMPLE_BRIEF, SAMPLE_COACHING, SAMPLE_GARMIN)
    garmin_field = [f for f in payload["embeds"][0]["fields"] if "Garmin" in f["name"]][0]
    assert "72" in garmin_field["value"]
    assert "Balanced" in garmin_field["value"]
    assert "81" in garmin_field["value"]


def test_garmin_empty_renders_placeholder():
    payload = build_embed(SAMPLE_BRIEF, SAMPLE_COACHING, {})
    garmin_field = [f for f in payload["embeds"][0]["fields"] if "Garmin" in f["name"]][0]
    assert "import_garmin.py" in garmin_field["value"]


def test_fatigue_colour_normal():
    coaching = {**SAMPLE_COACHING, "summary": {**SAMPLE_COACHING["summary"], "fatigue": "normal"}}
    payload = build_embed(SAMPLE_BRIEF, coaching, SAMPLE_GARMIN)
    assert payload["embeds"][0]["color"] == 0x00e5b4  # teal


def test_fatigue_colour_caution():
    coaching = {**SAMPLE_COACHING, "summary": {**SAMPLE_COACHING["summary"], "fatigue": "caution"}}
    payload = build_embed(SAMPLE_BRIEF, coaching, SAMPLE_GARMIN)
    assert payload["embeds"][0]["color"] == 0xf59e0b  # amber


def test_fatigue_colour_fatigue():
    coaching = {**SAMPLE_COACHING, "summary": {**SAMPLE_COACHING["summary"], "fatigue": "fatigue"}}
    payload = build_embed(SAMPLE_BRIEF, coaching, SAMPLE_GARMIN)
    assert payload["embeds"][0]["color"] == 0xef4444  # red


def test_competition_countdown_positive():
    payload = build_embed(SAMPLE_BRIEF, SAMPLE_COACHING, SAMPLE_GARMIN)
    countdown_field = [f for f in payload["embeds"][0]["fields"] if "Countdown" in f["name"]][0]
    # Extract the number of days from the field value
    import re
    match = re.search(r"(\d+) days", countdown_field["value"])
    assert match is not None
    days = int(match.group(1))
    assert days > 0


# ── load_brief tests ─────────────────────────────────────────────────────────


def test_load_brief_returns_none_when_no_file(tmp_path):
    with patch("pipelines.send_discord.BRIEFS_DIR", tmp_path):
        assert load_brief() is None


def test_load_brief_returns_content_from_latest(tmp_path):
    latest = tmp_path / "latest.txt"
    latest.write_text("Test brief content")
    with patch("pipelines.send_discord.BRIEFS_DIR", tmp_path):
        result = load_brief()
        assert result == "Test brief content"


# ── send_discord tests ───────────────────────────────────────────────────────


@patch("pipelines.send_discord.requests.post")
@patch("pipelines.send_discord.DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test/test")
def test_send_discord_succeeds_on_204(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 204
    mock_response.ok = True
    mock_response.raise_for_status = MagicMock()
    mock_post.return_value = mock_response

    result = send_discord({"embeds": []})
    assert result["status"] == 204
    assert result["ok"] is True
    mock_post.assert_called_once()


@patch("pipelines.send_discord.requests.post")
@patch("pipelines.send_discord.DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/test/test")
def test_send_discord_raises_on_non_204(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.raise_for_status.side_effect = Exception("Bad Request")
    mock_post.return_value = mock_response

    with pytest.raises(Exception, match="Bad Request"):
        send_discord({"embeds": []})


# ── fmt_split tests ──────────────────────────────────────────────────────────


def test_fmt_split_formats_correctly():
    assert fmt_split(135.0) == "2:15.0/500m"


def test_fmt_split_none_returns_dash():
    assert fmt_split(None) == "\u2014"
