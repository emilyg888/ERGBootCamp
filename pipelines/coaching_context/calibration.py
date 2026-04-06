"""
FR-C09 — Confidence calibration.

On first ingestion `confidence` defaults to `completeness_ratio(obj)`.
Each LLM interaction that references the object triggers a lineage
update via `recalibrate(obj, lineage_event)`. The recalculation is
delegated to a pluggable scorer (`fr_009_scoring_model`) so the existing
FR-009 model can be wired in once available; until then a defensible
default — exponential moving average between current confidence and
completeness × usefulness — is provided.

Calibration runs may be triggered manually via the CLI:

    python -m pipelines.coaching_context.calibration --object-id <id>
    python -m pipelines.coaching_context.calibration --all
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from typing import Callable, Iterable

from .models import CoachingEntity
from .scoring import completeness_ratio

_LOG = logging.getLogger("coaching_context.calibration")

EMA_ALPHA = 0.3  # weight given to the new observation


@dataclass(frozen=True)
class LineageEvent:
    """A single LLM interaction that referenced an entity."""

    object_id: str
    referenced: bool
    usefulness: float = 1.0  # 0..1; 1 = used directly in the response


def default_initial_confidence(obj: CoachingEntity) -> float:
    """FR-C09: confidence defaults to completeness on first ingest."""
    return completeness_ratio(obj)


# ── pluggable hook for the existing FR-009 scoring model ───────────────────
ScoringFn = Callable[[CoachingEntity, LineageEvent], float]


def _ema_recalibration(obj: CoachingEntity, event: LineageEvent) -> float:
    """Default lineage recalibration until FR-009's scorer is wired in."""
    target = completeness_ratio(obj) * (event.usefulness if event.referenced else 0.0)
    return (1 - EMA_ALPHA) * float(obj.confidence) + EMA_ALPHA * target


fr_009_scoring_model: ScoringFn = _ema_recalibration


def recalibrate(
    obj: CoachingEntity,
    event: LineageEvent,
    scorer: ScoringFn | None = None,
) -> CoachingEntity:
    """
    Returns a new CoachingEntity (models are frozen) with updated
    confidence. Persistence is the caller's responsibility.
    """
    fn = scorer or fr_009_scoring_model
    new_confidence = max(0.0, min(1.0, fn(obj, event)))
    return obj.model_copy(update={"confidence": new_confidence})


def recalibrate_batch(
    objects: Iterable[CoachingEntity],
    events_by_id: dict[str, LineageEvent],
    scorer: ScoringFn | None = None,
) -> list[CoachingEntity]:
    out: list[CoachingEntity] = []
    for obj in objects:
        event = events_by_id.get(obj.id)
        if event is None:
            out.append(obj)
            continue
        out.append(recalibrate(obj, event, scorer))
    return out


# ── CLI ────────────────────────────────────────────────────────────────────
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="coaching_context.calibration",
        description="Trigger confidence calibration runs (FR-C09).",
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--object-id", help="Recalibrate a single object")
    g.add_argument("--all", action="store_true", help="Recalibrate every known object")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute new confidences but do not persist",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    # Persistence is intentionally left to the caller's storage layer.
    # This CLI is the trigger surface required by FR-C09; concrete
    # loading/saving is wired in by the pipeline that owns the store.
    _LOG.info(
        "calibration requested: object_id=%s all=%s dry_run=%s",
        args.object_id,
        args.all,
        args.dry_run,
    )
    _LOG.info(
        "No persistent store is bound to coaching_context yet — wire "
        "load_objects()/save_objects() into this entrypoint when the "
        "coaching entity store lands."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
