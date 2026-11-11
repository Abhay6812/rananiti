from __future__ import annotations

from pathlib import Path
import sys

import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import BALLS_FILE, MATCHES_FILE, RAW_DATA  # noqa: E402
from src.rankings.rr_dashboard_insights import (  # noqa: E402
    compare_batter_rates,
    compare_bowler_economy,
    load_rr_dashboard_insights,
)

st.set_page_config(page_title="Rananiti | RR Pressure Intelligence", page_icon="\U0001F3CF", layout="wide")
st.markdown(
    """
    <style>
      :root { --royal-blue:#203b68; --admiral:#162b50; --rr-pink:#e50072; --hot-pink:#ff2f91; --blush:#fce8f1; --canvas:#f4f6fb; --ink:#18243a; }
      [data-testid="stAppViewContainer"] { background:radial-gradient(ellipse at 8% 0%,#fff 0%,var(--canvas) 47%,#eef2f8 100%); color:var(--ink); }
      [data-testid="stHeader"] { background:transparent; }
      [data-testid="stSidebar"] { background:linear-gradient(165deg,var(--admiral) 0%,#203e70 68%,#55224f 140%); box-shadow:8px 0 24px rgba(17,35,68,.18); }
      [data-testid="stSidebar"] * { color:#f7f9fc; }
      [data-testid="stSidebar"] [data-baseweb="select"] * { color:#18283d; }
      .block-container { padding-top:1.8rem; padding-bottom:2.5rem; max-width:1500px; }
      .rr-hero { position:relative; overflow:hidden; background:linear-gradient(118deg,#14284c 0%,#203b68 56%,#6f1d56 100%); border:1px solid rgba(255,255,255,.18); border-radius:22px; padding:30px 36px; color:white; margin-bottom:24px; box-shadow:0 20px 38px rgba(20,40,76,.22),0 5px 12px rgba(229,0,114,.12),inset 0 1px 0 rgba(255,255,255,.24); transform:perspective(1200px) rotateX(.35deg); }
      .rr-hero:after { content:"RR"; position:absolute; right:5%; top:-58px; color:rgba(255,255,255,.055); font-size:230px; line-height:1; font-weight:900; letter-spacing:-.1em; transform:rotate(-9deg); pointer-events:none; }
      .rr-eyebrow { color:#ff9bc7; font-size:.76rem; letter-spacing:.16em; font-weight:800; text-transform:uppercase; }
      .rr-hero h1 { color:white; margin:.35rem 0; font-size:2.2rem; }
      .rr-hero p { color:#e2eaf3; margin:0; font-size:1rem; }
      .rr-card { position:relative; overflow:hidden; background:linear-gradient(150deg,#fff 0%,#fff 66%,#fff7fb 100%); border:1px solid #f1d5e3; border-radius:17px; padding:18px 20px; min-height:126px; box-shadow:0 12px 22px rgba(31,50,84,.09),0 3px 6px rgba(31,50,84,.055),inset 0 1px 0 #fff; transition:transform .2s ease,box-shadow .2s ease; transform:perspective(900px) rotateX(.5deg); }
      .rr-card:before { content:""; position:absolute; left:0; top:0; bottom:0; width:4px; background:linear-gradient(180deg,var(--hot-pink),var(--royal-blue)); }
      .rr-card:hover { transform:perspective(900px) translateY(-4px) rotateX(1.5deg); box-shadow:0 19px 30px rgba(31,50,84,.14),0 5px 10px rgba(229,0,114,.1); }
      .rr-card-label { color:#68758a; text-transform:uppercase; letter-spacing:.08em; font-size:.72rem; font-weight:800; }
      .rr-card-player { color:var(--admiral); font-size:1.2rem; font-weight:800; margin:.45rem 0 .25rem; }
      .rr-card-detail { color:#53647b; font-size:.88rem; line-height:1.4; }
      .rr-note { color:#69778d; margin-top:-.55rem; margin-bottom:.9rem; }
      div[data-testid="stMetric"] { background:linear-gradient(145deg,#fff 0%,#fff 65%,#fff7fb 100%); border:1px solid #e5e9f0; border-radius:15px; padding:14px 16px; box-shadow:0 10px 20px rgba(31,50,84,.08),0 2px 4px rgba(31,50,84,.05); transition:transform .18s ease,box-shadow .18s ease; }
      div[data-testid="stMetric"]:hover { transform:translateY(-3px); box-shadow:0 16px 26px rgba(31,50,84,.13); }
      div[data-testid="stMetricLabel"] { color:#69778d; }
      div[data-testid="stMetricValue"] { color:var(--admiral); }
      div[data-testid="stPlotlyChart"] { background:linear-gradient(155deg,#fff,#fff 78%,#fff7fb); border:1px solid #e7eaf0; border-radius:17px; padding:8px 8px 0; box-shadow:0 12px 24px rgba(31,50,84,.08),0 3px 6px rgba(31,50,84,.045); }
      div[data-testid="stDataFrame"] { border-radius:15px; box-shadow:0 9px 20px rgba(31,50,84,.075); overflow:hidden; }
      div[data-baseweb="tab-list"] { gap:8px; background:#e9edf4; border-radius:13px; padding:5px; }
      button[data-baseweb="tab"] { border-radius:10px; color:#344763; }
      button[data-baseweb="tab"][aria-selected="true"] { background:linear-gradient(135deg,var(--royal-blue),var(--admiral)); color:#fff; box-shadow:0 4px 10px rgba(22,43,80,.24); }
      .stDownloadButton button { border-radius:10px; border:1px solid #e50072; color:#203b68; background:#fff; box-shadow:0 4px 9px rgba(31,50,84,.08); }
      .stDownloadButton button:hover { border-color:#e50072; color:#fff; background:linear-gradient(120deg,#e50072,#b50062); }
      div[data-testid="stAlert"] { border-radius:12px; box-shadow:0 5px 13px rgba(31,50,84,.065); }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=1800, show_spinner="Rebuilding RR pressure insights from ball-by-ball data…")
def get_insights(source_stamp: tuple[float, ...]):
    del source_stamp  # cache key changes whenever an input file changes
    return load_rr_dashboard_insights(max_top_x=10)


st.markdown(
    """
    <div class="rr-hero">
      <div class="rr-eyebrow">Rajasthan Royals · IPL 2022–2026</div>
      <h1>Performance under pressure</h1>
      <p>Find RR players with strong pressure evidence, then inspect the sample behind each score.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

source_files = [BALLS_FILE, MATCHES_FILE, RAW_DATA / "competitions.csv", RAW_DATA / "competition_team_player_mapping.csv"]
missing = [str(path) for path in source_files if not path.exists()]
if missing:
    st.error("Required input files are missing: " + ", ".join(missing))
    st.stop()

try:
    insights = get_insights(tuple(path.stat().st_mtime for path in source_files))
except Exception as exc:
    st.error(f"The RR insight backend could not build the rankings: {exc}")
    st.stop()

batters = insights["batters"]
bowlers = insights["bowlers"]
evaluation = insights["evaluation"]
if batters.empty or bowlers.empty:
    st.warning("The available RR pressure records do not populate both rankings.")
    st.stop()

top_x_max = min(10, len(batters), len(bowlers))
st.sidebar.markdown("### Dashboard controls")
top_x = st.sidebar.slider("Show Top X", 1, top_x_max, top_x_max)
st.sidebar.caption("Lists are ranked by Trust. Risk and sample size add decision context.")
st.sidebar.markdown("---")
st.sidebar.markdown("**Score guide**")
st.sidebar.caption("Higher Trust indicates stronger role or phase adjusted pressure evidence. Lower Risk is preferable. Confidence shrinks scores toward 50 when the sample is small.")

seasons = evaluation["seasons"]
k1, k2, k3, k4 = st.columns(4)
k1.metric("RR matches", f"{evaluation['rr_matches']:,}")
k2.metric("High-pressure batting balls", f"{evaluation['rr_high_pressure_batting_deliveries']:,}")
k3.metric("High-pressure bowling balls", f"{evaluation['rr_high_pressure_bowling_deliveries']:,}")
k4.metric("Seasons covered", f"{min(seasons)}–{max(seasons)}")

for col, insight in zip(st.columns(4), insights["insights"]):
    col.markdown(
        f"""<div class="rr-card"><div class="rr-card-label">{insight['title']}</div>
        <div class="rr-card-player">{insight['player']}</div><div class="rr-card-detail">{insight['detail']}</div></div>""",
        unsafe_allow_html=True,
    )

batter_cutoff = evaluation["batter_eligibility"]
bowler_cutoff = evaluation["bowler_eligibility"]
if batter_cutoff["minimum_pressure_balls"] < 12 or batter_cutoff["minimum_pressure_matches"] < 3:
    st.warning(
        "The RR-only batter pool required a fallback of "
        f"{batter_cutoff['minimum_pressure_balls']} pressure ball(s) in {batter_cutoff['minimum_pressure_matches']} match(es) "
        "to provide ten candidates. Review Confidence, pressure balls, and match count before relying on the order."
    )

batting_tab, bowling_tab, method_tab = st.tabs(["Batting", "Bowling", "Method & data"])

with batting_tab:
    view = batters.head(top_x).copy()
    roles = ["All roles"] + sorted(view["role"].dropna().unique().tolist())
    selected_role = st.selectbox("Batting role", roles, key="batter_role")
    if selected_role != "All roles":
        view = view[view["role"].eq(selected_role)]
    left, right = st.columns([1, 1.15])
    with left:
        st.subheader(f"Top {top_x} batting Trust scores")
        st.markdown('<div class="rr-note">Role adjusted ratings; hover for confidence and exposure.</div>', unsafe_allow_html=True)
        fig = px.bar(
            view.sort_values("trust_score"), x="trust_score", y="player", orientation="h", color="trust_score",
            color_continuous_scale=["#dfe7ef", "#ed8bb5", "#e50072"],
            hover_data={"confidence": True, "risk_score": True, "pressure_balls": True, "pressure_matches": True},
            labels={"trust_score": "Trust score", "player": "", "confidence": "Confidence", "risk_score": "Risk"},
        )
        fig.update_layout(height=390, margin=dict(l=5, r=15, t=10, b=10), coloraxis_showscale=False,
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          xaxis=dict(range=[0, 100], gridcolor="#e8edf2"), yaxis=dict(title=""))
        st.plotly_chart(fig, use_container_width=True)
    with right:
        st.subheader("Pressure strike rate vs baseline")
        st.markdown('<div class="rr-note">Compare scoring speed in pressure balls with the player’s usual RR rate.</div>', unsafe_allow_html=True)
        compare = compare_batter_rates(view).melt(id_vars="Player", var_name="Context", value_name="Strike rate")
        fig = px.bar(compare, x="Player", y="Strike rate", color="Context", barmode="group",
                     color_discrete_map={"Under pressure": "#e50072", "Usual baseline": "#203b68"})
        fig.update_layout(height=390, margin=dict(l=5, r=15, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)",
                          plot_bgcolor="rgba(0,0,0,0)", xaxis=dict(title="", tickangle=-25), yaxis=dict(gridcolor="#e8edf2"),
                          legend=dict(orientation="h", y=1.12, x=0))
        st.plotly_chart(fig, use_container_width=True)
    st.subheader("Batter evidence")
    batter_cols = ["rank", "player", "role", "trust_score", "risk_score", "confidence", "pressure_matches",
                   "pressure_balls", "pressure_strike_rate", "strike_rate", "pressure_average"]
    batter_table = view[[c for c in batter_cols if c in view]].rename(columns={
        "rank": "Rank", "player": "Player", "role": "Role", "trust_score": "Trust", "risk_score": "Risk",
        "confidence": "Confidence", "pressure_matches": "Pressure matches", "pressure_balls": "Pressure balls",
        "pressure_strike_rate": "Pressure SR", "strike_rate": "Baseline SR", "pressure_average": "Pressure average",
    })
    st.dataframe(batter_table, hide_index=True, use_container_width=True, column_config={
        key: st.column_config.ProgressColumn(key, min_value=0, max_value=100, format="%.1f")
        for key in ("Trust", "Risk", "Confidence")
    })
    st.download_button("Download batter view", batter_table.to_csv(index=False), "rr_batters_topx.csv", "text/csv")

with bowling_tab:
    view = bowlers.head(top_x).copy()
    phases = ["All phases"] + sorted(view["phase"].dropna().unique().tolist())
    selected_phase = st.selectbox("Innings phase", phases, key="bowler_phase")
    if selected_phase != "All phases":
        view = view[view["phase"].eq(selected_phase)]
    left, right = st.columns([1, 1.15])
    with left:
        st.subheader(f"Top {top_x} bowling Trust scores")
        st.markdown('<div class="rr-note">Each player appears once, assigned their strongest phase profile.</div>', unsafe_allow_html=True)
        fig = px.bar(
            view.sort_values("trust_score"), x="trust_score", y="player", orientation="h", color="trust_score",
            color_continuous_scale=["#dfe7ef", "#ed8bb5", "#e50072"],
            hover_data={"phase": True, "confidence": True, "risk_score": True, "pressure_balls": True},
            labels={"trust_score": "Trust score", "player": "", "phase": "Phase", "confidence": "Confidence"},
        )
        fig.update_layout(height=390, margin=dict(l=5, r=15, t=10, b=10), coloraxis_showscale=False,
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          xaxis=dict(range=[0, 100], gridcolor="#e8edf2"), yaxis=dict(title=""))
        st.plotly_chart(fig, use_container_width=True)
    with right:
        st.subheader("Pressure economy vs baseline")
        st.markdown('<div class="rr-note">Lower economy is better. Review beside wickets and sample size.</div>', unsafe_allow_html=True)
        compare = compare_bowler_economy(view).melt(id_vars="Player", var_name="Context", value_name="Economy")
        fig = px.bar(compare, x="Player", y="Economy", color="Context", barmode="group",
                     color_discrete_map={"Under pressure": "#e50072", "Usual baseline": "#203b68"})
        fig.update_layout(height=390, margin=dict(l=5, r=15, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)",
                          plot_bgcolor="rgba(0,0,0,0)", xaxis=dict(title="", tickangle=-25), yaxis=dict(gridcolor="#e8edf2"),
                          legend=dict(orientation="h", y=1.12, x=0))
        st.plotly_chart(fig, use_container_width=True)
    st.subheader("Bowler evidence")
    bowler_cols = ["rank", "player", "phase", "trust_score", "risk_score", "confidence", "pressure_matches",
                   "pressure_balls", "pressure_overs", "pressure_wickets", "pressure_economy", "economy"]
    bowler_table = view[[c for c in bowler_cols if c in view]].rename(columns={
        "rank": "Rank", "player": "Player", "phase": "Best phase", "trust_score": "Trust", "risk_score": "Risk",
        "confidence": "Confidence", "pressure_matches": "Pressure matches", "pressure_balls": "Pressure balls",
        "pressure_overs": "Pressure overs", "pressure_wickets": "Pressure wickets",
        "pressure_economy": "Pressure economy", "economy": "Baseline economy",
    })
    st.dataframe(bowler_table, hide_index=True, use_container_width=True, column_config={
        key: st.column_config.ProgressColumn(key, min_value=0, max_value=100, format="%.1f")
        for key in ("Trust", "Risk", "Confidence")
    })
    st.download_button("Download bowler view", bowler_table.to_csv(index=False), "rr_bowlers_topx.csv", "text/csv")

with method_tab:
    st.subheader("How to read the scores")
    st.markdown(
        """
        - **Trust** combines pressure performance with a confidence adjustment. Smaller pressure samples pull the rating toward 50.
        - **Risk** is an independent review signal. Read it with pressure balls, pressure matches, and confidence.
        - Batter roles are inferred from median batting position. The batter pool excludes lower-order profiles and requires at least 60 RR IPL balls faced.
        - Bowlers are compared within powerplay, middle, and death phases. Each player appears once using their strongest phase profile.
        - Baselines use each player's non-pressure RR IPL performance in the available seasons.
        """
    )
    st.subheader("Pressure definition")
    st.markdown(
        "The context score is computed before each delivery; high pressure is an index of 60 or higher. First-innings pressure combines "
        "wickets lost, scoring below phase pace, and innings progress. Chase pressure combines required run rate against observed scoring "
        "pace, wickets lost, and balls elapsed."
    )
    st.subheader("Data coverage and selection")
    st.json(evaluation)
    st.caption(
        f"Batter selection used {batter_cutoff['minimum_pressure_balls']} pressure ball(s) in {batter_cutoff['minimum_pressure_matches']} match(es). "
        f"Bowler selection used {bowler_cutoff['minimum_pressure_balls']} ball(s) in {bowler_cutoff['minimum_pressure_matches']} match(es). "
        "Bowling run totals estimate minimum wide/Overstep penalties because the supplied extras fields are incomplete."
    )

st.markdown("---")
st.caption("Rananiti · Decision support from historical IPL evidence. Scores support review and do not predict future performance.")
