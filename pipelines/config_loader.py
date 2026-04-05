"""
ERGBootCamp — shared configuration loader.
All pipelines import from here so settings live in one place.
"""

import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# ── resolve project root (works regardless of cwd) ─────────────────────────
ROOT = Path(__file__).resolve().parent.parent

load_dotenv(ROOT / "config" / ".env")


def load_settings() -> dict:
    with open(ROOT / "config" / "settings.yaml") as f:
        return yaml.safe_load(f)


SETTINGS = load_settings()

# ── paths ───────────────────────────────────────────────────────────────────
DB_PATH = str(ROOT / SETTINGS["database_path"])
BRIEFS_DIR = ROOT / SETTINGS["coaching"]["briefs_dir"]
BRIEFS_DIR.mkdir(parents=True, exist_ok=True)

# ── Concept2 ─────────────────────────────────────────────────────────────────
C2_API_TOKEN = os.getenv("C2_API_TOKEN")
C2_API_URL = SETTINGS["concept2"]["api_url"]
C2_REPLAY_DAYS = SETTINGS["concept2"]["replay_days"]

# ── LMStudio (OpenAI-compatible) ─────────────────────────────────────────────
LM_BASE_URL = SETTINGS["lmstudio"]["base_url"]
LM_MODEL = SETTINGS["lmstudio"]["model"]
LM_MAX_TOKENS = SETTINGS["lmstudio"]["max_tokens"]
LM_TEMPERATURE = SETTINGS["lmstudio"]["temperature"]


def get_lm_client() -> OpenAI:
    """Return an OpenAI client pointed at LMStudio."""
    return OpenAI(
        base_url=LM_BASE_URL,
        api_key=os.getenv("OPENAI_API_KEY", "lm-studio"),
    )


# ── Discord ──────────────────────────────────────────────────────────────────
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# ── Garmin ───────────────────────────────────────────────────────────────────
GARMIN_EMAIL = os.getenv("GARMIN_EMAIL")
GARMIN_PASSWORD = os.getenv("GARMIN_PASSWORD")

# ── Athlete ──────────────────────────────────────────────────────────────────
ATHLETE = SETTINGS["athlete"]

# ── Coaching memory ──────────────────────────────────────────────────────────
COACHING = SETTINGS["coaching"]
