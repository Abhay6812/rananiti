"""Build reproducible Top 10 rankings required by the SupeRR Selector brief."""
import json
from pathlib import Path

import pandas as pd

from config import BALLS_FILE, MATCHES_FILE, RAW_DATA, OUTPUTS, ROOT, MIN_PRESSURE_BALLS, MIN_PRESSURE_MATCHES
from src.pressure_engine.match_state import reconstruct_match_state
from src.pressure_engine.pressure_detection import detect_pressure
from src.feature_engineering.batter_features import batter_summary
from src.feature_engineering.bowler_features import bowler_summary
from src.scoring.trust_score import add_batter_scores, add_bowler_scores


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


def _select_top10(data: pd.DataFrame, score: str, distinct_id: str, ascending: list[bool],
                  exposure_col: str) -> tuple[pd.DataFrame, dict]:
    pool = data[data[exposure_col].ge(MIN_PRESSURE_BALLS) & data["pressure_matches"].ge(MIN_PRESSURE_MATCHES)]
    pool = pool.sort_values([score, "risk_score", "confidence", exposure_col],
                            ascending=ascending, na_position="last")
    selected = pool.drop_duplicates(distinct_id).head(10)
    selected = selected.reset_index(drop=True)
    selected.insert(0, "rank", range(1, len(selected) + 1))
    return selected, {"minimum_pressure_balls": MIN_PRESSURE_BALLS, "minimum_pressure_matches": MIN_PRESSURE_MATCHES,
                      "eligible_unique_players": int(pool[distinct_id].nunique()),
                      "candidate_unique_players": int(data[distinct_id].nunique())}


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
    state = detect_pressure(reconstructed, threshold=60)
    batter_scores = add_batter_scores(batter_summary(state))
    bowler_scores = add_bowler_scores(bowler_summary(state, by_phase=True))

    batters, batter_eligibility = _select_top10(
        batter_scores, "trust_score", "player_id", [False, True, False, False], "pressure_balls"
    )
    bowlers, bowler_eligibility = _select_top10(
        bowler_scores, "trust_score", "player_id", [False, True, False, False], "pressure_balls"
    )
    batter_cols = ["rank", "player_id", "player", "role", "trust_score", "risk_score", "confidence",
                   "pressure_matches", "pressure_balls", "pressure_runs", "pressure_strike_rate",
                   "pressure_average", "pressure_dot_pct", "pressure_boundary_pct", "strike_rate", "average",
                   "pressure_performance"]
    bowler_cols = ["rank", "player_id", "player", "phase", "trust_score", "risk_score", "confidence",
                   "pressure_matches", "pressure_balls", "pressure_overs", "pressure_wickets",
                   "pressure_economy", "pressure_average", "pressure_dot_pct", "pressure_boundary_pct",
                   "economy", "pressure_wickets_per_over", "pressure_performance"]
    batters = batters[[c for c in batter_cols if c in batters.columns]]
    bowlers = bowlers[[c for c in bowler_cols if c in bowlers.columns]]

    OUTPUTS.mkdir(parents=True, exist_ok=True)
    batters.to_csv(OUTPUTS / "batter_rankings.csv", index=False)
    bowlers.to_csv(OUTPUTS / "bowler_rankings.csv", index=False)
    sensitivity = {}
    for cutoff in (50, 60, 70):
        if cutoff == 60:
            cut_state, cut_batters, cut_bowlers = state, batter_scores, bowler_scores
        else:
            cut_state = detect_pressure(reconstructed, threshold=cutoff)
            cut_batters = add_batter_scores(batter_summary(cut_state))
            cut_bowlers = add_bowler_scores(bowler_summary(cut_state, by_phase=True))
        top_b, _ = _select_top10(cut_batters, "trust_score", "player_id", [False, True, False, False], "pressure_balls")
        top_w, _ = _select_top10(cut_bowlers, "trust_score", "player_id", [False, True, False, False], "pressure_balls")
        sensitivity[str(cutoff)] = {
            "pressure_deliveries": int(cut_state["is_pressure"].sum()),
            "batter_top10": top_b["player"].tolist(), "bowler_top10": top_w["player"].tolist(),
        }
    ordered_matches = matches.sort_values(["match_date", "match_id"])["match_id"].drop_duplicates().tolist()
    half_sets = {"odd": set(ordered_matches[::2]), "even": set(ordered_matches[1::2])}
    split_stability = {}
    for half, match_ids in half_sets.items():
        half_state = state[state["match_id"].isin(match_ids)]
        half_batters = add_batter_scores(batter_summary(half_state))
        half_bowlers = add_bowler_scores(bowler_summary(half_state, by_phase=True))
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
        "pressure_diagnostics": pressure_diagnostics(state),
        "cutoff_sensitivity": sensitivity,
        "alternating_match_split": split_stability,
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
    cutoff_rows = ["| Cutoff | Pressure deliveries | Batter overlap with 60 | Bowler overlap with 60 |",
                   "|---:|---:|---:|---:|"]
    baseline_batters = set(ev["cutoff_sensitivity"]["60"]["batter_top10"])
    baseline_bowlers = set(ev["cutoff_sensitivity"]["60"]["bowler_top10"])
    for cutoff, values in ev["cutoff_sensitivity"].items():
        cutoff_rows.append(f"| {cutoff} | {values['pressure_deliveries']:,} | {len(baseline_batters & set(values['batter_top10']))}/10 | {len(baseline_bowlers & set(values['bowler_top10']))}/10 |")
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
          "dismissal avoidance, retention of the player's normal strike rate, and match-to-match consistency. Percentiles are "
          "computed within historical batting role. Bowler performance combines pressure economy, dot-ball control, wickets per "
          "pressure over, boundary prevention, retention against normal economy, and match-to-match consistency; bowlers are "
          "compared within powerplay, middle, or death phase. Trust ratings are confidence-adjusted toward 50 for low exposure. "
          "Risk is calculated separately from performance deterioration, dismissals or boundaries, and volatility.", "",
          "Eligibility is fixed at at least "
          f"{MIN_PRESSURE_BALLS} pressure balls across {MIN_PRESSURE_MATCHES} pressure matches. Thresholds do not relax; "
          "if fewer than ten distinct players qualify, the output is shorter than ten. Each bowler appears once, using the "
          "highest Trust phase only among phase profiles that independently pass the fixed exposure threshold.", "",
          "The batting baseline is the player's aggregate batting rate across the eligible sample; bowler retention compares pressure "
          "economy with the non-pressure economy. Baselines are not shrunk to a role mean. Confidence adjustment shrinks the final "
          "Trust score toward 50 as pressure exposure falls. "
          "Players from IPL and T20I are pooled in the eligible dataset and compared within role or phase; there is no explicit "
          "opposition-strength or competition-format adjustment, so this remains a limitation.", "",
          "## Top 10 batters", "",
          "| Rank | Player | Role | Trust | Risk | Pressure balls | Pressure SR | Pressure average | Dot % |",
          "|---:|---|---|---:|---:|---:|---:|---:|---:|"]
    for _, r in batters.iterrows():
        md.append(f"| {int(r['rank'])} | {r['player']} | {r['role']} | {r['trust_score']:.1f} | {r['risk_score']:.1f} | {int(r['pressure_balls'])} | {r['pressure_strike_rate']:.1f} | {r['pressure_average']:.1f} | {r['pressure_dot_pct']:.1f} |")
    md += ["", "## Top 10 bowlers", "",
           "| Rank | Player | Best phase | Trust | Risk | Pressure balls | Pressure overs | Pressure economy | Wickets | Dot % |",
           "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for _, r in bowlers.iterrows():
        avg = f"{r['pressure_average']:.1f}" if pd.notna(r.get("pressure_average")) else "—"
        md.append(f"| {int(r['rank'])} | {r['player']} | {r['phase']} | {r['trust_score']:.1f} | {r['risk_score']:.1f} | {int(r['pressure_balls'])} | {r['pressure_overs']:.1f} | {r['pressure_economy']:.1f} | {int(r['pressure_wickets'])} | {r['pressure_dot_pct']:.1f} |")
    md += ["", "## Pressure evidence and sensitivity", "",
           f"Pressure index quantiles and delivery shares, plus observed run rate and wicket rate for pressure and ordinary balls, "
           f"are reported in `ranking_evaluation.json`. In this feed, pressure deliveries had run rate "
           f"{pressure_stats['pressure']['run_rate_per_6_balls']:.2f} vs {pressure_stats['ordinary']['run_rate_per_6_balls']:.2f} per six legal balls, "
           f"and {pressure_stats['pressure']['wickets_per_100_legal_balls']:.2f} vs {pressure_stats['ordinary']['wickets_per_100_legal_balls']:.2f} wickets per 100 legal balls. "
           f"Top-10 overlap is recalculated at cutoffs 50, 60 and 70. These are "
           f"descriptive sensitivity checks. Alternating date-ordered match halves are compared with the full-data Top 10 in "
           f"`ranking_evaluation.json`; a bootstrap rank interval is not yet implemented. There is no ball-level win-probability feed, "
           f"so win-probability swing is not estimated.", "",
           *cutoff_rows, "",
           "Top-10 sensitivity is limited across the tested cutoffs. Treat the index cutoff as a material modeling choice, not a validated optimum.", "",
           *split_rows, "",
           "The alternating match split shows rank instability, especially for bowlers; low overlap indicates these lists need validation before strong selection decisions.", "",
           "## Secondary RR dashboard exclusions", "",
           "The RR-only squad view is separate from the overall submission lists. Across its current 2022–2026 batting candidate pool, "
           "52 players were considered; 25 inferred lower-order profiles and 13 other players below 60 RR IPL balls were excluded, "
           "leaving 14 batter candidates. These screens apply only to that secondary RR view.", "",
           "## Reliability checks and limitations", "",
           "Eligibility counts, fixed thresholds, match counts, confidence, alternating-split overlap, and the full metric set are saved in `outputs/`. "
           "Rankings use observed IPL/T20I history from 2022 onward and avoid relying on reputation. Confidence and exposure describe "
           "sample quantity; the alternating split is a simple stability check, while bootstrap rank intervals remain future work. High-pressure samples can "
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
