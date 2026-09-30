"""Build a sampled instrument for daw from its official upstream release.

    scripts/instruments/package.sh salamander-grand WORK_DIR OUT_DIR
    scripts/instruments/package.sh upright-kw WORK_DIR OUT_DIR

Steps (all reproducible: pinned upstream archive, sha256-checked; deterministic analysis; a
byte-identical output for the same input):

1. download the upstream archive into WORK_DIR (kept as a cache) and check its sha256;
2. unpack it and parse the upstream SFZ (the author's own zone map: keys, velocity layers,
   release and pedal samples, loops);
3. measure every sample (onset, loudness after the onset, fundamental from the partials with the
   string's inharmonicity) and turn that into the `sampler@1` zone map: `tune_st` so every
   sampled key sits on equal temperament, `vel_db` so adjacent velocity layers meet at the same
   loudness, `start` to skip the silence before the hammer;
4. write OUT_DIR/<name>-v<major>.tar (an uncompressed tar of the upstream FLAC files, byte for
   byte: lossless, at the source rate, plus the upstream readme/licence and our NOTICE) and
   OUT_DIR/<name>-v<major>.tar.sha256, a measurement report OUT_DIR/<name>-report.json, and
   content/instruments/<name>/instrument.json (the zone map and the download manifest).

Only instrument.json is committed. The .tar is uploaded to a Nullframe/daw-content release
(see content/instruments/README.md).
"""

import hashlib
import io
import json
import os
import re
import sys
import tarfile
import urllib.request

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analysis as A  # noqa: E402

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

INSTRUMENTS = {
    "salamander-grand": {
        "id": "instrument/salamander-grand@1",
        "name": "Salamander Grand Piano",
        "description": (
            "Yamaha C5 grand recorded by Alexander Holm: 16 velocity layers sampled every minor "
            "third from A0 (48 kHz, 24-bit), hammer/key release noise on every key, string "
            "resonance releases in three layers, sustain-pedal noise. Retuned to equal "
            "temperament from measurements; velocity layers level-matched and crossfaded."
        ),
        "tags": ["piano", "acoustic", "grand", "keys", "yamaha"],
        "upstream": {
            "url": "https://freepats.zenvoid.org/Piano/SalamanderGrandPiano/"
            "SalamanderGrandPiano-SFZ+FLAC-V3+20200602.tar.gz",
            "sha256": "b7760e168494cf095344e217b0af013fc449ad033abbbdf1c65211cf11dc038b",
            "size": 741757374,
            "root": "SalamanderGrandPiano-SFZ+FLAC-V3+20200602",
            "sfz": "SalamanderGrandPiano-V3+20200602.sfz",
            "texts": ["readme.txt"],
        },
        "license": "public-domain",
        "license_url": "https://rytmenpinne.wordpress.com/sounds-and-such/salamander-grandpiano/",
        "author": "Alexander Holm (rytmenpinne); SFZ+FLAC edition by Roberto (FreePats)",
        "source": "https://freepats.zenvoid.org/Piano/acoustic-grand-piano.html",
        "license_note": (
            "Released under CC-BY 3.0 (archive.org item SalamanderGrandPianoV3, the FreePats "
            "page and the readme inside the archive). The author's page now says, verbatim: "
            "'As of 4.3.2022, this is now public domain! Have fun with it, it's yours and "
            "noones!' (checked 2026-09-29), and on 2 January 2026 he answered a commercial "
            "user asking whether credit is needed: 'I guess, it being public domain these days, "
            "technically no.. do what your conscience tells you'. Either way commercial "
            "redistribution is allowed; we credit him anyway (NOTICE.txt in the archive, docs). "
            "The FreePats FLAC edition is a lossless conversion of his 48 kHz/24-bit WAVs."
        ),
        # Crossfading these layers measured bumpier than switching (they are not phase
        # aligned, so a crossfade comb-filters by up to +-3 dB); level-matched switching
        # stays under 1.5 dB per velocity step (scripts/instruments/verify.py).
        "vel_xfade": 0,
        "max_per_key": 3,
        "trim_onset": True,
    },
    "upright-kw": {
        "id": "instrument/upright-kw@1",
        "name": "Upright Piano KW",
        "description": (
            "Kawai upright in a living room, recorded by Gonzalo and Roberto for FreePats with "
            "a Zoom H1 at the player's head: 2 velocity layers every minor third (extra loud-"
            "layer notes on B), 44.1 kHz/24-bit, looped bass. Retuned to equal temperament from "
            "measurements."
        ),
        "tags": ["piano", "acoustic", "upright", "keys", "intimate"],
        "upstream": {
            "url": "https://freepats.zenvoid.org/Piano/UprightPianoKW/"
            "UprightPianoKW-SFZ+FLAC-20220221.7z",
            "sha256": "3a66da3b25a2fd9499d90bcf09f1aee4431825796e249361b48af59b1201e703",
            "size": 33294287,
            "root": "UprightPianoKW-SFZ+FLAC-20220221",
            "sfz": "UprightPianoKW-20220221.sfz",
            "texts": ["readme.txt", "cc0.txt"],
        },
        "license": "CC0-1.0",
        "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "author": "Gonzalo and Roberto (FreePats project)",
        "source": "https://freepats.zenvoid.org/Piano/acoustic-grand-piano.html",
        "license_note": (
            "The FreePats page and the archive's readme.txt say 'Published under the terms of "
            "Creative Commons CC0 public domain dedication'; the archive ships the CC0 1.0 legal "
            "code (cc0.txt). Commercial redistribution is allowed without conditions."
        ),
        "vel_xfade": 0,
        "max_per_key": 3,
        "trim_onset": False,
    },
}

