"""
FR-C10 — Mode-aware injection.

Mode is an explicit per-task argument; it is never inferred from
conversation history.
"""

from __future__ import annotations

from enum import Enum

from .models import Tier


class ExecutionMode(str, Enum):
    EXPLORATION = "exploration"
    EXECUTION = "execution"


def allowed_tiers(mode: ExecutionMode) -> set[Tier]:
    """Tiers eligible for injection in the given mode."""
    if mode is ExecutionMode.EXECUTION:
        return {Tier.GOLD}
    if mode is ExecutionMode.EXPLORATION:
        return {Tier.GOLD, Tier.SILVER}
    raise ValueError(f"Unknown execution mode: {mode!r}")
