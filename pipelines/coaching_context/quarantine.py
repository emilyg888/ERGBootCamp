"""
FR-C08 — Quarantine log.

Structured JSONL log of every exclusion: completeness-below-threshold,
PEP access denied, and budget truncation. Records are queryable and
auto-pruned after 30 days on every write.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional

_LOG = logging.getLogger("coaching_context.quarantine")

# Resolve relative to ERGBootCamp project root
_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_PATH = _ROOT / "logs" / "coaching_quarantine.jsonl"
_RETENTION_DAYS = 30


VALID_REASONS = {
    "completeness_below_threshold",
    "pep_access_denied",
    "pep_tier_gate",
    "budget_truncation",
}


def _log_path() -> Path:
    override = os.getenv("COACHING_QUARANTINE_LOG")
    return Path(override) if override else _DEFAULT_PATH


def _ensure_parent(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)


def write(
    *,
    object_id: str,
    entity_type: str,
    reason_code: str,
    priority_score: float,
    extra: Optional[dict] = None,
) -> None:
    if reason_code not in VALID_REASONS:
        raise ValueError(f"Unknown quarantine reason_code: {reason_code!r}")
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "object_id": object_id,
        "entity_type": entity_type,
        "reason_code": reason_code,
        "priority_score": float(priority_score),
    }
    if extra:
        record["extra"] = extra

    path = _log_path()
    _ensure_parent(path)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    _prune(path)


def _prune(path: Path) -> None:
    """Drop entries older than _RETENTION_DAYS. Cheap rewrite — fine for JSONL."""
    if not path.exists():
        return
    cutoff = datetime.now(timezone.utc) - timedelta(days=_RETENTION_DAYS)
    kept: list[str] = []
    changed = False
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            try:
                ts = datetime.fromisoformat(json.loads(line)["timestamp"])
            except (ValueError, KeyError, json.JSONDecodeError):
                kept.append(line)
                continue
            if ts >= cutoff:
                kept.append(line)
            else:
                changed = True
    if changed:
        with path.open("w", encoding="utf-8") as f:
            f.write("\n".join(kept) + ("\n" if kept else ""))


def query(
    *,
    reason_code: Optional[str] = None,
    entity_type: Optional[str] = None,
    since: Optional[datetime] = None,
) -> Iterable[dict]:
    path = _log_path()
    if not path.exists():
        return []
    out: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if reason_code and rec.get("reason_code") != reason_code:
                continue
            if entity_type and rec.get("entity_type") != entity_type:
                continue
            if since:
                try:
                    ts = datetime.fromisoformat(rec["timestamp"])
                except (ValueError, KeyError):
                    continue
                if ts < since:
                    continue
            out.append(rec)
    return out


# Public alias for the namespace-style import in __init__.py
class _QuarantineLog:
    write = staticmethod(write)
    query = staticmethod(query)


quarantine_log = _QuarantineLog()
