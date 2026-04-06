"""
FR-C02 — recency_weight
FR-C03 — completeness_ratio
FR-C04 — injection_priority

All scorers are pure functions; configuration is read from environment
variables at call time so tests can monkeypatch os.environ freely.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from .models import CoachingEntity


# ── FR-C02 ──────────────────────────────────────────────────────────────────
def _decay_config() -> tuple[int, float]:
    days = int(os.getenv("RECENCY_DECAY_DAYS", "30"))
    floor = float(os.getenv("RECENCY_MIN_WEIGHT", "0.5"))
    return days, floor


def recency_weight(created_at: datetime) -> float:
    """
    1.0 within 7 days; linearly decays to RECENCY_MIN_WEIGHT at
    RECENCY_DECAY_DAYS; floor afterwards.
    """
    decay_days, floor = _decay_config()
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    age_days = (datetime.now(timezone.utc) - created_at).total_seconds() / 86400.0

    if age_days <= 7:
        return 1.0
    if age_days >= decay_days:
        return floor

    # linear decay from 1.0 at day 7 to `floor` at day `decay_days`
    span = decay_days - 7
    if span <= 0:
        return floor
    progress = (age_days - 7) / span
    return 1.0 - progress * (1.0 - floor)


# ── FR-C03 ──────────────────────────────────────────────────────────────────
def _is_present(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str) and value.strip() == "":
        return False
    if isinstance(value, (list, dict, tuple, set)) and len(value) == 0:
        return False
    return True


def completeness_ratio(obj: CoachingEntity) -> float:
    """Proportion of declared-required fields that are non-null/non-empty."""
    required = obj.required_field_names()
    if not required:
        return 1.0
    present = sum(1 for name in required if _is_present(getattr(obj, name, None)))
    return present / len(required)


# ── FR-C04 ──────────────────────────────────────────────────────────────────
def injection_priority(obj: CoachingEntity) -> float:
    """confidence × recency_weight × completeness_ratio"""
    return (
        float(obj.confidence)
        * recency_weight(obj.created_at)
        * completeness_ratio(obj)
    )
