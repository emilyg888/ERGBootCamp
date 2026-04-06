"""
ERGBootCamp — coaching context memory.

Persists coach tips in DuckDB so the AI always has recent context,
including session-type tagging (recovery / hard / race) and the
expected-taper flag that tells the model not to penalise slower
splits after a deliberate recovery row.
"""

import json
from datetime import datetime, UTC
from pathlib import Path
import duckdb

from pipelines.config_loader import DB_PATH, COACHING


# ── schema ──────────────────────────────────────────────────────────────────
# DDL also defined in semantic/schema.sql — keep in sync
DDL = """
CREATE TABLE IF NOT EXISTS coaching_tips (
    tip_id       TEXT PRIMARY KEY,
    created_at   TIMESTAMP NOT NULL,
    session_date TEXT,
    author       TEXT NOT NULL,          -- 'coach' | 'athlete'
    tip_text     TEXT NOT NULL,
    tag          TEXT,                   -- recovery|hard|race|technical|nutrition|performance
    session_type TEXT,                   -- declared intent for NEXT session
    expect_taper BOOLEAN DEFAULT FALSE   -- TRUE when next session is flagged as recovery
)
"""


def _connect() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(DB_PATH)


def ensure_table():
    con = _connect()
    con.execute(DDL)
    con.close()


def add_tip(
    tip_text: str,
    author: str = "coach",
    tag: str | None = None,
    session_type: str | None = None,
    session_date: str | None = None,
) -> dict:
    """
    Store a coaching tip.

    If tag == 'recovery' or session_type == 'recovery', sets expect_taper=True
    so the next session's slower splits are treated as intentional.
    """
    ensure_table()

    expect_taper = (tag == "recovery") or (session_type == "recovery")
    tip_id = f"tip_{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}"
    now = datetime.now(UTC)

    con = _connect()
    con.execute(
        """
        INSERT INTO coaching_tips
            (tip_id, created_at, session_date, author, tip_text, tag, session_type, expect_taper)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (tip_id, now, session_date, author, tip_text, tag, session_type, expect_taper),
    )
    con.close()

    return {
        "tip_id": tip_id,
        "created_at": now.isoformat(),
        "author": author,
        "tip_text": tip_text,
        "tag": tag,
        "session_type": session_type,
        "expect_taper": expect_taper,
    }


def get_recent_tips(limit: int | None = None) -> list[dict]:
    """Return recent tips newest-first, capped at coaching.context_window."""
    ensure_table()
    n = limit or COACHING["context_window"]
    con = _connect()
    rows = con.execute(
        """
        SELECT tip_id, created_at, session_date, author, tip_text, tag, session_type, expect_taper
        FROM coaching_tips
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (n,),
    ).fetchall()
    con.close()

    return [
        {
            "tip_id": r[0],
            "created_at": str(r[1]),
            "session_date": r[2],
            "author": r[3],
            "tip_text": r[4],
            "tag": r[5],
            "session_type": r[6],
            "expect_taper": bool(r[7]),
        }
        for r in rows
    ]


def last_taper_flag() -> bool:
    """
    Returns True if the most recent coach tip declared the NEXT session
    as a recovery row (expect_taper=True).  Used by the AI to contextualise
    slower splits.
    """
    ensure_table()
    con = _connect()
    row = con.execute(
        """
        SELECT expect_taper
        FROM coaching_tips
        WHERE author = 'coach'
        ORDER BY created_at DESC
        LIMIT 1
        """
    ).fetchone()
    con.close()
    return bool(row[0]) if row else False


def build_context_block(tips: list[dict]) -> str:
    """Format recent tips into a readable block for the LLM prompt."""
    if not tips:
        return "(No previous coaching context available)"

    lines = []
    for t in reversed(tips):  # chronological order for the model
        who = "Coach" if t["author"] == "coach" else "Athlete"
        taper = " [TAPER EXPECTED — recovery row]" if t["expect_taper"] else ""
        tag = f" [{t['tag']}]" if t["tag"] else ""
        lines.append(f"[{t['created_at'][:16]}] {who}{tag}{taper}: {t['tip_text']}")

    return "\n".join(lines)
