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
    thresholds = [(MIN_PRESSURE_BALLS, MIN_PRESSURE_MATCHES), (12, 3), (12, 1), (1, 1)]
    selected = data.iloc[0:0].copy()
    used = None
    for min_balls, min_matches in thresholds:
        pool = data[data[exposure_col].ge(min_balls) & data["pressure_matches"].ge(min_matches)]
        pool = pool.sort_values([score, "risk_score", "confidence", exposure_col],
                                ascending=ascending, na_position="last")
        pool = pool.drop_duplicates(distinct_id).head(10)
        if len(pool) >= min(10, data[distinct_id].nunique()):
            selected, used = pool, (min_balls, min_matches)
            break
        if len(pool) > len(selected):
            selected, used = pool, (min_balls, min_matches)
    selected = selected.reset_index(drop=True)
    selected.insert(0, "rank", range(1, len(selected) + 1))
    return selected, {"minimum_pressure_balls": used[0], "minimum_pressure_matches": used[1],
                      "eligible_unique_players": int(data.loc[data[exposure_col].ge(used[0]) & data["pressure_matches"].ge(used[1]), distinct_id].nunique()),
                      "candidate_unique_players": int(data[distinct_id].nunique())}


def build_rankings() -> dict:
    balls, matches, competitions = load_submission_data()
    state = detect_pressure(reconstruct_match_state(balls, matches))
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
    evaluation = {
        "dataset": {"deliveries": int(len(state)), "matches": int(state["match_id"].nunique()),
                    "competitions": int(matches["comp_id"].nunique()),
                    "date_start": str(matches["match_date"].min().date()),
                    "date_end": str(matches["match_date"].max().date()),
                    "high_pressure_deliveries": int(state["is_pressure"].sum()),
                    "formats": sorted(competitions["format_clean"].dropna().unique().tolist())},
        "pressure_definition": "Pre-delivery context index; high pressure is index >= 60.",
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
          "Eligibility initially requires at least "
          f"{MIN_PRESSURE_BALLS} pressure balls across {MIN_PRESSURE_MATCHES} pressure matches. If fewer than ten distinct "
          "players qualify, the threshold is relaxed in documented steps; each final ranking CSV and `ranking_evaluation.json` "
          "Top 10 bowlers are distinct players, ranked by their strongest phase-qualified profile.", "",
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
    md += ["", "## Reliability checks and limitations", "",
           "Eligibility counts, fallback thresholds, match counts, confidence, and the full metric set are saved in `outputs/`. "
           "Rankings use observed IPL/T20I history from 2022 onward and avoid relying on reputation. High-pressure samples can "
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
