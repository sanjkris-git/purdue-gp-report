"""Assemble everything the web viewer needs into one JSON-serialisable dict."""
import json
import numpy as np
from .config import MPS_TO_MPH
from .laps import gate_vectors


def r(a, nd=1): return np.round(np.asarray(a), nd).tolist()


def build_report_data(df, cfg, laps, crossings, bl, zones, loss_rate, smooth_rate, sync):
    N, data, lag = bl["N"], bl["data"], sync["lag_s"]
    racing = [l for l in laps if l["type"] in ("push", "caution")]
    push = [l for l in laps if l["type"] == "push"]; caut = [l for l in laps if l["type"] == "caution"]
    best = bl["best"]; times = [l["time_s"] for l in push]
    spd = df["GPS Speed"].values; idx_c, ct, _ = crossings
    # pit layer: everything from pit-affected laps, plus before the first and after the last crossing
    mask = np.zeros(len(df), bool); mask[:idx_c[0]] = True; mask[idx_c[-1]:] = True
    for l in laps:
        if l["type"] in ("in-lap", "out-lap"): mask[l["i0"]:l["i1"]] = True
    ix = np.where(mask)[0][::2]; segs = [[ix[0]]]
    for i in ix[1:]:
        if i - segs[-1][-1] > 3: segs.append([])
        segs[-1].append(i)
    pit = [dict(x=r(df.x.values[s]), y=r(df.y.values[s]), v=r(spd[s] * MPS_TO_MPH)) for s in segs if len(s) > 3]
    line = bl["line"]; p, _, nrm = gate_vectors(cfg["gate"]); lo, hi = cfg["gate"]["lateral_window_m"]
    sf = [*(p + nrm * lo).round(1).tolist(), *(p + nrm * hi).round(1).tolist()]
    ax = np.r_[line[:, 0], np.concatenate([q["x"] for q in pit])]; ay = np.r_[line[:, 1], np.concatenate([q["y"] for q in pit])]
    viewer = dict(N=N, OL=round(bl["length"]), b=[round(float(ax.min()), 1), round(float(ay.min()), 1), round(float(ax.max()), 1), round(float(ay.max()), 1)],
                  sf=sf, O=r(line), ov=r(bl["vopt"] * MPS_TO_MPH), lr=r(smooth_rate / smooth_rate.max(), 3), cav=r(np.cumsum(loss_rate), 3),
                  laps=[dict(n=l["n"], cat=l["type"], t=round(l["time_s"], 2), x=r(data[l["n"]]["x"]), y=r(data[l["n"]]["y"]),
                             v=r(data[l["n"]]["v"] * MPS_TO_MPH), o=r(data[l["n"]]["o"], 2), dv=r(data[l["n"]]["dv"] * MPS_TO_MPH),
                             ct=r(data[l["n"]]["ct"], 3)) for l in racing],
                  pit=pit, z=[dict(b0=z["b0"], b1=z["b1"], x=z["x"], y=z["y"]) for z in zones])
    # video time of each zone on the best lap (elapsed time interpolated from best-line speeds)
    elapsed = np.cumsum(bl["ds"] / np.maximum(data[best["n"]]["v"], 1)); elapsed = elapsed / elapsed[-1] * best["time_s"]
    for z in zones: z["video_s"] = float(best["start_s"] + (elapsed[z["b0"] - 1] if z["b0"] > 0 else 0) + lag)
    slow = max(racing, key=lambda l: l["time_s"])
    def trace(l):
        s = df.iloc[l["i0"]:l["i1"]]; return dict(n=l["n"], time_s=r(s.time_s.values[::2] - s.time_s.values[0], 2), mph=r(s["GPS Speed"].values[::2] * MPS_TO_MPH))
    hist, _ = np.histogram(df.RPM[df.RPM > 3000], bins=np.arange(3000, 15500, 500))
    hi_speed = df["GPS Speed"].max() * MPS_TO_MPH
    stint = lambda sel: float(np.mean([l["time_s"] for l in push if sel(l["n"])]))
    pit_laps = [l["n"] for l in laps if l["type"] in ("in-lap", "out-lap")]
    return dict(
        meta=dict(track=cfg["track"], **cfg["session"], samples=len(df), rate_hz=20),
        kpis=dict(best_lap_s=best["time_s"], best_lap_n=best["n"], push_avg_s=float(np.mean(times)), push_count=len(push),
                  top_speed_mph=float(hi_speed), peak_lat_g=float(df.GPS_LateralAcc.abs().quantile(.995)), max_rpm=int(df.RPM.max()),
                  best_line_s=bl["theoretical_s"]),
        summary=dict(push_min_s=min(times), push_max_s=max(times), push_sd_s=float(np.std(times)), caution_laps=[l["n"] for l in caut],
                     caution_avg_s=float(np.mean([l["time_s"] for l in caut])), caution_avg_mph=float(np.mean([l["avg_mph"] for l in caut])),
                     push_avg_mph=float(np.mean([l["avg_mph"] for l in push])), loss_total_s=float(loss_rate.sum()),
                     zones_total_s=float(sum(z["lost_s"] for z in zones)), stint1_s=stint(lambda n: n < min(pit_laps[1:] or [99])),
                     stint2_s=stint(lambda n: n > max(pit_laps)), lap_length_m=float(sum(spd[best["i0"]:best["i1"]]) * .05),
                     egt_peak=int(df["Exhaust Temp"].max()), rpm_over_12k_pct=float((df.RPM > 12000).mean() * 100),
                     slowest_lap=slow["n"], slowest_lap_s=slow["time_s"], caution_threshold_s=cfg["caution_min_lap_s"]),
        laps=[dict({k: v for k, v in l.items() if k not in ("i0", "i1")}, video_start_s=l["start_s"] + lag) for l in laps],
        final_inlap_video_s=float(ct[-1] + lag),
        zones=zones, sync=dict(sync, camera_start_local=cfg["session"]["camera_start_local"]),
        charts=dict(speed_best=trace(best), speed_slowest=trace(slow), rpm_hist=dict(start=3000, step=500, counts=hist.tolist())),
        viewer=viewer)


def write_outputs(report, cfg):
    js = cfg["root"] / cfg["paths"]["web_data"]; jj = cfg["root"] / cfg["paths"]["json"]
    jj.write_text(json.dumps(report)); js.write_text("window.REPORT_DATA = " + json.dumps(report) + ";\n")
