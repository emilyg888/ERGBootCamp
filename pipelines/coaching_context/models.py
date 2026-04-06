"""
FR-C01 — Typed coaching context object schema.

Each entity declares which fields are *required* via the
`json_schema_extra={"required_for_completeness": True}` marker on the
Pydantic field. `completeness_ratio` (FR-C03) inspects this marker; the
context injector (FR-C05/C07) refuses raw dicts and only accepts
instances of these classes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import ClassVar, Optional

from pydantic import BaseModel, ConfigDict, Field


class Tier(str, Enum):
    GOLD = "gold"
    SILVER = "silver"
    BRONZE = "bronze"


def _required(description: str = "", **kwargs):
    """Mark a field as contributing to completeness_ratio."""
    return Field(
        ...,
        description=description,
        json_schema_extra={"required_for_completeness": True},
        **kwargs,
    )


def _optional(default=None, description: str = "", **kwargs):
    # Pydantic disallows passing both default and default_factory; only forward
    # `default` when no factory is supplied.
    if "default_factory" in kwargs:
        return Field(
            description=description,
            json_schema_extra={"required_for_completeness": False},
            **kwargs,
        )
    return Field(
        default=default,
        description=description,
        json_schema_extra={"required_for_completeness": False},
        **kwargs,
    )


class CoachingEntity(BaseModel):
    """
    Base class for all typed coaching context objects.

    Subclasses MUST set `entity_type` and may declare additional required
    fields via `_required(...)`. The base fields below are common to every
    entity and participate in scoring (FR-C02..FR-C04) and policy
    enforcement (FR-C06).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    entity_type: ClassVar[str] = "coaching_entity"

    id: str = _required("Stable unique id")
    participant_id: str = _required("Owner of the data — used by PEP for RBAC")
    created_at: datetime = _required("Ingestion timestamp (UTC)")
    tier: Tier = _required("gold | silver | bronze — drives mode gating")
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Calibrated confidence (FR-C09). Defaults to completeness on first ingest.",
        json_schema_extra={"required_for_completeness": False},
    )
    content: str = _required("Free-text body used for serialisation/summary")

    @classmethod
    def required_field_names(cls) -> list[str]:
        """Names of fields that count toward completeness_ratio."""
        names: list[str] = []
        for fname, finfo in cls.model_fields.items():
            extra = finfo.json_schema_extra or {}
            if isinstance(extra, dict) and extra.get("required_for_completeness"):
                names.append(fname)
        return names


class ParticipantProfile(CoachingEntity):
    entity_type: ClassVar[str] = "participant_profile"

    display_name: str = _required("Human-readable name")
    goals_summary: Optional[str] = _optional(description="Free-text goals overview")
    preferred_pronouns: Optional[str] = _optional()


class SessionNote(CoachingEntity):
    entity_type: ClassVar[str] = "session_note"

    session_date: datetime = _required("When the coaching session occurred")
    coach_id: str = _required("Coach who authored the note")
    summary: Optional[str] = _optional(description="Short headline of the session")
    action_items: Optional[list[str]] = _optional(default_factory=list)


class GoalRecord(CoachingEntity):
    entity_type: ClassVar[str] = "goal_record"

    goal_text: str = _required("The goal statement")
    target_date: Optional[datetime] = _optional()
    status: Optional[str] = _optional(description="open | in_progress | done | dropped")


# ── helper for tests / fixtures ─────────────────────────────────────────────
def utc_now() -> datetime:
    return datetime.now(timezone.utc)
