"""
Unit tests for the coaching_context semantic layer (FR-C01..FR-C10).
Pure-function focused; no LLM calls.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

UTC = timezone.utc

import pytest

from pipelines.coaching_context import (
    CoachingEntity,
    ExecutionMode,
    GoalRecord,
    ParticipantProfile,
    PolicyEnforcementPoint,
    PolicyViolationError,
    SessionNote,
    Tier,
    build_context,
    completeness_ratio,
    injection_priority,
    recency_weight,
)
from pipelines.coaching_context.calibration import (
    LineageEvent,
    default_initial_confidence,
    recalibrate,
)


# ── fixtures ────────────────────────────────────────────────────────────────
def _profile(**overrides) -> ParticipantProfile:
    base = dict(
        id="p1",
        participant_id="p1",
        created_at=datetime.now(UTC),
        tier=Tier.GOLD,
        confidence=1.0,
        content="Athlete profile body",
        display_name="Pat",
    )
    base.update(overrides)
    return ParticipantProfile(**base)


def _session(**overrides) -> SessionNote:
    base = dict(
        id="s1",
        participant_id="p1",
        created_at=datetime.now(UTC),
        tier=Tier.SILVER,
        confidence=0.9,
        content="Session went well, focus on stroke rate",
        session_date=datetime.now(UTC),
        coach_id="c1",
    )
    base.update(overrides)
    return SessionNote(**base)


# ── FR-C01 ──────────────────────────────────────────────────────────────────
def test_required_field_names_excludes_optional():
    names = SessionNote.required_field_names()
    assert "session_date" in names
    assert "coach_id" in names
    assert "summary" not in names
    assert "action_items" not in names


def test_models_are_frozen():
    p = _profile()
    with pytest.raises(Exception):
        p.confidence = 0.1  # type: ignore[misc]


# ── FR-C02 ──────────────────────────────────────────────────────────────────
def test_recency_weight_fresh():
    assert recency_weight(datetime.now(UTC)) == 1.0


def test_recency_weight_within_grace():
    assert recency_weight(datetime.now(UTC) - timedelta(days=5)) == 1.0


def test_recency_weight_decays_linearly():
    w = recency_weight(datetime.now(UTC) - timedelta(days=18))  # midpoint of 7..30
    # midpoint between 1.0 and 0.5 → 0.75 ± rounding
    assert 0.72 < w < 0.78


def test_recency_weight_floor():
    assert recency_weight(datetime.now(UTC) - timedelta(days=365)) == 0.5


def test_recency_weight_env_override(monkeypatch):
    monkeypatch.setenv("RECENCY_DECAY_DAYS", "60")
    monkeypatch.setenv("RECENCY_MIN_WEIGHT", "0.2")
    assert recency_weight(datetime.now(UTC) - timedelta(days=365)) == 0.2


# ── FR-C03 ──────────────────────────────────────────────────────────────────
def test_completeness_full():
    assert completeness_ratio(_profile()) == 1.0


def test_completeness_missing_content():
    p = _profile(content="")
    assert completeness_ratio(p) < 1.0


# ── FR-C04 ──────────────────────────────────────────────────────────────────
def test_injection_priority_product():
    p = _profile(confidence=0.8)
    expected = 0.8 * recency_weight(p.created_at) * 1.0
    assert abs(injection_priority(p) - expected) < 1e-9


# ── FR-C05 ──────────────────────────────────────────────────────────────────
def test_build_context_rejects_raw_dicts():
    with pytest.raises(TypeError):
        build_context([{"id": "x"}])  # type: ignore[list-item]


def test_build_context_sorts_by_priority():
    high = _profile(id="hi", confidence=1.0)
    low = _profile(id="lo", confidence=0.1)
    out = build_context([low, high], token_budget=10_000)
    assert out[0]["id"] == "hi"
    assert out[1]["id"] == "lo"


def test_build_context_summary_below_threshold():
    long_text = " ".join(["word"] * 200)
    obj = _profile(confidence=0.5, content=long_text)  # priority < 0.85
    out = build_context([obj], token_budget=10_000)
    assert out[0].get("_summarised") is True
    assert len(out[0]["content"].split()) < 200


def test_build_context_full_text_above_threshold():
    obj = _profile(confidence=1.0, content="hello world")  # priority ≈ 1.0
    out = build_context([obj], token_budget=10_000)
    assert out[0].get("_summarised") is None
    assert out[0]["content"] == "hello world"


def test_build_context_budget_truncation(tmp_path, monkeypatch):
    monkeypatch.setenv("COACHING_QUARANTINE_LOG", str(tmp_path / "q.jsonl"))
    a = _profile(id="a", content="x" * 4000)
    b = _profile(id="b", content="y" * 4000)
    out = build_context([a, b], token_budget=200)
    assert len(out) <= 1


# ── FR-C06 ──────────────────────────────────────────────────────────────────
def _pep(mode=ExecutionMode.EXPLORATION, strict=True):
    return PolicyEnforcementPoint(
        coach_id="c1",
        coach_to_participants={"c1": {"p1"}},
        mode=mode,
        strict=strict,
    )


def test_pep_allows_authorised(tmp_path, monkeypatch):
    monkeypatch.setenv("COACHING_QUARANTINE_LOG", str(tmp_path / "q.jsonl"))
    pep = _pep()
    kept = pep.filter([_profile()])
    assert len(kept) == 1


def test_pep_blocks_unmapped_participant(tmp_path, monkeypatch):
    monkeypatch.setenv("COACHING_QUARANTINE_LOG", str(tmp_path / "q.jsonl"))
    pep = _pep()
    with pytest.raises(PolicyViolationError):
        pep.filter([_profile(participant_id="other")])


def test_pep_tier_gate_execution_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("COACHING_QUARANTINE_LOG", str(tmp_path / "q.jsonl"))
    pep = _pep(mode=ExecutionMode.EXECUTION)
    silver = _session()  # SILVER
    with pytest.raises(PolicyViolationError):
        pep.filter([silver])


def test_pep_non_strict_drops_silently(tmp_path, monkeypatch):
    monkeypatch.setenv("COACHING_QUARANTINE_LOG", str(tmp_path / "q.jsonl"))
    pep = _pep(mode=ExecutionMode.EXECUTION, strict=False)
    out = pep.filter([_session()])  # SILVER → dropped
    assert out == []


# ── FR-C09 ──────────────────────────────────────────────────────────────────
def test_default_initial_confidence_matches_completeness():
    p = _profile(confidence=0.0)
    assert default_initial_confidence(p) == 1.0


def test_recalibrate_moves_toward_target():
    p = _profile(confidence=0.0)
    event = LineageEvent(object_id=p.id, referenced=True, usefulness=1.0)
    new = recalibrate(p, event)
    assert new.confidence > p.confidence
    assert 0.0 <= new.confidence <= 1.0


# ── FR-C10 ──────────────────────────────────────────────────────────────────
def test_mode_must_match_pep():
    from pipelines.coaching_context.llm_call import call_llm_with_context

    pep = _pep(mode=ExecutionMode.EXPLORATION)
    with pytest.raises(ValueError):
        call_llm_with_context(
            objects=[],
            pep=pep,
            mode=ExecutionMode.EXECUTION,
            user_prompt="hi",
        )
