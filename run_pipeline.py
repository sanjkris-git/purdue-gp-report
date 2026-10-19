"""Run the full analysis and regenerate data/processed/report_data.json and web/data.js.
    python run_pipeline.py
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent / "src"))
from purdue_gp.config import load_config
from purdue_gp.load import load_session
from purdue_gp.laps import find_crossings, build_laps
from purdue_gp.bestline import build_best_line
from purdue_gp.zones import find_zones
from purdue_gp.sync import sync_video
from purdue_gp.export import build_report_data, write_outputs


def main():
    cfg = load_config(); df = load_session(cfg)
    idx, times, lat = find_crossings(df, cfg["gate"]); laps = build_laps(df, idx, times, lat, cfg)
    bl = build_best_line(df, laps, cfg); zones, rate, smooth_rate = find_zones(bl, cfg)
    sync = sync_video(df, cfg)
    report = build_report_data(df, cfg, laps, (idx, times, lat), bl, zones, rate, smooth_rate, sync)
    write_outputs(report, cfg)
    k = report["kpis"]
    print(f"{len(laps)} timed laps | best lap {k['best_lap_n']} = {k['best_lap_s']:.2f}s | best line {k['best_line_s']:.2f}s")
    print(f"video = logger + {sync['lag_s']:.2f}s (r={sync['correlation']:.3f}, windows {['%.2f' % w for w in sync['window_lags_s']]})")
    for i, z in enumerate(zones, 1): print(f"zone {i}: {z['distance_m']} m {z['position']} lost {z['lost_s']:.3f}s")


if __name__ == "__main__":
    main()
