"""
ERGBootCamp — build_daily_metrics.py
Rebuilds the daily_metrics DuckDB table from workout_sessions.
Also ensures the coaching_tips table exists (via coaching_memory).
"""

import duckdb
from pipelines.config_loader import DB_PATH
from pipelines.coaching_memory import ensure_table as ensure_tips_table


def build_metrics():
    con = duckdb.connect(DB_PATH)

    # DDL also defined in semantic/views.sql — keep in sync
    con.execute("""
    CREATE OR REPLACE TABLE daily_metrics AS
    SELECT
        t.*,
        CASE
            WHEN t.delta > 2 AND t.weekly_load_min > 60 THEN 'fatigue'
            WHEN t.delta > 1 THEN 'caution'
            ELSE 'normal'
        END AS fatigue_flag
    FROM (
        SELECT
            workout_date,
            avg_split_sec,
            duration_sec,
            distance_m,
            LAG(avg_split_sec) OVER (ORDER BY workout_date) AS prev_split,
            avg_split_sec - LAG(avg_split_sec) OVER (ORDER BY workout_date) AS delta,
            AVG(avg_split_sec) OVER (
                ORDER BY workout_date ROWS BETWEEN 1 PRECEDING AND CURRENT ROW
            ) AS rolling_avg_split,
            STDDEV(avg_split_sec) OVER (
                ORDER BY workout_date ROWS BETWEEN 3 PRECEDING AND CURRENT ROW
            ) AS consistency,
            SUM(duration_sec) OVER (
                ORDER BY workout_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
            ) / 60.0 AS weekly_load_min,
            CASE
                WHEN avg_split_sec <= 140 THEN 'race'
                WHEN avg_split_sec <= 145 THEN 'threshold'
                ELSE 'steady'
            END AS session_type
        FROM workout_sessions
        WHERE distance_m >= 500
          AND avg_split_sec <= 300 
    ) t
    """)

    count = con.execute("SELECT COUNT(*) FROM daily_metrics").fetchone()[0]
    con.close()

    print(f"Built daily_metrics table ({count} rows)")


if __name__ == "__main__":
    ensure_tips_table()
    build_metrics()
