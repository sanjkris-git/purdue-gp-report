import numpy as np
from .bestline import smooth
from .config import MPS_TO_MPH


def find_zones(bl, cfg):
    """Biggest time-loss zones: where the average push lap loses most time to the best line."""
    N, data, push = bl["N"], bl["data"], bl["push"]
    loss_rate = np.mean([np.diff(data[n]["ct"], prepend=0) for n in push], 0)
    smooth_rate = smooth(loss_rate, 15); work = smooth_rate.copy()
    line = bl["line"]; cx, cy = line.mean(0); hw = cfg["zone_half_width_bins"]
    heading = np.unwrap(np.arctan2(*np.gradient(line, axis=0)[:, ::-1].T))
    zones = []
    for _ in range(cfg["n_zones"]):
        b0 = int(np.argmax(work)); idx = np.arange(b0 - hw, b0 + hw + 1) % N
        lost = np.mean([data[n]["ct"][idx[-1]] - data[n]["ct"][idx[0]] if idx[-1] > idx[0] else 0 for n in push])
        dv = np.mean([data[n]["dv"][idx].mean() for n in push]) * MPS_TO_MPH
        turn = abs(np.degrees(heading[idx[-1]] - heading[idx[0]])); x, y = line[b0]
        ns = "north" if y > cy + 15 else "south" if y < cy - 15 else ""
        ew = "east" if x > cx + 15 else "west" if x < cx - 15 else ""
        zones.append(dict(b0=int(idx[0]), b1=int(idx[-1]), x=round(float(x), 1), y=round(float(y), 1),
                          lost_s=float(lost), speed_down_mph=float(-dv), distance_m=int(idx[0] / N * bl["length"]),
                          turn_deg=float(turn), position="-".join(q for q in (ns, ew) if q) or "centre",
                          kind="corner" if turn > 45 else "straight / kink"))
        for j in range(b0 - 30, b0 + 31): work[j % N] = -9  # keep zones apart
    return zones, loss_rate, smooth_rate
