"""Build the sound-lab sources: fetch every CC0 / public-domain recording in sources.json from
its upstream, condition it the same way every time, and write OUT/src-<id>.flac plus
SHA256SUMS, provenance.json and NOTICES.md.

    python3 build.py OUT [--cache DIR]

Conditioning (pinned numpy / scipy / soundfile, so the bytes are reproducible):
- decode (WAV, OGG, MP3) to float, keeping the channel count;
- resample to 48 kHz with scipy's polyphase filter when the source rate differs;
- cut the excerpt (`excerpt_s`, whole seconds at 48 kHz) for long recordings;
- write 24-bit FLAC.

FSD50K clips are range-read out of the dataset's split zip on Zenodo (one request per clip,
10 s apart, per Zenodo's robots Crawl-delay), so nothing else of the archive is downloaded.
"""
import hashlib, json, os, struct, subprocess, sys, time, zipfile, zlib
from fractions import Fraction

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

HERE = os.path.dirname(os.path.abspath(__file__))
UA = "Nullframe-daw-content/1.0 (sound-lab build; https://github.com/Nullframe/daw-content)"
ZENODO = "https://zenodo.org/api/records/4060432/files/{}/content"
PART = 3221225472
FSD = {
    "eval": {"parts": ["FSD50K.eval_audio.z01", "FSD50K.eval_audio.zip"], "last_size": 3037675767},
    "dev": {"parts": ["FSD50K.dev_audio.z0%d" % i for i in range(1, 6)] + ["FSD50K.dev_audio.zip"], "last_size": 2306663327},
}
_last = [0.0]


def curl(url, rng=None):
    args = ["curl", "-sSfL", "--retry", "3", "--retry-all-errors", "--retry-delay", "11", "-A", UA]
    if rng:
        args += ["-r", rng]
    out = subprocess.run(args + [url], capture_output=True)
    if out.returncode != 0:
        raise RuntimeError(f"{url}: {out.stderr.decode().strip()}")
    return out.stdout


def zenodo(name, start, end):
    wait = 10.5 - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()
    b = curl(ZENODO.format(name), f"{start}-{end}")
    if len(b) != end - start + 1:
        raise RuntimeError(f"short read from {name}")
    return b


def fsd_clip(f):
    """One clip out of the split zip: local header + data in one ranged request."""
    e, parts = f["zip_entry"], FSD[f["set"]]["parts"]
    a = e["disk"] * PART + e["lho"]
    i, off = a // PART, a % PART
    size = FSD[f["set"]]["last_size"] if i == len(parts) - 1 else PART
    blob = zenodo(parts[i], off, min(off + 30 + 2048 + e["csz"], size) - 1)
    assert blob[:4] == b"PK\x03\x04", "bad local header"
    nl, el = struct.unpack("<HH", blob[26:30])
    data = blob[30 + nl + el:30 + nl + el + e["csz"]]
    if len(data) < e["csz"]:  # crosses into the next part (rare)
        rest = e["csz"] - len(data)
        data += zenodo(parts[i + 1], 0, rest - 1)
    if e["meth"] == 8:
        data = zlib.decompress(data, -15)
    if zlib.crc32(data) & 0xFFFFFFFF != e["crc"]:
        raise RuntimeError(f"crc mismatch for FSD50K clip {f['clip']}")
    return data


def fetch(src, cache):
    f = src["fetch"]
    key = hashlib.sha256(json.dumps(f, sort_keys=True).encode()).hexdigest()[:16]
    ext = {"fsd50k": ".wav"}.get(f["kind"]) or os.path.splitext(f.get("member") or f["url"])[1].lower()
    path = os.path.join(cache, key + ext)
    if os.path.exists(path):
        return path
    if f["kind"] == "fsd50k":
        data = fsd_clip(f)
    elif f["kind"] == "url":
        data = curl(f["url"])
    elif f["kind"] == "zip":
        zpath = os.path.join(cache, hashlib.sha256(f["url"].encode()).hexdigest()[:16] + ".zip")
        if not os.path.exists(zpath):
            open(zpath, "wb").write(curl(f["url"]))
        data = zipfile.ZipFile(zpath).read(f["member"])
    else:
        raise ValueError(f["kind"])
    open(path, "wb").write(data)
    return path


def condition(path, sr_out, excerpt):
    # From a file with its extension: libsndfile detects MP3 by name when a tag precedes it.
    x, sr = sf.read(path, dtype="float64", always_2d=True)
    if sr != sr_out:
        r = Fraction(sr_out, sr)
        x = resample_poly(x, r.numerator, r.denominator, axis=0)
    if excerpt:
        a, b = excerpt
        x = x[a * sr_out:b * sr_out]
    return np.clip(x, -1.0, 1.0 - 2 ** -23)


def main():
    out = sys.argv[1]
    cache = sys.argv[sys.argv.index("--cache") + 1] if "--cache" in sys.argv else os.path.join(out, ".cache")
    os.makedirs(out, exist_ok=True)
    os.makedirs(cache, exist_ok=True)
    spec = json.load(open(os.path.join(HERE, "sources.json")))
    prov = {"tag": spec["tag"], "sources": {}}
    for s in spec["sources"]:
        x = condition(fetch(s, cache), spec["sample_rate"], s.get("excerpt_s"))
        p = os.path.join(out, s["file"])
        sf.write(p, x, spec["sample_rate"], subtype="PCM_24", format="FLAC")
        h = hashlib.sha256(open(p, "rb").read()).hexdigest()
        prov["sources"][s["file"]] = {k: s[k] for k in ("title", "author", "license", "license_url", "source", "source_url", "excerpt_s", "dataset_url") if k in s} | {
            "sha256": h, "size": os.path.getsize(p), "channels": x.shape[1], "duration_s": round(len(x) / spec["sample_rate"], 3)}
        print(s["file"], h, flush=True)
    json.dump(prov, open(os.path.join(out, "provenance.json"), "w"), indent=1)
    lines = [f"# {spec['tag']}: notices", "",
             "Source recordings for daw's sound-lab pack (content/packs/sound-lab in Nullframe/daw), fetched from their upstreams and conditioned by packs/sound-lab/build.py.", "",
             "- **CC0-1.0** (https://creativecommons.org/publicdomain/zero/1.0/): FSD50K clips whose Freesound licence is CC0 (Fonseca et al., FSD50K, Zenodo record 4060432; each clip's Freesound page is listed) and Kenney audio packs (www.kenney.nl).",
             "- **Public domain**: US National Park Service sound gallery recordings (works of the US federal government).",
             "- Attribution is not required; it is given here as a courtesy.", "",
             "| File | Title | Author | Licence | Source |", "|---|---|---|---|---|"]
    for f, v in sorted(prov["sources"].items()):
        lines.append(f"| {f} | {v['title'].replace('|', '/')} | {v['author']} | {v['license']} | {v['source_url']} |")
    open(os.path.join(out, "NOTICES.md"), "w").write("\n".join(lines) + "\n")
    with open(os.path.join(out, "SHA256SUMS"), "w") as f:
        for n in sorted(os.listdir(out)):
            p = os.path.join(out, n)
            if n == "SHA256SUMS" or os.path.isdir(p):
                continue
            f.write(f"{hashlib.sha256(open(p, 'rb').read()).hexdigest()}  {n}\n")


if __name__ == "__main__":
    main()
