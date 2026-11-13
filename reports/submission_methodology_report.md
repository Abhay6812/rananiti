# SupeRR Selector Season 2 — Methodology and Rankings

## Dataset

Analysed 194,014 deliveries across 837 IPL and T20I matches (2022-01-22 to 2026-11-01). The pressure engine marked 14,918 deliveries as high pressure.

## Pressure definition

Match state is reconstructed before each delivery to avoid leakage. First-innings pressure combines wickets lost, scoring below the observed phase-specific first-innings run rate, and innings progress. Chase pressure combines required run rate relative to the observed first-innings rate, wickets lost, and balls elapsed. The indicators are combined into a 0–100 pressure index; index 60 or higher is classified as high pressure. Matches with revised targets or overs use those match metadata where supplied.

## Rating and fair comparisons

Batter pressure performance combines pressure strike rate, pressure average, dot-ball avoidance, boundary scoring, dismissal avoidance, retention of the player's normal strike rate, and match-to-match consistency. Percentiles are computed within historical batting role. Bowler performance combines pressure economy, dot-ball control, wickets per pressure over, boundary prevention, retention against normal economy, and match-to-match consistency; bowlers are compared within powerplay, middle, or death phase. Trust ratings are confidence-adjusted toward 50 for low exposure. Risk is calculated separately from performance deterioration, dismissals or boundaries, and volatility.

Eligibility is fixed at at least 30 pressure balls across 5 pressure matches. Thresholds do not relax; if fewer than ten distinct players qualify, the output is shorter than ten. Each bowler appears once, using the highest Trust phase only among phase profiles that independently pass the fixed exposure threshold.

The batting baseline is the player's aggregate batting rate across the eligible sample; bowler retention compares pressure economy with the non-pressure economy. Baselines are not shrunk to a role mean. Confidence adjustment shrinks the final Trust score toward 50 as pressure exposure falls. Players from IPL and T20I are pooled in the eligible dataset and compared within role or phase; there is no explicit opposition-strength or competition-format adjustment, so this remains a limitation.

## Top 10 batters

| Rank | Player | Role | Trust | Risk | Pressure balls | Pressure SR | Pressure average | Dot % |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 1 | Rinku Singh | Finisher | 69.9 | 32.6 | 147 | 208.8 | 102.3 | 29.3 |
| 2 | Ravindra Jadeja | Finisher | 68.8 | 23.3 | 143 | 166.4 | 39.7 | 23.1 |
| 3 | Rashid Khan | Lower Order | 66.9 | 44.4 | 186 | 175.8 | 23.4 | 40.9 |
| 4 | Sikandar Raza | Middle Order | 66.3 | 25.4 | 62 | 212.9 | 66.0 | 29.0 |
| 5 | Naman Dhir | Finisher | 65.9 | 32.6 | 71 | 223.9 | 53.0 | 19.7 |
| 6 | Mahendra Singh Dhoni | Finisher | 65.4 | 39.6 | 158 | 180.4 | 35.6 | 31.6 |
| 7 | Namboori Tilak Varma | Middle Order | 65.0 | 38.2 | 147 | 198.6 | 32.4 | 27.2 |
| 8 | Akeal Hosein | Lower Order | 65.0 | 41.4 | 96 | 166.7 | 16.0 | 38.5 |
| 9 | Tristan Stubbs | Middle Order | 64.9 | 40.2 | 170 | 194.1 | 47.1 | 24.1 |
| 10 | Shashank Singh | Finisher | 64.1 | 35.5 | 127 | 169.3 | 43.0 | 27.6 |

## Top 10 bowlers

| Rank | Player | Best phase | Trust | Risk | Pressure balls | Pressure overs | Pressure economy | Wickets | Dot % |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Kuldeep Yadav | Death | 69.9 | 18.4 | 59 | 9.8 | 5.1 | 11 | 55.9 |
| 2 | Mohammad Nawaz | Middle | 63.7 | 22.9 | 37 | 6.2 | 4.1 | 6 | 56.8 |
| 3 | Abrar Ahmed | Middle | 63.1 | 32.9 | 48 | 8.0 | 3.9 | 2 | 52.1 |
| 4 | Corbin Bosch | Death | 62.1 | 27.9 | 33 | 5.5 | 5.8 | 4 | 69.7 |
| 5 | Shadab Khan | Middle | 62.1 | 28.2 | 46 | 7.7 | 5.1 | 5 | 45.7 |
| 6 | Gerald Coetzee | Death | 61.9 | 23.3 | 36 | 6.0 | 6.5 | 7 | 44.4 |
| 7 | Mitchell Santner | Middle | 61.7 | 29.4 | 59 | 9.8 | 5.3 | 4 | 44.1 |
| 8 | Jasprit Bumrah | Death | 61.7 | 44.4 | 121 | 20.2 | 5.8 | 14 | 50.4 |
| 9 | Mohammad Wasim | Death | 61.4 | 33.4 | 41 | 6.8 | 5.6 | 3 | 61.0 |
| 10 | Sunil Narine | Death | 60.6 | 31.8 | 42 | 7.0 | 4.7 | 4 | 40.5 |

## Pressure evidence and sensitivity

Pressure index quantiles and delivery shares, plus observed run rate and wicket rate for pressure and ordinary balls, are reported in `ranking_evaluation.json`. In this feed, pressure deliveries had run rate 8.53 vs 8.39 per six legal balls, and 9.64 vs 5.28 wickets per 100 legal balls. Top-10 overlap is recalculated at cutoffs 50, 60 and 70. These are descriptive sensitivity checks. Alternating date-ordered match halves are compared with the full-data Top 10 in `ranking_evaluation.json`; a bootstrap rank interval is not yet implemented. There is no ball-level win-probability feed, so win-probability swing is not estimated.

| Cutoff | Pressure deliveries | Batter overlap with 60 | Bowler overlap with 60 |
|---:|---:|---:|---:|
| 50 | 24,326 | 4/10 | 5/10 |
| 60 | 14,918 | 10/10 | 10/10 |
| 70 | 10,203 | 7/10 | 3/10 |

Top-10 sensitivity is limited across the tested cutoffs. Treat the index cutoff as a material modeling choice, not a validated optimum.

| Match half | Matches | Batter overlap with full Top 10 | Bowler overlap with full Top 10 |
|---|---:|---:|---:|
| Odd | 419 | 4/10 | 3/10 |
| Even | 418 | 4/10 | 0/10 |

The alternating match split shows rank instability, especially for bowlers; low overlap indicates these lists need validation before strong selection decisions.

## Secondary RR dashboard exclusions

The RR-only squad view is separate from the overall submission lists. Across its current 2022–2026 batting candidate pool, 52 players were considered; 25 inferred lower-order profiles and 13 other players below 60 RR IPL balls were excluded, leaving 14 batter candidates. These screens apply only to that secondary RR view.

## Reliability checks and limitations

Eligibility counts, fixed thresholds, match counts, confidence, alternating-split overlap, and the full metric set are saved in `outputs/`. Rankings use observed IPL/T20I history from 2022 onward and avoid relying on reputation. Confidence and exposure describe sample quantity; the alternating split is a simple stability check, while bootstrap rank intervals remain future work. High-pressure samples can still be small or uneven across contexts. Bowling runs include an estimated minimum penalty for wides and Oversteps because the supplied extras fields are incomplete; review bowling economy with that limitation in mind.
