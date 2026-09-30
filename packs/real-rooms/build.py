#!/usr/bin/env python3
"""Build the real-rooms IR pack from its upstream sources.

    python3 build.py OUT_DIR [--cache DIR] [--only NAME]

For every entry in recipes.json: download the upstream file (a WAV, or one member of a zip,
read with HTTP range requests so multi-GB archives are not fetched whole), then condition it
with irtools.prepare (DC removal, 48 kHz, onset trim, noise-floor tail cut, -1 dBFS peak,
24-bit WAV) and measure it (RT60 from T30, EDT, octave RT60, spectral balance). Writes the
WAVs, SHA256SUMS, measurements.json, provenance.json and NOTICES.md into OUT_DIR.
Requires numpy, scipy, soundfile. Deterministic for a given numpy/scipy/libsndfile.
"""
import hashlib, io, json, os, sys, time, urllib.request, zipfile
from pathlib import Path
import irtools

HERE = Path(__file__).resolve().parent
UA = {"User-Agent": "daw-content real-rooms pack builder (+https://github.com/Nullframe/daw-content)"}


def get(url, headers=None, tries=5):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={**UA, **(headers or {})})
            with urllib.request.urlopen(req, timeout=180) as r:
                return r.read(), r.headers
        except Exception as e:  # network hiccups: back off and retry
            if i == tries - 1:
                raise
            time.sleep(2 ** i)


class RangeFile(io.RawIOBase):
    """A seekable read-only view of a remote file through HTTP range requests."""

    def __init__(self, url):
        self.url, self.pos = url, 0
        _, h = get(url, {"Range": "bytes=0-0"})
        self.size = int(h["Content-Range"].split("/")[1])

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos

    def readinto(self, b):
        if self.pos >= self.size:
            return 0
        end = min(self.size, self.pos + len(b)) - 1
        data, _ = get(self.url, {"Range": f"bytes={self.pos}-{end}"})
        b[: len(data)] = data
        self.pos += len(data)
        return len(data)


def fetch(entry, cache):
    key = hashlib.sha256((entry["url"] + entry.get("member", "")).encode()).hexdigest()[:16]
    dst = cache / f"{key}-{Path(entry.get('member') or entry['url'].split('?')[0]).name}"
    if dst.is_file():
        return dst
    if "member" in entry:
        if "audb-public" in entry["url"]:  # small single-file zips: fetch whole
            data, _ = get(entry["url"])
            z = zipfile.ZipFile(io.BytesIO(data))
        else:
            z = zipfile.ZipFile(io.BufferedReader(RangeFile(entry["url"]), buffer_size=1 << 20))
        names = [n for n in z.namelist() if n.endswith(entry["member"])]
        if len(names) != 1:
            raise SystemExit(f"{entry['file']}: member {entry['member']} not found uniquely")
        data = z.read(names[0])
    else:
        data, _ = get(entry["url"])
    tmp = dst.with_suffix(".part")
    tmp.write_bytes(data)
    tmp.rename(dst)
    return dst


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    args = sys.argv[1:]
    out = Path(args[0])
    cache = Path(args[args.index("--cache") + 1]) if "--cache" in args else out / ".cache"
    only = args[args.index("--only") + 1] if "--only" in args else None
    out.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    recipes = json.loads((HERE / "recipes.json").read_text())
    meas, prov = {}, []
    for e in recipes["irs"]:
        if only and only not in e["file"]:
            continue
        src = fetch(e, cache)
        rep = irtools.prepare(src, out / e["file"], channels=e.get("channels"))
        rep["source_sha256"] = sha256(src)
        meas[e["file"]] = rep
        print(f"{e['file']:34s} rt60 {rep['rt60_s']:5.2f}  edt {rep['edt_s']:5.2f}  "
              f"len {rep['len_s']:5.2f}s  nf {rep['noise_floor_db']:6.1f} dB  clip {rep['clipped_samples']}/{rep['max_clip_run']}  dc {rep['dc_before']:.1e}",
              flush=True)
        prov.append({k: e[k] for k in e if k not in ("uses", "tags", "description")}
                    | {"source_file_sha256": rep["source_sha256"],
                       "processing": "DC removed (mean + 10 Hz high-pass), channels "
                       + (f"{e['channels']} (B-format W)" if "channels" in e else "as recorded")
                       + ", resampled to 48 kHz, onset trimmed to 0.5 ms before the direct sound, "
                       "tail cut at the noise floor with a 100 ms fade, peak normalised to -1 dBFS, 24-bit WAV"})
    (out / "measurements.json").write_text(json.dumps(meas, indent=1))
    (out / "provenance.json").write_text(json.dumps(prov, indent=1))
    wavs = sorted(p.name for p in out.glob("*.wav"))
    (out / "SHA256SUMS").write_text("".join(f"{sha256(out / w)}  {w}\n" for w in wavs))


if __name__ == "__main__":
    main()
