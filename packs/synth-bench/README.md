# Synthesis benchmark reference sounds (CC0)

The reference sounds of daw's synthesis benchmark (`daw-bench synth`, docs/research/synthesis-gaps.md
in daw). 53 targets across what users ask a synth for: drums, cinematic hits and transitions,
tonal instruments, textures, UI/SFX and a few oddballs. Each has a short text description of the
sound, which is all an agent gets in the benchmark's design-from-description track.

They are built by [`build-synth-bench`](../../.github/workflows/build-synth-bench.yml) from the
upstream files pinned in [`recipes.json`](recipes.json) and published as a `synth-bench-<date>`
release. **No audio is committed.**

## Sources and licences

Only CC0 sources, pinned by commit, URL or dataset id, with each upstream file's sha256:

| Library | Upstream | Licence |
|---|---|---|
| Recorded drums (CC0) | this repo's `drums-recorded-cc0-2026-09-30` release (VCSL, Karoryfer) | CC0-1.0 |
| Versilian Community Sample Library (VCSL) | [sgossner/VCSL](https://github.com/sgossner/VCSL) `c1ea7bc` | CC0-1.0 |
| VSCO 2 Community Edition | [sgossner/VSCO-2-CE](https://github.com/sgossner/VSCO-2-CE) `4403009` | CC0-1.0 |
| Sonic Pi sample set | [sonic-pi-net/sonic-pi](https://github.com/sonic-pi-net/sonic-pi) `4a9b201`, `etc/samples` (Freesound CC0 uploads and The Black Dog's CC0 donation; `loop_amen*` not used) | CC0-1.0 |
| Kenney Sci-Fi Sounds, Interface Sounds | kenney.nl (the zips' `License.txt`) | CC0-1.0 |
| FSD50K | [Zenodo 4060432](https://zenodo.org/records/4060432), CC0 clips only, range-read out of the split zip (>= 10 s between requests) | CC0-1.0 per clip (the dataset compilation is CC-BY-4.0) |

Freesound itself is never fetched: its robots.txt and API terms rule that out, so Freesound
sounds come only through FSD50K and Sonic Pi.

## Processing

`build.py` keeps each file's own sample rate and channels (identical channels become mono),
removes a DC offset, trims from 5 ms before the onset to a per-target length or to where it falls
70 dB under its peak, fades both ends, scales to a -1 dBFS peak and writes 24-bit WAV. No EQ,
compression or reverb: the benchmark compares synthesis with the recording as recorded.

## Descriptions

Each target's `description` was written from the source's own metadata (instrument, articulation,
note, the uploader's title and tags) and daw's measurements of the built file (pitch, attack,
decay, stereo correlation, how tonal it is, and how its spectrum moves over time). They say what a
user would ask for, including the note and the approximate length where that matters.
