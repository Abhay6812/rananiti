"""Transparent, context-aware pressure index computed before each delivery."""
import numpy as np
import pandas as pd


def detect_pressure(state: pd.DataFrame, threshold: float = 60) -> pd.DataFrame:
    df = state.copy()
    first = df[df["innings"].eq(1)]
    legal = first[first["legal_ball"]]
    stage_rate = legal.groupby("match_stage")["team_runs"].sum().div(
        legal.groupby("match_stage")["legal_ball"].sum().replace(0, np.nan)
    ).mul(6)
    overall_rate = (legal["team_runs"].sum() * 6 / max(legal["legal_ball"].sum(), 1))
    df["expected_stage_run_rate"] = df["match_stage"].map(stage_rate).fillna(overall_rate)

    # First-innings pressure combines lost wickets, falling behind the
    # dataset's phase-specific scoring pace, and the innings' time pressure.
    first_shortfall = ((df["expected_stage_run_rate"] - df["current_run_rate"]).clip(lower=0)
                       / df["expected_stage_run_rate"].replace(0, np.nan)).fillna(0).clip(0, 1)
    first_shortfall = first_shortfall.where(df["legal_balls_before"] >= 6, 0)
    innings_progress = (1 - df["balls_remaining"] / df["balls_in_innings"].replace(0, np.nan)).fillna(0).clip(0, 1)
    wicket_pressure = (df["wickets_before"] / 10).clip(0, 1)
    first_pressure = 100 * (0.40 * wicket_pressure + 0.40 * first_shortfall + 0.20 * innings_progress)

    # In a chase, pressure depends on the required rate relative to the
    # observed first-innings scoring pace, wickets lost, and balls remaining.
    rr_ratio = (df["required_run_rate"] / max(overall_rate, 1)).replace([np.inf, -np.inf], np.nan).fillna(0)
    chase_rate_pressure = ((rr_ratio - 1).clip(lower=0) / 1.0).clip(0, 1)
    chase_pressure = 100 * (0.55 * chase_rate_pressure + 0.30 * wicket_pressure + 0.15 * innings_progress)

    df["pressure_index"] = np.where(df["innings"].eq(1), first_pressure, chase_pressure).clip(0, 100).round(1)
    df["pressure_level"] = pd.cut(df["pressure_index"], [-1, 30, threshold - 0.001, 100], labels=["Low", "Medium", "High"]).astype(str)
    df["is_pressure"] = df["pressure_index"] >= threshold
    return df
