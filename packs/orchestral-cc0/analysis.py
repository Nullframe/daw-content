"""Measurements used to map multisampled instruments: onset, loudness and tuning.

Deterministic (numpy FFTs, fixed windows); results are rounded before they go in a manifest.
"""

import numpy as np

# Loudness window after the onset (s): the attack and early sustain, what a listener compares
# between velocity layers.
LOUD_FROM, LOUD_TO = 0.02, 0.32


def mono(x):
    return x.mean(axis=1) if x.ndim == 2 else x


def onset(x, sr, rel_db=-40.0):
    """First frame whose level is within `rel_db` of the file's peak."""
    m = np.abs(mono(x))
    pk = m.max()
    if pk <= 0:
        return 0
    return int(np.argmax(m >= pk * 10 ** (rel_db / 20)))


def loudness_db(x, sr, start=None):
    """RMS (dBFS, both channels) over the loudness window after the onset."""
    s = onset(x, sr) if start is None else start
    a, b = s + int(LOUD_FROM * sr), s + int(LOUD_TO * sr)
    seg = x[a:b]
    if len(seg) == 0:
        return -200.0
    return float(10 * np.log10(np.mean(seg.astype(np.float64) ** 2) + 1e-20))


def peak_db(x):
    return float(20 * np.log10(np.abs(x).max() + 1e-20))


def _spectrum(x, sr, t0, dur):
    """Magnitude spectrum of the mono segment [onset + t0, + dur] (Hann, 8x zero padding),
    cut where the note has decayed 30 dB below its level at t0 (the faint tail, where a
    key's unison strings drift apart, would otherwise weigh on the estimate)."""
    on = onset(x, sr)
    m = mono(x).astype(np.float64)
    a = on + int(t0 * sr)
    hop = int(0.05 * sr)
    env = [np.sqrt(np.mean(m[i : i + hop] ** 2) + 1e-30) for i in range(a, min(len(m), a + int(dur * sr)), hop)]
    if env:
        quiet = [i for i, e in enumerate(env) if e < env[0] * 10 ** (-30 / 20)]
        if quiet:
            dur = max(0.25, quiet[0] * 0.05)
    seg = m[on + int(t0 * sr) : on + int((t0 + dur) * sr)]
    if len(seg) < int(0.25 * sr):
        seg = m[on : on + int(dur * sr)]
    w = np.hanning(len(seg))
    nfft = 1 << int(np.ceil(np.log2(len(seg) * 8)))
    return np.abs(np.fft.rfft(seg * w, nfft)), sr / nfft


def _interp_peak(spec, df, f, tol_hz):
    """Parabolic-interpolated peak (Hz, magnitude) of `spec` within +-tol_hz of `f`, or None
    if the maximum sits on the edge of the range (no peak there)."""
    lo, hi = max(int((f - tol_hz) / df), 1), min(int(np.ceil((f + tol_hz) / df)), len(spec) - 2)
    if hi - lo < 2:
        return None
    k = lo + int(np.argmax(spec[lo : hi + 1]))
    if k <= lo or k >= hi:
        return None
    a, b, c = (np.log(spec[j] + 1e-30) for j in (k - 1, k, k + 1))
    d = 0.5 * (a - c) / (a - 2 * b + c)
    return (k + d) * df, spec[k]


# Pitch window after the onset (s). Two seconds average over the beating of a key's unison
# strings (which moves a short window's estimate by several cents in the treble).
PITCH_FROM, PITCH_DUR = 0.1, 2.0


