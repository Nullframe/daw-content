#!/usr/bin/env python3
"""Pick the drum and percussion hits for the recorded CC0 drum pack and write recipes.json.

Run once, by hand, against local checkouts of the upstream repositories (their commits are
pinned below). It records, for every output sample, which upstream files are mixed into it
(multi-mic libraries: close, overhead, resonant-head mics), at what gain, and each upstream
file's sha256, so build.py can rebuild the pack byte for byte from the pinned sources.

    python3 select.py --src vcsl=~/src/vcsl --src big-rusty=~/src/karoryfer.big-rusty-drums \
        --src swirly=~/src/karoryfer.swirly-drums > recipes.json

Curation (what is kept, what is dropped and why, the kits) is in this file and in
curation.json; nothing here is audio.
"""

import argparse
import hashlib
import json
import os
import re
import sys

SOURCES = {
    "vcsl": {
        "repo": "sgossner/VCSL",
        "commit": "c1ea7bcc3c7309650ab0da9d15c9cd1fbc4a4c7e",
        "name": "Versilian Community Sample Library (VCSL)",
        "author": "Versilian Studios LLC (Sam Gossner) and contributors",
        "license": "CC0-1.0",
        "license_url": "https://github.com/sgossner/VCSL/blob/c1ea7bcc3c7309650ab0da9d15c9cd1fbc4a4c7e/LICENSE",
        "page": "https://versilian-studios.com/vcsl/",
    },
    "big-rusty": {
        "repo": "sfzinstruments/karoryfer.big-rusty-drums",
        "commit": "f07ce00df34a46b6b08375be56fe116cf15782bc",
        "name": "Big Rusty Drums",
        "author": "Karoryfer Samples",
        "license": "CC0-1.0",
        "license_url": "https://github.com/sfzinstruments/karoryfer.big-rusty-drums/blob/f07ce00df34a46b6b08375be56fe116cf15782bc/LICENSE",
        "page": "https://shop.karoryfer.com/pages/free-samples",
    },
    "swirly": {
        "repo": "sfzinstruments/karoryfer.swirly-drums",
        "commit": "c40dafe0011cb2e54c0c220ff0fa308a11fc60f5",
        "name": "Swirly Drums",
        "author": "Karoryfer Samples",
        "license": "CC0-1.0",
        "license_url": "https://github.com/sfzinstruments/karoryfer.swirly-drums/blob/c40dafe0011cb2e54c0c220ff0fa308a11fc60f5/license",
        "page": "https://shop.karoryfer.com/pages/free-samples",
    },
}

# Mic mixes. Big Rusty Drums' own SFZ defaults: close 100, overhead 70 (amplitude %), which we
# keep; the kick's overhead (off by default) and the snare's bottom mic add some room and wire.
BR_TOM = [("cl", 1.0), ("oh", 0.7)]
BR_KICK = [("kick", 1.0), ("oh", 0.5)]
BR_SNARE = [("top", 1.0), ("btm", 0.45), ("oh", 0.7)]
BR_SIDESTICK = [("top", 1.0), ("oh", 0.7)]
BR_CYM = [("cl", 0.8), ("oh", 1.0)]
# Hats: closer (the overheads make a closed hat ring past 0.4 s).
BR_HAT = [("cl", 1.0), ("oh", 0.45)]

VCSL_MEM = "Membranophones/Struck Membranophones"
VCSL_IDI = "Idiophones/Struck Idiophones"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


