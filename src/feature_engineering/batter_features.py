import numpy as np
import pandas as pd


def _flag(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin(["true", "1", "yes"])


def _role(position) -> str:
    if pd.isna(position):
        return "Unclassified"
    if position <= 2:
        return "Opener"
    if position == 3:
        return "Top Order"
    if position <= 5:
        return "Middle Order"
    if position <= 7:
        return "Finisher"
    return "Lower Order"


def batter_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Player-level batting stats, splitting high-pressure and baseline balls."""
    d = df.copy()
    d["batter_runs"] = pd.to_numeric(d["runs"], errors="coerce").fillna(0)
    d["four"] = _flag(d.get("is_four", pd.Series(False, index=d.index)))
    d["six"] = _flag(d.get("is_six", pd.Series(False, index=d.index)))
    d["wicket"] = _flag(d.get("is_wicket", pd.Series(False, index=d.index)))
    dismissed_id = pd.to_numeric(d.get("dismissed_player_id", d["striker_id"]), errors="coerce")
    striker_id = pd.to_numeric(d["striker_id"], errors="coerce")
    d["batter_dismissed"] = d["wicket"] & dismissed_id.eq(striker_id)
    d["boundary"] = d["four"] | d["six"]
    extras_type = d.get("extras_type", pd.Series("", index=d.index)).astype(str).str.lower()
    d["ball_faced"] = ~extras_type.str.contains("wide", regex=True)

    rows = []
    for (pid, name), g in d.groupby(["striker_id", "striker_name"], dropna=False):
        p, normal = g[g["is_pressure"]], g[~g["is_pressure"]]
        p_faced = p["ball_faced"].sum()
        faced = g["ball_faced"].sum()
        outs = int(g["batter_dismissed"].sum())
        pressure_outs = int(p["batter_dismissed"].sum())
        p_runs = p["batter_runs"].sum()
        runs = g["batter_runs"].sum()
        match_stats = p.groupby(["match_id", "innings"], dropna=False).agg(
            match_runs=("batter_runs", "sum"), match_balls=("ball_faced", "sum")
        )
        match_stats = match_stats[match_stats["match_balls"].gt(0)]
        match_sr = 100 * match_stats["match_runs"] / match_stats["match_balls"]
        order = pd.to_numeric(g.get("batting_order", pd.Series(index=g.index, dtype=float)), errors="coerce").median()
        rows.append({
            "player_id": pid, "player": name, "role": _role(order), "batting_position": order,
            "balls": int(faced), "pressure_balls": int(p_faced),
            "pressure_matches": int(len(match_stats)), "runs": runs, "pressure_runs": p_runs,
            "strike_rate": 100 * runs / max(faced, 1),
            "pressure_strike_rate": 100 * p_runs / max(p_faced, 1),
            "average": runs / outs if outs else np.nan,
            "pressure_average": p_runs / pressure_outs if pressure_outs else np.nan,
            "dismissals": outs, "pressure_dismissals": pressure_outs,
            "dismissal_rate": 100 * outs / max(faced, 1),
            "pressure_dismissal_rate": 100 * pressure_outs / max(p_faced, 1),
            "dot_pct": 100 * (g.loc[g["ball_faced"], "batter_runs"].eq(0)).mean() if faced else np.nan,
            "pressure_dot_pct": 100 * (p.loc[p["ball_faced"], "batter_runs"].eq(0)).mean() if p_faced else np.nan,
            "boundary_pct": 100 * g.loc[g["ball_faced"], "boundary"].mean() if faced else np.nan,
            "pressure_boundary_pct": 100 * p.loc[p["ball_faced"], "boundary"].mean() if p_faced else np.nan,
            "pressure_match_strike_rate_std": match_sr.std(ddof=0) if len(match_sr) >= 2 else np.nan,
        })
    return pd.DataFrame(rows)
