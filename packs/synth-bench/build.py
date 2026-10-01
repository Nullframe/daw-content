#!/usr/bin/env python3
"""Build the synthesis benchmark's reference sounds from the CC0 sources pinned in recipes.json.

    python3 build.py OUT --cache CACHE [--tag TAG] [--pin]

For every target in recipes.json it:

1. fetches the upstream file and checks its sha256 (`--pin` writes the sha256s it sees into
   recipes.json instead; use it once when adding a target):
   - `drums-recorded-cc0`: a WAV from that daw-content release;
   - `vcsl`, `vsco2`, `sonic-pi`: raw.githubusercontent.com at the pinned commit;
   - `kenney-*`: one member of the pack's zip (the zip's sha256 is pinned);
   - `fsd50k`: one clip range-read out of FSD50K's split zip on Zenodo (polite: >= 10 s
     between requests; the zip's CRC and the pinned sha256 are both checked);
   - `fundsp`, `open303`: a render of one of our own hand-written patches (`render/`), made
     here with that permissively licensed engine; the pinned sha256 checks that the render is
     byte-identical to the one reviewed. These targets are marked `synthetic`;
2. decodes it (mono stays mono, anything wider keeps its first two channels) at its own
   sample rate, removes a DC offset over 0.001;
3. trims from 5 ms before the onset (the first sample over peak + `onset_db`, default -40 dB)
   or from `start` seconds, to `seconds` or to where the sound falls under peak -70 dB,
   whichever comes first, with a 2 ms fade-in and a raised-cosine fade-out (20 ms when cut
   short, 5 ms otherwise);
4. scales it to a -1 dBFS sample peak and writes a 24-bit WAV.

Then it writes SHA256SUMS, targets.json (the manifest daw pins: id, category, kind, seconds,
sample rate, channels, sha256, source and licence per target, and `synthetic` for renders) and
NOTICES.md.

Deterministic: the same inputs and the pinned numpy/scipy/soundfile versions give the same bytes.
"""

import argparse
import hashlib
import io
import json
import os
import struct
import subprocess
import time
import urllib.parse
import zlib

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
UA = "Nullframe-synth-bench/1.0 (swag@users.noreply.github.com)"
PEAK_DBFS = -1.0


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def curl(url, rng=None):
    cmd = ["curl", "-sSfL", "--retry", "4", "--retry-all-errors", "--retry-delay", "11", "-A", UA]
    if rng:
        cmd += ["-r", f"{rng[0]}-{rng[1]}"]
    out = subprocess.run(cmd + [url], capture_output=True)
    if out.returncode != 0:
        raise RuntimeError(f"{url}: {out.stderr.decode().strip()}")
    return out.stdout


def cached(cache, key, fetch):
    path = os.path.join(cache, hashlib.sha256(key.encode()).hexdigest()[:24])
    if os.path.exists(path):
        return open(path, "rb").read()
    b = fetch()
    tmp = path + ".part"
    open(tmp, "wb").write(b)
    os.replace(tmp, path)
    return b


# FSD50K: range reads out of the split zip on Zenodo (after daw's recorded-cc0 pack scripts).
FSD_BASE = "https://zenodo.org/api/records/4060432/files/{}/content"
FSD_PART = 3221225472
FSD_DEV = ["FSD50K.dev_audio.z0%d" % i for i in range(1, 6)] + ["FSD50K.dev_audio.zip"]
FSD_DEV_LAST = 2306663327
_last = [0.0]


def fsd_range(name, start, end):
    wait = 10.5 - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()
    b = curl(FSD_BASE.format(name), (start, end))
    if len(b) != end - start + 1:
        raise RuntimeError(f"short read {len(b)} vs {end - start + 1}")
    return b


def fsd_read(a, n):
    res = b""
    while n > 0:
        i, off = a // FSD_PART, a % FSD_PART
        size = FSD_PART if i < len(FSD_DEV) - 1 else FSD_DEV_LAST
        k = min(n, size - off)
        res += fsd_range(FSD_DEV[i], off, off + k - 1)
        a, n = a + k, n - k
    return res


