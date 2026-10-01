# Orchestral (CC0)

`voyager-daw library install orchestral-cc0` installs a recorded orchestra for daw's `sampler@1`
from an `orchestral-cc0-<date>` release: `instrument/orchestral-cc0@1`, one archive with 56 named
zone maps (articulations), played by daw's `sampler@1/<articulation>-cc0` presets. It is built by
[`build-orchestral`](../../.github/workflows/build-orchestral.yml) from the upstream recordings
pinned in [`recipes.json`](recipes.json). **No audio is committed.**

Why: synthesis gets bowed strings and brass to *usable*, not to *great*; a recorded orchestra is
the route for orchestral, cinematic and trailer music (daw's
`docs/research/timbre-coverage.md`). Founder decision: an on-demand CC0 pack from VSCO 2 CE and
VCSL; no CC-BY or non-commercial content; choir and guitars stay synthesized.

## Sources and licences

Only CC0 sources, each checked at the pinned commit (the LICENSE file) on 2026-10-01:

| Library | Author | Upstream (pinned commit) | Licence |
|---|---|---|---|
| VS Chamber Orchestra: Community Edition (VSCO 2 CE) | Versilian Studios LLC (Sam Gossner), Ivy Audio (Simon Dalzell); sample cutting by Elan Hickler | [sgossner/VSCO-2-CE](https://github.com/sgossner/VSCO-2-CE) `440300901dfe9275fd84e0b7763af1f8443ae62e` | CC0-1.0 (`LICENSE`). Its `Readme.txt` asks for credit and a link to the VSCO: CE homepage; a request, not a condition. We give it in `NOTICE.txt` and `NOTICES.md`. |
| Versilian Community Sample Library (VCSL) | Versilian Studios LLC and contributors | [sgossner/VCSL](https://github.com/sgossner/VCSL) `c1ea7bcc3c7309650ab0da9d15c9cd1fbc4a4c7e` | CC0-1.0 (`LICENSE`; the README: "no royalties, no credit, no special terms") |

The archive carries both licence texts and readmes (`licenses/`) and a `NOTICE.txt`;
`provenance.json` has, per file, the upstream repository, commit, path and sha256, and the
processing and measurements.

## What is in it

| Family | Articulations | Source |
|---|---|---|
| Strings | violins, violas, celli (sections), double bass (solo), solo violin: sustain (vibrato), spiccato, pizzicato, tremolo; `strings-*`: the four split by range on one track | VSCO 2 CE |
| Brass | horn, trumpet, tenor trombone, tuba: sustain, staccato; muted horn and trumpet; `brass-*`: split by range | VSCO 2 CE |
| Woodwinds | flute, oboe, clarinet, bassoon: sustain, staccato; flute and oboe without vibrato; `winds-*`: split by range | VSCO 2 CE |
| Harp | concert harp (2 layers) | VCSL |
| Mallets | glockenspiel, xylophone (hard mallets), marimba, vibraphone (soft and hard mallets; bowed), tubular bells | VCSL |
| Percussion | mark tree, bell tree, sleigh bells, finger cymbals, ratchets, one per key from C4 | VCSL |

VCSL's drums and orchestral percussion (timpani, bass drums, cymbals, gongs, triangles ...) are in
`drums-recorded-cc0` and are not repeated. Not available as CC0: a celesta, brass or woodwind
sections (VSCO's are solo players), a double-bass section, legato transitions, true brass swells
(daw's `*-swell-cc0` presets are the sustains with a slow attack).

1,624 files, 431,769,600 bytes (the tar), 44.1 kHz at the source bit depth (mostly 16-bit).

## How it is built

`pick.py` reads local checkouts of both libraries and writes `recipes.json`: every upstream file
with its sha256, sounding root note, velocity layer and round robin, and the ensembles' splits.
**Both libraries name most folders one octave below the sounding pitch** (VSCO's "C4" sounds C5;
the bassoon's "A#0" is its lowest B-flat, B-flat 1): `pick.py` checks the octave of every sample
against its odd-harmonic series and records the sounding root; VSCO's solo violin (sustain and
pizzicato), the VCSL harp and tubular bells are named at pitch. Seven readings more than 50 cents
off their name are listed under `flagged` for review (weak or noisy fundamentals at the edge of the
search; the roots stay as named, and `build.py` retunes only within 40 cents).

`build.py` rebuilds everything from `recipes.json`: a sparse git checkout of each library at its
pinned commit, every file checked against its sha256; trimmed to the onset (a short pre-roll and a
raised-cosine fade-in) and to the decay into its noise floor (raised-cosine fade-out); sustains and
tremolos loop in their steady part, the end matched to the start by cross-correlation, the
crossfade baked into the file (equal power for uncorrelated material, linear for correlated), the
file ending at the loop end; lossless otherwise (the kept frames are the upstream samples, FLAC at
the source rate and bit depth). It measures tuning (a partials fit; corrected with `tune_st` within
40 cents, for sustains, plucks and mallets), loudness and peaks, and writes the zone maps: key
ranges between recorded roots (stretched four semitones past the recorded range), velocity layers
split evenly, notes in a layer evened to a smooth curve over pitch, round robins level-matched,
adjacent layers 1-9 dB apart and meeting at the same loudness (`vel_db`), every articulation equally
loud at full velocity. The same inputs give the same bytes (pinned numpy, scipy, soundfile; fixed
tar metadata).

## Rebuilding and publishing

```sh
pip install numpy==2.4.6 scipy==1.17.1 soundfile==0.14.0
python3 build.py OUT --tag orchestral-cc0-<date>          # fetches the pinned upstream files
python3 pick.py --vsco PATH --vcsl PATH                    # only to change the selection
```

1. A pull request touching this folder builds and checks the archive against the sha256 daw pins
   (`SHA_ORCHESTRAL` in the workflow).
2. To publish, run the workflow by hand with the tag (or push a tag `orchestral-cc0-<date>`). Do
   not replace the assets of a tag daw already pins.
3. In daw: copy the release's `instrument.json` to `content/instruments/orchestral-cc0/` and
   regenerate the presets with `scripts/instruments/orchestral_presets.py`.
