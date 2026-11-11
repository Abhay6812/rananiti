import pandas as pd


def clean_ball_data(frame: pd.DataFrame) -> pd.DataFrame:
    df=frame.copy()
    df=df.dropna(subset=["match_id","innings","overid","striker_id","bowler_id"])
    for col in ("innings","overid","over_ball_num","runs"):
        if col in df: df[col]=pd.to_numeric(df[col],errors="coerce")
    return df