class Picker:
    def __init__(self, roots):
        self.roots = roots
        self.samples = []
        self.names = set()

    def src(self, lib, rel, gain=1.0):
        path = os.path.join(self.roots[lib], rel)
        if not os.path.isfile(path):
            sys.exit(f"missing upstream file: {lib}:{rel}")
        return {"lib": lib, "path": rel, "sha256": sha256(path), "gain": gain}

    def add(self, name, category, sources, instrument, uses, tags=(), dynamic=None, group=None,
            max_len_s=None, articulation=None):
        assert re.fullmatch(r"[a-z0-9-]+", name), name
        assert name not in self.names, name
        self.names.add(name)
        s = {
            "name": name,
            "category": category,
            "instrument": instrument,
            "sources": sources,
            "uses": list(dict.fromkeys(uses)),
            "tags": list(tags),
            # Round-robin group: takes of the same stroke at the same dynamic are level-matched
            # together and play as one kit pad.
            "group": group or re.sub(r"-rr\d+$", "", name),
        }
        if dynamic:
            s["dynamic"] = dynamic
        if articulation:
            s["articulation"] = articulation
        if max_len_s:
            s["max_len_s"] = max_len_s
        self.samples.append(s)

    # Karoryfer: <dir>/<mic>/<prefix>_vl<V>_rr<R>.flac, one file per mic.
    def br(self, base, prefix, vl, rrs, mics, name, category, instrument, uses, tags, dynamic,
           max_len_s=None, articulation=None):
        for rr in rrs:
            srcs = [self.src("big-rusty", f"Samples/{base}/{mic}/{prefix}_vl{vl}_rr{rr}.flac", g)
                    for mic, g in mics]
            self.add(f"{name}-rr{rr}", category, srcs, instrument, uses, tags, dynamic,
                     max_len_s=max_len_s, articulation=articulation)

    # Swirly: Samples/<dir>/<dir>_vl<V>_rr<R>[_<mic>].wav
    def sw(self, folder, vl, rrs, mics, name, category, instrument, uses, tags, dynamic):
        for rr in rrs:
            if mics:
                srcs = [self.src("swirly", f"Samples/{folder}/{folder}_vl{vl}_rr{rr}_{mic}.wav", g)
                        for mic, g in mics]
            else:
                srcs = [self.src("swirly", f"Samples/{folder}/{folder}_vl{vl}_rr{rr}.wav")]
            self.add(f"{name}-rr{rr}", category, srcs, instrument, uses, tags, dynamic)

    def vc(self, rel, name, category, instrument, uses, tags=(), dynamic=None, group=None,
           max_len_s=None, articulation=None):
        self.add(name, category, [self.src("vcsl", rel)], instrument, uses, tags, dynamic, group,
                 max_len_s, articulation)


T = ("trailer", "cinematic")
O = ("orchestral", "cinematic")
A = ("acoustic",)
L = ("launch",)