def f0_fit(x, sr, nominal, t0=PITCH_FROM, dur=PITCH_DUR, partials=16, search_cents=80):
    """Fundamental of a (piano) string: partials sit at f_n = n f0 sqrt(1 + B n^2).

    1. Grid search over f0 (+-search_cents around `nominal`, 0.5 cent steps) and B (0 and
       1e-5..3e-2): the pair whose predicted partials collect the most spectral energy
       (magnitudes compressed by a square root, so no single partial dominates).
    2. Each predicted partial is refined to its interpolated spectral peak; partials within
       40 dB of the strongest are fitted: (f_n / n)^2 = f0^2 + f0^2 B n^2, weighted by
       magnitude. The intercept gives f0.
    Returns (f0 Hz, B, partials used) or None."""
    spec, df = _spectrum(x, sr, t0, dur)
    comp = np.sqrt(spec)
    nyq = sr * 0.45
    f0s = nominal * 2 ** (np.arange(-search_cents, search_cents + 0.25, 0.5) / 1200)
    Bs = np.concatenate([[0.0], np.geomspace(1e-5, 3e-2, 60)])
    ns = np.arange(1, partials + 1, dtype=np.float64)
    best = (-1.0, nominal, 0.0)
    for B in Bs:
        fn = f0s[:, None] * ns[None, :] * np.sqrt(1 + B * ns[None, :] ** 2)
        ok = fn < nyq
        idx = np.clip(np.rint(fn / df).astype(np.int64), 0, len(comp) - 1)
        # The local maximum within one bin either side (the grid is finer than a peak's width).
        v = np.maximum(np.maximum(comp[idx], comp[np.clip(idx - 1, 0, None)]),
                       comp[np.clip(idx + 1, None, len(comp) - 1)])
        score = (v * ok).sum(axis=1)
        i = int(np.argmax(score))
        if score[i] > best[0]:
            best = (float(score[i]), float(f0s[i]), float(B))
    _, f0, B = best
    found = []
    for n in range(1, partials + 1):
        fp = n * f0 * np.sqrt(1 + B * n * n)
        if fp >= nyq:
            break
        p = _interp_peak(spec, df, fp, max(3 * df, fp * (2 ** (8 / 1200) - 1)))
        if p is not None:
            found.append((n, p[0], p[1]))
    if not found:
        return None
    top = max(m for _, _, m in found)
    use = [(n, fr, m) for n, fr, m in found if m >= top * 10 ** (-40 / 20)]
    if len(use) == 1:
        n, fr, _ = use[0]
        return fr / (n * np.sqrt(1 + B * n * n)), B, 1
    ks = np.array([n for n, _, _ in use], dtype=np.float64)
    fs = np.array([fr for _, fr, _ in use])
    wts = np.sqrt(np.array([m for _, _, m in use]) / top)
    X = np.stack([np.ones_like(ks), ks**2], axis=1)
    coef, *_ = np.linalg.lstsq(X * wts[:, None], (fs / ks) ** 2 * wts, rcond=None)
    f0sq = max(coef[0], 1e-9)
    return float(np.sqrt(f0sq)), float(max(coef[1] / f0sq, 0.0)), len(use)


def pitch_hz(x, sr, nominal):
    """The pitch a listener hears as the note's: the power-weighted centre of the first
    partial (+-15 cents around its peak, so a key whose unison strings are a few cents apart
    reads as their average, not whichever string's peak is higher), when that partial is within
    40 dB of the strongest one; else predicted from the fit, f0 sqrt(1 + B) (bass notes with a
    weak fundamental). Returns (Hz, B, partials)."""
    fit = f0_fit(x, sr, nominal)
    if fit is None:
        return None
    f0, B, n = fit
    spec, df = _spectrum(x, sr, PITCH_FROM, PITCH_DUR)
    f1 = f0 * np.sqrt(1 + B)
    top = spec[int(f1 * 0.9 / df) : int(min(f1 * 16, sr * 0.45) / df)].max()
    lo, hi = int(f1 * 2 ** (-25 / 1200) / df), int(np.ceil(f1 * 2 ** (25 / 1200) / df))
    k = lo + int(np.argmax(spec[lo : hi + 1]))
    if spec[k] < top * 0.01:
        return f1, B, n
    fk = k * df
    a, b = int(fk * 2 ** (-15 / 1200) / df), int(np.ceil(fk * 2 ** (15 / 1200) / df))
    p = spec[a : b + 1] ** 2
    p = np.maximum(p - p.min(), 0)
    return float((np.arange(a, b + 1) * df * p).sum() / p.sum()), B, n


def cents(f, ref):
    return float(1200 * np.log2(f / ref))


def et_hz(note):
    return 440.0 * 2 ** ((note - 69) / 12)
