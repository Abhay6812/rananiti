"""Role-aware pressure ratings with explicit sample confidence."""
import numpy as np
import pandas as pd

from config import MIN_PRESSURE_BALLS, MIN_PRESSURE_MATCHES


def _rank(df: pd.DataFrame, column: str, group: str, ascending: bool) -> pd.Series:
    return df.groupby(group, dropna=False)[column].rank(pct=True, ascending=ascending) * 100


def _weighted_score(df: pd.DataFrame, components: dict[str, tuple[str, bool]], group: str) -> pd.Series:
    values = pd.DataFrame(index=df.index)
    weights = {}
    for name, (column, ascending) in components.items():
        values[name] = _rank(df, column, group, ascending)
        weights[name] = 1 / len(components)
    w = pd.Series(weights)
    weighted = values.mul(w, axis=1)
    return weighted.sum(axis=1, min_count=1).div(values.notna().mul(w, axis=1).sum(axis=1).replace(0, np.nan))


def _confidence(df: pd.DataFrame) -> pd.Series:
    ball_conf = df["pressure_balls"] / (df["pressure_balls"] + 60)
    match_conf = df["pressure_matches"] / (df["pressure_matches"] + 5)
    return np.sqrt(ball_conf.clip(0, 1) * match_conf.clip(0, 1))


def add_batter_scores(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["retention"] = (100 * d["pressure_strike_rate"] / d["strike_rate"].replace(0, np.nan)).clip(upper=150)
    components = {
        "pressure_strike_rate": ("pressure_strike_rate", True),
        "pressure_average": ("pressure_average", True),
        "dot_avoidance": ("pressure_dot_pct", False),
        "boundary_scoring": ("pressure_boundary_pct", True),
        "dismissal_avoidance": ("pressure_dismissal_rate", False),
        "baseline_retention": ("retention", True),
        "match_consistency": ("pressure_match_strike_rate_std", False),
    }
    d["pressure_performance"] = _weighted_score(d, components, "role")
    conf = _confidence(d)
    d["confidence"] = (100 * conf).round(1)
    d["trust_score"] = (50 + conf * (d["pressure_performance"] - 50)).round(1)
    risk_components = {
        "performance_drop": ("retention", False),
        "dismissal_risk": ("pressure_dismissal_rate", True),
        "dot_ball_risk": ("pressure_dot_pct", True),
        "match_volatility": ("pressure_match_strike_rate_std", True),
    }
    d["risk_score"] = _weighted_score(d, risk_components, "role").round(1)
    d["eligible"] = (d["pressure_balls"] >= MIN_PRESSURE_BALLS) & (d["pressure_matches"] >= MIN_PRESSURE_MATCHES)
    return d


def add_bowler_scores(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    group = "phase" if "phase" in d else "player_id"
    d["retention"] = (100 * d["normal_economy"] / d["pressure_economy"].replace(0, np.nan)).clip(upper=150)
    components = {
        "pressure_economy": ("pressure_economy", False),
        "dot_ball_control": ("pressure_dot_pct", True),
        "wicket_rate": ("pressure_wickets_per_over", True),
        "boundary_prevention": ("pressure_boundary_pct", False),
        "baseline_retention": ("retention", True),
        "match_consistency": ("pressure_economy_std", False),
    }
    d["pressure_performance"] = _weighted_score(d, components, group)
    conf = _confidence(d)
    d["confidence"] = (100 * conf).round(1)
    d["trust_score"] = (50 + conf * (d["pressure_performance"] - 50)).round(1)
    risk_components = {
        "economy_deterioration": ("economy_variation", True),
        "boundary_risk": ("pressure_boundary_pct", True),
        "wicket_scarcity": ("pressure_wickets_per_over", False),
        "match_volatility": ("pressure_economy_std", True),
    }
    d["risk_score"] = _weighted_score(d, risk_components, group).round(1)
    d["eligible"] = (d["pressure_balls"] >= MIN_PRESSURE_BALLS) & (d["pressure_matches"] >= MIN_PRESSURE_MATCHES)
    return d