MAJOR = 1


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def fetch(up, work):
    dest = os.path.join(work, os.path.basename(up["url"]))
    if not (os.path.exists(dest) and sha256_file(dest) == up["sha256"]):
        print(f"downloading {up['url']}", file=sys.stderr)
        tmp = dest + ".part"
        with urllib.request.urlopen(up["url"]) as r, open(tmp, "wb") as f:
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                f.write(b)
        os.replace(tmp, dest)
    got = sha256_file(dest)
    if got != up["sha256"]:
        sys.exit(f"sha256 mismatch for {dest}: expected {up['sha256']}, got {got}")
    if os.path.getsize(dest) != up["size"]:
        sys.exit(f"size mismatch for {dest}")
    root = os.path.join(work, up["root"])
    if not os.path.isdir(root):
        print(f"unpacking {dest}", file=sys.stderr)
        if dest.endswith(".7z"):
            import py7zr

            with py7zr.SevenZipFile(dest) as z:
                z.extractall(work)
        else:
            with tarfile.open(dest) as t:
                t.extractall(work, filter="data")
    return root


# ---------------------------------------------------------------------------------------------
# SFZ

NOTE_RE = re.compile(r"^([a-gA-G])(#|b)?(-?\d)$")


def note_num(v):
    try:
        return int(v)
    except ValueError:
        m = NOTE_RE.match(v)
        if not m:
            raise
        pc = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}[m.group(1).lower()]
        pc += {"#": 1, "b": -1, None: 0}[m.group(2)]
        return 12 * (int(m.group(3)) + 1) + pc


def parse_sfz(path):
    """Regions with their <global>/<group> opcodes inherited (the SFZ subset these files use)."""
    text = open(path, encoding="utf-8", errors="replace").read()
    text = re.sub(r"//[^\n]*", "", text)
    glob, group, regions, cur = {}, {}, [], None
    for header, key, val in re.findall(r"<(\w+)>|(\w+)=(\S+)", text):
        if header == "global":
            glob, group = {}, {}
            cur = glob
        elif header in ("group", "master"):
            group = {}
            cur = group
        elif header == "region":
            regions.append({**glob, **group})
            cur = regions[-1]
        elif header:
            cur = {}
        elif cur is not None:
            cur[key] = val
    return regions


def sfz_vel_db(veltrack, lo, hi, points=9):
    """SFZ amp_veltrack as `vel_db` points across [lo, hi]: gain 1 - t + t (v/127)^2."""
    t = veltrack / 100.0
    vs = np.linspace(lo, hi, points) if hi > lo else np.array([hi])
    return [round(float(20 * np.log10(1 - t + t * (v / 127) ** 2)), 2) for v in vs]


def f(r, k, d=None, conv=float):
    return conv(r[k]) if k in r else d


# ---------------------------------------------------------------------------------------------


