"""Build the orchestral CC0 pack for daw's sampler@1 from recipes.json.

    python3 build.py OUT --cache DIR --tag orchestral-cc0-<date> [--src vsco=PATH --src vcsl=PATH]

1. Fetch: a sparse git checkout of each upstream library at its pinned commit (or a local
   checkout given with --src, which must be at that commit); every file is checked against
   the sha256 in recipes.json.
2. Each sample: trimmed to its onset (a short pre-roll with a raised-cosine fade-in) and to the
   decay into its noise floor (raised-cosine fade-out); sustains and tremolos get a loop in
   their steady part (the end matched to the start by cross-correlation, the crossfade baked
   into the file: equal power for uncorrelated material, linear for correlated) and end at the
   loop end. Lossless otherwise: the kept frames are the upstream samples, written as FLAC at
   the source rate and bit depth (44.1 kHz, 16 or 24 bit).
3. Measured: tuning (partials fit around the root; corrected with tune_st within 40 cents),
   loudness (attack window for short notes, a steady window for sustains), peaks.
4. Mapped: key ranges between recorded roots (stretched 4 semitones past the recorded range),
   velocity layers split evenly, notes in a layer evened to a smooth curve over pitch, round
   robins level-matched, adjacent layers meeting at the same loudness (vel_db), every
   articulation normalised to the same loudness at full velocity.
5. Written to OUT: orchestral-cc0-v1.tar (an uncompressed USTAR tar: FLAC files, NOTICE.txt and
   the upstream licence texts), instrument.json (daw's manifest: the archive's sha256, every
   file's sha256, the zone map per articulation), provenance.json, NOTICES.md, SHA256SUMS.

The same inputs give the same bytes (pinned numpy and soundfile; fixed tar metadata).
"""

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile

import numpy as np
import soundfile as sf

import analysis as A

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = "orchestral-cc0"
MAJOR = 1
REPO = "Nullframe/daw-content"
EXT = 4  # semitones a zone map reaches past the recorded range
REF_DB = -20.0  # loudness of every articulation at full velocity (dBFS RMS, before the preset gain)
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def note_name(n):
    return f"{NOTE_NAMES[n % 12]}{n // 12 - 1}"


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# ---- fetch ----------------------------------------------------------------------------------

def fetch(src, paths, cache, given):
    if given:
        root = given
    else:
        root = os.path.join(cache, src["repo"].replace("/", "_"))
        if not os.path.isdir(os.path.join(root, ".git")):
            subprocess.run(["git", "clone", "-q", "--filter=blob:none", "--no-checkout",
                            f"https://github.com/{src['repo']}", root], check=True)
        dirs = sorted({"/" + os.path.dirname(p) + "/" for p in paths})
        subprocess.run(["git", "-C", root, "sparse-checkout", "set", "--no-cone"] + dirs
                       + ["/" + t for t in src["texts"]], check=True)
        subprocess.run(["git", "-C", root, "checkout", "-q", src["commit"]], check=True)
    head = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"], capture_output=True,
                          text=True, check=True).stdout.strip()
    if head != src["commit"]:
        sys.exit(f"{root} is at {head}, not {src['commit']}")
    return root


# ---- processing ------------------------------------------------------------------------------

def env_db(m, sr, win=0.02):
    """RMS envelope in dB per `win` seconds."""
    hop = max(1, int(win * sr))
    n = len(m) // hop
    if n == 0:
        return np.array([-200.0]), hop
    e = np.sqrt(np.mean(m[: n * hop].reshape(n, hop) ** 2, axis=1) + 1e-20)
    return 20 * np.log10(e), hop


def raised_cosine(n):
    return 0.5 - 0.5 * np.cos(np.pi * (np.arange(n) + 0.5) / n)


