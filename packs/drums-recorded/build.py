#!/usr/bin/env python3
"""Build the recorded CC0 drum pack from the upstream files pinned in recipes.json.

    python3 build.py OUT --cache CACHE [--local vcsl=~/src/vcsl ...]

For every sample in recipes.json (minus the drops in curation.json) it:

1. fetches each upstream file (raw.githubusercontent.com at the pinned commit, or a local
   checkout with --local) and checks its sha256;
2. mixes the mics at the recipe's gains (all sources are 44.1 kHz; anything else is resampled
   to 44.1 kHz), mono mics sit in the centre;
3. high-passes at 20 Hz (2nd-order, causal: no pre-ringing);
4. evens out the left/right balance of centred instruments (drums, hand percussion) when the
   channels differ by more than 1.5 dB RMS; cymbals keep up to 3 dB of lean;
5. trims from 2 ms before the onset (peak -36 dB; -60 dB for rolls and swells) to where the
   sound falls under peak -70 dB or 8 dB over the recording's noise floor, whichever comes
   first, caps the length per class, and fades both ends (raised cosine);
6. levels every file to -1.1 dBTP (4x oversampled true peak), then level-matches each
   round-robin group on the loudness of its first 150 ms (within +/-3 dB, the loudest file of
   the group back at -1.1 dBTP);
7. measures it (length, decays, spectral centroid, low-frequency share, crest, L/R balance and
   correlation, noise floor) and tags its character within its class (bright/dark,
   tight/roomy, punchy, big);
8. writes a 44.1 kHz 24-bit WAV (mono when the channels are identical).

Then it writes SHA256SUMS, provenance.json (per-file sources, sha256s, gains, licences),
NOTICES.md and drums-recorded-cc0.json (the manifest daw pins; `python3 manifest.py` is not a
separate step here: build.py writes it with the release tag given by --tag).

Deterministic: the same inputs and pinned numpy/scipy/soundfile versions give the same bytes.
"""

import argparse
import hashlib
import json
import os
import sys
import urllib.parse
import urllib.request

import numpy as np
import soundfile as sf
from scipy import signal
from scipy.ndimage import minimum_filter1d

SR = 44100
PEAK_DBTP = -1.1
HERE = os.path.dirname(os.path.abspath(__file__))

# Classes whose image should be centred (a kit places them with its pan).
CENTRED = {"kick", "snare", "rim", "tom", "bass-drum", "timpani", "frame-drum", "clap", "perc",
           "impact", "roll"}
SWELLS = {"roll", "cymbal-swell"}
MAX_LEN = {"kick": 1.5, "snare": 1.5, "rim": 1.0, "clap": 1.5, "tom": 3.0, "bass-drum": 4.0,
           "timpani": 5.0, "frame-drum": 2.5, "hat-closed": 1.0, "hat-pedal": 1.0,
           "hat-open": 2.0, "perc": 2.0, "impact": 5.0, "crash": 6.0, "ride": 5.0, "gong": 14.0,
           "cymbal-swell": 12.0, "roll": 10.0}
# Low hits whose first transient is limited so the body carries the level: recorded acoustic
# drums peak 9-14 dB over their first 100 ms, commercial one-shots 2.6-6.5 dB (daw's weight
# check flags over 9). A smooth 8 ms look-around limiter takes the spike down to PUNCH_CREST_DB,
# never by more than PUNCH_MAX_DB.
PUNCH = {"kick", "tom", "bass-drum", "frame-drum"}
PUNCH_CREST_DB = 7.0
PUNCH_MAX_DB = 8.0
PUNCH_SAT_DB = 8.5
# Classes the character tags compare within (a tom is bright for a tom).
LOW = {"kick", "tom", "bass-drum", "timpani", "frame-drum", "roll"}


# Default pad gains (dB) over the peak-normalised files, for a kit that plays balanced out of
# the box; a kit's pad spec can set its own `gain_db`.
PAD_GAIN_DB = {"kick": 0.0, "snare": -2.0, "clap": -5.0, "rim": -8.0, "ch": -9.0, "ph": -12.0,
               "oh": -9.0, "tom_lo": -1.0, "tom_mid": -2.0, "tom_hi": -3.0, "crash": -6.0,
               "ride": -10.0, "perc": -6.0}


