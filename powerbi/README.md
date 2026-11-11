# Rajasthan Royals Top X Power BI project

Open `RR_TopX_Dashboard.pbip` in Power BI Desktop. If prompted, refresh the model to import the two ranking CSV files under `data/`.

The report has dedicated pressure-batting and pressure-bowling pages. Each page defaults to the Top 10. Use the **Top X - maximum rank** numeric range slicer and keep the minimum rank at 1; set the maximum rank to the desired X. For example, set ranks 1 to 5 to show the Top 5. Player history is restricted to Rajasthan Royals IPL deliveries from seasons 2022-2026. Batter candidates must have a median batting position of 7 or better and at least 60 RR balls faced; this keeps tail-end bowling profiles out of the batter list. The pressure rating uses the match-context scoring pipeline; role and phase remain visible in the evidence tables.

## Source files

- `data/RR_Batters.csv` and `data/RR_Bowlers.csv`: role/phase-aware Rajasthan Royals player rankings.
- `RR_TopX_Evaluation.json`: source match counts and selected pressure exposure thresholds.
- `Rananiti_Royals_Theme.json`: optional theme import in Power BI Desktop (View > Themes > Browse for themes).

The project was assembled as PBIP/PBIR source files because Power BI Desktop and Power BI Service are not available in this environment. Open it locally in Desktop and save as a `.pbix` if you need a packaged report. Publishing to a workspace and granting service access requires your Power BI account and target workspace.

Selection thresholds used to ensure up to ten candidates are available: batters 1 pressure balls across 1 matches; bowlers 12 pressure balls across 3 matches.