def fsd_central_dir(cache):
    path = os.path.join(cache, "fsd50k-dev-cd.json")
    if os.path.exists(path):
        return json.load(open(path))
    tail = fsd_range(FSD_DEV[-1], FSD_DEV_LAST - 65536, FSD_DEV_LAST - 1)
    j = tail.rfind(b"PK\x06\x06")
    (_, _, _, _, cd_disk, _, _, cd_size, cd_off) = struct.unpack("<QHHIIQQQQ", tail[j + 4:j + 56])
    cd = fsd_read(cd_disk * FSD_PART + cd_off, cd_size)
    ents, p = {}, 0
    while p < len(cd) and cd[p:p + 4] == b"PK\x01\x02":
        (_, _, _, meth, _, _, crc, csz, usz, nl, el, cl, dstart, _, _, lho) = struct.unpack(
            "<HHHHHHIIIHHHHHII", cd[p + 4:p + 46])
        name = cd[p + 46:p + 46 + nl].decode()
        extra = cd[p + 46 + nl:p + 46 + nl + el]
        q = 0
        while q < len(extra):
            hid, hsz = struct.unpack("<HH", extra[q:q + 4])
            body = extra[q + 4:q + 4 + hsz]
            if hid == 1:
                r = 0
                if usz == 0xFFFFFFFF:
                    usz = struct.unpack("<Q", body[r:r + 8])[0]; r += 8
                if csz == 0xFFFFFFFF:
                    csz = struct.unpack("<Q", body[r:r + 8])[0]; r += 8
                if lho == 0xFFFFFFFF:
                    lho = struct.unpack("<Q", body[r:r + 8])[0]; r += 8
                if dstart == 0xFFFF and r + 4 <= len(body):
                    dstart = struct.unpack("<I", body[r:r + 4])[0]
            q += 4 + hsz
        ents[name] = {"meth": meth, "csz": csz, "crc": crc, "disk": dstart, "lho": lho}
        p += 46 + nl + el + cl
    json.dump(ents, open(path, "w"))
    return ents


def fsd_clip(cache, clip_id):
    ent = fsd_central_dir(cache)[f"FSD50K.dev_audio/{clip_id}.wav"]
    a = ent["disk"] * FSD_PART + ent["lho"]
    blob = fsd_read(a, 30 + 1024 + ent["csz"])
    assert blob[:4] == b"PK\x03\x04", "bad local header"
    nl, el = struct.unpack("<HH", blob[26:30])
    data = blob[30 + nl + el:30 + nl + el + ent["csz"]]
    if len(data) < ent["csz"]:
        data += fsd_read(a + 30 + nl + el + len(data), ent["csz"] - len(data))
    if ent["meth"] == 8:
        data = zlib.decompress(data, -15)
    elif ent["meth"] != 0:
        raise RuntimeError("zip method %d" % ent["meth"])
    if zlib.crc32(data) & 0xFFFFFFFF != ent["crc"]:
        raise RuntimeError("crc mismatch")
    return data


# Renders (fundsp, Open303): built once per run from render/ and a pinned Open303 commit.
RENDER = os.path.join(HERE, "render")
_renderers = {}


def run(cmd, **kw):
    out = subprocess.run(cmd, capture_output=True, **kw)
    if out.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)}: {out.stderr.decode().strip()}")
    return out.stdout


