"""Assemble a Power BI project for the RR pressure Top X dashboard."""
import hashlib
import json
import shutil
from pathlib import Path

import pandas as pd

from config import OUTPUTS, ROOT
from src.rankings.rr_topx import build_rr_topx


POWERBI = ROOT / "powerbi"
REPORT = POWERBI / "RR_TopX_Dashboard.Report"
MODEL = POWERBI / "RR_TopX_Dashboard.SemanticModel"
DATA = POWERBI / "data"
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/"


def _write_json(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _name_id(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:20]


def _field(table: str, column: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": column}}


def _projection(table: str, column: str, label: str | None = None) -> dict:
    qref = f"{table}.{column}"
    item = {"field": _field(table, column), "queryRef": qref, "nativeQueryRef": label or column}
    return item


def _visual(page: Path, name: str, visual_type: str, box: tuple[int, int, int, int], projections: list[dict], role: str = "Values", title: str | None = None):
    visual_id = _name_id(name)
    definition = {
        "$schema": SCHEMA + "item/report/definition/visualContainer/2.7.0/schema.json",
        "name": visual_id,
        "position": {"x": box[0], "y": box[1], "z": 1000, "width": box[2], "height": box[3], "tabOrder": 1000},
        "visual": {
            "visualType": visual_type,
            "query": {"queryState": {role: {"projections": projections}}},
            "drillFilterOtherVisuals": True,
        },
    }
    if title:
        definition["visual"]["visualContainerObjects"] = {
            "title": [{"properties": {
                "show": {"expr": {"Literal": {"Value": "true"}}},
                "text": {"expr": {"Literal": {"Value": f"'{title}'"}}},
                "fontColor": {"solid": {"color": {"expr": {"Literal": {"Value": "'#19283D'"}}}}},
                "fontSize": {"expr": {"Literal": {"Value": "15D"}}},
                "fontFamily": {"expr": {"Literal": {"Value": "'Aptos Display'"}}},
                "bold": {"expr": {"Literal": {"Value": "true"}}},
            }}]
        }
    _write_json(page / "visuals" / visual_id / "visual.json", definition)


def _table_tmdl(name: str, csv_path: Path, df: pd.DataFrame) -> str:
    cols = []
    type_map = {"int64": "int64", "float64": "double", "bool": "boolean"}
    for column in df.columns:
        dtype = str(df[column].dtype)
        data_type = type_map.get(dtype, "string")
        safe_col = column if column.isidentifier() else f"'{column.replace(chr(39), chr(39)*2)}'"
        cols.extend([
            f"    column {safe_col}",
            f"        dataType: {data_type}",
            f"        sourceColumn: {column}",
            "        summarizeBy: none",
            "",
        ])
    literal_path = str(csv_path.resolve()).replace('"', '""')
    type_pairs = []
    for column in df.columns:
        dtype = str(df[column].dtype)
        m_type = {"int64": "Int64.Type", "float64": "type number", "bool": "type logical"}.get(dtype, "type text")
        type_pairs.append(f'{{"{column}", {m_type}}}')
    source = "\n".join([
        f"table '{name}'",
        "    partition Source = m",
        "        mode: import",
        "        source =",
        "            let",
        f'                Source = Csv.Document(File.Contents("{literal_path}"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),',
        "                Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),",
        f"                Types = Table.TransformColumnTypes(Headers, {{{', '.join(type_pairs)}}}, \"en-US\")",
        "            in",
        "                Types",
        "",
        *cols,
    ])
    return source


def build_project() -> Path:
    result = build_rr_topx(10)
    POWERBI.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OUTPUTS / "rr_topx_evaluation.json", POWERBI / "RR_TopX_Evaluation.json")
    DATA.mkdir(parents=True, exist_ok=True)

    bat_file = DATA / "RR_Batters.csv"
    bowl_file = DATA / "RR_Bowlers.csv"
    # Keep ten rows per list by default. A numeric rank-range slicer lets the
    # viewer set the upper rank to X without duplicating players.
    result["batters"].head(10).to_csv(bat_file, index=False)
    result["bowlers"].head(10).to_csv(bowl_file, index=False)
    bat = pd.read_csv(bat_file)
    bowl = pd.read_csv(bowl_file)

    definition = MODEL / "definition"
    tables_dir = definition / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    for stale in (tables_dir / "Top X.tmdl", tables_dir / "RR Top X Batters.tmdl",
                  tables_dir / "RR Top X Bowlers.tmdl", definition / "relationships.tmdl",
                  DATA / "Top_X.csv"):
        if stale.exists():
            stale.unlink()
    (MODEL / "definition.pbism").write_text(json.dumps({
        "$schema": SCHEMA + "item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.0", "settings": {"qnaEnabled": False}
    }, indent=2) + "\n", encoding="utf-8")
    (definition / "database.tmdl").write_text("database RR_TopX_Dashboard\n    compatibilityLevel: 1600\n", encoding="utf-8")
    (definition / "model.tmdl").write_text(
        "model Model\n"
        "    culture: en-US\n"
        "    defaultPowerBIDataSourceVersion: powerBI_V3\n"
        "\n"
        "    ref table 'RR Batters'\n"
        "    ref table 'RR Bowlers'\n"
        , encoding="utf-8")
    (tables_dir / "RR Batters.tmdl").write_text(_table_tmdl("RR Batters", bat_file, bat), encoding="utf-8")
    (tables_dir / "RR Bowlers.tmdl").write_text(_table_tmdl("RR Bowlers", bowl_file, bowl), encoding="utf-8")
    report_def = REPORT / "definition"
    pages = report_def / "pages"
    report_def.mkdir(parents=True, exist_ok=True)
    (REPORT / "definition.pbir").write_text(json.dumps({
        "$schema": SCHEMA + "item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byPath": {"path": "../RR_TopX_Dashboard.SemanticModel"}}
    }, indent=2) + "\n", encoding="utf-8")
    _write_json(report_def / "version.json", {"$schema": SCHEMA + "item/report/definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0"})
    _write_json(report_def / "report.json", {
        "$schema": SCHEMA + "item/report/definition/report/3.2.0/schema.json",
        "themeCollection": {}, "filterConfig": {"filters": []}, "objects": {}, "settings": {},
        "resourcePackages": [], "annotations": []
    })

    page_defs = [
        ("Batters", "Pressure Batting", "RR Batters", [
            ("Rank", "rank", "int64"), ("Player", "player", "string"), ("Role", "role", "string"),
            ("Trust score", "trust_score", "double"), ("Risk score", "risk_score", "double"),
            ("Confidence", "confidence", "double"), ("Pressure matches", "pressure_matches", "int64"),
            ("Pressure balls", "pressure_balls", "int64"), ("Pressure strike rate", "pressure_strike_rate", "double"),
            ("Pressure average", "pressure_average", "double"), ("Baseline strike rate", "strike_rate", "double"),
            ("Dot ball %", "pressure_dot_pct", "double"), ("Boundary %", "pressure_boundary_pct", "double"),
        ]),
        ("Bowlers", "Pressure Bowling", "RR Bowlers", [
            ("Rank", "rank", "int64"), ("Player", "player", "string"), ("Phase", "phase", "string"),
            ("Trust score", "trust_score", "double"), ("Risk score", "risk_score", "double"),
            ("Confidence", "confidence", "double"), ("Pressure matches", "pressure_matches", "int64"),
            ("Pressure balls", "pressure_balls", "int64"), ("Pressure overs", "pressure_overs", "double"),
            ("Pressure wickets", "pressure_wickets", "int64"), ("Pressure economy", "pressure_economy", "double"),
            ("Non-pressure baseline economy", "normal_economy", "double"),
            ("Overall economy", "economy", "double"), ("Dot ball %", "pressure_dot_pct", "double"),
            ("Boundary %", "pressure_boundary_pct", "double"),
        ]),
    ]
    page_ids = []
    for key, display, entity, columns in page_defs:
        page_id = _name_id(key)
        page_ids.append(page_id)
        page_dir = pages / page_id
        _write_json(page_dir / "page.json", {
            "$schema": SCHEMA + "item/report/definition/page/2.1.0/schema.json",
            "name": page_id, "displayName": display, "displayOption": "FitToPage", "height": 720, "width": 1280
        })
        _visual(page_dir, f"{key}-TopX-Slicer", "slicer", (35, 25, 220, 90),
                [_projection(entity, "rank", "Top X - maximum rank")], title="Top X - set maximum rank")
        _visual(page_dir, f"{key}-Trust-Chart", "barChart", (35, 135, 475, 505), [
            _projection(entity, "player", "Player"), _projection(entity, "trust_score", "Trust score")
        ], role="Category", title="Trust score by player")
        # Bar charts require separate category and value roles.
        chart_id = _name_id(f"{key}-Trust-Chart")
        chart_path = page_dir / "visuals" / chart_id / "visual.json"
        chart = json.loads(chart_path.read_text(encoding="utf-8"))
        chart["visual"]["query"]["queryState"] = {
            "Category": {"projections": [_projection(entity, "player", "Player")]},
            "Y": {"projections": [_projection(entity, "trust_score", "Trust score")]},
        }
        _write_json(chart_path, chart)
        _visual(page_dir, f"{key}-Evidence-Table", "tableEx", (535, 135, 710, 505),
                [_projection(entity, col, label) for label, col, _ in columns],
                title="Pressure evidence and baseline comparison")
    _write_json(pages / "pages.json", {
        "$schema": SCHEMA + "item/report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": page_ids, "activePageName": page_ids[0]
    })

    _write_json(POWERBI / "RR_TopX_Dashboard.pbip", {
        "$schema": SCHEMA + "pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0", "artifacts": [{"report": {"path": "RR_TopX_Dashboard.Report"}}],
        "settings": {"enableAutoRecovery": True}
    })
    theme = {
        "name": "Rananiti Rajasthan Royals",
        "dataColors": ["#E76F24", "#1A2742", "#4E6E81", "#B9C5D1", "#A33A4A", "#F2A65A"],
        "background": "#F6F8FB", "foreground": "#19283D", "tableAccent": "#E76F24",
        "visualStyles": {"*": {"*": [{"fontFamily": "Aptos", "titleText": [{"fontSize": 15, "fontFace": "Aptos Display", "color": {"solid": {"color": "#19283D"}}}]}]}}
    }
    _write_json(POWERBI / "Rananiti_Royals_Theme.json", theme)
    readme = f"""# Rajasthan Royals Top X Power BI project

Open `RR_TopX_Dashboard.pbip` in Power BI Desktop. If prompted, refresh the model to import the two ranking CSV files under `data/`.

The report has dedicated pressure-batting and pressure-bowling pages. Each page defaults to the Top 10. Use the **Top X - maximum rank** numeric range slicer and keep the minimum rank at 1; set the maximum rank to the desired X. For example, set ranks 1 to 5 to show the Top 5. Player history is restricted to Rajasthan Royals IPL deliveries from seasons 2022-2026. Batter candidates must have a median batting position of 7 or better and at least 60 RR balls faced; this keeps tail-end bowling profiles out of the batter list. The pressure rating uses the match-context scoring pipeline; role and phase remain visible in the evidence tables.

## Source files

- `data/RR_Batters.csv` and `data/RR_Bowlers.csv`: role/phase-aware Rajasthan Royals player rankings.
- `RR_TopX_Evaluation.json`: source match counts and selected pressure exposure thresholds.
- `Rananiti_Royals_Theme.json`: optional theme import in Power BI Desktop (View > Themes > Browse for themes).

The project was assembled as PBIP/PBIR source files because Power BI Desktop and Power BI Service are not available in this environment. Open it locally in Desktop and save as a `.pbix` if you need a packaged report. Publishing to a workspace and granting service access requires your Power BI account and target workspace.

Selection thresholds used to ensure up to ten candidates are available: batters {result['evaluation']['batter_eligibility']['minimum_pressure_balls']} pressure balls across {result['evaluation']['batter_eligibility']['minimum_pressure_matches']} matches; bowlers {result['evaluation']['bowler_eligibility']['minimum_pressure_balls']} pressure balls across {result['evaluation']['bowler_eligibility']['minimum_pressure_matches']} matches.
"""
    (POWERBI / "README.md").write_text(readme, encoding="utf-8")
    return POWERBI / "RR_TopX_Dashboard.pbip"


if __name__ == "__main__":
    print(str(build_project()).encode("ascii", "backslashreplace").decode("ascii"))