def build(name, work, out):
    cfg = INSTRUMENTS[name]
    up = cfg["upstream"]
    root = fetch(up, work)
    regions = parse_sfz(os.path.join(root, up["sfz"]))
    print(f"{len(regions)} regions", file=sys.stderr)

    cache = {}

    def audio(rel):
        if rel not in cache:
            x, sr = sf.read(os.path.join(root, rel), dtype="float32", always_2d=True)
            cache[rel] = (x, sr)
        return cache[rel]

    zones, undamped_from = [], 128
    attack = []
    for r in regions:
        rel = r["sample"].replace("\\", "/")
        z = {"path": rel}
        if "key" in r:
            lo = hi = root_key = note_num(r["key"])
        else:
            lo = note_num(r.get("lokey", "0"))
            hi = note_num(r.get("hikey", "127"))
            root_key = note_num(r.get("pitch_keycenter", "60"))
        trig = r.get("trigger", "attack")
        cc_lo = f(r, "on_locc64", None, int)
        if cc_lo is not None:
            trig = "pedal_down" if cc_lo >= 64 else "pedal_up"
            lo, hi, root_key = 0, 0, 60
        if r.get("pitch_keytrack") == "0":
            if lo != hi:
                sys.exit(f"{rel}: pitch_keytrack=0 over a key range is not supported")
            root_key = lo
        z.update({"root": root_key, "lo": lo, "hi": hi})
        vl, vh = f(r, "lovel", 1, int), f(r, "hivel", 127, int)
        if (vl, vh) != (1, 127):
            z.update({"vel_lo": vl, "vel_hi": vh})
        if trig != "attack":
            z["trigger"] = trig
        gain = f(r, "volume", 0.0)
        if gain:
            z["gain_db"] = gain
        if trig == "release":
            z["rt_decay_db"] = f(r, "rt_decay", 0.0)
            vt = f(r, "amp_veltrack", 100.0)
            z["vel_db"] = sfz_vel_db(vt, vl, vh)
        if "loop_start" in r and r.get("loop_mode", "loop_continuous") != "no_loop":
            ls, le = int(r["loop_start"]), int(r["loop_end"]) + 1
            z["loop"] = {"start": ls, "end": le, "xfade": min(2048, (le - ls) // 4)}
        if trig == "attack" and f(r, "ampeg_release", 0.0) >= 4.0:
            undamped_from = min(undamped_from, lo)
        zones.append(z)
        if trig == "attack":
            attack.append(z)

    # Onsets: skip the silence before the hammer (not for looped zones, whose start is fixed),
    # keeping 3 ms before the -50 dB point.
    if cfg["trim_onset"]:
        for z in attack:
            if "loop" in z:
                continue
            x, sr = audio(z["path"])
            on = A.onset(x, sr, -50.0)
            s = max(0, on - int(0.003 * sr))
            if s > 0:
                z["start"] = s

    # ---- measurements -------------------------------------------------------------------
    report = {"instrument": cfg["id"], "samples": {}, "keys": {}}
    for z in zones:
        x, sr = audio(z["path"])
        on = A.onset(x, sr, -50.0)
        rep = {
            "frames": int(len(x)),
            "rate": int(sr),
            "peak_dbfs": round(A.peak_db(x), 2),
            "onset_ms": round(on / sr * 1000, 2),
            "end_dbfs": round(A.peak_db(x[-256:]), 1),
        }
        if z.get("trigger", "attack") == "attack":
            # From where playback starts (the trimmed start), as verify.py measures it.
            rep["loudness_db"] = round(A.loudness_db(x, sr, z.get("start", 0)), 2)
            fit = A.pitch_hz(x, sr, A.et_hz(z["root"]))
            rep["f0_hz"] = round(fit[0], 4)
            rep["cents"] = round(A.cents(fit[0], A.et_hz(z["root"])), 2)
            rep["inharmonicity_b"] = float(f"{fit[1]:.3g}")
            rep["partials"] = fit[2]
        report["samples"][z["path"]] = rep

    # Tuning: every sample is corrected by its own measurement (layers of one key can differ
    # by several cents, most in the treble, where the unison strings beat); the report keeps
    # the per-key median and the spread between layers.
    by_root = {}
    for z in attack:
        by_root.setdefault(z["root"], []).append(report["samples"][z["path"]]["cents"])
    for rk, cs in sorted(by_root.items()):
        report["keys"][str(rk)] = {
            "cents_recorded": round(float(np.median(cs)), 2),
            "layer_spread_cents": round(max(cs) - min(cs), 2),
        }
    for z in attack:
        z["tune_st"] = round(-report["samples"][z["path"]]["cents"] / 100.0, 4)

    # Velocity layers meet at the same loudness: each layer plays at its recorded loudness at
    # the centre of its velocity range, and the level follows a line between the centres of
    # adjacent layers (`vel_db` at the bottom, middle and top of the range), so a step between
    # velocities is at most the gap between two layers spread over the distance of their
    # centres. A layer that measured quieter than the one below counts as the level below plus
    # 0.2 dB. Adjacent layer: the zone whose velocity range ends (or starts) next to this one's
    # and whose keys include this zone's root (else the nearest root).
    def below(z):
        cands = [y for y in attack if y.get("vel_hi", 127) == z.get("vel_lo", 1) - 1]
        if not cands:
            return None
        inside = [y for y in cands if y["lo"] <= z["root"] <= y["hi"]]
        return min(inside or cands, key=lambda y: (abs(y["root"] - z["root"]), y["path"]))

    loud = {z["path"]: report["samples"][z["path"]]["loudness_db"] for z in attack}

    def above(z):
        cands = [y for y in attack if y.get("vel_lo", 1) == z.get("vel_hi", 127) + 1]
        if not cands:
            return None
        inside = [y for y in cands if y["lo"] <= z["root"] <= y["hi"]]
        return min(inside or cands, key=lambda y: (abs(y["root"] - z["root"]), y["path"]))

    def center(z):
        return (z.get("vel_lo", 1) + z.get("vel_hi", 127)) / 2

    tgt = {}
    for z in sorted(attack, key=lambda z: (z.get("vel_lo", 1), z["root"], z["path"])):
        bz = below(z)
        rec = loud[z["path"]]
        tgt[id(z)] = rec if bz is None else max(rec, tgt[id(bz)] + 0.2)

    def target(z, v):
        """Target loudness at velocity v: linear between the centres of adjacent layers; below
        the softest layer's centre the slope continues (at most 6 dB lower at velocity 1),
        above the loudest layer's centre it stays flat."""
        c = center(z)
        n = below(z) if v < c else above(z)
        if n is None:
            if v >= c:
                return tgt[id(z)]
            up = above(z)
            slope = 0.0 if up is None else (tgt[id(up)] - tgt[id(z)]) / (center(up) - c)
            return tgt[id(z)] - min(slope * (c - v), 6.0)
        cn = center(n)
        return tgt[id(z)] + (tgt[id(n)] - tgt[id(z)]) * (v - c) / (cn - c)

    # Keys with many layers (the grand's 16): one straight line in dB per key through the
    # layers' targets (least squares over their centres), so the level rises evenly (a few
    # tenths of a dB per velocity step) and a velocity curve can't pile steps up at narrow
    # layers. Each layer's gain then departs from its recorded loudness by the line's
    # distance (reported). Fewer layers: the centre-to-centre line above.
    columns = {}
    for z in attack:
        columns.setdefault((z["lo"], z["hi"], z["root"]), []).append(z)
    line = {}
    for zs in columns.values():
        if len(zs) >= 3:
            cs = np.array([center(z) for z in zs])
            ts = np.array([tgt[id(z)] for z in zs])
            slope, icpt = np.polyfit(cs, ts, 1)
            for z in zs:
                line[id(z)] = (float(slope), float(icpt))
    report["layer_gain_vs_recorded_db"] = {}
    for z in attack:
        vl, vh = z.get("vel_lo", 1), z.get("vel_hi", 127)
        rec = loud[z["path"]]
        if id(z) in line:
            slope, icpt = line[id(z)]
            pts = [round(slope * v + icpt - rec, 2) for v in (vl, vh)] if vh > vl else [
                round(slope * vl + icpt - rec, 2)]
            report["layer_gain_vs_recorded_db"][z["path"]] = round(
                slope * center(z) + icpt - rec, 2)
        else:
            pts = [round(target(z, v) - rec, 2) for v in (vl, (vl + vh) / 2, vh)] if vh > vl else [
                round(target(z, vl) - rec, 2)]
        if any(abs(p) > 0.01 for p in pts):
            z["vel_db"] = pts

    # ---- the archive ------------------------------------------------------------------------
    stem = f"{name}-v{MAJOR}"
    files = sorted({z["path"] for z in zones})
    notice = notice_text(cfg)
    members = [(p, os.path.join(root, p)) for p in files]
    members += [(t, os.path.join(root, t)) for t in up["texts"]]
    os.makedirs(out, exist_ok=True)
    tar_path = os.path.join(out, stem + ".tar")
    shas = {}
    with open(tar_path + ".part", "wb") as fh:
        with tarfile.open(fileobj=fh, mode="w", format=tarfile.USTAR_FORMAT) as t:
            entries = [(p, open(src, "rb").read()) for p, src in members]
            entries.append(("NOTICE.txt", notice.encode()))
            for p, data in sorted(entries):
                ti = tarfile.TarInfo(p)
                ti.size, ti.mtime, ti.mode = len(data), 0, 0o644
                ti.uid = ti.gid = 0
                ti.uname = ti.gname = ""
                t.addfile(ti, io.BytesIO(data))
                shas[p] = hashlib.sha256(data).hexdigest()
    os.replace(tar_path + ".part", tar_path)
    tar_sha = sha256_file(tar_path)
    size = os.path.getsize(tar_path)
    with open(tar_path + ".sha256", "w") as fh:
        fh.write(f"{tar_sha}  {stem}.tar\n")

    # ---- instrument.json ---------------------------------------------------------------------
    frames = sum(report["samples"][p]["frames"] for p in files)
    stereo_frames = frames  # every file is stereo
    data = {
        "vel_xfade": cfg["vel_xfade"],
        "max_per_key": cfg["max_per_key"],
        "undamped_from": undamped_from,
        "mips": False,
        "storage": "compact",
        "zones": zones,
    }
    if data["vel_xfade"] == 0:
        del data["vel_xfade"]
    manifest = {
        "id": cfg["id"],
        "name": cfg["name"],
        "description": cfg["description"],
        "device": "sampler@1",
        "tags": cfg["tags"],
        "license": cfg["license"],
        "license_url": cfg["license_url"],
        "license_note": cfg["license_note"],
        "author": cfg["author"],
        "source": cfg["source"],
        "upstream": {k: up[k] for k in ("url", "sha256", "size")} | {"sfz": up["sfz"]},
        "packaged_by": "scripts/instruments/package.sh " + name,
        "archive": {
            "file": stem + ".tar",
            "url": stem + ".tar",
            "sha256": tar_sha,
            "size": size,
        },
        "stats": {
            "files": len(shas),
            "zones": len(zones),
            "sample_seconds": round(stereo_frames / report["samples"][files[0]]["rate"], 1),
            "memory_mb_compact": round(frames * 2 * 2 / 1e6, 1),
            "recorded_tuning_cents": [
                round(min(v["cents_recorded"] for v in report["keys"].values()), 1),
                round(max(v["cents_recorded"] for v in report["keys"].values()), 1),
            ],
            "max_layer_spread_cents": round(
                max(v["layer_spread_cents"] for v in report["keys"].values()), 1
            ),
        },
        "files": dict(sorted(shas.items())),
        "data": data,
    }
    dest = os.path.join(REPO, "content", "instruments", name)
    os.makedirs(dest, exist_ok=True)
    with open(os.path.join(dest, "instrument.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)
        fh.write("\n")
    with open(os.path.join(out, name + "-report.json"), "w") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print(json.dumps({"archive": tar_path, "sha256": tar_sha, "size": size,
                      "manifest": os.path.join(dest, "instrument.json")}, indent=1))


def notice_text(cfg):
    return (
        f"{cfg['name']} ({cfg['id']}), packaged for daw by scripts/instruments/package.py.\n\n"
        f"Author: {cfg['author']}\nSource: {cfg['source']}\nUpstream archive: "
        f"{cfg['upstream']['url']}\n  sha256 {cfg['upstream']['sha256']}\n\n"
        f"Licence: {cfg['license']} ({cfg['license_url']})\n{cfg['license_note']}\n\n"
        "The samples/ files are the upstream FLAC files, unmodified. Tuning, level and "
        "mapping corrections live in daw's instrument.json, not in the audio.\n"
    )


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] not in INSTRUMENTS:
        sys.exit(f"usage: package.py {'|'.join(INSTRUMENTS)} WORK_DIR OUT_DIR")
    build(sys.argv[1], os.path.abspath(sys.argv[2]), os.path.abspath(sys.argv[3]))
