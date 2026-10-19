import numpy as np
import pandas as pd


def load_session(cfg):
    """Read the logger CSV and add local x/y metres (east/north of the mean GPS position)."""
    df = pd.read_csv(cfg["root"] / cfg["paths"]["csv"])
    lat0, lon0 = df["GPS Latitude"].mean(), df["GPS Longitude"].mean()
    df["x"] = (df["GPS Longitude"] - lon0) * 111320 * np.cos(np.radians(lat0))
    df["y"] = (df["GPS Latitude"] - lat0) * 110574
    return df.iloc[3:].reset_index(drop=True)  # first rows have no GPS fix
