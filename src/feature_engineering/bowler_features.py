import numpy as np
import pandas as pd


def _flag(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin(["true", "1", "yes"])


def bowler_summary(df: pd.DataFrame, by_phase: bool = False) -> pd.DataFrame:
    """Bowling performance summary, optionally comparing within innings phase."""
    d = df.copy()
    d["runs_conceded"] = pd.to_numeric(d["team_runs"], errors="coerce").fillna(0)
    d["wicket"] = _flag(d.get("is_wicket", pd.Series(False, index=d.index)))
    dismissal = d.get("dismissal_type", pd.Series("", index=d.index)).astype(str).str.lower()
    non_bowler = dismissal.str.contains(r"run.?out|retire|obstruct", regex=True, na=False)
    d["bowler_wicket"] = d["wicket"] & ~non_bowler
    d["boundary"] = _flag(d.get("is_four", pd.Series(False, index=d.index))) | _flag(d.get("is_six", pd.Series(False, index=d.index)))

    keys = ["bowler_id", "bowler_name"] + (["match_stage"] if by_phase else [])
    rows = []
    for key, g in d.groupby(keys, dropna=False):
        pid, name = key[:2]
        phase = key[2] if len(key) > 2 else None
        p, normal = g[g["is_pressure"]], g[~g["is_pressure"]]
        legal_balls = int(g["legal_ball"].sum())
        p_legal = p[p["legal_ball"]]
        normal_legal = normal[normal["legal_ball"]]
        overs = legal_balls / 6
        p_overs = len(p_legal) / 6
        pressure_match = p_legal.groupby(["match_id", "innings"], dropna=False).agg(
            match_runs=("runs_conceded", "sum"), match_balls=("legal_ball", "sum")
        )
        pressure_match = pressure_match[pressure_match["match_balls"].gt(0)]
        per_match_economy = 6 * pressure_match["match_runs"] / pressure_match["match_balls"]
        pressure_wickets = int(p["bowler_wicket"].sum())
        normal_overs = int(normal["legal_ball"].sum()) / 6
        row = {
            "player_id": pid, "player": name, "balls": legal_balls, "overs": overs,
            "pressure_balls": len(p_legal), "pressure_overs": p_overs,
            "pressure_matches": int(len(pressure_match)),
            "economy": g["runs_conceded"].sum() / max(overs, 1/6),
            "normal_economy": normal["runs_conceded"].sum() / max(normal_overs, 1/6),
            "pressure_economy": p["runs_conceded"].sum() / max(p_overs, 1/6) if len(p_legal) else np.nan,
            "wickets": int(g["bowler_wicket"].sum()), "pressure_wickets": pressure_wickets,
            "pressure_wickets_per_over": pressure_wickets / max(p_overs, 1/6) if len(p_legal) else np.nan,
            "pressure_average": p["runs_conceded"].sum() / pressure_wickets if pressure_wickets else np.nan,
            "dot_pct": 100 * (g.loc[g["legal_ball"], "runs_conceded"].eq(0)).mean() if legal_balls else np.nan,
            "pressure_dot_pct": 100 * p_legal["runs_conceded"].eq(0).mean() if len(p_legal) else np.nan,
            "boundary_pct": 100 * g.loc[g["legal_ball"], "boundary"].mean() if legal_balls else np.nan,
            "pressure_boundary_pct": 100 * p_legal["boundary"].mean() if len(p_legal) else np.nan,
            "pressure_economy_std": per_match_economy.std(ddof=0) if len(per_match_economy) >= 2 else np.nan,
            "economy_variation": (p["runs_conceded"].sum() / max(p_overs, 1/6)) - (normal["runs_conceded"].sum() / max(normal_overs, 1/6)) if len(p_legal) else np.nan,
        }
        if phase is not None:
            row["phase"] = phase
        rows.append(row)
    return pd.DataFrame(rows)