def trim(x, sr, kind):
    """(start, end) frames to keep."""
    m = np.abs(x).max(axis=1)
    pk = m.max()
    on = int(np.argmax(m >= pk * 10 ** (-50 / 20)))
    pre = int((0.012 if kind == "sustain" else 0.004) * sr)
    start = max(0, on - pre)
    e, hop = env_db(x.mean(axis=1) if x.shape[1] > 1 else x[:, 0], sr)
    floor = float(np.percentile(e[-max(5, len(e) // 10):], 50))
    thr = max(e.max() - 70.0, floor + 6.0)
    above = np.nonzero(e > thr)[0]
    last = (above[-1] + 1) * hop if len(above) else len(x)
    end = min(len(x), last + int(0.05 * sr))
    if kind == "perc":
        end = len(x) if floor < e.max() - 60 else end
    return start, max(end, start + int(0.05 * sr))


def find_loop(x, sr):
    """(start, end, xfade) of a loop in the steady part of a sustain, or None."""
    mono = x.mean(axis=1)
    e, hop = env_db(mono, sr, 0.05)
    n = len(e)
    if n < 40:
        return None
    ref = float(np.median(e[n // 5: n // 2]))
    # The steady part: from where the level first comes within 4 dB of the reference to where
    # it last is (before the release).
    ok = np.nonzero(np.abs(e - ref) <= 4.0)[0]
    if len(ok) < 20:
        return None
    a, b = ok[0] * hop, (ok[-1] + 1) * hop
    a = max(a, int(0.6 * sr))  # past the attack
    b = b - int(0.15 * sr)
    if b - a < int(1.6 * sr):
        return None
    length = min(int(5.0 * sr), int((b - a) * 0.75))
    end = b
    start0 = end - length
    # Match the start to the end: the best normalised correlation of a 30 ms window within
    # +-25 ms of the nominal start.
    w = int(0.03 * sr)
    tgt = mono[end - w: end]
    best, bs = -2.0, start0
    for s in range(start0 - int(0.025 * sr), start0 + int(0.025 * sr)):
        seg = mono[s - w: s]
        den = np.sqrt((seg ** 2).sum() * (tgt ** 2).sum()) + 1e-20
        r = float((seg * tgt).sum() / den)
        if r > best:
            best, bs = r, s
    xf = min(int(0.4 * length), int(0.6 * sr), bs)
    return bs, end, xf


def bake_loop(y, start, end, xf):
    """Crossfade the audio before the loop end into the audio before the loop start, so the
    jump from end to start is seamless. Equal power when the two stretches are uncorrelated
    (vibrato out of phase), linear when they are correlated."""
    a = y[end - xf: end].copy()
    b = y[start - xf: start]
    r = float((a * b).sum() / (np.sqrt((a ** 2).sum() * (b ** 2).sum()) + 1e-20))
    t = (np.arange(xf) + 0.5) / xf
    if r > 0.5:
        ga, gb = 1 - t, t
    else:
        ga, gb = np.cos(t * np.pi / 2), np.sin(t * np.pi / 2)
    y[end - xf: end] = a * ga[:, None] + b * gb[:, None]
    return round(r, 3)


def loud_db(y, sr, kind, start=0):
    if kind == "sustain":
        a, b = start + int(0.3 * sr), start + int(1.5 * sr)
    else:
        a, b = start, start + int(0.25 * sr)
    seg = y[a:b]
    if len(seg) == 0:
        return -200.0
    return float(10 * np.log10(np.mean(seg ** 2) + 1e-20))


def process(path, kind, root, tune):
    info = sf.info(path)
    x, sr = sf.read(path, dtype="float64", always_2d=True)
    if x.shape[1] == 1:
        x = np.repeat(x, 2, axis=1)
    s, e = trim(x, sr, kind)
    y = x[s:e].copy()
    fin = min(int(0.004 * sr), len(y) // 4)
    y[:fin] *= raised_cosine(fin)[:, None]
    lp = find_loop(y, sr) if kind == "sustain" else None
    meta = {"rate": sr, "subtype": info.subtype, "trim_start": s, "trim_end": e}
    if lp:
        ls, le, xf = lp
        meta["loop_xfade_corr"] = bake_loop(y, ls, le, xf)
        y = y[:le]
        meta["loop"] = {"start": ls, "end": le, "xfade": xf}
    else:
        fout = min(int(0.1 * sr), len(y) // 5)
        y[-fout:] *= raised_cosine(fout)[::-1, None]
    cents = None
    if tune:
        fit = A.f0_fit(y, sr, A.et_hz(root), t0=0.05, dur=1.0, search_cents=60)
        if fit and fit[2] >= 2:
            cents = A.cents(fit[0], A.et_hz(root))
    meta.update({
        "seconds": round(len(y) / sr, 3),
        "loudness_db": round(loud_db(y, sr, kind), 2),
        "peak_db": round(A.peak_db(y), 2),
        "cents": None if cents is None else round(cents, 1),
    })
    if info.channels == 1:
        y = y[:, :1]
    buf = io.BytesIO()
    sf.write(buf, y, sr, format="FLAC", subtype=info.subtype)
    return buf.getvalue(), meta


# ---- mapping --------------------------------------------------------------------------------

def key_ranges(roots):
    rs = sorted(set(roots))
    out = {}
    for i, r in enumerate(rs):
        lo = max(0, r - EXT) if i == 0 else (rs[i - 1] + r) // 2 + 1
        hi = min(127, r + EXT) if i == len(rs) - 1 else (r + rs[i + 1]) // 2
        out[r] = (lo, hi)
    return out


def vel_ranges(n):
    edges = [round(1 + 127 * i / n) for i in range(n + 1)]
    return [(edges[i], edges[i + 1] - 1 if i < n - 1 else 127) for i in range(n)]


def map_articulation(art, metas):
    """Zones for one articulation; metas[path] holds each sample's measurements."""
    samples = art["samples"]
    kind = art["kind"]
    if kind == "perc":
        zones = []
        for s in samples:
            m = metas[s["path"]]
            zones.append({"path": s["file"], "root": s["root"], "lo": s["root"], "hi": s["root"],
                          "gain_db": round(REF_DB + 6 - m["loudness_db"], 2)})
        return zones, {"range": [samples[0]["root"], samples[-1]["root"]]}
    layers = sorted({s["layer"] for s in samples})
    vr = dict(zip(layers, vel_ranges(len(layers))))
    rec = {s["path"]: metas[s["path"]]["loudness_db"] for s in samples}
    # Round robins of one note and layer: level-matched to their mean (at most 3 dB).
    groups = {}
    for s in samples:
        groups.setdefault((s["root"], s["layer"]), []).append(s)
    rr_fix = {}
    for g in groups.values():
        mu = float(np.mean([rec[s["path"]] for s in g]))
        for s in g:
            rr_fix[s["path"]] = float(np.clip(mu - rec[s["path"]], -3, 3))
    # Notes within a layer: evened to a smooth curve over pitch (quadratic fit; at most 6 dB).
    fit_at, target = {}, {}
    for l in layers:
        pts = [(r, float(np.mean([rec[s["path"]] for s in g]))) for (r, ll), g in groups.items() if ll == l]
        rs = np.array([p[0] for p in pts], dtype=float)
        ls = np.array([p[1] for p in pts])
        deg = 2 if len(set(rs)) >= 6 else 1 if len(set(rs)) >= 3 else 0
        coef = np.polyfit(rs, ls, deg) if deg else np.array([ls.mean()])
        fit_at[l] = coef
        target[l] = float(np.mean(np.polyval(coef, rs)))
    recorded = dict(target)  # each layer's mean level as recorded (on its curve)
    # Adjacent layers are 1 to 9 dB apart, top down (the recordings span up to 31 dB from pp to
    # ff: too wide for a part at an ordinary velocity; the soft layers keep their timbre).
    for i in range(len(layers) - 2, -1, -1):
        hi_t = target[layers[i + 1]]
        target[layers[i]] = float(np.clip(target[layers[i]], hi_t - 9.0, hi_t - 1.0))
    shift = REF_DB - target[layers[-1]]
    centre = {l: (vr[l][0] + vr[l][1]) / 2 for l in layers}

    def tgt(v):
        """Loudness at velocity v: linear between the layers' centres; flat above the top
        centre; below the lowest the slope continues (at most 6 dB)."""
        cs = [centre[l] for l in layers]
        ts = [target[l] for l in layers]
        if len(layers) == 1:
            return ts[0]
        if v >= cs[-1]:
            return ts[-1]
        if v <= cs[0]:
            slope = (ts[1] - ts[0]) / (cs[1] - cs[0])
            return ts[0] - min(slope * (cs[0] - v), 6.0)
        return float(np.interp(v, cs, ts))

    ranges = {l: key_ranges([s["root"] for s in samples if s["layer"] == l]) for l in layers}
    zones = []
    for s in sorted(samples, key=lambda s: (s["layer"], s["root"], s["rr"])):
        m = metas[s["path"]]
        l = s["layer"]
        lo, hi = ranges[l][s["root"]]
        vl, vh = vr[l]
        # The zone plays at: its round robin group's level, moved onto the layer's smooth
        # curve over pitch (at most 6 dB), then up or down the velocity curve, then shifted so
        # every articulation is equally loud at full velocity.
        own = rec[s["path"]] + rr_fix[s["path"]]
        corr = float(np.clip(np.polyval(fit_at[l], s["root"]) - own, -6, 6))
        pts = [round(rr_fix[s["path"]] + corr + tgt(v) - recorded[l] + shift, 2) for v in (vl, (vl + vh) / 2, vh)]
        z = {"path": s["file"], "root": s["root"], "lo": lo, "hi": hi}
        if len(layers) > 1:
            z.update({"vel_lo": vl, "vel_hi": vh})
        z["vel_db"] = pts
        if m["cents"] is not None and abs(m["cents"]) <= 40:
            z["tune_st"] = round(-m["cents"] / 100, 3)
        if "loop" in m:
            z["loop"] = {"start": m["loop"]["start"], "end": m["loop"]["end"], "xfade": 0}
        zones.append(z)
    all_roots = [s["root"] for s in samples]
    return zones, {"range": [min(all_roots), max(all_roots)], "layers": len(layers),
                   "layer_db": {str(l): round(target[l] + shift, 2) for l in layers}}


def part_range(part, info):
    """'violins-sustain F4-F#6': where the part plays in an ensemble (its split, within the
    reach of its zone map)."""
    lo = max(part["lo"], NOTE_NAMES.index(info["range"][0][:-1]) + 12 * (int(info["range"][0][-1]) + 1) - EXT)
    hi = min(part["hi"], NOTE_NAMES.index(info["range"][1][:-1]) + 12 * (int(info["range"][1][-1]) + 1) + EXT)
    return f"{part['articulation']} {note_name(lo)}-{note_name(hi)}"


# ---- main -----------------------------------------------------------------------------------

def notice_text(recipes):
    v, c = recipes["sources"]["vsco"], recipes["sources"]["vcsl"]
    return f"""Orchestral CC0 pack for daw (orchestral-cc0-v{MAJOR})
===============================================

Recorded orchestral instruments: string sections (violins, violas, celli) and a solo double
bass with sustain, spiccato, pizzicato and tremolo; French horn, trumpet, tenor trombone and
tuba (sustain, staccato); flute, oboe, clarinet and bassoon (sustain, staccato); concert harp;
glockenspiel, xylophone, marimba, vibraphone (struck and bowed), tubular bells; mark tree, bell
tree, sleigh bells, finger cymbals and ratchets.

Licence: every file in this archive is CC0 1.0 Universal (public domain dedication). The
upstream licence texts are in licenses/.

Sources (checked at the pinned commits, {"2026-10-01"}):

- {v['name']}
  {v['author']}
  https://github.com/{v['repo']} at commit {v['commit']}
  Licence: CC0-1.0 (LICENSE at that commit). Its Readme.txt asks, as a courtesy (not a licence
  condition), for credit to Versilian Studios / Sam Gossner and Ivy Audio / Simon Dalzell and a
  link to the VSCO: CE homepage, {v['page']} . With thanks: this pack is built on their work.

- {c['name']}
  {c['author']}
  https://github.com/{c['repo']} at commit {c['commit']}
  Licence: CC0-1.0 (LICENSE at that commit; README: "no royalties, no credit, no special
  terms"). Credited anyway: {c['page']}

Processing (Nullframe/daw-content packs/orchestral-cc0/build.py): trimmed to the onset and to
the decay into the noise floor with raised-cosine fades; sustains and tremolos loop in their
steady part (crossfade baked in) and end at the loop end. The kept audio is otherwise the
upstream samples, losslessly re-encoded as FLAC at the source rate and bit depth. Tuning,
level and mapping corrections are in daw's instrument.json, not in the audio. Sounding pitch:
both libraries name most folders one octave below the sounding pitch (VSCO's "C4" sounds C5);
the roots here are sounding pitches, checked against the recordings.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--cache", default=os.path.join(HERE, ".cache"))
    ap.add_argument("--tag", required=True, help="the release tag, e.g. orchestral-cc0-2026-10-01")
    ap.add_argument("--src", action="append", default=[], help="LIB=PATH: a local checkout")
    a = ap.parse_args()
    with open(os.path.join(HERE, "recipes.json")) as fh:
        recipes = json.load(fh)
    given = dict(s.split("=", 1) for s in a.src)
    arts = recipes["articulations"]
    paths = {}
    for art in arts:
        for s in art["samples"]:
            paths.setdefault(art["lib"], set()).add(s["path"])
    roots = {lib: fetch(recipes["sources"][lib], sorted(ps), a.cache, given.get(lib))
             for lib, ps in sorted(paths.items())}
    os.makedirs(a.out, exist_ok=True)
    members = {}  # archive path -> bytes
    metas = {}
    prov = []
    for art in arts:
        lib = art["lib"]
        # Tuning from a partials fit needs a ringing or held note: not one-shot percussion,
        # tubular bells (their strike tone is not a partial) or staccato and spiccato bursts.
        tune = art["kind"] in ("sustain", "pluck", "mallet") and art["name"] != "tubular-bells"
        for s in art["samples"]:
            src = os.path.join(roots[lib], s["path"])
            if sha256_file(src) != s["sha256"]:
                sys.exit(f"{s['path']}: sha256 does not match recipes.json")
            if "name" in s:
                stem = s["name"]
            else:
                stem = f"{note_name(s['root']).replace('#', 's')}-l{s['layer']}-rr{s['rr']}"
            s["file"] = f"{art['family']}/{art['name']}/{stem}.flac"
            data, meta = process(src, art["kind"], s["root"], tune)
            members[s["file"]] = data
            metas[s["path"]] = meta
            prov.append({"file": s["file"], "sha256": sha256_bytes(data), "articulation": art["name"],
                         "root": s["root"], "layer": s["layer"], "rr": s["rr"],
                         "source": {"lib": lib, "repo": recipes["sources"][lib]["repo"],
                                    "commit": recipes["sources"][lib]["commit"], "path": s["path"],
                                    "sha256": s["sha256"]},
                         "measure": meta})
        print(f"{art['name']}: {len(art['samples'])} files", file=sys.stderr)
    articulations, info = {}, {}
    for art in arts:
        zones, extra = map_articulation(art, metas)
        articulations[art["name"]] = {"zones": zones}
        info[art["name"]] = {"instrument": art["instrument"], "family": art["family"],
                             "kind": art["kind"], "source": recipes["sources"][art["lib"]]["name"],
                             "range": [note_name(extra["range"][0]), note_name(extra["range"][1])],
                             "files": len(art["samples"]), **{k: v for k, v in extra.items() if k != "range"}}
    for ens in recipes["ensembles"]:
        zones = []
        for part in ens["parts"]:
            for z in articulations[part["articulation"]]["zones"]:
                lo, hi = max(z["lo"], part["lo"]), min(z["hi"], part["hi"])
                if lo <= hi:
                    zones.append(dict(z, lo=lo, hi=hi))
        articulations[ens["name"]] = {"zones": zones}
        first, last = ens["parts"][0]["articulation"], ens["parts"][-1]["articulation"]
        info[ens["name"]] = {"instrument": ens["instrument"], "family": info[first]["family"],
                             "kind": info[first]["kind"], "source": info[first]["source"],
                             "range": [info[first]["range"][0], info[last]["range"][1]],
                             "parts": [part_range(p, info[p["articulation"]]) for p in ens["parts"]]}
    # Licence texts and the notice.
    for lib, src in sorted(recipes["sources"].items()):
        for t in src["texts"]:
            with open(os.path.join(roots[lib], t), "rb") as fh:
                members[f"licenses/{src['repo'].split('/')[1]}-{t}"] = fh.read()
    members["NOTICE.txt"] = notice_text(recipes).encode()
    stem = f"{NAME}-v{MAJOR}"
    tar_path = os.path.join(a.out, stem + ".tar")
    with open(tar_path + ".part", "wb") as fh:
        with tarfile.open(fileobj=fh, mode="w", format=tarfile.USTAR_FORMAT) as t:
            for p in sorted(members):
                ti = tarfile.TarInfo(p)
                ti.size, ti.mtime, ti.mode = len(members[p]), 0, 0o644
                ti.uid = ti.gid = 0
                ti.uname = ti.gname = ""
                t.addfile(ti, io.BytesIO(members[p]))
    os.replace(tar_path + ".part", tar_path)
    tar_sha, size = sha256_file(tar_path), os.path.getsize(tar_path)
    default = "strings-sustain"
    manifest = {
        "id": f"instrument/{NAME}@{MAJOR}",
        "name": "Orchestral (CC0)",
        "description": "Recorded orchestra from VSCO 2 CE and VCSL (CC0): violin, viola and cello sections and double bass "
                       "(sustain, spiccato, pizzicato, tremolo), horn, trumpet, trombone and tuba (sustain, staccato), flute, "
                       "oboe, clarinet and bassoon (sustain, staccato), harp, glockenspiel, xylophone, marimba, vibraphone, "
                       "tubular bells and orchestral percussion colours; full-range section patches (strings, brass, winds). "
                       "Pick one with an articulation.",
        "device": "sampler@1",
        "tags": ["orchestral", "orchestra", "cinematic", "strings", "brass", "woodwinds", "harp", "mallets", "recorded", "cc0"],
        "license": "CC0-1.0",
        "license_url": recipes["sources"]["vsco"]["license_url"],
        "author": "Versilian Studios LLC (Sam Gossner), Ivy Audio (Simon Dalzell) and contributors; packaged by Nullframe",
        "source": f"https://github.com/{REPO}/tree/main/packs/{NAME}",
        "upstream": {k: {"repo": v["repo"], "commit": v["commit"], "license": v["license"],
                         "license_url": v["license_url"]} for k, v in recipes["sources"].items()},
        "packaged_by": f"{REPO} packs/{NAME}/build.py",
        "archive": {"file": stem + ".tar",
                    "url": f"https://github.com/{REPO}/releases/download/{a.tag}/{stem}.tar",
                    "sha256": tar_sha, "size": size},
        "default_articulation": default,
        "articulation_info": info,
        "stats": {"files": sum(len(x["samples"]) for x in arts),
                  "articulations": len(articulations),
                  "sample_seconds": round(sum(m["seconds"] for m in metas.values()), 1),
                  "sample_rate": 44100},
        "files": {p: sha256_bytes(b) for p, b in sorted(members.items())},
        "data": articulations[default],
        "articulations": articulations,
    }
    with open(os.path.join(a.out, "instrument.json"), "w") as fh:
        fh.write(dump_manifest(manifest))
    with open(os.path.join(a.out, "provenance.json"), "w") as fh:
        json.dump({"tag": a.tag, "archive": stem + ".tar", "sha256": tar_sha,
                   "sources": recipes["sources"], "files": prov}, fh, indent=1, default=_np)
        fh.write("\n")
    with open(os.path.join(HERE, "NOTICES.md")) as fh:
        notices = fh.read()
    with open(os.path.join(a.out, "NOTICES.md"), "w") as fh:
        fh.write(notices)
    with open(os.path.join(a.out, "SHA256SUMS"), "w") as fh:
        for f in sorted(os.listdir(a.out)):
            if f != "SHA256SUMS" and not f.endswith(".part"):
                fh.write(f"{sha256_file(os.path.join(a.out, f))}  {f}\n")
    print(json.dumps({"archive": tar_path, "sha256": tar_sha, "size": size,
                      "files": manifest["stats"]["files"]}, indent=1))


def _np(o):
    return o.item()


def dump_manifest(m):
    """indent=1 JSON with one zone per line (the zone map stays reviewable and small)."""
    def enc(v, ind):
        pad = " " * ind
        if isinstance(v, dict):
            if "path" in v and "root" in v:
                return json.dumps(v, separators=(", ", ": "), default=_np)
            if not v:
                return "{}"
            items = [f'{pad} {json.dumps(k)}: {enc(x, ind + 1)}' for k, x in v.items()]
            return "{\n" + ",\n".join(items) + f"\n{pad}}}"
        if isinstance(v, list):
            if all(not isinstance(x, (dict, list)) for x in v):
                return json.dumps(v, default=_np)
            items = [f"{pad} {enc(x, ind + 1)}" for x in v]
            return "[\n" + ",\n".join(items) + f"\n{pad}]"
        return json.dumps(v, default=_np)
    return enc(m, 0) + "\n"


if __name__ == "__main__":
    main()
