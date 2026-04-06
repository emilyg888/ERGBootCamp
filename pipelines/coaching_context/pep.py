"""
FR-C06 — Policy Enforcement Point.

Sits as a blocking filter between the context injector and the LLM call.
Enforces:
  (a) tier gate driven by the explicit ExecutionMode (FR-C10)
  (b) coach → participant role-based access control

Every decision is logged with a reason code; denials raise
PolicyViolationError if `strict=True`, otherwise the offending object is
dropped and recorded in the quarantine log.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

from .models import CoachingEntity, Tier
from .modes import ExecutionMode, allowed_tiers
from .quarantine import quarantine_log
from .scoring import injection_priority

_AUDIT = logging.getLogger("coaching_context.pep.audit")


class PolicyViolationError(Exception):
    """Raised when strict-mode PEP rejects an object."""


@dataclass(frozen=True)
class PEPDecision:
    object_id: str
    allowed: bool
    reason_code: str  # "ok" | "tier_gate" | "rbac_denied"


class PolicyEnforcementPoint:
    """
    Stateless policy filter.

    Parameters
    ----------
    coach_id:
        The coach making the request.
    coach_to_participants:
        Mapping coach_id -> set of participant_ids the coach is authorised
        to see. Anything outside this mapping is denied.
    mode:
        Explicit execution mode (FR-C10). Drives the tier gate.
    strict:
        If True, the first denial raises PolicyViolationError. If False,
        denied objects are filtered out and logged.
    """

    def __init__(
        self,
        coach_id: str,
        coach_to_participants: dict[str, set[str]],
        mode: ExecutionMode,
        strict: bool = True,
    ) -> None:
        self.coach_id = coach_id
        self.coach_to_participants = coach_to_participants
        self.mode = mode
        self.strict = strict
        self._tier_allowlist: set[Tier] = allowed_tiers(mode)

    # ── single-object check ────────────────────────────────────────────
    def evaluate(self, obj: CoachingEntity) -> PEPDecision:
        if obj.tier not in self._tier_allowlist:
            return PEPDecision(obj.id, False, "tier_gate")

        allowed_participants = self.coach_to_participants.get(self.coach_id, set())
        if obj.participant_id not in allowed_participants:
            return PEPDecision(obj.id, False, "rbac_denied")

        return PEPDecision(obj.id, True, "ok")

    # ── batch filter used between injector and LLM call ───────────────
    def filter(self, objects: Iterable[CoachingEntity]) -> list[CoachingEntity]:
        kept: list[CoachingEntity] = []
        for obj in objects:
            decision = self.evaluate(obj)

            _AUDIT.info(
                "pep_decision coach=%s mode=%s object=%s tier=%s allowed=%s reason=%s",
                self.coach_id,
                self.mode.value,
                obj.id,
                obj.tier.value,
                decision.allowed,
                decision.reason_code,
            )

            if decision.allowed:
                kept.append(obj)
                continue

            reason_for_quarantine = (
                "pep_tier_gate" if decision.reason_code == "tier_gate" else "pep_access_denied"
            )
            quarantine_log.write(
                object_id=obj.id,
                entity_type=obj.entity_type,
                reason_code=reason_for_quarantine,
                priority_score=injection_priority(obj),
                extra={
                    "coach_id": self.coach_id,
                    "mode": self.mode.value,
                    "tier": obj.tier.value,
                },
            )

            if self.strict:
                raise PolicyViolationError(
                    f"PEP denied object {obj.id} for coach {self.coach_id}: "
                    f"{decision.reason_code}"
                )

        return kept