def pick(p):
    # ---- Big toms (Big Rusty Drums: 22, 18, 15 and 14 inch, mallets and sticks) ----
    for size, vls in (("22", (7, 5)), ("18", (7, 5)), ("15", (7,)), ("14", (7,))):
        for vl in vls:
            dyn = "ff" if vl == vls[0] else "mf"
            p.br(f"tom_{size}/mallet", f"t{size}_m", vl, (1, 2, 3, 4), BR_TOM,
                 f"tom-{size}in-mallet-{dyn}", "tom", f"{size}-inch tom, felt mallets",
                 T + L, ("big", "tom", "mallet", "taiko-like" if size in ("22", "18") else "tom"),
                 dyn, articulation="mallet")
    for size, vl in (("22", 7), ("18", 8), ("15", 7), ("14", 6)):
        p.br(f"tom_{size}/center", f"t{size}", vl, (1, 2, 3, 4), BR_TOM,
             f"tom-{size}in-stick-ff", "tom", f"{size}-inch tom, sticks", A + T + L,
             ("tom", "stick"), "ff", articulation="stick")
    # ---- Kicks ----
    for vl, dyn in ((14, "ff"), (10, "mf")):
        p.br("kick_24/kick", "k", vl, (1, 2, 3, 4), BR_KICK, f"kick-24in-{dyn}", "kick",
             "24-inch kick, felt beater, damped", A + L, ("kick", "acoustic"), dyn)
    for vl, dyn in ((6, "ff"), (4, "mf")):
        p.br("kick_24_nodamp/kick", "k_nodamp", vl, (1, 2, 3, 4), BR_KICK, f"kick-24in-open-{dyn}", "kick",
             "24-inch kick, undamped (open, boomy)", A + T + L, ("kick", "open", "boomy"), dyn,
             max_len_s=2.5)
    # ---- Snare 14" ----
    for vl, dyn in ((10, "ff"), (7, "mf")):
        p.br("snare_14/center", "sn_center", vl, (1, 2, 3, 4), BR_SNARE, f"snare-14in-{dyn}", "snare",
             "14-inch snare, centre hits", A + L, ("snare",), dyn)
    p.br("snare_14/rimshot", "sn_rims", 6, (1, 2, 3, 4), BR_SNARE, "snare-14in-rimshot-ff", "snare",
         "14-inch snare, rimshots", A + T + L, ("snare", "rimshot", "crack"), "ff",
         articulation="rimshot")
    p.br("snare_14/sidestick", "sn_ss", 4, (1, 2, 3, 4), BR_SIDESTICK, "rim-sidestick-f", "rim",
         "14-inch snare, side stick", A + L, ("rim", "sidestick"), "f", articulation="sidestick")
    # ---- Cymbals and hats (Big Rusty) ----
    for vl, dyn in ((5, "ff"), (4, "f")):
        p.br("crash_17/cr", "cr", vl, (1, 2, 3, 4), BR_CYM, f"crash-17in-{dyn}", "crash",
             "17-inch crash, sticks", A + L, ("crash",), dyn, max_len_s=6.0)
    p.br("crash_17/mallet", "cr_m", 4, (1, 2, 3, 4), BR_CYM, "crash-17in-mallet-ff", "crash",
         "17-inch crash, mallets (a soft-attack swell hit)", T + A, ("crash", "mallet", "swell"),
         "ff", max_len_s=6.0, articulation="mallet")
    for vl, dyn in ((10, "f"), (7, "mf")):
        p.br("ride_22/rd", "rd", vl, (1, 2, 3), BR_CYM, f"ride-22in-{dyn}", "ride",
             "22-inch ride, bow", A, ("ride",), dyn, max_len_s=5.0)
    for vl, dyn in ((6, "f"), (4, "mf")):
        p.br("hihat_14/cl", "ht_cl", vl, (1, 2, 3, 4), BR_HAT, f"hat-closed-14in-{dyn}",
             "hat-closed", "14-inch hi-hat, closed", A + L, ("hat", "closed"), dyn)
    p.br("hihat_14/ho", "ht_ho", 4, (1, 2, 3, 4), BR_HAT, "hat-open-14in-f", "hat-open",
         "14-inch hi-hat, open", A + L, ("hat", "open"), "f", max_len_s=3.0)
    p.br("hihat_14/chik", "ht_chik", 5, (1, 2, 3, 4), BR_HAT, "hat-pedal-14in-f", "hat-pedal",
         "14-inch hi-hat, foot chick", A, ("hat", "pedal"), "f")

    # ---- Swirly Drums: marching bass drum (beater + resonant head), floor tom, hand drums ----
    for vl, dyn in ((22, "ff"), (18, "f")):
        p.sw("marching_kick", vl, (1, 2, 3, 4), [("beater", 1.0), ("reso", 1.0)],
             f"bass-drum-marching-{dyn}", "bass-drum", "marching bass drum", T + O + L,
             ("bass-drum", "marching", "big"), dyn)
    p.sw("tom_floor", 12, (1, 2, 3, 4), None, "tom-floor-ff", "tom", "floor tom, sticks", A + T,
         ("tom", "floor"), "ff")
    p.sw("djembe", 12, (1, 2, 3, 4), None, "djembe-ff", "perc", "djembe", A + L,
         ("hand-drum", "djembe", "world"), "ff")
    p.sw("darbouka", 12, (1, 2, 3, 4), None, "darbouka-ff", "perc", "darbouka (doumbek)", A + L,
         ("hand-drum", "darbuka", "world"), "ff")
    p.sw("lbongo", 10, (1, 2, 3, 4), None, "bongo-low-ff", "perc", "bongo, low", A + L,
         ("hand-drum", "bongo"), "ff")
    p.sw("hbongo", 10, (1, 2, 3, 4), None, "bongo-high-ff", "perc", "bongo, high", A + L,
         ("hand-drum", "bongo"), "ff")
    p.sw("cowbell", 9, (1, 2, 3, 4), None, "cowbell-f", "perc", "cowbell", A + L,
         ("cowbell", "metal"), "f")

    # ---- VCSL: orchestral bass drums ----
    for v in (7, 5):
        dyn = {7: "ff", 5: "f"}[v]
        for rr in (1, 2):
            p.vc(f"{VCSL_MEM}/Bass Drum 1/BDrumNew_hit_v{v}_rr{rr}_Sum.wav",
                 f"bass-drum-concert-a-{dyn}-rr{rr}", "bass-drum", "concert bass drum (A)", O + T,
                 ("bass-drum", "concert", "big"), dyn)
    for f, dyn, rr in (("hit_ff", "ff", 1), ("hit_f", "f", 1), ("hit_mf1", "mf", 1),
                       ("hit_mf2", "mf", 2)):
        p.vc(f"{VCSL_MEM}/Bass Drum 2/bassdrum_{f}.wav", f"bass-drum-concert-b-{dyn}-rr{rr}",
             "bass-drum", "concert bass drum (B)", O + T, ("bass-drum", "concert", "big"), dyn)
    for f, name in (("bdrum_fff_rr1", "fff-rr1"), ("bdrum_fff_rr2", "fff-rr2"),
                    ("bdrum_ff_rr1", "ff-rr1"), ("bdrum3_fff_rr1", "fff-rr3")):
        p.vc(f"{VCSL_MEM}/Bass Drum 3 - Legacy/{f}.wav", f"bass-drum-concert-c-{name}",
             "bass-drum", "concert bass drum (C)", O + T, ("bass-drum", "concert", "big"),
             name.split("-")[0], group=f"bass-drum-concert-c-{name.split('-')[0]}")
    for rr in (1, 2):
        p.vc(f"{VCSL_MEM}/Bass Drum 3 - Legacy/bdrum_muted_fff_rr{rr}.wav",
             f"bass-drum-concert-muted-fff-rr{rr}", "bass-drum", "concert bass drum, muted",
             O + T, ("bass-drum", "concert", "muted", "tight"), "fff")
    for f in ("cresc_short", "cresc_med"):
        p.vc(f"{VCSL_MEM}/Bass Drum 2/bassdrum_{f}.wav", f"roll-bass-drum-{f.replace('_', '-')}",
             "roll", "concert bass drum, crescendo roll", O + T, ("roll", "swell", "bass-drum"),
             group=f"roll-bass-drum-{f.replace('_', '-')}", max_len_s=10.0)

    # ---- VCSL: timpani ----
    for drum in range(1, 6):
        for rr in (1, 2):
            p.vc(f"{VCSL_MEM}/Timpani 1/Hit/Timpani{drum}_Hit_v4_rr{rr}_Sum.wav",
                 f"timpani-a{drum}-ff-rr{rr}", "timpani", f"timpani (set 1), drum {drum}", O + T,
                 ("timpani", "orchestral", "tonal"), "ff", max_len_s=5.0)
    timp2 = sorted({m.group(1) for m in (re.match(r"(Timpani\d[A-Z])_hit_v5_rr1_main\.wav$", f)
                    for f in os.listdir(os.path.join(p.roots["vcsl"], VCSL_MEM, "Timpani 2/Hit")))
                    if m})
    for t in timp2:
        n = t.replace("Timpani", "").lower()
        p.vc(f"{VCSL_MEM}/Timpani 2/Hit/{t}_hit_v5_rr1_main.wav", f"timpani-b{n}-ff",
             "timpani", f"timpani (set 2), drum {n[0]} note {n[1].upper()}", O + T,
             ("timpani", "orchestral", "tonal"), "ff", group=f"timpani-b{n}", max_len_s=5.0)
    for drum in (1, 2, 3, 4):
        p.vc(f"{VCSL_MEM}/Timpani 1/Roll/Timpani{drum}_Roll_v5_rr1_Sum.wav",
             f"roll-timpani-{drum}-ff", "roll", f"timpani roll, drum {drum}", O + T,
             ("roll", "timpani"), "ff", group=f"roll-timpani-{drum}", max_len_s=10.0)

    # ---- VCSL: toms, frame drums, snares ----
    for tom in (1, 2):
        pre = "TomH" if tom == 1 else "TomL"
        folder = f"{VCSL_MEM}/Tom {tom}/Mallet"
        files = sorted(f for f in os.listdir(os.path.join(p.roots["vcsl"], folder))
                       if re.match(rf"{pre}_HitM_v4_rr\d_Mid\.wav$", f))
        for i, f in enumerate(files, 1):
            p.vc(f"{folder}/{f}", f"tom-concert-{'high' if tom == 1 else 'low'}-mallet-ff-rr{i}",
                 "tom", f"concert tom ({'high' if tom == 1 else 'low'}), mallets", O + T,
                 ("tom", "concert", "mallet"), "ff", articulation="mallet")
    for side, folder in (("low", "tenor_lower"), ("high", "tenor_higher")):
        for rr in (1, 2, 3):
            pre = "tenor" if side == "low" else "tenorH"
            p.vc(f"{VCSL_MEM}/Legacy Toms/{folder}/{pre}_fff_rr{rr}.wav",
                 f"tom-tenor-{side}-fff-rr{rr}", "tom", f"marching tenor drum ({side})", O + T,
                 ("tom", "marching", "tenor"), "fff")
    for size, lab in (("L", "large"), ("S", "small")):
        for rr in (1, 2):
            p.vc(f"{VCSL_MEM}/Frame Drum/HDrum{size}_Hit_v3_rr{rr}_Sum.wav",
                 f"frame-drum-{lab}-f-rr{rr}", "frame-drum", f"frame drum ({lab})", T + O + A,
                 ("frame-drum", "hand-drum", "taiko-like" if size == "L" else "frame-drum"), "f")
            p.vc(f"{VCSL_MEM}/Frame Drum/HDrum{size}_HitMuted_v3_rr{rr}_Sum.wav",
                 f"frame-drum-{lab}-muted-f-rr{rr}", "frame-drum", f"frame drum ({lab}), muted",
                 T + O + A, ("frame-drum", "hand-drum", "muted", "tight"), "f")
    for rr in (1, 2):
        p.vc(f"{VCSL_MEM}/Snare Drum, Modern 1/Snare2_HitSN_v9_rr{rr}_Mid.wav",
             f"snare-concert-ff-rr{rr}", "snare", "concert snare, snares on", O + T,
             ("snare", "concert"), "ff")
        p.vc(f"{VCSL_MEM}/Snare Drum, Modern 1/Snare2_HitNS_v6_rr{rr}_Mid.wav",
             f"snare-concert-snares-off-ff-rr{rr}", "snare", "concert snare, snares off", O + T,
             ("snare", "concert", "snares-off", "tom-like"), "ff")
    for f, rr in (("snare3_fff_rr1", 1), ("snare3_f_rr1", 2), ("snare3_f_rr2", 3)):
        p.vc(f"{VCSL_MEM}/Legacy Snares/drum3_marching/{f}.wav", f"snare-field-f-rr{rr}", "snare",
             "field (marching) snare", O + T, ("snare", "marching", "field-drum"), "f",
             group="snare-field-f")
    for f in sorted(os.listdir(os.path.join(p.roots["vcsl"], VCSL_MEM, "Snare Drum, Modern 1"))):
        m = re.match(r"Snare2_rollSN_v(\d)_rr1_Mid\.wav$", f)
        if m and m.group(1) in ("4", "6"):
            p.vc(f"{VCSL_MEM}/Snare Drum, Modern 1/{f}", f"roll-snare-concert-v{m.group(1)}",
                 "roll", "concert snare roll", O + T, ("roll", "snare"), max_len_s=10.0)

    # ---- VCSL: orchestral cymbals, swells, gong ----
    for n, fs in ((1, ("hit_fff1", "hit_f1")), (2, ("hit_fff1", "hit_f1"))):
        for f in fs:
            dyn = f.split("_")[1][:-1]
            p.vc(f"{VCSL_IDI}/Suspended Cymbal {n}/susCymb{n}_{f}.wav",
                 f"crash-suspended-{n}-{dyn}", "crash", f"suspended cymbal {n}, mallet", O + T,
                 ("crash", "suspended", "orchestral"), dyn, group=f"crash-suspended-{dyn}",
                 max_len_s=8.0)
    for n, fs in ((1, ("cresc_1.5s", "cresc_2s", "cresc_4s")), (2, ("cresc_2.5s2", "cresc_4s"))):
        for f in fs:
            secs = f.split("_")[1].replace("s2", "s").replace(".", "-")
            p.vc(f"{VCSL_IDI}/Suspended Cymbal {n}/susCymb{n}_{f}.wav",
                 f"cymbal-swell-{n}-{secs}", "cymbal-swell", f"suspended cymbal {n}, mallet roll crescendo",
                 O + T + L, ("swell", "riser", "cymbal", "reverse-like"), group=f"cymbal-swell-{n}-{secs}",
                 max_len_s=12.0)
    for f in ("crash1_ff2", "crash1_ff3"):
        p.vc(f"{VCSL_IDI}/Clash Cymbals 1/cymbal_{f}.wav", f"crash-clash-1-ff-rr{f[-1]}", "crash",
             "clash (hand) cymbals 1", O + T, ("crash", "clash", "orchestral"), "ff", max_len_s=8.0)
    for f in ("crash2_fff1", "crash2_fff2"):
        p.vc(f"{VCSL_IDI}/Clash Cymbals 2/cymbal_{f}.wav", f"crash-clash-2-fff-rr{f[-1]}", "crash",
             "clash (hand) cymbals 2", O + T, ("crash", "clash", "orchestral"), "fff", max_len_s=8.0)
    for f in ("crash1_short1", "crash1_short2"):
        p.vc(f"{VCSL_IDI}/Clash Cymbals 1/cymbal_{f}.wav", f"crash-clash-choked-rr{f[-1]}", "crash",
             "clash cymbals, choked", O + T + L, ("crash", "clash", "choked", "tight"), "f")
    for f, name in (("gong_fff", "gong-fff"), ("gong_f", "gong-f"), ("gong_2_f", "gong-2-f")):
        p.vc(f"{VCSL_IDI}/Gong 1/{f}.wav", name, "gong", "tam-tam (gong)", O + T,
             ("gong", "tam-tam", "big"), group=name, max_len_s=14.0)

    # ---- VCSL: metal impacts ----
    for h in (1, 2, 3):
        p.vc(f"{VCSL_IDI}/Anvil/Anvil_Hit{h}_v3_rr1_Mid.wav", f"impact-anvil-{h}-ff", "impact",
             "anvil", T + O + L, ("impact", "metal", "anvil"), "ff", group="impact-anvil-ff")
    for f, name in (("BrakeDrum1_Hammer_v3_rr1_Mid", "impact-brake-drum-1-ff"),
                    ("BrakeDrum2_Hammer3_v3_rr1_Mid", "impact-brake-drum-2-ff")):
        p.vc(f"{VCSL_IDI}/Brake Drum/{f}.wav", name, "impact", "brake drum, hammer", T + L,
             ("impact", "metal", "brake-drum"), "ff", group="impact-brake-drum-ff")

    # ---- VCSL: hats (second set), claps, hand and small percussion ----
    for rr in (1, 2):
        p.vc(f"{VCSL_IDI}/Hi-Hat Cymbal/HiHat_HitC_v4_rr{rr}_Mid.wav", f"hat-closed-vcsl-f-rr{rr}",
             "hat-closed", "hi-hat, closed", A, ("hat", "closed"), "f")
        p.vc(f"{VCSL_IDI}/Hi-Hat Cymbal/HiHat_HitO_rr{rr}_Mid.wav", f"hat-open-vcsl-f-rr{rr}",
             "hat-open", "hi-hat, open", A, ("hat", "open"), "f", max_len_s=3.0)
        p.vc(f"{VCSL_IDI}/Hi-Hat Cymbal/HiHat_Close_rr{rr}_Mid.wav", f"hat-pedal-vcsl-rr{rr}",
             "hat-pedal", "hi-hat, pedal close", A, ("hat", "pedal"))
    for rr in range(1, 7):
        p.vc(f"{VCSL_IDI}/Claps/Clap_rr{rr}.wav", f"clap-group-rr{rr}", "clap", "hand claps (group)",
             A + L + T, ("clap", "group", "organic"))
    for rr in (1, 2, 3):
        p.vc(f"{VCSL_IDI}/Slapstick/slapstick_rr{rr}.wav", f"slapstick-f-rr{rr}", "clap",
             "slapstick (whip)", O + T + L, ("slapstick", "whip", "crack"), "f")
    for rr in (1, 2):
        p.vc(f"{VCSL_IDI}/Woodblock/wood_click_f_rr{rr}.wav", f"woodblock-f-rr{rr}", "perc",
             "woodblock", O + A + L, ("woodblock", "click", "wood"), "f")
    for n in (1, 2):
        p.vc(f"{VCSL_IDI}/Claves/Claves{n}_Hit_v3_rr1_Mid.wav", f"claves-{n}-f", "perc", "claves",
             A + L + O, ("claves", "click", "wood"), "f", group="claves-f")
    for n in (1, 2):
        p.vc(f"{VCSL_IDI}/Tambourine {n}/Tamb{n}_Hit_v2_rr{1 if n == 1 else 2}_Mid.wav",
             f"tambourine-{n}-f", "perc", "tambourine", O + A + L, ("tambourine", "jingle"), "f",
             group="tambourine-f")
    for rr in (1, 2):
        p.vc(f"{VCSL_IDI}/Shaker, Small/Mid_Shaker_Slap_rr{rr}.wav", f"shaker-slap-rr{rr}", "perc",
             "shaker, slap", A + L, ("shaker",))
    for f, name in (("Cajon_hit1_fff", "cajon-bass-fff"), ("Cajon_hit3_f", "cajon-slap-f")):
        for rr in (1, 2):
            p.vc(f"{VCSL_IDI}/Cajon/{f}_rr{rr}.wav", f"{name}-rr{rr}", "perc", "cajon", A + L,
                 ("cajon", "hand-drum", "wood"), name.rsplit("-", 1)[1])
    for drum, lab in (("Conga", "conga"), ("Quinto", "quinto"), ("Tumba", "tumba")):
        for rr in (1, 2):
            rel = f"{VCSL_MEM}/Conga/{drum}_HitN_v3_rr{rr}_Sum.wav"
            if not os.path.isfile(os.path.join(p.roots["vcsl"], rel)):
                rel = f"{VCSL_MEM}/Conga/{drum}_HitN_v2_rr{rr}_Sum.wav"
            if os.path.isfile(os.path.join(p.roots["vcsl"], rel)):
                p.vc(rel, f"conga-{lab}-f-rr{rr}", "perc", f"conga ({lab}), open tone", A + L,
                     ("conga", "hand-drum", "latin"), "f")
    for rr in (1, 2):
        p.vc(f"{VCSL_IDI}/Triangles/Triangle1_Hit_v2_rr{rr}_Mid.wav", f"triangle-f-rr{rr}", "perc",
             "triangle", O + A, ("triangle", "metal", "bright"), "f", max_len_s=6.0)
    for side in ("Hi", "Lo"):
        p.vc(f"{VCSL_IDI}/Slit Drum/LogDrum{side}_MedM_v3_rr1_Sum.wav",
             f"log-drum-{side.lower()}-f", "perc", f"slit (log) drum, {side.lower()}", A + T,
             ("log-drum", "wood", "tonal"), "f")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", action="append", default=[], help="lib=path of a local checkout")
    a = ap.parse_args()
    roots = {}
    for s in a.src:
        k, v = s.split("=", 1)
        roots[k] = os.path.expanduser(v)
    missing = set(SOURCES) - set(roots)
    if missing:
        sys.exit(f"need --src for {sorted(missing)}")
    p = Picker(roots)
    pick(p)
    json.dump({"sources": SOURCES, "samples": p.samples}, sys.stdout, indent=1)
    sys.stdout.write("\n")
    print(f"{len(p.samples)} samples", file=sys.stderr)


if __name__ == "__main__":
    main()
