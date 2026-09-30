#!/usr/bin/env python3
"""Write daw's pack manifest (daw: content/irs/packs/real-rooms.json) from a built or
downloaded release folder: python3 manifest.py RELEASE_DIR TAG > real-rooms.json"""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
rel, tag = Path(sys.argv[1]), sys.argv[2]
rec = json.loads((HERE / "recipes.json").read_text())
meas = json.loads((rel / "measurements.json").read_text())
sums = dict(reversed(l.split("  ")) for l in (rel / "SHA256SUMS").read_text().splitlines())
files = []
for e in rec["irs"]:
    m = meas[e["file"]]
    f = {
        "file": e["file"], "sha256": sums[e["file"]], "size": (rel / e["file"]).stat().st_size,
        "name": e["name"], "description": e["description"],
        "space": e["space"], "size_class": e["size_class"],
        "rt60_s": m["rt60_s"], "edt_s": m["edt_s"], "length_s": m["len_s"],
        "channels": 1 if m["src_channels"] == 1 or "channels" in e else 2,
        "uses": e["uses"], "tags": e["tags"],
        "license": e["license"], "author": e["author"], "source": e["source"],
    }
    files.append(f)
licenses = sorted({f["license"] for f in files})
out = {
    "id": "irpack/real-rooms@1",
    "name": "Real rooms",
    "description": "Recorded impulse responses of real spaces for convolution@1: rooms, a studio live room, drum rooms, wood and marble halls, concert and chamber halls, a theatre, cathedral and churches, stairwells, an industrial warehouse and a concrete hall, a railway tunnel, a cave, outdoor spaces and a spring. 48 kHz 24-bit WAV, trimmed, DC-free, peak -1 dBFS, at most 10 s. Optional: install with `daw library install real-rooms`.",
    "tier": "optional",
    "release": f"https://github.com/Nullframe/daw-content/releases/tag/{tag}",
    "base_url": f"https://github.com/Nullframe/daw-content/releases/download/{tag}/",
    "notices": f"https://github.com/Nullframe/daw-content/releases/download/{tag}/NOTICES.md",
    "licenses": licenses,
    "attribution_required": [l for l in licenses if l.startswith("CC-BY")],
    "measured_with": "Schroeder backward integration of the channel mean after the noise-floor cut; rt60_s from the -5..-35 dB fit (T30, or T20 when the range is short), edt_s from 0..-10 dB. Per-octave RT60s and spectral balance are in the release's measurements.json.",
    "files": files,
}
print(json.dumps(out, indent=2, ensure_ascii=False))
