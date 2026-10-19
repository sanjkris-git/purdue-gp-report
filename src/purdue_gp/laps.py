import numpy as np
from .config import MPS_TO_MPH


def gate_vectors(gate):
    p = np.array(gate["point"]); t = np.array(gate["direction"]); n = np.array([-t[1], t[0]])
    return p, t, n


def find_crossings(df, gate):
    """Indices, interpolated times and lateral offsets where the logger crosses the S/F line."""
    p, t, n = gate_vectors(gate)
    lo, hi = gate["lateral_window_m"]
    x, y, tm = df.x.values, df.y.values, df.time_s.values
    s = (x - p[0]) * t[0] + (y - p[1]) * t[1]
    lat = (x - p[0]) * n[0] + (y - p[1]) * n[1]
    idx = [i for i in range(1, len(df)) if s[i - 1] < 0 <= s[i] and lo <= lat[i] <= hi]
    times = [tm[i - 1] + (tm[i] - tm[i - 1]) * (-s[i - 1]) / (s[i] - s[i - 1]) for i in idx]
    return np.array(idx), np.array(times), lat[idx]


def build_laps(df, idx, times, lat, cfg):
    """One dict per timed lap. A crossing in the pit lane (lateral offset < threshold)
    makes that lap an out-lap (starts there) or in-lap (ends there)."""
    pit = cfg["gate"]["pit_lane_lateral_m"]
    laps = []
    for k in range(len(idx) - 1):
        seg = df.iloc[idx[k]:idx[k + 1]]
        time = float(times[k + 1] - times[k])
        if lat[k] < pit: kind = "out-lap"
        elif lat[k + 1] < pit: kind = "in-lap"
        else: kind = "caution" if time >= cfg["caution_min_lap_s"] else "push"
        laps.append(dict(
            n=k + 1, type=kind, start_s=float(times[k]), time_s=time, i0=int(idx[k]), i1=int(idx[k + 1]),
            top_mph=float(seg["GPS Speed"].max() * MPS_TO_MPH), avg_mph=float(seg["GPS Speed"].mean() * MPS_TO_MPH),
            avg_rpm=int(seg.RPM.mean()), egt_avg=int(seg["Exhaust Temp"].mean()), egt_max=int(seg["Exhaust Temp"].max()),
            lat_g=float(seg.GPS_LateralAcc.abs().quantile(0.99))))
    return laps


def racing_laps(laps):
    return [l for l in laps if l["type"] in ("push", "caution")]