def renderer(lib, info, cache):
    if lib in _renderers:
        return _renderers[lib]
    if lib == "fundsp":
        run(["cargo", "build", "--release", "--locked", "--quiet"], cwd=RENDER)
        exe = [os.path.join(RENDER, "target", "release", "synth-bench-render")]
    elif lib == "open303":
        src = os.path.join(cache, "open303-" + info["commit"])
        if not os.path.isdir(src):
            tmp = src + ".part"
            run(["rm", "-rf", tmp])
            run(["git", "init", "-q", tmp])
            run(["git", "-C", tmp, "fetch", "-q", "--depth", "1",
                 "https://github.com/%s" % info["repo"], info["commit"]])
            run(["git", "-C", tmp, "checkout", "-q", "FETCH_HEAD"])
            os.replace(tmp, src)
        head = run(["git", "-C", src, "rev-parse", "HEAD"]).decode().strip()
        if head != info["commit"]:
            raise RuntimeError(f"open303 at {head}, expected {info['commit']}")
        dsp = os.path.join(src, "Source", "DSPCode")
        exe = os.path.join(cache, "open303-acid-" + info["commit"][:12])
        obj = exe + "-fft4g.o"
        # Open303 is MIT; its headers miss two standard includes on current compilers.
        flags = ["-O2", "-ffp-contract=off", "-w"]
        run(["gcc"] + flags + ["-c", os.path.join(dsp, "fft4g.c"), "-o", obj])
        cpp = sorted(os.path.join(dsp, f) for f in os.listdir(dsp)
                     if f.startswith("rosic_") and f.endswith(".cpp"))
        run(["g++", "-std=c++17"] + flags + ["-include", "climits", "-include", "cstring",
             "-I", dsp, os.path.join(RENDER, "open303", "acid.cpp")] + cpp
            + [os.path.join(dsp, "GlobalFunctions.cpp"), obj, "-o", exe])
        exe = [exe]
    else:
        raise RuntimeError("unknown renderer " + lib)
    _renderers[lib] = exe
    return exe


def render(src, sources, cache):
    lib = src["lib"]
    exe = renderer(lib, sources[lib], cache)
    out = os.path.join(cache, "render-%s.wav" % src["patch"])
    run(exe + ([src["patch"], out] if lib == "fundsp" else [out]))
    b = open(out, "rb").read()
    os.remove(out)
    prov = {"engine": lib, "patch": src["patch"],
            "recipe": "packs/synth-bench/render (Nullframe/daw-content)"}
    for k in ("version", "repo", "commit"):
        if k in sources[lib]:
            prov[k] = sources[lib][k]
    return b, prov


def fetch(src, sources, cache):
    """The upstream file's bytes (and a provenance dict)."""
    lib = src["lib"]
    info = sources[lib]
    if lib in ("fundsp", "open303"):
        return render(src, sources, cache)
    if lib == "drums-recorded-cc0":
        b = cached(cache, src["url"], lambda: curl(src["url"]))
        return b, {"url": src["url"]}
    if "repo" in info:
        url = "https://raw.githubusercontent.com/%s/%s/%s" % (
            info["repo"], info["commit"], "/".join(
                urllib.parse.quote(p) for p in src["path"].split("/")))
        b = cached(cache, url, lambda: curl(url))
        return b, {"url": url, "repo": info["repo"], "commit": info["commit"], "path": src["path"]}
    if lib.startswith("kenney-"):
        import zipfile
        z = cached(cache, info["url"], lambda: curl(info["url"]))
        if "zip_sha256" in info and sha256(z) != info["zip_sha256"]:
            raise RuntimeError(f"{info['url']}: zip sha256 mismatch")
        info.setdefault("zip_sha256", sha256(z))
        b = zipfile.ZipFile(io.BytesIO(z)).read(src["member"])
        return b, {"url": info["url"], "member": src["member"]}
    if lib == "fsd50k":
        b = cached(cache, "fsd50k:" + src["id"], lambda: fsd_clip(cache, src["id"]))
        return b, {"dataset": info["record"], "clip": src["id"],
                   "freesound": "https://freesound.org/s/%s/" % src["id"]}
    raise RuntimeError("unknown source " + lib)


