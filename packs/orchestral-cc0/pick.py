"""Pick the samples of the orchestral CC0 pack from local checkouts of VSCO 2 CE and VCSL and
write recipes.json (every upstream file with its sha256, sounding root note, velocity layer and
round robin). build.py then rebuilds the pack from recipes.json alone.

    python3 pick.py --vsco PATH --vcsl PATH

The checkouts must be at the commits pinned in SOURCES (pick.py checks). File names give the
note, the dynamic and the round robin; the sounding note is checked against the recording
(the strongest odd-harmonic series near the named note, then a partial fit), because both
libraries name most folders one octave below the sounding pitch (VSCO's "C4" sounds C5).
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

import numpy as np
import soundfile as sf

import analysis as A

SOURCES = {
    "vsco": {
        "repo": "sgossner/VSCO-2-CE",
        "commit": "440300901dfe9275fd84e0b7763af1f8443ae62e",
        "name": "VS Chamber Orchestra: Community Edition (VSCO 2 CE)",
        "author": "Versilian Studios LLC (Sam Gossner) and Ivy Audio (Simon Dalzell); sample cutting by Elan Hickler (Soundemote)",
        "license": "CC0-1.0",
        "license_url": "https://github.com/sgossner/VSCO-2-CE/blob/440300901dfe9275fd84e0b7763af1f8443ae62e/LICENSE",
        "page": "http://vis.versilstudios.net/vsco-community.html",
        "texts": ["LICENSE", "Readme.txt", "README.md"],
    },
    "vcsl": {
        "repo": "sgossner/VCSL",
        "commit": "c1ea7bcc3c7309650ab0da9d15c9cd1fbc4a4c7e",
        "name": "Versilian Community Sample Library (VCSL)",
        "author": "Versilian Studios LLC (Sam Gossner) and contributors",
        "license": "CC0-1.0",
        "license_url": "https://github.com/sgossner/VCSL/blob/c1ea7bcc3c7309650ab0da9d15c9cd1fbc4a4c7e/LICENSE",
        "page": "https://versilian-studios.com/vcsl/",
        "texts": ["LICENSE", "README.md"],
    },
}

S = "Idiophones/Struck Idiophones/"

# name, instrument, family, kind, lib, folders, octave shift (sounding = named + shift),
# layer order (dynamic tokens, softest first; layers not listed are dropped), extra file filter.
# kind: sustain (looped, long notes), short (spiccato, staccato, pizzicato), pluck and mallet
# (let ring), perc (one-shots on keys).
V2 = ["v1", "v2"]
ARTICULATIONS = [
    # Strings: VSCO's violin, viola and cello sections and its solo double bass.
    ("violins-sustain", "Violin section, sustain with vibrato", "strings", "sustain", "vsco", ["Strings/Violin Section/susVib"], 12, V2, None),
    ("violins-spiccato", "Violin section, spiccato", "strings", "short", "vsco", ["Strings/Violin Section/Spic"], 12, V2, None),
    ("violins-pizzicato", "Violin section, pizzicato", "strings", "pluck", "vsco", ["Strings/Violin Section/Pizz"], 12, V2, None),
    ("violins-tremolo", "Violin section, tremolo", "strings", "sustain", "vsco", ["Strings/Violin Section/Trem"], 12, V2, None),
    ("violas-sustain", "Viola section, sustain with vibrato", "strings", "sustain", "vsco", ["Strings/Viola Section/susvib"], 12, V2, None),
    ("violas-spiccato", "Viola section, spiccato", "strings", "short", "vsco", ["Strings/Viola Section/spic"], 12, V2, None),
    ("violas-pizzicato", "Viola section, pizzicato", "strings", "pluck", "vsco", ["Strings/Viola Section/pizz"], 12, V2, None),
    ("violas-tremolo", "Viola section, tremolo", "strings", "sustain", "vsco", ["Strings/Viola Section/trem"], 12, V2, None),
    ("celli-sustain", "Cello section, sustain with vibrato", "strings", "sustain", "vsco", ["Strings/Cello Section/susvib"], 12, ["v1", "v3"], None),
    ("celli-spiccato", "Cello section, spiccato", "strings", "short", "vsco", ["Strings/Cello Section/spic"], 12, V2, None),
    ("celli-pizzicato", "Cello section, pizzicato", "strings", "pluck", "vsco", ["Strings/Cello Section/pizzT"], 12, V2, None),
    ("celli-tremolo", "Cello section, tremolo", "strings", "sustain", "vsco", ["Strings/Cello Section/trem"], 12, V2, None),
    ("basses-sustain", "Double bass (solo), sustain with vibrato", "strings", "sustain", "vsco", ["Strings/Solo Contrabass/SusVib"], 12, ["v1", "v3"], None),
    ("basses-spiccato", "Double bass (solo), spiccato", "strings", "short", "vsco", ["Strings/Solo Contrabass/Spic"], 12, ["v1", "v3"], None),
    ("basses-pizzicato", "Double bass (solo), pizzicato", "strings", "pluck", "vsco", ["Strings/Solo Contrabass/Pizz"], 12, ["v1", "v3"], None),
    ("basses-tremolo", "Double bass (solo), tremolo", "strings", "sustain", "vsco", ["Strings/Solo Contrabass/Trem"], 12, V2, None),
    ("violin-solo-sustain", "Solo violin, sustain with vibrato", "strings", "sustain", "vsco", ["Strings/Solo Violin/Arco Vib"], 0, ["p", "f"], None),
    ("violin-solo-spiccato", "Solo violin, spiccato", "strings", "short", "vsco", ["Strings/Solo Violin/spic"], 12, V2, None),
    ("violin-solo-pizzicato", "Solo violin, pizzicato", "strings", "pluck", "vsco", ["Strings/Solo Violin/Pizz"], 0, ["p", "f"], None),
    ("violin-solo-tremolo", "Solo violin, tremolo", "strings", "sustain", "vsco", ["Strings/Solo Violin/Trem"], 12, V2, None),
    # Brass (solo players).
    ("horn-sustain", "French horn, sustain", "brass", "sustain", "vsco", ["Brass/F Horn/sus"], 12, ["v1", "v2", "v3"], None),
    ("horn-staccato", "French horn, staccato", "brass", "short", "vsco", ["Brass/F Horn/stac"], 12, ["v1", "v2", "v3"], None),
    ("horn-muted", "French horn, muted sustain", "brass", "sustain", "vsco", ["Brass/F Horn/mute"], 12, ["v1", "v2"], None),
    ("trumpet-sustain", "Trumpet, sustain", "brass", "sustain", "vsco", ["Brass/Trumpet/sus"], 12, ["v1", "v3"], None),
    ("trumpet-muted", "Trumpet, straight mute sustain", "brass", "sustain", "vsco", ["Brass/Trumpet/straightM-sus"], 12, ["v1", "v3"], None),
    ("trumpet-staccato", "Trumpet, staccato", "brass", "short", "vsco", ["Brass/Trumpet/stac"], 12, ["v1", "v2", "v3"], None),
    ("trombone-sustain", "Tenor trombone, sustain", "brass", "sustain", "vsco", ["Brass/Tenor Trombone/sus"], 12, ["v1", "v2", "v3"], None),
    ("trombone-staccato", "Tenor trombone, staccato", "brass", "short", "vsco", ["Brass/Tenor Trombone/stac"], 12, ["v1", "v2", "v3", "v4"], None),
    ("tuba-sustain", "Tuba, sustain", "brass", "sustain", "vsco", ["Brass/Tuba/sus"], 12, ["v1", "v2", "v3"], None),
    ("tuba-staccato", "Tuba, staccato", "brass", "short", "vsco", ["Brass/Tuba/stac"], 12, V2, None),
    # Woodwinds (solo players).
    ("flute-sustain", "Flute, sustain with vibrato", "winds", "sustain", "vsco", ["Woodwinds/Flute/susvib"], 12, ["v1"], None),
    ("flute-sustain-nv", "Flute, sustain without vibrato", "winds", "sustain", "vsco", ["Woodwinds/Flute/susNV"], 12, ["v1", "v3"], None),
    ("flute-staccato", "Flute, staccato", "winds", "short", "vsco", ["Woodwinds/Flute/stac"], 12, ["v1", "v2", "v3"], None),
    ("oboe-sustain", "Oboe, sustain with vibrato", "winds", "sustain", "vsco", ["Woodwinds/Oboe/Vib"], 12, ["v1", "v3"], None),
    ("oboe-sustain-nv", "Oboe, sustain without vibrato", "winds", "sustain", "vsco", ["Woodwinds/Oboe/Sus"], 12, ["v1", "v3"], None),
    ("oboe-staccato", "Oboe, staccato", "winds", "short", "vsco", ["Woodwinds/Oboe/Stacc"], 12, ["v1", "v2", "v3"], None),
    ("clarinet-sustain", "Clarinet, sustain", "winds", "sustain", "vsco", ["Woodwinds/Clarinet/susLong"], 12, ["v1", "v2", "v3"], None),
    ("clarinet-staccato", "Clarinet, staccato", "winds", "short", "vsco", ["Woodwinds/Clarinet/stac"], 12, ["v1", "v2", "v3"], None),
    ("bassoon-sustain", "Bassoon, sustain", "winds", "sustain", "vsco", ["Woodwinds/Bassoon/sus"], 12, V2, None),
    ("bassoon-staccato", "Bassoon, staccato", "winds", "short", "vsco", ["Woodwinds/Bassoon/stac"], 12, V2, None),
    # Harp and mallets (VCSL).
    ("harp", "Concert harp", "harp", "pluck", "vcsl", ["Chordophones/Composite Chordophones/Concert Harp"], 0, ["p1|mp1|mf1|mf3", "f1|f2"], None),
    ("glockenspiel", "Glockenspiel", "mallets", "mallet", "vcsl", [S + "Glockenspiel"], 12, ["soft", "medium", "loud"], None),
    ("xylophone", "Xylophone, hard mallets", "mallets", "mallet", "vcsl", [S + "Xylophone/Hard Mallets"], 12, ["pp", "ff"], None),
    ("marimba", "Marimba", "mallets", "mallet", "vcsl", [S + "Marimba"], 12, ["soft", "med", "loud"], None),
    ("vibraphone", "Vibraphone, soft then hard mallets", "mallets", "mallet", "vcsl", [S + "Vibraphone/Soft Mallets", S + "Vibraphone/Hard Mallets"], 12, ["soft:v1", "soft:v2", "hard:v2", "hard:v3"], None),
    ("vibraphone-bowed", "Vibraphone, bowed", "mallets", "sustain", "vcsl", [S + "Vibraphone/Bowed"], 12, [""], None),
    ("tubular-bells", "Tubular bells", "mallets", "mallet", "vcsl", [S + "Tubular Bells 2"], 0, ["v2", "v4"], None),
]

# Unpitched orchestral colours that drums-recorded-cc0 does not have, one per key (C4 up).
PERC = [
    ("mark-tree-up", S + "Mark Trees/Legacy/windchimes_asc1.wav"),
    ("mark-tree-down", S + "Mark Trees/Legacy/windchimes_desc1.wav"),
    ("mark-tree-up-slow", S + "Mark Trees/Legacy/windchimes_slowAsc1.wav"),
    ("mark-tree-down-slow", S + "Mark Trees/Legacy/windchimes_slowDesc1.wav"),
    ("mark-tree-up-fast", S + "Mark Trees/Legacy/windchimes_fastAsc1.wav"),
    ("mark-tree-random", S + "Mark Trees/Legacy/windchimes_random.wav"),
    ("bell-tree-1", S + "Bell Tree/Stroke/BellTree_Stroke_1_Mid.wav"),
    ("bell-tree-3", S + "Bell Tree/Stroke/BellTree_Stroke_3_Mid.wav"),
    ("bell-tree-4", S + "Bell Tree/Stroke/BellTree_Stroke_4_Mid.wav"),
    ("bell-tree-6", S + "Bell Tree/Stroke/BellTree_Stroke_6_Mid.wav"),
    ("bell-tree-10", S + "Bell Tree/Stroke/BellTree_Stroke_10_Mid.wav"),
    ("sleigh-bells-hit", S + "Sleigh Bells/Sleighbells_Hit_rr1_Mid.wav"),
    ("sleigh-bells-hit-2", S + "Sleigh Bells/Sleighbells_Hit_rr2_Mid.wav"),
    ("sleigh-bells-shake", S + "Sleigh Bells/sleighbell1_shake1.wav"),
    ("sleigh-bells-shake-2", S + "Sleigh Bells/sleighbell2_shake1.wav"),
    ("sleigh-bells-loud", S + "Sleigh Bells/sleighbell2_hit_loud.wav"),
    ("finger-cymbals", S + "Finger Cymbals/Fing_Cymb.wav"),
    ("ratchet-crank", S + "Ratchet/Ratchet1_Crank_rr1_Mid.wav"),
    ("ratchet-fast", S + "Ratchet/Ratchet1_Fast_rr1_Mid.wav"),
    ("ratchet-slow", S + "Ratchet/Ratchet1_Slow_rr1_Mid.wav"),
    ("ratchet-2-crank", S + "Ratchet/Ratchet2_Crank_v1_rr1_Mid.wav"),
    ("ratchet-2-fast", S + "Ratchet/Ratchet2_Fast_rr1_Mid.wav"),
    ("ratchet-2-slow", S + "Ratchet/Ratchet2_Slow_rr1_Mid.wav"),
]
PERC_FIRST_KEY = 60

# Sections played from one track: each articulation over a key range (MIDI, inclusive).
# Splits sit where the higher section takes over (its lowest notes are its weakest).
ENSEMBLES = [
    ("strings-sustain", "String section (basses, celli, violas, violins), sustain", [("basses-sustain", 0, 40), ("celli-sustain", 41, 54), ("violas-sustain", 55, 64), ("violins-sustain", 65, 127)]),
    ("strings-spiccato", "String section, spiccato", [("basses-spiccato", 0, 40), ("celli-spiccato", 41, 54), ("violas-spiccato", 55, 64), ("violins-spiccato", 65, 127)]),
    ("strings-pizzicato", "String section, pizzicato", [("basses-pizzicato", 0, 40), ("celli-pizzicato", 41, 54), ("violas-pizzicato", 55, 64), ("violins-pizzicato", 65, 127)]),
    ("strings-tremolo", "String section, tremolo", [("basses-tremolo", 0, 40), ("celli-tremolo", 41, 54), ("violas-tremolo", 55, 64), ("violins-tremolo", 65, 127)]),
    ("brass-sustain", "Brass (tuba, trombone, horn, trumpet), sustain", [("tuba-sustain", 0, 45), ("trombone-sustain", 46, 55), ("horn-sustain", 56, 67), ("trumpet-sustain", 68, 127)]),
    ("brass-staccato", "Brass, staccato", [("tuba-staccato", 0, 45), ("trombone-staccato", 46, 55), ("horn-staccato", 56, 67), ("trumpet-staccato", 68, 127)]),
    ("winds-sustain", "Woodwinds (bassoon, clarinet, oboe, flute), sustain", [("bassoon-sustain", 0, 52), ("clarinet-sustain", 53, 64), ("oboe-sustain", 65, 74), ("flute-sustain", 75, 127)]),
    ("winds-staccato", "Woodwinds, staccato", [("bassoon-staccato", 0, 52), ("clarinet-staccato", 53, 64), ("oboe-staccato", 65, 74), ("flute-staccato", 75, 127)]),
]

NOTES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def note_of(tok):
    m = re.fullmatch(r"([A-G])(#|b)?(-?\d)", tok)
    if not m:
        return None
    return 12 * (int(m[3]) + 1) + NOTES[m[1]] + (1 if m[2] == "#" else -1 if m[2] == "b" else 0)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def mag_at(spec, df, f, c=40):
    lo, hi = int(f * 2 ** (-c / 1200) / df), int(np.ceil(f * 2 ** (c / 1200) / df)) + 1
    return float(spec[lo:hi].max()) if hi < len(spec) else 0.0


def odd_db(spec, df, f):
    """Energy at odd multiples of f over even ones: far below 0 dB when f is half the pitch."""
    o = sum(mag_at(spec, df, (2 * k - 1) * f) ** 2 for k in range(1, 5))
    e = sum(mag_at(spec, df, 2 * k * f) ** 2 for k in range(1, 5))
    return 10 * np.log10((o + 1e-20) / (e + 1e-20))


def measure(path, named):
    """(cents of the measured pitch from `named`, odd-harmonic check of `named` in dB, and of
    the octave below)."""
    x, sr = sf.read(path, dtype="float32", always_2d=True)
    spec, df = A._spectrum(x, sr, 0.05, 1.0)
    fit = A.f0_fit(x, sr, A.et_hz(named), t0=0.05, dur=1.0, search_cents=80)
    c = A.cents(fit[0], A.et_hz(named)) if fit else None
    return c, odd_db(spec, df, A.et_hz(named)), odd_db(spec, df, A.et_hz(named - 12))


def layer_rr(base, layers, sub):
    toks = re.split(r"[_\s]", base)
    lay = None
    for i, name in enumerate(layers):
        want = name.split(":")[-1].split("|")
        if (":" not in name or name.split(":")[0] == sub) and any(w in toks for w in want):
            lay = i + 1
    if layers == [""]:
        lay = 1
    rr = 1
    for t in toks:
        m = re.fullmatch(r"(?i)rr(\d+)", t)
        if m:
            rr = int(m[1])
    # VSCO sustains number their takes `_1`, `_2` after the dynamic.
    if len(toks) >= 2 and re.fullmatch(r"v\d", toks[-2]) and re.fullmatch(r"\d", toks[-1]):
        rr = int(toks[-1])
    return lay, rr


def git_head(path):
    return subprocess.run(["git", "-C", path, "rev-parse", "HEAD"], capture_output=True, text=True,
                          check=True).stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vsco", required=True)
    ap.add_argument("--vcsl", required=True)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "recipes.json"))
    a = ap.parse_args()
    roots = {"vsco": a.vsco, "vcsl": a.vcsl}
    for k, p in roots.items():
        if git_head(p) != SOURCES[k]["commit"]:
            sys.exit(f"{p} is not at {SOURCES[k]['commit']}")
    arts, flagged = [], []
    for name, inst, family, kind, lib, folders, shift, layers, _ in ARTICULATIONS:
        samples = []
        for folder in folders:
            sub = "soft" if "Soft" in folder else "hard" if "Hard" in folder else ""
            for fn in sorted(os.listdir(os.path.join(roots[lib], folder))):
                if not fn.lower().endswith(".wav"):
                    continue
                base = fn[:-4]
                named = next((note_of(t) for t in re.split(r"[_\s]", base) if note_of(t) is not None), None)
                lay, rr = layer_rr(base, layers, sub)
                if named is None or lay is None:
                    continue
                path = os.path.join(roots[lib], folder, fn)
                root = named + shift
                cents, odd, odd_below = measure(path, root)
                note = {"path": f"{folder}/{fn}", "sha256": sha256(path), "root": root,
                        "layer": lay, "rr": rr, "named": named}
                if family != "mallets" or name in ("glockenspiel", "xylophone", "marimba", "vibraphone"):
                    if cents is not None and abs(cents) > 50:
                        # Recorded for review only: such readings sit at the edge of the search
                        # (a weak or noisy fundamental); build.py retunes only within 40 cents.
                        flagged.append(f"{name}: {fn} reads {cents:+.0f} cents from {root}")
                samples.append(note)
        # Re-number round robins densely per (root, layer).
        groups = {}
        for s in sorted(samples, key=lambda s: (s["root"], s["layer"], s["rr"], s["path"])):
            groups.setdefault((s["root"], s["layer"]), []).append(s)
        for g in groups.values():
            for i, s in enumerate(g):
                s["rr"] = i + 1
        arts.append({"name": name, "instrument": inst, "family": family, "kind": kind, "lib": lib,
                     "layers": len(layers), "samples": samples})
        print(f"{name}: {len(samples)} samples", file=sys.stderr)
    perc = []
    for i, (pname, path) in enumerate(PERC):
        perc.append({"name": pname, "path": path, "sha256": sha256(os.path.join(roots["vcsl"], path)),
                     "root": PERC_FIRST_KEY + i, "layer": 1, "rr": 1})
    arts.append({"name": "orchestral-percussion", "instrument": "Mark tree, bell tree, sleigh bells, finger cymbals, ratchets (one per key from C4)",
                 "family": "percussion", "kind": "perc", "lib": "vcsl", "layers": 1, "samples": perc})
    doc = {
        "note": "Written by pick.py; build.py rebuilds the pack from this file alone. root: the sounding MIDI note (checked against the recording); layer: velocity layer (1 = softest); rr: round robin.",
        "sources": {k: {kk: vv for kk, vv in v.items()} for k, v in SOURCES.items()},
        "articulations": arts,
        "ensembles": [{"name": n, "instrument": d, "parts": [{"articulation": p, "lo": lo, "hi": hi} for p, lo, hi in parts]}
                      for n, d, parts in ENSEMBLES],
        "flagged": flagged,
    }
    with open(a.out, "w") as fh:
        json.dump(doc, fh, indent=1)
        fh.write("\n")
    print(f"{sum(len(x['samples']) for x in arts)} samples; {len(flagged)} pitch readings to review", file=sys.stderr)
    for f in flagged:
        print("  " + f, file=sys.stderr)


if __name__ == "__main__":
    main()
