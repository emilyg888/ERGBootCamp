"""
ERGBootCamp — dashboard.py  (Streamlit)

Run with:  streamlit run pipelines/dashboard.py
"""

import json
import sys
from pathlib import Path
from datetime import date, datetime

import duckdb
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

# ── path bootstrap ────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipelines.config_loader import DB_PATH, LM_MODEL, ATHLETE, COACHING
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
</style>
""", unsafe_allow_html=True)


# ── helpers ───────────────────────────────────────────────────────────────────
def fmt_split(sec) -> str:
    if sec is None:
        return "—"
    m = int(sec // 60)
    s = sec % 60
    return f"{m}:{s:04.1f}"


def days_to_competition() -> int:
    comp = datetime.strptime(ATHLETE["competition_date"], "%Y-%m-%d").date()
    return max((comp - date.today()).days, 0)


def load_db():
    con = duckdb.connect(DB_PATH)
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
    p = Path("data/coaching_output.json")
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return {}


def load_garmin_cache():
    p = Path("data/garmin_latest.json")
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


# ── load data ─────────────────────────────────────────────────────────────────
df, garmin_df = load_db()
coaching_output = load_coaching_output()
garmin = load_garmin_cache()
latest = df.iloc[-1] if not df.empty else None

# ── brand bar ─────────────────────────────────────────────────────────────────
days_left = days_to_competition()

st.markdown(f"""
<div class="brand-bar">
  <div>
    <div class="brand-name">ERG<span>BootCamp</span></div>
    <div class="brand-sub">Day {(date.today() - datetime.strptime(ATHLETE['training_start'], '%Y-%m-%d').date()).days} of 210 &nbsp;·&nbsp; {ATHLETE['goal']}</div>
  </div>
  <span class="model-badge">{LM_MODEL}</span>