def process(x, sr, t):
    """Trim, fade and level one sound; returns float64 (frames, channels)."""
    x = x[:, :2]
    if np.all(np.abs(x - x[:, :1]) < 1e-9):
        x = x[:, :1]
    for c in range(x.shape[1]):
        m = float(np.mean(x[:, c]))
        if abs(m) > 0.001:
            x[:, c] -= m
    env = np.max(np.abs(x), axis=1)
    peak = float(env.max())
    if peak <= 0:
        raise RuntimeError("silent")
    if "start" in t:
        s0 = int(round(t["start"] * sr))
    else:
        thr = peak * 10 ** (t.get("onset_db", -40) / 20)
        s0 = max(0, int(np.argmax(env > thr)) - int(0.005 * sr))
    n_max = int(round(t["seconds"] * sr))
    y = x[s0:s0 + n_max].copy()
    # End where a 10 ms RMS stays under peak -70 dB.
    w = max(1, sr // 100)
    rms = np.sqrt(np.convolve(np.mean(y ** 2, axis=1), np.ones(w) / w, mode="same"))
    loud = np.nonzero(rms > peak * 10 ** (-70 / 20))[0]
    end = int(loud[-1]) + 1 if len(loud) else len(y)
    cut = end >= len(y) and s0 + n_max < len(x)
    y = y[:end]
    fi = int(0.002 * sr)
    y[:fi] *= (0.5 - 0.5 * np.cos(np.pi * np.arange(fi) / fi))[:, None]
    fo = min(len(y) // 4, int((0.020 if cut else 0.005) * sr))
    if fo > 0:
        y[-fo:] *= (0.5 + 0.5 * np.cos(np.pi * np.arange(fo) / fo))[:, None]
    y *= 10 ** (PEAK_DBFS / 20) / float(np.max(np.abs(y)))
    return y


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--cache", default=os.path.expanduser("~/.cache/synth-bench"))
    ap.add_argument("--tag", default="synth-bench-dev")
    ap.add_argument("--pin", action="store_true", help="write the sha256s seen into recipes.json")
    ap.add_argument("--only", nargs="*", help="build only these ids")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    os.makedirs(a.cache, exist_ok=True)
    rec = json.load(open(os.path.join(HERE, "recipes.json")))
    sources = rec["sources"]
    manifest = []
    for t in rec["targets"]:
        if a.only and t["id"] not in a.only:
            continue
        b, prov = fetch(t["source"], sources, a.cache)
        h = sha256(b)
        if a.pin:
            t["source"]["sha256"] = h
        elif t["source"].get("sha256") != h:
            raise SystemExit(f"{t['id']}: sha256 {h} does not match the pinned "
                             f"{t['source'].get('sha256')}")
        x, sr = sf.read(io.BytesIO(b), dtype="float64", always_2d=True)
        y = process(x, sr, t)
        name = t["id"] + ".wav"
        sf.write(os.path.join(a.out, name), y, sr, subtype="PCM_24", format="WAV")
        wav = open(os.path.join(a.out, name), "rb").read()
        lib = t["source"]["lib"]
        manifest.append({
            "id": t["id"], "category": t["category"], "kind": t["kind"],
            **({"synthetic": True} if t.get("synthetic") else {}),
            "description": t["description"],
            "file": name, "sha256": sha256(wav), "bytes": len(wav),
            "sample_rate": sr, "channels": int(y.shape[1]),
            "seconds": round(len(y) / sr, 3),
            "license": "CC0-1.0",
            "source": dict(prov, lib=lib, name=sources[lib]["name"],
                           author=sources[lib].get("author", ""),
                           upstream_sha256=h),
        })
        print(f"{t['id']:20s} {sr} {y.shape[1]}ch {len(y) / sr:5.2f}s", flush=True)
    if a.pin:
        json.dump(rec, open(os.path.join(HERE, "recipes.json"), "w"), indent=1)
        open(os.path.join(HERE, "recipes.json"), "a").write("\n")
    json.dump({"tag": a.tag, "targets": manifest}, open(os.path.join(a.out, "targets.json"), "w"),
              indent=1)
    with open(os.path.join(a.out, "SHA256SUMS"), "w") as f:
        for m in sorted(manifest, key=lambda m: m["file"]):
            f.write(f"{m['sha256']}  {m['file']}\n")
    with open(os.path.join(a.out, "NOTICES.md"), "w") as f:
        f.write("# Synthesis benchmark reference sounds: sources\n\n"
                "Every file is CC0-1.0 (public domain dedication). Credit is not required; the "
                "sources are credited anyway.\n\n")
        for k, s in sources.items():
            f.write(f"- **{s['name']}** ({s.get('author', '')}): {s['license']}, "
                    f"{s.get('license_url', s.get('page', ''))}\n")
        f.write("\nTargets marked `synthetic` are our own renders of hand-written patches "
                "(packs/synth-bench/render) made with the engine named in their `source`; the "
                "engines are permissively licensed and the renders are released as CC0-1.0.\n")
        f.write("\nPer file: see targets.json (`source`).\n")


if __name__ == "__main__":
    main()
