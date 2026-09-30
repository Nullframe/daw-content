#!/usr/bin/env python3
"""NOTICES.md for a real-rooms release: python3 notices.py OUT_DIR (after build.py)."""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
out = Path(sys.argv[1])
rec = json.loads((HERE / "recipes.json").read_text())["irs"]
meas = json.loads((out / "measurements.json").read_text())
L = []
w = L.append
w("# Real rooms IR pack: notices and provenance\n")
w("Recorded impulse responses of real spaces, conditioned for daw's `convolution@1`. Every file is "
  "a **modified** version of the upstream recording: DC removed, reduced to at most two channels "
  "(B-format recordings: the omnidirectional W channel), resampled to 48 kHz, trimmed to 0.5 ms "
  "before the direct sound, tail cut where it meets the noise floor (100 ms fade, at most 10 s), "
  "peak-normalised to -1 dBFS, written as 24-bit WAV. `provenance.json` has the exact upstream URL "
  "and the sha256 of every upstream file; `build.py` in "
  "[Nullframe/daw-content/packs/real-rooms](https://github.com/Nullframe/daw-content/tree/main/packs/real-rooms) "
  "reproduces the pack.\n")
w("Licences: CC BY 4.0, CC BY 3.0 and MIT. All allow commercial use, modification and "
  "redistribution. **CC BY files require attribution**: credit them as below when you "
  "redistribute the IRs themselves. Audio you process through them is your own work; crediting "
  "the spaces in a release is a courtesy.\n")
groups = {}
for e in rec:
    groups.setdefault(e["collection"], []).append(e)
about = {
 "OpenAIR": ("OpenAIR, the Open Acoustic Impulse Response Library, AudioLab, University of York (https://www.openair.hosted.york.ac.uk/). Files from https://webfiles.york.ac.uk/OPENAIR/IRs/.",
             "CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/), as each space's OpenAIR page states (\"This work is licensed under a Creative Commons Attribution 4.0 International License\"). Checked 2026-09-30: the OpenAIR website was suspended that day, so the per-page statement was confirmed through search-engine copies of each page listed below and through audEERING's public redistribution of OpenAIR (`openair` 1.0.0: license CC-BY-4.0, usage commercial). Only spaces confirmed both ways are included."),
 "AIR": ("Aachen Impulse Response (AIR) database v1.4, Institute of Communication Systems (IKS), RWTH Aachen University: M. Jeub, M. Schäfer, P. Vary et al. (https://www.iks.rwth-aachen.de/en/research/tools-downloads/databases/aachen-impulse-response-database/). Files from audEERING's public mirror (`air` 1.4.0), because the official archive sits under a path the IKS robots.txt disallows.",
         "MIT (\"For license information see the included MIT license file.\", IKS page, checked 2026-09-30). The licence text is below."),
 "DetmoldSRIR": ("Open Database of Spatial Room Impulse Responses at Detmold University of Music (https://zenodo.org/records/4116247), `DetmoldSRIR_v01.zip`, by the authors listed on that record.",
                 "CC BY 4.0 (Zenodo record licence, checked 2026-09-30)."),
 "MaidaVale": ("BBC Maida Vale Impulse Response Dataset (https://zenodo.org/records/10020866), measured by researchers from the University of York (led by Prof Gavin Kearney and Prof Helena Daffern) and BBC R&D; cite Kearney, Daffern et al. as the record asks.",
               "CC BY 3.0 (Zenodo record licence, checked 2026-09-30)."),
}
for g, es in groups.items():
    src, lic = about[g]
    w(f"## {g}\n\nSource: {src}\n\nLicence: {lic}\n")
    w("| File | Space | Upstream file | Page |\n|---|---|---|---|")
    for e in es:
        up = e["url"] + (f" → `{e['member']}`" if "member" in e else "")
        w(f"| `{e['file']}` | {e['name']} | {up} | {e['source']} |")
    w("")
w("## MIT licence (AIR files)\n")
w("The official archive's LICENSE file could not be copied (robots.txt). This is the MIT licence "
  "the IKS states, with the database authors as the copyright holders:\n")
w("""```
Copyright (c) Marco Jeub, Magnus Schäfer, Hauke Krüger, Christoph Matthias Nelke,
Christophe Beaugeant, Peter Vary; Institute of Communication Systems, RWTH Aachen University

Permission is hereby granted, free of charge, to any person obtaining a copy of this software
and associated documentation files (the "Software"), to deal in the Software without
restriction, including without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or
substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
```
""")
w("## Measurements\n\n| File | RT60 (s) | EDT (s) | Length (s) |\n|---|---|---|---|")
for e in rec:
    m = meas[e["file"]]
    w(f"| `{e['file']}` | {m['rt60_s']} | {m['edt_s']} | {m['len_s']} |")
(out / "NOTICES.md").write_text("\n".join(L) + "\n")
