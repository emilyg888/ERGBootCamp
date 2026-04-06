"""
FR-C07 — Constrained LLM call.

The LLM only ever receives:
  - a fixed system prompt (below), and
  - a JSON-serialised list of pre-validated, read-only context objects.

No raw DB rows, no free-form retrieved text, no write paths. The PEP
(FR-C06) runs as a blocking filter before the call; if it raises
PolicyViolationError, the call does not happen.
"""

from __future__ import annotations

import json
from types import MappingProxyType
from typing import Any, Optional

from .injector import build_context
from .models import CoachingEntity
from .modes import ExecutionMode
from .pep import PolicyEnforcementPoint

SYSTEM_PROMPT = (
    "You are receiving pre-validated coaching context. "
    "Do not infer, hallucinate, or extrapolate beyond the provided objects."
)


def _freeze(payload: list[dict]) -> tuple[MappingProxyType, ...]:
    """Return a read-only view so downstream code cannot mutate it in place."""
    return tuple(MappingProxyType(dict(p)) for p in payload)


def call_llm_with_context(
    *,
    objects: list[CoachingEntity],
    pep: PolicyEnforcementPoint,
    mode: ExecutionMode,
    user_prompt: str,
    token_budget: int = 4000,
    llm_client: Optional[Any] = None,
    model: Optional[str] = None,
) -> dict:
    """
    Run PEP → injector → LLM. The LLM client is optional so the function
    can be exercised in tests without a live model. If `llm_client` is
    None, the assembled request payload is returned and no call is made.
    """
    if pep.mode is not mode:
        raise ValueError(
            f"PEP mode {pep.mode} does not match requested mode {mode}; "
            "mode must be explicitly declared per task (FR-C10)."
        )

    # FR-C06 — blocking filter. Raises PolicyViolationError on denial.
    cleared = pep.filter(objects)

    # FR-C05 — build the typed, budget-bounded context list.
    context_payload = build_context(cleared, token_budget=token_budget)

    # FR-C07 — read-only freeze, JSON serialisation, fixed system prompt.
    frozen = _freeze(context_payload)
    serialised_context = json.dumps([dict(p) for p in frozen], default=str)

    request = {
        "system": SYSTEM_PROMPT,
        "user": user_prompt,
        "context": serialised_context,
        "mode": mode.value,
    }

    if llm_client is None:
        return {"request": request, "response": None}

    completion = llm_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "system",
                "content": f"COACHING_CONTEXT_JSON: {serialised_context}",
            },
            {"role": "user", "content": user_prompt},
        ],
    )
    return {"request": request, "response": completion}
