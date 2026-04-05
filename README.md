# ERGBootCamp 🚣

Personal indoor rowing coach — Concept2 logbook + Qwen2.5-14B via LMStudio +
Garmin recovery signals + WhatsApp daily brief via Twilio.

## Quick start

```bash
# 1. Clone / unzip and enter the project
cd ERGBootCamp

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 3. Copy and fill in secrets
cp config/.env.example config/.env
#    → add C2_API_TOKEN, OPENAI_API_KEY=lm-studio,
#       TWILIO_*, GARMIN_EMAIL, GARMIN_PASSWORD

# 4. Start LMStudio with Qwen2.5-14B-Instruct Q6_K loaded
#    (server on http://localhost:1234)

# 5. Run the pipeline
bash scripts/run_pipeline.sh

# 6. Open the dashboard
streamlit run pipelines/dashboard.py
```

## Install 06:30 WhatsApp brief (macOS launchd)

```bash
bash scripts/install_launchd.sh
```

Trigger manually anytime:

```bash
launchctl start com.ergbootcamp.daily_brief
# or
python pipelines/send_whatsapp.py
```

## Architecture

```
ERGBootCamp/
├── config/
│   ├── .env                  ← secrets (never commit)
│   ├── .env.example
│   └── settings.yaml         ← all tunable config
│
├── pipelines/
│   ├── config_loader.py      ← single source of truth for all config
│   ├── coaching_memory.py    ← DuckDB-backed tip store with taper flags
│   ├── pull_concept2.py      ← Concept2 logbook API sync
│   ├── import_garmin.py      ← Garmin Connect recovery signals
│   ├── build_daily_metrics.py
│   ├── generate_coaching.py  ← Qwen2.5-14B via LMStudio
│   ├── generate_daily_brief.py
│   ├── send_whatsapp.py      ← Twilio WhatsApp Sandbox
│   └── dashboard.py          ← Streamlit UI
│
├── coaching/
│   ├── briefs/daily/         ← dated .txt briefs + latest.txt
│   └── prompts/
│
├── data/
│   ├── coaching_output.json
│   └── garmin_latest.json
│
├── db/
│   └── rowing.duckdb         ← all data: workouts, metrics, garmin, tips
│
├── launchd/
│   └── com.ergbootcamp.daily_brief.plist
│
├── scripts/
│   ├── install_launchd.sh
│   ├── run_pipeline.sh
│   └── start_dashboard.sh
│
└── logs/
    ├── daily_brief.log
    └── daily_brief_err.log
```

## Key features

### Coaching memory with taper awareness
Every coaching tip is stored in DuckDB with a `expect_taper` flag.
When you tag the next session as a **recovery row**, the AI automatically
knows that slower splits are intentional and will praise consistency
rather than flag a performance drop.

Quick-tag buttons in the dashboard:
- 🔵 Recovery row → sets `expect_taper=True`
- 🟡 Hard effort
- 🟢 Race simulation

### LMStudio (Qwen2.5-14B-Instruct Q6_K)
All AI calls use the OpenAI-compatible endpoint at `http://localhost:1234/v1`.
No cloud API key needed for inference — set `OPENAI_API_KEY=lm-studio` as a dummy.

To change the model, edit `config/settings.yaml`:
```yaml
lmstudio:
  model: "qwen2.5-14b-instruct-q6_k"   # must match LMStudio model name
  base_url: "http://localhost:1234/v1"
```

### Garmin Connect recovery signals
`import_garmin.py` pulls: Body Battery, HRV Status, Sleep Score,
Resting HR, Stress Level, Readiness. These feed into:
- The coaching prompt (AI adjusts prescription if battery < 70)
- The Recovery tab scatter plot (body battery vs split correlation)
- Auto-taper: if body battery < 70, target split is relaxed +4s

### Twilio WhatsApp Sandbox setup
1. Go to console.twilio.com → Messaging → Try it out → WhatsApp
2. Follow sandbox join instructions (text a code to +1 415 523 8886)
3. Add your number as `TWILIO_WHATSAPP_TO=whatsapp:+61XXXXXXXXX` in `.env`
4. Briefs are sent from the sandbox number (free, no approval needed)

### launchd schedule (macOS)
The `install_launchd.sh` script installs a LaunchAgent that fires at
06:30 every morning. It runs the full pipeline in order:
1. `pull_concept2.py` — fetch overnight Concept2 sessions
2. `import_garmin.py` — fetch Garmin overnight recovery data
3. `build_daily_metrics.py` — rebuild DuckDB metrics view
4. `send_whatsapp.py` — generate brief via LMStudio + send via Twilio

Logs: `logs/daily_brief.log` and `logs/daily_brief_err.log`

## Troubleshooting

| Problem | Fix |
|---|---|
| `Connection refused localhost:1234` | Start LMStudio server first |
| `Missing C2_API_TOKEN` | Add token to `config/.env` |
| `Twilio AuthenticationError` | Check SID + auth token in `.env` |
| `Garmin NotImplementedError` | Add `GARMIN_EMAIL` + `GARMIN_PASSWORD` to `.env` |
| `No data` in dashboard | Run `bash scripts/run_pipeline.sh` first |
| launchd not firing | `launchctl list \| grep ergbootcamp` — check exit codes |
