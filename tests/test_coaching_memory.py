"""Tests for pipelines.coaching_memory — taper logic and tip storage."""

import pytest
from unittest.mock import patch

import duckdb


@pytest.fixture()
def isolated_db(tmp_path):
    """Patch DB_PATH to a temporary DuckDB file so tests are isolated."""
    db_file = str(tmp_path / "test.duckdb")
    with patch("pipelines.coaching_memory.DB_PATH", db_file):
        # Ensure the table exists in the temp DB
        from pipelines.coaching_memory import ensure_table
        ensure_table()
        yield db_file


def test_add_tip_stores_and_returns(isolated_db):
    from pipelines.coaching_memory import add_tip

    result = add_tip(tip_text="Row easy tomorrow", author="coach", tag="technical")
    assert result["tip_text"] == "Row easy tomorrow"
    assert result["author"] == "coach"
    assert result["tag"] == "technical"
    assert "tip_id" in result
    assert "created_at" in result


def test_add_tip_recovery_sets_taper_true(isolated_db):
    from pipelines.coaching_memory import add_tip

    result = add_tip(tip_text="Recovery row next", author="coach", tag="recovery")
    assert result["expect_taper"] is True


def test_add_tip_performance_sets_taper_false(isolated_db):
    from pipelines.coaching_memory import add_tip

    result = add_tip(tip_text="Great effort", author="coach", tag="performance")
    assert result["expect_taper"] is False


def test_last_taper_flag_returns_false_when_empty(isolated_db):
    from pipelines.coaching_memory import last_taper_flag

    assert last_taper_flag() is False


def test_last_taper_flag_returns_true_after_recovery(isolated_db):
    from pipelines.coaching_memory import add_tip, last_taper_flag

    add_tip(tip_text="Recovery row", author="coach", tag="recovery")
    assert last_taper_flag() is True


def test_last_taper_flag_returns_false_after_non_recovery_follows(isolated_db):
    from pipelines.coaching_memory import add_tip, last_taper_flag

    add_tip(tip_text="Recovery row", author="coach", tag="recovery")
    add_tip(tip_text="Hard effort", author="coach", tag="performance")
    assert last_taper_flag() is False


def test_get_recent_tips_newest_first_capped(isolated_db):
    from pipelines.coaching_memory import add_tip, get_recent_tips

    for i in range(5):
        add_tip(tip_text=f"Tip {i}", author="coach", tag="technical")

    tips = get_recent_tips(limit=3)
    assert len(tips) == 3
    # newest first — Tip 4 should be first
    assert tips[0]["tip_text"] == "Tip 4"
    assert tips[1]["tip_text"] == "Tip 3"
    assert tips[2]["tip_text"] == "Tip 2"


def test_build_context_block_empty(isolated_db):
    from pipelines.coaching_memory import build_context_block

    result = build_context_block([])
    assert result == "(No previous coaching context available)"


def test_build_context_block_includes_taper_label(isolated_db):
    from pipelines.coaching_memory import build_context_block

    tips = [
        {
            "tip_id": "tip_1",
            "created_at": "2026-03-21T10:00:00",
            "session_date": None,
            "author": "coach",
            "tip_text": "Recovery next",
            "tag": "recovery",
            "session_type": None,
            "expect_taper": True,
        }
    ]
    result = build_context_block(tips)
    assert "[TAPER EXPECTED" in result
