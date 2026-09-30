"""IR conditioning and measurement for the real-rooms pack.

prepare(src, dst): load, check clipping/DC, remove DC, keep <=2 channels, resample to 48 kHz,
trim leading silence (0.5 ms pre-roll before the direct sound), cut the tail where the
envelope meets the noise floor (+ fade), normalise peak to -1 dBFS, write 24-bit WAV.
measure(x, sr): Schroeder backward integral -> T30-based RT60, EDT, per-octave RT60,
band energy balance, noise floor.
"""
import numpy as np, soundfile as sf
from scipy import signal

SR = 48000


def load(path):
    x, sr = sf.read(path, always_2d=True, dtype="float64")
    return x, sr


def octave(x, sr, fc):
    lo, hi = fc / np.sqrt(2), min(fc * np.sqrt(2), sr / 2 * 0.95)
    sos = signal.butter(4, [lo, hi], btype="band", fs=sr, output="sos")
    return signal.sosfiltfilt(sos, x)


def schroeder(e):
    """e: energy (x^2), trimmed to the useful part. Returns dB curve normalised to 0."""
    c = np.cumsum(e[::-1])[::-1]
    c = c / (c[0] + 1e-30)
    return 10 * np.log10(c + 1e-30)


def noise_floor_cut(mono, sr):
    """(index where the smoothed envelope first falls to the noise floor + 5 dB after the peak,
    noise floor in dB relative to the envelope peak). Lundeby-style: the floor is the median
    of the last 20 % of the non-silent file (trailing digital zeros are ignored)."""
    nz = np.nonzero(np.abs(mono) > 1e-9)[0]
    n = (nz[-1] + 1) if len(nz) else len(mono)
    e = mono[:n] ** 2
    win = int(0.05 * sr)
    env = np.convolve(e, np.ones(win) / win, mode="same")
    env_db = 10 * np.log10(env + 1e-30)
    noise = float(np.median(env_db[int(n * 0.8):]))
    peak_i = int(np.argmax(env_db))
    below = np.where(env_db[peak_i:] < noise + 5)[0]
    cut = peak_i + (int(below[0]) if len(below) else n - peak_i - 1)
    return cut, noise - env_db.max()


def decay_times(x, sr):
    """x mono float. Returns (rt60 T30-based, edt) seconds, or nan."""
    cut, _ = noise_floor_cut(x, sr)
    e = x[:max(cut, int(0.05 * sr))] ** 2
    d = schroeder(e)
    t = np.arange(len(d)) / sr

    def fit(a, b):
        idx = np.where((d <= a) & (d >= b))[0]
        if len(idx) < 10:
            return np.nan
        k, _ = np.polyfit(t[idx], d[idx], 1)
        return -60.0 / k if k < 0 else np.nan

    t30 = fit(-5, -35)
    if np.isnan(t30):
        t30 = fit(-5, -25)  # T20 when the dynamic range is short
    edt = fit(0, -10)
    return t30, edt


def measure(x, sr):
    """x: (n, ch). Everything on the channel mean."""
    m = x.mean(axis=1)
    rt, edt = decay_times(m, sr)
    bands = {}
    for fc in (125, 250, 500, 1000, 2000, 4000, 8000):
        b = octave(m, sr, fc)
        bands[fc] = decay_times(b, sr)[0]
    f, pxx = signal.welch(m, sr, nperseg=4096)
    tot = pxx.sum() + 1e-30
    low = pxx[f < 250].sum() / tot
    mid = pxx[(f >= 250) & (f < 4000)].sum() / tot
    high = pxx[f >= 4000].sum() / tot
    centroid = float((f * pxx).sum() / tot)
    _, nf = noise_floor_cut(m, sr)
    return {
        "rt60_s": round(float(rt), 2), "edt_s": round(float(edt), 2),
        "rt60_bands": {k: (None if np.isnan(v) else round(float(v), 2)) for k, v in bands.items()},
        "balance_db": {"low_lt250": round(10 * np.log10(low + 1e-12), 1),
                       "mid": round(10 * np.log10(mid + 1e-12), 1),
                       "high_gt4k": round(10 * np.log10(high + 1e-12), 1)},
        "centroid_hz": round(centroid),
        "noise_floor_db": round(float(nf), 1),
    }


def prepare(src, dst, channels=None, max_s=10.0, gain_db=-1.0):
    x, sr = load(src)
    if channels is not None:
        x = x[:, channels]
    x = x[:, :2]
    report = {"src_sr": sr, "src_channels": int(x.shape[1]), "src_len_s": round(len(x) / sr, 3)}
    # Clipping = two or more consecutive full-scale samples (a single one is just a
    # peak-normalised source).
    full = np.abs(x) >= 0.9999
    run = best = 0
    for v in full.any(axis=1):
        run = run + 1 if v else 0
        best = max(best, run)
    report["clipped_samples"] = int(full.sum())
    report["max_clip_run"] = int(best)
    report["dc_before"] = float(np.abs(x.mean(axis=0)).max())
    x = x - x.mean(axis=0)
    # 10 Hz high-pass removes residual DC drift without touching the room.
    sos = signal.butter(2, 10, btype="high", fs=sr, output="sos")
    x = signal.sosfiltfilt(sos, x, axis=0)
    if sr != SR:
        from math import gcd
        g = gcd(SR, sr)
        x = signal.resample_poly(x, SR // g, sr // g, axis=0)
        sr = SR
    m = np.abs(x).max(axis=1)
    pk = m.max()
    onset = int(np.argmax(m > pk * 0.1))  # direct sound (-20 dB of peak)
    start = max(0, onset - int(0.0005 * sr))
    x = x[start:]
    cut, nf = noise_floor_cut(x.mean(axis=1), sr)
    end = min(len(x), cut + int(0.05 * sr), int(max_s * sr))
    x = x[:end].copy()
    fade = min(int(0.1 * sr), len(x) // 4)
    x[-fade:] *= np.cos(np.linspace(0, np.pi / 2, fade))[:, None] ** 2
    x *= 10 ** (gain_db / 20) / np.abs(x).max()
    report["trim_start_ms"] = round(start / SR * 1000, 1)
    report["len_s"] = round(len(x) / sr, 3)
    report["noise_floor_db"] = round(float(nf), 1)
    report["dc_after"] = float(np.abs(x.mean(axis=0)).max())
    sf.write(dst, x.astype(np.float32), sr, subtype="PCM_24")
    report.update(measure(x, sr))
    return report
