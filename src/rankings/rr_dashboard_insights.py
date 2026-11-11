"""Backend service layer for the Rajasthan Royals Streamlit dashboard."""
from __future__ import annotations

import pandas as pd

from src.rankings.rr_topx import build_rr_topx


def load_rr_dashboard_insights(max_top_x: int = 10) -> dict:
    """Return ranked RR data plus concise, evidence-linked dashboard insights."""
    result = build_rr_topx(max_top_x=max_top_x)
    batters = result["batters"].copy()
    bowlers = result["bowlers"].copy()
    evaluation = result["evaluation"]

    batter_leader = batters.sort_values(["trust_score", "risk_score"], ascending=[False, True]).iloc[0] if not batters.empty else None
    bowler_leader = bowlers.sort_values(["trust_score", "risk_score"], ascending=[False, True]).iloc[0] if not bowlers.empty else None
    high_risk_batter = batters.sort_values(["risk_score", "trust_score"], ascending=[False, True]).iloc[0] if not batters.empty else None
    high_risk_bowler = bowlers.sort_values(["risk_score", "trust_score"], ascending=[False, True]).iloc[0] if not bowlers.empty else None

    insights = []
    if batter_leader is not None:
        insights.append({
            "title": "Batting trust leader",
            "player": batter_leader["player"],
            "detail": f"Trust {batter_leader['trust_score']:.1f} with {int(batter_leader['pressure_balls'])} pressure balls across {int(batter_leader['pressure_matches'])} matches.",
            "kind": "positive",
        })
    if bowler_leader is not None:
        insights.append({
            "title": "Bowling trust leader",
            "player": bowler_leader["player"],
            "detail": f"Trust {bowler_leader['trust_score']:.1f} in the {str(bowler_leader['phase']).lower()} phase; pressure economy {bowler_leader['pressure_economy']:.2f}.",
            "kind": "positive",
        })
    if high_risk_batter is not None:
        insights.append({
            "title": "Batting risk to review",
            "player": high_risk_batter["player"],
            "detail": f"Risk {high_risk_batter['risk_score']:.1f}; interpret with confidence {high_risk_batter['confidence']:.1f} and pressure exposure of {int(high_risk_batter['pressure_balls'])} balls.",
            "kind": "caution",
        })
    if high_risk_bowler is not None:
        insights.append({
            "title": "Bowling risk to review",
            "player": high_risk_bowler["player"],
            "detail": f"Risk {high_risk_bowler['risk_score']:.1f} in the {str(high_risk_bowler['phase']).lower()} phase; pressure economy {high_risk_bowler['pressure_economy']:.2f}.",
            "kind": "caution",
        })

    return {
        "batters": batters,
        "bowlers": bowlers,
        "evaluation": evaluation,
        "insights": insights,
        "metric_notes": {
            "trust": "Role and phase adjusted pressure performance, confidence shrunk toward 50 for smaller samples.",
            "risk": "Independent risk signal; review alongside confidence, pressure balls, and match count.",
        },
    }


def compare_batter_rates(frame: pd.DataFrame) -> pd.DataFrame:
    view = frame[["player", "pressure_strike_rate", "strike_rate"]].copy()
    return view.rename(columns={"player": "Player", "pressure_strike_rate": "Under pressure", "strike_rate": "Usual baseline"})


def compare_bowler_economy(frame: pd.DataFrame) -> pd.DataFrame:
    view = frame[["player", "pressure_economy", "economy"]].copy()
    return view.rename(columns={"player": "Player", "pressure_economy": "Under pressure", "economy": "Usual baseline"})
