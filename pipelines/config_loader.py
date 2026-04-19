"""
ERGBootCamp — shared configuration loader.
All pipelines import from here so settings live in one place.
"""

import os
import subprocess
import yaml
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

# ── resolve project root (works regardless of cwd) ─────────────────────────
ROOT = Path(__file__).resolve().parent.parent


def _resolve_data_root() -> Path:
    """Return the main git working tree root for data paths.

    When running inside a git worktree (e.g. .claude/worktrees/*), data files
    like the DuckDB database and JSON snapshots live in the main working tree
    because they are gitignored.  This helper ensures all data I/O targets the
    main tree regardless of which worktree the code is executing from.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        git_common = Path(result.stdout.strip())
        if not git_common.is_absolute():
            git_common = (ROOT / git_common).resolve()
        # git-common-dir returns e.g. "/repo/.git" → parent is the repo root
        return git_common.parent
    except Exception:
        return ROOT


DATA_ROOT = _resolve_data_root()

load_dotenv(ROOT / "config" / ".env")


class LMStudioSettings(BaseModel):
    base_url: str
    model: str
    max_tokens: int
    temperature: float


class Concept2Settings(BaseModel):
    api_url: str
    replay_days: int


class CoachingSettings(BaseModel):
    context_window: int
    briefs_dir: str


class AthleteSettings(BaseModel):
    name: str
    competition_date: str


class Settings(BaseModel):
    lmstudio: LMStudioSettings
    concept2: Concept2Settings
    coaching: CoachingSettings
    athlete: AthleteSettings
    database_path: str


def load_settings() -> dict:
    with open(ROOT / "config" / "settings.yaml") as f:
        raw = yaml.safe_load(f)
    try:
        Settings(**raw)
    except Exception as e:
        raise ValueError(f"settings.yaml validation failed: {e}") from e
    return raw


SETTINGS = load_settings()

# ── paths (data lives in the main working tree, not in worktrees) ──────────
DB_PATH = str(DATA_ROOT / SETTINGS["database_path"])
BRIEFS_DIR = DATA_ROOT / SETTINGS["coaching"]["briefs_dir"]
BRIEFS_DIR.mkdir(parents=True, exist_ok=True)

# ── Concept2 ─────────────────────────────────────────────────────────────────
C2_API_TOKEN = os.getenv("C2_API_TOKEN")
C2_API_URL = SETTINGS["concept2"]["api_url"]
C2_REPLAY_DAYS = SETTINGS["concept2"]["replay_days"]

# ── LM Studio (OpenAI-compatible) ────────────────────────────────────────────
LM_BASE_URL = SETTINGS["lmstudio"]["base_url"]
LM_MODEL = SETTINGS["lmstudio"]["model"]
LM_MAX_TOKENS = SETTINGS["lmstudio"]["max_tokens"]
LM_TEMPERATURE = SETTINGS["lmstudio"]["temperature"]


def get_lm_client() -> OpenAI:
    """Return an OpenAI client pointed at LM Studio."""
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


# ── Formatting ──────────────────────────────────────────────────────────────
def fmt_split(sec, suffix="/500m") -> str:
    if sec is None:
        return "\u2014"
    m = int(sec // 60)
    s = sec % 60
    return f"{m}:{s:04.1f}{suffix}"
