# SupeRR Selector Season 2 — Methodology and Rankings

## Dataset

Analysed 194,014 deliveries across 837 IPL and T20I matches (2022-01-22 to 2026-11-01). The pressure engine marked 14,918 deliveries as high pressure.

## Pressure definition

Match state is reconstructed before each delivery to avoid leakage. First-innings pressure combines wickets lost, scoring below the observed phase-specific first-innings run rate, and innings progress. Chase pressure combines required run rate relative to the observed first-innings rate, wickets lost, and balls elapsed. The indicators are combined into a 0–100 pressure index; index 60 or higher is classified as high pressure. Matches with revised targets or overs use those match metadata where supplied.

## Rating and fair comparisons

Batter pressure performance combines pressure strike rate, pressure average, dot-ball avoidance, boundary scoring, dismissal avoidance, retention of the player's non-pressure strike rate, and match-to-match consistency. Percentiles are computed within historical batting role. Bowler performance combines pressure economy, dot-ball control, wickets per pressure over, boundary prevention, retention against normal economy, and match-to-match consistency; bowlers are compared within powerplay, middle, or death phase. Trust ratings are confidence-adjusted toward 50 for low exposure. Risk is calculated separately from performance deterioration, dismissals or boundaries, and volatility.

Final Trust is the arithmetic mean of the confidence-adjusted Trust at pressure-index cutoffs 50, 60, and 70; a player without a qualifying profile at one cutoff receives neutral Trust (50) for that cutoff. Eligibility and the reported exposure metrics are anchored to cutoff 60.

Eligibility is fixed at at least 60 pressure balls across 5 pressure matches. Thresholds do not relax; if fewer than ten distinct players qualify, the output is shorter than ten. Each bowler appears once, using the highest Trust phase only among phase profiles that independently pass the fixed exposure threshold.

For batters, the baseline strike rate is non-pressure batter runs per non-pressure balls faced. For bowlers, the baseline economy is team runs conceded per non-pressure legal over; this is distinct from overall economy. These are player-specific observed baselines and are not shrunk to a role mean. Confidence adjustment shrinks Trust toward 50 as pressure exposure falls. IPL and T20I are pooled from 2022 onward, with within-role or within-phase normalization, but there is no explicit opposition-strength or competition-format adjustment. Results are therefore not opposition-adjusted and should not be read as a neutralized IPL-versus-T20I comparison.

Bowling phase is assigned from legal balls completed before the delivery: balls 0–35 are Powerplay, 36–89 Middle, and ball 90 onward Death. A bowler's listed phase is the highest-Trust profile that meets the same exposure rules; the label describes the ranked pressure sample, not the bowler's usual deployment. For example, Sunil Narine's audited Death pressure sample was 42 balls, below the 60-ball requirement, so it cannot qualify for the final list.

## Top 10 batters

| Rank | Player | Role | Mean Trust | Risk | Confidence | Pressure balls | Pressure SR | Non-pressure SR | 90% bootstrap rank | Eligible in resamples |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | Rinku Singh | Finisher | 68.0 | 34.3 | 68.8 | 147 | 208.8 | 145.4 | 1–19 | 94.0% |
| 2 | Tristan Stubbs | Middle Order | 67.8 | 39.7 | 72.2 | 170 | 194.1 | 141.7 | 1–26 | 98.0% |
| 3 | Ravindra Jadeja | Finisher | 66.9 | 24.3 | 72.0 | 143 | 166.4 | 129.6 | 1–17 | 98.0% |
| 4 | Mahendra Singh Dhoni | Finisher | 66.0 | 38.9 | 73.7 | 158 | 180.4 | 133.8 | 1–32 | 98.0% |
| 5 | Akeal Hosein | Lower Order | 64.8 | 42.1 | 69.4 | 96 | 166.7 | 99.2 | 1–31 | 90.0% |
| 6 | Rashid Khan | Lower Order | 64.5 | 48.5 | 78.5 | 186 | 175.8 | 144.5 | 2–32 | 99.0% |
| 7 | Naman Dhir | Finisher | 64.4 | 33.7 | 54.4 | 71 | 223.9 | 163.7 | 1–18 | 55.0% |
| 8 | Marco Jansen | Lower Order | 63.9 | 46.4 | 65.9 | 86 | 187.2 | 101.6 | 2–36 | 82.0% |
| 9 | Sikandar Raza | Middle Order | 63.7 | 25.7 | 50.4 | 62 | 212.9 | 130.4 | 1–17 | 46.0% |
| 10 | David Miller | Middle Order | 63.7 | 47.2 | 77.0 | 166 | 204.8 | 141.0 | 2–57 | 99.0% |

