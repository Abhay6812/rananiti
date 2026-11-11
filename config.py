from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW_DATA = ROOT / "data" / "raw"
BALLS_FILE = RAW_DATA / "ball_by_ball.csv"
MATCHES_FILE = RAW_DATA / "matches.csv"
TEAMS_FILE = RAW_DATA / "teams.csv"
OUTPUTS = ROOT / "outputs"
MIN_PRESSURE_BALLS = 30
MIN_PRESSURE_MATCHES = 5
PRESSURE_THRESHOLD = 60
