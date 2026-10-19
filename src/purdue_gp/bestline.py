"""Best demonstrated line: the three fastest push laps through each stretch of track,
at the best speed any push lap reached there. Not a theoretical optimum."""
import numpy as np


def smooth(a, w):
    """Circular moving average (the lap is a closed loop)."""
    return np.convolve(np.r_[a[-w:], a, a[:w]], np.ones(w) / w, "same")[w:-w]


def tangents(p):
    t = np.gradient(p, axis=0)
    return t / (np.hypot(t[:, 0], t[:, 1])[:, None] + 1e-9)


def build_best_line(df, laps, cfg):
    N = cfg["bins"]
    x, y, spd = df.x.values, df.y.values, df["GPS Speed"].values
    racing = racing_laps_of(laps)
    best = min(racing, key=lambda l: l["time_s"])
    ref = np.c_[x[best["i0"]:best["i1"] + 1], y[best["i0"]:best["i1"] + 1]]
    ref_s = np.r_[0, np.cumsum(np.hypot(*np.diff(ref, axis=0).T))]
    bins = np.linspace(0, ref_s[-1], N, endpoint=False)
    data = {}
    for l in racing:  # project every lap onto the best lap's path, resample by distance
        pts = np.c_[x[l["i0"]:l["i1"] + 1], y[l["i0"]:l["i1"] + 1]]
        v = spd[l["i0"]:l["i1"] + 1]
        j = int(np.argmin(np.hypot(*(ref[:40] - pts[0]).T))); idx = []
        for p in pts:
            hi = min(j + 25, len(ref) - 1)
            j += int(np.argmin(np.hypot(*(ref[j:hi + 1] - p).T))); idx.append(j)
        s = np.maximum.accumulate(ref_s[idx]); u, ui = np.unique(s, return_index=True)
        f = lambda a: np.interp(bins, u, a[ui])
        data[l["n"]] = dict(x=f(pts[:, 0]), y=f(pts[:, 1]), v=f(v))
    push = [l["n"] for l in racing if l["type"] == "push"]
    vs = np.array([smooth(data[n]["v"], 5) for n in push])
    xs = np.array([data[n]["x"] for n in push]); ys = np.array([data[n]["y"] for n in push])
    vopt = vs.max(0); k = cfg["best_line_top_laps"]; top = np.argsort(-vs, axis=0)[:k]
    line = np.c_[smooth(np.array([xs[top[:, i], i].mean() for i in range(N)]), 5),
                 smooth(np.array([ys[top[:, i], i].mean() for i in range(N)]), 5)]
    ds = np.hypot(*np.diff(np.r_[line, line[:1]], axis=0).T)
    t = tangents(line); normal = np.c_[-t[:, 1], t[:, 0]]
    for d in data.values():  # per-lap offset (m, left +), speed delta, cumulative time lost
        d["o"] = ((np.c_[d["x"], d["y"]] - line) * normal).sum(1)
        d["dv"] = d["v"] - vopt
        d["ct"] = np.cumsum(ds * (1 / np.maximum(d["v"], 1) - 1 / vopt))
    return dict(best=best, push=push, data=data, line=line, vopt=vopt, ds=ds, length=float(ds.sum()),
                theoretical_s=float((ds / vopt).sum()), N=N)


def racing_laps_of(laps):
    return [l for l in laps if l["type"] in ("push", "caution")]
