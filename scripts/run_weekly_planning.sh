#!/bin/bash
# ERGBootCamp — run_weekly_planning.sh
set -e

cd "$(dirname "$0")/.."
source .venv/bin/activate

echo "=== ERGBootCamp Weekly Planning === $(date)"

echo "--- Syncing Concept2 workouts ---"
python pipelines/pull_concept2.py

echo "--- Importing Garmin data ---"
python pipelines/import_garmin.py 2>/dev/null || echo "(Garmin skipped)"

echo "--- Building daily metrics ---"
python pipelines/build_daily_metrics.py

echo "--- Generating weekly plan ---"
python pipelines/generate_weekly_plan.py

echo ""
echo "Weekly planning complete. Dashboard: streamlit run pipelines/dashboard.py"
