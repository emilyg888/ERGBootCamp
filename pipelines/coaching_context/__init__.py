"""
Coaching context semantic layer.

Implements FR-C01..FR-C10: typed coaching entities, scoring, policy
enforcement, and constrained LLM context injection.
"""

from .models import (
    CoachingEntity,
    ParticipantProfile,
    SessionNote,
    GoalRecord,
    Tier,
)
from .scoring import recency_weight, completeness_ratio, injection_priority
from .injector import build_context
from .pep import PolicyEnforcementPoint, PolicyViolationError, PEPDecision
from .modes import ExecutionMode
from .quarantine import quarantine_log
from .llm_call import call_llm_with_context

__all__ = [
    "CoachingEntity",
    "ParticipantProfile",
    "SessionNote",
    "GoalRecord",
    "Tier",
    "recency_weight",
    "completeness_ratio",
    "injection_priority",
    "build_context",
    "PolicyEnforcementPoint",
    "PolicyViolationError",
    "PEPDecision",
    "ExecutionMode",
    "quarantine_log",
    "call_llm_with_context",
]
