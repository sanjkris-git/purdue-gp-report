# Purdue Grand Prix Track: practice session report

Analysis of one 13-minute kart practice session (logger CSV + GoPro motion data).
Python does the analysis and writes data files; a small static web page displays them.

## Run it
```bash
pip install -r requirements.txt
python run_pipeline.py          # rewrites data/processed/report_data.json and web/data.js
```
Then open `web/index.html` (double-click works; `data.js` is a script tag, so no server is needed).
In VS Code, the Live Server extension also works.

## Layout
| Path | What |
|---|---|
| `config.json` | All tunable choices: start/finish gate, caution threshold, bins, zone count |
| `data/raw/` | `0968_data.csv` (logger, 20 Hz) and `gopro_gpmf.bin` (GoPro metadata track from ffmpeg) |
| `data/processed/report_data.json` | Everything the page shows (laps, best line, zones, sync) |
| `src/purdue_gp/` | `load` > `laps` > `bestline` > `zones`, plus `sync` (GoPro) and `export` |
| `run_pipeline.py` | Runs the steps in order |
| `web/` | `index.html`, `style.css`, `app.js` (renders from `data.js`) |

## Common changes
- **Move the start/finish line:** in `config.json`, add metres to `gate.point` along `gate.direction`
  (`new_point = point + direction * metres`). Laps, best line, zones and video times all recompute.
- **Change which laps count as caution:** edit `caution_min_lap_s`.
- **More or fewer loss zones:** `n_zones`.
- **New session:** replace the two files in `data/raw/`, update `session` in `config.json`, rerun.
  The gate coordinates are track-specific local metres, so reuse them only for the same logger origin.

## How it works (short)
1. **Laps:** the logger path crosses the gate line; crossings in the pit lane make out-laps and in-laps.
2. **Best line:** every racing lap is projected onto the best lap and resampled by distance. The best line is the
   mean path of the three fastest push laps in each stretch, at the best speed any push lap reached there.
   It is demonstrated pace, not a theoretical optimum.
3. **Loss zones:** where the average push lap loses the most time to the best line.
4. **Video sync:** camera yaw rate (gyro about gravity) is correlated with the logger yaw rate from GPS.
   video time = logger time + `lag_s`. No GoPro GPS needed.

## Caveats
GPS position accuracy is about 0.9 m, so line offsets under 1 m are trends. Speed is assumed m/s and
accelerations g. One session, one driver: treat results as a worked example, not a validated method.

## GitHub
- **Run in the browser:** Code > Codespaces > Create codespace. It installs the packages and runs the pipeline.
  View the page with `python -m http.server 8000 --directory web` and open the forwarded port 8000.
- **Publish:** Settings > Pages > Source: GitHub Actions. `.github/workflows/pages.yml` rebuilds and deploys `web/` on each push to `main`.
  Pages on a private repo needs a paid plan; a public repo also makes `data/raw/` public.