def db(x):
    return 20.0 * np.log10(np.maximum(x, 1e-12))


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def fetch(src, sources, cache, local):
    lib = sources[src["lib"]]
    if src["lib"] in local:
        path = os.path.join(local[src["lib"]], src["path"])
    else:
        path = os.path.join(cache, src["lib"], src["path"])
        if not (os.path.isfile(path) and sha256_file(path) == src["sha256"]):
            url = "https://raw.githubusercontent.com/{}/{}/{}".format(
                lib["repo"], lib["commit"], urllib.parse.quote(src["path"]))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            for attempt in range(4):
                try:
                    with urllib.request.urlopen(url, timeout=120) as r:
                        data = r.read()
                    break
                except Exception as e:  # noqa: BLE001 - retried, then fatal
                    if attempt == 3:
                        sys.exit(f"download failed: {url}: {e}")
            with open(path + ".part", "wb") as f:
                f.write(data)
            os.replace(path + ".part", path)
    got = sha256_file(path)
    if got != src["sha256"]:
        sys.exit(f"sha256 mismatch for {src['lib']}:{src['path']}: {got} != {src['sha256']}")
    return path


def load(path):
    x, sr = sf.read(path, dtype="float64", always_2d=True)
    if sr != SR:
        g = np.gcd(SR, sr)
        x = signal.resample_poly(x, SR // g, sr // g, axis=0)
    if x.shape[1] == 1:
        x = np.repeat(x, 2, axis=1)
    return x[:, :2]


def true_peak(x):
    up = signal.resample_poly(x, 4, 1, axis=0)
    return float(np.max(np.abs(up)))


def env_db(x, win):
    """RMS envelope (dB) over hops of `win` samples, max over channels."""
    n = len(x) // win
    if n == 0:
        return np.array([db(np.sqrt(np.mean(x ** 2)))])
    e = x[: n * win].reshape(n, win, x.shape[1])
    return db(np.sqrt(np.mean(e ** 2, axis=1)).max(axis=1))


def raised_cosine(n):
    return 0.5 - 0.5 * np.cos(np.pi * (np.arange(n) + 0.5) / n)


def punch(x, info):
    """Limit the transient spike of a trimmed low hit (see PUNCH): repeat until the crest of
    the first 100 ms (mono peak over mono RMS, as daw's weight check measures it) is at
    PUNCH_CREST_DB, never limiting more than PUNCH_MAX_DB in all."""
    n100 = int(0.1 * SR)
    w = int(0.008 * SR) | 1
    kernel = np.hanning(w + 2)[1:-1]
    kernel /= kernel.sum()
    a0 = np.abs(x).max()
    floor = a0 * 10 ** (-PUNCH_MAX_DB / 20)
    for _ in range(8):
        m = x[:n100].mean(axis=1)
        crest = float(db(np.abs(m).max()) - db(np.sqrt(np.mean(m ** 2))))
        a = np.abs(x).max(axis=1)
        if crest <= PUNCH_CREST_DB + 0.1 or a.max() <= floor * 1.001:
            break
        ceil = max(a.max() * 10 ** (-(crest - PUNCH_CREST_DB) / 20), floor)
        g = np.minimum(1.0, ceil / np.maximum(a, 1e-12))
        g = minimum_filter1d(g, w, mode="nearest")
        g = np.convolve(np.pad(g, (w // 2, w // 2), mode="edge"), kernel, mode="valid")
        x = x * g[:, None]
    info["limited_db"] = round(float(db(a0) - db(np.abs(x).max())), 2)
    # Still spiky (a fast-decaying body under the beater): saturate the whole hit gently, the
    # least drive (tanh, 1..6) that brings the crest to PUNCH_SAT_DB.
    def crest_of(y):
        m = y[:n100].mean(axis=1)
        return float(db(np.abs(m).max()) - db(np.sqrt(np.mean(m ** 2))))
    if crest_of(x) > PUNCH_SAT_DB:
        y0 = x / np.abs(x).max()
        drive = 1.0
        for drive in np.arange(1.0, 6.01, 0.25):
            y = np.tanh(drive * y0) / np.tanh(drive)
            if crest_of(y) <= PUNCH_SAT_DB:
                break
        x = y
        info["saturation_drive"] = round(float(drive), 2)
    return x


def process(x, category, max_len):
    info = {}
    # Clipping in the source: runs of 3+ samples at the rail.
    rail = np.abs(x) >= 0.999
    runs = np.sum(rail[2:] & rail[1:-1] & rail[:-2])
    info["source_clipped_runs"] = int(runs)
    sos = signal.butter(2, 20.0, "highpass", fs=SR, output="sos")
    x = signal.sosfilt(sos, x, axis=0)
    a = np.abs(x).max(axis=1)
    peak = a.max()
    thr = peak * 10 ** ((-60 if category in SWELLS else -36) / 20)
    i0 = int(np.argmax(a >= thr))
    pre = int(0.002 * SR)
    start = max(0, i0 - pre)
    # Noise floor: the quietest 10 ms window of the last quarter of the recording.
    win = int(0.01 * SR)
    tail = env_db(x[len(x) * 3 // 4:], win)
    floor = float(np.min(tail)) if len(tail) else -120.0
    e = env_db(x[start:], win)
    stop_db = max(db(peak) - 70.0, floor + 8.0)
    above = np.nonzero(e > stop_db)[0]
    end = start + (int(above[-1]) + 1) * win if len(above) else len(x)
    end = min(end, len(x), start + int(max_len * SR))
    x = x[start:end].copy()
    n = len(x)
    fin = min(i0 - start, n // 4)
    if fin > 0:
        x[:fin] *= raised_cosine(fin)[:, None]
    fout = int(np.clip(0.15 * n, 0.02 * SR, 0.4 * SR))
    fout = min(fout, n // 2)
    x[n - fout:] *= raised_cosine(fout)[::-1][:, None]
    info["snr_db"] = round(float(db(peak) - floor), 1)
    info["floor_dbfs_source"] = round(floor, 1)
    # L/R balance.
    rms = np.sqrt(np.mean(x ** 2, axis=0))
    bal = float(db(rms[0]) - db(rms[1]))
    info["balance_db_source"] = round(bal, 2)
    lim = 1.5 if category in CENTRED else 3.0
    if abs(bal) > lim:
        keep = 0.0 if category in CENTRED else np.sign(bal) * lim
        corr = (bal - keep) / 2.0
        x[:, 0] *= 10 ** (-corr / 20)
        x[:, 1] *= 10 ** (corr / 20)
    if category in PUNCH:
        x = punch(x, info)
    x *= 10 ** (PEAK_DBTP / 20) / true_peak(x)
    return x, info


def measure(x, category):
    m = {}
    n = len(x)
    mono = x.mean(axis=1)
    m["duration_s"] = round(n / SR, 3)
    win = int(0.005 * SR)
    e = env_db(x, win)
    k = int(np.argmax(e))
    pk = e[k]
    for drop in (20, 40):
        below = np.nonzero(e[k:] < pk - drop)[0]
        m[f"decay_{drop}_s"] = round(float(below[0] * win / SR), 3) if len(below) else None
    h = min(n, int(0.15 * SR))
    m["loud150_db"] = round(float(db(np.sqrt(np.mean(x[:h] ** 2)))), 2)
    w50 = int(0.05 * SR)
    sq = np.concatenate([[0.0], np.cumsum((x ** 2).mean(axis=1))])
    if n > w50:
        m["loud50_db"] = round(float(db(np.sqrt(np.max(sq[w50:] - sq[:-w50]) / w50))), 2)
    else:
        m["loud50_db"] = round(float(db(np.sqrt(sq[-1] / max(n, 1)))), 2)
    m["crest_db"] = round(float(db(np.abs(x).max()) - m["loud150_db"]), 2)
    seg = mono[: min(n, int(0.3 * SR))]
    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg)), 1 << 15)) ** 2
    f = np.fft.rfftfreq(1 << 15, 1 / SR)
    tot = spec.sum() + 1e-30
    m["centroid_hz"] = round(float((spec * f).sum() / tot), 0)
    m["low_share_db"] = round(float(10 * np.log10(spec[f < 150].sum() / tot + 1e-12)), 2)
    m["sub_share_db"] = round(float(10 * np.log10(spec[(f >= 20) & (f < 80)].sum() / tot + 1e-12)), 2)
    rms = np.sqrt(np.mean(x ** 2, axis=0))
    m["balance_db"] = round(float(db(rms[0]) - db(rms[1])), 2)
    if np.std(x[:, 0]) > 0 and np.std(x[:, 1]) > 0:
        m["correlation"] = round(float(np.corrcoef(x[:, 0], x[:, 1])[0, 1]), 3)
    m["true_peak_dbtp"] = round(float(db(true_peak(x))), 2)
    m["end_dbfs"] = round(float(db(np.sqrt(np.mean(x[-3 * win:-2 * win] ** 2)))), 1)
    return m


def character(samples):
    """Tags relative to the sample's class: bright/dark, tight/roomy, punchy, big."""
    by = {}
    for s in samples:
        by.setdefault(s["category"], []).append(s)
    for cat, group in by.items():
        def pct(key, q):
            v = [s["measure"][key] for s in group if s["measure"].get(key) is not None]
            return float(np.percentile(v, q)) if v else None
        c33, c67 = pct("centroid_hz", 33), pct("centroid_hz", 67)
        d33, d67 = pct("decay_40_s", 33), pct("decay_40_s", 67)
        k67 = pct("crest_db", 67)
        l50 = pct("low_share_db", 50)
        for s in group:
            m, t = s["measure"], []
            if len(group) >= 3:
                if m["centroid_hz"] >= c67:
                    t.append("bright")
                elif m["centroid_hz"] <= c33:
                    t.append("dark")
                d = m.get("decay_40_s")
                if d is not None and d33 is not None:
                    if d <= d33:
                        t.append("tight")
                    elif d >= d67:
                        t.append("roomy")
                if m["crest_db"] >= k67 and (m.get("decay_20_s") or 9) < 0.35:
                    t.append("punchy")
            if cat in LOW | {"gong", "impact"} and m["low_share_db"] >= (l50 or 0) and \
                    m["duration_s"] >= 0.8:
                t.append("big")
            s["character"] = t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--cache", default=os.path.join(HERE, ".cache"))
    ap.add_argument("--local", action="append", default=[], help="lib=path of a checkout")
    ap.add_argument("--tag", default="drums-recorded-cc0-2026-09-30")
    a = ap.parse_args()
    local = dict(s.split("=", 1) for s in a.local)
    local = {k: os.path.expanduser(v) for k, v in local.items()}
    rec = json.load(open(os.path.join(HERE, "recipes.json")))
    cur = json.load(open(os.path.join(HERE, "curation.json")))
    sources = rec["sources"]
    drops = cur.get("drop", {})
    os.makedirs(a.out, exist_ok=True)
    kept = []
    for s in rec["samples"]:
        if s["name"] in drops:
            continue
        mix = None
        for src in s["sources"]:
            y = load(fetch(src, sources, a.cache, local)) * src["gain"]
            if mix is None:
                mix = y
            else:
                n = max(len(mix), len(y))
                mix = np.pad(mix, ((0, n - len(mix)), (0, 0))) + np.pad(y, ((0, n - len(y)), (0, 0)))
        x, info = process(mix, s["category"], s.get("max_len_s", MAX_LEN[s["category"]]))
        kept.append(dict(s, audio=x, info=info))
    # Round-robin groups: match the first 150 ms loudness within +/-3 dB, loudest back to the
    # peak target.
    groups = {}
    for s in kept:
        groups.setdefault(s["group"], []).append(s)
    for g in groups.values():
        h = int(0.15 * SR)
        loud = [float(db(np.sqrt(np.mean(s["audio"][:h] ** 2)))) for s in g]
        target = float(np.median(loud))
        for s, l in zip(g, loud):
            s["audio"] = s["audio"] * 10 ** (float(np.clip(target - l, -3, 3)) / 20)
        tp = max(true_peak(s["audio"]) for s in g)
        for s in g:
            s["audio"] = s["audio"] * (10 ** (PEAK_DBTP / 20) / tp)
    for s in kept:
        s["measure"] = measure(s["audio"], s["category"])
    character(kept)
    files = []
    for s in kept:
        x = s.pop("audio")
        mono = np.array_equal(x[:, 0], x[:, 1])
        fname = s["name"] + ".wav"
        path = os.path.join(a.out, fname)
        sf.write(path, x[:, 0] if mono else x, SR, subtype="PCM_24")
        files.append((s, fname, path, 1 if mono else 2))
    # SHA256SUMS and provenance.
    sums, prov = [], []
    for s, fname, path, ch in files:
        h = sha256_file(path)
        s["file"], s["sha256"], s["size"], s["channels"] = fname, h, os.path.getsize(path), ch
        sums.append(f"{h}  {fname}")
        libs = sorted({src["lib"] for src in s["sources"]})
        prov.append({
            "file": fname, "sha256": h, "category": s["category"], "instrument": s["instrument"],
            "license": "CC0-1.0",
            "author": "; ".join(sources[l]["author"] for l in libs),
            "sources": [{"library": sources[src["lib"]]["name"], "repo": sources[src["lib"]]["repo"],
                         "commit": sources[src["lib"]]["commit"], "path": src["path"],
                         "sha256": src["sha256"], "gain": src["gain"],
                         "url": "https://github.com/{}/blob/{}/{}".format(
                             sources[src["lib"]]["repo"], sources[src["lib"]]["commit"],
                             urllib.parse.quote(src["path"]))} for src in s["sources"]],
            "processing": s["info"],
            "measure": s["measure"],
        })
    with open(os.path.join(a.out, "SHA256SUMS"), "w") as f:
        f.write("\n".join(sorted(sums, key=lambda l: l.split("  ")[1])) + "\n")
    with open(os.path.join(a.out, "provenance.json"), "w") as f:
        json.dump({"pack": "drums-recorded-cc0", "tag": a.tag, "sources": sources,
                   "dropped": drops, "files": prov}, f, indent=1)
        f.write("\n")
    write_notices(os.path.join(a.out, "NOTICES.md"), sources, len(files))
    manifest = make_manifest(files, sources, cur, a.tag)
    with open(os.path.join(a.out, "drums-recorded-cc0.json"), "w") as f:
        json.dump(manifest, f, indent=1)
        f.write("\n")
    print(f"{len(files)} files, {len(drops)} dropped, {len(manifest['kits'])} kits", file=sys.stderr)


def write_notices(path, sources, n):
    lines = [
        "# Recorded drums (CC0): notices",
        "",
        f"{n} one-shots of drums and percussion, trimmed, mixed from the upstream microphones, "
        "levelled and level-matched for daw. Every file is derived only from the CC0 recordings "
        "below, so the pack is CC0-1.0 too (https://creativecommons.org/publicdomain/zero/1.0/). "
        "No credit is required; we give it anyway.",
        "",
    ]
    for key, s in sources.items():
        lines += [
            f"## {s['name']}",
            "",
            f"- Author: {s['author']}",
            f"- Licence: {s['license']} ({s['license_url']})",
            f"- Upstream: https://github.com/{s['repo']} at commit `{s['commit']}`",
            f"- Page: {s['page']}",
            "",
        ]
    lines += [
        "Karoryfer Samples states on its free-samples page that all its free libraries are CC0 "
        "(Marie Ork excepted; not used here). Each repository used carries the CC0 1.0 legal "
        "text at the pinned commit.",
        "",
        "Per-file sources (repository, commit, path, upstream sha256 and mic gain) are in "
        "`provenance.json`.",
        "",
    ]
    with open(path, "w") as f:
        f.write("\n".join(lines))


def make_manifest(files, sources, cur, tag):
    base = f"https://github.com/Nullframe/daw-content/releases/download/{tag}/"
    by_name = {s["name"]: s for s, *_ in files}
    samples = []
    for s, fname, path, ch in files:
        libs = sorted({src["lib"] for src in s["sources"]})
        e = {
            "file": fname, "sha256": s["sha256"], "size": s["size"], "category": s["category"],
            "name": s["name"], "instrument": s["instrument"], "group": s["group"],
            "tags": s["tags"], "character": s["character"], "uses": s["uses"],
            "license": "CC0-1.0",
            "author": "; ".join(sources[l]["author"] for l in libs),
            "source": "; ".join(f"https://github.com/{sources[l]['repo']}" for l in libs),
            "measure": s["measure"],
        }
        if "dynamic" in s:
            e["dynamic"] = s["dynamic"]
        samples.append(e)
    kits = []
    for k in cur["kits"]:
        pads = {}
        for pad, spec in k["pads"].items():
            names = [n for g in spec["groups"] for n in sorted(by_name) if by_name[n]["group"] == g]
            if not names:
                continue
            pads[pad] = {"files": [by_name[n]["file"] for n in names],
                         "gain_db": spec.get("gain_db", PAD_GAIN_DB.get(pad, -6.0))}
        kits.append(dict(k, pads=pads))
    return {
        "id": "recpack/drums-recorded-cc0@1",
        "name": "Recorded drums (CC0)",
        "description": cur["description"],
        "tier": "optional",
        "release": f"https://github.com/Nullframe/daw-content/releases/tag/{tag}",
        "base_url": base,
        "notices": base + "NOTICES.md",
        "provenance": base + "provenance.json",
        "licenses": ["CC0-1.0"],
        "sample_rate": SR,
        "files": samples,
        "kits": kits,
    }


if __name__ == "__main__":
    main()
