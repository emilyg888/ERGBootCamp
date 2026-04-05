#!/bin/bash
# ERGBootCamp — run_pipeline.sh
set -e

cd "$(dirname "$0")/.."
source .venv/bin/activate

echo "=== ERGBootCamp Pipeline === $(date)"

echo "--- Syncing Concept2 workouts ---"
python pipelines/pull_concept2.py

echo "--- Importing Garmin data ---"
python pipelines/import_garmin.py 2>/dev/null || echo "(Garmin skipped)"

echo "--- Building daily metrics ---"
python pipelines/build_daily_metrics.py

echo "--- Generating coaching insight ---"
python pipelines/generate_coaching.py

echo "--- Sending Discord brief ---"
python pipelines/send_discord.py

echo ""
echo "Pipeline complete. Dashboard: streamlit run pipelines/dashboard.py"
