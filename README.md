# Rananiti | RR Pressure Intelligence

Rananiti uses ball-by-ball cricket data to identify batters and bowlers with evidence of performing well in high-pressure situations. It produces role-aware Trust and Risk ratings, confidence and sample-size context, a Rajasthan Royals (RR) Top X dashboard, and a Power BI report source project.

The project has two ranking workflows. The submission workflow ranks eligible players across IPL and T20I competitions. The RR workflow restricts the analysis to Rajasthan Royals IPL matches from 2022 onward and supplies the Streamlit and Power BI dashboards. Their generated ranking files are separate.

## Quick start: Streamlit dashboard

Run these commands in PowerShell from the project root:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run dashboard/app.py
```

Streamlit serves the app at `http://localhost:8501`. The dashboard shows RR batting and bowling rankings, supports a Top X selection, compares pressure performance with a player's usual baseline, and provides evidence tables and CSV downloads. The **Method & data** tab shows the scoring approach, coverage and applied sample thresholds.

The app reads its source files from `data/raw/` and builds the RR insights through `src/rankings/rr_dashboard_insights.py` and `src/rankings/rr_topx.py`. If inputs change, the app cache refreshes when the source file modification times change.

## Project workflow

```text
data/raw/*.csv
  |-- notebooks: inspect and review data
  |-- src/data_processing: load, clean and join
  |-- src/pressure_engine: reconstruct match context and label pressure
  |-- src/feature_engineering and src/role_engine: summarize by role/phase
  |-- src/scoring: calculate Trust, Risk and confidence
  |-- src/rankings: write rankings and evaluation evidence
       |-- outputs/ and reports/
       |-- dashboard/app.py (Streamlit RR dashboard)
       |-- powerbi/ (Power BI RR Top X project and CSV sources)
```

### 1. Source data

Place the provided CSV files in `data/raw/`:

- `ball_by_ball.csv` - delivery-level batting, bowling and extras records.
- `matches.csv` - match dates, competition links, innings and match context.
- `competitions.csv` - competition names, seasons and formats.
- `competition_team_player_mapping.csv` - team/player identities by competition.
- `playing_eleven.csv` and `teams.csv` - participation and team lookup data used by data review or related analyses.

`config.py` defines the raw-data and output locations, plus default pressure eligibility settings. Keep source CSVs unchanged; cleaning and feature preparation happen in Python dataframes.

### 2. Jupyter notebooks

Start Jupyter from the project root so notebook imports and relative paths resolve:

```powershell
python -m pip install jupyter
jupyter notebook
```

Run notebooks in numeric order:

1. `notebooks/01_data_exploration.ipynb` - inspect source coverage, columns and distributions.
2. `notebooks/02_data_cleaning.ipynb` - review field quality, duplicates, and feed-specific encodings.
3. `notebooks/03_match_state_reconstruction.ipynb` - inspect pre-delivery match-state calculations.
4. `notebooks/04_pressure_detection.ipynb` - apply and inspect pressure labels.
5. `notebooks/05_batter_analysis.ipynb` and `06_bowler_analysis.ipynb` - generate and review the overall submission rankings.
6. `notebooks/07_trust_risk_scoring.ipynb` - review ranking reliability and eligibility checks.
7. `notebooks/08_submission_report.ipynb` - generate and display the methodology and evidence report.

The notebooks call shared code under `src/`; they are an analysis and review interface rather than separate implementations of the ranking logic.

### 3. Ranking and scoring logic

The main pipeline is organized by responsibility:

- `src/data_processing/` loads, validates, cleans and joins source tables.
- `src/pressure_engine/` reconstructs match state before a delivery and identifies high-pressure contexts. The current high-pressure cutoff is a pressure index of 60.
- `src/feature_engineering/` summarizes batting and bowling performance under pressure and at baseline.
- `src/role_engine/` assigns batter roles and bowler phases for fairer comparisons.
- `src/scoring/` calculates performance Trust and independent Risk indicators, with confidence adjusting for sample size.
- `src/rankings/` assembles rankings, RR-specific dashboard data and Power BI source files.

Trust indicates pressure performance adjusted for comparison group and sample confidence. Risk is a separate caution signal; review it alongside Trust, confidence, pressure balls and pressure matches. These are historical decision-support ratings, not predictions of future performance.

### 4. Regenerate overall IPL/T20I submission outputs

From the project root:

```powershell
python -m src.rankings.rank_players
```

This uses eligible IPL and T20I matches from 2022 onward and writes the overall lists and evaluation files, including:

- `outputs/batter_rankings.csv`
- `outputs/bowler_rankings.csv`
- `outputs/ranking_evaluation.json`
- `reports/submission_methodology_report.md`

The corresponding notebooks 05?08 call this same pipeline.

### 5. Generate RR-only Top X data and Power BI project

To regenerate RR rankings and their evaluation outputs:

```powershell
python -m src.rankings.rr_topx
```

This writes RR-specific ranking files under `outputs/`, including `rr_batter_rankings.csv`, `rr_bowler_rankings.csv`, expanded Top X CSVs and `rr_topx_evaluation.json`.

To also refresh the Power BI data and project definitions:

```powershell
python -m src.rankings.build_rr_powerbi
```

Open `powerbi/RR_TopX_Dashboard.pbip` in Power BI Desktop. The source CSVs are `powerbi/data/RR_Batters.csv` and `powerbi/data/RR_Bowlers.csv`. See [`powerbi/README.md`](powerbi/README.md) for report controls and refresh details. The Power BI project is a local source project; publishing it to Power BI Service requires a signed-in account and a destination workspace.

### Important RR selection rules

- RR data is restricted to IPL seasons 2022 onward.
- Batter candidates exclude inferred lower-order profiles and need at least 60 RR IPL balls faced.
- Bowlers are compared by powerplay, middle or death phase; the dashboard lists each player once using their strongest qualifying phase profile.
- The pressure ball/match eligibility threshold can relax in steps when the available RR pool is too small for ten names. The dashboard and `outputs/rr_topx_evaluation.json` show the threshold used. Check exposure and confidence before treating a rank as reliable.

### Repository map

```text
config.py                       Shared paths and default thresholds
data/raw/                      Original match and delivery CSVs
notebooks/                      Ordered exploration and analysis notebooks
src/data_processing/            Data loading, cleaning and merging
src/pressure_engine/             Match state and pressure context
src/feature_engineering/         Batter and bowler summaries
src/role_engine/                 Batter roles and bowling phases
src/scoring/                     Trust, Risk and consistency scoring
src/rankings/                    Overall, RR and Power BI workflows
dashboard/app.py                 Streamlit user interface
data/                            Raw source data
outputs/                         Generated rankings and evaluations
reports/                         Methodology and findings
powerbi/                         PBIP report, model source and dashboard CSVs
models/                          Model-artifact location (if used by a separate analysis)
```

### Current scope and limitations

The running Top X product is built from the pressure, role/phase, Trust and Risk pipeline described above. The notebooks currently present in `notebooks/` do not train or load a clustering model, and clustering artifacts are not part of the Streamlit or Power BI ranking workflow. The `models/` folder is reserved for separate model artifacts.

The pressure ranking depends on the coverage and quality of the supplied historical data. RR samples may be small, so confidence and exposure should be considered with every score. Supplied extras fields are incomplete for some bowling penalties; bowling run totals estimate minimum wide/Overstep penalties. Validate candidates with cricket staff and match context before making squad decisions.
