Concept2 → Data platform → Semantic layer → AI coaching

/Users/emilygao/Projects/concept2-coaching-lab/.codex/pyproject.toml

Mac starts / scheduled time
        ↓
run_pipeline.sh
        ↓
data updated
        ↓
dashboard always ready

pull_concept2.py          → data ingestion

build_daily_metrics.py    → compute features (SQL layer)

generate_daily_brief.py   → produce clean JSON summary

generate_coaching.py      → LLM reasoning

dashboard.py              → visualization

[Concept2 Sync]
        ↓
[daily_metrics]
        ↓
[generate_coaching.py]
        ↓
📦 coaching_output.json   ← SINGLE SOURCE OF TRUTH
        ↓
[Streamlit dashboard]

✅ What pull_concept2.py should do (v1)

Keep it simple:

Responsibilities:
Call Concept2 API
Parse response
Insert into workout_sessions
Upsert (no duplicates)

concept2-coaching-lab/
├── README.md
├── data/
│ ├── raw/
│ │ ├── concept2/
│ │ ├── garmin/
│ │ └── manual/
│ ├── processed/
│ └── snapshots/
├── db/
│ └── rowing.duckdb
├── pipelines/
│ ├── pull_concept2.py
│ ├── import_garmin.py
│ ├── ingest_manual_metrics.py
│ ├── build_daily_metrics.py
│ └── generate_daily_brief.py
├── semantic/
│ ├── schema.sql
│ ├── views.sql
│ └── metrics_definitions.yaml
├── coaching/
│ ├── prompts/
│ │ ├── daily_coach_prompt.md
│ │ └── weekly_review_prompt.md
│ ├── briefs/
│ │ ├── daily/
│ │ └── weekly/
│ └── plans/
├── notebooks/
│ ├── training_trends.ipynb
│ └── race_prediction.ipynb
├── outputs/
│ ├── charts/
│ └── reports/
├── config/
│ ├── .env
│ └── settings.yaml
└── tests/