## Top 10 bowlers

| Rank | Player | Best phase | Mean Trust | Risk | Confidence | Pressure balls | Pressure economy | Non-pressure economy | 90% bootstrap rank | Eligible in resamples |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | Jasprit Bumrah | Death | 61.0 | 44.4 | 72.7 | 121 | 5.80 | 7.86 | 1–35 | 98.0% |
| 2 | Mohit Sharma | Death | 59.5 | 32.7 | 63.0 | 82 | 7.61 | 11.51 | 2–22 | 79.0% |
| 3 | Maheesh Theekshana | Death | 59.5 | 40.9 | 70.2 | 99 | 6.79 | 8.71 | 2–22 | 98.0% |
| 4 | Matheesha Pathirana | Death | 57.9 | 44.5 | 76.3 | 174 | 8.48 | 9.20 | 4–24 | 100.0% |
| 5 | Tim Southee | Death | 57.6 | 34.8 | 69.7 | 110 | 7.20 | 10.04 | 3–29 | 94.0% |
| 6 | Varun Chakravarthy | Death | 56.9 | 42.5 | 72.6 | 113 | 6.58 | 9.59 | 2–40 | 100.0% |
| 7 | Kyle Jamieson | Death | 56.5 | 38.6 | 54.4 | 62 | 7.45 | 11.63 | 2–41 | 58.0% |
| 8 | Yuzvendra Chahal | Death | 55.8 | 49.6 | 68.2 | 94 | 7.91 | 10.45 | 5–34 | 99.0% |
| 9 | Mustafizur Rahman | Death | 54.4 | 57.2 | 77.4 | 154 | 7.44 | 9.32 | 3–44 | 100.0% |
| 10 | Rashid Khan | Death | 54.1 | 45.3 | 75.9 | 138 | 7.26 | 8.66 | 4–41 | 100.0% |

## Pressure evidence and sensitivity

Pressure index quantiles and delivery shares, plus observed run rate and wicket rate for pressure and ordinary balls, are reported in `ranking_evaluation.json`. In this feed, pressure deliveries had run rate 8.53 vs 8.39 per six legal balls, and 9.64 vs 5.28 wickets per 100 legal balls. Pressure's observed run-rate gap is modest, while its wicket-rate gap is larger; batting performance still explicitly includes pressure strike rate and retention against the player's non-pressure rate. These aggregates are descriptive, not causal. Cutoff overlaps compare each single-cutoff Top 10 with the final three-cutoff mean ranking. The match-level bootstrap resamples whole matches with replacement (100 replicates) and reports the 5th–95th percentile rank among draws where the player remains eligible; adjacent eligibility percentages show how often they qualified. It measures sampling sensitivity, not future performance. There is no ball-level win-probability feed, so win-probability swing is not estimated.

| Cutoff | Pressure deliveries | Batter overlap with final Top 10 | Bowler overlap with final Top 10 |
|---:|---:|---:|---:|
| 50 | 24,326 | 3/10 | 2/10 |
| 60 | 14,918 | 8/10 | 8/10 |
| 70 | 10,203 | 9/10 | 5/10 |

The final ranking averages all three cutoffs to reduce dependence on any single threshold; cutoff overlap remains a useful stability diagnostic, not proof of robustness.

| Match half | Matches | Batter overlap with full Top 10 | Bowler overlap with full Top 10 |
|---|---:|---:|---:|
| Odd | 419 | 5/10 | 4/10 |
| Even | 418 | 4/10 | 5/10 |

The alternating match split is another descriptive stability check. Bootstrap bands and alternating splits do not eliminate sampling bias or contextual differences.

## Secondary RR dashboard exclusions

The RR-only squad view is separate from the overall submission lists. Across its current 2022–2026 batting candidate pool, 52 players were considered; 25 inferred lower-order profiles and 13 other players below 60 RR IPL balls were excluded, leaving 14 batter candidates. These screens apply only to that secondary RR view.

## Reliability checks and limitations

Eligibility counts, fixed thresholds, match counts, confidence, cutoff sensitivity, bootstrap intervals, and the full metric set are saved in `outputs/`. Rankings use observed IPL/T20I history from 2022 onward and avoid relying on reputation. Confidence and exposure describe sample quantity; bootstrap rank intervals are conditional on remaining eligible in each resample. High-pressure samples can still be small or uneven across contexts. Bowling runs include an estimated minimum penalty for wides and Oversteps because the supplied extras fields are incomplete; review bowling economy with that limitation in mind.
