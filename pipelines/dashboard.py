"""
ERGBootCamp — dashboard.py  (Streamlit)

Run with:  streamlit run pipelines/dashboard.py
"""

import html as _html
import json
import os
import re as _re
import subprocess
import sys
import time
from pathlib import Path
from datetime import date, datetime, timezone

import duckdb
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

# ── path bootstrap ────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipelines.config_loader import DB_PATH, LM_MODEL, ATHLETE, COACHING, DATA_ROOT, fmt_split as _fmt_split
from pipelines.coaching_memory import (
    get_recent_tips, add_tip, last_taper_flag, build_context_block,
)

# ── page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ERGBootCamp",
    page_icon="🚣",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;500;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'Syne', sans-serif !important;
}
.stApp { background-color: #0a0e1a; color: #f0f4ff; }

/* top brand bar */
.brand-bar {
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 0 18px 0; border-bottom: 1px solid rgba(255,255,255,0.08);
    margin-bottom: 20px;
}
.brand-name { font-size: 22px; font-weight: 700; color: #00e5b4; letter-spacing: -0.5px; }
.brand-name span { color: #f0f4ff; }
.brand-sub { font-size: 11px; color: #7a8ba8; font-family: 'JetBrains Mono', monospace; margin-top: 2px; }
.model-badge {
    background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1);
    border-radius: 20px; font-size: 10px; padding: 3px 10px;
    font-family: 'JetBrains Mono', monospace; color: #7a8ba8;
}

/* metric cards */
.kpi-card {
    background: #111827; border: 1px solid rgba(255,255,255,0.07);
    border-radius: 10px; padding: 16px; position: relative; overflow: hidden;
}
.kpi-label { font-size: 10px; color: #7a8ba8; font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.8px; text-transform: uppercase; margin-bottom: 6px; }
.kpi-value { font-size: 26px; font-weight: 700; font-family: 'JetBrains Mono', monospace;
    line-height: 1.1; }
.kpi-delta { font-size: 11px; font-family: 'JetBrains Mono', monospace; margin-top: 3px; }
.kpi-teal { color: #00e5b4; } .kpi-blue { color: #3b82f6; }
.kpi-amber { color: #f59e0b; } .kpi-red { color: #ef4444; } .kpi-purple { color: #a78bfa; }

/* countdown */
.countdown-card {
    background: #111827; border: 1px solid rgba(239,68,68,0.2);
    border-radius: 10px; padding: 16px; display: flex;
    align-items: center; justify-content: space-between;
}
.countdown-num { font-size: 32px; font-weight: 700; font-family: 'JetBrains Mono', monospace;
    color: #ef4444; line-height: 1; }
.countdown-unit-label { font-size: 9px; color: #7a8ba8;
    font-family: 'JetBrains Mono', monospace; }
.phase-pill {
    background: rgba(245,158,11,0.12); border: 1px solid rgba(245,158,11,0.25);
    border-radius: 20px; padding: 4px 12px; font-size: 11px;
    font-family: 'JetBrains Mono', monospace; color: #fbbf24; display: inline-block;
}

/* chat tip items */
.tip-coach {
    background: #1a2234; border: 1px solid rgba(255,255,255,0.07);
    border-radius: 8px; padding: 10px 14px; margin-bottom: 8px;
}
.tip-athlete {
    background: rgba(0,229,180,0.05); border: 1px solid rgba(0,229,180,0.15);
    border-radius: 8px; padding: 10px 14px; margin-bottom: 8px;
}
.tip-who { font-size: 9px; color: #7a8ba8; font-family: 'JetBrains Mono', monospace;
    text-transform: uppercase; letter-spacing: 0.8px; }
.tip-time { font-size: 9px; color: #7a8ba8; font-family: 'JetBrains Mono', monospace; }
.tip-body { font-size: 13px; line-height: 1.55; margin-top: 5px; }
.taper-badge {
    display: inline-block; margin-top: 6px; font-size: 10px; padding: 2px 8px;
    border-radius: 10px; background: rgba(59,130,246,0.12);
    border: 1px solid rgba(59,130,246,0.25); color: #60a5fa;
    font-family: 'JetBrains Mono', monospace;
}

/* recovery cards */
.rec-card {
    background: #1a2234; border: 1px solid rgba(255,255,255,0.07);
    border-radius: 8px; padding: 12px; text-align: center;
}
.rec-val-good { color: #00e5b4; font-size: 22px; font-weight: 700;
    font-family: 'JetBrains Mono', monospace; }
.rec-val-warn { color: #f59e0b; font-size: 22px; font-weight: 700;
    font-family: 'JetBrains Mono', monospace; }
.rec-val-bad  { color: #ef4444; font-size: 22px; font-weight: 700;
    font-family: 'JetBrains Mono', monospace; }
.rec-label { font-size: 9px; color: #7a8ba8; font-family: 'JetBrains Mono', monospace;
    text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 4px; }

/* section headers */
.section-hdr {
    font-size: 10px; color: #7a8ba8; font-family: 'JetBrains Mono', monospace;
    letter-spacing: 1.5px; text-transform: uppercase; margin: 18px 0 10px 0;
    border-bottom: 1px solid rgba(255,255,255,0.05); padding-bottom: 6px;
}
.stButton > button {
    background: transparent; border: 1px solid rgba(255,255,255,0.15);
    color: #f0f4ff; border-radius: 8px; font-family: 'Syne', sans-serif;
    transition: all 0.2s;
}
.stButton > button:hover { border-color: #00e5b4; color: #00e5b4; }

/* ── coaching note form: radio-as-pills ──────────────────────────────── */
/* pill row for Tag and Author */
div[data-testid="stRadio"] > label {
    font-size: 11px; color: #7a8ba8;
    font-family: 'JetBrains Mono', monospace; text-transform: uppercase;
    letter-spacing: 0.8px;
}
div[data-testid="stRadio"] > div[role="radiogroup"] {
    gap: 8px;
    flex-wrap: wrap;
}
div[data-testid="stRadio"] > div[role="radiogroup"] > label {
    border: 1px solid rgba(255,255,255,0.15) !important;
    border-radius: 20px !important;
    padding: 4px 14px !important;
    font-size: 12px !important;
    font-family: 'JetBrains Mono', monospace !important;
    color: #9aafc7 !important;
    background: transparent !important;
    cursor: pointer;
    transition: all 0.15s;
}
div[data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) {
    border-color: #00e5b4 !important;
    color: #00e5b4 !important;
    background: rgba(0,229,180,0.10) !important;
}
/* hide the circle radio dot */
div[data-testid="stRadio"] > div[role="radiogroup"] > label > div:first-child {
    display: none !important;
}
</style>
""", unsafe_allow_html=True)


# ── helpers ───────────────────────────────────────────────────────────────────
def fmt_split(sec) -> str:
    return _fmt_split(sec, suffix="")


def days_to_competition() -> int:
    comp = datetime.strptime(ATHLETE["competition_date"], "%Y-%m-%d").date()
    return max((comp - date.today()).days, 0)


def load_db():
    try:
        con = duckdb.connect(DB_PATH, read_only=True)
    except Exception:
        return pd.DataFrame(), pd.DataFrame()
    try:
        df = con.execute("SELECT * FROM daily_metrics ORDER BY workout_date").fetchdf()
    except Exception:
        df = pd.DataFrame()
    try:
        garmin_df = con.execute(
            "SELECT * FROM garmin_daily ORDER BY record_date DESC LIMIT 7"
        ).fetchdf()
    except Exception:
        garmin_df = pd.DataFrame()
    con.close()
    return df, garmin_df


def load_coaching_output():
    p = DATA_ROOT / "data" / "coaching_output.json"
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return {}


def _coaching_summary_dt(coaching_output: dict) -> datetime | None:
    summary_date = coaching_output.get("summary", {}).get("date")
    if not summary_date:
        return None
    try:
        return datetime.fromisoformat(str(summary_date))
    except ValueError:
        return None


def load_weekly_plan():
    p = DATA_ROOT / "data" / "snapshots" / "weekly_plan.json"
    if p.exists():
        try:
            with open(p) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None
    return None


def load_garmin_cache():
    p = DATA_ROOT / "data" / "garmin_latest.json"
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return {}


def plotly_defaults() -> dict:
    return dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#7a8ba8", size=11),
        margin=dict(l=10, r=10, t=10, b=10),
    )


def _job_recent(state_key: str, ttl_seconds: int) -> bool:
    started_at = st.session_state.get(state_key)
    if started_at is None:
        return False
    return (datetime.now(timezone.utc) - started_at).total_seconds() < ttl_seconds


def _file_mtime(path: Path) -> datetime | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def _launch_background_script(script_name: str, stdout_name: str, stderr_name: str):
    script_path = ROOT / "scripts" / script_name
    log_dir = DATA_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)

    with open(log_dir / stdout_name, "ab") as stdout_handle, open(log_dir / stderr_name, "ab") as stderr_handle:
        subprocess.Popen(
            ["/bin/bash", str(script_path)],
            cwd=ROOT,
            env=env,
            stdout=stdout_handle,
            stderr=stderr_handle,
            start_new_session=True,
        )


# ── load data ─────────────────────────────────────────────────────────────────
df, garmin_df = load_db()
coaching_output = load_coaching_output()
garmin          = load_garmin_cache()
weekly_snapshot_path = DATA_ROOT / "data" / "snapshots" / "weekly_plan.json"
weekly_snapshot_mtime = _file_mtime(weekly_snapshot_path)

# Auto-detect external file changes and rerun to pick up fresh data
_prev_mtime = st.session_state.get("_weekly_snapshot_mtime_seen")
if weekly_snapshot_mtime is not None and _prev_mtime is not None and weekly_snapshot_mtime > _prev_mtime:
    st.session_state["_weekly_snapshot_mtime_seen"] = weekly_snapshot_mtime
    st.rerun()
if weekly_snapshot_mtime is not None:
    st.session_state["_weekly_snapshot_mtime_seen"] = weekly_snapshot_mtime

weekly_plan     = load_weekly_plan()
latest = df.iloc[-1] if not df.empty else None

# ── brand bar ─────────────────────────────────────────────────────────────────
days_left = days_to_competition()
training_day = (date.today() - datetime.strptime(ATHLETE["training_start"], "%Y-%m-%d").date()).days
run_now_active = _job_recent("run_now_requested_at", 120)
weekly_requested_at = st.session_state.get("weekly_plan_requested_at")
weekly_completed = (
    weekly_requested_at is not None
    and weekly_snapshot_mtime is not None
    and weekly_snapshot_mtime >= weekly_requested_at
)
if weekly_completed:
    st.session_state["weekly_plan_requested_at"] = None
    if st.session_state.get("weekly_plan_completed_at") != weekly_snapshot_mtime:
        st.session_state["weekly_plan_completed_at"] = weekly_snapshot_mtime
        st.toast("Weekly planning finished. The training plan has been refreshed.")
        # Force a clean rerun so every tab re-reads the fresh snapshot
        st.rerun()

weekly_active = (
    weekly_requested_at is not None
    and not weekly_completed
    and _job_recent("weekly_plan_requested_at", 600)
)

if weekly_active:
    st.caption("Weekly planning is running. This page will refresh automatically.")
    time.sleep(3)
    st.rerun()

brand_col, run_col, weekly_col, badge_col = st.columns([6.5, 1.3, 1.8, 1.4], vertical_alignment="bottom")

with brand_col:
    st.markdown(f"""
    <div class="brand-bar" style="border-bottom:none;margin-bottom:0;padding:10px 0 0 0">
      <div>
        <div class="brand-name">ERG<span>BootCamp</span></div>
        <div class="brand-sub">Day {training_day} of 210 &nbsp;·&nbsp; {ATHLETE['goal']}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

with run_col:
    if st.button(
        "Running..." if run_now_active else "Run Now",
        key="header_run_now",
        use_container_width=True,
        type="primary",
        help="Kick off the full end-to-end refresh pipeline.",
    ):
        try:
            _launch_background_script(
                "run_pipeline.sh",
                "dashboard_run_now.log",
                "dashboard_run_now_err.log",
            )
            st.session_state["run_now_requested_at"] = datetime.now(timezone.utc)
            st.toast("End-to-end refresh started. Check logs/dashboard_run_now.log in about 2 minutes.")
            st.rerun()
        except Exception as e:
            st.error(f"Could not start refresh: {e}")

with weekly_col:
    if st.button(
        "Planning..." if weekly_active else "Weekly Planning",
        key="header_weekly_plan",
        use_container_width=True,
        help="Sync data, rebuild metrics, and generate the weekly plan.",
    ):
        try:
            _launch_background_script(
                "run_weekly_planning.sh",
                "dashboard_weekly_planning.log",
                "dashboard_weekly_planning_err.log",
            )
            st.session_state["weekly_plan_requested_at"] = datetime.now(timezone.utc)
            st.toast("Weekly planning started. Check logs/dashboard_weekly_planning.log in a few minutes.")
            st.rerun()
        except Exception as e:
            st.error(f"Could not start weekly planning: {e}")

with badge_col:
    st.markdown(
        f'<div style="display:flex;justify-content:flex-end;padding-top:14px"><span class="model-badge">{LM_MODEL}</span></div>',
        unsafe_allow_html=True,
    )

st.markdown(
    '<div style="border-bottom:1px solid rgba(255,255,255,0.08);margin:8px 0 20px 0"></div>',
    unsafe_allow_html=True,
)

# ── tabs ──────────────────────────────────────────────────────────────────────
tab_overview, tab_sessions, tab_training, tab_recovery, tab_coach = st.tabs(
    ["📊 Overview", "🗓 Sessions", "📋 Training Plan", "💚 Recovery", "🧠 Coach"]
)


# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — OVERVIEW
# ════════════════════════════════════════════════════════════════════════════
with tab_overview:

    # countdown row
    hrs = (days_left * 24) % 24
    col_c1, col_c2, col_c3, col_c4 = st.columns([1, 1, 1, 1])
    with col_c1:
        st.markdown(f"""<div class="countdown-card">
          <div>
            <div class="rec-label">Competition Countdown</div>
            <div style="display:flex;gap:16px;margin-top:6px">
              <div><div class="countdown-num">{days_left}</div><div class="countdown-unit-label">days</div></div>
            </div>
          </div>
          <div><span class="phase-pill">Base Building · Wk 6</span></div>
        </div>""", unsafe_allow_html=True)

    if latest is not None:
        split_sec = float(latest["avg_split_sec"])
        delta_v = float(latest["delta"]) if latest["delta"] is not None else 0
        arrow = "↑" if delta_v < 0 else "↓"
        delta_color = "kpi-teal" if delta_v < 0 else "kpi-red"

        with col_c2:
            st.markdown(f"""<div class="kpi-card">
              <div class="kpi-label">Today's Split</div>
              <div class="kpi-value kpi-teal">{fmt_split(split_sec)}</div>
              <div class="kpi-delta {delta_color}">{arrow} {abs(delta_v):.1f}s vs prev</div>
            </div>""", unsafe_allow_html=True)

        weekly = float(latest["weekly_load_min"]) if latest["weekly_load_min"] is not None else 0
        with col_c3:
            st.markdown(f"""<div class="kpi-card">
              <div class="kpi-label">Weekly Load</div>
              <div class="kpi-value kpi-amber">{weekly:.0f} min</div>
              <div class="kpi-delta" style="color:#7a8ba8">{int(latest['distance_m'])}m last row</div>
            </div>""", unsafe_allow_html=True)

        bb = garmin.get("body_battery")
        bb_color = "kpi-teal" if (bb or 0) >= 70 else ("kpi-amber" if (bb or 0) >= 50 else "kpi-red")
        with col_c4:
            st.markdown(f"""<div class="kpi-card">
              <div class="kpi-label">Body Battery</div>
              <div class="kpi-value {bb_color}">{bb if bb else '—'}</div>
              <div class="kpi-delta" style="color:#7a8ba8">Garmin recovery signal</div>
            </div>""", unsafe_allow_html=True)

    st.markdown('<div class="section-hdr">Split Trend — last sessions</div>', unsafe_allow_html=True)

    if not df.empty:
        fig = go.Figure()
        # colour-code recovery vs hard sessions
        session_colors = df["session_type"].map(
            {"steady": "#3b82f6", "threshold": "#f59e0b", "race": "#ef4444"}
        ).fillna("#7a8ba8")

        fig.add_trace(go.Scatter(
            x=df["workout_date"], y=df["avg_split_sec"],
            mode="lines+markers",
            line=dict(color="#00e5b4", width=2),
            marker=dict(color=session_colors, size=8, line=dict(color="#0a0e1a", width=1)),
            name="Split",
            hovertemplate="<b>%{x|%b %d}</b><br>Split: %{customdata}<br><extra></extra>",
            customdata=[fmt_split(v) for v in df["avg_split_sec"]],
        ))
        fig.add_trace(go.Scatter(
            x=df["workout_date"], y=df["rolling_avg_split"],
            mode="lines", line=dict(color="#7a8ba8", width=1, dash="dot"),
            name="Rolling avg",
        ))
        fig.update_yaxes(
            autorange="reversed",
            gridcolor="rgba(255,255,255,0.04)",
            tickformat=".0f",
            ticksuffix="s",
        )
        fig.update_xaxes(gridcolor="rgba(255,255,255,0.04)")
        fig.update_layout(**plotly_defaults(), height=220, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    col_p1, col_p2 = st.columns(2)
    with col_p1:
        st.markdown('<div class="section-hdr">Weekly Volume (m)</div>', unsafe_allow_html=True)
        if not df.empty:
            weekly_df = df.groupby(df["workout_date"].dt.isocalendar().week)["distance_m"].sum().reset_index()
            weekly_df.columns = ["week", "distance"]
            fig2 = go.Figure(go.Bar(
                x=weekly_df["week"].astype(str),
                y=weekly_df["distance"],
                marker_color="#f59e0b",
                marker_line_color="rgba(0,0,0,0)",
            ))
            fig2.update_layout(**plotly_defaults(), height=160)
            fig2.update_yaxes(gridcolor="rgba(255,255,255,0.04)")
            fig2.update_xaxes(gridcolor="rgba(255,255,255,0.04)", title="Week")
            st.plotly_chart(fig2, use_container_width=True)

    with col_p2:
        st.markdown('<div class="section-hdr">Progress to Goals</div>', unsafe_allow_html=True)
        goals = [
            ("2km TT", 536, 495, "#00e5b4"),      # current 8:56, target 8:15
            ("Avg split", 134, 123, "#3b82f6"),    # 2:14 vs 2:03
            ("Weekly vol", 10000, 20000, "#f59e0b"),
            ("Stroke rate", 22, 26, "#a78bfa"),
        ]
        for label, current, target, color in goals:
            pct = min(int(current / target * 100), 100)
            st.markdown(f"""
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
              <div style="font-size:11px;color:#7a8ba8;min-width:90px">{label}</div>
              <div style="flex:1;height:4px;background:rgba(255,255,255,0.06);border-radius:2px">
                <div style="width:{pct}%;height:4px;background:{color};border-radius:2px"></div>
              </div>
              <div style="font-size:11px;font-family:'JetBrains Mono',monospace;color:{color};min-width:40px;text-align:right">{pct}%</div>
            </div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — SESSIONS
# ════════════════════════════════════════════════════════════════════════════
with tab_sessions:
    st.markdown('<div class="section-hdr">Session History</div>', unsafe_allow_html=True)

    if df.empty:
        st.info("No sessions yet — run the sync pipeline.")
    else:
        display_df = df[["workout_date", "distance_m", "duration_sec", "avg_split_sec",
                          "session_type", "fatigue_flag", "delta", "weekly_load_min"]].copy()
        display_df["split"] = display_df["avg_split_sec"].apply(fmt_split)
        display_df["duration_min"] = (display_df["duration_sec"] / 60).round(1)
        display_df["delta_s"] = display_df["delta"].apply(
            lambda x: f"+{x:.1f}s" if x > 0 else f"{x:.1f}s" if x is not None else "—"
        )
        display_df = display_df.rename(columns={
            "workout_date": "Date", "distance_m": "Distance (m)",
            "session_type": "Type", "fatigue_flag": "Fatigue",
            "weekly_load_min": "Weekly Load (min)",
        })
        st.dataframe(
            display_df[["Date", "Distance (m)", "duration_min", "split", "delta_s",
                         "Type", "Fatigue", "Weekly Load (min)"]],
            use_container_width=True,
            height=400,
            column_config={
                "Date": st.column_config.DatetimeColumn(format="DD MMM YYYY"),
                "split": st.column_config.TextColumn("Split /500m"),
                "delta_s": st.column_config.TextColumn("Δ vs Prev"),
                "duration_min": st.column_config.NumberColumn("Duration (min)", format="%.1f"),
            },
        )

    # Load vs split scatter
    if not df.empty:
        st.markdown('<div class="section-hdr">Load vs Performance</div>', unsafe_allow_html=True)
        fig3 = px.scatter(
            df, x="weekly_load_min", y="avg_split_sec",
            size="distance_m", color="session_type",
            color_discrete_map={"steady": "#3b82f6", "threshold": "#f59e0b", "race": "#ef4444"},
            hover_data={"avg_split_sec": False},
            custom_data=["avg_split_sec"],
        )
        fig3.update_traces(
            hovertemplate="Load: %{x:.0f} min<br>Split: %{customdata[0]:.1f}s<extra></extra>"
        )
        fig3.update_yaxes(autorange="reversed", gridcolor="rgba(255,255,255,0.04)")
        fig3.update_xaxes(gridcolor="rgba(255,255,255,0.04)")
        fig3.update_layout(**plotly_defaults(), height=220)
        st.plotly_chart(fig3, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — TRAINING PLAN
# ════════════════════════════════════════════════════════════════════════════
with tab_training:
    from datetime import timedelta

    # Refresh button so the user can manually pull latest data
    _tp_hdr_l, _tp_hdr_r = st.columns([9, 1])
    with _tp_hdr_r:
        if st.button("↻ Refresh", key="refresh_training_plan"):
            st.rerun()

    today       = date.today()
    day_labels  = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    TYPE_STYLE = {
        "steady":    ("#00e5b4", "1px solid rgba(0,229,180,0.35)",   "rgba(0,229,180,0.04)"),
        "long":      ("#00e5b4", "1px solid rgba(0,229,180,0.35)",   "rgba(0,229,180,0.04)"),
        "threshold": ("#a78bfa", "1px solid rgba(167,139,250,0.4)",  "rgba(167,139,250,0.05)"),
        "interval":  ("#f59e0b", "1px solid rgba(245,158,11,0.45)",  "rgba(245,158,11,0.05)"),
        "recovery":  ("#60a5fa", "1px solid rgba(96,165,250,0.4)",   "rgba(96,165,250,0.05)"),
        "rest":      ("#3b4a60", "1px solid rgba(255,255,255,0.05)", "transparent"),
    }

    # ── Section 1: Week in review ────────────────────────────────────────────
    st.markdown('<div class="section-hdr">Week in Review</div>', unsafe_allow_html=True)

    if weekly_plan:
        tw  = weekly_plan.get("this_week", {})
        pw  = weekly_plan.get("prev_week", {})
        gen = weekly_plan.get("generated_at", "")[:16].replace("T", " ")

        # Stat cards
        def _delta_html(curr, prev, unit="", lower_is_better=False):
            if not curr or not prev:
                return ""
            d = curr - prev
            if abs(d) < 0.01:
                return ""
            better = (d < 0) if lower_is_better else (d > 0)
            color  = "#00e5b4" if better else "#ef4444"
            arrow  = "↓" if d < 0 else "↑"
            return f'<span style="font-size:10px;color:{color};margin-left:4px">{arrow}{abs(d):.1f}{unit}</span>'

        kpi_cols = st.columns(4)
        kpis = [
            ("Volume", f"{tw.get('total_volume_km', 0)} km",
             _delta_html(tw.get('total_volume_km'), pw.get('total_volume_km'), " km")),
            ("Sessions", str(tw.get('sessions_completed', 0)),
             _delta_html(tw.get('sessions_completed'), pw.get('sessions_completed'))),
            ("Avg Split", tw.get('avg_split_formatted', '—'),
             _delta_html(tw.get('avg_split_sec'), pw.get('avg_split_sec'), "s", lower_is_better=True)),
            ("Duration", f"{tw.get('total_duration_min', 0)} min",
             _delta_html(tw.get('total_duration_min'), pw.get('total_duration_min'), " min")),
        ]
        for col, (label, value, delta) in zip(kpi_cols, kpis):
            with col:
                st.markdown(f"""
                <div class="kpi-card">
                  <div class="kpi-label">{label}</div>
                  <div class="kpi-value kpi-teal" style="font-size:20px">{value}{delta}</div>
                </div>""", unsafe_allow_html=True)

        # Insight note
        if weekly_plan.get("insight"):
            st.markdown(f"""
            <div style="background:#1a2234;border:1px solid rgba(255,255,255,0.07);border-left:3px solid #00e5b4;
                        border-radius:8px;padding:14px 16px;margin-top:4px">
              <div style="font-size:9px;color:#7a8ba8;font-family:'JetBrains Mono',monospace;
                          letter-spacing:0.8px;margin-bottom:8px">COACH INSIGHT · {gen}</div>
              <div style="font-size:13px;line-height:1.6;color:#c8d6e8">{_html.escape(weekly_plan['insight'])}</div>
            </div>""", unsafe_allow_html=True)

        # This-week actual sessions bar chart
        week_start_dt = date.fromisoformat(weekly_plan["week_start"])
        week_end_dt   = date.fromisoformat(weekly_plan["week_end"])
        # Build a full Mon–Sun scaffold so the chart always has 7 bars
        week_mon_dt   = week_start_dt - timedelta(days=week_start_dt.weekday())
        all_7_dates   = [week_mon_dt + timedelta(days=i) for i in range(7)]
        # Index actual sessions by date
        session_by_date = {}
        if not df.empty:
            for _, row in df.iterrows():
                d = pd.Timestamp(row["workout_date"]).date()
                if week_mon_dt <= d <= all_7_dates[-1]:
                    session_by_date[d] = row["distance_m"] / 1000

        bar_x      = [d.strftime("%-d %b") for d in all_7_dates]
        bar_labels = [day_labels[i] for i in range(7)]
        bar_y      = [session_by_date.get(d, 0) for d in all_7_dates]
        bar_colors = ["#00e5b4" if v > 0 else "rgba(255,255,255,0.04)" for v in bar_y]

        fig_w = go.Figure(go.Bar(
            x=bar_x,
            y=bar_y,
            marker_color=bar_colors,
            text=[f"{v:.1f}km" if v > 0 else "" for v in bar_y],
            textposition="outside",
            textfont=dict(size=10, color="#7a8ba8"),
        ))
        fig_w.update_layout(**plotly_defaults(), height=160,
                            yaxis_title="km", xaxis_title=None,
                            bargap=0.3)
        fig_w.update_yaxes(gridcolor="rgba(255,255,255,0.04)", rangemode="tozero")
        fig_w.update_xaxes(tickfont=dict(size=11))
        st.plotly_chart(fig_w, use_container_width=True)
    else:
        st.info("No weekly summary yet. Use the top-right Weekly Planning button, or run `bash scripts/run_weekly_planning.sh` manually.")

    # ── Section 2: Next week plan ────────────────────────────────────────────
    st.markdown('<div class="section-hdr">Next Week Plan</div>', unsafe_allow_html=True)

    next_week_entries = weekly_plan.get("next_week_plan", []) if weekly_plan else []

    def _parse_plan_km(label: str) -> float:
        """Extract planned distance in km from a plan label like '5km easy row' or '3x1km intervals'."""
        m = _re.match(r"(\d+)[xX](\d+(?:\.\d+)?)\s*km", label)
        if m:
            return int(m.group(1)) * float(m.group(2))
        m = _re.search(r"(\d+(?:\.\d+)?)\s*km", label)
        if m:
            return float(m.group(1))
        return 0.0

    if next_week_entries:
        # ── Planned-volume bar chart ────────────────────────────────────
        plan_days    = [e.get("day", "") for e in next_week_entries]
        plan_dates   = [date.fromisoformat(e["date"]).strftime("%-d %b") if e.get("date") else "" for e in next_week_entries]
        plan_km      = [_parse_plan_km(e.get("label", "")) for e in next_week_entries]
        plan_colors  = [TYPE_STYLE.get(e.get("session_type", "rest"), TYPE_STYLE["steady"])[0] for e in next_week_entries]

        fig_nw = go.Figure(go.Bar(
            x=plan_dates,
            y=plan_km,
            marker_color=plan_colors,
            text=[f"{v:.0f}km" if v > 0 else "" for v in plan_km],
            textposition="outside",
            textfont=dict(size=10, color="#7a8ba8"),
        ))
        fig_nw.update_layout(**plotly_defaults(), height=160,
                             yaxis_title="km", xaxis_title=None, bargap=0.3)
        fig_nw.update_yaxes(gridcolor="rgba(255,255,255,0.04)", rangemode="tozero")
        fig_nw.update_xaxes(tickfont=dict(size=11))
        st.plotly_chart(fig_nw, use_container_width=True)

        # ── Day cards ───────────────────────────────────────────────────
        day_cols = st.columns(7)
        for col, entry in zip(day_cols, next_week_entries):
            stype      = entry.get("session_type", "rest")
            label      = entry.get("label", "—")
            target     = entry.get("target_split") or ""
            notes      = entry.get("notes") or ""
            day_lbl    = entry.get("day", "")
            day_dt     = date.fromisoformat(entry["date"]) if entry.get("date") else None
            is_today   = day_dt == today if day_dt else False
            date_str   = day_dt.strftime("%-d %b") if day_dt else ""
            color, border, bg = TYPE_STYLE.get(stype, TYPE_STYLE["steady"])
            today_ring = "outline:2px solid rgba(255,255,255,0.2);outline-offset:2px;" if is_today else ""
            target_html = f'<div style="font-size:10px;color:{color};opacity:0.85;margin-top:4px;font-family:\'JetBrains Mono\',monospace">{target}</div>' if target else ""
            notes_html  = f'<div style="font-size:9px;color:#7a8ba8;margin-top:5px;line-height:1.4">{_html.escape(notes[:60])}</div>' if notes else ""
            with col:
                st.markdown(f"""
                <div style="border:{border};background:{bg};border-radius:8px;{today_ring}
                            padding:10px 6px;text-align:center;">
                  <div style="font-size:10px;color:#7a8ba8;font-family:'JetBrains Mono',monospace;
                              letter-spacing:0.8px;text-transform:uppercase">{day_lbl}</div>
                  <div style="font-size:10px;color:#4a5a70;font-family:'JetBrains Mono',monospace;
                              margin-bottom:6px">{date_str}</div>
                  <div style="font-size:11px;color:{color};line-height:1.4">{label}</div>
                  {target_html}
                  {notes_html}
                </div>""", unsafe_allow_html=True)
    else:
        # Fallback placeholder grid when no plan exists yet
        next_monday = today + timedelta(days=(7 - today.weekday()))
        day_cols    = st.columns(7)
        for i, (col, day_lbl) in enumerate(zip(day_cols, day_labels)):
            day_dt   = next_monday + timedelta(days=i)
            is_today = day_dt == today
            today_ring = "outline:2px solid rgba(255,255,255,0.2);outline-offset:2px;" if is_today else ""
            with col:
                st.markdown(f"""
                <div style="border:1px solid rgba(255,255,255,0.05);border-radius:8px;{today_ring}
                            padding:10px 6px;text-align:center;min-height:72px">
                  <div style="font-size:10px;color:#7a8ba8;font-family:'JetBrains Mono',monospace;
                              letter-spacing:0.8px;text-transform:uppercase">{day_lbl}</div>
                  <div style="font-size:10px;color:#4a5a70;font-family:'JetBrains Mono',monospace;
                              margin-bottom:6px">{day_dt.strftime("%-d %b")}</div>
                  <div style="font-size:18px;color:#3b4a60">—</div>
                </div>""", unsafe_allow_html=True)

    # ── Section 3: 7-Month Periodisation ────────────────────────────────────
    st.markdown('<div class="section-hdr">7-Month Periodisation</div>', unsafe_allow_html=True)

    phases = [
        ("Weeks 1–6",   "Base Aerobic",      "Long easy rows, HR zone 2, aerobic engine",  "#3b82f6", True),
        ("Weeks 7–12",  "Aerobic Threshold", "Tempo, 2×20min steady state pieces",         "#00e5b4", False),
        ("Weeks 13–18", "VO₂max Development","4–8min intervals, race-pace exposure",       "#f59e0b", False),
        ("Weeks 19–24", "Race Specificity",  "2km simulations, sprint, rating work",       "#f97316", False),
        ("Weeks 25–28", "Peak & Taper",      "Reduced volume, maintained intensity",       "#ef4444", False),
        ("Weeks 29–30", "Competition",       "Race week — minimal training, mental prep",  "#a78bfa", False),
    ]
    for weeks, focus, desc, color, current in phases:
        border = f"border:1px solid {color}33;background:{color}0a;" if current else "border:1px solid rgba(255,255,255,0.06);"
        tag    = ' <span style="font-size:9px;background:rgba(0,229,180,0.12);color:#00e5b4;padding:2px 8px;border-radius:10px;font-family:\'JetBrains Mono\',monospace">CURRENT</span>' if current else ""
        st.markdown(f"""
        <div style="{border}border-left:3px solid {color};border-radius:8px;padding:12px 14px;margin-bottom:8px">
          <div style="font-size:9px;color:{color};font-family:'JetBrains Mono',monospace;letter-spacing:0.8px">{weeks}{tag}</div>
          <div style="font-size:13px;font-weight:500;margin-top:3px">{focus}</div>
          <div style="font-size:11px;color:#7a8ba8;margin-top:2px">{desc}</div>
        </div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 4 — RECOVERY
# ════════════════════════════════════════════════════════════════════════════
with tab_recovery:
    st.markdown('<div class="section-hdr">Garmin Connect — Recovery Signals</div>', unsafe_allow_html=True)

    if not garmin:
        st.info("Run `python pipelines/import_garmin.py` to sync Garmin data.")
    else:
        def rec_class(val, low, high):
            if val is None: return "kpi-value kpi-amber"
            return "rec-val-good" if val >= high else ("rec-val-warn" if val >= low else "rec-val-bad")

        cols = st.columns(6)
        metrics = [
            ("Body Battery", garmin.get("body_battery"), 70, 85, "/100"),
            ("HRV Status",   garmin.get("hrv_status"),   None, None, ""),
            ("Sleep Score",  garmin.get("sleep_score"),  65, 80, ""),
            ("Resting HR",   garmin.get("resting_hr"),   None, None, "bpm"),
            ("Stress",       garmin.get("stress"),        None, None, ""),
            ("Readiness",    garmin.get("readiness"),     60, 75, "%"),
        ]
        for i, (label, val, low, high, unit) in enumerate(metrics):
            cls = rec_class(val, low or 0, high or 100) if isinstance(val, (int, float)) else "rec-val-warn"
            with cols[i]:
                st.markdown(f"""<div class="rec-card">
                  <div class="rec-label">{label}</div>
                  <div class="{cls}">{val if val is not None else '—'}{unit}</div>
                </div>""", unsafe_allow_html=True)

        bb = garmin.get("body_battery", 100)
        if bb and bb < 70:
            st.warning(
                f"⚡ Body Battery is {bb} (below threshold 70). "
                "Today's target split will be auto-adjusted +4s. "
                "Performance taper is intentional."
            )

    # Recovery vs performance chart
    if not df.empty and not garmin_df.empty:
        st.markdown('<div class="section-hdr">Recovery vs Performance Correlation</div>', unsafe_allow_html=True)
        merged = pd.merge(
            df[["workout_date", "avg_split_sec"]],
            garmin_df[["record_date", "body_battery", "sleep_score"]].rename(
                columns={"record_date": "workout_date"}
            ),
            on="workout_date", how="inner",
        )
        if not merged.empty:
            fig4 = px.scatter(
                merged, x="body_battery", y="avg_split_sec",
                size="sleep_score", color="avg_split_sec",
                color_continuous_scale=[[0, "#ef4444"], [0.5, "#f59e0b"], [1, "#00e5b4"]],
            )
            fig4.update_yaxes(autorange="reversed", gridcolor="rgba(255,255,255,0.04)")
            fig4.update_xaxes(gridcolor="rgba(255,255,255,0.04)", title="Body Battery")
            fig4.update_layout(**plotly_defaults(), height=200, coloraxis_showscale=False)
            st.plotly_chart(fig4, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 5 — COACH (memory-aware)
# ════════════════════════════════════════════════════════════════════════════
with tab_coach:
    col_chat, col_latest = st.columns([1, 1])

    with col_chat:
        st.markdown('<div class="section-hdr">Coaching Memory — last exchanges</div>', unsafe_allow_html=True)

        tips = get_recent_tips()
        if not tips:
            st.info("No coaching tips yet. Add one below.")
        else:
            # Build a lookup: date-string → (distance_m, avg_split_sec) from daily_metrics
            session_lookup = {}
            if not df.empty and "workout_date" in df.columns:
                for _, row in df.iterrows():
                    key = str(row["workout_date"])[:10]
                    session_lookup[key] = (
                        int(row["distance_m"]) if pd.notna(row.get("distance_m")) else None,
                        row["avg_split_sec"] if pd.notna(row.get("avg_split_sec")) else None,
                    )

            for t in tips:  # newest first
                who = "🤖 AI Coach" if t["author"] == "coach" else "👤 You"
                css_class = "tip-coach" if t["author"] == "coach" else "tip-athlete"
                taper_html = '<div class="taper-badge">↓ taper expected next session</div>' if t["expect_taper"] else ""
                tag_html = f'<span style="font-size:9px;padding:2px 7px;border-radius:10px;background:rgba(59,130,246,0.12);color:#60a5fa;font-family:\'JetBrains Mono\',monospace;margin-left:6px">{t["tag"]}</span>' if t.get("tag") else ""
                # Render card header as HTML (safe — no user content injected into divs)
                st.markdown(f"""
                <div class="{css_class}">
                  <div style="display:flex;justify-content:space-between">
                    <span class="tip-who">{who}{tag_html}</span>
                    <span class="tip-time">{t['created_at'][:16]}</span>
                  </div>
                  {taper_html}
                </div>""", unsafe_allow_html=True)
                # Expander label: "4,500 m · 2:48.6/500m" when session data is available
                skey = str(t.get("session_date", ""))[:10]
                dist, split_sec = session_lookup.get(skey, (None, None))
                if dist and split_sec:
                    expander_label = f"{dist:,} m · {fmt_split(split_sec)}"
                elif dist:
                    expander_label = f"{dist:,} m"
                else:
                    expander_label = skey or "coaching tip"
                with st.expander(expander_label, expanded=False):
                    st.markdown(t['tip_text'])

        st.markdown('<div class="section-hdr">Add coaching note</div>', unsafe_allow_html=True)

        TAG_OPTIONS   = ["recovery", "performance", "hard", "race", "technical", "caution"]
        STYPE_LABELS  = ["— no flag", "🔵 Recovery · easy/taper", "🟡 Hard · push the pace", "🟢 Race sim · full effort", "🔴 Technique · drill focus"]
        STYPE_VALUES  = ["", "recovery", "hard", "race", "technique"]

        with st.form("coach_note_form", clear_on_submit=True):
            note_text = st.text_area(
                "Note",
                placeholder="e.g. Next session is a recovery row — expect splits to taper",
                label_visibility="collapsed",
            )

            tag = st.radio("Tag", TAG_OPTIONS, index=1, horizontal=True)

            stype_label = st.radio("Next session type", STYPE_LABELS, index=0, horizontal=True)
            session_type = STYPE_VALUES[STYPE_LABELS.index(stype_label)]

            col_author, col_submit = st.columns([2, 1])
            with col_author:
                author = st.radio("Author", ["coach", "athlete"], horizontal=True)
            with col_submit:
                submitted = st.form_submit_button("Save tip", use_container_width=True)

            if submitted and note_text.strip():
                result = add_tip(
                    tip_text=note_text.strip(),
                    author=author,
                    tag=tag,
                    session_type=session_type or None,
                )
                taper_msg = " ✅ Taper flag set — next session's slower splits will be treated as intentional." if result["expect_taper"] else ""
                st.success(f"Tip saved.{taper_msg}")
                st.rerun()

    with col_latest:
        st.markdown('<div class="section-hdr">Latest AI coaching insight</div>', unsafe_allow_html=True)
        latest_session_dt = None if latest is None else pd.Timestamp(latest["workout_date"]).to_pydatetime()
        coaching_summary_dt = _coaching_summary_dt(coaching_output)
        coaching_is_stale = (
            latest_session_dt is not None
            and (
                coaching_summary_dt is None
                or coaching_summary_dt < latest_session_dt
            )
        )

        if coaching_output:
            coaching_text = coaching_output.get("coaching", "")
            generated_at = coaching_output.get("generated_at", "")
            model_used = coaching_output.get("model", LM_MODEL)

            if coaching_is_stale:
                st.warning(
                    "Coaching insight is out of date. "
                    f"Latest session: {latest_session_dt.strftime('%d %b %Y %H:%M')} | "
                    f"Coaching file covers: {coaching_summary_dt.strftime('%d %b %Y %H:%M') if coaching_summary_dt else 'unknown'}"
                )

            st.markdown(f"""
            <div style="font-size:9px;color:#7a8ba8;font-family:'JetBrains Mono',monospace;margin-bottom:10px">
              {model_used} · {generated_at[:16]}
            </div>""", unsafe_allow_html=True)

            st.markdown(coaching_text)
        else:
            st.info("Run `python pipelines/generate_coaching.py` to generate insights.")

        st.markdown('<div class="section-hdr">Discord Brief</div>', unsafe_allow_html=True)

        brief_path = Path("coaching/briefs/daily/latest.txt")
        if brief_path.exists():
            brief_text = brief_path.read_text()
            st.text_area("Latest generated brief", brief_text, height=200)

        col_wa1, col_wa2, col_wa3 = st.columns(3)
        with col_wa1:
            if st.button("🧠 Refresh coaching insight"):
                with st.spinner("Generating coaching insight..."):
                    try:
                        from pipelines.generate_coaching import main as coaching_main
                        coaching_main()
                        st.success("Coaching insight regenerated.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
        with col_wa2:
            if st.button("📱 Generate & send brief now"):
                with st.spinner("Generating brief via LM Studio..."):
                    try:
                        from pipelines.send_discord import main as send_main
                        send_main()
                        st.success("Brief sent via Discord!")
                    except Exception as e:
                        st.error(f"Error: {e}")
        with col_wa3:
            if st.button("🔄 Re-generate brief (no send)"):
                with st.spinner("Generating..."):
                    try:
                        from pipelines.generate_daily_brief import main as brief_main
                        brief_main()
                        st.success("Brief regenerated.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")


# ════════════════════════════════════════════════════════════════════════════
# TAB 6 — CONTEXT (FR-C08 quarantine log observability)
# ════════════════════════════════════════════════════════════════════════════