</div>
""", unsafe_allow_html=True)

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
    st.markdown('<div class="section-hdr">7-Month Periodisation</div>', unsafe_allow_html=True)

    phases = [
        ("Weeks 1–6",  "Base Aerobic",       "Long easy rows, HR zone 2, aerobic engine",   "#3b82f6", True),
        ("Weeks 7–12", "Aerobic Threshold",   "Tempo, 2×20min steady state pieces",          "#00e5b4", False),
        ("Weeks 13–18","VO₂max Development",  "4–8min intervals, race-pace exposure",        "#f59e0b", False),
        ("Weeks 19–24","Race Specificity",    "2km simulations, sprint, rating work",        "#f97316", False),
        ("Weeks 25–28","Peak & Taper",        "Reduced volume, maintained intensity",        "#ef4444", False),
        ("Weeks 29–30","Competition",         "Race week — minimal training, mental prep",   "#a78bfa", False),
    ]

    for weeks, focus, desc, color, current in phases:
        border = f"border: 1px solid {color}33; background: {color}0a;" if current else "border: 1px solid rgba(255,255,255,0.06);"
        tag = ' <span style="font-size:9px;background:rgba(0,229,180,0.12);color:#00e5b4;padding:2px 8px;border-radius:10px;font-family:\'JetBrains Mono\',monospace">CURRENT</span>' if current else ""
        st.markdown(f"""
        <div style="{border} border-left: 3px solid {color}; border-radius:8px; padding:12px 14px; margin-bottom:8px">
          <div style="font-size:9px;color:{color};font-family:'JetBrains Mono',monospace;letter-spacing:0.8px">{weeks}{tag}</div>
          <div style="font-size:13px;font-weight:500;margin-top:3px">{focus}</div>
          <div style="font-size:11px;color:#7a8ba8;margin-top:2px">{desc}</div>
        </div>""", unsafe_allow_html=True)

    col_w1, col_w2 = st.columns(2)
    with col_w1:
        st.markdown('<div class="section-hdr">This Week</div>', unsafe_allow_html=True)
        week_plan = [
            ("Mon", "6km easy", True), ("Tue", "4km recovery", True),
            ("Wed", "8×500m intervals", False), ("Thu", "Rest", False),
            ("Fri", "5km steady", False), ("Sat", "8km long row", False), ("Sun", "Rest", False),
        ]
        for day, session, done in week_plan:
            color = "#00e5b4" if done else ("#f59e0b" if "interval" in session.lower() else "#7a8ba8")
            tick = "✓" if done else "→" if "interval" in session.lower() else "·"
            st.markdown(f"""
            <div style="display:flex;justify-content:space-between;padding:7px 0;
                        border-bottom:1px solid rgba(255,255,255,0.05)">
              <span style="font-size:12px">{day}</span>
              <span style="font-size:12px;font-family:'JetBrains Mono',monospace;color:{color}">{tick} {session}</span>
            </div>""", unsafe_allow_html=True)

    with col_w2:
        st.markdown('<div class="section-hdr">Next Session</div>', unsafe_allow_html=True)
        st.markdown("""
        <div style="padding:8px 0">
          <div style="font-size:20px;font-weight:700;color:#f59e0b;font-family:'JetBrains Mono',monospace">8 × 500m</div>
          <div style="font-size:11px;color:#7a8ba8;margin-top:2px">Interval training · Wednesday</div>
          <div style="margin-top:14px;display:flex;flex-direction:column;gap:8px">
            <div style="font-size:12px"><span style="color:#7a8ba8">Target split: </span>
              <span style="font-family:'JetBrains Mono',monospace;color:#00e5b4">2:08 /500m</span></div>
            <div style="font-size:12px"><span style="color:#7a8ba8">Rest: </span>
              <span style="font-family:'JetBrains Mono',monospace">2:00 between</span></div>
            <div style="font-size:12px"><span style="color:#7a8ba8">Rate: </span>
              <span style="font-family:'JetBrains Mono',monospace">24–26 spm</span></div>
            <div style="font-size:12px"><span style="color:#7a8ba8">Est. duration: </span>
              <span style="font-family:'JetBrains Mono',monospace">~35 min</span></div>
          </div>
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
            for t in reversed(tips):  # chronological
                who = "🤖 AI Coach" if t["author"] == "coach" else "👤 You"
                css_class = "tip-coach" if t["author"] == "coach" else "tip-athlete"
                taper_html = '<div class="taper-badge">↓ taper expected next session</div>' if t["expect_taper"] else ""
                tag_html = f'<span style="font-size:9px;padding:2px 7px;border-radius:10px;background:rgba(59,130,246,0.12);color:#60a5fa;font-family:\'JetBrains Mono\',monospace;margin-left:6px">{t["tag"]}</span>' if t.get("tag") else ""
                st.markdown(f"""
                <div class="{css_class}">
                  <div style="display:flex;justify-content:space-between">
                    <span class="tip-who">{who}{tag_html}</span>
                    <span class="tip-time">{t['created_at'][:16]}</span>
                  </div>
                  <div class="tip-body">{t['tip_text'][:300]}{'...' if len(t['tip_text']) > 300 else ''}</div>
                  {taper_html}
                </div>""", unsafe_allow_html=True)

        st.markdown('<div class="section-hdr">Add coaching note</div>', unsafe_allow_html=True)

        with st.form("coach_note_form", clear_on_submit=True):
            note_text = st.text_area("Note", placeholder="e.g. Next session is a recovery row — expect splits to taper")
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                tag = st.selectbox("Tag", ["recovery", "hard", "race", "technical", "nutrition", "performance"])
            with col_f2:
                author = st.selectbox("Author", ["coach", "athlete"])
            with col_f3:
                session_type = st.selectbox("Next session type", ["", "recovery", "hard", "race", "technique"])

            submitted = st.form_submit_button("Save tip")
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

        st.markdown('<div class="section-hdr">Quick tags</div>', unsafe_allow_html=True)
        quick_col1, quick_col2, quick_col3 = st.columns(3)
        with quick_col1:
            if st.button("🔵 Recovery row"):
                add_tip("Next session is a RECOVERY row — splits expected 10–15s slower. This is intentional.", author="coach", tag="recovery", session_type="recovery")
                st.rerun()
        with quick_col2:
            if st.button("🟡 Hard effort"):
                add_tip("Next session is a HARD effort — push splits, target 2:08 or faster.", author="coach", tag="hard", session_type="hard")
                st.rerun()
        with quick_col3:
            if st.button("🟢 Race simulation"):
                add_tip("Race simulation today — treat it like competition. Give everything.", author="coach", tag="race", session_type="race")
                st.rerun()

    with col_latest:
        st.markdown('<div class="section-hdr">Latest AI coaching insight</div>', unsafe_allow_html=True)

        if coaching_output:
            coaching_text = coaching_output.get("coaching", "")
            generated_at = coaching_output.get("generated_at", "")
            model_used = coaching_output.get("model", LM_MODEL)

            st.markdown(f"""
            <div style="font-size:9px;color:#7a8ba8;font-family:'JetBrains Mono',monospace;margin-bottom:10px">
              {model_used} · {generated_at[:16]}
            </div>""", unsafe_allow_html=True)

            st.markdown(coaching_text)
        else:
            st.info("Run `python pipelines/generate_coaching.py` to generate insights.")

        st.markdown('<div class="section-hdr">WhatsApp Brief</div>', unsafe_allow_html=True)

        brief_path = Path("coaching/briefs/daily/latest.txt")
        if brief_path.exists():
            brief_text = brief_path.read_text()
            st.text_area("Latest brief (sent at 06:30)", brief_text, height=200)

        col_wa1, col_wa2 = st.columns(2)
        with col_wa1:
            if st.button("📱 Generate & send brief now"):
                with st.spinner("Generating brief via LMStudio..."):
                    try:
                        from pipelines.send_whatsapp import main as send_main
                        send_main()
                        st.success("Brief sent via WhatsApp!")
                    except Exception as e:
                        st.error(f"Error: {e}")
        with col_wa2:
            if st.button("🔄 Re-generate brief (no send)"):
                with st.spinner("Generating..."):
                    try:
                        from pipelines.generate_daily_brief import main as brief_main
                        brief_main()
                        st.success("Brief regenerated.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
