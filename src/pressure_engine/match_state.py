"""Reconstruct a delivery's match state using only information before the ball."""
import numpy as np
import pandas as pd


def _bool(series):
    return series.astype(str).str.strip().str.lower().isin(["true", "1", "yes"])


def reconstruct_match_state(balls: pd.DataFrame, matches: pd.DataFrame | None = None) -> pd.DataFrame:
    required = {"match_id", "innings", "overid", "over_ball_num", "batting_team_id", "bowling_team_id", "striker_id", "bowler_id", "runs"}
    missing = required - set(balls.columns)
    if missing:
        raise ValueError(f"ball_by_ball.csv is missing required columns: {', '.join(sorted(missing))}")
    df = balls.copy()
    df["_source_order"] = np.arange(len(df))
    df["innings"] = pd.to_numeric(df["innings"], errors="coerce").fillna(1).astype(int)
    df["overid"] = pd.to_numeric(df["overid"], errors="coerce").fillna(0)
    df["over_ball_num"] = pd.to_numeric(df["over_ball_num"], errors="coerce").fillna(0)
    df["runs"] = pd.to_numeric(df["runs"], errors="coerce").fillna(0)
    for col in ("extras_2_runs",):
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df["is_wicket"] = _bool(df["is_wicket"]) if "is_wicket" in df else False
    df = df.sort_values(["match_id", "innings", "overid", "over_ball_num", "_source_order"], kind="stable")
    # In this feed `runs` is batter runs and extras1_runs is a categorical
    # code (1=Overstep, 2=wide, ... 6=no extras), not a number of runs.
    explicit_extras = df["extras_2_runs"] if "extras_2_runs" in df else 0
    extra_type = df.get("extras_type", pd.Series("", index=df.index)).astype(str).str.lower()
    # Wide and no-ball penalties are at least one run; the source does not
    # provide reliable penalties for every such delivery, so flag the estimate.
    penalty = extra_type.str.contains("wide|overstep", regex=True).astype(int)
    df["team_runs"] = df["runs"] + explicit_extras + penalty
    df["legal_ball"] = ~extra_type.str.contains("wide|overstep", regex=True)
    grp = ["match_id", "innings"]
    df["score_before"] = df.groupby(grp)["team_runs"].cumsum() - df["team_runs"]
    df["wickets_before"] = df.groupby(grp)["is_wicket"].cumsum() - df["is_wicket"].astype(int)
    df["legal_balls_before"] = df.groupby(grp)["legal_ball"].cumsum() - df["legal_ball"].astype(int)
    df["balls_in_innings"] = 120
    if matches is not None and {"match_id", "first_inn_revised_overs", "second_inn_revised_overs"}.issubset(matches.columns):
        overs = matches[["match_id", "first_inn_revised_overs", "second_inn_revised_overs"]].drop_duplicates("match_id").copy()
        overs["first_inn_revised_overs"] = pd.to_numeric(overs["first_inn_revised_overs"], errors="coerce")
        overs["second_inn_revised_overs"] = pd.to_numeric(overs["second_inn_revised_overs"], errors="coerce")
        df = df.merge(overs, on="match_id", how="left")
        innings_overs = np.where(df["innings"].eq(1), df["first_inn_revised_overs"], df["second_inn_revised_overs"])
        df["balls_in_innings"] = pd.Series(innings_overs, index=df.index).where(pd.Series(innings_overs, index=df.index).gt(0), 20).mul(6)
    df["balls_remaining"] = (df["balls_in_innings"] - df["legal_balls_before"]).clip(lower=0)
    df["wickets_remaining"] = (10 - df["wickets_before"]).clip(lower=0)
    df["current_run_rate"] = np.where(df["legal_balls_before"] > 0, df["score_before"] * 6 / df["legal_balls_before"], 0)
    # Innings-one totals provide the chase target, keyed by match. Revised targets can override.
    totals = df[df["innings"] == 1].groupby("match_id")["team_runs"].sum().add(1).rename("target")
    df = df.join(totals, on="match_id")
    if matches is not None and {"match_id", "revised_target"}.issubset(matches.columns):
        revised = matches[["match_id", "revised_target"]].drop_duplicates("match_id").set_index("match_id")["revised_target"]
        revised = pd.to_numeric(revised, errors="coerce")
        df["target"] = df["match_id"].map(revised).where(lambda s: s.gt(0), df["target"])
    df["runs_required"] = (df["target"] - df["score_before"]).clip(lower=0)
    df["required_run_rate"] = np.where((df["innings"] > 1) & (df["balls_remaining"] > 0), df["runs_required"] * 6 / df["balls_remaining"], np.nan)
    df["match_stage"] = pd.cut(df["legal_balls_before"], [-1, 35, 89, 1000], labels=["Powerplay", "Middle", "Death"], right=True).astype(str)
    return df.drop(columns=["_source_order"])
