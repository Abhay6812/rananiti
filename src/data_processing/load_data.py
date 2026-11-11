from pathlib import Path
import pandas as pd


def load_csv(path: str | Path, required_columns=()) -> pd.DataFrame:
    path=Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")
    frame=pd.read_csv(path,low_memory=False)
    missing=set(required_columns)-set(frame.columns)
    if missing:
        raise ValueError(f"{path.name} is missing columns: {', '.join(sorted(missing))}")
    return frame
