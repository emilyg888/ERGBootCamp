"""
FR-C05 — Context injector.

Builds an ordered list of read-only JSON-serialisable dicts from typed
CoachingEntity instances. Objects above the priority threshold get
full-text serialisation; objects below get a summary. Injection halts
when the cumulative token estimate exceeds the budget — truncated
objects are logged to WARNING and to the quarantine log.
"""

from __future__ import annotations

import logging
import os
from typing import Iterable

from .models import CoachingEntity
from .quarantine import quarantine_log
from .scoring import (
    completeness_ratio,
    injection_priority,
)

_LOG = logging.getLogger("coaching_context.injector")

PRIORITY_FULL_TEXT_THRESHOLD = 0.85
COMPLETENESS_QUARANTINE_THRESHOLD = 0.5


def _summary_ratio() -> float:
    return float(os.getenv("COACHING_SUMMARY_RATIO", "0.3"))


def _estimate_tokens(text: str) -> int:
    """Cheap chars/4 heuristic. Replace with tiktoken if precision matters."""
    return max(1, len(text) // 4)


def _summarise(content: str) -> str:
    words = content.split()
    keep = max(1, int(len(words) * _summary_ratio()))
    return " ".join(words[:keep])


def _serialise_full(obj: CoachingEntity) -> dict:
    return obj.model_dump(mode="json")


def _serialise_summary(obj: CoachingEntity) -> dict:
    payload = obj.model_dump(mode="json")
    payload["content"] = _summarise(obj.content)
    payload["_summarised"] = True
    return payload


def build_context(
    objects: list[CoachingEntity],
    token_budget: int = 4000,
) -> list[dict]:
    """
    FR-C05. Returns a list of read-only dicts ready for the LLM.

    Pipeline:
      1. Reject raw dicts (FR-C01 enforcement).
      2. Quarantine entities below the completeness threshold.
      3. Sort by injection_priority descending.
      4. Serialise full vs. summary based on threshold.
      5. Stop when cumulative token estimate exceeds budget; quarantine
         the rest as budget_truncation.
    """
    # FR-C01 enforcement: only typed objects are accepted.
    for o in objects:
        if not isinstance(o, CoachingEntity):
            raise TypeError(
                f"build_context only accepts CoachingEntity instances, got {type(o).__name__}"
            )

    eligible: list[CoachingEntity] = []
    for obj in objects:
        ratio = completeness_ratio(obj)
        if ratio < COMPLETENESS_QUARANTINE_THRESHOLD:
            quarantine_log.write(
                object_id=obj.id,
                entity_type=obj.entity_type,
                reason_code="completeness_below_threshold",
                priority_score=injection_priority(obj),
                extra={"completeness_ratio": ratio},
            )
            continue
        eligible.append(obj)

    eligible.sort(key=injection_priority, reverse=True)

    out: list[dict] = []
    used_tokens = 0
    overflow_started = False

    for obj in eligible:
        priority = injection_priority(obj)
        if priority >= PRIORITY_FULL_TEXT_THRESHOLD:
            payload = _serialise_full(obj)
        else:
            payload = _serialise_summary(obj)

        est = _estimate_tokens(str(payload))

        if overflow_started or used_tokens + est > token_budget:
            overflow_started = True
            _LOG.warning(
                "context budget truncation: id=%s priority=%.3f est_tokens=%d",
                obj.id,
                priority,
                est,
            )
            quarantine_log.write(
                object_id=obj.id,
                entity_type=obj.entity_type,
                reason_code="budget_truncation",
                priority_score=priority,
                extra={"estimated_tokens": est, "token_budget": token_budget},
            )
            continue

        used_tokens += est
        out.append(payload)

    return out
