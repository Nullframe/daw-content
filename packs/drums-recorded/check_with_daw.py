#!/usr/bin/env python3
"""Run daw's own one-shot checks over a built pack (curation aid; needs a voyager-daw binary).

    python3 check_with_daw.py OUT --daw path/to/voyager-daw [--work DIR] [--json checks.json]

Wraps every file of OUT/drums-recorded-cc0.json in a throwaway recipe pack whose recipe only
imports the file (`audio import FILE --warp off`), then runs `voyager-daw library render-pack`
on it: the same checks factory packs pass (finite, clipping, hits, truncated, dc, true peak,
length) and the same flags (thin/weight, tail, partial, tonal, cut, harsh noise). Failures are
duds to drop (curation.json "drop"); flags are read one by one. Prints a summary and writes
every file's check block to --json.
"""

import argparse
import collections
import json
import math
import os
import subprocess
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--daw", default="voyager-daw")
    ap.add_argument("--work", default="/tmp/drums-recorded-check")
    ap.add_argument("--json")
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    m = json.load(open(os.path.join(out, "drums-recorded-cc0.json")))
    pack = os.path.join(a.work, "checkpack")
    os.makedirs(pack, exist_ok=True)
    samples = []
    for f in m["files"]:
        d = f["measure"]["duration_s"]
        samples.append({
            "name": f["name"], "category": f["category"], "recipe": "imp.cmds",
            "approach": "resampled", "source": ["recorded"], "length": d, "ucs": "none",
            "standard": "none",
            "vars": {"file": os.path.join(out, f["file"]), "bars": math.ceil((d + 0.6) / 2.0)},
        })
    json.dump({"name": "checkpack", "description": "daw checks over a recorded pack",
               "license": "CC0-1.0", "author": "check", "defaults": {"bpm": 120},
               "samples": samples}, open(os.path.join(pack, "pack.json"), "w"), indent=1)
    with open(os.path.join(pack, "imp.cmds"), "w") as f:
        f.write("section add a --bars {{bars}}\ntrack add main\n"
                "audio import {{file}} --track main --at 1:1 --warp off\n")
    env = dict(os.environ, DAW_HOME=os.path.join(a.work, "home"))
    subprocess.run([a.daw, "library", "render-pack", pack, "-j", str(os.cpu_count() or 2)],
                   env=env, check=False, stdout=subprocess.DEVNULL)
    ix = json.load(open(os.path.join(a.work, "home/samples/checkpack/index.json")))
    flags = collections.defaultdict(list)
    failed = []
    checks = {}
    for s in ix["samples"]:
        checks[s["name"]] = s["check"]
        if not s["ok"]:
            failed.append((s["name"], [x["check"] for x in s["check"].get("failures", [])]))
        for x in s["check"].get("flags", []):
            flags[x["check"]].append(s["name"])
    print(f"{len(ix['samples'])} checked, {len(failed)} failed")
    for n, why in failed:
        print(f"  FAIL {n}: {', '.join(why)}")
    for k, v in sorted(flags.items()):
        print(f"  flag {k} ({len(v)}): {' '.join(v)}")
    if a.json:
        json.dump(checks, open(a.json, "w"), indent=1, sort_keys=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
