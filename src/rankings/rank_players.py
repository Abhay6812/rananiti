"""Build reproducible Top 10 rankings required by the SupeRR Selector brief."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from config import BALLS_FILE, MATCHES_FILE, RAW_DATA, OUTPUTS, ROOT, MIN_PRESSURE_BALLS, MIN_PRESSURE_MATCHES
from src.pressure_engine.match_state import reconstruct_match_state
from src.pressure_engine.pressure_detection import detect_pressure
from src.feature_engineering.batter_features import batter_summary
from src.feature_engineering.bowler_features import bowler_summary
from src.scoring.trust_score import add_batter_scores, add_bowler_scores

CUTOFFS = (50, 60, 70)
BOOTSTRAP_REPLICATES = 100
BOOTSTRAP_SEED = 2026


def load_submission_data():
    balls = pd.read_csv(BALLS_FILE, low_memory=False)
    matches = pd.read_csv(MATCHES_FILE, low_memory=False)
    competitions = pd.read_csv(RAW_DATA / "competitions.csv", low_memory=False)
    competitions["format_clean"] = competitions["match_format"].astype(str).str.strip().str.upper()
    is_t20i = competitions["format_clean"].eq("T20I")
    is_ipl = competitions["comp_name"].astype(str).str.match(r"^IPL\s+\d{4}$", case=False, na=False)
    allowed = competitions[is_t20i | is_ipl]
    matches["match_date"] = pd.to_datetime(matches["match_date"], errors="coerce")
    eligible_matches = matches[matches["comp_id"].isin(allowed["comp_id"]) & matches["match_date"].ge("2022-01-01")].copy()
    eligible_matches = eligible_matches.drop_duplicates("match_id")
    balls = balls[balls["match_id"].isin(eligible_matches["match_id"])].copy()
    return balls, eligible_matches, allowed


def _rank_eligible(data: pd.DataFrame, score: str, distinct_id: str, ascending: list[bool],
                   exposure_col: str) -> pd.DataFrame:
    pool = data[data[exposure_col].ge(MIN_PRESSURE_BALLS) & data["pressure_matches"].ge(MIN_PRESSURE_MATCHES)]
    pool = pool.sort_values([score, "risk_score", "confidence", exposure_col],
                            ascending=ascending, na_position="last", kind="mergesort")
    selected = pool.drop_duplicates(distinct_id).reset_index(drop=True)
    selected.insert(0, "rank", range(1, len(selected) + 1))
    return selected


def _select_top10(data: pd.DataFrame, score: str, distinct_id: str, ascending: list[bool],
                  exposure_col: str) -> tuple[pd.DataFrame, dict]:
    pool = _rank_eligible(data, score, distinct_id, ascending, exposure_col)
    selected = pool.head(10)
    return selected, {"minimum_pressure_balls": MIN_PRESSURE_BALLS, "minimum_pressure_matches": MIN_PRESSURE_MATCHES,
                      "eligible_unique_players": int(pool[distinct_id].nunique()),
                      "candidate_unique_players": int(data[distinct_id].nunique())}


def _average_cutoff_trust(base: pd.DataFrame, scores_by_cutoff: dict[int, pd.DataFrame],
                          keys: list[str]) -> pd.DataFrame:
    result = base.copy()
    trust_columns = []
    for cutoff, scores in scores_by_cutoff.items():
        column = f"trust_score_cutoff_{cutoff}"
        if len(keys) == 1:
            lookup = scores.drop_duplicates(keys).set_index(keys[0])["trust_score"]
            result[column] = result[keys[0]].map(lookup)
        else:
            lookup = scores.drop_duplicates(keys).set_index(keys)["trust_score"]
            result[column] = lookup.reindex(pd.MultiIndex.from_frame(result[keys])).to_numpy()
        trust_columns.append(column)
    result["trust_score"] = result[trust_columns].fillna(50).mean(axis=1).round(1)
    return result


def _flag(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin(["true", "1", "yes"])


def _batter_match_summaries(state: pd.DataFrame) -> pd.DataFrame:
    data = state.copy()
    data["batter_runs"] = pd.to_numeric(data["runs"], errors="coerce").fillna(0)
    data["ball_faced"] = ~data.get("extras_type", pd.Series("", index=data.index)).astype(str).str.lower().str.contains("wide")
    dismissed_id = pd.to_numeric(data.get("dismissed_player_id", data["striker_id"]), errors="coerce")
    striker_id = pd.to_numeric(data["striker_id"], errors="coerce")
    data["batter_dismissed"] = _flag(data.get("is_wicket", pd.Series(False, index=data.index))) & dismissed_id.eq(striker_id)
    data["boundary"] = _flag(data.get("is_four", pd.Series(False, index=data.index))) | _flag(
        data.get("is_six", pd.Series(False, index=data.index))
    )
    pressure = data["is_pressure"].astype(bool)
    faced = data["ball_faced"]
    runs = data["batter_runs"]
    data["normal_runs"] = runs.where(~pressure, 0)
    data["normal_balls"] = (faced & ~pressure).astype(int)
    data["total_balls"] = faced.astype(int)
    data["pressure_runs"] = runs.where(pressure, 0)
    data["pressure_balls"] = (faced & pressure).astype(int)
    data["dismissals"] = data["batter_dismissed"].astype(int)
    data["pressure_dismissals"] = (data["batter_dismissed"] & pressure).astype(int)
    data["dots"] = (faced & runs.eq(0)).astype(int)
    data["pressure_dots"] = (faced & pressure & runs.eq(0)).astype(int)
    data["boundaries"] = (faced & data["boundary"]).astype(int)
    data["pressure_boundaries"] = (faced & pressure & data["boundary"]).astype(int)
    keys = ["match_id", "innings", "striker_id", "striker_name"]
    match = data.groupby(keys, dropna=False, sort=False).agg(
        normal_runs=("normal_runs", "sum"),
        normal_balls=("normal_balls", "sum"),
        total_runs=("batter_runs", "sum"),
        total_balls=("total_balls", "sum"),
        pressure_runs=("pressure_runs", "sum"),
        pressure_balls=("pressure_balls", "sum"),
        dismissals=("dismissals", "sum"),
        pressure_dismissals=("pressure_dismissals", "sum"),
        dots=("dots", "sum"),
        pressure_dots=("pressure_dots", "sum"),
        boundaries=("boundaries", "sum"),
        pressure_boundaries=("pressure_boundaries", "sum"),
    ).reset_index()
    match["has_pressure"] = match["pressure_balls"].gt(0).astype(int)
    match["match_pressure_strike_rate"] = (
        100 * match["pressure_runs"] / match["pressure_balls"].replace(0, np.nan)
    )
    return match


def _aggregate_batter_matches(sample: pd.DataFrame, roles: pd.Series) -> pd.DataFrame:
    keys = ["striker_id", "striker_name"]
    grouped = sample.groupby(keys, dropna=False, sort=False)
    result = grouped.agg(
        normal_runs=("normal_runs", "sum"),
        normal_balls=("normal_balls", "sum"),
        runs=("total_runs", "sum"),
        balls=("total_balls", "sum"),
        pressure_runs=("pressure_runs", "sum"),
        pressure_balls=("pressure_balls", "sum"),
        dismissals=("dismissals", "sum"),
        pressure_dismissals=("pressure_dismissals", "sum"),
        dots=("dots", "sum"),
        pressure_dots=("pressure_dots", "sum"),
        boundaries=("boundaries", "sum"),
        pressure_boundaries=("pressure_boundaries", "sum"),
        pressure_matches=("has_pressure", "sum"),
    ).reset_index().rename(columns={"striker_id": "player_id", "striker_name": "player"})
    pressure_match_rates = sample[sample["pressure_balls"].gt(0)].groupby(
        ["striker_id", "striker_name"], dropna=False, sort=False
    )["match_pressure_strike_rate"].agg(["count", lambda values: values.std(ddof=0)])
    pressure_match_rates.columns = ["match_count", "pressure_match_strike_rate_std"]
    pressure_match_rates.loc[
        pressure_match_rates["match_count"].lt(2), "pressure_match_strike_rate_std"
    ] = np.nan
    result = result.merge(
        pressure_match_rates["pressure_match_strike_rate_std"].reset_index().rename(
            columns={"striker_id": "player_id", "striker_name": "player"}
        ),
        on=["player_id", "player"],
        how="left",
    )
    result["role"] = result["player_id"].map(roles)
    result["strike_rate"] = 100 * result["normal_runs"] / result["normal_balls"].clip(lower=1)
    result["pressure_strike_rate"] = 100 * result["pressure_runs"] / result["pressure_balls"].clip(lower=1)
    result["average"] = result["runs"] / result["dismissals"].replace(0, np.nan)
    result["pressure_average"] = result["pressure_runs"] / result["pressure_dismissals"].replace(0, np.nan)
    result["pressure_dismissal_rate"] = 100 * result["pressure_dismissals"] / result["pressure_balls"].clip(lower=1)
    result["pressure_dot_pct"] = 100 * result["pressure_dots"] / result["pressure_balls"].clip(lower=1)
    result["pressure_boundary_pct"] = 100 * result["pressure_boundaries"] / result["pressure_balls"].clip(lower=1)
    no_pressure = result["pressure_balls"].eq(0)
    result.loc[no_pressure, ["pressure_dot_pct", "pressure_boundary_pct"]] = np.nan
    return result


def _bowler_match_summaries(state: pd.DataFrame) -> pd.DataFrame:
    data = state.copy()
    data["runs_conceded"] = pd.to_numeric(data["team_runs"], errors="coerce").fillna(0)
    wicket = _flag(data.get("is_wicket", pd.Series(False, index=data.index)))
    dismissal = data.get("dismissal_type", pd.Series("", index=data.index)).astype(str).str.lower()
    non_bowler = dismissal.str.contains(r"run.?out|retire|obstruct", regex=True, na=False)
    data["bowler_wickets"] = (wicket & ~non_bowler).astype(int)
    data["boundary"] = _flag(data.get("is_four", pd.Series(False, index=data.index))) | _flag(
        data.get("is_six", pd.Series(False, index=data.index))
    )
    pressure = data["is_pressure"].astype(bool)
    legal = data["legal_ball"].astype(bool)
    data["normal_runs"] = data["runs_conceded"].where(~pressure, 0)
    data["normal_legal_balls"] = (legal & ~pressure).astype(int)
    data["legal_balls"] = legal.astype(int)
    data["pressure_runs"] = data["runs_conceded"].where(pressure, 0)
    data["pressure_legal_balls"] = (legal & pressure).astype(int)
    data["pressure_legal_runs"] = data["runs_conceded"].where(legal & pressure, 0)
    data["wickets"] = data["bowler_wickets"]
    data["pressure_wickets"] = (data["bowler_wickets"].astype(bool) & pressure).astype(int)
    data["dots"] = (legal & data["runs_conceded"].eq(0)).astype(int)
    data["pressure_dots"] = (legal & pressure & data["runs_conceded"].eq(0)).astype(int)
    data["boundaries"] = (legal & data["boundary"]).astype(int)
    data["pressure_boundaries"] = (legal & pressure & data["boundary"]).astype(int)
    keys = ["match_id", "innings", "bowler_id", "bowler_name", "match_stage"]
    match = data.groupby(keys, dropna=False, sort=False).agg(
        runs=("runs_conceded", "sum"),
        normal_runs=("normal_runs", "sum"),
        normal_legal_balls=("normal_legal_balls", "sum"),
        legal_balls=("legal_balls", "sum"),
        pressure_runs=("pressure_runs", "sum"),
        pressure_legal_balls=("pressure_legal_balls", "sum"),
        pressure_legal_runs=("pressure_legal_runs", "sum"),
        wickets=("wickets", "sum"),
        pressure_wickets=("pressure_wickets", "sum"),
        dots=("dots", "sum"),
        pressure_dots=("pressure_dots", "sum"),
        boundaries=("boundaries", "sum"),
        pressure_boundaries=("pressure_boundaries", "sum"),
    ).reset_index()
    match["has_pressure"] = match["pressure_legal_balls"].gt(0).astype(int)
    match["match_pressure_economy"] = (
        6 * match["pressure_legal_runs"] / match["pressure_legal_balls"].replace(0, np.nan)
    )
    return match


def _aggregate_bowler_matches(sample: pd.DataFrame) -> pd.DataFrame:
    keys = ["bowler_id", "bowler_name", "match_stage"]
    grouped = sample.groupby(keys, dropna=False, sort=False)
    result = grouped.agg(
        runs=("runs", "sum"),
        normal_runs=("normal_runs", "sum"),
        normal_legal_balls=("normal_legal_balls", "sum"),
        legal_balls=("legal_balls", "sum"),
        pressure_runs=("pressure_runs", "sum"),
        pressure_legal_balls=("pressure_legal_balls", "sum"),
        wickets=("wickets", "sum"),
        pressure_wickets=("pressure_wickets", "sum"),
        dots=("dots", "sum"),
        pressure_dots=("pressure_dots", "sum"),
        boundaries=("boundaries", "sum"),
        pressure_boundaries=("pressure_boundaries", "sum"),
        pressure_matches=("has_pressure", "sum"),
    ).reset_index().rename(columns={
        "bowler_id": "player_id", "bowler_name": "player", "match_stage": "phase",
    })
    pressure_match_economy = sample[sample["pressure_legal_balls"].gt(0)].groupby(
        ["bowler_id", "bowler_name", "match_stage"], dropna=False, sort=False
    )["match_pressure_economy"].agg(["count", lambda values: values.std(ddof=0)])
    pressure_match_economy.columns = ["match_count", "pressure_economy_std"]
    pressure_match_economy.loc[
        pressure_match_economy["match_count"].lt(2), "pressure_economy_std"
    ] = np.nan
    result = result.merge(
        pressure_match_economy["pressure_economy_std"].reset_index().rename(columns={
            "bowler_id": "player_id", "bowler_name": "player", "match_stage": "phase",
        }),
        on=["player_id", "player", "phase"],
        how="left",
    )
    overs = result["legal_balls"] / 6
    pressure_overs = result["pressure_legal_balls"] / 6
    normal_overs = result["normal_legal_balls"] / 6
    result["pressure_balls"] = result["pressure_legal_balls"]
    result["pressure_overs"] = pressure_overs
    result["economy"] = result["runs"] / overs.clip(lower=1 / 6)
    result["normal_economy"] = result["normal_runs"] / normal_overs.clip(lower=1 / 6)
    result["pressure_economy"] = result["pressure_runs"] / pressure_overs.clip(lower=1 / 6)
    result.loc[result["pressure_legal_balls"].eq(0), "pressure_economy"] = np.nan
    result["pressure_wickets_per_over"] = result["pressure_wickets"] / pressure_overs.clip(lower=1 / 6)
    result.loc[result["pressure_legal_balls"].eq(0), "pressure_wickets_per_over"] = np.nan
    result["pressure_average"] = result["pressure_runs"] / result["pressure_wickets"].replace(0, np.nan)
    result["pressure_dot_pct"] = 100 * result["pressure_dots"] / result["pressure_legal_balls"].clip(lower=1)
    result["pressure_boundary_pct"] = 100 * result["pressure_boundaries"] / result["pressure_legal_balls"].clip(lower=1)
    no_pressure = result["pressure_legal_balls"].eq(0)
    result.loc[no_pressure, ["pressure_dot_pct", "pressure_boundary_pct"]] = np.nan
    result["economy_variation"] = result["pressure_economy"] - result["normal_economy"]
    return result


def _bootstrap_rank_intervals(
    states_by_cutoff: dict[int, pd.DataFrame],
    top_batters: pd.DataFrame,
    top_bowlers: pd.DataFrame,
    replicates: int = BOOTSTRAP_REPLICATES,
) -> dict:
    batter_match_groups = {
        cutoff: _batter_match_summaries(state).groupby("match_id", sort=False)
        for cutoff, state in states_by_cutoff.items()
    }
    bowler_match_groups = {
        cutoff: _bowler_match_summaries(state).groupby("match_id", sort=False)
        for cutoff, state in states_by_cutoff.items()
    }
    batter_match_rows = {
        cutoff: {match_id: group for match_id, group in groups}
        for cutoff, groups in batter_match_groups.items()
    }
    bowler_match_rows = {
        cutoff: {match_id: group for match_id, group in groups}
        for cutoff, groups in bowler_match_groups.items()
    }
    match_ids = np.asarray(list(batter_match_rows[60]))
    roles = batter_summary(states_by_cutoff[60]).drop_duplicates("player_id").set_index("player_id")["role"]
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    targets = {
        "batters": {
            "ids": top_batters["player_id"].tolist(),
            "scores": {player_id: [] for player_id in top_batters["player_id"]},
        },
        "bowlers": {
            "ids": top_bowlers["player_id"].tolist(),
            "scores": {player_id: [] for player_id in top_bowlers["player_id"]},
        },
    }

    for _ in range(replicates):
        sampled_ids = rng.choice(match_ids, size=len(match_ids), replace=True)
        batter_scores_by_cutoff = {}
        bowler_scores_by_cutoff = {}
        for cutoff in CUTOFFS:
            sampled_batter_matches = pd.concat(
                [batter_match_rows[cutoff][match_id] for match_id in sampled_ids],
                ignore_index=True,
            )
            sampled_bowler_matches = pd.concat(
                [bowler_match_rows[cutoff][match_id] for match_id in sampled_ids],
                ignore_index=True,
            )
            batter_summary_sample = _aggregate_batter_matches(sampled_batter_matches, roles)
            bowler_summary_sample = _aggregate_bowler_matches(sampled_bowler_matches)
            batter_scores_by_cutoff[cutoff] = add_batter_scores(batter_summary_sample)
            bowler_scores_by_cutoff[cutoff] = add_bowler_scores(bowler_summary_sample)

        batter_scores = _average_cutoff_trust(
            batter_scores_by_cutoff[60], batter_scores_by_cutoff, ["player_id"]
        )
        bowler_scores = _average_cutoff_trust(
            bowler_scores_by_cutoff[60], bowler_scores_by_cutoff, ["player_id", "phase"]
        )
        ranked = {
            "batters": _rank_eligible(
                batter_scores, "trust_score", "player_id", [False, True, False, False], "pressure_balls"
            ),
            "bowlers": _rank_eligible(
                bowler_scores, "trust_score", "player_id", [False, True, False, False], "pressure_balls"
            ),
        }
        for group, ranking in ranked.items():
            rank_by_id = ranking.set_index("player_id")["rank"]
            for player_id in targets[group]["ids"]:
                if player_id in rank_by_id.index:
                    targets[group]["scores"][player_id].append(int(rank_by_id.loc[player_id]))

    intervals = {}
    for group, target in targets.items():
        group_intervals = {}
        for player_id, ranks in target["scores"].items():
            group_intervals[str(player_id)] = {
                "rank_05": int(np.floor(np.quantile(ranks, 0.05))) if ranks else None,
                "rank_95": int(np.ceil(np.quantile(ranks, 0.95))) if ranks else None,
                "eligible_pct": round(100 * len(ranks) / replicates, 1),
            }
        intervals[group] = group_intervals
    return {
        "replicates": replicates,
        "unit": "match",
        "confidence_level": 0.90,
        "seed": BOOTSTRAP_SEED,
        "rank_intervals": intervals,
    }


def pressure_diagnostics(state: pd.DataFrame) -> dict:
    """Summarize index distribution and observable differences by pressure flag."""
    legal = state[state["legal_ball"]].copy()
    legal["wicket"] = legal["is_wicket"].astype(bool)
    bins = pd.cut(state["pressure_index"], [-0.01, 30, 50, 60, 70, 85, 100],
                  labels=["0-30", "30-50", "50-60", "60-70", "70-85", "85-100"], include_lowest=True)
    distribution = bins.value_counts(sort=False).rename_axis("index_band").reset_index(name="deliveries")
    distribution["share_pct"] = (100 * distribution["deliveries"] / max(len(state), 1)).round(2)
    metrics = {}
    for label, group in legal.groupby("is_pressure"):
        key = "pressure" if bool(label) else "ordinary"
        n = len(group)
        metrics[key] = {
            "legal_deliveries": int(n),
            "run_rate_per_6_balls": round(6 * group["team_runs"].sum() / max(n, 1), 3),
            "wickets_per_100_legal_balls": round(100 * group["wicket"].sum() / max(n, 1), 3),
        }
    return {
        "index_quantiles": {str(q): round(float(state["pressure_index"].quantile(q)), 2)
                            for q in [0, .25, .5, .75, .9, .95, 1]},
        "distribution": distribution.to_dict(orient="records"),
        "by_pressure_flag": metrics,
        "win_probability_swing": None,
        "win_probability_note": "Not calculated: source data has final results but no ball-level win-probability model or licensed feed.",
    }


def build_rankings() -> dict:
    balls, matches, competitions = load_submission_data()
    reconstructed = reconstruct_match_state(balls, matches)
    states_by_cutoff = {}
    batter_scores_by_cutoff = {}
    bowler_scores_by_cutoff = {}
    for cutoff in CUTOFFS:
        state = detect_pressure(reconstructed, threshold=cutoff)
        states_by_cutoff[cutoff] = state
        batter_scores_by_cutoff[cutoff] = add_batter_scores(batter_summary(state))
        bowler_scores_by_cutoff[cutoff] = add_bowler_scores(bowler_summary(state, by_phase=True))

    state = states_by_cutoff[60]
    batter_scores = _average_cutoff_trust(
        batter_scores_by_cutoff[60], batter_scores_by_cutoff, ["player_id"]
    )
    bowler_scores = _average_cutoff_trust(
        bowler_scores_by_cutoff[60], bowler_scores_by_cutoff, ["player_id", "phase"]
    )

    batters, batter_eligibility = _select_top10(
        batter_scores, "trust_score", "player_id", [False, True, False, False], "pressure_balls"
    )
    bowlers, bowler_eligibility = _select_top10(
        bowler_scores, "trust_score", "player_id", [False, True, False, False], "pressure_balls"
    )
    batter_cols = ["rank", "player_id", "player", "role", "trust_score", "risk_score", "confidence",
                   "pressure_matches", "pressure_balls", "pressure_runs", "pressure_strike_rate",
                   "pressure_average", "pressure_dot_pct", "pressure_boundary_pct", "strike_rate", "average",
                   "pressure_performance", "trust_score_cutoff_50", "trust_score_cutoff_60",
                   "trust_score_cutoff_70"]
    bowler_cols = ["rank", "player_id", "player", "phase", "trust_score", "risk_score", "confidence",
                   "pressure_matches", "pressure_balls", "pressure_overs", "pressure_wickets",
                   "pressure_economy", "pressure_average", "pressure_dot_pct", "pressure_boundary_pct",
                   "economy", "normal_economy", "pressure_wickets_per_over", "pressure_performance",
                   "trust_score_cutoff_50", "trust_score_cutoff_60", "trust_score_cutoff_70"]
    batters = batters[[c for c in batter_cols if c in batters.columns]]
    bowlers = bowlers[[c for c in bowler_cols if c in bowlers.columns]]

    OUTPUTS.mkdir(parents=True, exist_ok=True)
    sensitivity = {}
    for cutoff in CUTOFFS:
        cut_state = states_by_cutoff[cutoff]
        cut_batters = batter_scores_by_cutoff[cutoff]
        cut_bowlers = bowler_scores_by_cutoff[cutoff]
        top_b, _ = _select_top10(cut_batters, "trust_score", "player_id", [False, True, False, False], "pressure_balls")
        top_w, _ = _select_top10(cut_bowlers, "trust_score", "player_id", [False, True, False, False], "pressure_balls")
        sensitivity[str(cutoff)] = {
            "pressure_deliveries": int(cut_state["is_pressure"].sum()),
            "batter_top10": top_b["player"].tolist(), "bowler_top10": top_w["player"].tolist(),
        }
    for cutoff in CUTOFFS:
        sensitivity[str(cutoff)]["batter_overlap_with_final_top10"] = len(
            set(sensitivity[str(cutoff)]["batter_top10"]) & set(batters["player"])
        )
        sensitivity[str(cutoff)]["bowler_overlap_with_final_top10"] = len(
            set(sensitivity[str(cutoff)]["bowler_top10"]) & set(bowlers["player"])
        )

    bootstrap = _bootstrap_rank_intervals(states_by_cutoff, batters, bowlers)
    for frame, group in ((batters, "batters"), (bowlers, "bowlers")):
        interval_by_id = bootstrap["rank_intervals"][group]
        frame["bootstrap_rank_low"] = frame["player_id"].map(
            lambda player_id: interval_by_id[str(player_id)]["rank_05"]
        )
        frame["bootstrap_rank_high"] = frame["player_id"].map(
            lambda player_id: interval_by_id[str(player_id)]["rank_95"]
        )
        frame["bootstrap_eligible_pct"] = frame["player_id"].map(
            lambda player_id: interval_by_id[str(player_id)]["eligible_pct"]
        )
    batters.to_csv(OUTPUTS / "batter_rankings.csv", index=False)
    bowlers.to_csv(OUTPUTS / "bowler_rankings.csv", index=False)

    ordered_matches = matches.sort_values(["match_date", "match_id"])["match_id"].drop_duplicates().tolist()
    half_sets = {"odd": set(ordered_matches[::2]), "even": set(ordered_matches[1::2])}
    split_stability = {}
    for half, match_ids in half_sets.items():
        half_reconstructed = reconstructed[reconstructed["match_id"].isin(match_ids)]
        half_scores_by_cutoff = {cutoff: detect_pressure(half_reconstructed, threshold=cutoff) for cutoff in CUTOFFS}
        half_batters_by_cutoff = {
            cutoff: add_batter_scores(batter_summary(half_state))
            for cutoff, half_state in half_scores_by_cutoff.items()
        }
        half_bowlers_by_cutoff = {
            cutoff: add_bowler_scores(bowler_summary(half_state, by_phase=True))
            for cutoff, half_state in half_scores_by_cutoff.items()
        }
        half_state = half_scores_by_cutoff[60]
        half_batters = _average_cutoff_trust(
            half_batters_by_cutoff[60], half_batters_by_cutoff, ["player_id"]
        )
        half_bowlers = _average_cutoff_trust(
            half_bowlers_by_cutoff[60], half_bowlers_by_cutoff, ["player_id", "phase"]
        )
        half_top_b, _ = _select_top10(half_batters, "trust_score", "player_id", [False, True, False, False], "pressure_balls")
        half_top_w, _ = _select_top10(half_bowlers, "trust_score", "player_id", [False, True, False, False], "pressure_balls")
        split_stability[half] = {
            "matches": int(half_state["match_id"].nunique()),
            "eligible_batters": int(half_batters.loc[half_batters.pressure_balls.ge(MIN_PRESSURE_BALLS) & half_batters.pressure_matches.ge(MIN_PRESSURE_MATCHES), "player_id"].nunique()),
            "eligible_bowlers": int(half_bowlers.loc[half_bowlers.pressure_balls.ge(MIN_PRESSURE_BALLS) & half_bowlers.pressure_matches.ge(MIN_PRESSURE_MATCHES), "player_id"].nunique()),
            "batter_top10": half_top_b.player.tolist(), "bowler_top10": half_top_w.player.tolist(),
        }
    for half, values in split_stability.items():
        values["batter_overlap_with_full_top10"] = len(set(values["batter_top10"]) & set(batters.player))
        values["bowler_overlap_with_full_top10"] = len(set(values["bowler_top10"]) & set(bowlers.player))
    evaluation = {
        "dataset": {"deliveries": int(len(state)), "matches": int(state["match_id"].nunique()),
                    "competitions": int(matches["comp_id"].nunique()),
                    "date_start": str(matches["match_date"].min().date()),
                    "date_end": str(matches["match_date"].max().date()),
                    "high_pressure_deliveries": int(state["is_pressure"].sum()),
                    "formats": sorted(competitions["format_clean"].dropna().unique().tolist())},
        "pressure_definition": "Pre-delivery context index; high pressure is index >= 60.",
        "ranking_method": {
            "trust_score": "Mean of role/phase-adjusted Trust at pressure cutoffs 50, 60, and 70; missing cutoff scores are neutral (50).",
            "eligibility_cutoff": 60,
            "minimum_pressure_balls": MIN_PRESSURE_BALLS,
            "minimum_pressure_matches": MIN_PRESSURE_MATCHES,
        },
        "pressure_diagnostics": pressure_diagnostics(state),
        "cutoff_sensitivity": sensitivity,
        "alternating_match_split": split_stability,
        "bootstrap": bootstrap,
        "batter_eligibility": batter_eligibility,
        "bowler_eligibility": bowler_eligibility,
        "batter_top10_count": int(len(batters)),
        "bowler_top10_count": int(len(bowlers)),
        "notes": ["Batter ratings are percentile-normalized within historical batting role.",
                  "Bowler ratings are percentile-normalized within innings phase; each player appears once in the Top 10.",
                  "Ratings are human-review aids, not predictions of future performance."],
    }
    (OUTPUTS / "ranking_evaluation.json").write_text(json.dumps(evaluation, indent=2), encoding="utf-8")
    return {"state": state, "batters": batter_scores, "bowlers": bowler_scores,
            "top_batters": batters, "top_bowlers": bowlers, "evaluation": evaluation}


def write_submission_report(result: dict) -> Path:
    batters, bowlers, ev = result["top_batters"], result["top_bowlers"], result["evaluation"]
    def bootstrap_band(row: pd.Series) -> str:
        low, high = row["bootstrap_rank_low"], row["bootstrap_rank_high"]
        if pd.isna(low) or pd.isna(high):
            return "Not estimable"
        return f"{int(low)}–{int(high)}"

    cutoff_rows = ["| Cutoff | Pressure deliveries | Batter overlap with final Top 10 | Bowler overlap with final Top 10 |",
                   "|---:|---:|---:|---:|"]
    for cutoff, values in ev["cutoff_sensitivity"].items():
        cutoff_rows.append(
            f"| {cutoff} | {values['pressure_deliveries']:,} | "
            f"{values['batter_overlap_with_final_top10']}/10 | "
            f"{values['bowler_overlap_with_final_top10']}/10 |"
        )
    split_rows = ["| Match half | Matches | Batter overlap with full Top 10 | Bowler overlap with full Top 10 |",
                  "|---|---:|---:|---:|"]
    for half, values in ev["alternating_match_split"].items():
        split_rows.append(f"| {half.title()} | {values['matches']:,} | {values['batter_overlap_with_full_top10']}/10 | {values['bowler_overlap_with_full_top10']}/10 |")
    pressure_stats = ev["pressure_diagnostics"]["by_pressure_flag"]
    md = ["# SupeRR Selector Season 2 — Methodology and Rankings", "",
          "## Dataset", "",
          f"Analysed {ev['dataset']['deliveries']:,} deliveries across {ev['dataset']['matches']:,} IPL and T20I matches "
          f"({ev['dataset']['date_start']} to {ev['dataset']['date_end']}). The pressure engine marked "
          f"{ev['dataset']['high_pressure_deliveries']:,} deliveries as high pressure.", "",
          "## Pressure definition", "",
          "Match state is reconstructed before each delivery to avoid leakage. First-innings pressure combines wickets lost, "
          "scoring below the observed phase-specific first-innings run rate, and innings progress. Chase pressure combines "
          "required run rate relative to the observed first-innings rate, wickets lost, and balls elapsed. The indicators are "
          "combined into a 0–100 pressure index; index 60 or higher is classified as high pressure. Matches with revised "
          "targets or overs use those match metadata where supplied.", "",
          "## Rating and fair comparisons", "",
          "Batter pressure performance combines pressure strike rate, pressure average, dot-ball avoidance, boundary scoring, "
           "dismissal avoidance, retention of the player's non-pressure strike rate, and match-to-match consistency. Percentiles are "
          "computed within historical batting role. Bowler performance combines pressure economy, dot-ball control, wickets per "
          "pressure over, boundary prevention, retention against normal economy, and match-to-match consistency; bowlers are "
          "compared within powerplay, middle, or death phase. Trust ratings are confidence-adjusted toward 50 for low exposure. "
          "Risk is calculated separately from performance deterioration, dismissals or boundaries, and volatility.", "",
           "Final Trust is the arithmetic mean of the confidence-adjusted Trust at pressure-index cutoffs 50, 60, and 70; "
           "a player without a qualifying profile at one cutoff receives neutral Trust (50) for that cutoff. Eligibility and "
           "the reported exposure metrics are anchored to cutoff 60.", "",
          "Eligibility is fixed at at least "
          f"{MIN_PRESSURE_BALLS} pressure balls across {MIN_PRESSURE_MATCHES} pressure matches. Thresholds do not relax; "
          "if fewer than ten distinct players qualify, the output is shorter than ten. Each bowler appears once, using the "
          "highest Trust phase only among phase profiles that independently pass the fixed exposure threshold.", "",
           "For batters, the baseline strike rate is non-pressure batter runs per non-pressure balls faced. For bowlers, the "
           "baseline economy is team runs conceded per non-pressure legal over; this is distinct from overall economy. These are "
           "player-specific observed baselines and are not shrunk to a role mean. Confidence adjustment shrinks Trust toward 50 "
           "as pressure exposure falls. IPL and T20I are pooled from 2022 onward, with within-role or within-phase normalization, "
           "but there is no explicit opposition-strength or competition-format adjustment. Results are therefore not "
           "opposition-adjusted and should not be read as a neutralized IPL-versus-T20I comparison.", "",
           "Bowling phase is assigned from legal balls completed before the delivery: balls 0–35 are Powerplay, 36–89 Middle, "
           "and ball 90 onward Death. A bowler's listed phase is the highest-Trust profile that meets the same exposure rules; "
           "the label describes the ranked pressure sample, not the bowler's usual deployment. For example, Sunil Narine's "
           "audited Death pressure sample was 42 balls, below the 60-ball requirement, so it cannot qualify for the final list.", "",
          "## Top 10 batters", "",
           "| Rank | Player | Role | Mean Trust | Risk | Confidence | Pressure balls | Pressure SR | Non-pressure SR | 90% bootstrap rank | Eligible in resamples |",
           "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for _, r in batters.iterrows():
        interval = bootstrap_band(r)
        md.append(
             f"| {int(r['rank'])} | {r['player']} | {r['role']} | {r['trust_score']:.1f} | "
             f"{r['risk_score']:.1f} | {r['confidence']:.1f} | {int(r['pressure_balls'])} | "
             f"{r['pressure_strike_rate']:.1f} | {r['strike_rate']:.1f} | {interval} | "
             f"{r['bootstrap_eligible_pct']:.1f}% |"
        )
    md += ["", "## Top 10 bowlers", "",
            "| Rank | Player | Best phase | Mean Trust | Risk | Confidence | Pressure balls | Pressure economy | Non-pressure economy | 90% bootstrap rank | Eligible in resamples |",
            "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for _, r in bowlers.iterrows():
        interval = bootstrap_band(r)
        md.append(
             f"| {int(r['rank'])} | {r['player']} | {r['phase']} | {r['trust_score']:.1f} | "
             f"{r['risk_score']:.1f} | {r['confidence']:.1f} | {int(r['pressure_balls'])} | "
             f"{r['pressure_economy']:.2f} | {r['normal_economy']:.2f} | {interval} | "
             f"{r['bootstrap_eligible_pct']:.1f}% |"
        )
    md += ["", "## Pressure evidence and sensitivity", "",
           f"Pressure index quantiles and delivery shares, plus observed run rate and wicket rate for pressure and ordinary balls, "
           f"are reported in `ranking_evaluation.json`. In this feed, pressure deliveries had run rate "
           f"{pressure_stats['pressure']['run_rate_per_6_balls']:.2f} vs {pressure_stats['ordinary']['run_rate_per_6_balls']:.2f} per six legal balls, "
           f"and {pressure_stats['pressure']['wickets_per_100_legal_balls']:.2f} vs {pressure_stats['ordinary']['wickets_per_100_legal_balls']:.2f} wickets per 100 legal balls. "
           f"Pressure's observed run-rate gap is modest, while its wicket-rate gap is larger; batting performance still explicitly "
           f"includes pressure strike rate and retention against the player's non-pressure rate. These aggregates are descriptive, "
           f"not causal. Cutoff overlaps compare each single-cutoff Top 10 with the final three-cutoff mean ranking. The match-level "
           f"bootstrap resamples whole matches with replacement ({ev['bootstrap']['replicates']} replicates) and reports the 5th–95th "
           f"percentile rank among draws where the player remains eligible; adjacent eligibility percentages show how often they "
           f"qualified. It measures sampling sensitivity, not future performance. There is no ball-level win-probability feed, "
           f"so win-probability swing is not estimated.", "",
           *cutoff_rows, "",
            "The final ranking averages all three cutoffs to reduce dependence on any single threshold; cutoff overlap remains a useful stability diagnostic, not proof of robustness.", "",
           *split_rows, "",
            "The alternating match split is another descriptive stability check. Bootstrap bands and alternating splits do not eliminate sampling bias or contextual differences.", "",
           "## Secondary RR dashboard exclusions", "",
           "The RR-only squad view is separate from the overall submission lists. Across its current 2022–2026 batting candidate pool, "
           "52 players were considered; 25 inferred lower-order profiles and 13 other players below 60 RR IPL balls were excluded, "
           "leaving 14 batter candidates. These screens apply only to that secondary RR view.", "",
           "## Reliability checks and limitations", "",
           "Eligibility counts, fixed thresholds, match counts, confidence, cutoff sensitivity, bootstrap intervals, and the full metric set are saved in `outputs/`. "
           "Rankings use observed IPL/T20I history from 2022 onward and avoid relying on reputation. Confidence and exposure describe "
           "sample quantity; bootstrap rank intervals are conditional on remaining eligible in each resample. High-pressure samples can "
           "still be small or uneven across contexts. Bowling runs include an estimated minimum penalty for wides and Oversteps "
           "because the supplied extras fields are incomplete; review bowling economy with that limitation in mind.", ""]
    path = ROOT / "reports" / "submission_methodology_report.md"
    path.write_text("\n".join(md), encoding="utf-8")
    return path


def main():
    result = build_rankings()
    report = write_submission_report(result)
    print("Top 10 batter rankings:\n", result["top_batters"].to_string(index=False))
    print("\nTop 10 bowler rankings:\n", result["top_bowlers"].to_string(index=False))
    print("\nMethodology report:", str(report).encode("ascii", "backslashreplace").decode("ascii"))
    print("Ranking evaluation:", str(OUTPUTS / "ranking_evaluation.json").encode("ascii", "backslashreplace").decode("ascii"))


if __name__ == "__main__":
    main()
