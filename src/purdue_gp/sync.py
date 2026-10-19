"""Sync GoPro video to the logger using only the camera IMU (works with no GPS fix).
Camera yaw rate (gyro about the gravity axis) is correlated with the logger's GPS-derived yaw rate."""
import struct
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import butter, filtfilt, correlate

_FMT = {"b": ("b", 1), "B": ("B", 1), "s": ("h", 2), "S": ("H", 2), "l": ("i", 4), "L": ("I", 4),
        "f": ("f", 4), "d": ("d", 8), "j": ("q", 8), "J": ("Q", 8)}


def _klv(buf, o, end):
    """Walk GPMF key-length-value records, descending into nested containers."""
    while o + 8 <= end:
        key = buf[o:o + 4].decode("latin1"); typ = chr(buf[o + 4]); size = buf[o + 5]
        rep = struct.unpack(">H", buf[o + 6:o + 8])[0]; n = size * rep; d = o + 8
        if typ == "\x00":
            yield key, None, d, n; yield from _klv(buf, d, d + n)
        else:
            yield key, (typ, size), d, n
        o = d + ((n + 3) // 4) * 4


def read_imu(path):
    """Return accelerometer (m/s^2), gyroscope (rad/s) arrays and the video duration in seconds."""
    buf = open(path, "rb").read(); streams = []; cur = None; devc = 0
    for key, ts, d, n in _klv(buf, 0, len(buf)):
        if key == "DEVC": devc += 1
        elif key == "STRM": cur = {}; streams.append(cur)
        elif cur is not None and ts: cur.setdefault(key, []).append((ts, d, n))

    def vals(ts, d, n):
        f, w = _FMT[ts[0]]; cnt = n // w
        return np.array(struct.unpack(">" + f * cnt, buf[d:d + cnt * w])), ts[1] // w

    out = {}
    for s in streams:
        for k in ("ACCL", "GYRO"):
            if k in s and "SCAL" in s:
                scale = vals(*s["SCAL"][0])[0][0]
                for ts, d, n in s[k]:
                    v, cols = vals(ts, d, n); out.setdefault(k, []).append(v.reshape(-1, cols) / scale)
    return np.vstack(out["ACCL"]), np.vstack(out["GYRO"]), devc


def _lowpass(x, fs, fc=1.5):
    b, a = butter(2, fc / (fs / 2)); return filtfilt(b, a, x)


def logger_yaw_rate(df):
    xs, ys = gaussian_filter1d(df.x.values, 4), gaussian_filter1d(df.y.values, 4); t = df.time_s.values
    vx, vy = np.gradient(xs, t), np.gradient(ys, t); heading = np.unwrap(np.arctan2(vy, vx))
    yaw = np.gradient(gaussian_filter1d(heading, 2), t); yaw[np.hypot(vx, vy) < 2] = 0
    return yaw


def sync_video(df, cfg):
    """Return dict(lag_s, correlation, window_lags_s). video_time = logger_time + lag_s."""
    acc, gyro, dur = read_imu(cfg["root"] / cfg["paths"]["gopro_gpmf"])
    fs = len(gyro) / dur; g = acc.mean(0) / np.linalg.norm(acc.mean(0))
    cam = _lowpass(gyro @ g, fs); tc = np.arange(len(cam)) / fs
    t = df.time_s.values; yaw = logger_yaw_rate(df)
    step = 0.05; grid = np.arange(0, dur, step); lgrid = np.arange(t[0], t[-1], step)
    a = np.interp(grid, tc, cam); b = np.interp(lgrid, t, yaw)
    a = (a - a.mean()) / a.std(); b = (b - b.mean()) / b.std()
    lo, hi = cfg["sync"]["coarse_lag_range_s"]; best = None
    for sign in (1, -1):  # camera may be mounted either way round
        cc = correlate(sign * a, b, mode="full", method="fft") / len(b)
        lags = (np.arange(len(cc)) - (len(b) - 1)) * step
        m = (lags > lo) & (lags < hi); i = int(np.argmax(np.where(m, cc, -9)))
        if best is None or cc[i] > best[0]: best = (cc[i], lags[i], sign)
    _, coarse, sign = best; tl = np.arange(t[0] + 1, t[-1] - 6, 0.01); lg = np.interp(tl, t, yaw)

    def score(lag, mask):
        return np.corrcoef(sign * np.interp(tl[mask] + lag, tc, cam), lg[mask])[0, 1]

    h = cfg["sync"]["refine_halfwidth_s"]; lags = np.arange(coarse - h, coarse + h, 0.01)
    full = np.ones(len(tl), bool); sc = [score(l, full) for l in lags]; i = int(np.argmax(sc))
    edges = np.linspace(tl[0], tl[-1], 5); wl = []
    for a_, b_ in zip(edges[:-1], edges[1:]):  # same offset in each quarter => no clock drift
        m = (tl >= a_) & (tl < b_); wl.append(float(lags[int(np.argmax([score(l, m) for l in lags]))]))
    return dict(lag_s=float(lags[i]), correlation=float(sc[i]), window_lags_s=wl)
