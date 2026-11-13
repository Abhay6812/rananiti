"""Create Rajasthan Royals pressure rankings and Power BI Top X tables."""
import json
from pathlib import Path

import pandas as pd

from config import BALLS_FILE, MATCHES_FILE, OUTPUTS, RAW_DATA
from src.feature_engineering.batter_features import batter_summary
from src.feature_engineering.bowler_features import bowler_summary
from src.pressure_engine.match_state import reconstruct_match_state
from src.pressure_engine.pressure_detection import detect_pressure
from src.scoring.trust_score import add_batter_scores, add_bowler_scores


def build_rr_topx(max_top_x: int = 10) -> dict:
    balls = pd.read_csv(BALLS_FILE, low_memory=False)
    matches = pd.read_csv(MATCHES_FILE, low_memory=False)
    competitions = pd.read_csv(RAW_DATA / "competitions.csv", low_memory=False)
    mapping = pd.read_csv(RAW_DATA / "competition_team_player_mapping.csv", low_memory=False)
    competitions["format_clean"] = competitions["match_format"].astype(str).str.strip().str.upper()
    ipl = competitions[
        competitions["comp_name"].astype(str).str.match(r"^IPL\s+\d{4}$", case=False, na=False)
        & pd.to_numeric(competitions["season"], errors="coerce").ge(2022)
    ].copy()
    matches["match_date"] = pd.to_datetime(matches["match_date"], errors="coerce")
    matches = matches[matches["comp_id"].isin(ipl["comp_id"]) & matches["match_date"].ge("2022-01-01")].copy()
    matches = matches.drop_duplicates("match_id")
    balls = balls[balls["match_id"].isin(matches["match_id"])].copy()

    rr = mapping[mapping["team_name"].astype(str).str.casefold().eq("rajasthan royals")]
    rr = rr[rr["comp_id"].isin(ipl["comp_id"])].drop_duplicates(["comp_id", "team_id"])
    if rr.empty:
        raise ValueError("Rajasthan Royals team mapping was not found for IPL seasons 2022 onward.")

    state = detect_pressure(reconstruct_match_state(balls, matches))
    match_comp = matches[["match_id", "comp_id"]]
    state = state.merge(match_comp, on="match_id", how="inner")
    rr_ids = rr[["comp_id", "team_id"]].rename(columns={"team_id": "rr_team_id"})
    state = state.merge(rr_ids, on="comp_id", how="inner")
    rr_batting = state[pd.to_numeric(state["batting_team_id"], errors="coerce").eq(pd.to_numeric(state["rr_team_id"], errors="coerce"))].copy()
    rr_bowling = state[pd.to_numeric(state["bowling_team_id"], errors="coerce").eq(pd.to_numeric(state["rr_team_id"], errors="coerce"))].copy()

    batters = add_batter_scores(batter_summary(rr_batting))
    # The inferred Lower Order group mainly represents tail-end bowling roles
    # in this feed. Require a meaningful RR batting history as well, so players
    # with only a few tail-end appearances don't enter the batter list.
    rr_batter_candidates = int(batters["player_id"].nunique())
    excluded_lower_order = int(batters.loc[batters["role"].eq("Lower Order"), "player_id"].nunique())
    excluded_under_60_balls = int(batters.loc[batters["role"].ne("Lower Order") & batters["balls"].lt(60), "player_id"].nunique())
    batters = batters[batters["role"].ne("Lower Order") & batters["balls"].ge(60)].copy()
    bowlers = add_bowler_scores(bowler_summary(rr_bowling, by_phase=True))
    thresholds = [(30, 5), (12, 3), (12, 1), (1, 1)]

    def rank_unique(data: pd.DataFrame, exposure: str):
        selected = data.iloc[0:0].copy()
        used = None
        qualifying_count = 0
        for min_balls, min_matches in thresholds:
            pool = data[data[exposure].ge(min_balls) & data["pressure_matches"].ge(min_matches)]
            pool = pool.sort_values(["trust_score", "risk_score", "confidence", exposure],
                                    ascending=[False, True, False, False], na_position="last")
            pool = pool.drop_duplicates("player_id")
            if len(pool) >= min(max_top_x, data["player_id"].nunique()):
                selected, used = pool.head(max_top_x), (min_balls, min_matches)
                qualifying_count = len(pool)
                break
            if len(pool) > len(selected):
                selected, used = pool.head(max_top_x), (min_balls, min_matches)
                qualifying_count = len(pool)
        if used is None:
            used = thresholds[-1]
        selected = selected.reset_index(drop=True)
        selected.insert(0, "rank", range(1, len(selected) + 1))
        return selected, {"minimum_pressure_balls": used[0], "minimum_pressure_matches": used[1],
                          "qualifying_players": int(qualifying_count),
                          "candidate_players": int(data["player_id"].nunique())}

    batter_rank, batter_eligibility = rank_unique(batters, "pressure_balls")
    bowler_rank, bowler_eligibility = rank_unique(bowlers, "pressure_balls")
    batter_cols = ["rank", "player_id", "player", "role", "trust_score", "risk_score", "confidence",
                   "pressure_matches", "pressure_balls", "pressure_runs", "pressure_strike_rate",
                   "pressure_average", "pressure_dot_pct", "pressure_boundary_pct", "strike_rate", "average"]
    bowler_cols = ["rank", "player_id", "player", "phase", "trust_score", "risk_score", "confidence",
                   "pressure_matches", "pressure_balls", "pressure_overs", "pressure_wickets",
                   "pressure_economy", "pressure_average", "pressure_dot_pct", "pressure_boundary_pct",
                   "economy", "normal_economy"]
    batter_rank = batter_rank[[c for c in batter_cols if c in batter_rank.columns]]
    bowler_rank = bowler_rank[[c for c in bowler_cols if c in bowler_rank.columns]]
    max_top_x = max(1, min(int(max_top_x), 10))

    def expand(data: pd.DataFrame) -> pd.DataFrame:
        frames = []
        for top_x in range(1, max_top_x + 1):
            block = data[data["rank"].le(top_x)].copy()
            block.insert(0, "top_x", top_x)
            frames.append(block)
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    OUTPUTS.mkdir(parents=True, exist_ok=True)
    batter_rank.to_csv(OUTPUTS / "rr_batter_rankings.csv", index=False)
    bowler_rank.to_csv(OUTPUTS / "rr_bowler_rankings.csv", index=False)
    expand(batter_rank).to_csv(OUTPUTS / "rr_batters_topx.csv", index=False)
    expand(bowler_rank).to_csv(OUTPUTS / "rr_bowlers_topx.csv", index=False)
    pd.DataFrame({"top_x": range(1, max_top_x + 1)}).to_csv(OUTPUTS / "top_x_values.csv", index=False)
    evaluation = {
        "team": "Rajasthan Royals",
        "seasons": sorted(pd.to_numeric(ipl["season"], errors="coerce").dropna().astype(int).unique().tolist()),
        "matches": int(matches["match_id"].nunique()),
        "rr_matches": int(state.loc[state["rr_team_id"].notna(), "match_id"].nunique()),
        "rr_high_pressure_batting_deliveries": int(rr_batting["is_pressure"].sum()),
        "rr_high_pressure_bowling_deliveries": int(rr_bowling["is_pressure"].sum()),
        "batter_eligibility": batter_eligibility,
        "bowler_eligibility": bowler_eligibility,
        "batter_screen": "Median batting position above 7 and at least 60 RR IPL balls faced across 2022-2026.",
        "batter_candidates_before_screen": rr_batter_candidates,
        "excluded_lower_order_players": excluded_lower_order,
        "excluded_non_lower_order_under_60_balls": excluded_under_60_balls,
        "batter_candidates_after_screen": int(batters["player_id"].nunique()),
        "top_x_max": max_top_x,
    }
    (OUTPUTS / "rr_topx_evaluation.json").write_text(json.dumps(evaluation, indent=2), encoding="utf-8")
    return {"batters": batter_rank, "bowlers": bowler_rank, "evaluation": evaluation}


if __name__ == "__main__":
    result = build_rr_topx()
    print("RR Top batters:")
    print(result["batters"].head(10).to_string(index=False))
    print("\nRR Top bowlers:")
    print(result["bowlers"].head(10).to_string(index=False))
    print("\nEvaluation:", json.dumps(result["evaluation"], indent=2))
